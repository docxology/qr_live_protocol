"""
QR Live Protocol (QRLP)

A comprehensive system for generating and displaying live QR codes that encode
time-stamped, cryptographically verifiable information for livestreaming
and official video releases.

Built on the qrkey protocol for QR code generation and recovery.
"""

__version__ = "1.4.0"
__author__ = "QRLP Development Team (@docxology)"
__email__ = "danielarifriedman@gmail.com"

from .core import QRLiveProtocol, QRData, VerificationResult
from .config import QRLPConfig
from .serializer import QRSerializer
from .qr_generator import QRDataTooLargeError, QRGenerator
from .time_provider import TimeProvider
from .blockchain_verifier import BlockchainVerifier
from .identity_manager import IdentityManager
from .web_server import QRLiveWebServer
from .trust import TrustStore, TrustedPublicKey
from .crypto import (
    KeyManager, KeyPair, KeyInfo,
    DigitalSigner, SignatureVerifier, QRSignatureManager,
    DataEncryptor, EncryptionKey,
    HMACManager,
    CryptoError, KeyManagementError, SignatureError, EncryptionError, HMACError
)
from .error_recovery import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState,
    RetryStrategy, ResilientOperation, ResilienceManager,
    CircuitBreakerOpenError
)

__all__ = [
    "QRLiveProtocol", "QRData", "VerificationResult",
    "QRLPConfig",
    "QRSerializer",
    "QRGenerator", "QRDataTooLargeError",
    "TimeProvider",
    "BlockchainVerifier",
    "IdentityManager",
    "QRLiveWebServer",
    "TrustStore", "TrustedPublicKey",
    "KeyManager", "KeyPair", "KeyInfo",
    "DigitalSigner", "SignatureVerifier", "QRSignatureManager",
    "DataEncryptor", "EncryptionKey",
    "HMACManager",
    "CryptoError", "KeyManagementError", "SignatureError", "EncryptionError", "HMACError",
    "CircuitBreaker", "CircuitBreakerConfig", "CircuitBreakerState",
    "RetryStrategy", "ResilientOperation", "ResilienceManager",
    "CircuitBreakerOpenError"
]
