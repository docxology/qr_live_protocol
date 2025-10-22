"""
Unit tests for Circuit Breaker error recovery functionality.

Tests circuit breaker state management, failure detection, and recovery patterns.
"""

import pytest
import time
from unittest.mock import patch

from src.error_recovery import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState,
    CircuitBreakerStats, CircuitBreakerOpenError
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
        result = cb(successful_operation)
        assert result == "success"
        assert cb.stats.successful_requests == 1

    def test_circuit_breaker_failure_detection(self):
        """Test circuit breaker detects failures and opens circuit."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=1.0)
        cb = CircuitBreaker("failure_test", config)

        def failing_operation():
            raise ConnectionError("Service unavailable")

        # First failure - should still be closed
        with pytest.raises(ConnectionError):
            cb(failing_operation)

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb._consecutive_failures == 1
        assert cb.stats.failed_requests == 1

        # Second failure - should open circuit
        with pytest.raises(ConnectionError):
            cb(failing_operation)

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
            cb(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Should now block execution
        with pytest.raises(CircuitBreakerOpenError):
            cb(lambda: "should_not_execute")

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
            cb(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Should transition to half-open and succeed
        result = cb(successful_operation)
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
            cb(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Should be in half-open state, fail again
        with pytest.raises(ConnectionError):
            cb(failing_operation)

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
            cb(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Should be in half-open state
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # First success - still half-open
        result = cb(successful_operation)
        assert result == "success"
        assert cb.state == CircuitBreakerState.HALF_OPEN
        assert cb._consecutive_successes == 1

        # Second success - still half-open
        result = cb(successful_operation)
        assert result == "success"
        assert cb.state == CircuitBreakerState.HALF_OPEN
        assert cb._consecutive_successes == 2

        # Third success - should close circuit
        result = cb(successful_operation)
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
        result = cb(successful_operation)
        stats = cb.get_stats()
        assert stats.total_requests == 1
        assert stats.successful_requests == 1
        assert stats.failed_requests == 0

        # Failed operation
        with pytest.raises(ConnectionError):
            cb(failing_operation)

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
            cb(failing_operation)

        assert cb.state == CircuitBreakerState.OPEN

        # Reset circuit breaker
        cb.reset()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb._consecutive_failures == 0
        assert cb._consecutive_successes == 0

        # Should now allow execution
        result = cb(lambda: "after_reset")
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
        with pytest.raises(Exception):  # Timeout or circuit breaker error
            cb(timeout_operation)

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
        cb = CircuitBreaker("exception_test")

        def operation_that_raises_value_error():
            raise ValueError("Value error")

        def operation_that_raises_runtime_error():
            raise RuntimeError("Runtime error")

        # Both types of exceptions should be handled the same way
        with pytest.raises(ValueError):
            cb(operation_that_raises_value_error)

        assert cb._consecutive_failures == 1

        with pytest.raises(RuntimeError):
            cb(operation_that_raises_runtime_error)

        assert cb._consecutive_failures == 2
        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_concurrent_access(self):
        """Test circuit breaker thread safety."""
        import threading
        import queue

        cb = CircuitBreaker("concurrent_test")

        results = queue.Queue()

        def concurrent_operation():
            try:
                # Mix of successful and failing operations
                if threading.current_thread().name.endswith('0'):  # Every 10th thread fails
                    raise ConnectionError("Concurrent failure")
                else:
                    return "concurrent_success"
            except Exception as e:
                results.put(f"error: {e}")
                raise

        # Run multiple concurrent operations
        threads = []
        for i in range(10):
            thread = threading.Thread(target=lambda: results.put(cb(concurrent_operation)()))
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Check results
        success_count = 0
        while not results.empty():
            result = results.get()
            if result == "concurrent_success":
                success_count += 1
            elif result.startswith("error:"):
                # Expected some failures
                pass

        # Should have mostly successes (9 out of 10)
        assert success_count >= 8

        # Circuit breaker should have handled the failure
        stats = cb.get_stats()
        assert stats.total_requests == 10
        assert stats.successful_requests >= 8

