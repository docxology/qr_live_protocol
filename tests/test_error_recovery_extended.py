"""
Extended tests for error_recovery.py circuit breaker, retry, and resilience.

Covers all state transitions, async paths, decorators, and managers.
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, patch

from src.error_recovery import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState,
    CircuitBreakerStats, RetryStrategy, ResilientOperation,
    CircuitBreakerManager, ResilienceManager, CircuitBreakerOpenError,
    resilience_manager, resilient_qr_generation, resilient_verification,
)


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig validation."""

    def test_defaults(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 3
        assert config.timeout == 30.0

    def test_failure_threshold_too_low(self):
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreakerConfig(failure_threshold=0)

    def test_recovery_timeout_negative(self):
        with pytest.raises(ValueError, match="recovery_timeout"):
            CircuitBreakerConfig(recovery_timeout=-1)

    def test_success_threshold_too_low(self):
        with pytest.raises(ValueError, match="success_threshold"):
            CircuitBreakerConfig(success_threshold=0)


class TestCircuitBreakerClosed:
    """Test CLOSED state behavior."""

    def test_execute_success(self):
        cb = CircuitBreaker("test")
        result = cb.execute(lambda: 42)
        assert result == 42
        assert cb.state == CircuitBreakerState.CLOSED

    def test_execute_failure_increments(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitBreakerState.CLOSED

    def test_execute_failure_opens_circuit(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitBreakerState.OPEN


class TestCircuitBreakerOpen:
    """Test OPEN state behavior."""

    def test_open_rejects_request(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1, recovery_timeout=10))
        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitBreakerState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            cb.execute(lambda: 42)

    def test_open_transitions_to_half_open(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1))
        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitBreakerState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitBreakerState.HALF_OPEN


class TestCircuitBreakerHalfOpen:
    """Test HALF_OPEN state behavior."""

    def test_half_open_success_closes(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1, recovery_timeout=0.1, success_threshold=1))
        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        time.sleep(0.15)
        assert cb.state == CircuitBreakerState.HALF_OPEN
        result = cb.execute(lambda: 42)
        assert result == 42
        assert cb.state == CircuitBreakerState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1, recovery_timeout=0.1, success_threshold=2))
        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        time.sleep(0.15)
        assert cb.state == CircuitBreakerState.HALF_OPEN
        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitBreakerState.OPEN

    def test_half_open_in_flight_rejects(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1, recovery_timeout=0.1, success_threshold=2))
        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        time.sleep(0.15)
        assert cb.state == CircuitBreakerState.HALF_OPEN
        # Manually set in-flight
        cb._half_open_in_flight = True
        with pytest.raises(CircuitBreakerOpenError, match="already testing"):
            cb.execute(lambda: 42)


class TestCircuitBreakerTimeout:
    """Test timeout behavior."""

    def test_execute_with_timeout_exceeds(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(timeout=0.05))
        with pytest.raises(TimeoutError):
            cb.execute(lambda: time.sleep(1))

    def test_execute_no_timeout(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(timeout=0))
        result = cb.execute(lambda: 42)
        assert result == 42


