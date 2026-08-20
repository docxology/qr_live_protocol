"""
QR Live Protocol (QRLP)

A comprehensive system for generating and displaying live QR codes that encode
time-stamped, cryptographically verifiable information for livestreaming
and official video releases.

Built on the qrkey protocol for QR code generation and recovery.
"""

__version__ = "1.5.0"
__author__ = "QRLP Development Team (@docxology)"
__email__ = "danielarifriedman@gmail.com"

from .blockchain_verifier import BlockchainVerifier
from .config import QRLPConfig
from .core import QRData, QRLiveProtocol, VerificationResult
from .crypto import (
    CryptoError,
    DataEncryptor,
    DigitalSigner,
    EncryptionError,
    EncryptionKey,
    HMACError,
    HMACManager,
    KeyInfo,
    KeyManagementError,
    KeyManager,
    KeyPair,
    QRSignatureManager,
    SignatureError,
    SignatureVerifier,
)
from .error_recovery import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    ResilienceManager,
    ResilientOperation,
    RetryStrategy,
)
from .frame_recovery import (
    FrameRecoveryConfig,
    FrameRecoveryController,
    FrameRecoveryStats,
    RecoveryDecision,
)
from .identity_manager import IdentityManager
from .live_simulator import (
    LiveSimulator,
    OpticalChannelModel,
    SimulatedFrame,
    SimulationReport,
)
from .optical_throughput import (
    OpticalThroughputController,
    ThroughputConfig,
    ThroughputStats,
)
from .qr_generator import QRDataTooLargeError, QRGenerator
from .serializer import QRSerializer
from .time_provider import TimeProvider
from .time_stamper import TimeStamper
from .time_stamper_integration import QRLPTimeStampVerifier
from .trust import TrustedPublicKey, TrustStore
from .web_server import QRLiveWebServer

__all__ = [
    "BlockchainVerifier",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpenError",
    "CircuitBreakerState",
    "CryptoError",
    "DataEncryptor",
    "DigitalSigner",
    "EncryptionError",
    "EncryptionKey",
    "FrameRecoveryConfig",
    "FrameRecoveryController",
    "FrameRecoveryStats",
    "HMACError",
    "HMACManager",
    "IdentityManager",
    "KeyInfo",
    "KeyManagementError",
    "KeyManager",
    "KeyPair",
    "LiveSimulator",
    "OpticalChannelModel",
    "OpticalThroughputController",
    "QRData",
    "QRDataTooLargeError",
    "QRGenerator",
    "QRLPConfig",
    "QRLPTimeStampVerifier",
    "QRLiveProtocol",
    "QRLiveWebServer",
    "QRSerializer",
    "QRSignatureManager",
    "RecoveryDecision",
    "ResilienceManager",
    "ResilientOperation",
    "RetryStrategy",
    "SignatureError",
    "SignatureVerifier",
    "SimulatedFrame",
    "SimulationReport",
    "ThroughputConfig",
    "ThroughputStats",
    "TimeProvider",
    "TimeStamper",
    "TrustStore",
    "TrustedPublicKey",
    "VerificationResult"
]
