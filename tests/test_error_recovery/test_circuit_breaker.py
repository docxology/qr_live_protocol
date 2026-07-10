"""
Unit tests for Circuit Breaker error recovery functionality.

Tests circuit breaker state management, failure detection, and recovery patterns.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.error_recovery import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState,
    CircuitBreakerOpenError
)


class TestCircuitBreaker:
    """Test suite for CircuitBreaker class."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes correctly."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=5.0,
            success_threshold=2
        )
        cb = CircuitBreaker("test_circuit", config)

        assert cb.name == "test_circuit"
        assert cb.config == config
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb._consecutive_failures == 0
        assert cb._consecutive_successes == 0

    def test_circuit_breaker_default_config(self):
        """Test circuit breaker with default configuration."""
        cb = CircuitBreaker("default_test")

        assert cb.config.failure_threshold == 5
        assert cb.config.recovery_timeout == 60.0
        assert cb.config.success_threshold == 3

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state allows execution."""
        cb = CircuitBreaker("closed_test")

        def successful_operation():
            return "success"

        # Should allow execution in closed state
        result = cb.execute(successful_operation)
        assert result == "success"
        assert cb.stats.successful_requests == 1

    def test_circuit_breaker_rejects_invalid_config(self):
        """Test invalid circuit breaker configuration fails loudly."""
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreakerConfig(failure_threshold=0)

        with pytest.raises(ValueError, match="recovery_timeout"):
            CircuitBreakerConfig(recovery_timeout=-0.1)

        with pytest.raises(ValueError, match="success_threshold"):
            CircuitBreakerConfig(success_threshold=0)

    def test_circuit_breaker_failure_detection(self):
        """Test circuit breaker detects failures and opens circuit."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=1.0)
        cb = CircuitBreaker("failure_test", config)

        def failing_operation():
            raise ConnectionError("Service unavailable")

        # First failure - should still be closed
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb._consecutive_failures == 1
        assert cb.stats.failed_requests == 1

        # Second failure - should open circuit
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN
        assert cb._consecutive_failures == 2
        assert cb.stats.failed_requests == 2
        assert cb.stats.state_changes == 1

    def test_circuit_breaker_open_state_blocks_execution(self):
        """Test circuit breaker in open state blocks execution."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=10.0)
        cb = CircuitBreaker("open_test", config)

        def failing_operation():
            raise ConnectionError("Service down")

        # Trigger failure to open circuit
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Should now block execution
        with pytest.raises(CircuitBreakerOpenError):
            cb.execute(lambda: "should_not_execute")

    def test_circuit_breaker_recovery_attempt(self):
        """Test circuit breaker recovery mechanism."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,  # Very short timeout for testing
            success_threshold=1
        )
        cb = CircuitBreaker("recovery_test", config)

        def failing_operation():
            raise ConnectionError("Service down")

        def successful_operation():
            return "recovered"

        # Trigger failure to open circuit
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Should transition to half-open and succeed
        result = cb.execute(successful_operation)
        assert result == "recovered"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.stats.state_changes == 2  # Open -> Half-open -> Closed

    def test_circuit_breaker_half_open_failure(self):
        """Test circuit breaker returns to open state after half-open failure."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=1
        )
        cb = CircuitBreaker("half_open_test", config)

        def failing_operation():
            raise ConnectionError("Still failing")

        # Trigger failure to open circuit
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Should be in half-open state, fail again
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.stats.state_changes == 2  # Open -> Half-open -> Open

    def test_circuit_breaker_multiple_success_threshold(self):
        """Test circuit breaker requires multiple successes to close."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=3  # Require 3 successes
        )
        cb = CircuitBreaker("multi_success_test", config)

        def failing_operation():
            raise ConnectionError("Service down")

        def successful_operation():
            return "success"

        # Trigger failure to open circuit
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Should be in half-open state
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # First success - still half-open
        result = cb.execute(successful_operation)
        assert result == "success"
        assert cb.state == CircuitBreakerState.HALF_OPEN
        assert cb._consecutive_successes == 1

        # Second success - still half-open
        result = cb.execute(successful_operation)
        assert result == "success"
        assert cb.state == CircuitBreakerState.HALF_OPEN
        assert cb._consecutive_successes == 2

        # Third success - should close circuit
        result = cb.execute(successful_operation)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb._consecutive_successes == 0

    def test_circuit_breaker_stats_tracking(self):
        """Test circuit breaker statistics tracking."""
        cb = CircuitBreaker("stats_test")

        def successful_operation():
            return "success"

        def failing_operation():
            raise ConnectionError("Failure")

        # Initial stats
        stats = cb.get_stats()
        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.failed_requests == 0
        assert stats.state_changes == 0

        # Successful operation
        result = cb.execute(successful_operation)
        stats = cb.get_stats()
        assert stats.total_requests == 1
        assert stats.successful_requests == 1
        assert stats.failed_requests == 0

        # Failed operation
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        stats = cb.get_stats()
        assert stats.total_requests == 2
        assert stats.successful_requests == 1
        assert stats.failed_requests == 1

    def test_circuit_breaker_reset(self):
        """Test circuit breaker reset functionality."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("reset_test", config)

        def failing_operation():
            raise ConnectionError("Failure")

        # Trigger failure to open circuit
        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Reset circuit breaker
        cb.reset()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb._consecutive_failures == 0
        assert cb._consecutive_successes == 0

        # Should now allow execution
        result = cb.execute(lambda: "after_reset")
        assert result == "after_reset"

    def test_circuit_breaker_timeout_handling(self):
        """Test circuit breaker timeout behavior."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.5,  # 500ms timeout
            timeout=0.1  # 100ms operation timeout
        )
        cb = CircuitBreaker("timeout_test", config)

        def timeout_operation():
            """Operation that times out."""
            time.sleep(0.2)  # Sleep longer than timeout
            return "should_not_reach"

        # This should fail due to timeout and open circuit
        with pytest.raises(TimeoutError):
            cb.execute(timeout_operation)

        # Wait for recovery timeout
        time.sleep(0.6)

        # Should now be in half-open state
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_decorator_functionality(self):
        """Test circuit breaker decorator functionality."""
        cb = CircuitBreaker("decorator_test")

        @cb
        def decorated_function(x, y):
            return x + y

        # Should work normally
        result = decorated_function(2, 3)
        assert result == 5

        # Should track statistics
        stats = cb.get_stats()
        assert stats.successful_requests == 1
        assert stats.total_requests == 1

    def test_circuit_breaker_exception_handling(self):
        """Test circuit breaker handles various exception types."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("exception_test", config)

        def operation_that_raises_value_error():
            raise ValueError("Value error")

        def operation_that_raises_runtime_error():
            raise RuntimeError("Runtime error")

        # Both types of exceptions should be handled the same way
        with pytest.raises(ValueError):
            cb.execute(operation_that_raises_value_error)

        assert cb._consecutive_failures == 1

        with pytest.raises(RuntimeError):
            cb.execute(operation_that_raises_runtime_error)

        assert cb._consecutive_failures == 2
        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_concurrent_access(self):
        """Test circuit breaker thread safety."""
        cb = CircuitBreaker("concurrent_test")

        def concurrent_operation(index):
            if index == 0:
                raise ConnectionError("Concurrent failure")
            return "concurrent_success"

        # Run multiple concurrent operations
        results = []
        errors = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(cb.execute, concurrent_operation, index)
                for index in range(10)
            ]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except ConnectionError as exc:
                    errors.append(exc)

        # Check results
        success_count = results.count("concurrent_success")

        # Should have 9 successes and one controlled failure without unhandled thread errors
        assert success_count == 9
        assert len(errors) == 1

        # Circuit breaker should have handled the failure
        stats = cb.get_stats()
        assert stats.total_requests == 10
        assert stats.successful_requests == 9
        assert stats.failed_requests == 1

    def test_circuit_breaker_concurrent_failures_open_once(self):
        """Test concurrent threshold failures only record one open transition."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("concurrent_open_test", config)
        barrier = threading.Barrier(2)

        def failing_operation():
            barrier.wait(timeout=1.0)
            raise ConnectionError("Concurrent failure")

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(cb.execute, failing_operation)
                for _ in range(2)
            ]
            for future in futures:
                with pytest.raises(ConnectionError):
                    future.result(timeout=2.0)

        assert cb.state == CircuitBreakerState.OPEN
        stats = cb.get_stats()
        assert stats.failed_requests == 2
        assert stats.state_changes == 1

    def test_circuit_breaker_half_open_allows_single_recovery_probe(self):
        """Test half-open state permits only one in-flight recovery probe."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        cb = CircuitBreaker("single_probe_test", config)
        started = threading.Event()
        release = threading.Event()

        def failing_operation():
            raise ConnectionError("Service down")

        def slow_successful_operation():
            started.set()
            assert release.wait(timeout=1.0)
            return "recovered"

        with pytest.raises(ConnectionError):
            cb.execute(failing_operation)

        time.sleep(0.2)

        with ThreadPoolExecutor(max_workers=1) as executor:
            probe = executor.submit(cb.execute, slow_successful_operation)
            assert started.wait(timeout=1.0)

            with pytest.raises(CircuitBreakerOpenError):
                cb.execute(lambda: "second_probe")

            release.set()
            assert probe.result(timeout=1.0) == "recovered"

        assert cb.state == CircuitBreakerState.CLOSED
        stats = cb.get_stats()
        assert stats.successful_requests == 1
        assert stats.failed_requests == 2

    def test_circuit_breaker_execute_async_tracks_success(self):
        """Test async execution awaits the operation and tracks success."""
        cb = CircuitBreaker("async_success_test")

        async def successful_operation():
            await asyncio.sleep(0)
            return "async_success"

        result = asyncio.run(cb.execute_async(successful_operation))

        assert result == "async_success"
        stats = cb.get_stats()
        assert stats.total_requests == 1
        assert stats.successful_requests == 1

    def test_circuit_breaker_execute_async_timeout_opens_circuit(self):
        """Test async timeout failures are counted and open the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=1.0,
            timeout=0.01,
        )
        cb = CircuitBreaker("async_timeout_test", config)

        async def slow_operation():
            await asyncio.sleep(0.1)
            return "too_slow"

        with pytest.raises(TimeoutError):
            asyncio.run(cb.execute_async(slow_operation))

        assert cb.state == CircuitBreakerState.OPEN
        stats = cb.get_stats()
        assert stats.total_requests == 1
        assert stats.failed_requests == 1

    def test_circuit_breaker_async_decorator_awaits_operation(self):
        """Test async decorator support awaits the wrapped coroutine."""
        cb = CircuitBreaker("async_decorator_test")

        @cb
        async def decorated_function(x, y):
            await asyncio.sleep(0)
            return x + y

        result = asyncio.run(decorated_function(2, 3))

        assert result == 5
        stats = cb.get_stats()
        assert stats.total_requests == 1
        assert stats.successful_requests == 1
