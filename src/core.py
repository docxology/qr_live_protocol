"""
Core QRLP (QR Live Protocol) implementation.

This module provides the main QRLiveProtocol class that coordinates all 
components to generate live, verifiable QR codes with time and identity information.
"""

import json
import time
import hashlib
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Callable, Any
from dataclasses import dataclass, asdict

from .qr_generator import QRGenerator
from .time_provider import TimeProvider
from .blockchain_verifier import BlockchainVerifier
from .identity_manager import IdentityManager
from .config import QRLPConfig
from .crypto import KeyManager, QRSignatureManager, DataEncryptor, HMACManager


@dataclass
class QRData:
    """Structure for QR code data payload."""
    timestamp: str
    identity_hash: str
    blockchain_hashes: Dict[str, str]
    time_server_verification: Dict[str, str]
    user_data: Optional[Dict] = None
    sequence_number: int = 0

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
    
    @classmethod
    def from_json(cls, json_str: str) -> 'QRData':
        """Create QRData from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


class QRLiveProtocol:
    """
    Main QR Live Protocol coordinator.
    
    Orchestrates time providers, blockchain verifiers, identity management,
    and QR generation to create live, verifiable QR codes for streaming.
    """
    
    def __init__(self, config: Optional[QRLPConfig] = None):
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
        self.key_manager = KeyManager()
        self.signature_manager = QRSignatureManager(self.key_manager)
        self.encryptor = DataEncryptor()
        self.hmac_manager = HMACManager()
        
        # State management
        self._running = False
        self._current_qr_data: Optional[QRData] = None
        self._sequence_number = 0
        self._update_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[QRData, bytes], None]] = []
        
        # User data callback for external input
        self._user_data_callback: Optional[Callable[[], Optional[str]]] = None
        
        # Performance tracking
        self._last_update_time = 0
        self._update_count = 0
        
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
                          sign_data: bool = True, encrypt_data: bool = False) -> tuple[QRData, bytes]:
        """
        Generate a single QR code with current time and verification data.

        Args:
            user_data: Optional additional data to include in QR
            sign_data: Whether to digitally sign the QR data
            encrypt_data: Whether to encrypt sensitive fields

        Returns:
            Tuple of (QRData object, QR image as bytes)
        """
        # Gather all verification data
        current_time = self.time_provider.get_current_time()
        identity_hash = self.identity_manager.get_identity_hash()
        blockchain_hashes = self.blockchain_verifier.get_blockchain_hashes()
        time_verification = self.time_provider.get_time_server_verification()

        # Increment sequence number for this QR
        self._sequence_number += 1

        # Create QR data payload
        qr_data = QRData(
            timestamp=current_time.isoformat(),
            identity_hash=identity_hash,
            blockchain_hashes=blockchain_hashes,
            time_server_verification=time_verification,
            user_data=user_data,
            sequence_number=self._sequence_number
        )

        # Apply cryptographic enhancements (always apply HMAC)
        signed_qr_data = self._apply_cryptographic_enhancements(qr_data, sign_data, encrypt_data)

        # Generate QR code image
        qr_json = json.dumps(signed_qr_data, separators=(',', ':'))
        qr_image = self.qr_generator.generate_qr_image(qr_json)

        # Store enhanced data
        self._current_qr_data = QRData(**signed_qr_data)

        # Return the original qr_data but with HMAC fields populated
        qr_data_enhanced = QRData(**signed_qr_data)
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
        # Generate base QR data
        qr_data, qr_image = self.generate_single_qr(user_data, sign_data=False)

        # Sign the QR data
        if signing_key_id is None:
            # Use the first available key or generate one
            keys = self.key_manager.list_keys()
            if keys:
                signing_key_id = list(keys.keys())[0]
            else:
                # Generate a new key for signing
                public_key, private_key = self.key_manager.generate_keypair(
                    algorithm="rsa", key_size=2048, purpose="qr_signing"
                )
                signing_key_id = list(self.key_manager.list_keys().keys())[0]

        signed_qr_data = self.signature_manager.create_signed_qr_data(qr_data.__dict__, signing_key_id)

        # Update QR data with signature info
        qr_data.__dict__.update(signed_qr_data)

        # Regenerate QR image with signed data
        qr_json = json.dumps(signed_qr_data, separators=(',', ':'))
        qr_image = self.qr_generator.generate_qr_image(qr_json)

        return qr_data, qr_image

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
        # Generate base QR data
        qr_data, qr_image = self.generate_single_qr(user_data, encrypt_data=False)

        # Encrypt sensitive fields
        if encryption_key_id is None:
            encryption_key_id = self.encryptor.key_id

        encrypted_qr_data = self.encryptor.create_encrypted_qr_data(qr_data.__dict__, encryption_key_id)

        # Update QR data with encrypted info
        qr_data.__dict__.update(encrypted_qr_data)

        # Regenerate QR image with encrypted data
        qr_json = json.dumps(encrypted_qr_data, separators=(',', ':'))
        qr_image = self.qr_generator.generate_qr_image(qr_json)

        return qr_data, qr_image

    def _apply_cryptographic_enhancements(self, qr_data: QRData,
                                        sign_data: bool = True,
                                        encrypt_data: bool = False) -> Dict[str, Any]:
        """
        Apply cryptographic enhancements to QR data.

        Order: Sign -> HMAC -> Encrypt (so HMAC covers signed data)

        Args:
            qr_data: Original QR data
            sign_data: Whether to add digital signature
            encrypt_data: Whether to encrypt sensitive fields

        Returns:
            Enhanced QR data dictionary
        """
        qr_dict = qr_data.__dict__.copy()

        # Step 1: Add digital signature if requested (before HMAC so signature is covered)
        if sign_data:
            try:
                keys = self.key_manager.list_keys()
                if keys:
                    signing_key_id = list(keys.keys())[0]
                    signed_data = self.signature_manager.create_signed_qr_data(qr_dict, signing_key_id)
                    qr_dict = signed_data
            except Exception as e:
                print(f"Warning: Digital signature failed: {e}, continuing with HMAC-only")

        # Step 2: Add HMAC for integrity checking (always applied, covers signature if present)
        hmac_qr_data = self.hmac_manager.create_integrity_checked_qr(qr_dict)

        # Step 3: Add encryption if requested
        if encrypt_data:
            try:
                encrypted_data = self.encryptor.encrypt_qr_payload(hmac_qr_data)
                return encrypted_data
            except Exception as e:
                # If encryption fails, continue with HMAC-only
                print(f"Warning: Encryption failed: {e}, continuing with HMAC-only")

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
                "signature_count": self.signature_manager.key_manager.keys_info.get(list(self.key_manager.keys_info.keys())[0]).usage_count if self.key_manager.keys_info else 0,
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
            # First parse as raw JSON to check for encryption
            raw_data = json.loads(qr_json)

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
                        "hmac_verified": False
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
                "encrypted": '_encrypted_fields' in raw_data
            }

            # Verify HMAC integrity (always present)
            hmac_verified = self.hmac_manager.verify_integrity_checked_qr(qr_data_dict)
            results["hmac_verified"] = hmac_verified

            # Verify digital signature if present
            if 'digital_signature' in qr_data_dict:
                signature_verified = self.signature_manager.verify_signed_qr_data(qr_data_dict)
                results["signature_verified"] = signature_verified

            # Verify identity hash
            expected_identity = self.identity_manager.get_identity_hash()
            results["identity_verified"] = qr_data.identity_hash == expected_identity

            # Verify time is reasonable (within acceptable window)
            qr_time = datetime.fromisoformat(qr_data.timestamp.replace('Z', '+00:00'))
            time_diff = abs((datetime.now(timezone.utc) - qr_time).total_seconds())
            results["time_verified"] = time_diff <= self.config.verification_settings.max_time_drift

            # Verify blockchain hashes (if available)
            if qr_data.blockchain_hashes:
                current_hashes = self.blockchain_verifier.get_blockchain_hashes()
                results["blockchain_verified"] = any(
                    current_hashes.get(chain) == hash_val
                    for chain, hash_val in qr_data.blockchain_hashes.items()
                )

            return results

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return {
                "valid_json": False,
                "error": str(e),
                "identity_verified": False,
                "time_verified": False,
                "blockchain_verified": False,
                "signature_verified": False,
                "hmac_verified": False,
                "encrypted": False
            }
    
    def _update_loop(self) -> None:
        """Main update loop for continuous QR generation."""
        while self._running:
            try:
                start_time = time.time()
                
                # Get user data from callback if available
                user_data = None
                if self._user_data_callback:
                    try:
                        user_text = self._user_data_callback()
                        if user_text:
                            user_data = {"user_text": user_text}
                    except Exception as e:
                        print(f"User data callback error: {e}")
                
                # Generate new QR code with user data
                qr_data, qr_image = self.generate_single_qr(user_data)
                
                # Notify all callbacks
                for callback in self._callbacks:
                    try:
                        callback(qr_data, qr_image)
                    except Exception as e:
                        # Log error but continue with other callbacks
                        print(f"Callback error: {e}")
                
                # Update statistics
                self._last_update_time = start_time
                self._update_count += 1
                
                # Sleep for remaining interval time
                elapsed = time.time() - start_time
                sleep_time = max(0, self.config.update_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"Update loop error: {e}")
                # Continue running even if one update fails
                time.sleep(1.0)  # Brief pause before retry
    
    def __enter__(self):
        """Context manager entry."""
        self.start_live_generation()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_live_generation() 