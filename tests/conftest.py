"""
Pytest configuration and shared fixtures for QRLP tests.

Provides common test fixtures, configuration, and utilities used across
the entire test suite.
"""

import pytest
import tempfile
import shutil
import os
import json
from pathlib import Path
from typing import Dict, Any

from src import QRLiveProtocol, QRLPConfig
from src.crypto import KeyManager, DataEncryptor, HMACManager, QRSignatureManager


@pytest.fixture(scope="session")
def test_config():
    """Test configuration with minimal settings for fast testing."""
    config = QRLPConfig()

    # Minimal settings for testing
    config.update_interval = 0.1  # Fast updates for testing
    config.qr_settings.error_correction_level = "L"  # Minimal error correction
    config.qr_settings.box_size = 8  # Smaller QR codes for testing
    config.blockchain_settings.cache_duration = 1  # Short cache for testing
    config.time_settings.update_interval = 0.1  # Fast time updates

    # Disable external dependencies for testing
    config.blockchain_settings.enabled_chains = set()  # No blockchain calls
    config.time_settings.time_servers = []  # No NTP calls

    return config


@pytest.fixture(scope="session")
def temp_key_dir():
    """Temporary directory for key storage during tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="qrlp_test_keys_"))
    yield temp_dir
    # Cleanup after tests
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def key_manager(temp_key_dir):
    """Key manager instance for testing."""
    return KeyManager(str(temp_key_dir))


@pytest.fixture
def data_encryptor():
    """Data encryptor instance for testing."""
    return DataEncryptor()


@pytest.fixture
def hmac_manager():
    """HMAC manager instance for testing."""
    return HMACManager()


@pytest.fixture
def qrlp_instance(test_config, temp_key_dir):
    """QRLiveProtocol instance for testing."""
    # Override key directory for testing
    test_config.identity_settings.identity_file = None  # Use auto-generated identity

    qrlp = QRLiveProtocol(test_config)

    # Override key manager to use test directory
    qrlp.key_manager = KeyManager(str(temp_key_dir))

    return qrlp


@pytest.fixture
def sample_qr_data():
    """Sample QR data for testing."""
    return {
        "timestamp": "2025-01-11T15:30:45.123Z",
        "identity_hash": "abc123def456789012345678901234567890",
        "blockchain_hashes": {
            "bitcoin": "00000000000000000008a15c6c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4",
            "ethereum": "0x1234567890abcdef1234567890abcdef12345678"
        },
        "time_server_verification": {
            "time.nist.gov": {
                "timestamp": "2025-01-11T15:30:45.123Z",
                "offset": 0.001
            }
        },
        "user_data": {"test": "data"},
        "sequence_number": 1
    }


@pytest.fixture
def sample_signed_qr_data(sample_qr_data):
    """Sample QR data with digital signature for testing."""
    # This would be created by the signature manager in real usage
    signed_data = sample_qr_data.copy()
    signed_data['digital_signature'] = "abc123signature456789"
    signed_data['signing_key_id'] = "test_key_123"
    signed_data['signature_algorithm'] = "rsa"
    return signed_data


@pytest.fixture
def sample_encrypted_qr_data(sample_qr_data):
    """Sample QR data with encrypted fields for testing."""
    # This would be created by the encryptor in real usage
    encrypted_data = sample_qr_data.copy()
    encrypted_data['user_data'] = "encrypted_user_data_here"
    encrypted_data['_encrypted_fields'] = ['user_data']
    encrypted_data['_encryption_key_id'] = "test_encryption_key"
    return encrypted_data


@pytest.fixture
def mock_time_provider():
    """Mock time provider for testing."""
    class MockTimeProvider:
        def get_current_time(self):
            from datetime import datetime, timezone
            return datetime.now(timezone.utc)

        def get_time_server_verification(self):
            return {"mock_server": {"timestamp": "2025-01-11T15:30:45Z", "offset": 0}}

        def get_statistics(self):
            return {"total_syncs": 1, "successful_syncs": 1}

    return MockTimeProvider()


@pytest.fixture
def mock_blockchain_verifier():
    """Mock blockchain verifier for testing."""
    class MockBlockchainVerifier:
        def get_blockchain_hashes(self):
            return {
                "bitcoin": "00000000000000000008a15c6c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4",
                "ethereum": "0x1234567890abcdef1234567890abcdef12345678"
            }

        def get_statistics(self):
            return {"total_requests": 1, "successful_requests": 1}

    return MockBlockchainVerifier()


@pytest.fixture
def mock_identity_manager():
    """Mock identity manager for testing."""
    class MockIdentityManager:
        def get_identity_hash(self):
            return "mock_identity_hash_123456789"

        def get_statistics(self):
            return {"hash_generations": 1, "file_count": 0}

    return MockIdentityManager()


# Test utilities
class TestUtils:
    """Utility functions for testing."""

    @staticmethod
    def create_test_qr_json(data: Dict[str, Any]) -> str:
        """Create JSON string for testing."""
        return json.dumps(data, separators=(',', ':'))

    @staticmethod
    def assert_qr_data_structure(qr_data: Dict[str, Any]):
        """Assert that QR data has expected structure."""
        required_fields = ['timestamp', 'identity_hash', 'sequence_number']
        for field in required_fields:
            assert field in qr_data, f"Missing required field: {field}"

    @staticmethod
    def assert_verification_result(result: Dict[str, Any]):
        """Assert that verification result has expected structure."""
        expected_keys = [
            'valid_json', 'identity_verified', 'time_verified',
            'blockchain_verified', 'signature_verified', 'hmac_verified'
        ]
        for key in expected_keys:
            assert key in result, f"Missing verification field: {key}"


@pytest.fixture
def test_utils():
    """Test utilities instance."""
    return TestUtils()

