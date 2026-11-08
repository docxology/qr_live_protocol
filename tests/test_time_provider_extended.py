"""
Extended tests for time_provider.py NTP/HTTP time sync.

All network calls are mocked.
"""

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.config import TimeSettings
from src.time_provider import TimeProvider, TimeServerResponse


def make_mock_ntp_response():
    """Create a mock NTP response."""
    resp = MagicMock()
    resp.tx_time = time.time()
    resp.mode = 4
    resp.leap = 0
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
        assert result.tzinfo == UTC

    def test_without_offsets(self):
        """Falls back to local time when no offsets."""
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        provider.time_offsets = {}
        result = provider.get_current_time()
        assert result.tzinfo == UTC

    def test_even_number_offsets_median(self):
        """Median of even number of offsets uses average of middle two."""
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        provider.time_offsets = {"s1": 0.0, "s2": 0.2, "s3": 0.4, "s4": 0.6}
        result = provider.get_current_time()
        assert result.tzinfo == UTC


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
        now = datetime.now(UTC).isoformat()
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

    @pytest.mark.parametrize(("field", "value"), [("stratum", 0), ("leap", 3), ("mode", 3)])
    def test_unusable_server_reply(self, field, value):
        provider = TimeProvider(TimeSettings(time_servers=[]))
        response = make_mock_ntp_response()
        setattr(response, field, value)
        with patch.object(provider.ntp_client, "request", return_value=response):
            result = provider.get_ntp_time("ntp.example")
        assert result.success is False
        assert result.error == "NTP source returned an unusable time sample"


class TestGetHttpTime:
    """Test get_http_time."""

    def test_success(self):
        settings = TimeSettings(time_servers=[])
        provider = TimeProvider(settings)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "datetime": datetime.now(UTC).isoformat(),
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

    def test_only_queries_configured_sources(self):
        provider = TimeProvider(TimeSettings(time_servers=["ntp.example", "https://clock.example"]))
        with patch.object(provider, "get_ntp_time") as ntp, patch.object(provider, "get_http_time") as http:
            provider.sync_all_servers()
        ntp.assert_called_once_with("ntp.example")
        http.assert_called_once_with("https://clock.example")

    def test_failed_sync_is_throttled_and_drops_unavailable_observations(self):
        provider = TimeProvider(TimeSettings(time_servers=["ntp.example"], update_interval=60))
        responses = [
            [TimeServerResponse("ntp.example", time.time(), 0.1, 0.1, 1, True)],
            [TimeServerResponse("ntp.example", 0, 0, 0, 0, False)],
        ]
        with patch.object(provider, "sync_all_servers", side_effect=responses) as sync:
            assert provider.force_sync()
            assert "ntp.example" in provider.get_time_server_verification()
            assert not provider.force_sync()
            assert provider.get_time_server_verification() == {}
            assert provider.get_time_server_verification() == {}
        assert sync.call_count == 2

    def test_unavailable_clock_when_local_fallback_is_disabled(self):
        provider = TimeProvider(TimeSettings(time_servers=[], local_fallback=False))
        with pytest.raises(RuntimeError, match="No configured time source"):
            provider.get_current_time()


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

    def test_nist_poll_limit_preserves_observation_and_other_source_refresh(self, monkeypatch):
        elapsed = [100.0]
        monkeypatch.setattr("src.time_provider.time.monotonic", lambda: elapsed[0])
        provider = TimeProvider(TimeSettings(
            time_servers=["time.nist.gov", "other.example"], update_interval=1.0,
        ))
        with patch.object(
            provider.ntp_client, "request", side_effect=lambda *_args, **_kwargs: make_mock_ntp_response(),
        ) as query:
            assert provider.force_sync()
            first = provider.get_time_server_verification()
            elapsed[0] += 1.0
            assert provider.force_sync()
            second = provider.get_time_server_verification()
            assert first["time.nist.gov"]["last_sync"] == second["time.nist.gov"]["last_sync"]
            assert [call.args[0] for call in query.call_args_list] == [
                "time.nist.gov", "other.example", "other.example",
            ]
            elapsed[0] += 3.0
            assert provider.force_sync()
        assert [call.args[0] for call in query.call_args_list[-2:]] == ["time.nist.gov", "other.example"]

    def test_removing_all_configured_sources_drops_observations(self):
        settings = TimeSettings(time_servers=["ntp.example"])
        provider = TimeProvider(settings)
        with patch.object(provider.ntp_client, "request", return_value=make_mock_ntp_response()) as query:
            assert "ntp.example" in provider.get_time_server_verification()
            settings.time_servers.clear()
            assert provider.get_time_server_verification() == {}
        query.assert_called_once()


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
