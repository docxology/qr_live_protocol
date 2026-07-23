"""
Tests for async_core.py AsyncQRLiveProtocol.

Covers async QR generation, verification, batch operations,
blockchain/time data, performance stats, and sync wrappers.
All network calls are mocked.
"""

import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from src.async_core import AsyncQRLiveProtocol
from src.config import QRLPConfig
from src.core import QRData


@pytest.fixture
def async_config(tmp_path):
    """Config with blockchain and time servers disabled."""
    config = QRLPConfig()
    config.update_interval = 0.1
    config.blockchain_settings.enabled_chains = set()
    config.time_settings.time_servers = []
    config.security_settings.key_dir = str(tmp_path / "keys")
    return config


class TestAsyncInit:
    """Test AsyncQRLiveProtocol initialization."""

    def test_init(self, async_config):
        async_qrlp = AsyncQRLiveProtocol(async_config)
        assert async_qrlp.config is async_config
        assert async_qrlp.sync_qrlp is not None
        assert async_qrlp._executor is not None
        assert len(async_qrlp._session_pool) == 0

    def test_init_default_config(self):
        async_qrlp = AsyncQRLiveProtocol()
        assert async_qrlp.config is not None


class TestAsyncContextManager:
    """Test async context manager."""

    async def test_aenter_aexit(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            assert len(qrlp._session_pool) == 3
        # After exit, sessions should be closed
        # Executor should be shut down


class TestAsyncQRGeneration:
    """Test async QR generation."""

    async def test_generate_single_qr_async(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            qr_data, qr_image = await qrlp.generate_single_qr_async()
            assert isinstance(qr_data, QRData)
            assert isinstance(qr_image, bytes)
            assert qr_image[:4] == b'\x89PNG'

    async def test_generate_single_qr_async_with_user_data(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            qr_data, _ = await qrlp.generate_single_qr_async(
                user_data={"event": "test"}
            )
            assert qr_data.user_data == {"event": "test"}

    async def test_generate_signed_qr_async(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            qr_data, qr_image = await qrlp.generate_signed_qr_async()
            assert qr_data.digital_signature is not None
            assert qr_image[:4] == b'\x89PNG'

    async def test_generate_encrypted_qr_async(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            qr_data, qr_image = await qrlp.generate_encrypted_qr_async(
                user_data={"secret": "value"}
            )
            assert qr_data._encrypted_fields is not None
            assert qr_image[:4] == b'\x89PNG'

    async def test_verify_qr_data_async(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            qr_data, _ = await qrlp.generate_single_qr_async(sign_data=True)
            results = await qrlp.verify_qr_data_async(qr_data.to_json())
            assert results["valid_json"] is True


class TestAsyncBatch:
    """Test async batch operations."""

    async def test_batch_generate_qr_async(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            items = [{"id": 1}, {"id": 2}, {"id": 3}]
            results = await qrlp.batch_generate_qr_async(items, sign_data=True)
            assert len(results) == 3
            for qr_data, qr_image in results:
                assert isinstance(qr_data, QRData)
                assert qr_image[:4] == b'\x89PNG'

    async def test_batch_generate_with_empty_list(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            results = await qrlp.batch_generate_qr_async([])
            assert results == []


class TestAsyncStream:
    """Test async QR stream generation."""

    async def test_generate_qr_stream_async(self, async_config):
        async_config.update_interval = 0.05
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            results = await qrlp.generate_qr_stream_async(
                interval=0.01, max_qrs=3
            )
            assert len(results) == 3

    async def test_generate_qr_stream_with_callback(self, async_config):
        async_config.update_interval = 0.05
        received = []
        async def callback(qr_data, qr_image):
            received.append(qr_data)

        async with AsyncQRLiveProtocol(async_config) as qrlp:
            await qrlp.generate_qr_stream_async(
                interval=0.01, max_qrs=2, callback=callback
            )
            assert len(received) == 2


class TestAsyncBlockchainData:
    """Test async blockchain data retrieval."""

    async def test_get_blockchain_data_async_no_chains(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            result = await qrlp.get_blockchain_data_async()
            assert result == {}

    async def test_get_blockchain_data_async_with_mock(self, async_config):
        """Mock the aiohttp session to return fake blockchain data."""
        async_config.blockchain_settings.enabled_chains = {"bitcoin"}
        qrlp = AsyncQRLiveProtocol(async_config)
        # Don't use context manager -- mock the session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value="00000000000000000008a15c")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.close = AsyncMock()

        qrlp._session_pool = [mock_session]
        result = await qrlp.get_blockchain_data_async()
        assert "bitcoin" in result
        await qrlp._cleanup_async_resources()


class TestAsyncTimeData:
    """Test async time data retrieval."""

    async def test_get_time_data_async(self, async_config):
        async_config.time_settings.time_servers = ["time.nist.gov"]
        qrlp = AsyncQRLiveProtocol(async_config)
        # Mock HTTP time API
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "datetime": "2025-01-11T15:30:45.123456+00:00"
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.close = AsyncMock()

        qrlp._session_pool = [mock_session]
        result = await qrlp.get_time_data_async()
        assert len(result) > 0
        await qrlp._cleanup_async_resources()


class TestAsyncLiveGeneration:
    """Test async live generation start/stop."""

    async def test_start_stop_live_generation(self, async_config):
        async_config.update_interval = 0.05
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            await qrlp.start_live_generation_async()
            assert qrlp._generation_task is not None
            await asyncio.sleep(0.15)
            await qrlp.stop_live_generation_async()
            # Task should be cancelled
            assert qrlp._generation_task.cancelled() or qrlp._generation_task.done()


class TestAsyncPerformanceStats:
    """Test async performance statistics."""

    async def test_get_performance_stats_async(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            stats = await qrlp.get_performance_stats_async()
            assert "cache_stats" in stats
            assert "operation_performance" in stats
            assert "async_resources" in stats
            assert stats["cache_stats"]["hits"] == 0
            assert stats["cache_stats"]["misses"] == 0

    async def test_get_performance_stats_after_cache_ops(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            # Simulate cache hits and misses
            await qrlp.cache_qr_image_async("key1", b"image", ttl=60)
            await qrlp.get_cached_qr_async("key1")
            stats = await qrlp.get_performance_stats_async()
            assert stats["cache_stats"]["hits"] >= 1
            assert stats["cache_stats"]["misses"] >= 1

    async def test_cache_and_retrieve(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            await qrlp.cache_qr_image_async("test-key", b"qr-image-data", ttl=60)
            # get_cached_qr_async always returns None (cache miss is simulated)
            result = await qrlp.get_cached_qr_async("test-key")
            assert result is None  # Cache miss simulation


class TestAsyncOptimize:
    """Test async optimization."""

    async def test_optimize_performance_async(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            result = await qrlp.optimize_performance_async()
            assert "recommendations" in result
            assert "performance_stats" in result
            assert "optimization_applied" in result

    async def test_apply_optimizations_async_disabled(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            result = await qrlp.apply_optimizations_async(auto_optimize=False)
            assert result["message"] == "Auto-optimization disabled"

    async def test_apply_optimizations_async_enabled(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            result = await qrlp.apply_optimizations_async(auto_optimize=True)
            assert "optimizations_applied" in result or "message" in result


class TestMemoryUsage:
    """Test _get_memory_usage."""

    def test_get_memory_usage(self, async_config):
        qrlp = AsyncQRLiveProtocol(async_config)
        result = qrlp._get_memory_usage()
        # Either returns memory stats or error about psutil
        if "error" in result:
            assert "psutil" in result["error"]
        else:
            assert "rss_mb" in result
            assert "vms_mb" in result


class TestSyncWrappers:
    """Test synchronous compatibility wrappers."""

    def test_generate_single_qr_sync(self, async_config):
        qrlp = AsyncQRLiveProtocol(async_config)
        qr_data, qr_image = qrlp.generate_single_qr(sign_data=True)
        assert isinstance(qr_data, QRData)
        assert qr_image[:4] == b'\x89PNG'

    def test_verify_qr_data_sync(self, async_config):
        qrlp = AsyncQRLiveProtocol(async_config)
        qr_data, _ = qrlp.generate_single_qr(sign_data=True)
        results = qrlp.verify_qr_data(qr_data.to_json())
        assert results["valid_json"] is True

    def test_get_statistics_sync(self, async_config):
        qrlp = AsyncQRLiveProtocol(async_config)
        stats = qrlp.get_statistics()
        assert "running" in stats
        assert "async_performance" in stats
