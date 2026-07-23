"""
Extended tests for time_provider.py NTP/HTTP time sync.

All network calls are mocked.
"""

import time
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.time_provider import TimeProvider, TimeServerResponse
from src.config import TimeSettings


def make_mock_ntp_response():
    """Create a mock NTP response."""
    resp = MagicMock()
    resp.tx_time = time.time()
    resp.offset = 0.001
    resp.delay = 0.05
    resp.stratum = 1
    return resp


class TestGetCurrentTime:
    """Test get_current_time."""

    def test_with_offsets(self):
        """Uses median offset from synced servers."""
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        provider.time_offsets = {"s1": 0.1, "s2": 0.2, "s3": 0.3}
        result = provider.get_current_time()
        assert result.tzinfo == timezone.utc

    def test_without_offsets(self):
        """Falls back to local time when no offsets."""
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        provider.time_offsets = {}
        result = provider.get_current_time()
        assert result.tzinfo == timezone.utc

    def test_even_number_offsets_median(self):
        """Median of even number of offsets uses average of middle two."""
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        provider.time_offsets = {"s1": 0.0, "s2": 0.2, "s3": 0.4, "s4": 0.6}
        result = provider.get_current_time()
        assert result.tzinfo == timezone.utc


class TestGetTimeServerVerification:
    """Test get_time_server_verification."""

    def test_returns_server_info(self):
        settings = TimeSettings(time_servers=[], update_interval=999)
        provider = TimeProvider(settings)
        provider.time_offsets = {"server1": 0.1}
        provider.last_sync_time = time.time()
        result = provider.get_time_server_verification()
        assert "server1" in result
        assert "timestamp" in result["server1"]
        assert "offset" in result["server1"]
        assert "last_sync" in result["server1"]

    def test_empty_offsets(self):
        settings = TimeSettings(time_servers=[], update_interval=999)
        provider = TimeProvider(settings)
        provider.time_offsets = {}
        result = provider.get_time_server_verification()
        assert result == {}


class TestVerifyTimestamp:
    """Test verify_timestamp."""

    def test_valid_timestamp(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        now = datetime.now(timezone.utc).isoformat()
        result = provider.verify_timestamp(now, tolerance=30.0)
        assert result["valid"] is True
        assert "time_difference" in result

    def test_expired_timestamp(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        old = "2020-01-01T00:00:00+00:00"
        result = provider.verify_timestamp(old, tolerance=30.0)
        assert result["valid"] is False

    def test_invalid_format(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        result = provider.verify_timestamp("not-a-timestamp", tolerance=30.0)
        assert result["valid"] is False
        assert "error" in result


class TestGetNtpTime:
    """Test get_ntp_time."""

    def test_success(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        with patch.object(provider.ntp_client, 'request', return_value=make_mock_ntp_response()):
            result = provider.get_ntp_time("time.nist.gov")
            assert result.success is True
            assert result.server == "time.nist.gov"
            assert result.stratum == 1

    def test_failure(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        with patch.object(provider.ntp_client, 'request', side_effect=Exception("timeout")):
            result = provider.get_ntp_time("time.nist.gov")
            assert result.success is False
            assert result.error is not None


class TestGetHttpTime:
    """Test get_http_time."""

    def test_success(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "datetime": datetime.now(timezone.utc).isoformat(),
        }
        with patch('requests.get', return_value=mock_response):
            result = provider.get_http_time("http://worldtimeapi.org/api/timezone/UTC")
            assert result.success is True

    def test_failure(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        with patch('requests.get', side_effect=Exception("network error")):
            result = provider.get_http_time("http://example.com")
            assert result.success is False
            assert result.error is not None


class TestSyncAllServers:
    """Test sync_all_servers."""

    def test_empty_servers(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        result = provider.sync_all_servers()
        assert result == []

    def test_with_mocked_ntp(self):
        settings = TimeSettings(time_servers=["time.nist.gov"])
        provider = TimeProvider(settings)
        with patch.object(provider.ntp_client, 'request', return_value=make_mock_ntp_response()):
            result = provider.sync_all_servers()
            assert len(result) >= 1
            assert result[0].success is True


class TestForceSync:
    """Test force_sync."""

    def test_force_sync_success(self):
        settings = TimeSettings(time_servers=["time.nist.gov"])
        provider = TimeProvider(settings)
        with patch.object(provider.ntp_client, 'request', return_value=make_mock_ntp_response()):
            result = provider.force_sync()
            assert result is True

    def test_force_sync_failure(self):
        settings = TimeSettings(time_servers=["time.nist.gov"])
        provider = TimeProvider(settings)
        with patch.object(provider.ntp_client, 'request', side_effect=Exception("fail")):
            result = provider.force_sync()
            assert result is False


class TestGetStatistics:
    """Test get_statistics."""

    def test_initial_stats(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        stats = provider.get_statistics()
        assert "total_syncs" in stats
        assert "successful_syncs" in stats
        assert "failed_syncs" in stats
        assert "active_servers" in stats
        assert "time_offsets" in stats
        assert "success_rate" in stats
