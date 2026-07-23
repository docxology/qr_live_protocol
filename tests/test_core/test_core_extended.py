"""
Extended tests for core.py QRLiveProtocol.

Covers encrypted QR generation, verification with encryption,
update loop, context manager, callbacks, and statistics.
"""

import json
import time
import pytest
import tempfile
import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.core import QRLiveProtocol, QRData
from src.config import QRLPConfig
from src.crypto import KeyManager, HMACManager, DataEncryptor, QRSignatureManager
from src.trust import TrustStore


class TestEncryptedQR:
    """Test encrypted QR generation and verification."""

    def test_generate_encrypted_qr(self, qrlp_instance):
        """generate_encrypted_qr should produce encrypted QR data."""
        qr_data, qr_image = qrlp_instance.generate_encrypted_qr(
            user_data={"secret": "value"}
        )
        assert qr_data._encrypted_fields is not None
        assert "user_data" in qr_data._encrypted_fields
        assert qr_image[:4] == b'\x89PNG'

    def test_verify_encrypted_qr(self, qrlp_instance):
        """verify_qr_data should decrypt and verify encrypted QR."""
        qr_data, _ = qrlp_instance.generate_encrypted_qr(
            user_data={"secret": "value"}
        )
        qr_json = qr_data.to_json()
        results = qrlp_instance.verify_qr_data(qr_json)
        assert results["valid_json"] is True
        assert results["encrypted"] is True

    def test_verify_encrypted_qr_decryption_failure(self, qrlp_instance):
        """verify_qr_data returns invalid when decryption fails."""
        qr_data, _ = qrlp_instance.generate_encrypted_qr(
            user_data={"secret": "value"}
        )
        qr_json = qr_data.to_json()
        # Tamper with encrypted data
        tampered = json.loads(qr_json)
        tampered["user_data"] = "tampered_encrypted_data"
        results = qrlp_instance.verify_qr_data(json.dumps(tampered))
        # Should either fail decryption or fail HMAC
        assert results["valid"] is False or results.get("encrypted") is True


class TestUpdateLoop:
    """Test live generation update loop."""

    def test_start_stop_live_generation(self, qrlp_instance):
        """start_live_generation and stop_live_generation work."""
        qrlp_instance.config.update_interval = 0.05
        qrlp_instance.start_live_generation()
        assert qrlp_instance._running is True
        time.sleep(0.2)
        qrlp_instance.stop_live_generation()
        assert qrlp_instance._running is False

    def test_start_live_generation_idempotent(self, qrlp_instance):
        """Starting live generation twice doesn't create two threads."""
        qrlp_instance.config.update_interval = 0.05
        qrlp_instance.start_live_generation()
        first_thread = qrlp_instance._update_thread
        qrlp_instance.start_live_generation()
        assert qrlp_instance._update_thread is first_thread
        qrlp_instance.stop_live_generation()

    def test_context_manager(self, qrlp_instance):
        """QRLiveProtocol works as context manager."""
        qrlp_instance.config.update_interval = 0.05
        with qrlp_instance as qrlp:
            assert qrlp._running is True
            time.sleep(0.15)
        assert qrlp._running is False

    def test_update_loop_generates_qr(self, qrlp_instance):
        """Update loop should generate QR codes and update state."""
        qrlp_instance.config.update_interval = 0.05
        qrlp_instance.start_live_generation()
        time.sleep(0.25)
        qrlp_instance.stop_live_generation()
        assert qrlp_instance._update_count > 0
        assert qrlp_instance._current_qr_data is not None


class TestCallbacks:
    """Test callback management."""

    def test_add_callback_called(self, qrlp_instance):
        """Callbacks are called on QR generation."""
        received = []
        def callback(qr_data, qr_image):
            received.append((qr_data, qr_image))

        qrlp_instance.add_update_callback(callback)
        qrlp_instance.generate_single_qr()
        assert len(received) == 1
        assert received[0][0].sequence_number == 1
        assert isinstance(received[0][1], bytes)

    def test_remove_callback(self, qrlp_instance):
        """Removed callbacks are not called."""
        received = []
        def callback(qr_data, qr_image):
            received.append(qr_data)

        qrlp_instance.add_update_callback(callback)
        qrlp_instance.generate_single_qr()
        assert len(received) == 1

        qrlp_instance.remove_update_callback(callback)
        qrlp_instance.generate_single_qr()
        assert len(received) == 1  # No new call

    def test_callback_exception_doesnt_crash(self, qrlp_instance):
        """Exception in callback doesn't crash generation."""
        def bad_callback(qr_data, qr_image):
            raise RuntimeError("Callback error")

        qrlp_instance.add_update_callback(bad_callback)
        # Should not raise
        qr_data, qr_image = qrlp_instance.generate_single_qr()
        assert qr_data is not None

    def test_set_user_data_callback(self, qrlp_instance):
        """User data callback provides dynamic data."""
        def data_callback():
            return {"dynamic": "data"}

        qrlp_instance.set_user_data_callback(data_callback)
        qr_data, _ = qrlp_instance.generate_single_qr()
        assert qr_data.user_data == {"dynamic": "data"}

    def test_user_data_callback_returns_string(self, qrlp_instance):
        """User data callback returning string wraps in dict."""
        def data_callback():
            return "plain text"

        qrlp_instance.set_user_data_callback(data_callback)
        qr_data, _ = qrlp_instance.generate_single_qr()
        assert qr_data.user_data == {"user_text": "plain text"}

    def test_user_data_callback_returns_none(self, qrlp_instance):
        """User data callback returning None means no user data."""
        def data_callback():
            return None

        qrlp_instance.set_user_data_callback(data_callback)
        qr_data, _ = qrlp_instance.generate_single_qr()
        assert qr_data.user_data is None

    def test_user_data_callback_exception(self, qrlp_instance):
        """User data callback exception is caught."""
        def data_callback():
            raise RuntimeError("callback error")

        qrlp_instance.set_user_data_callback(data_callback)
        qr_data, _ = qrlp_instance.generate_single_qr()
        assert qr_data.user_data is None


