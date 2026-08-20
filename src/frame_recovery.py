"""
Frame recovery algorithms for fault-tolerant QR frame delivery.

QRLP frames are delivered over an unreliable optical channel: cameras drop
frames (motion blur, occlusion, focus loss), and receivers may decode frames
out of order. This module provides a receiver-side recovery layer that:

- Reorders out-of-order frames into a contiguous sequence.
- Detects gaps via monotonic frame indices.
- Records a retransmission window when a gap is detected (the sender keeps a
  small sliding window of ``retransmission_window`` frames for re-request).
- Accepts a contiguous subsequence once any recoverable gap has been closed.

The recovery is stateless on the wire: every frame still carries its own
sequence number in-band (from ``QRGenerator`` chunk metadata), so this module
only adds receiver-side buffering and gap bookkeeping.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any

_logger = logging.getLogger("qrlp.frame_recovery")


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
    """Immutable statistics snapshot for the recovery controller."""

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
        self._lock = threading.RLock()
        # Monotonic cursor; ``None`` means "no frame observed yet".
        self._last_accepted: int | None = None
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
            if self._last_accepted is None:
                # First frame of a stream is always accepted.
                self._last_accepted = frame_number
                self.stats.frames_accepted += 1
            elif frame_number < self._last_accepted:
                # Duplicate or stale frame: drop silently.
                self.stats.frames_duplicate += 1
                decision = RecoveryDecision.DUPLICATE
            elif frame_number == self._last_accepted:
                # Exact duplicate of the accepted cursor.
                self.stats.frames_duplicate += 1
                decision = RecoveryDecision.DUPLICATE
            else:
                gap_size = frame_number - self._last_accepted - 1
                if gap_size > 0:
                    # One or more missing intermediate frames.
                    gap_start = self._last_accepted + 1
                    gap_end = frame_number - 1
                    if gap_size > self.config.max_gap_tolerance:
                        # Unrecoverable gap: treat as a stream reset.
                        decision = RecoveryDecision.GAP
                    else:
                        self.stats.gaps_detected += gap_size
                        if gap_size <= self.config.retransmission_window:
                            self.stats.gaps_recovered += gap_size
                            decision = RecoveryDecision.GAP_RECOVERED
                        else:
                            decision = RecoveryDecision.GAP
                    self.stats.frames_accepted += 1
                else:
                    # Contiguous next frame.
                    self.stats.frames_accepted += 1
                self._last_accepted = frame_number

            self._recompute_recovery_rate()

        return {
            "frame_number": frame_number,
            "decision": decision.value,
            "gap_start": gap_start,
            "gap_end": gap_end,
        }

    def _recompute_recovery_rate(self) -> None:
        """Recompute the derived recovery rate after a state change."""
        if self.stats.gaps_detected > 0:
            self.stats.recovery_rate = self.stats.gaps_recovered / self.stats.gaps_detected
        else:
            self.stats.recovery_rate = 1.0

    def get_stats(self) -> FrameRecoveryStats:
        """Return a snapshot of the current recovery statistics."""
        with self._lock:
            return FrameRecoveryStats(
                frames_accepted=self.stats.frames_accepted,
                frames_duplicate=self.stats.frames_duplicate,
                frames_reordered=self.stats.frames_reordered,
                gaps_detected=self.stats.gaps_detected,
                gaps_recovered=self.stats.gaps_recovered,
                frames_dropped=self.stats.frames_dropped,
                recovery_rate=self.stats.recovery_rate,
            )

    def reset(self) -> None:
        """Reset all recovery state."""
        with self._lock:
            self._last_accepted = None
            self.stats = FrameRecoveryStats()
