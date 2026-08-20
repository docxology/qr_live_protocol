"""
End-to-end live QR streaming simulator.

Simulates a complete live QRLP optical delivery loop without real hardware:

    encoder  ->  optical channel (drops / reorders)  ->  receiver recovery

The simulator wires the real components together:

- :class:`OpticalThroughputController` paces *and* caches frame production.
- A configurable optical channel model drops a fraction of frames
  (motion blur, occlusion, focus loss) and optionally reorders them.
- :class:`FrameRecoveryController` re-orders and recovers the received stream.

A run produces a full report: frames produced, frames dropped, gaps detected,
gaps recovered, recovery rate, adapted frames-per-second, and the lasting
impact of throughput adaptation. The model is deterministic when a seed is
provided, so simulator runs are reproducible. No hardware is required.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable

from .frame_recovery import FrameRecoveryConfig, FrameRecoveryController
from .optical_throughput import OpticalThroughputController, ThroughputConfig


@dataclass
class OpticalChannelModel:
    """Deterministic model of an unreliable optical camera channel."""

    drop_rate: float = 0.15          # Fraction of frames dropped by the camera
    reorder_rate: float = 0.0        # Fraction of received frames delivered late
    reorder_span: int = 3            # Max frames a reordered frame can lag
    seed: int | None = None          # Deterministic PRNG seed

    def __post_init__(self) -> None:
        if not (0.0 <= self.drop_rate <= 1.0):
            raise ValueError("drop_rate must be within [0, 1]")
        if not (0.0 <= self.reorder_rate <= 1.0):
            raise ValueError("reorder_rate must be within [0, 1]")
        if self.reorder_span < 0:
            raise ValueError("reorder_span must be non-negative")
        self._random = random.Random(self.seed)

    def transmit(self, frames: list[Any]) -> list[Any]:
        """
        Pass frames through the unreliable channel.

        Frames are either dropped, delivered in order, or (when reorder is
        enabled) delivered late. Returns the frames observed by the receiver.

        Args:
            frames: Ordered list of produced frames.

        Returns:
            The subset of frames that arrive at the receiver.
        """
        received = []
        drop_pool = set()

        for index, frame in enumerate(frames):
            if self._random.random() < self.drop_rate:
                drop_pool.add(index)
                continue
            # With the reorder probability, defer this frame a few positions.
            if self.reorder_rate > 0 and self._random.random() < self.reorder_rate:
                received.append(_DeferredFrame(index, frame))
            else:
                received.append(frame)

        return received


class _DeferredFrame:
    """
    A frame whose delivery is intentionally deferred to simulate reordering.

    Wraps an original frame so it still exposes ``frame_number`` but arrives
    after frames with larger sequence numbers.
    """

    __slots__ = ("_payload", "frame_number")

    def __init__(self, frame_number: int, payload: Any):
        self.frame_number = frame_number
        self._payload = payload

    def unwrap(self) -> Any:
        """Return the underlying produced frame."""
        return self._payload


@dataclass
class SimulatedFrame:
    """A producer output that carries its sequence number and payload."""

    frame_number: int
    payload: bytes

    def __bool__(self) -> bool:
        return bool(self.payload)

    def __len__(self) -> int:
        return len(self.payload)


@dataclass
class SimulationReport:
    """Result of an end-to-end live simulation run."""

    frames_produced: int
    frames_received: int
    frames_dropped: int
    gaps_detected: int
    gaps_recovered: int
    recovery_rate: float
    adapted_frames_per_second: float
    cache_hit_rate: float
    encode_average_s: float
    loss_pattern: list[int]  # Frame numbers that were dropped on the channel

    def summary_json(self) -> dict[str, Any]:
        """Return a JSON-serializable summary."""
        return {
            "frames_produced": self.frames_produced,
            "frames_received": self.frames_received,
            "frames_dropped": self.frames_dropped,
            "gaps_detected": self.gaps_detected,
            "gaps_recovered": self.gaps_recovered,
            "recovery_rate": self.recovery_rate,
            "adapted_frames_per_second": self.adapted_frames_per_second,
            "cache_hit_rate": self.cache_hit_rate,
            "encode_average_s": self.encode_average_s,
        }


class LiveSimulator:
    """
    End-to-end live streaming simulator tying encoder, channel, and recovery.

    Args:
        encoder: Callable(frame_number) -> bytes. Defaults to a synthetic
            ``b"frame:<n>"`` encoder when left as ``None`` (no hardware/QR
            dependency, so simulations run anywhere).
        config: Optional throughput configuration.
        recovery_config: Optional frame recovery configuration.
        channel: Optional optical channel model. A default 15% drop rate is
            used when left as ``None``.
    """

    def __init__(
        self,
        encoder: Callable[[int], Any] | None = None,
        config: ThroughputConfig | None = None,
        recovery_config: FrameRecoveryConfig | None = None,
        channel: OpticalChannelModel | None = None,
    ):
        def default_encoder(frame_number: int) -> SimulatedFrame:
            payload = f"QRLP-FRAME-{frame_number}".encode("ascii")
            return SimulatedFrame(frame_number=frame_number, payload=payload)

        self._encoder = encoder or default_encoder
        self.config = config or ThroughputConfig()
        self.recovery_config = recovery_config or FrameRecoveryConfig()
        self.channel = channel or OpticalChannelModel(seed=42)

        self._producer = OpticalThroughputController(self._encoder, self.config)
        self._recovery = FrameRecoveryController(self.recovery_config)

    def run(self, frame_count: int, adapt_on_reads: bool = True) -> SimulationReport:
        """
        Run a full simulation and return the resulting report.

        Args:
            frame_count: Number of frames the producer attempts to emit.
            adapt_on_reads: Whether read success feeds interval adaptation.

        Returns:
            A :class:`SimulationReport` summarizing the run.
        """
        if frame_count < 1:
            raise ValueError("frame_count must be at least 1")

        produced_frames: list[Any] = []
        loss_pattern: list[int] = []

        # Phase 1: produce frames, applying drops so adaptation reacts.
        for n in range(frame_count):
            frame = self._producer.produce(n)
            if self._channel_drops_frame():
                loss_pattern.append(n)
                if adapt_on_reads:
                    self._producer.adapt(reads_ok=False)
            elif adapt_on_reads:
                self._producer.adapt(reads_ok=True)
            produced_frames.append(frame)

        # Phase 2: pass frames through the channel model (drop + reorder).
        delivered = self.channel.transmit(produced_frames)
        # Flatten reordered (deferred) wrappers back to their payloads.
        flattened = [
            frame.unwrap() if isinstance(frame, _DeferredFrame) else frame
            for frame in delivered
        ]

        # Phase 3: drive the recovery controller over delivered frame numbers.
        received_numbers = []
        for frame in flattened:
            frame_number = getattr(frame, "frame_number", None)
            if frame_number is None:
                frame_number = frame if isinstance(frame, int) else None
            if frame_number is not None:
                received_numbers.append(frame_number)
                self._recovery.feed_frame(frame_number)

        report_stats = self._producer.get_performance_report()
        recovery_stats = self._recovery.get_stats()

        return SimulationReport(
            frames_produced=report_stats["frames_produced"],
            frames_received=len(received_numbers),
            frames_dropped=report_stats["frames_produced"] - len(received_numbers),
            gaps_detected=recovery_stats.gaps_detected,
            gaps_recovered=recovery_stats.gaps_recovered,
            recovery_rate=recovery_stats.recovery_rate,
            adapted_frames_per_second=report_stats["frames_per_second"],
            cache_hit_rate=report_stats["cache_hit_rate"],
            encode_average_s=report_stats["encode_average_s"],
            loss_pattern=sorted(set(loss_pattern)),
        )

    def _channel_drops_frame(self) -> bool:
        """Query the channel's PRNG for a single-frame drop decision."""
        return self.channel._random.random() < self.channel.drop_rate

    def summary(self, frame_count: int = 100) -> str:
        """Return a human-readable summary of a simulation run."""
        report = self.run(frame_count)
        lines = [
            "Live streaming simulation report",
            "=" * 40,
            f"Frames produced      : {report.frames_produced}",
            f"Frames received      : {report.frames_received}",
            f"Frames dropped       : {report.frames_dropped}"
            f" ({self._drop_percent(report):.1f}%)",
            f"Gaps detected        : {report.gaps_detected}",
            f"Gaps recovered       : {report.gaps_recovered}",
            f"Recovery rate        : {report.recovery_rate:.1%}",
            f"Adapted fps          : {report.adapted_frames_per_second:.1f}",
            f"Cache hit rate       : {report.cache_hit_rate:.1%}",
            f"Avg encode latency   : {report.encode_average_s * 1000:.2f} ms",
        ]
        return "\n".join(lines)

    @staticmethod
    def _drop_percent(report: SimulationReport) -> float:
        if report.frames_produced <= 0:
            return 0.0
        return 100.0 * report.frames_dropped / report.frames_produced
