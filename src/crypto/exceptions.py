"""
Cryptographic Exceptions

Custom exception classes for QRLP cryptographic operations.
"""


class CryptoError(Exception):
    """Base exception for cryptographic operations."""
    pass


class KeyError(CryptoError):
    """Exception for key management operations."""
    pass


class SignatureError(CryptoError):
    """Exception for digital signature operations."""
    pass


class EncryptionError(CryptoError):
    """Exception for encryption/decryption operations."""
    pass


class HMACError(CryptoError):
    """Exception for HMAC operations."""
    pass

