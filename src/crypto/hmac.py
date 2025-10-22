"""
HMAC Module

HMAC-SHA256 message authentication for QR data integrity verification.
Provides tamper detection for QR codes and data integrity checks.
"""

import hashlib
import hmac
import secrets
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

from .exceptions import HMACError


@dataclass
class HMACKey:
    """HMAC key with metadata."""
    key_id: str
    key_data: bytes
    algorithm: str
    created_at: str
    purpose: str


class HMACManager:
    """
    HMAC-SHA256 message authentication manager.

    Provides HMAC-based integrity verification for QR data and messages,
    ensuring data has not been tampered with during transmission.
    """

    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize HMAC manager.

        Args:
            master_key: Master HMAC key (generates new one if None)
        """
        self.master_key = master_key or secrets.token_bytes(32)
        self.key_id = self._generate_key_id()

    def generate_hmac(self, data: Any, key_id: Optional[str] = None) -> Tuple[bytes, str]:
        """
        Generate HMAC for data integrity verification.

        Args:
            data: Data to create HMAC for (string, dict, or bytes)
            key_id: Optional key identifier for multi-key support

        Returns:
            Tuple of (hmac_bytes, key_id_used)
        """
        # Serialize data consistently
        if isinstance(data, (dict, list)):
            message = self._serialize_data(data)
        elif isinstance(data, str):
            message = data.encode('utf-8')
        elif isinstance(data, bytes):
            message = data
        else:
            message = str(data).encode('utf-8')

        # Use specified key or master key
        hmac_key = self._get_key_by_id(key_id) if key_id else self.master_key

        # Generate HMAC
        hmac_value = hmac.new(
            hmac_key,
            message,
            hashlib.sha256
        ).digest()

        return hmac_value, key_id or self.key_id

    def verify_hmac(self, data: Any, hmac_value: bytes, key_id: Optional[str] = None) -> bool:
        """
        Verify HMAC for data integrity.

        Args:
            data: Original data that was HMAC'd
            hmac_value: HMAC value to verify
            key_id: Key identifier used for HMAC generation

        Returns:
            True if HMAC is valid
        """
        try:
            # Generate expected HMAC
            expected_hmac, _ = self.generate_hmac(data, key_id)

            # Compare HMACs securely
            return hmac.compare_digest(expected_hmac, hmac_value)

        except Exception as e:
            raise HMACError(f"HMAC verification failed: {e}")

    def create_integrity_checked_qr(self, qr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create QR data with HMAC integrity check.

        Args:
            qr_data: QR data dictionary

        Returns:
            QR data with HMAC field
        """
        # Create HMAC for the data
        hmac_value, key_id = self.generate_hmac(qr_data)

        # Add HMAC to data
        integrity_checked_data = qr_data.copy()
        integrity_checked_data['_hmac'] = hmac_value.hex()
        integrity_checked_data['_hmac_key_id'] = key_id
        integrity_checked_data['_hmac_algorithm'] = 'sha256'
        integrity_checked_data['_integrity_checked_at'] = self._get_timestamp()

        return integrity_checked_data

    def verify_integrity_checked_qr(self, qr_data: Dict[str, Any]) -> bool:
        """
        Verify QR code with embedded HMAC.

        Args:
            qr_data: QR data with HMAC fields

        Returns:
            True if HMAC is valid
        """
        if '_hmac' not in qr_data:
            return False

        hmac_hex = qr_data['_hmac']
        if not hmac_hex:
            return False

        key_id = qr_data.get('_hmac_key_id')

        hmac_value = bytes.fromhex(hmac_hex)

        # Remove HMAC fields for verification
        verification_data = qr_data.copy()
        verification_data.pop('_hmac', None)
        verification_data.pop('_hmac_key_id', None)
        verification_data.pop('_hmac_algorithm', None)
        verification_data.pop('_integrity_checked_at', None)
        
        # Also filter out None values to match serialization during creation
        verification_data = {k: v for k, v in verification_data.items() if v is not None}

        return self.verify_hmac(verification_data, hmac_value, key_id)

    def generate_data_key(self, purpose: str = "hmac") -> HMACKey:
        """
        Generate a new HMAC key for data integrity.

        Args:
            purpose: Description of key usage

        Returns:
            HMACKey object
        """
        key_data = secrets.token_bytes(32)
        key_id = self._generate_key_id()

        return HMACKey(
            key_id=key_id,
            key_data=key_data,
            algorithm="hmac-sha256",
            created_at=self._get_timestamp(),
            purpose=purpose
        )

    def _serialize_data(self, data: Any) -> bytes:
        """Consistently serialize data for HMAC."""
        import json

        # Filter to exclude None values for consistent serialization
        if isinstance(data, dict):
            data_filtered = {k: v for k, v in data.items() if v is not None}
        else:
            data_filtered = data

        # Convert to JSON with consistent formatting
        json_str = json.dumps(data_filtered, sort_keys=True, separators=(',', ':'))
        return json_str.encode('utf-8')

    def _generate_key_id(self) -> str:
        """Generate unique key identifier."""
        return secrets.token_hex(16)

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def _get_key_by_id(self, key_id: str) -> bytes:
        """Get HMAC key by ID (placeholder for future key storage)."""
        # For now, only support the master key
        # In production, this would retrieve from secure key storage
        return self.master_key

