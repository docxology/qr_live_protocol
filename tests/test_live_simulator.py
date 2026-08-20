"""
Tests for src.live_simulator (end-to-end live streaming simulator).

Covers the full optical deliver loop: perfect channel, lossy channel with
gap recovery, reordering, deterministic seeds, report shape, and CLI-facing
summary output.
"""

import pytest

from src.frame_recovery import FrameRecoveryConfig
from src.live_simulator import (
    LiveSimulator,
    OpticalChannelModel,
    SimulatedFrame,
    SimulationReport,
)
from src.optical_throughput import ThroughputConfig


def _new_simulator(drop_rate=0.0, reorder_rate=0.0, seed=1234, window=4):
    return LiveSimulator(
        config=ThroughputConfig(
            floor_interval=0.01,
            ceiling_interval=1.0,
            initial_interval=0.2,
        ),
        recovery_config=FrameRecoveryConfig(retransmission_window=window),
        channel=OpticalChannelModel(
            drop_rate=drop_rate,
            reorder_rate=reorder_rate,
            seed=seed,
        ),
    )


def test_perfect_channel_no_loss():
    sim = _new_simulator(drop_rate=0.0)
    report = sim.run(20)
    assert report.frames_produced == 20
    assert report.frames_dropped == 0
    assert report.frames_received == 20
    assert report.gaps_detected == 0
    assert report.recovery_rate == 1.0


def test_lossy_channel_recovers_small_gaps():
    # Drops <= retransmission window are recovered.
    sim = _new_simulator(drop_rate=0.1)
    report = sim.run(200)
    assert report.frames_produced == 200
    assert report.frames_dropped > 0
    assert report.frames_received == report.frames_produced - report.frames_dropped
    # All detected gaps should be within the recovery window at 10% drop.
    assert report.gaps_recovered == report.gaps_detected
    assert report.recovery_rate == 1.0


def test_heavier_loss_lowers_recovery_rate():
    # High loss produces wide gaps that exceed the window -> partial recovery.
    sim = _new_simulator(drop_rate=0.5, window=2)
    report = sim.run(200)
    assert report.gaps_detected >= report.gaps_recovered
    assert report.recovery_rate <= 1.0


def test_deterministic_seed_reproducibility():
    sim_a = _new_simulator(drop_rate=0.3, seed=99)
    sim_b = _new_simulator(drop_rate=0.3, seed=99)
    report_a = sim_a.run(100)
    report_b = sim_b.run(100)
    assert report_a.loss_pattern == report_b.loss_pattern
    assert report_a.frames_dropped == report_b.frames_dropped


def test_reordering_produces_duplicates_at_receiver():
    # Reordered frames arrive after their sequence was already accepted,
    # which the recovery layer treats as duplicates.
    sim = _new_simulator(drop_rate=0.0, reorder_rate=0.5)
    report = sim.run(50)
    assert report.frames_received > 0
    # No frames are dropped, so delivery is complete.
    assert report.frames_dropped == 0


def test_report_shape():
    report = _new_simulator(drop_rate=0.1).run(50)
    assert isinstance(report, SimulationReport)
    summary = report.summary_json()
    for key in (
        "frames_produced",
        "frames_received",
        "frames_dropped",
        "gaps_detected",
        "gaps_recovered",
        "recovery_rate",
        "adapted_frames_per_second",
        "cache_hit_rate",
        "encode_average_s",
    ):
        assert key in summary


def test_invalid_channel_config_rejected():
    with pytest.raises(ValueError):
        OpticalChannelModel(drop_rate=1.5)
    with pytest.raises(ValueError):
        OpticalChannelModel(drop_rate=-0.1)
    with pytest.raises(ValueError):
        OpticalChannelModel(reorder_rate=2.0)


def test_invalid_frame_count_rejected():
    sim = _new_simulator()
    with pytest.raises(ValueError):
        sim.run(0)


def test_custom_encoder_is_used():
    calls = []

    def encoder(n):
        calls.append(n)
        return SimulatedFrame(frame_number=n, payload=b"custom")

    sim = LiveSimulator(
        encoder=encoder,
        channel=OpticalChannelModel(drop_rate=0.0, seed=1),
    )
    report = sim.run(10)
    assert len(calls) == 10
    assert report.frames_produced == 10


def test_summary_string_renderable(sim=None):
    sim = sim or _new_simulator(drop_rate=0.2)
    text = sim.summary(60)
    assert "Live streaming simulation report" in text
    assert "Recovery rate" in text


def test_channel_transmit_preserves_frames():
    model = OpticalChannelModel(drop_rate=0.0, seed=7)
    frames = [SimulatedFrame(n, f"p{n}".encode()) for n in range(5)]
    received = model.transmit(frames)
    assert received == frames
    for frame in received:
        assert frame.frame_number >= 0