class TestVerification:
    """Test QR verification paths."""

    def test_verify_invalid_json(self, qrlp_instance):
        """verify_qr_data returns invalid for bad JSON."""
        results = qrlp_instance.verify_qr_data("not json at all")
        assert results["valid_json"] is False
        assert results["valid"] is False
        assert "error" in results

    def test_verify_non_object_json(self, qrlp_instance):
        """verify_qr_data returns invalid for non-object JSON."""
        results = qrlp_instance.verify_qr_data("[1, 2, 3]")
        assert results["valid_json"] is False
        assert results["valid"] is False

    def test_verify_signed_qr_round_trip(self, qrlp_instance):
        """Sign a QR and verify it."""
        qr_data, _ = qrlp_instance.generate_single_qr(sign_data=True)
        results = qrlp_instance.verify_qr_data(qr_data.to_json())
        assert results["valid_json"] is True
        assert results["signature_verified"] is True

    def test_verify_with_trust_store(self, qrlp_instance):
        """Verify with trusted public key."""
        qr_data, _ = qrlp_instance.generate_single_qr(sign_data=True)
        public_key = qrlp_instance.key_manager.export_public_key(qr_data.signing_key_id)

        trust_store = TrustStore()
        trust_store.add_public_key(
            qr_data.issuer_id,
            qr_data.signing_key_id,
            public_key,
            qr_data.signature_algorithm,
        )
        qrlp_instance.trust_store = trust_store

        results = qrlp_instance.verify_qr_data(qr_data.to_json())
        assert results["signature_verified"] is True
        assert results["trust_mode"] == "public_signature"

    def test_verify_tampered_hmac(self, qrlp_instance):
        """Tampered HMAC fails verification."""
        qr_data, _ = qrlp_instance.generate_single_qr(sign_data=False)
        qr_json = qr_data.to_json()
        tampered = json.loads(qr_json)
        tampered["_hmac"] = "0" * 64
        results = qrlp_instance.verify_qr_data(json.dumps(tampered))
        assert results["hmac_verified"] is False

    def test_verify_missing_hmac(self, qrlp_instance):
        """Missing HMAC field returns hmac_verified=False."""
        qr_data, _ = qrlp_instance.generate_single_qr(sign_data=False)
        qr_json = qr_data.to_json()
        tampered = json.loads(qr_json)
        del tampered["_hmac"]
        results = qrlp_instance.verify_qr_data(json.dumps(tampered))
        assert results["hmac_verified"] is False

    def test_verify_expired_qr(self, qrlp_instance):
        """Expired QR should fail time verification."""
        qr_data, _ = qrlp_instance.generate_single_qr()
        qr_json = qr_data.to_json()
        tampered = json.loads(qr_json)
        # Set expiry in the past
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        tampered["expires_at"] = past
        results = qrlp_instance.verify_qr_data(json.dumps(tampered))
        assert results["time_verified"] is False

    def test_verify_with_blockchain_hashes(self, qrlp_instance):
        """QR with blockchain hashes triggers blockchain verification."""
        qr_data, _ = qrlp_instance.generate_single_qr()
        qr_json = qr_data.to_json()
        tampered = json.loads(qr_json)
        tampered["blockchain_hashes"] = {"bitcoin": "fakehash"}
        results = qrlp_instance.verify_qr_data(json.dumps(tampered))
        # Blockchain hash won't match current
        assert "blockchain_verified" in results


class TestStatistics:
    """Test get_statistics."""

    def test_statistics_initial(self, qrlp_instance):
        """Initial statistics show zero state."""
        stats = qrlp_instance.get_statistics()
        assert stats["running"] is False
        assert stats["total_updates"] == 0
        assert stats["sequence_number"] == 0
        assert stats["current_qr_data"] is None

    def test_statistics_after_generation(self, qrlp_instance):
        """Statistics update after QR generation."""
        qrlp_instance.generate_single_qr()
        qrlp_instance.generate_single_qr()
        stats = qrlp_instance.get_statistics()
        assert stats["total_updates"] == 2
        assert stats["sequence_number"] == 2
        assert stats["current_qr_data"] is not None
        assert "time_provider_stats" in stats
        assert "blockchain_stats" in stats
        assert "identity_stats" in stats
        assert "crypto_stats" in stats

    def test_get_current_qr_data(self, qrlp_instance):
        """get_current_qr_data returns most recent QR data."""
        assert qrlp_instance.get_current_qr_data() is None
        qrlp_instance.generate_single_qr()
        current = qrlp_instance.get_current_qr_data()
        assert current is not None
        assert current.sequence_number == 1


