"""
Data Encryption Module

AES-256 encryption and decryption for sensitive QR data and user information.
Provides secure storage and transmission of confidential data.
"""

import base64
import json
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..serializer import QRSerializer
from .exceptions import EncryptionError

_SENSITIVE_FIELDS = ("user_data", "identity_hash", "custom_data")
_NONCE_SIZE = 12
_TAG_SIZE = 16


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

    def __init__(self, master_key: bytes | None = None):
        """
        Initialize data encryptor.

        Args:
            master_key: Master encryption key (generates new one if None)
        """
        self.master_key = master_key or secrets.token_bytes(32)
        self.key_id = self._generate_key_id()
        self.key_store: dict[str, bytes] = {}
        self._lock = threading.RLock()

    def encrypt_sensitive_data(self, data: Any, additional_data: str | None = None) -> bytes:
        """Encrypt data with the current master key, returning Base64 bytes."""
        with self._lock:
            key = self.master_key
        return self._encrypt(data, key, additional_data)

    def decrypt_sensitive_data(self, encrypted_data_b64: bytes, additional_data: str | None = None) -> Any:
        """Decrypt Base64 bytes encrypted with the current master key."""
        with self._lock:
            key = self.master_key
        return self._decode_plaintext(self._decrypt(encrypted_data_b64, key, additional_data))

    @staticmethod
    def _encrypt(data: Any, key: bytes, additional_data: str | None) -> bytes:
        if isinstance(data, (dict, list)):
            plaintext = QRSerializer.serialize(data, filter_none=False).encode("utf-8")
        elif isinstance(data, bytes):
            plaintext = data
        else:
            plaintext = str(data).encode("utf-8")

        iv = secrets.token_bytes(_NONCE_SIZE)
        aad = additional_data.encode("utf-8") if additional_data else None
        try:
            ciphertext_and_tag = AESGCM(key).encrypt(iv, plaintext, aad)
        except (ValueError, OverflowError) as error:
            raise EncryptionError("Encryption failed") from error
        # QRLP encodes IV + tag + ciphertext, unlike AESGCM's return value.
        ciphertext, tag = ciphertext_and_tag[:-_TAG_SIZE], ciphertext_and_tag[-_TAG_SIZE:]
        return base64.b64encode(iv + tag + ciphertext)

    @staticmethod
    def _decrypt(encrypted: str | bytes, key: bytes, additional_data: str | None) -> str:
        try:
            wire = base64.b64decode(encrypted, validate=True)
            if len(wire) < _NONCE_SIZE + _TAG_SIZE:
                raise ValueError("Encrypted data is truncated")
            iv = wire[:_NONCE_SIZE]
            tag = wire[_NONCE_SIZE:_NONCE_SIZE + _TAG_SIZE]
            ciphertext = wire[_NONCE_SIZE + _TAG_SIZE:]
            aad = additional_data.encode("utf-8") if additional_data else None
            return AESGCM(key).decrypt(iv, ciphertext + tag, aad).decode("utf-8")
        except (InvalidTag, TypeError, ValueError) as error:
            raise EncryptionError("Decryption failed") from error

    @staticmethod
    def _decode_plaintext(plaintext: str) -> Any:
        try:
            return QRSerializer.deserialize(plaintext)
        except json.JSONDecodeError:
            return plaintext

    def encrypt_qr_payload(self, qr_data: dict[str, Any]) -> dict[str, Any]:
        """Encrypt present sensitive QR fields with the current master key."""
        with self._lock:
            key_id, key = self.key_id, self.master_key
        return self._encrypt_fields(qr_data, key, key_id)

    def _encrypt_fields(
        self, qr_data: dict[str, Any], key: bytes, key_id: str,
    ) -> dict[str, Any]:
        encrypted = qr_data.copy()
        fields = [field for field in _SENSITIVE_FIELDS if encrypted.get(field) is not None]
        if not fields:
            raise EncryptionError("No sensitive QR fields to encrypt")
        for field in fields:
            encrypted[field] = self._encrypt(encrypted[field], key, f"qr_field_{field}").decode("ascii")
        encrypted.update({
            "_encrypted_fields": fields,
            "_encryption_key_id": key_id,
            "_encrypted_at": self._get_timestamp(),
        })
        return encrypted

    def decrypt_qr_payload(self, encrypted_qr_data: dict[str, Any]) -> dict[str, Any]:
        """Decrypt the whole QR payload or raise if a protected field fails."""
        decrypted = encrypted_qr_data.copy()
        fields = decrypted.get("_encrypted_fields")
        if fields is None:
            return decrypted
        if (
            not isinstance(fields, list) or not fields
            or any(field not in _SENSITIVE_FIELDS for field in fields)
            or len(fields) != len(set(fields))
        ):
            raise EncryptionError("Invalid encrypted field list")

        decrypted.pop("_encrypted_fields")
        master_id = decrypted.pop("_encryption_key_id", None)
        data_key_id = decrypted.pop("_data_key_id", None)
        decrypted.pop("_encrypted_at", None)
        if master_id is not None and not isinstance(master_id, str):
            raise EncryptionError("Invalid encryption key identifier")
        with self._lock:
            if data_key_id is not None:
                if not isinstance(data_key_id, str) or not data_key_id:
                    raise EncryptionError("Invalid data key identifier")
                key = self._get_key_by_id(data_key_id).key_data
            else:
                # Older payloads use a sender-local master ID. A verifier
                # with the same master bytes can still authenticate the fields.
                key = self.key_store.get(master_id, self.master_key)

        # Legacy writers listed absent sensitive fields. A payload must
        # nevertheless contain at least one actual encrypted field.
        present = [field for field in fields if decrypted.get(field) is not None]
        if not present:
            raise EncryptionError("No encrypted QR fields to decrypt")
        for field in present:
            value = decrypted[field]
            if not isinstance(value, str):
                raise EncryptionError("Invalid encrypted field")
            plaintext = self._decrypt(value, key, f"qr_field_{field}")
            try:
                decrypted[field] = plaintext if field == "identity_hash" else self._decode_plaintext(plaintext)
            except ValueError as error:
                raise EncryptionError("Invalid encrypted field value") from error
        return decrypted

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

        key = EncryptionKey(
            key_id=key_id,
            key_data=key_data,
            algorithm="aes-256-gcm",
            created_at=self._get_timestamp(),
            purpose=purpose,
        )
        with self._lock:
            self.key_store[key_id] = key_data
        return key

    def create_encrypted_qr_data(self, qr_data: dict[str, Any], key_id: str) -> dict[str, Any]:
        """Encrypt sensitive QR fields with a registered data key."""
        with self._lock:
            key = self._get_key_by_id(key_id)
            master_id = self.key_id
        encrypted = self._encrypt_fields(qr_data, key.key_data, master_id)
        encrypted["_data_key_id"] = key.key_id
        return encrypted

    def decrypt_encrypted_qr_data(self, encrypted_qr_data: dict[str, Any]) -> dict[str, Any]:
        """Decrypt a QR payload using its embedded key metadata."""
        return self.decrypt_qr_payload(encrypted_qr_data)

    def _generate_key_id(self) -> str:
        """Generate unique key identifier."""
        return secrets.token_hex(16)

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(UTC).isoformat()

    def _get_key_by_id(self, key_id: str) -> EncryptionKey:
        """Get encryption key by ID.

        Looks up the key in key_store, falling back to the master key only when
        ``key_id`` is this encryptor's own master key id. Any other unknown
        id raises instead of silently decrypting/encrypting with the master key
        (fail-open on an arbitrary key id would defeat key separation).
        """
        if key_id in self.key_store:
            key_data = self.key_store[key_id]
        elif key_id == self.key_id:
            # Legacy calls may refer to the master key by its own id.
            key_data = self.master_key
        else:
            raise EncryptionError(f"Encryption key not found: {key_id}")

        return EncryptionKey(
            key_id=key_id,
            key_data=key_data,
            algorithm="aes-256-gcm",
            created_at=self._get_timestamp(),
            purpose="stored"
        )

    def add_key(self, key_id: str, key_data: bytes) -> None:
        """Register an additional key in the key store.

        Args:
            key_id: Unique identifier for the key
            key_data: The key bytes to store
        """
        with self._lock:
            self.key_store[key_id] = key_data

    def rotate_key(self) -> str:
        """Rotate the master key.

        Generates a new master key and archives the old one in key_store.

        Returns:
            The key_id of the new master key
        """
        with self._lock:
            self.key_store[self.key_id] = self.master_key
            self.master_key = secrets.token_bytes(32)
            self.key_id = self._generate_key_id()
            return self.key_id
