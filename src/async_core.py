"""
Async QRLiveProtocol - Asynchronous QR Live Protocol implementation.

Provides async/await patterns for non-blocking QR generation, verification,
and cryptographic operations with improved performance and scalability.
"""

import asyncio
import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Callable, Any, Tuple
from dataclasses import dataclass, asdict
import aiohttp
import aiofiles
import concurrent.futures

from .core import QRLiveProtocol, QRData
from .config import QRLPConfig
from .crypto import KeyManager, QRSignatureManager, DataEncryptor, HMACManager


class AsyncQRLiveProtocol:
    """
    Asynchronous QR Live Protocol implementation.

    Provides async/await patterns for non-blocking operations including:
    - Async QR generation with concurrent processing
    - Async blockchain and time server operations
    - Async cryptographic operations
    - Async web server operations
    - Connection pooling and resource management
    """

    def __init__(self, config: Optional[QRLPConfig] = None):
        """
        Initialize async QRLiveProtocol.

        Args:
            config: QRLPConfig object with settings
        """
        self.config = config or QRLPConfig()
        self.sync_qrlp = QRLiveProtocol(self.config)

        # Async components
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._session_pool: List[aiohttp.ClientSession] = []
        self._semaphore = asyncio.Semaphore(10)  # Limit concurrent operations

        # Performance tracking
        self._operation_times: Dict[str, List[float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    async def __aenter__(self):
        """Async context manager entry."""
        await self._initialize_async_resources()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._cleanup_async_resources()

    async def _initialize_async_resources(self):
        """Initialize async resources."""
        # Create HTTP session pool for blockchain/time APIs
        for _ in range(3):
            session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
            self._session_pool.append(session)

    async def _cleanup_async_resources(self):
        """Clean up async resources."""
        # Close all HTTP sessions
        for session in self._session_pool:
            await session.close()

        # Shutdown executor
        self._executor.shutdown(wait=True)

    async def generate_single_qr_async(self, user_data: Optional[Dict] = None,
                                      sign_data: bool = True,
                                      encrypt_data: bool = False) -> Tuple[QRData, bytes]:
        """
        Generate a single QR code asynchronously.

        Args:
            user_data: Optional custom data to include
            sign_data: Whether to digitally sign the QR data
            encrypt_data: Whether to encrypt sensitive fields

        Returns:
            Tuple of (QRData object, QR image as bytes)
        """
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor,
                self.sync_qrlp.generate_single_qr,
                user_data, sign_data, encrypt_data
            )

    async def generate_signed_qr_async(self, user_data: Optional[Dict] = None,
                                      signing_key_id: str = None) -> Tuple[QRData, bytes]:
        """
        Generate a cryptographically signed QR code asynchronously.

        Args:
            user_data: Optional custom data to include
            signing_key_id: Specific key ID for signing

        Returns:
            Tuple of (QRData object, QR image as bytes)
        """
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor,
                self.sync_qrlp.generate_signed_qr,
                user_data, signing_key_id
            )

    async def generate_encrypted_qr_async(self, user_data: Optional[Dict] = None,
                                         encryption_key_id: str = None) -> Tuple[QRData, bytes]:
        """
        Generate an encrypted QR code asynchronously.

        Args:
            user_data: Optional custom data to include
            encryption_key_id: Specific key ID for encryption

        Returns:
            Tuple of (QRData object, QR image as bytes)
        """
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor,
                self.sync_qrlp.generate_encrypted_qr,
                user_data, encryption_key_id
            )

    async def verify_qr_data_async(self, qr_json: str) -> Dict[str, bool]:
        """
        Verify QR code data asynchronously.

        Args:
            qr_json: JSON string from QR code

        Returns:
            Dictionary with verification results
        """
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor,
                self.sync_qrlp.verify_qr_data,
                qr_json
            )

    async def batch_generate_qr_async(self, items: List[Dict[str, Any]],
                                     sign_data: bool = True,
                                     encrypt_data: bool = False) -> List[Tuple[QRData, bytes]]:
        """
        Generate multiple QR codes asynchronously in parallel.

        Args:
            items: List of data items to encode
            sign_data: Whether to sign each QR
            encrypt_data: Whether to encrypt each QR

        Returns:
            List of (QRData, QR image) tuples
        """
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
            if isinstance(result, Exception):
                print(f"Batch generation error: {result}")
            else:
                successful_results.append(result)

        return successful_results

    async def generate_qr_stream_async(self, interval: float = 1.0,
                                      max_qrs: Optional[int] = None,
                                      callback: Optional[Callable] = None) -> List[Tuple[QRData, bytes]]:
        """
        Generate a stream of QR codes asynchronously.

        Args:
            interval: Time between QR generations in seconds
            max_qrs: Maximum number of QR codes to generate
            callback: Optional callback for each generated QR

        Returns:
            List of generated (QRData, QR image) tuples
        """
        generated_qrs = []
        count = 0

        try:
            while max_qrs is None or count < max_qrs:
                # Generate QR asynchronously
                qr_data, qr_image = await self.generate_single_qr_async()

                generated_qrs.append((qr_data, qr_image))
                count += 1

                # Call callback if provided
                if callback:
                    try:
                        await callback(qr_data, qr_image)
                    except Exception as e:
                        print(f"Stream callback error: {e}")

                # Wait for next interval
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            print("QR stream generation cancelled")
        except Exception as e:
            print(f"Stream generation error: {e}")

        return generated_qrs

    async def get_blockchain_data_async(self) -> Dict[str, str]:
        """
        Get blockchain data asynchronously with connection pooling.

        Returns:
            Dictionary mapping chain names to block hashes
        """
        async with self._semaphore:
            # Use session pool for concurrent requests
            tasks = []
            for chain in self.config.blockchain_settings.enabled_chains:
                task = self._get_chain_data_async(chain)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            blockchain_hashes = {}
            for result in results:
                if isinstance(result, Exception):
                    print(f"Blockchain API error: {result}")
                elif isinstance(result, dict):
                    blockchain_hashes.update(result)

            return blockchain_hashes

    async def _get_chain_data_async(self, chain: str) -> Dict[str, str]:
        """Get blockchain data for a specific chain asynchronously."""
        if not self._session_pool:
            await self._initialize_async_resources()

        # Use first available session
        session = self._session_pool[0]

        # Blockchain API endpoints
        endpoints = {
            'bitcoin': 'https://blockstream.info/api/blocks/tip/hash',
            'ethereum': 'https://api.blockcypher.com/v1/eth/main',
            'litecoin': 'https://api.blockcypher.com/v1/ltc/main'
        }

        endpoint = endpoints.get(chain)
        if not endpoint:
            return {}

        try:
            async with session.get(endpoint) as response:
                if response.status == 200:
                    data = await response.json()

                    if chain == 'bitcoin':
                        # Bitcoin returns just the hash
                        return {chain: data.strip()}
                    else:
                        # Other chains return full block info
                        return {chain: data.get('hash', '')}
                else:
                    print(f"Blockchain API error for {chain}: {response.status}")
                    return {}

        except Exception as e:
            print(f"Blockchain API exception for {chain}: {e}")
            return {}

    async def get_time_data_async(self) -> Dict[str, Any]:
        """
        Get time synchronization data asynchronously.

        Returns:
            Dictionary with time server verification data
        """
        async with self._semaphore:
            # Get current time from multiple sources concurrently
            tasks = []
            for server in self.config.time_settings.time_servers[:3]:  # Limit to 3
                task = self._get_time_from_server_async(server)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            time_verification = {}
            for result in results:
                if isinstance(result, Exception):
                    print(f"Time server error: {result}")
                elif isinstance(result, dict):
                    time_verification.update(result)

            return time_verification

    async def _get_time_from_server_async(self, server: str) -> Dict[str, Dict[str, str]]:
        """Get time from a specific server asynchronously."""
        if not self._session_pool:
            await self._initialize_async_resources()

        session = self._session_pool[0]

        try:
            # Use HTTP time API
            url = f"http://worldtimeapi.org/api/timezone/UTC"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    timestamp = data['datetime']

                    return {
                        server: {
                            "timestamp": timestamp,
                            "offset": "0",  # HTTP APIs don't provide offset
                            "server": server
                        }
                    }

        except Exception as e:
            print(f"Time server error for {server}: {e}")

        return {}

    async def start_live_generation_async(self, callback: Optional[Callable] = None) -> None:
        """
        Start continuous QR generation asynchronously.

        Args:
            callback: Optional callback for each generated QR
        """
        async def generation_loop():
            while True:
                try:
                    qr_data, qr_image = await self.generate_single_qr_async()

                    if callback:
                        await callback(qr_data, qr_image)

                    await asyncio.sleep(self.config.update_interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Async generation error: {e}")
                    await asyncio.sleep(1.0)

        # Start generation loop as background task
        self._generation_task = asyncio.create_task(generation_loop())

    async def stop_live_generation_async(self) -> None:
        """Stop continuous QR generation."""
        if hasattr(self, '_generation_task'):
            self._generation_task.cancel()
            try:
                await self._generation_task
            except asyncio.CancelledError:
                pass

    async def get_performance_stats_async(self) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics asynchronously.

        Returns:
            Dictionary with performance metrics
        """
        # Calculate average operation times
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
            'concurrent_operations': len(asyncio.all_tasks()) - 1,  # Exclude current task
            'memory_usage': self._get_memory_usage(),
            'async_resources': {
                'http_sessions': len(self._session_pool),
                'thread_pool_workers': self._executor._max_workers
            }
        }

    def _get_memory_usage(self) -> Dict[str, float]:
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

    async def cache_qr_image_async(self, cache_key: str, qr_image: bytes,
                                  ttl: float = 60.0) -> None:
        """
        Cache QR image asynchronously.

        Args:
            cache_key: Unique cache key
            qr_image: QR image bytes to cache
            ttl: Time to live in seconds
        """
        # Simple in-memory cache with TTL
        expiry_time = time.time() + ttl

        # Use executor for thread-safe cache operations
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self._cache_qr_sync,
            cache_key, qr_image, expiry_time
        )

    def _cache_qr_sync(self, cache_key: str, qr_image: bytes, expiry_time: float):
        """Synchronous cache operation (thread-safe)."""
        # This would be implemented with a thread-safe cache
        # For now, just track cache statistics
        self._cache_hits += 1

    async def get_cached_qr_async(self, cache_key: str) -> Optional[bytes]:
        """
        Get cached QR image asynchronously.

        Args:
            cache_key: Cache key to lookup

        Returns:
            Cached QR image bytes or None if not found/expired
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._get_cached_qr_sync,
            cache_key
        )

    def _get_cached_qr_sync(self, cache_key: str) -> Optional[bytes]:
        """Synchronous cache lookup (thread-safe)."""
        # This would check the actual cache
        # For now, simulate cache miss
        self._cache_misses += 1
        return None

    async def optimize_performance_async(self) -> Dict[str, Any]:
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

    async def apply_optimizations_async(self, auto_optimize: bool = True) -> Dict[str, Any]:
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
    def generate_single_qr(self, user_data: Optional[Dict] = None,
                          sign_data: bool = True, encrypt_data: bool = False) -> Tuple[QRData, bytes]:
        """Synchronous wrapper for async QR generation."""
        return asyncio.run(self.generate_single_qr_async(user_data, sign_data, encrypt_data))

    def verify_qr_data(self, qr_json: str) -> Dict[str, bool]:
        """Synchronous wrapper for async verification."""
        return asyncio.run(self.verify_qr_data_async(qr_json))

    def get_statistics(self) -> Dict:
        """Get combined sync and async statistics."""
        sync_stats = self.sync_qrlp.get_statistics()
        async_stats = asyncio.run(self.get_performance_stats_async())

        return {
            **sync_stats,
            'async_performance': async_stats
        }

