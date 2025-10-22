"""
Data Encryption Module

AES-256 encryption and decryption for sensitive QR data and user information.
Provides secure storage and transmission of confidential data.
"""

import os
import json
import base64
import secrets
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, hmac

from .exceptions import EncryptionError


@dataclass
class EncryptionKey:
    """Represents an encryption key with metadata."""
    key_id: str
    key_data: bytes
    algorithm: str
    created_at: str
    purpose: str


class DataEncryptor:
    """
    AES-256 encryption for sensitive data.

    Provides secure encryption/decryption of QR data, user information,
    and other sensitive content with authenticated encryption.
    """

    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize data encryptor.

        Args:
            master_key: Master encryption key (generates new one if None)
        """
        self.master_key = master_key or secrets.token_bytes(32)
        self.key_id = self._generate_key_id()

    def encrypt_sensitive_data(self, data: Any, additional_data: Optional[str] = None) -> bytes:
        """
        Encrypt sensitive data using AES-256-GCM.

        Args:
            data: Data to encrypt (string, dict, or bytes)
            additional_data: Additional authenticated data

        Returns:
            Encrypted data as bytes
        """
        # Serialize data if needed
        if isinstance(data, (dict, list)):
            plaintext = json.dumps(data, separators=(',', ':')).encode('utf-8')
        elif isinstance(data, str):
            plaintext = data.encode('utf-8')
        elif isinstance(data, bytes):
            plaintext = data
        else:
            plaintext = str(data).encode('utf-8')

        # Generate random IV
        iv = secrets.token_bytes(12)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.master_key),
            modes.GCM(iv),
            backend=default_backend()
        )

        encryptor = cipher.encryptor()

        # Add additional authenticated data if provided
        if additional_data:
            encryptor.authenticate_additional_data(additional_data.encode('utf-8'))

        # Encrypt data
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        # Combine IV, tag, and ciphertext
        tag = encryptor.tag
        encrypted_data = iv + tag + ciphertext

        return base64.b64encode(encrypted_data)

    def decrypt_sensitive_data(self, encrypted_data_b64: bytes, additional_data: Optional[str] = None) -> Any:
        """
        Decrypt data encrypted with encrypt_sensitive_data.

        Args:
            encrypted_data_b64: Base64-encoded encrypted data
            additional_data: Additional authenticated data used during encryption

        Returns:
            Decrypted data (original format)
        """
        try:
            # Decode base64
            encrypted_data = base64.b64decode(encrypted_data_b64)

            # Extract components
            iv = encrypted_data[:12]
            tag = encrypted_data[12:28]
            ciphertext = encrypted_data[28:]

            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.master_key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )

            decryptor = cipher.decryptor()

            # Add additional authenticated data if provided
            if additional_data:
                decryptor.authenticate_additional_data(additional_data.encode('utf-8'))

            # Decrypt data
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            # Try to parse as JSON first
            try:
                return json.loads(plaintext.decode('utf-8'))
            except json.JSONDecodeError:
                # Return as string if not JSON
                return plaintext.decode('utf-8')

        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    def encrypt_qr_payload(self, qr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in QR data payload.

        Args:
            qr_data: QR data dictionary

        Returns:
            QR data with sensitive fields encrypted
        """
        encrypted_qr = qr_data.copy()

        # Fields to encrypt
        sensitive_fields = ['user_data', 'identity_hash', 'custom_data']

        for field in sensitive_fields:
            if field in encrypted_qr and encrypted_qr[field] is not None:
                encrypted_qr[field] = self.encrypt_sensitive_data(
                    encrypted_qr[field],
                    additional_data=f"qr_field_{field}"
                ).decode('utf-8')

        # Add encryption metadata
        encrypted_qr['_encrypted_fields'] = sensitive_fields
        encrypted_qr['_encryption_key_id'] = self.key_id
        encrypted_qr['_encrypted_at'] = self._get_timestamp()

        return encrypted_qr

    def decrypt_qr_payload(self, encrypted_qr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in QR data payload.

        Args:
            encrypted_qr_data: QR data with encrypted fields

        Returns:
            QR data with sensitive fields decrypted
        """
        decrypted_qr = encrypted_qr_data.copy()

        # Check if data is encrypted
        if '_encrypted_fields' not in decrypted_qr:
            return decrypted_qr

        encrypted_fields = decrypted_qr.pop('_encrypted_fields')
        key_id = decrypted_qr.pop('_encryption_key_id', None)
        encrypted_at = decrypted_qr.pop('_encrypted_at', None)

        for field in encrypted_fields:
            if field in decrypted_qr and decrypted_qr[field] is not None:
                try:
                    encrypted_value = decrypted_qr[field]
                    if isinstance(encrypted_value, str):
                        decrypted_qr[field] = self.decrypt_sensitive_data(
                            encrypted_value.encode('utf-8'),
                            additional_data=f"qr_field_{field}"
                        )
                except Exception as e:
                    print(f"Warning: Failed to decrypt field {field}: {e}")
                    # Keep encrypted value if decryption fails

        return decrypted_qr

    def generate_data_key(self, purpose: str = "data") -> EncryptionKey:
        """
        Generate a new data encryption key.

        Args:
            purpose: Description of key usage

        Returns:
            EncryptionKey object
        """
        key_data = secrets.token_bytes(32)
        key_id = self._generate_key_id()

        return EncryptionKey(
            key_id=key_id,
            key_data=key_data,
            algorithm="aes-256-gcm",
            created_at=self._get_timestamp(),
            purpose=purpose
        )

    def create_encrypted_qr_data(self, qr_data: Dict[str, Any], key_id: str) -> Dict[str, Any]:
        """
        Create QR data with encrypted sensitive information.

        Args:
            qr_data: Original QR data
            key_id: Encryption key identifier

        Returns:
            QR data with encrypted fields
        """
        # Get encryption key
        key = self._get_key_by_id(key_id)
        if not key:
            raise EncryptionError(f"Encryption key not found: {key_id}")

        # Temporarily use this key for encryption
        original_key = self.master_key
        self.master_key = key.key_data

        try:
            encrypted_data = self.encrypt_qr_payload(qr_data)
            encrypted_data['_data_key_id'] = key_id
            return encrypted_data
        finally:
            # Restore original key
            self.master_key = original_key

    def decrypt_encrypted_qr_data(self, encrypted_qr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt QR data with encrypted sensitive information.

        Args:
            encrypted_qr_data: QR data with encrypted fields

        Returns:
            QR data with decrypted fields
        """
        key_id = encrypted_qr_data.get('_data_key_id')
        if not key_id:
            return encrypted_qr_data

        # Get decryption key
        key = self._get_key_by_id(key_id)
        if not key:
            raise EncryptionError(f"Decryption key not found: {key_id}")

        # Temporarily use this key for decryption
        original_key = self.master_key
        self.master_key = key.key_data

        try:
            return self.decrypt_qr_payload(encrypted_qr_data)
        finally:
            # Restore original key
            self.master_key = original_key

    def _generate_key_id(self) -> str:
        """Generate unique key identifier."""
        return secrets.token_hex(16)

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _get_key_by_id(self, key_id: str) -> Optional[EncryptionKey]:
        """Get encryption key by ID (placeholder for future key storage)."""
        # For now, only support the master key
        # In production, this would retrieve from secure key storage
        return EncryptionKey(
            key_id=key_id,
            key_data=self.master_key,
            algorithm="aes-256-gcm",
            created_at=self._get_timestamp(),
            purpose="master"
        )

