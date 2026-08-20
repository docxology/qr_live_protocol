"""
Tests for src.optical_throughput.

Covers dynamic frame cadence adaptation, payload symbol reuse / caching,
batch pre-encoding and drain, config validation, and the performance report.
"""

import time

import pytest

from src.optical_throughput import (
    OpticalThroughputController,
    ThroughputAdaptation,
    ThroughputConfig,
)


@pytest.fixture
def encoder_counts():
    state = {"calls": 0}

    def encoder(payload):
        state["calls"] += 1
        time.sleep(0.001)
        return b"\x89PNG-payload-frames"

    return state, encoder


@pytest.fixture
def controller(encoder_counts):
    _, encoder = encoder_counts
    return OpticalThroughputController(
        encoder,
        ThroughputConfig(
            floor_interval=0.01,
            ceiling_interval=1.0,
            initial_interval=0.2,
            adapt_smoothing=0.5,
        ),
    )


def test_produce_encodes_once_then_reuses_cache(controller, encoder_counts):
    state, _ = encoder_counts
    first = controller.produce("payload-a")
    second = controller.produce("payload-a")
    assert first == second
    assert state["calls"] == 1  # only encoded once
    report = controller.get_performance_report()
    assert report["frames_produced"] == 2
    assert report["frames_from_cache"] == 1
    assert report["cache_hit_rate"] == 0.5


def test_force_reencode_bypasses_cache(controller, encoder_counts):
    state, _ = encoder_counts
    controller.produce("p")
    controller.produce("p", force_reencode=True)
    assert state["calls"] == 2


def test_distinct_payloads_not_cached(controller, encoder_counts):
    state, _ = encoder_counts
    controller.produce("p1")
    controller.produce("p2")
    assert state["calls"] == 2
    assert controller.get_performance_report()["cache_hit_rate"] == 0.0


def test_speed_up_on_reads_ok(controller):
    before = controller.current_interval
    decision = controller.adapt(reads_ok=True, encode_headroom=True)
    assert decision == ThroughputAdaptation.SPEED_UP.value
    assert controller.current_interval < before


def test_slow_down_on_read_failure(controller):
    before = controller.current_interval
    decision = controller.adapt(reads_ok=False)
    assert decision == ThroughputAdaptation.SLOW_DOWN.value
    assert controller.current_interval > before


def test_hold_on_saturated_encoder(controller):
    decision = controller.adapt(reads_ok=True, encode_headroom=False)
    assert decision == ThroughputAdaptation.HOLD.value


def test_interval_respects_floor(controller):
    # Repeated speed-ups must not push below the floor.
    for _ in range(50):
        controller.adapt(reads_ok=True, encode_headroom=True)
    assert controller.current_interval >= controller.config.floor_interval


def test_interval_respects_ceiling(controller):
    for _ in range(50):
        controller.adapt(reads_ok=False)
    assert controller.current_interval <= controller.config.ceiling_interval


def test_pre_encode_and_drain_batch(controller, encoder_counts):
    state, _ = encoder_counts
    controller.pre_encode_batch(["b1", "b2", "b3"])
    assert state["calls"] == 3
    first = controller.drain_batch()
    second = controller.drain_batch()
    third = controller.drain_batch()
    assert None not in (first, second, third)
    assert controller.drain_batch() is None  # queue now empty
    assert controller.get_performance_report()["batch_queue_depth"] == 0


def test_pre_encode_reuses_cache(controller, encoder_counts):
    state, _ = encoder_counts
    controller.produce("c")
    controller.pre_encode_batch(["c", "new1"])
    # "c" cached; only "new1" triggers an encoder call.
    assert state["calls"] == 2


def test_batch_queue_bounded(controller):
    controller.pre_encode_batch([f"x{i}" for i in range(20)])
    # Queue is capped at max_batch_size, keeping the most recent frames.
    assert controller.get_performance_report()["batch_queue_depth"] == 4
    assert controller.drain_batch() is not None
    assert controller.drain_batch() is not None


def test_should_sleep_paces_producer(controller):
    assert controller.should_sleep(0.0) is True
    assert controller.should_sleep(1000.0) is False


def test_frames_per_second_reflects_interval(controller):
    assert controller.frames_per_second == pytest.approx(1.0 / 0.2)
    controller.adapt(reads_ok=False)
    assert controller.frames_per_second < (1.0 / 0.2)


def test_register_encode_tracks_latency(controller):
    controller.register_encode(0.01)
    assert controller.get_performance_report()["encode_average_s"] > 0.0


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        OpticalThroughputController(lambda p: b"", ThroughputConfig(floor_interval=0))
    with pytest.raises(ValueError):
        OpticalThroughputController(
            lambda p: b"",
            ThroughputConfig(floor_interval=0.5, ceiling_interval=0.1),
        )
    with pytest.raises(ValueError):
        OpticalThroughputController(
            lambda p: b"",
            ThroughputConfig(floor_interval=0.01, ceiling_interval=1.0, initial_interval=5.0),
        )


def test_reset_clears_state(controller):
    controller.produce("r1")
    controller.produce("r1")
    controller.pre_encode_batch(["r2"])
    controller.adapt(reads_ok=False)
    controller.reset()
    report = controller.get_performance_report()
    assert report["frames_produced"] == 0
    assert report["frames_from_cache"] == 0
    assert report["current_interval_s"] == controller.config.initial_interval
    assert controller.drain_batch() is None


def test_empty_payload_report_rate(controller):
    # No frames produced: hit-rate defaults to 1.0, fps defined by interval.
    report = controller.get_performance_report()
    assert report["cache_hit_rate"] == 1.0
    assert report["frames_per_second"] > 0.0
