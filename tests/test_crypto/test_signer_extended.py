"""
Tests for signer canonicalization and crypto exception renaming.

Covers the double-canonicalization fix, KeyManagementError export,
and HMACError export.
"""

import pytest
from src.crypto import (
    KeyManager, QRSignatureManager, HMACManager, DataEncryptor,
    CryptoError, KeyManagementError, SignatureError, EncryptionError, HMACError,
)
from src.crypto.signer import (
    canonicalize_qr_payload_for_signature,
    DigitalSigner, SignatureVerifier,
    SIGNATURE_FIELDS, HMAC_FIELDS, ENCRYPTION_FIELDS,
)
from src.crypto.exceptions import KeyManagementError as exceptions_KeyManagementError


class TestCryptoExceptions:
    """Test renamed exception classes."""

    def test_key_management_error_is_crypto_error(self):
        """KeyManagementError should be a subclass of CryptoError."""
        assert issubclass(KeyManagementError, CryptoError)

    def test_key_management_error_not_builtin_keyerror(self):
        """KeyManagementError should NOT shadow Python's builtin KeyError."""
        assert KeyManagementError is not KeyError

    def test_hmac_error_is_crypto_error(self):
        """HMACError should be a subclass of CryptoError."""
        assert issubclass(HMACError, CryptoError)

    def test_hmac_error_exported(self):
        """HMACError should be exportable from src."""
        from src import HMACError as src_hmac_error
        assert src_hmac_error is HMACError

    def test_key_management_error_exported(self):
        """KeyManagementError should be exportable from src."""
        from src import KeyManagementError as src_kme
        assert src_kme is KeyManagementError


class TestCanonicalization:
    """Test payload canonicalization for signatures."""

    def test_canonicalize_strips_signature_fields(self):
        """canonicalize should remove signature, HMAC, and encryption fields."""
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc",
            "blockchain_hashes": {},
            "time_server_verification": {},
            "sequence_number": 1,
            "digital_signature": "sig",
            "signing_key_id": "key1",
            "signature_algorithm": "rsa",
            "_hmac": "hmacval",
            "_hmac_key_id": "key2",
            "_hmac_algorithm": "sha256",
            "_integrity_checked_at": "2025-01-01",
            "_encrypted_fields": ["user_data"],
            "_encryption_key_id": "key3",
            "_data_key_id": "key4",
            "_encrypted_at": "2025-01-01",
        }
        canonical = canonicalize_qr_payload_for_signature(data)
        for field in SIGNATURE_FIELDS | HMAC_FIELDS | ENCRYPTION_FIELDS:
            assert field not in canonical, f"Field {field} should be stripped"

    def test_canonicalize_strips_none_values(self):
        """canonicalize should remove None values."""
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc",
            "user_data": None,
            "issuer_id": None,
        }
        canonical = canonicalize_qr_payload_for_signature(data)
        assert "user_data" not in canonical
        assert "issuer_id" not in canonical
        assert "timestamp" in canonical

    def test_canonicalize_from_object(self):
        """canonicalize should work with objects having __dict__."""
        class FakeQRData:
            def __init__(self):
                self.timestamp = "2025-01-01T00:00:00Z"
                self.identity_hash = "abc"
                self.digital_signature = "sig"
                self.user_data = None
        obj = FakeQRData()
        canonical = canonicalize_qr_payload_for_signature(obj)
        assert canonical["timestamp"] == "2025-01-01T00:00:00Z"
        assert "digital_signature" not in canonical
        assert "user_data" not in canonical


class TestSignatureRoundTrip:
    """Test signature creation and verification round-trip."""

    def test_sign_and_verify_round_trip(self, temp_key_dir):
        """Sign data and verify with the same key."""
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="rsa", key_size=2048, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))

        mgr = QRSignatureManager(km)
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc123",
            "blockchain_hashes": {"bitcoin": "hashval"},
            "time_server_verification": {},
            "sequence_number": 1,
        }

        signed = mgr.create_signed_qr_data(data, key_id)
        assert "digital_signature" in signed
        assert "signing_key_id" in signed
        assert "signature_algorithm" in signed

        # Verify with local key
        assert mgr.verify_signed_qr_data(signed) is True

    def test_sign_and_verify_with_external_public_key(self, temp_key_dir):
        """Sign data, export public key, verify with external key."""
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="rsa", key_size=2048, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))

        mgr = QRSignatureManager(km)
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc123",
            "blockchain_hashes": {},
            "time_server_verification": {},
            "sequence_number": 1,
        }

        signed = mgr.create_signed_qr_data(data, key_id)
        public_key_pem = km.export_public_key(key_id)

        # Verify with external public key
        assert mgr.verify_signed_qr_data(
            signed, public_key_pem=public_key_pem, algorithm="rsa"
        ) is True

    def test_verify_tampered_signature_fails(self, temp_key_dir):
        """Tampered signature should fail verification."""
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="rsa", key_size=2048, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))

        mgr = QRSignatureManager(km)
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc123",
            "blockchain_hashes": {},
            "time_server_verification": {},
            "sequence_number": 1,
        }

        signed = mgr.create_signed_qr_data(data, key_id)
        # Tamper with the data
        signed["identity_hash"] = "tampered"
        assert mgr.verify_signed_qr_data(signed) is False

    def test_verify_missing_signature_returns_false(self, temp_key_dir):
        """Missing digital_signature field should return False."""
        km = KeyManager(str(temp_key_dir))
        mgr = QRSignatureManager(km)
        data = {"timestamp": "2025-01-01T00:00:00Z"}
        assert mgr.verify_signed_qr_data(data) is False

    def test_verify_corrupted_signature_returns_false(self, temp_key_dir):
        """Corrupted signature hex should return False."""
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="rsa", key_size=2048, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))

        mgr = QRSignatureManager(km)
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc123",
            "blockchain_hashes": {},
            "time_server_verification": {},
            "sequence_number": 1,
        }
        signed = mgr.create_signed_qr_data(data, key_id)
        # Corrupt the signature
        signed["digital_signature"] = "not_valid_hex!!"
        assert mgr.verify_signed_qr_data(signed) is False

    def test_sign_with_ecdsa(self, temp_key_dir):
        """ECDSA signing should work."""
        km = KeyManager(str(temp_key_dir))
        km.generate_keypair(algorithm="ecdsa", key_size=256, purpose="qr_signing")
        key_id = next(iter(km.list_keys()))

        mgr = QRSignatureManager(km)
        data = {
            "timestamp": "2025-01-01T00:00:00Z",
            "identity_hash": "abc123",
            "blockchain_hashes": {},
            "time_server_verification": {},
            "sequence_number": 1,
        }

        signed = mgr.create_signed_qr_data(data, key_id)
        assert signed["signature_algorithm"] == "ecdsa"
        assert mgr.verify_signed_qr_data(signed) is True

    def test_sign_qr_with_nonexistent_key_raises(self, temp_key_dir):
        """Signing with nonexistent key should raise SignatureError."""
        km = KeyManager(str(temp_key_dir))
        mgr = QRSignatureManager(km)
        data = {"timestamp": "2025-01-01T00:00:00Z"}
        with pytest.raises(SignatureError, match="Key not found"):
            mgr.sign_qr_with_key(data, "nonexistent_key")
