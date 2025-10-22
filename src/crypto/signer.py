"""
Digital Signature Module

RSA and ECDSA digital signature creation and verification for QR data authenticity.
Provides cryptographic proof of QR code origin and integrity.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
from dataclasses import asdict
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding, utils
from cryptography.exceptions import InvalidSignature

from .key_manager import KeyManager
from .exceptions import SignatureError


class DigitalSigner:
    """
    Digital signature creation for QR data.

    Creates cryptographic signatures using RSA or ECDSA to prove
    QR code authenticity and prevent tampering.
    """

    def __init__(self, private_key_pem: bytes, algorithm: str = "rsa"):
        """
        Initialize digital signer.

        Args:
            private_key_pem: Private key in PEM format
            algorithm: Signature algorithm ('rsa' or 'ecdsa')
        """
        self.algorithm = algorithm.lower()
        self.private_key = self._load_private_key(private_key_pem)

    def sign_qr_data(self, qr_data: Any) -> bytes:
        """
        Create digital signature for QR data.

        Args:
            qr_data: QRData object or dictionary to sign

        Returns:
            Digital signature bytes
        """
        # Convert QR data to canonical JSON for consistent signing
        if hasattr(qr_data, 'to_json'):
            data_json = qr_data.to_json()
        else:
            data_json = json.dumps(qr_data, sort_keys=True, separators=(',', ':'))

        # Create hash of the data
        data_hash = hashlib.sha256(data_json.encode('utf-8')).digest()

        # Sign the hash
        if self.algorithm == "rsa":
            signature = self.private_key.sign(
                data_hash,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        elif self.algorithm == "ecdsa":
            signature = self.private_key.sign(
                data_hash,
                ec.ECDSA(hashes.SHA256())
            )
        else:
            raise SignatureError(f"Unsupported algorithm: {self.algorithm}")

        return signature

    def sign_message(self, message: str) -> bytes:
        """
        Create digital signature for arbitrary message.

        Args:
            message: Message string to sign

        Returns:
            Digital signature bytes
        """
        message_hash = hashlib.sha256(message.encode('utf-8')).digest()

        if self.algorithm == "rsa":
            signature = self.private_key.sign(
                message_hash,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        elif self.algorithm == "ecdsa":
            signature = self.private_key.sign(
                message_hash,
                ec.ECDSA(hashes.SHA256())
            )

        return signature

    def _load_private_key(self, private_key_pem: bytes):
        """Load private key from PEM bytes."""
        try:
            return serialization.load_pem_private_key(
                private_key_pem,
                password=None  # Assuming no password for now
            )
        except Exception as e:
            raise SignatureError(f"Failed to load private key: {e}")


class SignatureVerifier:
    """
    Digital signature verification for QR data.

    Verifies cryptographic signatures to ensure QR code authenticity
    and detect any tampering or unauthorized modifications.
    """

    def __init__(self, public_key_pem: bytes, algorithm: str = "rsa"):
        """
        Initialize signature verifier.

        Args:
            public_key_pem: Public key in PEM format
            algorithm: Signature algorithm ('rsa' or 'ecdsa')
        """
        self.algorithm = algorithm.lower()
        self.public_key = self._load_public_key(public_key_pem)

    def verify_qr_data(self, qr_data: Any, signature: bytes) -> bool:
        """
        Verify digital signature for QR data.

        Args:
            qr_data: QRData object or dictionary that was signed
            signature: Digital signature to verify

        Returns:
            True if signature is valid
        """
        try:
            # Convert QR data to canonical JSON for consistent verification
            if hasattr(qr_data, 'to_json'):
                data_json = qr_data.to_json()
            else:
                data_json = json.dumps(qr_data, sort_keys=True, separators=(',', ':'))

            # Create hash of the data
            data_hash = hashlib.sha256(data_json.encode('utf-8')).digest()

            # Verify signature
            if self.algorithm == "rsa":
                self.public_key.verify(
                    signature,
                    data_hash,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            elif self.algorithm == "ecdsa":
                self.public_key.verify(
                    signature,
                    data_hash,
                    ec.ECDSA(hashes.SHA256())
                )
            else:
                raise SignatureError(f"Unsupported algorithm: {self.algorithm}")

            return True

        except InvalidSignature:
            return False
        except Exception as e:
            raise SignatureError(f"Verification failed: {e}")

    def verify_message(self, message: str, signature: bytes) -> bool:
        """
        Verify digital signature for arbitrary message.

        Args:
            message: Original message that was signed
            signature: Digital signature to verify

        Returns:
            True if signature is valid
        """
        try:
            message_hash = hashlib.sha256(message.encode('utf-8')).digest()

            if self.algorithm == "rsa":
                self.public_key.verify(
                    signature,
                    message_hash,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            elif self.algorithm == "ecdsa":
                self.public_key.verify(
                    signature,
                    message_hash,
                    ec.ECDSA(hashes.SHA256())
                )

            return True

        except InvalidSignature:
            return False
        except Exception as e:
            raise SignatureError(f"Message verification failed: {e}")

    def _load_public_key(self, public_key_pem: bytes):
        """Load public key from PEM bytes."""
        try:
            return serialization.load_pem_public_key(public_key_pem)
        except Exception as e:
            raise SignatureError(f"Failed to load public key: {e}")


class QRSignatureManager:
    """
    High-level manager for QR code signing and verification.

    Provides convenient interface for signing QR data and managing
    the complete signature lifecycle including key management.
    """

    def __init__(self, key_manager: KeyManager):
        """
        Initialize QR signature manager.

        Args:
            key_manager: KeyManager instance for key operations
        """
        self.key_manager = key_manager

    def sign_qr_with_key(self, qr_data: Any, key_id: str) -> Tuple[bytes, str]:
        """
        Sign QR data using specified key.

        Args:
            qr_data: QRData object or dictionary to sign
            key_id: Key identifier to use for signing

        Returns:
            Tuple of (signature_bytes, key_id)
        """
        keypair = self.key_manager.get_keypair(key_id)
        if not keypair:
            raise SignatureError(f"Key not found: {key_id}")

        # Update usage statistics
        if key_id in self.key_manager.keys_info:
            key_info = self.key_manager.keys_info[key_id]
            key_info.usage_count += 1
            key_info.last_used = datetime.now()
            self.key_manager._save_key_metadata()

        signer = DigitalSigner(keypair.private_key, keypair.algorithm)
        signature = signer.sign_qr_data(qr_data)

        return signature, key_id

    def verify_qr_signature(self, qr_data: Any, signature: bytes, key_id: str) -> bool:
        """
        Verify QR data signature using specified key.

        Args:
            qr_data: QRData object or dictionary that was signed
            signature: Digital signature to verify
            key_id: Key identifier used for verification

        Returns:
            True if signature is valid
        """
        keypair = self.key_manager.get_keypair(key_id)
        if not keypair:
            return False

        verifier = SignatureVerifier(keypair.public_key, keypair.algorithm)
        return verifier.verify_qr_data(qr_data, signature)

    def create_signed_qr_data(self, qr_data: Any, signing_key_id: str) -> Dict[str, Any]:
        """
        Create QR data with embedded signature.

        Args:
            qr_data: Original QR data
            signing_key_id: Key ID for signing

        Returns:
            QR data dictionary with signature field
        """
        signature, used_key_id = self.sign_qr_with_key(qr_data, signing_key_id)

        # Create signed QR data
        if hasattr(qr_data, '__dict__'):
            signed_data = qr_data.__dict__.copy()
        else:
            signed_data = qr_data.copy()

        signed_data['digital_signature'] = signature.hex()
        signed_data['signing_key_id'] = used_key_id
        signed_data['signature_algorithm'] = self.key_manager.get_keypair(used_key_id).algorithm

        return signed_data

    def verify_signed_qr_data(self, signed_qr_data: Dict[str, Any]) -> bool:
        """
        Verify QR data with embedded signature.

        Args:
            signed_qr_data: QR data with signature field

        Returns:
            True if signature is valid
        """
        if 'digital_signature' not in signed_qr_data:
            return False

        signature_hex = signed_qr_data['digital_signature']
        key_id = signed_qr_data['signing_key_id']

        signature = bytes.fromhex(signature_hex)

        # Remove signature fields for verification
        verification_data = signed_qr_data.copy()
        verification_data.pop('digital_signature', None)
        verification_data.pop('signing_key_id', None)
        verification_data.pop('signature_algorithm', None)

        return self.verify_qr_signature(verification_data, signature, key_id)

