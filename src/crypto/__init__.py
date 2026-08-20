"""
QRLP Cryptographic Module

Comprehensive cryptographic system providing digital signatures, encryption,
key management, and message authentication for QR Live Protocol.

Features:
- RSA/ECDSA digital signatures for QR data authenticity
- AES-256 encryption for sensitive data protection
- HMAC-SHA256 for message integrity verification
- Secure key generation and management
- Hardware security module support (future)
"""

from .encryptor import DataEncryptor, EncryptionKey
from .exceptions import CryptoError, EncryptionError, HMACError, KeyManagementError, SignatureError
from .hmac import HMACManager
from .key_manager import KeyInfo, KeyManager, KeyPair
from .signer import DigitalSigner, QRSignatureManager, SignatureVerifier

__all__ = [
    'CryptoError',
    'DataEncryptor',
    'DigitalSigner',
    'EncryptionError',
    'EncryptionKey',
    'HMACError',
    'HMACManager',
    'KeyInfo',
    'KeyManagementError',
    'KeyManager',
    'KeyPair',
    'QRSignatureManager',
    'SignatureError',
    'SignatureVerifier'
]

__version__ = "1.0.0"