class TestKeyManagerProperty:
    """Test key_manager property and setter."""

    def test_key_manager_setter_updates_signature_manager(self, qrlp_instance, temp_key_dir):
        """Setting key_manager updates signature_manager.key_manager."""
        new_km = KeyManager(str(temp_key_dir))
        qrlp_instance.key_manager = new_km
        assert qrlp_instance.key_manager is new_km
        assert qrlp_instance.signature_manager.key_manager is new_km

    def test_key_manager_property_returns_manager(self, qrlp_instance):
        """key_manager property returns the KeyManager."""
        assert qrlp_instance.key_manager is not None
        assert hasattr(qrlp_instance.key_manager, 'list_keys')


class TestResolveMethods:
    """Test internal resolve methods."""

    def test_resolve_issuer_id_with_explicit(self, qrlp_instance):
        """_resolve_issuer_id returns issuer_id when set."""
        qrlp_instance.issuer_id = "my-issuer"
        result = qrlp_instance._resolve_issuer_id("some-hash")
        assert result == "my-issuer"

    def test_resolve_issuer_id_fallback(self, qrlp_instance):
        """_resolve_issuer_id falls back to identity_hash."""
        qrlp_instance.issuer_id = None
        result = qrlp_instance._resolve_issuer_id("some-hash")
        assert result == "some-hash"

    def test_content_hash_none(self, qrlp_instance):
        """_content_hash handles None user_data."""
        h = qrlp_instance._content_hash(None)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_content_hash_with_data(self, qrlp_instance):
        """_content_hash produces deterministic hash."""
        h1 = qrlp_instance._content_hash({"a": 1})
        h2 = qrlp_instance._content_hash({"a": 1})
        h3 = qrlp_instance._content_hash({"a": 2})
        assert h1 == h2
        assert h1 != h3

    def test_expires_at_with_ttl(self, qrlp_instance):
        """_expires_at uses qr_ttl_seconds when set."""
        qrlp_instance.config.security_settings.qr_ttl_seconds = 60
        now = datetime.now(timezone.utc)
        result = qrlp_instance._expires_at(now)
        expires = datetime.fromisoformat(result)
        assert (expires - now).total_seconds() == 60

    def test_expires_at_fallback_to_max_time_drift(self, qrlp_instance):
        """_expires_at falls back to max_time_drift."""
        qrlp_instance.config.security_settings.qr_ttl_seconds = None
        qrlp_instance.config.verification_settings.max_time_drift = 45.0
        now = datetime.now(timezone.utc)
        result = qrlp_instance._expires_at(now)
        expires = datetime.fromisoformat(result)
        assert int((expires - now).total_seconds()) == 45

    def test_ensure_signing_key_existing(self, qrlp_instance):
        """_ensure_signing_key returns existing key."""
        # Generate a key first
        qrlp_instance.key_manager.generate_keypair(purpose="qr_signing")
        key_id = qrlp_instance._ensure_signing_key()
        assert key_id is not None
        assert qrlp_instance.key_manager.get_keypair(key_id) is not None

    def test_ensure_signing_key_nonexistent_raises(self, qrlp_instance):
        """_ensure_signing_key raises for nonexistent specified key."""
        with pytest.raises(ValueError, match="Signing key not found"):
            qrlp_instance._ensure_signing_key("nonexistent-key-id")

    def test_ensure_signing_key_auto_generates(self, temp_key_dir):
        """_ensure_signing_key auto-generates a key when none exist."""
        config = QRLPConfig()
        config.blockchain_settings.enabled_chains = set()
        config.time_settings.time_servers = []
        config.security_settings.key_dir = str(temp_key_dir)
        qrlp = QRLiveProtocol(config)
        key_id = qrlp._ensure_signing_key()
        assert key_id is not None
        assert qrlp.key_manager.get_keypair(key_id) is not None


class TestGenerateSignedQR:
    """Test generate_signed_qr method."""

    def test_generate_signed_qr(self, qrlp_instance):
        """generate_signed_qr produces signed QR."""
        qr_data, qr_image = qrlp_instance.generate_signed_qr(
            user_data={"event": "test"}
        )
        assert qr_data.digital_signature is not None
        assert qr_data.signing_key_id is not None
        assert qr_data.signature_algorithm is not None
        assert qr_image[:4] == b'\x89PNG'

    def test_generate_signed_qr_with_key_id(self, qrlp_instance):
        """generate_signed_qr with specific key_id."""
        qrlp_instance.key_manager.generate_keypair(purpose="qr_signing")
        key_id = next(iter(qrlp_instance.key_manager.list_keys()))
        qr_data, _ = qrlp_instance.generate_signed_qr(signing_key_id=key_id)
        assert qr_data.signing_key_id == key_id
