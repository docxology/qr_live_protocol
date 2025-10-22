#!/usr/bin/env python3
"""
Error Recovery and Resilience Demo for QRLP

Demonstrates comprehensive error handling, circuit breakers, retry logic,
and graceful degradation patterns for production QRLP deployments.

This example shows real-world error scenarios and how QRLP handles them:
- Network failures and API timeouts
- Cryptographic operation failures
- File I/O errors
- Configuration issues
- Resource exhaustion
- External service failures
"""

import sys
import time
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src import QRLiveProtocol, QRLPConfig
from src.error_recovery import (
    CircuitBreaker, CircuitBreakerConfig, RetryStrategy,
    ResilientOperation, ResilienceManager,
    resilient_qr_generation, resilient_verification,
    CircuitBreakerOpenError
)
from src.crypto.exceptions import CryptoError


class ErrorRecoveryDemo:
    """
    Comprehensive error recovery demonstration.

    Shows how QRLP handles various failure scenarios with
    circuit breakers, retry logic, and graceful degradation.
    """

    def __init__(self):
        """Initialize error recovery demo."""
        self.qrlp = QRLiveProtocol()
        self.resilience_manager = ResilienceManager()
        self.demo_stats = {
            'scenarios_tested': 0,
            'errors_handled': 0,
            'circuit_breaker_trips': 0,
            'successful_recoveries': 0,
            'degraded_operations': 0
        }

    def demonstrate_network_failures(self):
        """
        Demonstrate handling of network and API failures.

        Shows circuit breaker protection and retry logic
        for external service dependencies.
        """
        print("\n🌐 Network Failure Recovery Demo")
        print("=" * 50)

        # Create circuit breaker for blockchain API
        blockchain_cb = CircuitBreaker(
            "blockchain_api_demo",
            CircuitBreakerConfig(
                failure_threshold=2,  # Fail fast for demo
                recovery_timeout=5.0,  # Quick recovery
                success_threshold=1
            )
        )

        # Create retry strategy for network operations
        network_retry = RetryStrategy(
            max_attempts=3,
            base_delay=0.5,
            max_delay=2.0
        )

        # Create resilient operation
        resilient_op = ResilientOperation(
            "blockchain_demo",
            network_retry,
            blockchain_cb
        )

        def failing_blockchain_call():
            """Simulate failing blockchain API."""
            self.demo_stats['scenarios_tested'] += 1
            raise ConnectionError("Blockchain API unavailable")

        def eventually_succeeding_call():
            """Simulate API that eventually recovers."""
            if self.demo_stats['scenarios_tested'] < 5:
                self.demo_stats['scenarios_tested'] += 1
                raise ConnectionError("Still failing...")
            return {"bitcoin": "success_hash_123"}

        print("🧪 Testing circuit breaker with failing API...")

        # First few calls should fail and open circuit
        for i in range(3):
            try:
                resilient_op.execute(failing_blockchain_call)
                print(f"   Call {i+1}: Unexpected success")
            except CircuitBreakerOpenError:
                print(f"   Call {i+1}: Circuit breaker open (expected)")
                self.demo_stats['circuit_breaker_trips'] += 1
            except Exception as e:
                print(f"   Call {i+1}: {type(e).__name__}: {e}")

        print("
⏳ Waiting for circuit breaker recovery..."        time.sleep(6)  # Wait longer than recovery timeout

        print("🔄 Testing circuit breaker recovery...")

        # Should now be in half-open state and eventually succeed
        try:
            result = resilient_op.execute(eventually_succeeding_call)
            print(f"✅ Recovery successful: {result}")
            self.demo_stats['successful_recoveries'] += 1
        except Exception as e:
            print(f"❌ Recovery failed: {e}")

        print(f"\n📊 Circuit Breaker Stats:")
        print(f"   Total Requests: {blockchain_cb.stats.total_requests}")
        print(f"   Failed Requests: {blockchain_cb.stats.failed_requests}")
        print(f"   State Changes: {blockchain_cb.stats.state_changes}")
        print(f"   Current State: {blockchain_cb.state.value}")

    def demonstrate_cryptographic_failures(self):
        """
        Demonstrate handling of cryptographic operation failures.

        Shows how QRLP gracefully degrades when cryptographic
        operations fail while maintaining basic functionality.
        """
        print("\n🔐 Cryptographic Failure Recovery Demo")
        print("=" * 50)

        # Create crypto circuit breaker
        crypto_cb = CircuitBreaker(
            "crypto_operations_demo",
            CircuitBreakerConfig(
                failure_threshold=2,
                recovery_timeout=3.0
            )
        )

        # Create crypto retry strategy
        crypto_retry = RetryStrategy(
            max_attempts=2,
            base_delay=0.3
        )

        resilient_crypto = ResilientOperation(
            "crypto_demo",
            crypto_retry,
            crypto_cb
        )

        def failing_crypto_operation():
            """Simulate cryptographic operation failure."""
            self.demo_stats['scenarios_tested'] += 1
            raise CryptoError("Key generation failed")

        def basic_qr_generation():
            """Fallback to basic QR generation."""
            return self.qrlp.generate_single_qr({"fallback": "crypto_failed"})

        print("🧪 Testing cryptographic failure handling...")

        # First, show that crypto operations can fail gracefully
        try:
            # This should fail due to crypto error
            resilient_crypto.execute(failing_crypto_operation)
            print("   Unexpected success in crypto operation")
        except CryptoError as e:
            print(f"   Crypto operation failed: {e}")
            self.demo_stats['errors_handled'] += 1

        # Show graceful degradation to basic functionality
        print("
🔄 Falling back to basic QR generation..."        try:
            qr_data, qr_image = basic_qr_generation()
            print(f"✅ Fallback successful: QR #{qr_data.sequence_number}")
            self.demo_stats['degraded_operations'] += 1
        except Exception as e:
            print(f"❌ Even fallback failed: {e}")

    def demonstrate_resource_exhaustion(self):
        """
        Demonstrate handling of resource exhaustion scenarios.

        Shows how QRLP handles memory issues, file system problems,
        and resource constraints.
        """
        print("\n💾 Resource Exhaustion Recovery Demo")
        print("=" * 50)

        # Create resource-intensive operation
        def memory_intensive_operation():
            """Simulate memory-intensive operation."""
            self.demo_stats['scenarios_tested'] += 1

            # Simulate memory allocation
            large_data = "x" * (100 * 1024 * 1024)  # 100MB

            # This would normally succeed but we'll simulate failure
            if self.demo_stats['scenarios_tested'] > 2:
                raise MemoryError("Out of memory")

            return {"status": "memory_operation_complete", "size": len(large_data)}

        # Create resilient operation for resource management
        resource_retry = RetryStrategy(max_attempts=1)  # Don't retry memory issues
        resilient_resource = ResilientOperation("resource_demo", resource_retry)

        print("🧪 Testing resource exhaustion handling...")

        # Test normal operation
        try:
            result = resilient_resource.execute(memory_intensive_operation)
            print(f"   Memory operation succeeded: {result['size']} bytes")
        except MemoryError as e:
            print(f"   Memory operation failed: {e}")
            self.demo_stats['errors_handled'] += 1

        # Show resource monitoring and cleanup
        print("
📊 Resource monitoring:"        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            print(f"   Current memory usage: {memory_mb:.1f}MB")

            if memory_mb > 100:  # High memory usage threshold
                print("   ⚠️  High memory usage detected - consider cleanup")
            else:
                print("   ✅ Memory usage normal")

        except ImportError:
            print("   📊 Memory monitoring not available")

    def demonstrate_configuration_errors(self):
        """
        Demonstrate handling of configuration and validation errors.

        Shows how QRLP validates configuration and provides
        helpful error messages for misconfigurations.
        """
        print("\n⚙️  Configuration Error Recovery Demo")
        print("=" * 50)

        def test_invalid_config():
            """Test with invalid configuration."""
            self.demo_stats['scenarios_tested'] += 1

            # Create config with invalid settings
            invalid_config = QRLPConfig()
            invalid_config.update_interval = -1  # Invalid negative interval
            invalid_config.qr_settings.error_correction_level = "X"  # Invalid level

            # Try to create QRLP instance
            try:
                QRLiveProtocol(invalid_config)
                return False  # Should have failed
            except Exception as e:
                return str(e)

        def test_missing_dependencies():
            """Test handling of missing dependencies."""
            self.demo_stats['scenarios_tested'] += 1

            # Try to import non-existent module
            try:
                import nonexistent_module
                return False
            except ImportError as e:
                return str(e)

        print("🧪 Testing configuration validation...")

        # Test invalid configuration
        config_error = test_invalid_config()
        if config_error and "update_interval" in config_error:
            print("   ✅ Configuration validation working")
            print(f"   Error message: {config_error}")
            self.demo_stats['errors_handled'] += 1
        else:
            print("   ❌ Configuration validation not working properly")

        # Test missing dependencies
        import_error = test_missing_dependencies()
        if import_error and "nonexistent_module" in import_error:
            print("   ✅ Import error handling working")
            print(f"   Error message: {import_error}")
            self.demo_stats['errors_handled'] += 1
        else:
            print("   ❌ Import error handling not working properly")

    def demonstrate_qr_generation_resilience(self):
        """
        Demonstrate QR generation resilience under various conditions.

        Shows how QRLP handles different types of failures during
        QR generation while maintaining service availability.
        """
        print("\n📱 QR Generation Resilience Demo")
        print("=" * 50)

        # Test scenarios that might cause QR generation to fail
        scenarios = [
            ("Large data payload", {"data": "x" * 10000}),
            ("Special characters", {"text": "🔥✨🎯💯"}),
            ("Empty data", {}),
            ("Nested structures", {"level1": {"level2": {"level3": "deep"}}}),
            ("Unicode content", {"unicode": "测试内容🚀"})
        ]

        print("🧪 Testing QR generation under various conditions...")

        for scenario_name, test_data in scenarios:
            print(f"\n📝 Scenario: {scenario_name}")

            try:
                # Attempt QR generation
                qr_data, qr_image = self.qrlp.generate_single_qr(test_data)

                # Verify result
                qr_json = qr_data.to_json()
                verification = self.qrlp.verify_qr_data(qr_json)

                if verification['hmac_verified']:
                    print(f"   ✅ QR generation successful: {len(qr_image)} bytes")
                    print(f"   📊 Sequence: #{qr_data.sequence_number}")
                    self.demo_stats['successful_recoveries'] += 1
                else:
                    print("   ⚠️  QR generated but verification failed")

            except Exception as e:
                print(f"   ❌ QR generation failed: {type(e).__name__}: {e}")
                self.demo_stats['errors_handled'] += 1

    def demonstrate_error_recovery_patterns(self):
        """
        Demonstrate comprehensive error recovery patterns.

        Shows real-world error scenarios and how QRLP handles them
        with circuit breakers, retry logic, and graceful degradation.
        """
        print("\n🛡️  Comprehensive Error Recovery Demo")
        print("=" * 60)

        # Demonstrate circuit breaker pattern
        self.demonstrate_network_failures()

        # Demonstrate cryptographic failure handling
        self.demonstrate_cryptographic_failures()

        # Demonstrate resource exhaustion handling
        self.demonstrate_resource_exhaustion()

        # Demonstrate configuration error handling
        self.demonstrate_configuration_errors()

        # Demonstrate QR generation resilience
        self.demonstrate_qr_generation_resilience()

        # Show resilience manager health
        print("
🏥 Resilience Manager Health:"        health_status = self.resilience_manager.get_health_status()
        print(f"   Overall Health: {health_status['health']}")
        print(f"   Message: {health_status['message']}")
        print(f"   Open Circuits: {health_status['open_circuits']}")
        print(f"   Active Operations: {health_status['active_operations']}")

    def demonstrate_graceful_degradation(self):
        """
        Demonstrate graceful degradation patterns.

        Shows how QRLP maintains partial functionality when
        some components fail, ensuring service availability.
        """
        print("\n🔄 Graceful Degradation Demo")
        print("=" * 40)

        print("🎯 Testing graceful degradation scenarios...")

        # Test with disabled blockchain verification
        print("\n1️⃣  Testing with blockchain disabled...")

        config_no_blockchain = QRLPConfig()
        config_no_blockchain.blockchain_settings.enabled_chains = set()

        qrlp_no_blockchain = QRLiveProtocol(config_no_blockchain)

        qr_data, qr_image = qrlp_no_blockchain.generate_single_qr({"test": "no_blockchain"})
        verification = qrlp_no_blockchain.verify_qr_data(qr_data.to_json())

        print(f"   ✅ QR generated without blockchain: {verification['valid_json']}")
        print(f"   📊 HMAC verified: {verification['hmac_verified']}")
        print(f"   🔗 Blockchain verified: {verification['blockchain_verified']}")

        # Test with disabled time servers
        print("\n2️⃣  Testing with time servers disabled...")

        config_no_time = QRLPConfig()
        config_no_time.time_settings.time_servers = []

        qrlp_no_time = QRLiveProtocol(config_no_time)

        qr_data, qr_image = qrlp_no_time.generate_single_qr({"test": "no_time"})
        verification = qrlp_no_time.verify_qr_data(qr_data.to_json())

        print(f"   ✅ QR generated without time servers: {verification['valid_json']}")
        print(f"   ⏰ Time verified: {verification['time_verified']}")
        print(f"   📊 HMAC verified: {verification['hmac_verified']}")

        # Test with minimal cryptographic features
        print("\n3️⃣  Testing with minimal cryptography...")

        qr_data, qr_image = qrlp_no_time.generate_single_qr(
            {"test": "minimal_crypto"},
            sign_data=False,  # No signing
            encrypt_data=False  # No encryption
        )

        verification = qrlp_no_time.verify_qr_data(qr_data.to_json())

        print(f"   ✅ Minimal crypto QR: {verification['valid_json']}")
        print(f"   🔐 Signature verified: {verification['signature_verified']}")
        print(f"   🔒 Encrypted: {verification['encrypted']}")
        print(f"   📊 HMAC verified: {verification['hmac_verified']}")

        self.demo_stats['degraded_operations'] += 3

    def demonstrate_retry_patterns(self):
        """
        Demonstrate retry logic with exponential backoff.

        Shows how QRLP implements intelligent retry strategies
        for different types of operations.
        """
        print("\n🔄 Retry Logic Demo")
        print("=" * 30)

        # Create different retry strategies
        strategies = {
            "network": RetryStrategy(max_attempts=3, base_delay=0.5, max_delay=4.0),
            "crypto": RetryStrategy(max_attempts=2, base_delay=0.3, max_delay=1.0),
            "file_io": RetryStrategy(max_attempts=3, base_delay=0.1, max_delay=0.5)
        }

        def simulate_operation_with_retry(strategy_name: str, operation_func):
            """Simulate operation with retry strategy."""
            strategy = strategies[strategy_name]
            attempt = 0

            while attempt < strategy.max_attempts:
                attempt += 1

                try:
                    return operation_func()
                except Exception as e:
                    if not strategy.should_retry(attempt, e):
                        raise

                    delay = strategy.calculate_delay(attempt)
                    print(f"   Retry {attempt}/{strategy.max_attempts} in {delay:.1f}s: {e}")
                    time.sleep(delay)

            raise RuntimeError("All retry attempts exhausted")

        # Test network-like operation
        print("🧪 Testing network retry strategy...")

        def network_operation():
            if time.time() % 2 < 1:  # Fail half the time
                raise ConnectionError("Network unavailable")
            return {"status": "network_success"}

        try:
            result = simulate_operation_with_retry("network", network_operation)
            print(f"✅ Network operation succeeded: {result}")
        except Exception as e:
            print(f"❌ Network operation failed: {e}")

        # Test crypto-like operation
        print("\n🧪 Testing crypto retry strategy...")

        def crypto_operation():
            if time.time() % 3 < 1:  # Fail occasionally
                raise CryptoError("Cryptographic operation failed")
            return {"status": "crypto_success"}

        try:
            result = simulate_operation_with_retry("crypto", crypto_operation)
            print(f"✅ Crypto operation succeeded: {result}")
        except Exception as e:
            print(f"❌ Crypto operation failed: {e}")

    def run_comprehensive_error_demo(self):
        """Run the complete error recovery demonstration."""
        print("🛡️  QRLP Error Recovery & Resilience Comprehensive Demo")
        print("=" * 80)
        print("This demo shows how QRLP handles failures gracefully:")
        print("• Network failures with circuit breaker protection")
        print("• Cryptographic operation failures with graceful degradation")
        print("• Resource exhaustion with monitoring and recovery")
        print("• Configuration errors with validation and guidance")
        print("• QR generation failures with fallback mechanisms")
        print("• Retry logic with exponential backoff")
        print("=" * 80)

        try:
            # Run all error recovery demonstrations
            self.demonstrate_error_recovery_patterns()
            self.demonstrate_graceful_degradation()
            self.demonstrate_retry_patterns()

            # Print comprehensive summary
            self.print_error_demo_summary()

        except KeyboardInterrupt:
            print("\n🛑 Error recovery demo interrupted by user")
        except Exception as e:
            print(f"\n❌ Error recovery demo failed: {e}")
            import traceback
            traceback.print_exc()

    def print_error_demo_summary(self):
        """Print comprehensive error recovery demo summary."""
        print("\n" + "=" * 80)
        print("📊 QRLP Error Recovery Demo Summary")
        print("=" * 80)

        print("🎯 Error Scenarios Tested:")
        print(f"   Total Scenarios: {self.demo_stats['scenarios_tested']}")
        print(f"   Errors Handled: {self.demo_stats['errors_handled']}")
        print(f"   Circuit Breaker Trips: {self.demo_stats['circuit_breaker_trips']}")
        print(f"   Successful Recoveries: {self.demo_stats['successful_recoveries']}")
        print(f"   Degraded Operations: {self.demo_stats['degraded_operations']}")

        # Calculate resilience metrics
        if self.demo_stats['errors_handled'] > 0:
            recovery_rate = (self.demo_stats['successful_recoveries'] /
                           self.demo_stats['errors_handled']) * 100
            print(f"   Recovery Rate: {recovery_rate:.1f}%")

        # Show resilience manager status
        health = self.resilience_manager.get_health_status()
        print("
🏥 System Resilience Status:"        print(f"   Overall Health: {health['health']}")
        print(f"   Active Operations: {health['active_operations']}")

        if health['open_circuits']:
            print(f"   ⚠️  Open Circuits: {', '.join(health['open_circuits'])}")

        print("
✨ Resilience Features Demonstrated:"        features = [
            "✅ Circuit breaker pattern for cascading failure prevention",
            "✅ Retry logic with exponential backoff",
            "✅ Graceful degradation to reduced functionality",
            "✅ Resource exhaustion monitoring and recovery",
            "✅ Configuration validation with helpful error messages",
            "✅ Cryptographic operation failure handling",
            "✅ Network failure protection and recovery",
            "✅ QR generation resilience under various conditions"
        ]

        for feature in features:
            print(f"   {feature}")

        print("
🎉 Error recovery demo completed successfully!"        print("=" * 80)


def demonstrate_resilient_qr_operations():
    """Demonstrate resilient QR operations using the error recovery system."""
    print("\n🚀 Resilient QR Operations Demo")
    print("=" * 40)

    qrlp = QRLiveProtocol()

    # Generate QR with resilience
    print("📱 Generating QR with resilience protection...")

    try:
        qr_data, qr_image = resilient_qr_generation(
            qrlp,
            user_data={"resilient_test": True},
            sign_data=True
        )

        print(f"✅ QR generated successfully: #{qr_data.sequence_number}")

        # Verify with resilience
        qr_json = qr_data.to_json()
        verification = resilient_verification(qrlp, qr_json)

        print(f"✅ Verification successful: {verification['hmac_verified']}")

        if verification['signature_verified']:
            print("✅ Digital signature verified")

    except Exception as e:
        print(f"❌ Resilient operation failed: {e}")


def main():
    """Run the complete error recovery demonstration."""
    demo = ErrorRecoveryDemo()
    demo.run_comprehensive_error_demo()

    # Additional demonstration of resilient operations
    demonstrate_resilient_qr_operations()


if __name__ == "__main__":
    main()

