"""
High-fps dynamic optical throughput optimization for QRLP.

QR codes displayed on a screen are physically limited by the encoding latency
of each frame and by the receiver's read cadence. This module provides a
controller that dynamically tunes frame production to maximize the optical
throughput (frames successfully read per second) without over-driving the
encoder or the display.

It tracks per-frame encode latency and adds:

- **Dynamic frame interval**: if encoding is fast and reads are succeeding,
  the interval shrinks toward a floor; if reads start failing or the encoder
  is saturated, the interval grows to avoid wasted frames.
- **Payload dedup / symbol reuse**: repeated QR payloads within a short
  horizon are served from a cache instead of re-encoding, cutting latency and
  freeing CPU for the frames that actually change.
- **Batch pre-encoding**: when the payload set is small and known, multiple
  frames are encoded ahead of time and drained first-in-first-out.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

PayloadT = TypeVar("PayloadT")


@dataclass
class ThroughputConfig:
    """Configuration for the dynamic throughput controller."""

    floor_interval: float = 0.05      # Fastest allowed frame cadence (20 fps)
    ceiling_interval: float = 1.0     # Slowest allowed cadence (1 fps)
    initial_interval: float = 0.2     # Starting cadence
    adapt_smoothing: float = 0.3      # EMA weight for interval adaptation
    encode_latency_smoothing: float = 0.5  # EMA weight for latency tracking
    max_batch_size: int = 4           # Max frames to pre-encode ahead
    slow_threshold: float = 0.75      # Fraction of target budget => too slow
    cache_size: int = 128             # Max distinct payload images retained


class ThroughputAdaptation(Enum):
    """Result of an interval adaptation step."""

    HOLD = "hold"
    SPEED_UP = "speed_up"
    SLOW_DOWN = "slow_down"


@dataclass
class ThroughputStats:
    """Statistics for the throughput controller."""

    frames_produced: int = 0
    frames_from_cache: int = 0
    encode_average: float = 0.0
    current_interval: float = 0.2
    adapted_frames_per_second: float = 5.0
    cache_hit_rate: float = 1.0

    def recompute(self, produced: int, cached: int) -> None:
        """Recompute derived hit-rate."""
        self.cache_hit_rate = cached / produced if produced else 1.0
        self.adapted_frames_per_second = 1.0 / self.current_interval if self.current_interval > 0 else 0.0


class OpticalThroughputController(Generic[PayloadT]):
    """Dynamically optimize QR frame production for optical throughput."""

    def __init__(self, encoder: Callable[[PayloadT], bytes], config: ThroughputConfig | None = None):
        """
        Initialize the throughput controller.

        Args:
            encoder: Callable payload -> frame image bytes.
            config: Optional throughput configuration.
        """
        self._encoder = encoder
        self.config = config or ThroughputConfig()
        if self.config.floor_interval <= 0:
            raise ValueError("floor_interval must be positive")
        if self.config.ceiling_interval < self.config.floor_interval:
            raise ValueError("ceiling_interval must be >= floor_interval")
        if self.config.initial_interval < self.config.floor_interval or self.config.initial_interval > self.config.ceiling_interval:
            raise ValueError("initial_interval must lie within [floor, ceiling]")
        if self.config.cache_size < 0:
            raise ValueError("cache_size must be non-negative")
        if self.config.max_batch_size < 0:
            raise ValueError("max_batch_size must be non-negative")

        self._lock = threading.RLock()
        self._current_interval = self.config.initial_interval
        self._encode_average = 0.0
        self._frames_produced = 0
        self._frames_from_cache = 0
        # Payload dedup cache: (encoded_image) keyed by payload identity.
        self._cache: OrderedDict[PayloadT, bytes] = OrderedDict()
        self._batch_queue: deque[bytes] = deque(maxlen=self.config.max_batch_size)

    @property
    def current_interval(self) -> float:
        """Return the current production interval in seconds."""
        with self._lock:
            return self._current_interval

    @property
    def frames_per_second(self) -> float:
        """Return the current adapted frames-per-second estimate."""
        with self._lock:
            return 1.0 / self._current_interval if self._current_interval > 0 else 0.0

    def produce(self, payload: PayloadT, force_reencode: bool = False) -> bytes:
        """
        Produce a frame for the given payload, applying cache reuse.

        Args:
            payload: Payload to render.
            force_reencode: Skip the cache and re-encode unconditionally.

        Returns:
            Frame image bytes.
        """
        with self._lock:
            frame, from_cache = self._get_frame(payload, force_reencode)
            self._frames_produced += 1
            if from_cache:
                self._frames_from_cache += 1
            return frame

    def _get_frame(self, payload: PayloadT, force_reencode: bool = False) -> tuple[bytes, bool]:
        if not force_reencode and payload in self._cache:
            self._cache.move_to_end(payload)
            return self._cache[payload], True

        started_at = time.perf_counter()
        frame = self._encoder(payload)
        self.register_encode(time.perf_counter() - started_at)
        if self.config.cache_size:
            self._cache[payload] = frame
            self._cache.move_to_end(payload)
            while len(self._cache) > self.config.cache_size:
                self._cache.popitem(last=False)
        return frame, False

    def register_encode(self, latency: float) -> None:
        """Record an encoder latency measurement (outside context of produce)."""
        with self._lock:
            self._encode_average = (
                self.config.encode_latency_smoothing * latency
                + (1 - self.config.encode_latency_smoothing) * self._encode_average
            )

    def pre_encode_batch(self, payloads: list[PayloadT]) -> None:
        """
        Pre-encode a batch of payloads into the FIFO drain queue.

        Args:
            payloads: Ordered payloads to pre-encode ahead of time.
        """
        with self._lock:
            for payload in payloads:
                frame, _ = self._get_frame(payload)
                self._batch_queue.append(frame)

    def drain_batch(self) -> bytes | None:
        """
        Pop the next pre-encoded frame from the FIFO queue, if any.

        Returns:
            Frame image bytes, or ``None`` when the queue is empty.
        """
        with self._lock:
            if not self._batch_queue:
                return None
            frame = self._batch_queue.popleft()
            self._frames_produced += 1
            return frame

    def should_sleep(self, elapsed_in_frame: float) -> bool:
        """
        Decide whether the producer should pace itself before the next frame.

        Args:
            elapsed_in_frame: Time spent in the current frame.

        Returns:
            True if the producer should wait, False if it may emit now.
        """
        with self._lock:
            return elapsed_in_frame < self._current_interval

    def adapt(self, reads_ok: bool, encode_headroom: bool = True) -> str:
        """
        Adapt the production interval based on read success and encoder load.

        Args:
            reads_ok: Whether the most recent frames were successfully read.
            encode_headroom: Whether the encoder finished under its time budget.

        Returns:
            The adaptation decision taken (a ``ThroughputAdaptation`` value).
        """
        with self._lock:
            if encode_headroom and reads_ok:
                # Speeding up: shrink the interval toward the floor.
                new_interval = max(
                    self.config.floor_interval,
                    self._current_interval
                    * (1 - self.config.adapt_smoothing),
                )
                decision = ThroughputAdaptation.SPEED_UP.value
            elif not reads_ok:
                # Backing off: grow the interval toward the ceiling.
                new_interval = min(
                    self.config.ceiling_interval,
                    self._current_interval
                    * (1 + self.config.adapt_smoothing),
                )
                decision = ThroughputAdaptation.SLOW_DOWN.value
            else:
                # Encoder saturated: hold the current cadence.
                new_interval = self._current_interval
                decision = ThroughputAdaptation.HOLD.value

            self._current_interval = new_interval
            return decision

    def get_performance_report(self) -> dict[str, Any]:
        """Return a human- and machine-readable performance report."""
        with self._lock:
            produced = self._frames_produced
            cached = self._frames_from_cache
            stats = ThroughputStats(
                frames_produced=produced,
                frames_from_cache=cached,
                encode_average=self._encode_average,
                current_interval=self._current_interval,
                adapted_frames_per_second=(
                    1.0 / self._current_interval if self._current_interval > 0 else 0.0
                ),
            )
            stats.recompute(produced, cached)
            return {
                "frames_produced": stats.frames_produced,
                "frames_from_cache": stats.frames_from_cache,
                "cache_hit_rate": stats.cache_hit_rate,
                "encode_average_s": stats.encode_average,
                "current_interval_s": stats.current_interval,
                "frames_per_second": stats.adapted_frames_per_second,
                "batch_queue_depth": len(self._batch_queue),
                "interval_bounds": {
                    "floor": self.config.floor_interval,
                    "ceiling": self.config.ceiling_interval,
                },
            }

    def reset(self) -> None:
        """Reset production counters, cache, and cadence."""
        with self._lock:
            self._frames_produced = 0
            self._frames_from_cache = 0
            self._encode_average = 0.0
            self._current_interval = self.config.initial_interval
            self._cache.clear()
            self._batch_queue.clear()
