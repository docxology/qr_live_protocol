"""
Core QRLP (QR Live Protocol) implementation.

This module provides the main QRLiveProtocol class that coordinates all
components to generate live, verifiable QR codes with time and identity information.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .blockchain_verifier import BlockchainVerifier
from .config import QRLPConfig
from .crypto import DataEncryptor, EncryptionError, HMACError, HMACManager, KeyManager, QRSignatureManager
from .identity_manager import IdentityManager
from .qr_generator import QRGenerator
from .serializer import QRSerializer
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
        """Serialize the wire payload. The local proof path is out of band."""
        data = self.to_dict()
        data.pop("ots_proof_path", None)
        return QRSerializer.serialize(data, filter_none=False)

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
        return cls.from_dict(QRSerializer.deserialize(json_str))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QRData:
        """Create QRData from a dictionary.

        Inverse of ``to_dict()``. Unknown fields are silently ignored
        for forward compatibility, same as ``from_json()``.
        """
        if not isinstance(data, dict):
            raise ValueError("QR data must be a JSON object")
        known_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class VerificationResult:
    """Structured result of QR data verification.

    The public ``verify_qr_data`` method returns this result as a dictionary.
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
    replayed: bool = False

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
        encryption_key = self.config.security_settings.get_encryption_key() if encryptor is None else None

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
            timeout=self.config.time_settings.timeout,
        )

        # Initialize cryptographic components
        self._key_manager: KeyManager | None = None
        self.key_manager = key_manager or KeyManager(self.config.security_settings.key_dir)
        self.signature_manager = signature_manager or QRSignatureManager(self.key_manager)
        self.signature_manager.key_manager = self.key_manager
        self.encryptor = encryptor if encryptor is not None else DataEncryptor(encryption_key)
        self.hmac_manager = hmac_manager or HMACManager()
        self.trust_store = trust_store if trust_store is not None else TrustStore()
        self.issuer_id = issuer_id or self.config.security_settings.issuer_id

        # State management
        self._running = False
        self._current_qr_data: QRData | None = None
        self._sequence_number = 0
        self._state_lock = threading.Lock()
        self._live_stop = threading.Event()
        self._update_thread: threading.Thread | None = None
        self._callbacks: list[Callable[[QRData, bytes], None]] = []

        # User data callback for external input
        self._user_data_callback: Callable[[], dict[str, Any] | str | None] | None = None

        # Expiry notification callback
        self._expiry_callback: Callable[[QRData], None] | None = None

        # Replay-protection state: nonce -> timestamp of first sighting, pruned
        # on each use. Only consulted when replay protection is enabled.
        self._seen_nonces: OrderedDict[tuple[str, str], float] = OrderedDict()

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

    def set_user_data_callback(self, callback: Callable[[], dict[str, Any] | str | None]) -> None:
        """
        Set callback function to get user data for QR generation.

        Args:
            callback: Function that returns metadata, operator text, or None
        """
        self._user_data_callback = callback

    def start_live_generation(self) -> None:
        """Start continuous QR code generation in background thread."""
        with self._state_lock:
            if self._running:
                return
            if self._update_thread is not None:
                raise RuntimeError("Previous QR generation worker is still stopping")
            self._live_stop.clear()
            thread = threading.Thread(
                target=self._update_loop, daemon=True, name="QRLP-Update-Thread",
            )
            thread.start()
            self._update_thread = thread
            self._running = True

    def stop_live_generation(self) -> None:
        """Stop continuous QR code generation."""
        with self._state_lock:
            thread = self._update_thread
            self._running = False
            self._live_stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def generate_single_qr(self, user_data: dict | None = None,
                          sign_data: bool | None = None, encrypt_data: bool | None = None,
                          signing_key_id: str | None = None,
                          encryption_key_id: str | None = None, *,
                          style: str | None = None,
                          include_text: bool = False) -> tuple[QRData, bytes]:
        """
        Generate a single QR code with current time and verification data.

        Args:
            user_data: Explicit metadata. When omitted, use configured live metadata and callback data.
            sign_data: Whether to sign the QR data (None uses configuration)
            encrypt_data: Whether to encrypt sensitive fields (None uses configuration)
            signing_key_id: Optional local key to use for signing
            encryption_key_id: Optional data key to use for encryption
            style: Optional QR image style
            include_text: Add a human-readable label below the QR code

        Returns:
            Tuple of (QRData object, QR image as bytes)
        """
        if sign_data is None:
            sign_data = self.config.security_settings.sign_qr_data
        if encrypt_data is None:
            encrypt_data = self.config.security_settings.encrypt_qr_data

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

        # Use the same wire bytes for the image, exports, and timestamp commitment.
        qr_data_enhanced = QRData(**signed_qr_data)
        qr_json = qr_data_enhanced.to_json()
        if style is None:
            qr_image = self.qr_generator.generate_qr_image(qr_json)
        else:
            qr_image = self.qr_generator.generate_qr_image(qr_json, style=style)
        if include_text:
            qr_image = self.qr_generator.add_text_overlay(qr_image, qr_data_enhanced.to_dict())

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
                    qr_data_enhanced.ots_proof_path = str(proof_path)
            except Exception as e:
                _logger.debug("OTS stamping skipped: %s", e)

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
            if encryption_key_id is not None:
                return self.encryptor.create_encrypted_qr_data(
                    hmac_qr_data,
                    encryption_key_id,
                )
            return self.encryptor.encrypt_qr_payload(hmac_qr_data)

        return hmac_qr_data

    def get_current_qr_data(self) -> QRData | None:
        """Get the most recently generated QR data."""
        return self._current_qr_data

    def get_statistics(self) -> dict:
        """Get performance and usage statistics."""
        keys = self.key_manager.list_keys()
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
                "keys_count": len(keys),
                "signature_count": sum(key.usage_count for key in keys.values()),
                "encryption_enabled": True,
                "hmac_enabled": True
            }
        }

    def verify_qr_data(self, qr_json: str) -> dict[str, Any]:
        """Verify the QR wire payload and return diagnostics for each layer."""
        result = VerificationResult(valid_json=False)
        try:
            raw_data = QRSerializer.deserialize(qr_json)
            if not isinstance(raw_data, dict):
                raise ValueError("QR data must be a JSON object")

            # Older callers serialized every dataclass field, including
            # a null encryption marker for plaintext payloads.
            result.encrypted = raw_data.get("_encrypted_fields") is not None
            payload = self.encryptor.decrypt_qr_payload(raw_data) if result.encrypted else raw_data
            qr_data = QRData.from_dict(payload)
            self._validate_verification_fields(qr_data)
            result.error = self._payload_time_error(qr_data)
            result.time_verified = result.error is None
        except EncryptionError:
            result.error = "Decryption failed"
            return result.to_dict()
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            result.error = str(error)
            return result.to_dict()

        result.valid_json = True
        # Retain unknown fields when checking authenticity. Only the typed
        # view of the payload drops fields from newer protocol versions.
        try:
            result.hmac_verified = self.hmac_manager.verify_integrity_checked_qr(payload)
        except (HMACError, TypeError, ValueError):
            pass
        if result.hmac_verified:
            result.trust_mode = "local_hmac"

        if qr_data.digital_signature:
            trusted_key = self.trust_store.get_public_key(qr_data.issuer_id, qr_data.signing_key_id)
            if trusted_key is None:
                result.signature_verified = self.signature_manager.verify_signed_qr_data(payload)
            else:
                result.signature_verified = self.signature_manager.verify_signed_qr_data(
                    payload,
                    public_key_pem=trusted_key.public_key_pem,
                    algorithm=trusted_key.algorithm,
                )
            if result.signature_verified:
                result.trust_mode = "public_signature" if trusted_key is not None else "local_signature"

        result.identity_verified = (
            qr_data.identity_hash == self.identity_manager.get_identity_hash()
            or result.trust_mode == "public_signature"
        )
        authenticated = result.signature_verified or result.hmac_verified
        # Looking up live chain state is a network operation. Only consider
        # hashes supplied by an authenticated, timely payload.
        if authenticated and result.time_verified and qr_data.blockchain_hashes:
            current_hashes = self.blockchain_verifier.get_blockchain_hashes()
            result.blockchain_verified = any(
                current_hashes.get(chain) == hash_val
                for chain, hash_val in qr_data.blockchain_hashes.items()
            )

        settings = self.config.verification_settings
        result.valid = (
            authenticated and result.time_verified
            and (not settings.require_blockchain or result.blockchain_verified)
        )
        if result.valid and settings.enable_replay_protection:
            window = settings.replay_window_seconds
            if type(window) is not int or window <= 0:
                result.valid = False
                result.error = "Replay protection requires a positive integer window"
            elif not qr_data.nonce:
                result.valid = False
                result.error = "Replay protection requires a nonce"
            else:
                result.replayed = self._check_and_record_replay(qr_data.issuer_id, qr_data.nonce, window)
                result.valid = not result.replayed

        return result.to_dict()

    @staticmethod
    def _validate_verification_fields(qr_data: QRData) -> None:
        for name in ("timestamp", "identity_hash"):
            if not isinstance(getattr(qr_data, name), str):
                raise ValueError(f"{name} must be a string")
        for name in ("issuer_id", "nonce", "expires_at", "signing_key_id", "digital_signature",
                     "signature_algorithm"):
            value = getattr(qr_data, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string")
        if not isinstance(qr_data.blockchain_hashes, dict) or any(
            not isinstance(value, str) for value in qr_data.blockchain_hashes.values()
        ):
            raise ValueError("blockchain_hashes must be an object with string values")
        if not isinstance(qr_data.time_server_verification, dict):
            raise ValueError("time_server_verification must be an object")

    def _payload_time_error(self, qr_data: QRData) -> str | None:
        settings = self.config.verification_settings
        now = datetime.now(UTC)
        issued_at = self._parse_payload_time(qr_data.timestamp)
        if qr_data.expires_at is not None and now > self._parse_payload_time(qr_data.expires_at):
            return "QR payload has expired"
        within_drift = abs((now - issued_at).total_seconds()) <= settings.max_time_drift
        if not within_drift:
            return "QR timestamp is outside the allowed clock drift"
        if settings.require_time_server and not qr_data.time_server_verification:
            return "QR payload lacks required time-source observations"
        return None

    @staticmethod
    def _parse_payload_time(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)

    def _update_loop(self) -> None:
        """Main update loop for continuous QR generation."""
        last_expiry: QRData | None = None
        try:
            while not self._live_stop.is_set():
                started = time.monotonic()
                current = self.get_current_qr_data()
                callback = self._expiry_callback
                if callback and current and current is not last_expiry and current.expires_at:
                    try:
                        if datetime.now(UTC) >= self._parse_payload_time(current.expires_at):
                            last_expiry = current
                            callback(current)
                    except Exception:
                        _logger.exception("QR expiry callback failed")

                if self._live_stop.is_set():
                    break
                try:
                    self.generate_single_qr()
                except Exception:
                    _logger.exception("QR update failed")
                    self._live_stop.wait(1.0)
                else:
                    elapsed = time.monotonic() - started
                    self._live_stop.wait(max(0, self.config.update_interval - elapsed))
        finally:
            with self._state_lock:
                self._update_thread = None
                self._running = False

    def __enter__(self):
        """Context manager entry."""
        self.start_live_generation()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_live_generation()

    def _resolve_user_data(self, user_data: dict | None) -> dict | None:
        if user_data is not None:
            return user_data

        configured = self.config.get_live_user_data()
        if self._user_data_callback is None:
            return configured
        try:
            callback_data = self._user_data_callback()
        except Exception as e:
            _logger.error(f"User data callback error: {e}")
            return configured

        if callback_data is None:
            return configured
        dynamic = callback_data if isinstance(callback_data, dict) else {"user_text": str(callback_data)}
        return {**(configured or {}), **dynamic}

    def _resolve_issuer_id(self, identity_hash: str) -> str:
        return self.issuer_id or identity_hash

    def _content_hash(self, user_data: dict | None) -> str:
        canonical = QRSerializer.serialize(user_data or {}, filter_none=False, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _check_and_record_replay(self, issuer_id: str | None, nonce: str, window: int) -> bool:
        """Return ``True`` if the nonce is a replay within the window.

        A QR is identified by its ``nonce`` (scoped by issuer to avoid
        cross-issuer collisions). First sighting records the nonce and returns
        ``False``; a repeat sighting inside the configured window returns
        ``True``. Only accepted QR payloads reach this method.
        """
        replay_key = (issuer_id or "", nonce)
        with self._state_lock:
            now = time.monotonic()
            # Entries are ordered by first accepted use. Prune the stale prefix.
            while self._seen_nonces:
                oldest = next(iter(self._seen_nonces))
                if now - self._seen_nonces[oldest] <= window:
                    break
                self._seen_nonces.popitem(last=False)

            if replay_key in self._seen_nonces:
                return True
            self._seen_nonces[replay_key] = now
            return False

    def _expires_at(self, issued_at: datetime) -> str:
        ttl = self.config.security_settings.qr_ttl_seconds
        if ttl is None:
            ttl = int(self.config.verification_settings.max_time_drift)
        return (issued_at + timedelta(seconds=ttl)).isoformat()

    def _ensure_signing_key(self, signing_key_id: str | None = None) -> str:
        candidate = signing_key_id or self.config.security_settings.signing_key_id
        if candidate:
            if self.key_manager.get_public_key(candidate):
                return candidate
            raise ValueError(f"Signing key not found: {candidate}")

        with self._state_lock:
            keys = self.key_manager.list_keys()
            algorithm = self.config.security_settings.signature_algorithm
            compatible = {
                key_id: info for key_id, info in keys.items() if info.algorithm.lower() == algorithm
            }
            for key_id, key_info in compatible.items():
                if key_info.purpose == "qr_signing" and self.key_manager.get_public_key(key_id):
                    return key_id
            for key_id in compatible:
                if self.key_manager.get_public_key(key_id):
                    return key_id

            self.key_manager.generate_keypair(
                algorithm=algorithm,
                key_size=256 if algorithm == "ecdsa" else 2048,
                purpose="qr_signing"
            )
            return next(key_id for key_id in self.key_manager.list_keys() if key_id not in keys)

    def _notify_callbacks(self, qr_data: QRData, qr_image: bytes) -> None:
        for callback in list(self._callbacks):
            try:
                callback(qr_data, qr_image)
            except Exception as e:
                _logger.error(f"Callback error: {e}")
