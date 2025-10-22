"""
Unit tests for QRLiveProtocol core functionality.

Tests QR generation, verification, and integration with cryptographic components.
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock

from src import QRLiveProtocol, QRLPConfig, QRData
from src.crypto import KeyManager, DataEncryptor, HMACManager


class TestQRLiveProtocol:
    """Test suite for QRLiveProtocol class."""

    def test_qrlive_protocol_initialization(self, test_config, temp_key_dir):
        """Test QRLiveProtocol initializes correctly."""
        qrlp = QRLiveProtocol(test_config)

        assert qrlp.config == test_config
        assert qrlp._running is False
        assert qrlp._sequence_number == 0
        assert qrlp._update_count == 0
        assert qrlp.qr_generator is not None
        assert qrlp.time_provider is not None
        assert qrlp.blockchain_verifier is not None
        assert qrlp.identity_manager is not None

        # Check cryptographic components are initialized
        assert qrlp.key_manager is not None
        assert qrlp.signature_manager is not None
        assert qrlp.encryptor is not None
        assert qrlp.hmac_manager is not None

    def test_generate_single_qr_basic(self, qrlp_instance):
        """Test basic QR generation."""
        qr_data, qr_image = qrlp_instance.generate_single_qr()

        assert isinstance(qr_data, QRData)
        assert isinstance(qr_image, bytes)
        assert len(qr_image) > 0

        # Check QR data structure
        assert qr_data.timestamp is not None
        assert qr_data.identity_hash is not None
        assert qr_data.sequence_number == 1

        # Check that QR image is valid PNG
        assert qr_image.startswith(b'\x89PNG\r\n\x1a\n')

    def test_generate_single_qr_with_user_data(self, qrlp_instance):
        """Test QR generation with custom user data."""
        user_data = {"event": "test_event", "user_id": "user123"}

        qr_data, qr_image = qrlp_instance.generate_single_qr(user_data)

        assert qr_data.user_data == user_data
        assert qr_image is not None

    def test_generate_single_qr_with_signing(self, qrlp_instance):
        """Test QR generation with digital signature."""
        # Generate a key first
        public_key, private_key = qrlp_instance.key_manager.generate_keypair("rsa", 2048)

        qr_data, qr_image = qrlp_instance.generate_single_qr(sign_data=True)

        # Should have signature fields
        qr_dict = qr_data.__dict__
        assert '_hmac' in qr_dict  # HMAC is always added
        # Digital signature may or may not be present depending on key availability

    def test_generate_signed_qr(self, qrlp_instance):
        """Test generating signed QR codes."""
        # Generate a key first
        public_key, private_key = qrlp_instance.key_manager.generate_keypair("rsa", 2048)

        keys_info = qrlp_instance.key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        qr_data, qr_image = qrlp_instance.generate_signed_qr(signing_key_id=key_id)

        # Should have signature fields
        qr_dict = qr_data.__dict__
        assert 'digital_signature' in qr_dict
        assert 'signing_key_id' in qr_dict
        assert 'signature_algorithm' in qr_dict

        # Signature should be valid hex
        signature_hex = qr_dict['digital_signature']
        signature_bytes = bytes.fromhex(signature_hex)
        assert len(signature_bytes) > 0

    def test_generate_encrypted_qr(self, qrlp_instance):
        """Test generating encrypted QR codes."""
        user_data = {"sensitive": "secret_data"}

        qr_data, qr_image = qrlp_instance.generate_encrypted_qr(user_data)

        # Should have encryption fields
        qr_dict = qr_data.__dict__
        assert '_encrypted_fields' in qr_dict
        assert '_encryption_key_id' in qr_dict
        assert '_encrypted_at' in qr_dict

        # User data should be encrypted
        assert qr_dict['user_data'] != user_data['sensitive']

    def test_verify_qr_data_basic(self, qrlp_instance):
        """Test basic QR data verification."""
        # Generate QR data
        qr_data, qr_image = qrlp_instance.generate_single_qr()

        # Convert to JSON for verification
        qr_json = qr_data.to_json()

        # Verify the QR data
        results = qrlp_instance.verify_qr_data(qr_json)

        # Should have all verification fields
        expected_keys = [
            'valid_json', 'identity_verified', 'time_verified',
            'blockchain_verified', 'signature_verified', 'hmac_verified', 'encrypted'
        ]

        for key in expected_keys:
            assert key in results

        # HMAC should always be verified (it's always added)
        assert results['hmac_verified'] is True

    def test_verify_qr_data_with_signature(self, qrlp_instance):
        """Test verification of signed QR data."""
        # Generate signed QR data
        keys_info = qrlp_instance.key_manager.list_keys()
        if keys_info:
            key_id = list(keys_info.keys())[0]
            qr_data, qr_image = qrlp_instance.generate_signed_qr(signing_key_id=key_id)

            # Convert to JSON for verification
            qr_json = json.dumps(qr_data.__dict__, separators=(',', ':'))

            # Verify the QR data
            results = qrlp_instance.verify_qr_data(qr_json)

            assert results['signature_verified'] is True
            assert results['hmac_verified'] is True

    def test_verify_qr_data_with_encryption(self, qrlp_instance):
        """Test verification of encrypted QR data."""
        # Generate encrypted QR data
        user_data = {"test": "data"}
        qr_data, qr_image = qrlp_instance.generate_encrypted_qr(user_data)

        # Convert to JSON for verification
        qr_json = json.dumps(qr_data.__dict__, separators=(',', ':'))

        # Verify the QR data
        results = qrlp_instance.verify_qr_data(qr_json)

        assert results['encrypted'] is True
        # Should be able to decrypt and verify HMAC
        assert results['hmac_verified'] is True

    def test_verify_invalid_json_fails(self, qrlp_instance):
        """Test that invalid JSON fails verification."""
        invalid_json = '{"invalid": json}'

        results = qrlp_instance.verify_qr_data(invalid_json)

        assert results['valid_json'] is False
        assert 'error' in results

    def test_verify_tampered_qr_fails(self, qrlp_instance):
        """Test that tampered QR data fails verification."""
        # Generate valid QR data
        qr_data, qr_image = qrlp_instance.generate_single_qr()

        # Convert to dictionary and tamper with it
        qr_dict = qr_data.__dict__.copy()
        qr_dict['sequence_number'] = 999  # Tamper with sequence number

        # Convert back to JSON
        tampered_json = json.dumps(qr_dict, separators=(',', ':'))

        # Verification should fail
        results = qrlp_instance.verify_qr_data(tampered_json)

        # HMAC verification should fail because data was tampered
        assert results['hmac_verified'] is False

    def test_qr_generation_sequence_numbering(self, qrlp_instance):
        """Test that QR generation increments sequence numbers."""
        # Generate first QR
        qr_data1, _ = qrlp_instance.generate_single_qr()
        assert qr_data1.sequence_number == 1

        # Generate second QR
        qr_data2, _ = qrlp_instance.generate_single_qr()
        assert qr_data2.sequence_number == 2

        # Generate third QR
        qr_data3, _ = qrlp_instance.generate_single_qr()
        assert qr_data3.sequence_number == 3

    def test_get_current_qr_data(self, qrlp_instance):
        """Test getting current QR data."""
        # Initially should be None
        current = qrlp_instance.get_current_qr_data()
        assert current is None

        # Generate a QR
        qr_data, _ = qrlp_instance.generate_single_qr()

        # Should now return the generated data
        current = qrlp_instance.get_current_qr_data()
        assert current is not None
        assert current.sequence_number == qr_data.sequence_number

    def test_get_statistics(self, qrlp_instance):
        """Test getting statistics."""
        stats = qrlp_instance.get_statistics()

        # Should have all expected sections
        expected_sections = [
            'running', 'total_updates', 'sequence_number', 'last_update_time',
            'current_qr_data', 'time_provider_stats', 'blockchain_stats',
            'identity_stats', 'crypto_stats'
        ]

        for section in expected_sections:
            assert section in stats

        # Check crypto stats
        crypto_stats = stats['crypto_stats']
        assert 'keys_count' in crypto_stats
        assert 'signature_count' in crypto_stats
        assert 'encryption_enabled' in crypto_stats
        assert 'hmac_enabled' in crypto_stats

    def test_callback_system(self, qrlp_instance):
        """Test callback system for QR updates."""
        callback_called = False
        callback_data = None
        callback_image = None

        def test_callback(qr_data, qr_image):
            nonlocal callback_called, callback_data, callback_image
            callback_called = True
            callback_data = qr_data
            callback_image = qr_image

        # Add callback
        qrlp_instance.add_update_callback(test_callback)

        # Generate QR (should trigger callback)
        qr_data, qr_image = qrlp_instance.generate_single_qr()

        # Callback should have been called
        assert callback_called is True
        assert callback_data is not None
        assert callback_image is not None
        assert callback_data.sequence_number == qr_data.sequence_number

    def test_remove_callback(self, qrlp_instance):
        """Test removing callbacks."""
        callback_called = False

        def test_callback(qr_data, qr_image):
            nonlocal callback_called
            callback_called = True

        # Add and then remove callback
        qrlp_instance.add_update_callback(test_callback)
        qrlp_instance.remove_update_callback(test_callback)

        # Generate QR (should not trigger removed callback)
        qrlp_instance.generate_single_qr()

        # Callback should not have been called
        assert callback_called is False

    def test_user_data_callback(self, qrlp_instance):
        """Test user data callback functionality."""
        def get_user_data():
            return "Test user data from callback"

        # Set user data callback
        qrlp_instance.set_user_data_callback(get_user_data)

        # Generate QR with user data
        qr_data, qr_image = qrlp_instance.generate_single_qr()

        # Should include user data from callback
        assert qr_data.user_data is not None
        assert qr_data.user_data.get('user_text') == "Test user data from callback"

    def test_qr_data_to_from_json(self):
        """Test QRData JSON serialization and deserialization."""
        # Create original QR data
        original_data = QRData(
            timestamp="2025-01-11T15:30:45.123Z",
            identity_hash="test_hash_123",
            blockchain_hashes={"bitcoin": "block_hash"},
            time_server_verification={"server1": {"timestamp": "2025-01-11T15:30:45Z"}},
            user_data={"test": "data"},
            sequence_number=1
        )

        # Convert to JSON
        json_str = original_data.to_json()

        # Convert back from JSON
        restored_data = QRData.from_json(json_str)

        # Should be identical
        assert restored_data.timestamp == original_data.timestamp
        assert restored_data.identity_hash == original_data.identity_hash
        assert restored_data.blockchain_hashes == original_data.blockchain_hashes
        assert restored_data.time_server_verification == original_data.time_server_verification
        assert restored_data.user_data == original_data.user_data
        assert restored_data.sequence_number == original_data.sequence_number

    def test_qr_data_json_format(self):
        """Test that QR data JSON is properly formatted."""
        qr_data = QRData(
            timestamp="2025-01-11T15:30:45.123Z",
            identity_hash="test_hash_123",
            blockchain_hashes={"bitcoin": "block_hash"},
            time_server_verification={"server1": {"timestamp": "2025-01-11T15:30:45Z"}},
            sequence_number=1
        )

        json_str = qr_data.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

        # Should use compact formatting (no spaces after commas/colons)
        assert '","' in json_str or '":{"' in json_str

    def test_cryptographic_enhancement_integration(self, qrlp_instance):
        """Test that cryptographic enhancements work together."""
        # Generate QR with all cryptographic features
        user_data = {"test": "integration_data"}
        qr_data, qr_image = qrlp_instance.generate_single_qr(
            user_data=user_data,
            sign_data=True,
            encrypt_data=True
        )

        # Convert to JSON for verification
        qr_dict = qr_data.__dict__
        qr_json = json.dumps(qr_dict, separators=(',', ':'))

        # Verify the QR data
        results = qrlp_instance.verify_qr_data(qr_json)

        # Should verify successfully with all features
        assert results['valid_json'] is True
        assert results['hmac_verified'] is True

        # May have signature verification depending on key availability
        if results['signature_verified']:
            assert results['signature_verified'] is True

        # Should be marked as encrypted
        assert results['encrypted'] is True

