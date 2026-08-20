"""
Tests for src.frame_recovery.

Covers the frame recovery controller: in-order delivery, gap detection,
retransmission-window recovery, duplicate suppression, unrecoverable-gap
stream resets, config validation, and stats snapshots.
"""

from dataclasses import dataclass

import pytest

from src.frame_recovery import (
    FrameRecoveryConfig,
    FrameRecoveryController,
    RecoveryDecision,
)


@dataclass
class Frame:
    """Test frame carrying a monotonic sequence number."""

    frame_number: int
    payload: bytes = b"data"


@pytest.fixture
def controller() -> FrameRecoveryController:
    """A default recovery controller with a generous window."""
    return FrameRecoveryController(
        FrameRecoveryConfig(
            buffer_size=8,
            max_gap_tolerance=10,
            retransmission_window=4,
        )
    )


def test_in_order_frames_accepted(controller):
    for i in range(5):
        result = controller.feed_frame(Frame(i))
        assert result["decision"] == RecoveryDecision.ACCEPT.value
    stats = controller.get_stats()
    assert stats.frames_accepted == 5
    assert stats.frames_duplicate == 0
    assert stats.recovery_rate == 1.0


def test_int_frame_accepted(controller):
    result = controller.feed_frame(3)
    assert result["frame_number"] == 3
    assert result["decision"] == RecoveryDecision.ACCEPT.value


def test_duplicate_frame_dropped(controller):
    controller.feed_frame(Frame(1))
    result = controller.feed_frame(Frame(1))
    assert result["decision"] == RecoveryDecision.DUPLICATE.value
    stats = controller.get_stats()
    assert stats.frames_accepted == 1
    assert stats.frames_duplicate == 1


def test_stale_frame_dropped(controller):
    controller.feed_frame(Frame(5))
    result = controller.feed_frame(Frame(3))
    assert result["decision"] == RecoveryDecision.DUPLICATE.value


def test_small_gap_recovered_within_window(controller):
    controller.feed_frame(Frame(0))
    result = controller.feed_frame(Frame(3))
    assert result["decision"] == RecoveryDecision.GAP_RECOVERED.value
    assert result["gap_start"] == 1
    assert result["gap_end"] == 2
    stats = controller.get_stats()
    assert stats.gaps_detected == 2
    assert stats.gaps_recovered == 2
    assert stats.recovery_rate == 1.0


def test_gap_outside_window_reported_as_gap(controller):
    controller.feed_frame(Frame(0))
    # 5-frame gap with retransmission_window=4 is beyond recovery.
    result = controller.feed_frame(Frame(6))
    assert result["decision"] == RecoveryDecision.GAP.value
    assert result["gap_start"] == 1
    assert result["gap_end"] == 5
    stats = controller.get_stats()
    assert stats.gaps_detected == 5
    assert stats.gaps_recovered == 0
    assert stats.recovery_rate == 0.0


def test_large_gap_triggers_stream_reset(controller):
    controller.feed_frame(Frame(0))
    controller.feed_frame(Frame(1))
    # 12-frame gap exceeds max_gap_tolerance (10): treated as a reset.
    result = controller.feed_frame(Frame(14))
    assert result["decision"] == RecoveryDecision.GAP.value
    stats = controller.get_stats()
    assert stats.frames_accepted == 3  # 0, 1, 14


def test_out_of_order_then_recovery(controller):
    first = controller.feed_frame(Frame(0))
    assert first["decision"] == RecoveryDecision.ACCEPT.value
    # Missing 1,2,3 -> gap recovered (within window).
    late = controller.feed_frame(Frame(4))
    assert late["decision"] == RecoveryDecision.GAP_RECOVERED.value
    # Now the missing frames arrive late; they are now stale -> duplicate.
    stale = controller.feed_frame(Frame(2))
    assert stale["decision"] == RecoveryDecision.DUPLICATE.value


def test_negative_frame_number_rejected(controller):
    with pytest.raises(ValueError):
        controller.feed_frame(Frame(-1))


def test_frame_without_number_rejected(controller):
    with pytest.raises(ValueError):
        controller.feed_frame(object())


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        FrameRecoveryConfig(buffer_size=0)
    with pytest.raises(ValueError):
        FrameRecoveryConfig(max_gap_tolerance=-1)
    with pytest.raises(ValueError):
        FrameRecoveryConfig(retransmission_window=0)


def test_reset_clears_state(controller):
    controller.feed_frame(Frame(0))
    controller.feed_frame(Frame(5))
    assert controller.get_stats().frames_accepted == 2
    controller.reset()
    stats = controller.get_stats()
    assert stats.frames_accepted == 0
    assert stats.gaps_detected == 0
    # A fresh frame after reset starts a new stream.
    result = controller.feed_frame(Frame(0))
    assert result["decision"] == RecoveryDecision.ACCEPT.value


def test_stats_snapshot_is_isolated(controller):
    controller.feed_frame(Frame(0))
    snapshot = controller.get_stats()
    controller.feed_frame(Frame(1))
    # The earlier snapshot must be independent of later mutations.
    assert snapshot.frames_accepted == 1
    assert controller.get_stats().frames_accepted == 2


def test_mixed_gap_and_recovery_rates(controller):
    # Frame sequence with a recoverable gap (1) and an out-of-window gap (2,3,4,5,6).
    controller.feed_frame(Frame(0))
    controller.feed_frame(Frame(2))  # recoverable 1-frame gap (window 4)
    controller.feed_frame(Frame(9))  # 6-frame gap, outside window -> GAP
    stats = controller.get_stats()
    assert stats.gaps_detected == (1 + 6)
    assert stats.gaps_recovered == 1
    assert 0.0 < stats.recovery_rate < 1.0
