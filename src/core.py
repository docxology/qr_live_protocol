"""
Core QRLP (QR Live Protocol) implementation.

This module provides the main QRLiveProtocol class that coordinates all
components to generate live, verifiable QR codes with time and identity information.
"""

import json
import time
import hashlib
import threading
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict, fields

from .qr_generator import QRGenerator
from .time_provider import TimeProvider
from .blockchain_verifier import BlockchainVerifier
from .identity_manager import IdentityManager
from .config import QRLPConfig
from .crypto import KeyManager, QRSignatureManager, DataEncryptor, HMACManager
from .trust import TrustStore

_logger = logging.getLogger("qrlp.core")



@dataclass
class QRData:
    """Structure for QR code data payload."""
    timestamp: str
    identity_hash: str
    blockchain_hashes: Dict[str, str]
    time_server_verification: Dict[str, str]
    user_data: Optional[Dict] = None
    sequence_number: int = 0
    issuer_id: Optional[str] = None
    event_id: Optional[str] = None
    content_hash: Optional[str] = None
    expires_at: Optional[str] = None
    nonce: Optional[str] = None

    # Cryptographic enhancement fields
    digital_signature: Optional[str] = None
    signing_key_id: Optional[str] = None
    signature_algorithm: Optional[str] = None
    _hmac: Optional[str] = None
    _hmac_key_id: Optional[str] = None
    _hmac_algorithm: Optional[str] = None
    _integrity_checked_at: Optional[str] = None
    _encrypted_fields: Optional[List[str]] = None
    _encryption_key_id: Optional[str] = None
    _data_key_id: Optional[str] = None
    _encrypted_at: Optional[str] = None

    def to_json(self) -> str:
        """Convert to JSON string for QR encoding."""
        # Convert to dict and filter out None values for deterministic serialization
        data_dict = asdict(self)
        # Keep only non-None values or values that are explicitly needed
        filtered_dict = {k: v for k, v in data_dict.items() if v is not None}
        return json.dumps(filtered_dict, separators=(',', ':'))

    def to_dict(self) -> Dict[str, Any]:
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
    def from_json(cls, json_str: str) -> 'QRData':
        """Create QRData from JSON string.

        Unknown fields are silently ignored so that forward-compatible
        QR payloads (with newly added fields) do not break older verifiers.
        """
        data = json.loads(json_str)
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
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
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
        config: Optional[QRLPConfig] = None,
        key_manager: Optional[KeyManager] = None,
        signature_manager: Optional[QRSignatureManager] = None,
        encryptor: Optional[DataEncryptor] = None,
        hmac_manager: Optional[HMACManager] = None,
        trust_store: Optional[TrustStore] = None,
        issuer_id: Optional[str] = None,
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

        # Initialize cryptographic components
        self._key_manager: Optional[KeyManager] = None
        self.key_manager = key_manager or KeyManager(self.config.security_settings.key_dir)
        self.signature_manager = signature_manager or QRSignatureManager(self.key_manager)
        self.signature_manager.key_manager = self.key_manager
        self.encryptor = encryptor or DataEncryptor()
        self.hmac_manager = hmac_manager or HMACManager()
        self.trust_store = trust_store or TrustStore()
        self.issuer_id = issuer_id or self.config.security_settings.issuer_id

        # State management
        self._running = False
        self._current_qr_data: Optional[QRData] = None
        self._sequence_number = 0
        self._state_lock = threading.Lock()
        self._update_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[QRData, bytes], None]] = []

        # User data callback for external input
        self._user_data_callback: Optional[Callable[[], Optional[str]]] = None

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

    def set_user_data_callback(self, callback: Callable[[], Optional[str]]) -> None:
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

    def generate_single_qr(self, user_data: Optional[Dict] = None,
                          sign_data: Optional[bool] = None, encrypt_data: bool = False,
                          signing_key_id: Optional[str] = None,
                          encryption_key_id: Optional[str] = None) -> tuple[QRData, bytes]:
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

        # Return the original qr_data but with HMAC fields populated
        qr_data_enhanced = QRData(**signed_qr_data)
        with self._state_lock:
            self._current_qr_data = qr_data_enhanced
            self._last_update_time = time.time()
            self._update_count += 1

        self._notify_callbacks(qr_data_enhanced, qr_image)
        return qr_data_enhanced, qr_image

    def generate_signed_qr(self, user_data: Optional[Dict] = None,
                          signing_key_id: str = None) -> tuple[QRData, bytes]:
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

    def generate_encrypted_qr(self, user_data: Optional[Dict] = None,
                             encryption_key_id: str = None) -> tuple[QRData, bytes]:
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
                                        signing_key_id: Optional[str] = None,
                                        encryption_key_id: Optional[str] = None) -> Dict[str, Any]:
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
            signing_key_id = self._ensure_signing_key(signing_key_id)
            qr_dict = self.signature_manager.create_signed_qr_data(qr_dict, signing_key_id)

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

    def get_current_qr_data(self) -> Optional[QRData]:
        """Get the most recently generated QR data."""
        return self._current_qr_data

    def get_statistics(self) -> Dict:
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

    def verify_qr_data(self, qr_json: str) -> Dict[str, bool]:
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
            if '_encrypted_fields' in raw_data and raw_data['_encrypted_fields']:
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

            # Create QRData object from dictionary
            qr_data = QRData(**qr_data_dict)

            results = {
                "valid_json": True,
                "identity_verified": False,
                "time_verified": False,
                "blockchain_verified": False,
                "signature_verified": False,
                "hmac_verified": False,
                "encrypted": '_encrypted_fields' in raw_data,
                "valid": False,
                "trust_mode": "none"
            }

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
                qr_time = qr_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            time_diff = abs((now - qr_time).total_seconds())
            time_verified = time_diff <= self.config.verification_settings.max_time_drift
            if self.config.verification_settings.require_time_server and not qr_data.time_server_verification:
                time_verified = False
            if qr_data.expires_at:
                expires_at = datetime.fromisoformat(qr_data.expires_at.replace('Z', '+00:00'))
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
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
                authenticity_ok
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
                "valid": False,
                "trust_mode": "none"
            }

    def _update_loop(self) -> None:
        """Main update loop for continuous QR generation."""
        while self._running:
            try:
                start_time = time.time()

                # Generate new QR code with user data
                qr_data, qr_image = self.generate_single_qr()

                # Update statistics
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

    def _resolve_user_data(self, user_data: Optional[Dict]) -> Optional[Dict]:
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

    def _content_hash(self, user_data: Optional[Dict]) -> str:
        canonical = json.dumps(user_data or {}, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _expires_at(self, issued_at: datetime) -> str:
        ttl = self.config.security_settings.qr_ttl_seconds
        if ttl is None:
            ttl = int(self.config.verification_settings.max_time_drift)
        return (issued_at + timedelta(seconds=ttl)).isoformat()

    def _ensure_signing_key(self, signing_key_id: Optional[str] = None) -> str:
        candidate = signing_key_id or self.config.security_settings.signing_key_id
        if candidate:
            if self.key_manager.get_keypair(candidate):
                return candidate
            raise ValueError(f"Signing key not found: {candidate}")

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