"""
Async QRLiveProtocol - Asynchronous QR Live Protocol implementation.

Provides async/await patterns for non-blocking QR generation, verification,
and cryptographic operations with improved performance and scalability.
"""

import asyncio
import concurrent.futures
import logging
import time
from collections import OrderedDict, deque
from collections.abc import AsyncIterator, Callable
from functools import partial
from inspect import isawaitable
from typing import Any, TypeVar

from .config import QRLPConfig
from .core import QRData, QRLiveProtocol

_logger = logging.getLogger("qrlp.async_core")
_Result = TypeVar("_Result")


class AsyncQRLiveProtocol:
    """Run QRLP generation, verification and provider access off the event loop.

    Use an async context manager or call :meth:`aclose` to stop live generation
    and release this instance's worker threads.
    """

    _WORKERS = 4
    _CACHE_SIZE = 100
    _TIMING_WINDOW = 128

    def __init__(self, config: QRLPConfig | None = None):
        self.config = config or QRLPConfig()
        self.sync_qrlp = QRLiveProtocol(self.config)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self._WORKERS)
        self._semaphore = asyncio.Semaphore(10)
        self._generation_task: asyncio.Task[None] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._active_operations = 0
        self._operation_times: dict[str, deque[float]] = {}
        self._image_cache: OrderedDict[str, tuple[bytes, float]] = OrderedDict()
        self._cache_ttl = 60.0
        self._cache_hits = 0
        self._cache_misses = 0

    async def __aenter__(self) -> "AsyncQRLiveProtocol":
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()

    def _ensure_open(self) -> None:
        if self._close_task is not None:
            raise RuntimeError("AsyncQRLiveProtocol is closed")

    async def aclose(self) -> None:
        """Stop live generation and wait for in-flight work without blocking the loop."""
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        await asyncio.shield(self._close_task)

    async def _close(self) -> None:
        await self.stop_live_generation_async()
        await asyncio.to_thread(self._executor.shutdown, wait=True, cancel_futures=True)
        self._image_cache.clear()

    async def _run(self, operation: str, call: Callable[[], _Result]) -> _Result:
        self._ensure_open()
        async with self._semaphore:
            self._ensure_open()
            self._active_operations += 1
            start = time.perf_counter()
            try:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(self._executor, call)
            finally:
                self._active_operations -= 1
                self._operation_times.setdefault(operation, deque(maxlen=self._TIMING_WINDOW)).append(
                    time.perf_counter() - start
                )

    async def generate_single_qr_async(
        self,
        user_data: dict | None = None,
        sign_data: bool | None = True,
        encrypt_data: bool | None = None,
    ) -> tuple[QRData, bytes]:
        """Generate a QR using the same payload and settings as synchronous QRLP."""
        return await self._run(
            "qr_generation",
            partial(self.sync_qrlp.generate_single_qr, user_data, sign_data, encrypt_data),
        )

    async def generate_signed_qr_async(
        self, user_data: dict | None = None, signing_key_id: str | None = None
    ) -> tuple[QRData, bytes]:
        """Generate a signed QR with an optional signing key ID."""
        return await self._run(
            "qr_generation", partial(self.sync_qrlp.generate_signed_qr, user_data, signing_key_id)
        )

    async def generate_encrypted_qr_async(
        self, user_data: dict | None = None, encryption_key_id: str | None = None
    ) -> tuple[QRData, bytes]:
        """Generate an encrypted QR with an optional encryption key ID."""
        return await self._run(
            "qr_generation", partial(self.sync_qrlp.generate_encrypted_qr, user_data, encryption_key_id)
        )

    async def verify_qr_data_async(self, qr_json: str) -> dict[str, Any]:
        """Verify a decoded QR payload off the event loop."""
        return await self._run("qr_verification", partial(self.sync_qrlp.verify_qr_data, qr_json))

    async def batch_generate_qr_async(self, items: list[dict[str, Any]],
                                     sign_data: bool | None = True,
                                     encrypt_data: bool | None = None) -> list[tuple[QRData, bytes]]:
        """
        Generate multiple QR codes asynchronously in parallel.

        Args:
            items: List of data items to encode
            sign_data: Whether to sign each QR
            encrypt_data: Whether to encrypt each QR

        Returns:
            List of (QRData, QR image) tuples
        """
        self._ensure_open()
        # Create async tasks for each item
        tasks = [
            self.generate_single_qr_async(item, sign_data, encrypt_data)
            for item in items
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        successful_results = []
        for result in results:
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, Exception):
                _logger.error("Batch generation error: %s", result)
            else:
                successful_results.append(result)

        return successful_results

    async def iter_qr_stream_async(
        self, interval: float = 1.0, max_qrs: int | None = None
    ) -> AsyncIterator[tuple[QRData, bytes]]:
        """Yield frames one at a time without retaining previous images."""
        self._ensure_open()
        count = 0
        while max_qrs is None or count < max_qrs:
            if count:
                await asyncio.sleep(interval)
            yield await self.generate_single_qr_async()
            count += 1

    async def generate_qr_stream_async(
        self,
        interval: float = 1.0,
        max_qrs: int | None = None,
        callback: Callable | None = None,
    ) -> list[tuple[QRData, bytes]]:
        """Collect frames, preserving partial results after errors or cancellation.

        Use :meth:`iter_qr_stream_async` for a long stream without retaining images.
        """
        self._ensure_open()
        frames = []
        try:
            async for frame in self.iter_qr_stream_async(interval, max_qrs):
                frames.append(frame)
                if callback is not None:
                    try:
                        await self._notify_callback(callback, *frame)
                    except Exception:
                        _logger.exception("Stream callback error")
        except asyncio.CancelledError:
            _logger.info("QR stream generation cancelled")
        except Exception:
            _logger.exception("Stream generation error")
        return frames

    @staticmethod
    async def _notify_callback(callback: Callable, data: QRData, image: bytes) -> None:
        result = callback(data, image)
        if isawaitable(result):
            await result

    async def get_blockchain_data_async(self) -> dict[str, str]:
        """Read the shared blockchain tip cache and schedule a refresh if stale."""
        self._ensure_open()
        try:
            return await self._run(
                "blockchain", self.sync_qrlp.blockchain_verifier.get_blockchain_hashes
            )
        except Exception:
            _logger.exception("Blockchain provider failed")
            return {}

    async def get_time_data_async(self) -> dict[str, dict[str, str]]:
        """Return observations from the configured sources used for QR generation."""
        self._ensure_open()
        try:
            observations = await self._run(
                "time_sync", self.sync_qrlp.time_provider.get_time_server_verification
            )
        except Exception:
            _logger.exception("Time provider failed")
            return {}
        return {
            server: {
                "timestamp": observation["timestamp"],
                "offset": str(observation["offset"]),
                "server": server,
            }
            for server, observation in observations.items()
        }

    async def start_live_generation_async(self, callback: Callable | None = None) -> None:
        """Start one background generator with an optional sync or async callback."""
        self._ensure_open()
        if self._generation_task is not None and not self._generation_task.done():
            return

        async def generation_loop() -> None:
            while True:
                try:
                    frame = await self.generate_single_qr_async()
                    if callback is not None:
                        await self._notify_callback(callback, *frame)
                    await asyncio.sleep(self.config.update_interval)
                except Exception:
                    _logger.exception("Async generation error")
                    await asyncio.sleep(1.0)

        self._generation_task = asyncio.create_task(generation_loop())

    async def stop_live_generation_async(self) -> None:
        """Cancel and wait for the active background generator."""
        task = self._generation_task
        if task is None or task.done():
            return
        task.cancel()
        if task is not asyncio.current_task():
            await asyncio.gather(task, return_exceptions=True)

    async def get_performance_stats_async(self) -> dict[str, Any]:
        """
        Get comprehensive performance statistics asynchronously.

        Returns:
            Dictionary with performance metrics
        """
        return self._performance_stats()

    def _performance_stats(self) -> dict[str, Any]:
        perf_stats = {}
        for operation, times in self._operation_times.items():
            if times:
                perf_stats[operation] = {
                    'count': len(times),
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times)
                }

        return {
            'cache_stats': {
                'hits': self._cache_hits,
                'misses': self._cache_misses,
                'hit_rate': self._cache_hits / max(1, self._cache_hits + self._cache_misses)
            },
            'operation_performance': perf_stats,
            'concurrent_operations': self._active_operations,
            'memory_usage': self._get_memory_usage(),
            'async_resources': {
                'http_sessions': 0,  # Providers own their own connections.
                'thread_pool_workers': self._WORKERS
            }
        }

    def _get_memory_usage(self) -> dict[str, float]:
        """Get memory usage statistics."""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                'rss_mb': memory_info.rss / 1024 / 1024,
                'vms_mb': memory_info.vms / 1024 / 1024,
                'percent': process.memory_percent()
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            return {'error': str(e)}

    async def cache_qr_image_async(
        self, cache_key: str, qr_image: bytes, ttl: float | None = None
    ) -> None:
        """Cache an image using the given TTL, or the current default TTL."""
        self._ensure_open()
        self._image_cache[cache_key] = (
            qr_image,
            time.monotonic() + (self._cache_ttl if ttl is None else ttl),
        )
        self._image_cache.move_to_end(cache_key)
        if len(self._image_cache) > self._CACHE_SIZE:
            self._image_cache.popitem(last=False)

    async def get_cached_qr_async(self, cache_key: str) -> bytes | None:
        """Return a live cached image, evicting an expired entry if present."""
        self._ensure_open()
        entry = self._image_cache.get(cache_key)
        if entry is not None:
            image, expires_at = entry
            if time.monotonic() < expires_at:
                self._cache_hits += 1
                self._image_cache.move_to_end(cache_key)
                return image
            del self._image_cache[cache_key]
        self._cache_misses += 1
        return None

    async def optimize_performance_async(self) -> dict[str, Any]:
        """
        Analyze and optimize performance asynchronously.

        Returns:
            Optimization recommendations
        """
        # Get current performance stats
        stats = await self.get_performance_stats_async()

        recommendations = []

        # Analyze cache performance
        cache_stats = stats.get('cache_stats', {})
        hit_rate = cache_stats.get('hit_rate', 0)

        if hit_rate < 0.5:
            recommendations.append({
                'type': 'cache_optimization',
                'priority': 'medium',
                'description': 'Cache hit rate is low, consider increasing cache size or TTL',
                'current_hit_rate': hit_rate,
                'recommended_hit_rate': 0.8
            })

        # Analyze operation performance
        op_perf = stats.get('operation_performance', {})
        for operation, metrics in op_perf.items():
            avg_time = metrics.get('avg_time', 0)
            if avg_time > 0.1:  # 100ms threshold
                recommendations.append({
                    'type': 'performance_optimization',
                    'priority': 'high' if avg_time > 0.5 else 'medium',
                    'operation': operation,
                    'description': f'{operation} is slow ({avg_time:.3f}s avg)',
                    'current_avg_time': avg_time,
                    'recommended_max_time': 0.1
                })

        # Memory analysis
        memory = stats.get('memory_usage', {})
        if isinstance(memory, dict) and 'rss_mb' in memory:
            rss_mb = memory['rss_mb']
            if rss_mb > 200:  # 200MB threshold
                recommendations.append({
                    'type': 'memory_optimization',
                    'priority': 'high',
                    'description': f'Memory usage is high ({rss_mb:.1f}MB)',
                    'current_usage': rss_mb,
                    'recommended_max': 200
                })

        return {
            'recommendations': recommendations,
            'performance_stats': stats,
            'optimization_applied': len(recommendations) == 0
        }

    async def apply_optimizations_async(self, auto_optimize: bool = True) -> dict[str, Any]:
        """
        Apply performance optimizations asynchronously.

        Args:
            auto_optimize: Whether to automatically apply optimizations

        Returns:
            Optimization results
        """
        if not auto_optimize:
            return {'message': 'Auto-optimization disabled'}

        optimization_results = await self.optimize_performance_async()

        if not optimization_results.get('recommendations'):
            return {'message': 'No optimizations needed'}

        applied_optimizations = []

        for rec in optimization_results['recommendations']:
            if rec['type'] == 'cache_optimization':
                # Increase cache TTL
                self._cache_ttl = 120  # 2 minutes
                applied_optimizations.append('cache_ttl_increased')

            elif rec['type'] == 'performance_optimization':
                # Reduce update frequency for slow operations
                if rec['operation'] == 'qr_generation':
                    self.config.update_interval = max(self.config.update_interval, 2.0)
                    applied_optimizations.append('update_interval_adjusted')

        return {
            'optimizations_applied': applied_optimizations,
            'recommendations_count': len(optimization_results['recommendations']),
            'performance_improved': len(applied_optimizations) > 0
        }

    # Synchronous compatibility methods
    def generate_single_qr(self, user_data: dict | None = None,
                          sign_data: bool | None = True,
                          encrypt_data: bool | None = None) -> tuple[QRData, bytes]:
        """Generate a QR synchronously."""
        self._ensure_open()
        return self.sync_qrlp.generate_single_qr(user_data, sign_data, encrypt_data)

    def verify_qr_data(self, qr_json: str) -> dict[str, Any]:
        """Verify a QR synchronously."""
        self._ensure_open()
        return self.sync_qrlp.verify_qr_data(qr_json)

    def get_statistics(self) -> dict:
        """Get combined sync and async statistics."""
        sync_stats = self.sync_qrlp.get_statistics()
        async_stats = self._performance_stats()

        return {
            **sync_stats,
            'async_performance': async_stats
        }

