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

from .key_manager import KeyManager, KeyPair, KeyInfo
from .signer import DigitalSigner, SignatureVerifier, QRSignatureManager
from .encryptor import DataEncryptor, EncryptionKey
from .hmac import HMACManager
from .exceptions import CryptoError, KeyError, SignatureError, EncryptionError

__all__ = [
    'KeyManager', 'KeyPair', 'KeyInfo',
    'DigitalSigner', 'SignatureVerifier', 'QRSignatureManager',
    'DataEncryptor', 'EncryptionKey',
    'HMACManager',
    'CryptoError', 'KeyError', 'SignatureError', 'EncryptionError'
]

__version__ = "1.0.0"

