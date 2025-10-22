"""
Key Management Module

Secure key generation, storage, and management for QRLP cryptographic operations.
Supports RSA and ECDSA key pairs with secure storage and backup capabilities.
"""

import os
import json
import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import secrets


@dataclass
class KeyPair:
    """Represents a cryptographic key pair."""
    public_key: bytes
    private_key: bytes
    algorithm: str  # 'rsa' or 'ecdsa'
    key_size: int
    created_at: datetime
    key_id: str


@dataclass
class KeyInfo:
    """Metadata about a key pair."""
    key_id: str
    algorithm: str
    key_size: int
    created_at: datetime
    last_used: Optional[datetime]
    usage_count: int
    encrypted: bool
    purpose: str


class KeyManager:
    """
    Secure key management for QRLP.

    Handles key generation, storage, encryption, and lifecycle management
    for both RSA and ECDSA key pairs used in digital signatures and encryption.
    """

    def __init__(self, key_dir: Optional[str] = None):
        """
        Initialize key manager.

        Args:
            key_dir: Directory to store keys (default: ~/.qrlp/keys)
        """
        self.key_dir = Path(key_dir) if key_dir else Path.home() / ".qrlp" / "keys"
        self.key_dir.mkdir(parents=True, exist_ok=True)

        self.keys_file = self.key_dir / "key_metadata.json"
        self.keys_info: Dict[str, KeyInfo] = {}
        self._load_key_metadata()

        # Master key for encrypting private keys on disk
        self._master_key = self._get_or_create_master_key()

    def generate_keypair(self, algorithm: str = "rsa", key_size: int = 2048,
                        purpose: str = "general") -> Tuple[bytes, bytes]:
        """
        Generate a new cryptographic key pair.

        Args:
            algorithm: 'rsa' or 'ecdsa'
            key_size: Key size in bits (RSA: 2048-4096, ECDSA: 256-521)
            purpose: Description of key usage

        Returns:
            Tuple of (public_key_bytes, private_key_bytes)
        """
        key_id = self._generate_key_id()

        if algorithm.lower() == "rsa":
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            public_key = private_key.public_key()

        elif algorithm.lower() == "ecdsa":
            if key_size not in [256, 384, 521]:
                raise ValueError("ECDSA key size must be 256, 384, or 521")

            private_key = ec.generate_private_key(
                ec.SECP256R1() if key_size == 256 else
                ec.SECP384R1() if key_size == 384 else
                ec.SECP521R1(),
                backend=default_backend()
            )
            public_key = private_key.public_key()

        else:
            raise ValueError("Algorithm must be 'rsa' or 'ecdsa'")

        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Store key metadata
        key_info = KeyInfo(
            key_id=key_id,
            algorithm=algorithm,
            key_size=key_size,
            created_at=datetime.now(timezone.utc),
            last_used=None,
            usage_count=0,
            encrypted=True,  # Private key will be encrypted on disk
            purpose=purpose
        )

        self.keys_info[key_id] = key_info

        # Store encrypted private key
        encrypted_private = self._encrypt_private_key(private_pem, key_id)
        key_pair = KeyPair(
            public_key=public_pem,
            private_key=encrypted_private,
            algorithm=algorithm,
            key_size=key_size,
            created_at=datetime.now(timezone.utc),
            key_id=key_id
        )

        self._save_key_pair(key_pair)
        self._save_key_metadata()

        return public_pem, private_pem

    def get_keypair(self, key_id: str) -> Optional[KeyPair]:
        """
        Retrieve a key pair by ID.

        Args:
            key_id: Unique key identifier

        Returns:
            KeyPair object or None if not found
        """
        key_file = self.key_dir / f"{key_id}.key"
        if not key_file.exists():
            return None

        try:
            with open(key_file, 'rb') as f:
                data = json.load(f)

            # Decrypt private key for use
            encrypted_private = base64.b64decode(data['private_key'])
            decrypted_private = self._decrypt_private_key(encrypted_private, key_id)

            return KeyPair(
                public_key=base64.b64decode(data['public_key']),
                private_key=decrypted_private,
                algorithm=data['algorithm'],
                key_size=data['key_size'],
                created_at=datetime.fromisoformat(data['created_at']),
                key_id=key_id
            )
        except Exception:
            return None

    def list_keys(self) -> Dict[str, KeyInfo]:
        """
        List all available keys with their metadata.

        Returns:
            Dictionary mapping key_id to KeyInfo
        """
        return self.keys_info.copy()

    def delete_key(self, key_id: str) -> bool:
        """
        Delete a key pair and its metadata.

        Args:
            key_id: Key identifier to delete

        Returns:
            True if key was deleted successfully
        """
        if key_id not in self.keys_info:
            return False

        # Remove key file
        key_file = self.key_dir / f"{key_id}.key"
        if key_file.exists():
            key_file.unlink()

        # Remove metadata
        del self.keys_info[key_id]
        self._save_key_metadata()

        return True

    def export_public_key(self, key_id: str, format: str = "pem") -> Optional[bytes]:
        """
        Export public key in specified format.

        Args:
            key_id: Key identifier
            format: Export format ('pem', 'der', 'json')

        Returns:
            Public key bytes in requested format
        """
        keypair = self.get_keypair(key_id)
        if not keypair:
            return None

        if format.lower() == "pem":
            return keypair.public_key
        elif format.lower() == "der":
            # Convert PEM to DER
            public_key = serialization.load_pem_public_key(
                keypair.public_key, backend=default_backend()
            )
            return public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        elif format.lower() == "json":
            return json.dumps({
                "key_id": key_id,
                "algorithm": keypair.algorithm,
                "public_key": base64.b64encode(keypair.public_key).decode(),
                "created_at": keypair.created_at.isoformat()
            }, indent=2).encode()

        return None

    def backup_keys(self, backup_dir: str) -> bool:
        """
        Create encrypted backup of all keys.

        Args:
            backup_dir: Directory to store backup

        Returns:
            True if backup was successful
        """
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            # Backup key metadata
            metadata_backup = backup_path / "keys_backup.json"
            backup_data = {
                "backup_created": datetime.now(timezone.utc).isoformat(),
                "keys": {}
            }

            for key_id, key_info in self.keys_info.items():
                keypair = self.get_keypair(key_id)
                if keypair:
                    backup_data["keys"][key_id] = {
                        "key_info": asdict(key_info),
                        "public_key": base64.b64encode(keypair.public_key).decode(),
                        "private_key": base64.b64encode(keypair.private_key).decode(),
                        "algorithm": keypair.algorithm,
                        "key_size": keypair.key_size
                    }

            with open(metadata_backup, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)

            return True

        except Exception as e:
            print(f"Backup failed: {e}")
            return False

    def _generate_key_id(self) -> str:
        """Generate unique key identifier."""
        return secrets.token_hex(16)

    def _get_or_create_master_key(self) -> bytes:
        """Get or create master key for encrypting private keys."""
        master_key_file = self.key_dir / ".master_key"

        if master_key_file.exists():
            with open(master_key_file, 'rb') as f:
                return f.read()

        # Generate new master key
        master_key = secrets.token_bytes(32)
        with open(master_key_file, 'wb') as f:
            f.write(master_key)

        # Set restrictive permissions
        master_key_file.chmod(0o600)

        return master_key

    def _encrypt_private_key(self, private_key_pem: bytes, key_id: str) -> bytes:
        """Encrypt private key using master key."""
        # Use AES-256-GCM for encryption
        iv = secrets.token_bytes(12)
        cipher = Cipher(
            algorithms.AES(self._master_key),
            modes.GCM(iv),
            backend=default_backend()
        )

        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(private_key_pem) + encryptor.finalize()

        # Combine IV, tag, and encrypted data
        tag = encryptor.tag
        return base64.b64encode(iv + tag + encrypted_data)

    def _decrypt_private_key(self, encrypted_data_b64: bytes, key_id: str) -> bytes:
        """Decrypt private key using master key."""
        encrypted_data = base64.b64decode(encrypted_data_b64)

        # Extract components
        iv = encrypted_data[:12]
        tag = encrypted_data[12:28]
        ciphertext = encrypted_data[28:]

        cipher = Cipher(
            algorithms.AES(self._master_key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )

        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()

    def _save_key_pair(self, keypair: KeyPair) -> None:
        """Save key pair to disk."""
        key_file = self.key_dir / f"{keypair.key_id}.key"

        data = {
            "public_key": base64.b64encode(keypair.public_key).decode(),
            "private_key": base64.b64encode(keypair.private_key).decode(),
            "algorithm": keypair.algorithm,
            "key_size": keypair.key_size,
            "created_at": keypair.created_at.isoformat()
        }

        with open(key_file, 'w') as f:
            json.dump(data, f, indent=2)

        # Set restrictive permissions
        key_file.chmod(0o600)

    def _load_key_metadata(self) -> None:
        """Load key metadata from disk."""
        if not self.keys_file.exists():
            return

        try:
            with open(self.keys_file, 'r') as f:
                data = json.load(f)

            for key_id, key_data in data.items():
                self.keys_info[key_id] = KeyInfo(
                    key_id=key_id,
                    algorithm=key_data['algorithm'],
                    key_size=key_data['key_size'],
                    created_at=datetime.fromisoformat(key_data['created_at']),
                    last_used=datetime.fromisoformat(key_data['last_used']) if key_data.get('last_used') else None,
                    usage_count=key_data['usage_count'],
                    encrypted=key_data['encrypted'],
                    purpose=key_data['purpose']
                )
        except Exception as e:
            print(f"Warning: Could not load key metadata: {e}")

    def _save_key_metadata(self) -> None:
        """Save key metadata to disk."""
        data = {}
        for key_id, key_info in self.keys_info.items():
            data[key_id] = {
                "algorithm": key_info.algorithm,
                "key_size": key_info.key_size,
                "created_at": key_info.created_at.isoformat(),
                "last_used": key_info.last_used.isoformat() if key_info.last_used else None,
                "usage_count": key_info.usage_count,
                "encrypted": key_info.encrypted,
                "purpose": key_info.purpose
            }

        with open(self.keys_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)

