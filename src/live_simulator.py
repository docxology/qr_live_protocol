"""
End-to-end live QR streaming simulator.

Simulates a complete live QRLP optical delivery loop without real hardware:

    encoder  ->  optical channel (drops / reorders)  ->  receiver recovery

The simulator wires the real components together:

- :class:`OpticalThroughputController` paces *and* caches frame production.
- A configurable optical channel model drops a fraction of frames
  (motion blur, occlusion, focus loss) and optionally reorders them.
- :class:`FrameRecoveryController` tracks gaps and actual late arrivals.

A run produces a full report: frames produced, frames dropped, gaps detected,
gaps recovered, recovery rate, adapted frames-per-second, and the lasting
impact of throughput adaptation. The model is deterministic when a seed is
provided, so simulator runs are reproducible. No hardware is required.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Any, TypeVar

from .frame_recovery import FrameRecoveryConfig, FrameRecoveryController
from .optical_throughput import OpticalThroughputController, ThroughputConfig

_Frame = TypeVar("_Frame")


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

    def transmit(self, frames: list[_Frame]) -> list[_Frame]:
        """Return the original frames in simulated delivery order."""
        return [frame for _, frame in self._deliver(frames)]

    def _deliver(
        self,
        frames: Iterable[_Frame],
        on_attempt: Callable[[int, bool], None] | None = None,
    ) -> Iterator[tuple[int, _Frame]]:
        pending: list[tuple[int, int, _Frame]] = []
        for index, frame in enumerate(frames):
            received = self._random.random() >= self.drop_rate
            if on_attempt is not None:
                on_attempt(index, received)

            if received:
                if self.reorder_span and self.reorder_rate and self._random.random() < self.reorder_rate:
                    delay = self._random.randint(1, self.reorder_span)
                    heappush(pending, (index + delay, index, frame))
                else:
                    yield index, frame

            while pending and pending[0][0] <= index:
                _, original_index, delayed_frame = heappop(pending)
                yield original_index, delayed_frame

        while pending:
            _, original_index, delayed_frame = heappop(pending)
            yield original_index, delayed_frame


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
            byte payload, so the simulation needs no hardware.
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
        def default_encoder(frame_number: int) -> bytes:
            return f"QRLP-FRAME-{frame_number}".encode("ascii")

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

        self._producer.reset()
        self._recovery.reset(start_frame=0)
        loss_pattern: list[int] = []

        def observe(index: int, received: bool) -> None:
            if not received:
                loss_pattern.append(index)
            if adapt_on_reads:
                self._producer.adapt(reads_ok=received)

        frames = (self._producer.produce(index) for index in range(frame_count))
        for frame_number, _ in self.channel._deliver(frames, observe):
            self._recovery.feed_frame(frame_number)

        report_stats = self._producer.get_performance_report()
        recovery_stats = self._recovery.get_stats()

        return SimulationReport(
            frames_produced=report_stats["frames_produced"],
            frames_received=frame_count - len(loss_pattern),
            frames_dropped=len(loss_pattern),
            gaps_detected=recovery_stats.gaps_detected,
            gaps_recovered=recovery_stats.gaps_recovered,
            recovery_rate=recovery_stats.recovery_rate,
            adapted_frames_per_second=report_stats["frames_per_second"],
            cache_hit_rate=report_stats["cache_hit_rate"],
            encode_average_s=report_stats["encode_average_s"],
            loss_pattern=loss_pattern,
        )

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
