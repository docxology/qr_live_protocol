"""
Error Recovery and Resilience Module

Provides circuit breaker patterns, retry logic, and graceful degradation
for robust QRLP operations in production environments.
"""

import time
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, TypeVar, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from .crypto.exceptions import CryptoError


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 60.0      # Seconds before attempting recovery
    success_threshold: int = 3          # Successes needed to close
    timeout: float = 30.0               # Request timeout


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None


class CircuitBreaker:
    """
    Circuit breaker implementation for resilient operations.

    Protects against cascading failures by temporarily stopping
    requests to failing services and allowing recovery testing.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker identifier
            config: Configuration settings
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.stats = CircuitBreakerStats()
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time = 0.0
        self._logger = logging.getLogger(f"circuit_breaker.{name}")

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker."""
        def wrapper(*args, **kwargs):
            if not self._can_execute():
                self._logger.warning(f"Circuit breaker {self.name} is OPEN, rejecting request")
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise

        return wrapper

    async def __call_async(self, func: Callable) -> Callable:
        """Async decorator for async functions."""
        async def wrapper(*args, **kwargs):
            if not self._can_execute():
                self._logger.warning(f"Circuit breaker {self.name} is OPEN, rejecting request")
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise

        return wrapper

    def _can_execute(self) -> bool:
        """Check if circuit breaker allows execution."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self._last_failure_time >= self.config.recovery_timeout:
                self._logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        return False

    def _on_success(self):
        """Handle successful operation."""
        self.stats.successful_requests += 1
        self.stats.last_success_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self._consecutive_successes += 1
            if self._consecutive_successes >= self.config.success_threshold:
                self._logger.info(f"Circuit breaker {self.name} transitioning to CLOSED")
                self.state = CircuitBreakerState.CLOSED
                self._consecutive_failures = 0
                self._consecutive_successes = 0
                self.stats.state_changes += 1

    def _on_failure(self):
        """Handle failed operation."""
        self.stats.failed_requests += 1
        self.stats.last_failure_time = time.time()
        self._consecutive_failures += 1

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Failed in half-open state, go back to open
            self._logger.warning(f"Circuit breaker {self.name} failed in HALF_OPEN, returning to OPEN")
            self.state = CircuitBreakerState.OPEN
            self._consecutive_successes = 0
            self.stats.state_changes += 1
        elif self._consecutive_failures >= self.config.failure_threshold:
            # Too many failures, open circuit
            self._logger.warning(f"Circuit breaker {self.name} opening after {self._consecutive_failures} failures")
            self.state = CircuitBreakerState.OPEN
            self.stats.state_changes += 1

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self.stats

    def reset(self):
        """Reset circuit breaker to initial state."""
        self.state = CircuitBreakerState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self.stats = CircuitBreakerStats()


class RetryStrategy:
    """Configurable retry strategy with exponential backoff."""

    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, backoff_factor: float = 2.0):
        """
        Initialize retry strategy.

        Args:
            max_attempts: Maximum retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay between retries
            backoff_factor: Exponential backoff multiplier
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay)

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if retry should be attempted."""
        # Don't retry on certain exceptions
        if isinstance(exception, (KeyboardInterrupt, SystemExit)):
            return False

        # Don't retry if max attempts reached
        if attempt >= self.max_attempts:
            return False

        return True


class ResilientOperation:
    """
    Resilient operation wrapper with retry and circuit breaker support.

    Combines retry logic with circuit breaker patterns for maximum
    reliability in distributed systems.
    """

    def __init__(self, name: str, retry_strategy: RetryStrategy = None,
                 circuit_breaker: CircuitBreaker = None):
        """
        Initialize resilient operation.

        Args:
            name: Operation identifier
            retry_strategy: Retry configuration
            circuit_breaker: Circuit breaker instance
        """
        self.name = name
        self.retry_strategy = retry_strategy or RetryStrategy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name)
        self._logger = logging.getLogger(f"resilient_op.{name}")

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute operation with retry and circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            Exception: If all retries fail
        """
        for attempt in range(1, self.retry_strategy.max_attempts + 1):
            try:
                # Apply circuit breaker protection
                result = self.circuit_breaker(func)(*args, **kwargs)
                self._logger.debug(f"Operation {self.name} succeeded on attempt {attempt}")
                return result

            except CircuitBreakerOpenError:
                raise  # Don't retry circuit breaker opens

            except Exception as e:
                self._logger.warning(f"Operation {self.name} failed on attempt {attempt}: {e}")

                if not self.retry_strategy.should_retry(attempt, e):
                    self._logger.error(f"Operation {self.name} failed after {attempt} attempts")
                    raise

                # Calculate delay and wait
                delay = self.retry_strategy.calculate_delay(attempt)
                self._logger.info(f"Retrying operation {self.name} in {delay:.1f}s (attempt {attempt + 1})")
                time.sleep(delay)

        # Should never reach here due to should_retry check
        raise RuntimeError(f"Operation {self.name} failed unexpectedly")

    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute async operation with retry and circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        for attempt in range(1, self.retry_strategy.max_attempts + 1):
            try:
                # Apply circuit breaker protection to async function
                protected_func = self.circuit_breaker.__call_async(func)
                result = await protected_func(*args, **kwargs)
                self._logger.debug(f"Async operation {self.name} succeeded on attempt {attempt}")
                return result

            except CircuitBreakerOpenError:
                raise  # Don't retry circuit breaker opens

            except Exception as e:
                self._logger.warning(f"Async operation {self.name} failed on attempt {attempt}: {e}")

                if not self.retry_strategy.should_retry(attempt, e):
                    self._logger.error(f"Async operation {self.name} failed after {attempt} attempts")
                    raise

                # Calculate delay and wait
                delay = self.retry_strategy.calculate_delay(attempt)
                self._logger.info(f"Retrying async operation {self.name} in {delay:.1f}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)

        # Should never reach here
        raise RuntimeError(f"Async operation {self.name} failed unexpectedly")


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers.

    Provides centralized management of circuit breakers for
    different operations and services.
    """

    def __init__(self):
        """Initialize circuit breaker manager."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._logger = logging.getLogger("circuit_breaker_manager")

    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """
        Get or create circuit breaker for operation.

        Args:
            name: Circuit breaker name
            config: Optional configuration

        Returns:
            CircuitBreaker instance
        """
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
            self._logger.info(f"Created circuit breaker: {name}")

        return self.circuit_breakers[name]

    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers."""
        return {
            name: cb.get_stats()
            for name, cb in self.circuit_breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.reset()
        self._logger.info("Reset all circuit breakers")


class ResilienceManager:
    """
    Comprehensive resilience management for QRLP.

    Provides circuit breakers, retry logic, and graceful degradation
    for all QRLP operations including cryptographic, network, and I/O operations.
    """

    def __init__(self):
        """Initialize resilience manager."""
        self.circuit_breaker_manager = CircuitBreakerManager()
        self.retry_strategies: Dict[str, RetryStrategy] = {}
        self.resilient_operations: Dict[str, ResilientOperation] = {}
        self._logger = logging.getLogger("resilience_manager")

        # Setup default circuit breakers
        self._setup_default_circuit_breakers()

        # Setup default retry strategies
        self._setup_default_retry_strategies()

    def _setup_default_circuit_breakers(self):
        """Setup default circuit breakers for QRLP operations."""
        # Blockchain API circuit breaker
        blockchain_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2
        )
        self.circuit_breaker_manager.get_circuit_breaker("blockchain_api", blockchain_config)

        # Time server circuit breaker
        time_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=45.0,
            success_threshold=3
        )
        self.circuit_breaker_manager.get_circuit_breaker("time_servers", time_config)

        # QR generation circuit breaker
        qr_config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=60.0,
            success_threshold=5
        )
        self.circuit_breaker_manager.get_circuit_breaker("qr_generation", qr_config)

    def _setup_default_retry_strategies(self):
        """Setup default retry strategies."""
        # Network operations
        self.retry_strategies["network"] = RetryStrategy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0
        )

        # Cryptographic operations
        self.retry_strategies["crypto"] = RetryStrategy(
            max_attempts=2,
            base_delay=0.5,
            max_delay=2.0
        )

        # File I/O operations
        self.retry_strategies["file_io"] = RetryStrategy(
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0
        )

    def create_resilient_operation(self, name: str,
                                  retry_strategy: str = "network",
                                  circuit_breaker: str = None) -> ResilientOperation:
        """
        Create resilient operation with specified strategies.

        Args:
            name: Operation name
            retry_strategy: Name of retry strategy to use
            circuit_breaker: Name of circuit breaker to use

        Returns:
            ResilientOperation instance
        """
        retry_config = self.retry_strategies.get(retry_strategy, RetryStrategy())
        cb = None

        if circuit_breaker:
            cb = self.circuit_breaker_manager.get_circuit_breaker(circuit_breaker)

        resilient_op = ResilientOperation(name, retry_config, cb)
        self.resilient_operations[name] = resilient_op

        return resilient_op

    def get_resilient_operation(self, name: str) -> Optional[ResilientOperation]:
        """Get existing resilient operation."""
        return self.resilient_operations.get(name)

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall resilience health status."""
        cb_stats = self.circuit_breaker_manager.get_all_stats()

        # Analyze circuit breaker health
        open_circuits = []
        degraded_circuits = []

        for name, stats in cb_stats.items():
            # Check if circuit is open
            if hasattr(self.circuit_breaker_manager.circuit_breakers[name], 'state'):
                state = self.circuit_breaker_manager.circuit_breakers[name].state
                if state == CircuitBreakerState.OPEN:
                    open_circuits.append(name)
                elif state == CircuitBreakerState.HALF_OPEN:
                    degraded_circuits.append(name)

        # Overall health assessment
        if open_circuits:
            health = "critical"
            message = f"{len(open_circuits)} circuit(s) open: {', '.join(open_circuits)}"
        elif degraded_circuits:
            health = "degraded"
            message = f"{len(degraded_circuits)} circuit(s) in recovery: {', '.join(degraded_circuits)}"
        else:
            health = "healthy"
            message = "All circuits operational"

        return {
            "health": health,
            "message": message,
            "open_circuits": open_circuits,
            "degraded_circuits": degraded_circuits,
            "circuit_breaker_stats": cb_stats,
            "active_operations": len(self.resilient_operations)
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


# Global resilience manager instance
resilience_manager = ResilienceManager()


def resilient_qr_generation(qrlp_instance, user_data: Optional[Dict] = None,
                          sign_data: bool = True, encrypt_data: bool = False):
    """
    Resilient QR generation with automatic retry and circuit breaker protection.

    Args:
        qrlp_instance: QRLiveProtocol instance
        user_data: Optional user data
        sign_data: Whether to sign the QR
        encrypt_data: Whether to encrypt the QR

    Returns:
        Tuple of (QRData, QR image bytes)
    """
    operation = resilience_manager.get_resilient_operation("qr_generation")
    if not operation:
        operation = resilience_manager.create_resilient_operation("qr_generation")

    return operation.execute(
        qrlp_instance.generate_single_qr,
        user_data, sign_data, encrypt_data
    )


async def resilient_qr_generation_async(qrlp_instance, user_data: Optional[Dict] = None,
                                       sign_data: bool = True, encrypt_data: bool = False):
    """
    Async resilient QR generation.

    Args:
        qrlp_instance: QRLiveProtocol instance
        user_data: Optional user data
        sign_data: Whether to sign the QR
        encrypt_data: Whether to encrypt the QR

    Returns:
        Tuple of (QRData, QR image bytes)
    """
    operation = resilience_manager.get_resilient_operation("qr_generation_async")
    if not operation:
        operation = resilience_manager.create_resilient_operation("qr_generation_async")

    return await operation.execute_async(
        qrlp_instance.generate_single_qr_async,
        user_data, sign_data, encrypt_data
    )


def resilient_verification(qrlp_instance, qr_json: str) -> Dict[str, bool]:
    """
    Resilient QR verification with automatic retry.

    Args:
        qrlp_instance: QRLiveProtocol instance
        qr_json: JSON string from QR code

    Returns:
        Verification results dictionary
    """
    operation = resilience_manager.get_resilient_operation("qr_verification")
    if not operation:
        operation = resilience_manager.create_resilient_operation("qr_verification")

    return operation.execute(qrlp_instance.verify_qr_data, qr_json)


async def resilient_verification_async(qrlp_instance, qr_json: str) -> Dict[str, bool]:
    """
    Async resilient QR verification.

    Args:
        qrlp_instance: QRLiveProtocol instance
        qr_json: JSON string from QR code

    Returns:
        Verification results dictionary
    """
    operation = resilience_manager.get_resilient_operation("qr_verification_async")
    if not operation:
        operation = resilience_manager.create_resilient_operation("qr_verification_async")

    return await operation.execute_async(qrlp_instance.verify_qr_data_async, qr_json)

