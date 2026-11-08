"""
Tests for async_core.py AsyncQRLiveProtocol.

Covers async QR generation, verification, batch operations,
blockchain/time data, performance stats, and sync wrappers.
Provider tests use controlled observations from the shared synchronous providers.
"""

import asyncio
import threading

import pytest

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

    def test_init_default_config(self):
        async_qrlp = AsyncQRLiveProtocol()
        assert async_qrlp.config is not None


class TestAsyncContextManager:
    """Test async context manager."""

    async def test_aenter_aexit(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            assert isinstance(qrlp, AsyncQRLiveProtocol)
        with pytest.raises(RuntimeError, match="closed"):
            await qrlp.generate_single_qr_async()
        await qrlp.aclose()


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


class TestAsyncProviders:
    async def test_blockchain_data_uses_shared_provider(self, async_config, monkeypatch):
        loop_thread = threading.get_ident()

        def observe():
            assert threading.get_ident() != loop_thread
            return {"bitcoin": "00000000000000000008a15c"}

        async with AsyncQRLiveProtocol(async_config) as qrlp:
            monkeypatch.setattr(qrlp.sync_qrlp.blockchain_verifier, "get_blockchain_hashes", observe)
            assert await qrlp.get_blockchain_data_async() == {"bitcoin": "00000000000000000008a15c"}

    async def test_time_data_uses_actual_observed_sources(self, async_config, monkeypatch):
        timestamp = "2025-01-11T15:30:45.123456+00:00"
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            monkeypatch.setattr(
                qrlp.sync_qrlp.time_provider,
                "get_time_server_verification",
                lambda: {"test-server": {"timestamp": timestamp, "offset": 0.25, "last_sync": 1.0}},
            )
            assert await qrlp.get_time_data_async() == {
                "test-server": {"timestamp": timestamp, "offset": "0.25", "server": "test-server"}
            }


class TestAsyncLiveGeneration:
    """Test async live generation start/stop."""

    async def test_start_stop_live_generation(self, async_config):
        async_config.update_interval = 0.05
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            ready = asyncio.Event()
            await qrlp.start_live_generation_async(lambda *_: ready.set())
            generation_task = qrlp._generation_task
            await qrlp.start_live_generation_async()
            assert qrlp._generation_task is generation_task
            await asyncio.wait_for(ready.wait(), timeout=5)
        assert generation_task.done()


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
            await qrlp.cache_qr_image_async("key1", b"image", ttl=60)
            await qrlp.get_cached_qr_async("key1")
            await qrlp.get_cached_qr_async("missing")
            stats = await qrlp.get_performance_stats_async()
            assert stats["cache_stats"]["hits"] == 1
            assert stats["cache_stats"]["misses"] == 1

    async def test_cache_and_retrieve(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            await qrlp.cache_qr_image_async("test-key", b"qr-image-data", ttl=60)
            result = await qrlp.get_cached_qr_async("test-key")
            assert result == b"qr-image-data"
            await qrlp.cache_qr_image_async("test-key", b"expired", ttl=0)
            assert await qrlp.get_cached_qr_async("test-key") is None

    async def test_cache_evicts_oldest_when_full(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            for index in range(101):
                await qrlp.cache_qr_image_async(str(index), b"image")
            assert await qrlp.get_cached_qr_async("0") is None
            assert await qrlp.get_cached_qr_async("100") == b"image"


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
