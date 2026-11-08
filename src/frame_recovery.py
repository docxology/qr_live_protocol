"""Track gaps and late deliveries in a numbered optical frame stream.

The receiver retains a bounded window of missing frame numbers and marks a
frame as recovered when it actually arrives. Callers own payload buffering
and any retransmission requests.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any


class RecoveryDecision(Enum):
    """Action the recovery buffer takes for an arriving frame."""

    ACCEPT = "accept"          # Frame accepted (in-order, no gap)
    DUPLICATE = "duplicate"    # Frame already seen; drop silently
    REORDER = "reorder"        # Frame accepted out-of-order and buffered
    GAP = "gap"                # A missing intermediate frame was detected
    GAP_RECOVERED = "gap_recovered"  # Gap closed via a retransmission


@dataclass
class FrameRecoveryConfig:
    """Configuration for the frame recovery controller."""

    buffer_size: int = 8
    max_gap_tolerance: int = 10
    retransmission_window: int = 4

    def __post_init__(self) -> None:
        """Validate recovery parameters at construction time."""
        if self.buffer_size < 1:
            raise ValueError("buffer_size must be at least 1")
        if self.max_gap_tolerance < 0:
            raise ValueError("max_gap_tolerance must be non-negative")
        if self.retransmission_window < 1:
            raise ValueError("retransmission_window must be at least 1")


@dataclass
class FrameRecoveryStats:
    """Statistics snapshot for the recovery controller."""

    frames_accepted: int = 0
    frames_duplicate: int = 0
    frames_reordered: int = 0
    gaps_detected: int = 0
    gaps_recovered: int = 0
    frames_dropped: int = 0
    recovery_rate: float = 0.0


class FrameRecoveryController:
    """
    Receiver-side fault-tolerant frame ordering and gap recovery.

    The controller watches a stream of frames carrying monotonically
    increasing ``frame_number`` values. Discontinuities are treated as gaps,
    a recovery decision is recorded, and the accepted cursor advances so the
    pipeline can keep flowing without stalling.
    """

    def __init__(self, config: FrameRecoveryConfig | None = None):
        """Initialize the recovery controller with an optional config."""
        self.config = config or FrameRecoveryConfig()
        self._lock = threading.Lock()
        self._last_accepted: int | None = None
        self._pending: dict[int, None] = {}
        self.stats = FrameRecoveryStats()

    @staticmethod
    def _frame_number(frame: object) -> int:
        """Extract an integer frame number from a frame object or int."""
        if isinstance(frame, int):
            return frame
        frame_num = getattr(frame, "frame_number", None)
        if frame_num is None:
            raise ValueError(
                "frame object must be an int or expose a frame_number attribute"
            )
        return int(frame_num)

    def feed_frame(self, frame: object) -> dict[str, Any]:
        """
        Submit a received frame and return a recovery decision record.

        Returns:
            dict with keys: ``frame_number``, ``decision``, ``gap_start`` and
            ``gap_end`` (gap bounds are ``None`` when no gap applies).
        """
        frame_number = self._frame_number(frame)
        if frame_number < 0:
            raise ValueError("frame_number must be non-negative")

        decision = RecoveryDecision.ACCEPT
        gap_start: int | None = None
        gap_end: int | None = None

        with self._lock:
            if frame_number in self._pending:
                del self._pending[frame_number]
                self.stats.frames_accepted += 1
                self.stats.frames_reordered += 1
                self.stats.gaps_recovered += 1
                decision = RecoveryDecision.GAP_RECOVERED
                gap_start = gap_end = frame_number
            elif self._last_accepted is not None and frame_number <= self._last_accepted:
                self.stats.frames_duplicate += 1
                decision = RecoveryDecision.DUPLICATE
            else:
                if self._last_accepted is not None:
                    self._expire_pending(frame_number)
                    gap_size = frame_number - self._last_accepted - 1
                    if gap_size:
                        decision = RecoveryDecision.GAP
                        gap_start = self._last_accepted + 1
                        gap_end = frame_number - 1
                        self._record_gap(gap_start, gap_end, gap_size)
                self._last_accepted = frame_number
                self.stats.frames_accepted += 1

            self._recompute_recovery_rate()

        return {
            "frame_number": frame_number,
            "decision": decision.value,
            "gap_start": gap_start,
            "gap_end": gap_end,
        }

    def _expire_pending(self, frame_number: int) -> None:
        oldest_allowed = frame_number - self.config.retransmission_window
        while self._pending:
            oldest = next(iter(self._pending))
            if oldest >= oldest_allowed:
                break
            del self._pending[oldest]
            self.stats.frames_dropped += 1

    def _record_gap(self, start: int, end: int, size: int) -> None:
        self.stats.gaps_detected += size
        window = min(
            self.config.max_gap_tolerance,
            self.config.retransmission_window,
            self.config.buffer_size,
        )
        if size > window:
            self.stats.frames_dropped += size
            return

        while len(self._pending) + size > self.config.buffer_size:
            del self._pending[next(iter(self._pending))]
            self.stats.frames_dropped += 1
        self._pending.update(dict.fromkeys(range(start, end + 1)))

    def _recompute_recovery_rate(self) -> None:
        """Recompute the derived recovery rate after a state change."""
        if self.stats.gaps_detected > 0:
            self.stats.recovery_rate = self.stats.gaps_recovered / self.stats.gaps_detected
        else:
            self.stats.recovery_rate = 1.0

    def get_stats(self) -> FrameRecoveryStats:
        """Return a snapshot of the current recovery statistics."""
        with self._lock:
            return replace(self.stats)

    def reset(self, *, start_frame: int | None = None) -> None:
        """Reset recovery and optionally set the expected first frame number."""
        if start_frame is not None and start_frame < 0:
            raise ValueError("start_frame must be non-negative")
        with self._lock:
            self._last_accepted = None if start_frame is None else start_frame - 1
            self._pending.clear()
            self.stats = FrameRecoveryStats()
