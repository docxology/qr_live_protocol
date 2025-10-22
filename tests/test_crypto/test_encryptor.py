"""
Unit tests for Data Encryptor cryptographic functionality.

Tests AES-256 encryption and decryption operations for sensitive data protection.
"""

import pytest
import json
import base64

from src.crypto import DataEncryptor, EncryptionKey
from src.crypto.exceptions import EncryptionError


class TestDataEncryptor:
    """Test suite for DataEncryptor class."""

    def test_encryptor_initialization(self):
        """Test encryptor initializes correctly."""
        encryptor = DataEncryptor()

        assert encryptor.master_key is not None
        assert len(encryptor.master_key) == 32  # AES-256 key
        assert encryptor.key_id is not None

    def test_encrypt_decrypt_string(self):
        """Test encryption and decryption of string data."""
        encryptor = DataEncryptor()

        original_data = "This is a test message for encryption"

        # Encrypt data
        encrypted = encryptor.encrypt_sensitive_data(original_data)

        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 0
        assert encrypted != original_data.encode('utf-8')  # Should be encrypted

        # Decrypt data
        decrypted = encryptor.decrypt_sensitive_data(encrypted)

        assert decrypted == original_data

    def test_encrypt_decrypt_dict(self):
        """Test encryption and decryption of dictionary data."""
        encryptor = DataEncryptor()

        original_data = {
            "user_id": "user123",
            "api_key": "sk_live_abcdef123456789",
            "permissions": ["read", "write"]
        }

        # Encrypt data
        encrypted = encryptor.encrypt_sensitive_data(original_data)
        assert isinstance(encrypted, bytes)

        # Decrypt data
        decrypted = encryptor.decrypt_sensitive_data(encrypted)

        assert decrypted == original_data

    def test_encrypt_decrypt_bytes(self):
        """Test encryption and decryption of binary data."""
        encryptor = DataEncryptor()

        original_data = b"Binary data for encryption test"

        # Encrypt data
        encrypted = encryptor.encrypt_sensitive_data(original_data)
        assert isinstance(encrypted, bytes)

        # Decrypt data
        decrypted = encryptor.decrypt_sensitive_data(encrypted)

        assert decrypted == original_data.decode('utf-8')

    def test_encrypt_with_additional_data(self):
        """Test encryption with additional authenticated data."""
        encryptor = DataEncryptor()

        original_data = "Secret message"
        additional_data = "context_info_123"

        # Encrypt with additional data
        encrypted = encryptor.encrypt_sensitive_data(original_data, additional_data)

        # Decrypt with additional data
        decrypted = encryptor.decrypt_sensitive_data(encrypted, additional_data)

        assert decrypted == original_data

    def test_decrypt_without_additional_data_fails(self):
        """Test that decryption fails without matching additional data."""
        encryptor = DataEncryptor()

        original_data = "Secret message"
        additional_data = "context_info_123"

        # Encrypt with additional data
        encrypted = encryptor.encrypt_sensitive_data(original_data, additional_data)

        # Try to decrypt without additional data
        with pytest.raises(EncryptionError):
            encryptor.decrypt_sensitive_data(encrypted)

    def test_encrypt_qr_payload(self):
        """Test encryption of QR data payload."""
        encryptor = DataEncryptor()

        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_hash_123",
            "user_data": {"sensitive": "secret_info"},
            "public_data": "public_info"
        }

        # Encrypt sensitive fields
        encrypted_qr = encryptor.encrypt_qr_payload(qr_data)

        # Should have encryption metadata
        assert '_encrypted_fields' in encrypted_qr
        assert '_encryption_key_id' in encrypted_qr
        assert '_encrypted_at' in encrypted_qr

        # Sensitive data should be encrypted
        assert encrypted_qr['user_data'] != qr_data['user_data']['sensitive']

        # Public data should remain unchanged
        assert encrypted_qr['public_data'] == qr_data['public_data']

    def test_decrypt_qr_payload(self):
        """Test decryption of QR data payload."""
        encryptor = DataEncryptor()

        original_qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_hash_123",
            "user_data": {"sensitive": "secret_info"},
            "public_data": "public_info"
        }

        # Encrypt QR data
        encrypted_qr = encryptor.encrypt_qr_payload(original_qr_data)

        # Decrypt QR data
        decrypted_qr = encryptor.decrypt_qr_payload(encrypted_qr)

        # Should match original data
        assert decrypted_qr['timestamp'] == original_qr_data['timestamp']
        assert decrypted_qr['identity_hash'] == original_qr_data['identity_hash']
        assert decrypted_qr['user_data'] == original_qr_data['user_data']
        assert decrypted_qr['public_data'] == original_qr_data['public_data']

        # Should not have encryption metadata
        assert '_encrypted_fields' not in decrypted_qr
        assert '_encryption_key_id' not in decrypted_qr

    def test_generate_data_key(self):
        """Test data key generation."""
        encryptor = DataEncryptor()

        key = encryptor.generate_data_key("test_purpose")

        assert isinstance(key, EncryptionKey)
        assert key.key_id is not None
        assert key.key_data is not None
        assert len(key.key_data) == 32  # AES-256
        assert key.algorithm == "aes-256-gcm"
        assert key.purpose == "test_purpose"
        assert key.created_at is not None

    def test_create_encrypted_qr_data(self):
        """Test creating QR data with encryption using specific key."""
        encryptor = DataEncryptor()

        # Generate encryption key
        key = encryptor.generate_data_key("qr_encryption")

        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_hash_123",
            "user_data": {"encrypted": "secret_data"},
            "public_data": "public_info"
        }

        # Create encrypted QR data
        encrypted_qr = encryptor.create_encrypted_qr_data(qr_data, key.key_id)

        # Should have encryption metadata
        assert '_encrypted_fields' in encrypted_qr
        assert '_data_key_id' in encrypted_qr
        assert encrypted_qr['_data_key_id'] == key.key_id

        # Sensitive data should be encrypted
        assert encrypted_qr['user_data'] != qr_data['user_data']['encrypted']

    def test_decrypt_encrypted_qr_data(self):
        """Test decrypting QR data with specific encryption key."""
        encryptor = DataEncryptor()

        # Generate encryption key
        key = encryptor.generate_data_key("qr_encryption")

        original_qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_hash_123",
            "user_data": {"encrypted": "secret_data"},
            "public_data": "public_info"
        }

        # Create encrypted QR data
        encrypted_qr = encryptor.create_encrypted_qr_data(original_qr_data, key.key_id)

        # Decrypt QR data
        decrypted_qr = encryptor.decrypt_encrypted_qr_data(encrypted_qr)

        # Should match original data
        assert decrypted_qr['timestamp'] == original_qr_data['timestamp']
        assert decrypted_qr['identity_hash'] == original_qr_data['identity_hash']
        assert decrypted_qr['user_data'] == original_qr_data['user_data']
        assert decrypted_qr['public_data'] == original_qr_data['public_data']

    def test_encryption_determinism(self):
        """Test that encryption produces consistent results with same key."""
        encryptor = DataEncryptor()

        data = "Deterministic encryption test"

        # Encrypt same data multiple times
        encrypted1 = encryptor.encrypt_sensitive_data(data)
        encrypted2 = encryptor.encrypt_sensitive_data(data)

        # Results should be different (due to random IV)
        assert encrypted1 != encrypted2

        # But both should decrypt to same data
        decrypted1 = encryptor.decrypt_sensitive_data(encrypted1)
        decrypted2 = encryptor.decrypt_sensitive_data(encrypted2)

        assert decrypted1 == data
        assert decrypted2 == data
        assert decrypted1 == decrypted2

    def test_encryption_with_different_keys(self):
        """Test encryption with different keys produces different results."""
        encryptor1 = DataEncryptor()
        encryptor2 = DataEncryptor()

        data = "Different keys test"

        # Encrypt with different keys
        encrypted1 = encryptor1.encrypt_sensitive_data(data)
        encrypted2 = encryptor2.encrypt_sensitive_data(data)

        # Results should be different
        assert encrypted1 != encrypted2

        # Should decrypt correctly with respective keys
        decrypted1 = encryptor1.decrypt_sensitive_data(encrypted1)
        decrypted2 = encryptor2.decrypt_sensitive_data(encrypted2)

        assert decrypted1 == data
        assert decrypted2 == data

    def test_invalid_encrypted_data_raises_error(self):
        """Test that invalid encrypted data raises appropriate error."""
        encryptor = DataEncryptor()

        # Invalid base64 data
        invalid_data = b"invalid_base64_data"

        with pytest.raises(EncryptionError):
            encryptor.decrypt_sensitive_data(invalid_data)

    def test_empty_data_encryption(self):
        """Test encryption of empty data."""
        encryptor = DataEncryptor()

        # Test empty string
        empty_str = ""
        encrypted = encryptor.encrypt_sensitive_data(empty_str)
        decrypted = encryptor.decrypt_sensitive_data(encrypted)
        assert decrypted == empty_str

        # Test empty dict
        empty_dict = {}
        encrypted = encryptor.encrypt_sensitive_data(empty_dict)
        decrypted = encryptor.decrypt_sensitive_data(encrypted)
        assert decrypted == empty_dict

    def test_large_data_encryption(self):
        """Test encryption of large data."""
        encryptor = DataEncryptor()

        # Create large data
        large_data = "x" * (1024 * 1024)  # 1MB of data

        # Should handle large data without issues
        encrypted = encryptor.encrypt_sensitive_data(large_data)
        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 0

        decrypted = encryptor.decrypt_sensitive_data(encrypted)
        assert decrypted == large_data

    def test_encryption_key_metadata(self):
        """Test encryption key metadata handling."""
        encryptor = DataEncryptor()

        # Generate key
        key = encryptor.generate_data_key("metadata_test")

        # Check key properties
        assert key.key_id is not None
        assert key.key_data is not None
        assert len(key.key_data) == 32
        assert key.algorithm == "aes-256-gcm"
        assert key.purpose == "metadata_test"
        assert key.created_at is not None

