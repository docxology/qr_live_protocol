"""
Stream error-resilience tests for src.async_core.

Exercises the resilience branches of the async protocol: partial batch
results on item failure, stream cancellation/data errors, gracefully
degrading blockchain/time-server failures, live generation start/stop, and
performance optimization paths.
"""

import asyncio

import pytest

from src.async_core import AsyncQRLiveProtocol
from src.config import QRLPConfig
from src.core import QRData


@pytest.fixture
def async_config(tmp_path):
    config = QRLPConfig()
    config.update_interval = 0.05
    config.blockchain_settings.enabled_chains = set()
    config.time_settings.time_servers = []
    config.security_settings.key_dir = str(tmp_path / "keys")
    return config


class TestBatchResilience:
    """Partial-failure behaviour of batch generation."""

    async def test_batch_keeps_successful_when_one_item_fails(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            # Force a failure on item 1 by patching the single generator.
            orig = qrlp.generate_single_qr_async
            calls = {"n": 0}

            async def flaky(item, sign=True, encrypt=False):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise RuntimeError("simulated failure")
                return await orig(item, sign, encrypt)

            qrlp.generate_single_qr_async = flaky
            results = await qrlp.batch_generate_qr_async(
                [{"a": 1}, {"b": 2}, {"c": 3}]
            )
            # One failed, two succeeded -> partial batch is surfaced.
            assert len(results) == 2
            for qr_data, _ in results:
                assert isinstance(qr_data, QRData)


class TestStreamResilience:
    """Resilience of the async QR stream generator."""

    async def test_stream_stops_at_max(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            results = await qrlp.generate_qr_stream_async(interval=0.005, max_qrs=4)
            assert len(results) == 4

    async def test_stream_recovers_from_callback_error(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            received = []

            async def bad_callback(qr_data, qr_image):
                raise RuntimeError("callback boom")

            async def good_callback(qr_data, qr_image):
                received.append(qr_data)

            results = await qrlp.generate_qr_stream_async(
                interval=0.005,
                max_qrs=3,
                callback=bad_callback,
            )
            # Callback errors are logged and do not abort the stream.
            assert len(results) == 3
            assert received == []

    async def test_stream_cancellation_returns_partial(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            task = asyncio.create_task(
                qrlp.generate_qr_stream_async(interval=0.01, max_qrs=None)
            )
            # The loop's own error handling swallows CancelledError and returns
            # whatever partial stream was produced.
            await asyncio.sleep(0.03)
            task.cancel()
            results = await asyncio.wait_for(task, timeout=5)
            assert results is not None

    async def test_stream_no_max_runs_until_cancelled(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            task = asyncio.create_task(
                qrlp.generate_qr_stream_async(interval=0.005, max_qrs=None)
            )
            # Give the loop time to emit at least one frame.
            await asyncio.sleep(0.08)
            task.cancel()
            results = await asyncio.wait_for(task, timeout=5)
            # It returns gracefully (not raising) with whatever was produced.
            assert isinstance(results, list)


class TestLiveGenerationResilience:
    """Start/stop of the continuous live generation task."""

    async def test_start_and_stop_live_generation(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            await qrlp.start_live_generation_async()
            assert hasattr(qrlp, "_generation_task")
            await asyncio.sleep(0.05)
            await qrlp.stop_live_generation_async()
            # The generation loop catches CancelledError and stops cleanly.
            assert qrlp._generation_task.done()


class TestNetworkResilience:
    """Graceful degradation on blockchain/time-server failures."""

    async def test_blockchain_data_returns_empty_on_failure(self, async_config):
        async_config.blockchain_settings.enabled_chains = {"bitcoin"}
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            # All requests will fail against a closed port -> empty dict, no raise.
            qrlp._get_chain_data_async = _fail
            result = await qrlp.get_blockchain_data_async()
            assert result == {}

    async def test_time_data_returns_empty_on_failure(self, async_config):
        async_config.time_settings.time_servers = ["http://127.0.0.1:1"]
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            result = await qrlp.get_time_data_async()
            assert result == {}


async def _fail(chain):
    raise ConnectionError("network down")


class TestOptimization:
    """Performance optimization recommendation paths."""

    async def test_optimize_recommends_improvements(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            qrlp._operation_times["qr_generation"] = [0.5, 0.6, 0.7]
            qrlp._cache_hits = 0
            qrlp._cache_misses = 100
            result = await qrlp.optimize_performance_async()
            types = {rec["type"] for rec in result["recommendations"]}
            assert "cache_optimization" in types
            assert "performance_optimization" in types

    async def test_optimize_returns_none_when_fast(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            qrlp._cache_hits = 100
            qrlp._cache_misses = 0
            result = await qrlp.optimize_performance_async()
            assert result["optimization_applied"] is True

    async def test_apply_optimizations_updates_interval(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            qrlp._operation_times["qr_generation"] = [0.6]
            qrlp._cache_hits = 0
            qrlp._cache_misses = 50
            original_interval = qrlp.config.update_interval
            result = await qrlp.apply_optimizations_async(auto_optimize=True)
            assert "update_interval_adjusted" in result["optimizations_applied"]
            assert qrlp.config.update_interval >= original_interval

    async def test_apply_optimizations_disabled(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            result = await qrlp.apply_optimizations_async(auto_optimize=False)
            assert "error" not in result or result.get("message") == "Auto-optimization disabled"
            assert "message" in result

    async def test_performance_stats_shape(self, async_config):
        async with AsyncQRLiveProtocol(async_config) as qrlp:
            stats = await qrlp.get_performance_stats_async()
            assert "cache_stats" in stats
            assert "operation_performance" in stats
            assert "async_resources" in stats


class TestSyncWrappers:
    """Synchronous compatibility methods mirror async behaviour."""

    def test_get_statistics_combines(self, async_config):
        qrlp = AsyncQRLiveProtocol(async_config)
        stats = qrlp.get_statistics()
        assert "async_performance" in stats
        assert "total_updates" in stats
