"""
Unit tests for Digital Signature cryptographic functionality.

Tests RSA and ECDSA digital signature creation and verification.
"""

import pytest
import json
from datetime import datetime, timezone

from src.crypto import KeyManager, DigitalSigner, SignatureVerifier, QRSignatureManager
from src.crypto.exceptions import SignatureError


class TestDigitalSigner:
    """Test suite for DigitalSigner class."""

    def test_rsa_signer_initialization(self, key_manager):
        """Test RSA signer initialization."""
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        signer = DigitalSigner(private_key, "rsa")

        assert signer.algorithm == "rsa"
        assert signer.private_key is not None

    def test_ecdsa_signer_initialization(self, key_manager):
        """Test ECDSA signer initialization."""
        public_key, private_key = key_manager.generate_keypair("ecdsa", 256)

        signer = DigitalSigner(private_key, "ecdsa")

        assert signer.algorithm == "ecdsa"
        assert signer.private_key is not None

    def test_sign_qr_data(self, key_manager):
        """Test signing QR data."""
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        signer = DigitalSigner(private_key, "rsa")

        # Create test QR data
        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        signature = signer.sign_qr_data(qr_data)

        assert isinstance(signature, bytes)
        assert len(signature) > 0

    def test_sign_message(self, key_manager):
        """Test signing arbitrary message."""
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        signer = DigitalSigner(private_key, "rsa")

        message = "Test message for signing"
        signature = signer.sign_message(message)

        assert isinstance(signature, bytes)
        assert len(signature) > 0

    def test_invalid_algorithm_raises_error(self, key_manager):
        """Test that invalid algorithm raises error."""
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        with pytest.raises(SignatureError, match="Unsupported algorithm"):
            DigitalSigner(private_key, "invalid_algorithm")


class TestSignatureVerifier:
    """Test suite for SignatureVerifier class."""

    def test_rsa_verifier_initialization(self, key_manager):
        """Test RSA verifier initialization."""
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        verifier = SignatureVerifier(public_key, "rsa")

        assert verifier.algorithm == "rsa"
        assert verifier.public_key is not None

    def test_ecdsa_verifier_initialization(self, key_manager):
        """Test ECDSA verifier initialization."""
        public_key, private_key = key_manager.generate_keypair("ecdsa", 256)

        verifier = SignatureVerifier(public_key, "ecdsa")

        assert verifier.algorithm == "ecdsa"
        assert verifier.public_key is not None

    def test_verify_qr_data_signature(self, key_manager):
        """Test verifying QR data signature."""
        # Generate key pair
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        # Create signer and verifier
        signer = DigitalSigner(private_key, "rsa")
        verifier = SignatureVerifier(public_key, "rsa")

        # Create and sign QR data
        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        signature = signer.sign_qr_data(qr_data)

        # Verify signature
        is_valid = verifier.verify_qr_data(qr_data, signature)
        assert is_valid is True

    def test_verify_message_signature(self, key_manager):
        """Test verifying message signature."""
        # Generate key pair
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        # Create signer and verifier
        signer = DigitalSigner(private_key, "rsa")
        verifier = SignatureVerifier(public_key, "rsa")

        # Create and sign message
        message = "Test message for verification"
        signature = signer.sign_message(message)

        # Verify signature
        is_valid = verifier.verify_message(message, signature)
        assert is_valid is True

    def test_verify_invalid_signature_fails(self, key_manager):
        """Test that invalid signature fails verification."""
        # Generate key pair
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        # Create verifier
        verifier = SignatureVerifier(public_key, "rsa")

        # Create fake signature (wrong data)
        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        fake_signature = b"fake_signature_data"

        # Verification should fail
        is_valid = verifier.verify_qr_data(qr_data, fake_signature)
        assert is_valid is False

    def test_verify_tampered_data_fails(self, key_manager):
        """Test that tampered data fails verification."""
        # Generate key pair
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        # Create signer and verifier
        signer = DigitalSigner(private_key, "rsa")
        verifier = SignatureVerifier(public_key, "rsa")

        # Create and sign QR data
        original_qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        signature = signer.sign_qr_data(original_qr_data)

        # Tamper with the data
        tampered_qr_data = original_qr_data.copy()
        tampered_qr_data["sequence_number"] = 999

        # Verification should fail
        is_valid = verifier.verify_qr_data(tampered_qr_data, signature)
        assert is_valid is False

    def test_ecdsa_signature_verification(self, key_manager):
        """Test ECDSA signature verification."""
        # Generate ECDSA key pair
        public_key, private_key = key_manager.generate_keypair("ecdsa", 256)

        # Create signer and verifier
        signer = DigitalSigner(private_key, "ecdsa")
        verifier = SignatureVerifier(public_key, "ecdsa")

        # Create and sign data
        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash_ecdsa",
            "sequence_number": 2
        }

        signature = signer.sign_qr_data(qr_data)

        # Verify signature
        is_valid = verifier.verify_qr_data(qr_data, signature)
        assert is_valid is True