class TestCircuitBreakerAsync:
    """Test async circuit breaker."""

    async def test_execute_async_success(self):
        cb = CircuitBreaker("test")
        async def func():
            return 42
        result = await cb.execute_async(func)
        assert result == 42

    async def test_execute_async_failure(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
        async def fail():
            raise ValueError("async fail")
        with pytest.raises(ValueError):
            await cb.execute_async(fail)
        assert cb.state == CircuitBreakerState.OPEN

    async def test_execute_async_timeout(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(timeout=0.05))
        async def slow():
            await asyncio.sleep(1)
        with pytest.raises(TimeoutError):
            await cb.execute_async(slow)


class TestCircuitBreakerDecorator:
    """Test circuit breaker as decorator."""

    def test_decorator_sync(self):
        cb = CircuitBreaker("test")
        @cb
        def func(x):
            return x * 2
        assert func(21) == 42

    async def test_decorator_async(self):
        cb = CircuitBreaker("test")
        @cb
        async def func(x):
            return x * 2
        result = await func(21)
        assert result == 42


class TestCircuitBreakerStats:
    """Test statistics and reset."""

    def test_get_stats(self):
        cb = CircuitBreaker("test")
        cb.execute(lambda: 42)
        stats = cb.get_stats()
        assert stats.total_requests == 1
        assert stats.successful_requests == 1

    def test_reset(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitBreakerState.OPEN
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.stats.total_requests == 0


class TestRetryStrategy:
    """Test RetryStrategy."""

    def test_calculate_delay_exponential(self):
        rs = RetryStrategy(base_delay=1.0, backoff_factor=2.0, max_delay=60.0)
        assert rs.calculate_delay(1) == 1.0
        assert rs.calculate_delay(2) == 2.0
        assert rs.calculate_delay(3) == 4.0

    def test_calculate_delay_capped(self):
        rs = RetryStrategy(base_delay=1.0, backoff_factor=10.0, max_delay=5.0)
        assert rs.calculate_delay(3) == 5.0

    def test_should_retry_true(self):
        rs = RetryStrategy(max_attempts=3)
        assert rs.should_retry(1, ValueError("fail")) is True

    def test_should_retry_max_attempts(self):
        rs = RetryStrategy(max_attempts=3)
        assert rs.should_retry(3, ValueError("fail")) is False

    def test_should_retry_keyboard_interrupt(self):
        rs = RetryStrategy()
        assert rs.should_retry(1, KeyboardInterrupt()) is False

    def test_should_retry_system_exit(self):
        rs = RetryStrategy()
        assert rs.should_retry(1, SystemExit()) is False


class TestResilientOperation:
    """Test ResilientOperation."""

    def test_execute_success(self):
        op = ResilientOperation("test")
        result = op.execute(lambda: 42)
        assert result == 42

    def test_execute_retry_then_success(self):
        calls = [0]
        def func():
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("fail")
            return 42
        op = ResilientOperation("test", RetryStrategy(max_attempts=3, base_delay=0.01))
        result = op.execute(func)
        assert result == 42
        assert calls[0] == 2

    def test_execute_all_retries_fail(self):
        def func():
            raise ValueError("always fail")
        op = ResilientOperation("test", RetryStrategy(max_attempts=2, base_delay=0.01))
        with pytest.raises(ValueError):
            op.execute(func)

    def test_execute_circuit_breaker_open_not_retried(self):
        """CircuitBreakerOpenError is not retried."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1, recovery_timeout=999))
        # Manually open the circuit with a recent failure time
        cb.state = CircuitBreakerState.OPEN
        import time as _time
        cb._last_failure_time = _time.monotonic()  # Just now, so recovery not due
        op = ResilientOperation("test", RetryStrategy(max_attempts=3), cb)
        with pytest.raises(CircuitBreakerOpenError):
            op.execute(lambda: 42)

    async def test_execute_async_success(self):
        op = ResilientOperation("test")
        async def func():
            return 42
        result = await op.execute_async(func)
        assert result == 42


class TestCircuitBreakerManager:
    """Test CircuitBreakerManager."""

    def test_get_or_create(self):
        mgr = CircuitBreakerManager()
        cb1 = mgr.get_circuit_breaker("test")
        cb2 = mgr.get_circuit_breaker("test")
        assert cb1 is cb2

    def test_get_all_stats(self):
        mgr = CircuitBreakerManager()
        mgr.get_circuit_breaker("a")
        mgr.get_circuit_breaker("b")
        stats = mgr.get_all_stats()
        assert "a" in stats
        assert "b" in stats

    def test_reset_all(self):
        mgr = CircuitBreakerManager()
        cb = mgr.get_circuit_breaker("test", CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitBreakerState.OPEN
        mgr.reset_all()
        assert cb.state == CircuitBreakerState.CLOSED


class TestResilienceManager:
    """Test ResilienceManager."""

    def test_default_circuit_breakers(self):
        mgr = ResilienceManager()
        assert "blockchain_api" in mgr.circuit_breaker_manager.circuit_breakers
        assert "time_servers" in mgr.circuit_breaker_manager.circuit_breakers
        assert "qr_generation" in mgr.circuit_breaker_manager.circuit_breakers

    def test_default_retry_strategies(self):
        mgr = ResilienceManager()
        assert "network" in mgr.retry_strategies
        assert "crypto" in mgr.retry_strategies
        assert "file_io" in mgr.retry_strategies

    def test_create_resilient_operation(self):
        mgr = ResilienceManager()
        op = mgr.create_resilient_operation("test_op", "network", "blockchain_api")
        assert op.name == "test_op"

    def test_get_resilient_operation(self):
        mgr = ResilienceManager()
        mgr.create_resilient_operation("test_op")
        assert mgr.get_resilient_operation("test_op") is not None
        assert mgr.get_resilient_operation("nonexistent") is None

    def test_get_health_status_healthy(self):
        mgr = ResilienceManager()
        status = mgr.get_health_status()
        assert status["health"] == "healthy"

    def test_get_health_status_critical(self):
        mgr = ResilienceManager()
        # Open the blockchain_api circuit breaker
        cb = mgr.circuit_breaker_manager.circuit_breakers["blockchain_api"]
        cb_config = cb.config
        # Force open by triggering failures
        for _ in range(cb_config.failure_threshold):
            with pytest.raises(ValueError):
                cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        status = mgr.get_health_status()
        assert status["health"] == "critical"
        assert "blockchain_api" in status["open_circuits"]


class TestResilientFunctions:
    """Test module-level resilient functions."""

    def test_resilient_qr_generation(self):
        mock_qrlp = MagicMock()
        mock_qrlp.generate_single_qr.return_value = ("qr_data", b"qr_image")
        result = resilient_qr_generation(mock_qrlp, {"key": "val"}, True, False)
        assert result == ("qr_data", b"qr_image")
        mock_qrlp.generate_single_qr.assert_called_once()

    def test_resilient_verification(self):
        mock_qrlp = MagicMock()
        mock_qrlp.verify_qr_data.return_value = {"valid": True}
        result = resilient_verification(mock_qrlp, '{"test": true}')
        assert result == {"valid": True}
