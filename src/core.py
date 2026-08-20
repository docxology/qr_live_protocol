"""
Core QRLP (QR Live Protocol) implementation.

This module provides the main QRLiveProtocol class that coordinates all
components to generate live, verifiable QR codes with time and identity information.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .blockchain_verifier import BlockchainVerifier
from .config import QRLPConfig
from .crypto import DataEncryptor, HMACManager, KeyManager, QRSignatureManager
from .identity_manager import IdentityManager
from .qr_generator import QRGenerator
from .time_provider import TimeProvider
from .time_stamper import TimeStamper
from .trust import TrustStore

_logger = logging.getLogger("qrlp.core")



@dataclass
class QRData:
    """Structure for QR code data payload."""
    timestamp: str
    identity_hash: str
    blockchain_hashes: dict[str, str]
    time_server_verification: dict[str, str]
    user_data: dict | None = None
    sequence_number: int = 0
    issuer_id: str | None = None
    event_id: str | None = None
    content_hash: str | None = None
    expires_at: str | None = None
    nonce: str | None = None

    # Cryptographic enhancement fields
    digital_signature: str | None = None
    signing_key_id: str | None = None
    signature_algorithm: str | None = None
    _hmac: str | None = None
    _hmac_key_id: str | None = None
    _hmac_algorithm: str | None = None
    _integrity_checked_at: str | None = None
    _encrypted_fields: list[str] | None = None
    _encryption_key_id: str | None = None
    _data_key_id: str | None = None
    _encrypted_at: str | None = None

    # OpenTimestamps (OTS) proof — additive, optional, backwards compatible.
    # Populated when OTS stamping is enabled in TimeSettings. Old QR payloads
    # without these fields still verify unchanged.
    ots_proof_path: str | None = None
    ots_verified: bool | None = None
    ots_timestamp: str | None = None

    def to_json(self) -> str:
        """Convert to JSON string for QR encoding."""
        # Convert to dict and filter out None values for deterministic serialization
        data_dict = asdict(self)
        # Keep only non-None values or values that are explicitly needed
        filtered_dict = {k: v for k, v in data_dict.items() if v is not None}
        return json.dumps(filtered_dict, separators=(',', ':'))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, filtering out None values.

        Unlike ``asdict()``, this returns a clean dict without None
        entries, suitable for JSON serialization or API responses.
        """
        data_dict = asdict(self)
        return {k: v for k, v in data_dict.items() if v is not None}

    def __repr__(self) -> str:
        return (
            f"QRData(seq={self.sequence_number}, ts={self.timestamp[:19]}, "
            f"issuer={self.issuer_id}, signed={'yes' if self.digital_signature else 'no'})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_json(cls, json_str: str) -> QRData:
        """Create QRData from JSON string.

        Unknown fields are silently ignored so that forward-compatible
        QR payloads (with newly added fields) do not break older verifiers.
        """
        data = json.loads(json_str)
        known_fields = {f.name for f in fields(cls)}  # type: ignore[name-defined]
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRData:
        """Create QRData from a dictionary.

        Inverse of ``to_dict()``. Unknown fields are silently ignored
        for forward compatibility, same as ``from_json()``.
        """
        known_fields = {f.name for f in fields(cls)}  # type: ignore[name-defined]
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class VerificationResult:
    """Structured result of QR data verification.

    Replaces the untyped dict returned by ``verify_qr_data`` with a
    typed dataclass that can be serialized to JSON or inspected programmatically.
    """

    valid_json: bool
    identity_verified: bool = False
    time_verified: bool = False
    blockchain_verified: bool = False
    signature_verified: bool = False
    hmac_verified: bool = False
    encrypted: bool = False
    valid: bool = False
    trust_mode: str = "none"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class QRLiveProtocol:
    """
    Main QR Live Protocol coordinator.

    Orchestrates time providers, blockchain verifiers, identity management,
    and QR generation to create live, verifiable QR codes for streaming.
    """

    def __init__(
        self,
        config: QRLPConfig | None = None,
        key_manager: KeyManager | None = None,
        signature_manager: QRSignatureManager | None = None,
        encryptor: DataEncryptor | None = None,
        hmac_manager: HMACManager | None = None,
        trust_store: TrustStore | None = None,
        issuer_id: str | None = None,
    ):
        """
        Initialize QRLP with configuration.

        Args:
            config: QRLPConfig object with settings, uses defaults if None
        """
        self.config = config or QRLPConfig()

        # Initialize components
        self.qr_generator = QRGenerator(self.config.qr_settings)
        self.time_provider = TimeProvider(self.config.time_settings)
        self.blockchain_verifier = BlockchainVerifier(self.config.blockchain_settings)
        self.identity_manager = IdentityManager(self.config.identity_settings)

        # OpenTimestamps stamper — additive layer. Disabled by default; when
        # enabled, QR commitments are periodically stamped against a public
        # blockchain. Graceful degradation: stamping failures never block QR
        # generation.
        self.time_stamper = TimeStamper(
            enabled=self.config.time_settings.ots_enabled,
            server=self.config.time_settings.ots_server,
            min_interval=self.config.time_settings.ots_min_interval,
            proof_dir=Path(self.config.time_settings.ots_proof_dir),
        )

        # Initialize cryptographic components
        self._key_manager: KeyManager | None = None
        self.key_manager = key_manager or KeyManager(self.config.security_settings.key_dir)
        self.signature_manager = signature_manager or QRSignatureManager(self.key_manager)
        self.signature_manager.key_manager = self.key_manager
        self.encryptor = encryptor or DataEncryptor()
        self.hmac_manager = hmac_manager or HMACManager()
        self.trust_store = trust_store or TrustStore()
        self.issuer_id = issuer_id or self.config.security_settings.issuer_id

        # State management
        self._running = False
        self._current_qr_data: QRData | None = None
        self._sequence_number = 0
        self._state_lock = threading.Lock()
        self._update_thread: threading.Thread | None = None
        self._callbacks: list[Callable[[QRData, bytes], None]] = []

        # User data callback for external input
        self._user_data_callback: Callable[[], str | None] | None = None

        # Expiry notification callback
        self._expiry_callback: Callable[[QRData], None] | None = None

        # Replay-protection state: nonce -> timestamp of first sighting, pruned
        # on each use. Only consulted when replay protection is enabled.
        self._seen_nonces: dict[str, float] = {}

        # Performance tracking
        self._last_update_time = 0
        self._update_count = 0

    @property
    def key_manager(self) -> KeyManager:
        """Key manager used for local signing and verification."""
        return self._key_manager

    @key_manager.setter
    def key_manager(self, value: KeyManager) -> None:
        self._key_manager = value
        if hasattr(self, "signature_manager") and self.signature_manager:
            self.signature_manager.key_manager = value

    def add_update_callback(self, callback: Callable[[QRData, bytes], None]) -> None:
        """
        Add callback function to be called when QR code updates.

        Args:
            callback: Function that takes (qr_data, qr_image_bytes) parameters
        """
        self._callbacks.append(callback)

    def remove_update_callback(self, callback: Callable[[QRData, bytes], None]) -> None:
        """Remove previously added callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def set_expiry_callback(self, callback: Callable[[QRData], None]) -> None:
        """Set callback invoked when a QR payload expires.

        Args:
            callback: Function that receives the expired QRData
        """
        self._expiry_callback = callback

    def set_user_data_callback(self, callback: Callable[[], str | None]) -> None:
        """
        Set callback function to get user data for QR generation.

        Args:
            callback: Function that returns user input string or None
        """
        self._user_data_callback = callback

    def start_live_generation(self) -> None:
        """Start continuous QR code generation in background thread."""
        if self._running:
            return

        self._running = True
        self._update_thread = threading.Thread(
            target=self._update_loop,
            daemon=True,
            name="QRLP-Update-Thread"
        )
        self._update_thread.start()

    def stop_live_generation(self) -> None:
        """Stop continuous QR code generation."""
        self._running = False
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=1.0)

    def generate_single_qr(self, user_data: dict | None = None,
                          sign_data: bool | None = None, encrypt_data: bool = False,
                          signing_key_id: str | None = None,
                          encryption_key_id: str | None = None) -> tuple[QRData, bytes]:
        """
        Generate a single QR code with current time and verification data.

        Args:
            user_data: Optional additional data to include in QR
            sign_data: Whether to digitally sign the QR data
            encrypt_data: Whether to encrypt sensitive fields
            signing_key_id: Optional local key to use for signing
            encryption_key_id: Optional data key to use for encryption

        Returns:
            Tuple of (QRData object, QR image as bytes)
        """
        if sign_data is None:
            sign_data = self.config.security_settings.sign_qr_data

        user_data = self._resolve_user_data(user_data)

        # Gather all verification data
        current_time = self.time_provider.get_current_time()
        identity_hash = self.identity_manager.get_identity_hash()
        blockchain_hashes = self.blockchain_verifier.get_blockchain_hashes()
        time_verification = self.time_provider.get_time_server_verification()
        issuer_id = self._resolve_issuer_id(identity_hash)

        # Increment sequence number for this QR
        with self._state_lock:
            self._sequence_number += 1
            sequence_number = self._sequence_number

        # Create QR data payload
        qr_data = QRData(
            timestamp=current_time.isoformat(),
            identity_hash=identity_hash,
            blockchain_hashes=blockchain_hashes,
            time_server_verification=time_verification,
            user_data=user_data,
            sequence_number=sequence_number,
            issuer_id=issuer_id,
            event_id=self.config.security_settings.event_id,
            content_hash=self._content_hash(user_data),
            expires_at=self._expires_at(current_time),
            nonce=secrets.token_hex(12)
        )

        # Apply cryptographic enhancements (always apply HMAC)
        signed_qr_data = self._apply_cryptographic_enhancements(
            qr_data,
            sign_data,
            encrypt_data,
            signing_key_id=signing_key_id,
            encryption_key_id=encryption_key_id,
        )

        # Generate QR code image
        qr_json = json.dumps(signed_qr_data, separators=(',', ':'))
        qr_image = self.qr_generator.generate_qr_image(qr_json)

        # OpenTimestamps stamping (additive, opt-in). The proof is stamped
        # against the exact QR payload bytes (``qr_json``) so that any verifier
        # can later confirm "this QR data existed at this time" on a public
        # blockchain. Only stamps periodically (``ots_min_interval``) to avoid
        # stamping every frame. Failures degrade gracefully: the QR is still
        # returned, just without an OTS proof path.
        if self.config.time_settings.ots_enabled:
            try:
                proof_path = self.time_stamper.stamp(qr_json.encode("utf-8"))
                if proof_path is not None:
                    signed_qr_data["ots_proof_path"] = str(proof_path)
            except Exception as e:
                _logger.debug("OTS stamping skipped: %s", e)

        # Return the original qr_data but with HMAC fields populated
        qr_data_enhanced = QRData(**signed_qr_data)
        with self._state_lock:
            self._current_qr_data = qr_data_enhanced
            self._last_update_time = time.time()
            self._update_count += 1

        self._notify_callbacks(qr_data_enhanced, qr_image)
        return qr_data_enhanced, qr_image

    def generate_signed_qr(self, user_data: dict | None = None,
                          signing_key_id: str | None = None) -> tuple[QRData, bytes]:
        """
        Generate a QR code with digital signature.

        Args:
            user_data: Optional additional data to include
            signing_key_id: Specific key ID for signing (uses default if None)

        Returns:
            Tuple of (QRData object, QR image as bytes)
        """
        return self.generate_single_qr(
            user_data=user_data,
            sign_data=True,
            encrypt_data=False,
            signing_key_id=signing_key_id,
        )

    def generate_encrypted_qr(self, user_data: dict | None = None,
                             encryption_key_id: str | None = None) -> tuple[QRData, bytes]:
        """
        Generate a QR code with encrypted sensitive data.

        Args:
            user_data: Optional additional data to include
            encryption_key_id: Specific key ID for encryption

        Returns:
            Tuple of (QRData object, QR image as bytes)
        """
        return self.generate_single_qr(
            user_data,
            sign_data=True,
            encrypt_data=True,
            encryption_key_id=encryption_key_id,
        )

    def _apply_cryptographic_enhancements(self, qr_data: QRData,
                                        sign_data: bool = True,
                                        encrypt_data: bool = False,
                                        signing_key_id: str | None = None,
                                        encryption_key_id: str | None = None) -> dict[str, Any]:
        """
        Apply cryptographic enhancements to QR data.

        Order: Sign -> HMAC -> Encrypt (so HMAC covers signed data)

        Args:
            qr_data: Original QR data
            sign_data: Whether to add digital signature
            encrypt_data: Whether to encrypt sensitive fields
            signing_key_id: Optional local key to use for signing
            encryption_key_id: Optional data key to use for encryption

        Returns:
            Enhanced QR data dictionary
        """
        qr_dict = qr_data.__dict__.copy()

        # Step 1: Add digital signature if requested (before HMAC so signature is covered)
        if sign_data:
            key_id_to_use = self._ensure_signing_key(signing_key_id)
            qr_dict = self.signature_manager.create_signed_qr_data(qr_dict, key_id_to_use)

        # Step 2: Add HMAC for integrity checking (always applied, covers signature if present)
        hmac_qr_data = self.hmac_manager.create_integrity_checked_qr(qr_dict)

        # Step 3: Add encryption if requested
        if encrypt_data:
            try:
                if encryption_key_id:
                    encrypted_data = self.encryptor.create_encrypted_qr_data(
                        hmac_qr_data,
                        encryption_key_id,
                    )
                else:
                    encrypted_data = self.encryptor.encrypt_qr_payload(hmac_qr_data)
                return encrypted_data
            except Exception as e:
                # If encryption fails, continue with HMAC-only
                import logging
                logging.getLogger(__name__).warning(
                    "Encryption failed, continuing with HMAC-only: %s", e
                )

        return hmac_qr_data

    def get_current_qr_data(self) -> QRData | None:
        """Get the most recently generated QR data."""
        return self._current_qr_data

    def get_statistics(self) -> dict:
        """Get performance and usage statistics."""
        return {
            "running": self._running,
            "total_updates": self._update_count,
            "sequence_number": self._sequence_number,
            "last_update_time": self._last_update_time,
            "current_qr_data": asdict(self._current_qr_data) if self._current_qr_data else None,
            "time_provider_stats": self.time_provider.get_statistics(),
            "blockchain_stats": self.blockchain_verifier.get_statistics(),
            "identity_stats": self.identity_manager.get_statistics(),
            "crypto_stats": {
                "keys_count": len(self.key_manager.list_keys()),
                "signature_count": sum(key.usage_count for key in self.key_manager.keys_info.values()),
                "encryption_enabled": True,
                "hmac_enabled": True
            }
        }

    def verify_qr_data(self, qr_json: str) -> dict[str, bool]:
        """
        Verify a QR code's data integrity and authenticity.

        Args:
            qr_json: JSON string from QR code

        Returns:
            Dictionary with verification results for each component
        """
        try:
            raw_data = json.loads(qr_json)
            if not isinstance(raw_data, dict):
                raise ValueError("QR data must be a JSON object")

            # Check if data is encrypted
            if raw_data.get('_encrypted_fields'):
                try:
                    decrypted_data = self.encryptor.decrypt_qr_payload(raw_data)
                    qr_data_dict = decrypted_data
                except Exception as e:
                    return {
                        "valid_json": False,
                        "error": f"Decryption failed: {e}",
                        "identity_verified": False,
                        "time_verified": False,
                        "blockchain_verified": False,
                        "signature_verified": False,
                        "hmac_verified": False,
                        "encrypted": True,
                        "valid": False,
                        "trust_mode": "none"
                    }
            else:
                qr_data_dict = raw_data

            # Create QRData object from dictionary. from_dict() silently drops
            # unknown fields so forward-compatible payloads (fields added by
            # newer versions) still verify instead of raising here.
            qr_data = QRData.from_dict(qr_data_dict)

            results = {
                "valid_json": True,
                "identity_verified": False,
                "time_verified": False,
                "blockchain_verified": False,
                "signature_verified": False,
                "hmac_verified": False,
                "encrypted": '_encrypted_fields' in raw_data,
                "replayed": False,
                "valid": False,
                "trust_mode": "none"
            }

            # Replay protection: if enabled, a QR whose nonce was already seen
            # within the replay window is a replay and is rejected.
            replay = self._check_and_record_replay(qr_data)
            if self.config.verification_settings.enable_replay_protection:
                results["replayed"] = replay

            # Verify HMAC integrity (always present)
            try:
                hmac_verified = self.hmac_manager.verify_integrity_checked_qr(qr_data_dict)
            except Exception:
                hmac_verified = False
            results["hmac_verified"] = hmac_verified

            # Verify digital signature if present
            trusted_key = self.trust_store.get_public_key(qr_data.issuer_id, qr_data.signing_key_id)
            if qr_data.digital_signature:
                if trusted_key:
                    signature_verified = self.signature_manager.verify_signed_qr_data(
                        qr_data_dict,
                        public_key_pem=trusted_key.public_key_pem,
                        algorithm=trusted_key.algorithm,
                    )
                    if signature_verified:
                        results["trust_mode"] = "public_signature"
                else:
                    signature_verified = self.signature_manager.verify_signed_qr_data(qr_data_dict)
                    if signature_verified:
                        results["trust_mode"] = "local_signature"
                results["signature_verified"] = signature_verified

            # Verify identity hash
            expected_identity = self.identity_manager.get_identity_hash()
            results["identity_verified"] = (
                qr_data.identity_hash == expected_identity or
                (trusted_key is not None and results["signature_verified"])
            )

            # Verify time is reasonable (within acceptable window)
            qr_time = datetime.fromisoformat(qr_data.timestamp.replace('Z', '+00:00'))
            if qr_time.tzinfo is None:
                qr_time = qr_time.replace(tzinfo=UTC)
            now = datetime.now(UTC)
            time_diff = abs((now - qr_time).total_seconds())
            time_verified = time_diff <= self.config.verification_settings.max_time_drift
            if self.config.verification_settings.require_time_server and not qr_data.time_server_verification:
                time_verified = False
            if qr_data.expires_at:
                expires_at = datetime.fromisoformat(qr_data.expires_at.replace('Z', '+00:00'))
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                time_verified = time_verified and now <= expires_at
            results["time_verified"] = time_verified

            # Verify blockchain hashes (if available)
            if qr_data.blockchain_hashes:
                current_hashes = self.blockchain_verifier.get_blockchain_hashes()
                results["blockchain_verified"] = any(
                    current_hashes.get(chain) == hash_val
                    for chain, hash_val in qr_data.blockchain_hashes.items()
                )

            if not self.config.verification_settings.require_blockchain and not qr_data.blockchain_hashes:
                blockchain_ok = True
            else:
                blockchain_ok = (
                    not self.config.verification_settings.require_blockchain or
                    results["blockchain_verified"]
                )

            authenticity_ok = results["signature_verified"] or results["hmac_verified"]
            results["valid"] = (
                results["valid_json"] and
                results["time_verified"] and
                blockchain_ok and
                authenticity_ok and
                not results["replayed"]
            )

            return results

        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            return {
                "valid_json": False,
                "error": str(e),
                "identity_verified": False,
                "time_verified": False,
                "blockchain_verified": False,
                "signature_verified": False,
                "hmac_verified": False,
                "encrypted": False,
                "replayed": False,
                "valid": False,
                "trust_mode": "none"
            }

    def _update_loop(self) -> None:
        """Main update loop for continuous QR generation."""
        while self._running:
            try:
                start_time = time.time()

                # Check if previous QR expired
                if self._expiry_callback and self._current_qr_data:
                    if self._current_qr_data.expires_at:
                        try:
                            expires = datetime.fromisoformat(
                                self._current_qr_data.expires_at.replace('Z', '+00:00')
                            )
                            if expires.tzinfo is None:
                                expires = expires.replace(tzinfo=UTC)
                            if datetime.now(UTC) >= expires:
                                self._expiry_callback(self._current_qr_data)
                        except Exception:
                            pass  # Don't crash loop on expiry check errors

                # Generate new QR code with user data
                qr_data, qr_image = self.generate_single_qr()

                # Sleep for remaining interval time
                elapsed = time.time() - start_time
                sleep_time = max(0, self.config.update_interval - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                _logger.error(f"Update loop error: {e}")
                # Continue running even if one update fails
                time.sleep(1.0)  # Brief pause before retry

    def __enter__(self):
        """Context manager entry."""
        self.start_live_generation()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_live_generation()

    def _resolve_user_data(self, user_data: dict | None) -> dict | None:
        if user_data is not None or not self._user_data_callback:
            return user_data

        try:
            callback_data = self._user_data_callback()
        except Exception as e:
            _logger.error(f"User data callback error: {e}")
            return None

        if callback_data is None:
            return None
        if isinstance(callback_data, dict):
            return callback_data
        return {"user_text": str(callback_data)}

    def _resolve_issuer_id(self, identity_hash: str) -> str:
        return self.issuer_id or identity_hash

    def _content_hash(self, user_data: dict | None) -> str:
        canonical = json.dumps(user_data or {}, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _check_and_record_replay(self, qr_data: QRData) -> bool:
        """Return ``True`` if ``qr_data`` is a replay within the window.

        A QR is identified by its ``nonce`` (scoped by issuer to avoid
        cross-issuer collisions). First sighting records the nonce and returns
        ``False``; a repeat sighting inside the configured window returns
        ``True``. Stale entries are pruned on each call so the map stays
        bounded. When replay protection is disabled this still tracks nonces,
        but the caller only consults the result when protection is enabled.
        """
        window = self.config.verification_settings.replay_window_seconds
        if window <= 0 or not qr_data.nonce:
            return False

        now = time.time()
        issuer = qr_data.issuer_id or ""
        replay_key = f"{issuer}:{qr_data.nonce}"

        with self._state_lock:
            # Prune entries older than the window.
            stale = [k for k, t in self._seen_nonces.items() if now - t > window]
            for k in stale:
                del self._seen_nonces[k]

            is_replay = replay_key in self._seen_nonces
            if not is_replay:
                self._seen_nonces[replay_key] = now
            return is_replay

    def _expires_at(self, issued_at: datetime) -> str:
        ttl = self.config.security_settings.qr_ttl_seconds
        if ttl is None:
            ttl = int(self.config.verification_settings.max_time_drift)
        return (issued_at + timedelta(seconds=ttl)).isoformat()

    def _ensure_signing_key(self, signing_key_id: str | None = None) -> str:
        candidate = signing_key_id or self.config.security_settings.signing_key_id
        if candidate:
            if self.key_manager.get_keypair(candidate):
                return candidate
            raise ValueError(f"Signing key not found: {candidate}")

        with self._state_lock:
            keys = self.key_manager.list_keys()
            for key_id, key_info in keys.items():
                if key_info.purpose == "qr_signing":
                    return key_id
            if keys:
                return next(iter(keys))

            self.key_manager.generate_keypair(
                algorithm=self.config.security_settings.signature_algorithm
                if hasattr(self.config.security_settings, "signature_algorithm")
                else "rsa",
                key_size=2048,
                purpose="qr_signing"
            )
            return next(iter(self.key_manager.list_keys()))

    def _notify_callbacks(self, qr_data: QRData, qr_image: bytes) -> None:
        for callback in list(self._callbacks):
            try:
                callback(qr_data, qr_image)
            except Exception as e:
                _logger.error(f"Callback error: {e}")