class TestQRSignatureManager:
    """Test suite for QRSignatureManager class."""

    def test_signature_manager_initialization(self, key_manager):
        """Test signature manager initialization."""
        sm = QRSignatureManager(key_manager)

        assert sm.key_manager == key_manager

    def test_sign_qr_with_key(self, key_manager):
        """Test signing QR data with specific key."""
        # Generate key pair
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        sm = QRSignatureManager(key_manager)

        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Create QR data
        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        # Sign with specific key
        signature, used_key_id = sm.sign_qr_with_key(qr_data, key_id)

        assert isinstance(signature, bytes)
        assert len(signature) > 0
        assert used_key_id == key_id

        # Check that usage was tracked
        key_info = key_manager.list_keys()[key_id]
        assert key_info.usage_count == 1
        assert key_info.last_used is not None

    def test_verify_qr_signature(self, key_manager):
        """Test verifying QR signature with specific key."""
        # Generate key pair
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        sm = QRSignatureManager(key_manager)

        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Create and sign QR data
        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        signature, _ = sm.sign_qr_with_key(qr_data, key_id)

        # Verify signature
        is_valid = sm.verify_qr_signature(qr_data, signature, key_id)
        assert is_valid is True

    def test_verify_invalid_signature_fails(self, key_manager):
        """Test that invalid signature fails verification."""
        sm = QRSignatureManager(key_manager)

        keys_info = key_manager.list_keys()
        if keys_info:
            key_id = list(keys_info.keys())[0]

            qr_data = {
                "timestamp": "2025-01-11T15:30:45.123Z",
                "identity_hash": "test_identity_hash",
                "sequence_number": 1
            }

            fake_signature = b"fake_signature"

            is_valid = sm.verify_qr_signature(qr_data, fake_signature, key_id)
            assert is_valid is False

    def test_create_signed_qr_data(self, key_manager):
        """Test creating QR data with embedded signature."""
        # Generate key pair
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        sm = QRSignatureManager(key_manager)

        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Create original QR data
        original_qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        # Create signed QR data
        signed_qr_data = sm.create_signed_qr_data(original_qr_data, key_id)

        # Should have signature fields
        assert 'digital_signature' in signed_qr_data
        assert 'signing_key_id' in signed_qr_data
        assert 'signature_algorithm' in signed_qr_data

        # Signature should be valid hex
        signature_hex = signed_qr_data['digital_signature']
        signature_bytes = bytes.fromhex(signature_hex)
        assert len(signature_bytes) > 0

        # Key ID should match
        assert signed_qr_data['signing_key_id'] == key_id

    def test_verify_signed_qr_data(self, key_manager):
        """Test verifying QR data with embedded signature."""
        # Generate key pair
        public_key, private_key = key_manager.generate_keypair("rsa", 2048)

        sm = QRSignatureManager(key_manager)

        keys_info = key_manager.list_keys()
        key_id = list(keys_info.keys())[0]

        # Create original QR data
        original_qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        # Create signed QR data
        signed_qr_data = sm.create_signed_qr_data(original_qr_data, key_id)

        # Verify signed data
        is_valid = sm.verify_signed_qr_data(signed_qr_data)
        assert is_valid is True

    def test_verify_signed_qr_data_tampered_fails(self, key_manager):
        """Test that tampered signed data fails verification."""
        sm = QRSignatureManager(key_manager)

        keys_info = key_manager.list_keys()
        if keys_info:
            key_id = list(keys_info.keys())[0]

            # Create original QR data
            original_qr_data = {
                "timestamp": "2025-01-11T15:30:45.123Z",
                "identity_hash": "test_identity_hash",
                "sequence_number": 1
            }

            # Create signed QR data
            signed_qr_data = sm.create_signed_qr_data(original_qr_data, key_id)

            # Tamper with the data
            signed_qr_data["sequence_number"] = 999

            # Verification should fail
            is_valid = sm.verify_signed_qr_data(signed_qr_data)
            assert is_valid is False

    def test_verify_signed_qr_data_missing_signature_fails(self):
        """Test that data without signature fails verification."""
        sm = QRSignatureManager(KeyManager())

        qr_data = {
            "timestamp": "2025-01-11T15:30:45.123Z",
            "identity_hash": "test_identity_hash",
            "sequence_number": 1
        }

        # Should fail because no signature
        is_valid = sm.verify_signed_qr_data(qr_data)
        assert is_valid is False

