# Core Module Agent Guidelines

## Development Philosophy

**"Show not tell"** - Implement real QR Live Protocol functionality with comprehensive cryptographic verification, not just descriptions.

**Modular design** - Each function has single responsibility with clear interfaces.

**Test-first development** - Write tests before implementation to ensure correctness.

## Key Patterns

### Core QRLiveProtocol Class

```python
# Real implementation pattern (see src/core.py)
class QRLiveProtocol:
    """Main coordinator for QR Live Protocol operations."""

    def __init__(self, config: QRLPConfig | None = None,
                 key_manager: KeyManager | None = None,
                 signature_manager: QRSignatureManager | None = None,
                 encryptor: DataEncryptor | None = None,
                 hmac_manager: HMACManager | None = None,
                 trust_store: TrustStore | None = None,
                 issuer_id: str | None = None):
        """Initialize QRLP with optional configuration and components."""
        self.config = config or QRLPConfig()

        # Initialize all components
        self.qr_generator = QRGenerator(self.config.qr_settings)
        self.time_provider = TimeProvider(self.config.time_settings)
        self.blockchain_verifier = BlockchainVerifier(self.config.blockchain_settings)
        self.identity_manager = IdentityManager(self.config.identity_settings)

        # OpenTimestamps stamper (additive layer, disabled by default)
        self.time_stamper = TimeStamper(
            enabled=self.config.time_settings.ots_enabled,
            server=self.config.time_settings.ots_server,
            min_interval=self.config.time_settings.ots_min_interval,
            proof_dir=Path(self.config.time_settings.ots_proof_dir),
        )

        # Cryptographic components (key_manager is a read/write property)
        self.key_manager = key_manager or KeyManager(self.config.security_settings.key_dir)
        self.signature_manager = signature_manager or QRSignatureManager(self.key_manager)
        self.encryptor = encryptor or DataEncryptor()
        self.hmac_manager = hmac_manager or HMACManager()
        self.trust_store = trust_store or TrustStore()

    def generate_single_qr(self, user_data: Optional[Dict] = None,
                          sign_data: bool = True, encrypt_data: bool = False) -> tuple[QRData, bytes]:
        """Generate single QR with cryptographic enhancements."""
        # Real implementation with all verification layers
        current_time = self.time_provider.get_current_time()
        identity_hash = self.identity_manager.get_identity_hash()
        blockchain_hashes = self.blockchain_verifier.get_blockchain_hashes()

        qr_data = QRData(
            timestamp=current_time.isoformat(),
            identity_hash=identity_hash,
            blockchain_hashes=blockchain_hashes,
            time_server_verification=self.time_provider.get_time_server_verification(),
            user_data=user_data,
            sequence_number=self._sequence_number
        )

        # Apply cryptographic enhancements
        enhanced_data = self._apply_cryptographic_enhancements(qr_data, sign_data, encrypt_data)

        qr_json = json.dumps(enhanced_data, separators=(',', ':'))
        qr_image = self.qr_generator.generate_qr_image(qr_json)

        return qr_data, qr_image

    def verify_qr_data(self, qr_json: str) -> Dict[str, bool]:
        """Verify QR data with comprehensive cryptographic checks."""
        # Real verification implementation
        raw_data = json.loads(qr_json)

        # Check encryption
        if '_encrypted_fields' in raw_data:
            decrypted_data = self.encryptor.decrypt_qr_payload(raw_data)
            qr_data_dict = decrypted_data
        else:
            qr_data_dict = raw_data

        # Verify HMAC (always present)
        hmac_verified = self.hmac_manager.verify_integrity_checked_qr(qr_data_dict)

        # Verify digital signature if present
        signature_verified = False
        if 'digital_signature' in qr_data_dict:
            signature_verified = self.signature_manager.verify_signed_qr_data(qr_data_dict)

        # Verify identity and time
        qr_data = QRData.from_dict(qr_data_dict)  # drops unknown fields
        identity_verified = qr_data.identity_hash == self.identity_manager.get_identity_hash()

        qr_time = datetime.fromisoformat(qr_data.timestamp.replace('Z', '+00:00'))
        time_diff = abs((datetime.now(timezone.utc) - qr_time).total_seconds())
        time_verified = time_diff <= self.config.verification_settings.max_time_drift

        # Verify blockchain hashes
        blockchain_verified = False
        if qr_data.blockchain_hashes:
            current_hashes = self.blockchain_verifier.get_blockchain_hashes()
            blockchain_verified = any(
                current_hashes.get(chain) == hash_val
                for chain, hash_val in qr_data.blockchain_hashes.items()
            )

        return {
            "valid_json": True,
            "identity_verified": identity_verified,
            "time_verified": time_verified,
            "blockchain_verified": blockchain_verified,
            "signature_verified": signature_verified,
            "hmac_verified": hmac_verified,
            "encrypted": '_encrypted_fields' in raw_data
        }
```

## Implementation Rules

### 1. Cryptographic Integration
- Always apply HMAC integrity checking
- Support optional digital signatures
- Support optional field-level encryption
- Use proper key management for all operations

### 2. Error Handling
```python
# Real error handling pattern (generation errors propagate; the update loop
# logs and continues, see QRLiveProtocol._update_loop in src/core.py)
def _update_loop(self) -> None:
    while self._running:
        try:
            self.generate_single_qr()
            time.sleep(self.config.update_interval)
        except Exception as e:
            _logger.error(f"Update loop error: {e}")
            time.sleep(1.0)  # Prevent tight error loops
```

There is no `QRLiveProtocolError`, `_generate_basic_qr`, or `_log_error`
symbol in this codebase — errors are standard exceptions; generation
failures raise (e.g. `QRDataTooLargeError` for oversized payloads).

### 3. Testing Requirements
- Unit tests for all public methods
- Integration tests for component interaction
- Performance tests for load scenarios
- Security tests for cryptographic operations

### 4. Configuration Management
```python
# Real configuration pattern: validate() is a QRLPConfig method that returns
# a list of issue strings; call it explicitly before construction if needed.
config = QRLPConfig()
issues = config.validate()
if issues:
    raise ValueError(f"Invalid configuration: {issues}")

qrlp = QRLiveProtocol(config)
```

There is no `ConfigurationError` exception in this codebase; `validate()`
returns issues rather than raising.

## Component Interaction Patterns

### Real-Time Updates
```python
# Real callback pattern
def start_live_generation(self):
    """Start continuous QR generation with real callbacks."""
    if self._running:
        return

    self._running = True
    self._update_thread = threading.Thread(
        target=self._update_loop,
        daemon=True,
        name="QRLP-Update-Thread"
    )
    self._update_thread.start()

def _update_loop(self):
    """Real update loop (simplified from src/core.py)."""
    while self._running:
        try:
            start_time = time.time()

            # Generate new QR (signing/encryption come from config defaults)
            qr_data, qr_image = self.generate_single_qr()
            # Callbacks are notified inside generate_single_qr via _notify_callbacks()

            # Sleep for the remaining interval time
            elapsed = time.time() - start_time
            sleep_time = max(0, self.config.update_interval - elapsed)
            time.sleep(sleep_time)

        except Exception as e:
            _logger.error(f"Update loop error: {e}")
            time.sleep(1.0)  # Prevent tight error loops
```

### Verification Workflow
```python
# Real verification pattern
def verify_qr_data(self, qr_json: str) -> Dict[str, bool]:
    """Comprehensive verification with all security layers."""
    try:
        # Parse and decrypt if needed
        raw_data = json.loads(qr_json)

        if '_encrypted_fields' in raw_data:
            decrypted_data = self.encryptor.decrypt_qr_payload(raw_data)
            verification_data = decrypted_data
        else:
            verification_data = raw_data

        # Verify all layers
        results = {
            'valid_json': True,
            'hmac_verified': self.hmac_manager.verify_integrity_checked_qr(verification_data),
            'signature_verified': False,
            'identity_verified': False,
            'time_verified': False,
            'blockchain_verified': False,
            'encrypted': '_encrypted_fields' in raw_data
        }

        # Digital signature verification
        if 'digital_signature' in verification_data:
            results['signature_verified'] = self.signature_manager.verify_signed_qr_data(verification_data)

        # Identity verification
        qr_data = QRData.from_dict(verification_data)  # drops unknown fields
        results['identity_verified'] = qr_data.identity_hash == self.identity_manager.get_identity_hash()

        # Time verification
        qr_time = datetime.fromisoformat(qr_data.timestamp.replace('Z', '+00:00'))
        time_diff = abs((datetime.now(timezone.utc) - qr_time).total_seconds())
        results['time_verified'] = time_diff <= self.config.verification_settings.max_time_drift

        # Blockchain verification
        if qr_data.blockchain_hashes:
            current_hashes = self.blockchain_verifier.get_blockchain_hashes()
            results['blockchain_verified'] = any(
                current_hashes.get(chain) == hash_val
                for chain, hash_val in qr_data.blockchain_hashes.items()
            )

        return results

    except Exception as e:
        return {
            'valid_json': False,
            'error': str(e),
            'hmac_verified': False,
            'signature_verified': False,
            'identity_verified': False,
            'time_verified': False,
            'blockchain_verified': False,
            'encrypted': False
        }
```

## Development Workflow

### 1. Feature Development
1. Write failing test first
2. Implement minimal functionality
3. Add cryptographic enhancements
4. Ensure security validation
5. Update documentation

### 2. Code Review Checklist
- [ ] All public methods have type hints
- [ ] Error handling covers all edge cases
- [ ] Cryptographic operations are properly implemented
- [ ] Tests pass and cover functionality
- [ ] Documentation is accurate and complete
- [ ] Security considerations addressed

### 3. Performance Considerations
- QR generation should complete in < 100ms
- Cryptographic operations should be cached appropriately
- Memory usage should not grow unbounded
- Threading should be safe and deadlock-free

## Integration Examples

### Real-World Usage
```python
# Real livestream integration
qrlp = QRLiveProtocol()
qrlp.start_live_generation()

# Generate signed QR for important announcement
qr_data, qr_image = qrlp.generate_signed_qr(
    {"announcement": "Product launch", "timestamp": "2025-01-11T15:30:00Z"},
    signing_key_id="product_launch_key"
)

# Verify authenticity
verification = qrlp.verify_qr_data(qr_data.to_json())
assert verification['signature_verified'] == True
assert verification['identity_verified'] == True
```

### Production Deployment
```python
# Real production configuration
config = QRLPConfig()
config.update_interval = 1.0  # Fast updates for live events
config.security_settings.encrypt_qr_data = True  # Encrypt sensitive data
config.verification_settings.require_blockchain = True  # Require blockchain verification

qrlp = QRLiveProtocol(config)

# Generate cryptographically secure QR
qr_data, qr_image = qrlp.generate_single_qr(
    user_data={"event": "live_conference"},
    sign_data=True,
    encrypt_data=True
)
```

## Security Requirements

### Cryptographic Standards
- Use RSA-2048 or ECDSA-P256 for digital signatures
- Use AES-256-GCM for encryption
- Use HMAC-SHA256 for integrity checking
- Generate cryptographically secure random keys
- Implement proper key rotation

### Input Validation
```python
# Real validation pattern: there is no @validator decorator or ValidationError
# class in this codebase. The web layer uses SecurityValidator (src/web_server.py);
# plain code should raise ValueError.
from src.config import QRSettings

MAX_QR_SIZE = QRSettings().max_data_size  # 2000 bytes by default

def validate_qr_data_input(data: str) -> str:
    """Validate QR data input with security checks."""
    if not isinstance(data, str):
        raise ValueError("QR data must be string")

    if len(data) > MAX_QR_SIZE:
        raise ValueError("QR data too large")

    # Parse and validate JSON structure
    try:
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            raise ValueError("QR data must be JSON object")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid QR data JSON: {e}")

    return data
```

### Error Handling
```python
# Error handling pattern (there is no _log_security_event or
# QRLiveProtocolError in this codebase — use logging and standard exceptions)
import logging

_logger = logging.getLogger(__name__)

def secure_qr_generation(qrlp: QRLiveProtocol, user_data: dict | None = None) -> tuple[QRData, bytes]:
    """Generate QR with comprehensive error handling."""
    try:
        return qrlp.generate_single_qr(user_data, sign_data=True, encrypt_data=True)
    except CryptoError as e:
        _logger.error(f"Crypto error: {e}")
        # Continue with reduced functionality
        return qrlp.generate_single_qr(user_data, sign_data=False, encrypt_data=False)
    except Exception as e:
        _logger.error(f"QR generation failed: {e}")
        raise
```

## Testing Strategy

### Unit Tests
```python
# Real unit test pattern
def test_qr_generation_with_cryptography():
    """Test QR generation with all cryptographic features."""
    qrlp = QRLiveProtocol()
    # Encryption inflates the payload — lower EC level to leave QR headroom
    qrlp.config.qr_settings.error_correction_level = "L"

    # Generate cryptographically enhanced QR
    qr_data, qr_image = qrlp.generate_single_qr(
        user_data={"test": "data"},
        sign_data=True,
        encrypt_data=True
    )

    # Verify cryptographic features are applied
    qr_dict = qr_data.to_dict()
    assert '_hmac' in qr_dict
    assert 'digital_signature' in qr_dict
    assert '_encrypted_fields' in qr_dict

    # Verify functionality
    qr_json = json.dumps(qr_dict, separators=(',', ':'))
    results = qrlp.verify_qr_data(qr_json)

    assert results['hmac_verified'] == True
    assert results['signature_verified'] == True
    assert results['encrypted'] == True
```

### Integration Tests
```python
# Real integration test pattern
def test_full_qr_lifecycle():
    """Test complete QR lifecycle from generation to verification."""
    qrlp1 = QRLiveProtocol()  # Generator
    qrlp2 = QRLiveProtocol()  # Verifier

    # Share key manager for consistent verification
    qrlp2.key_manager = qrlp1.key_manager

    # Generate QR with full cryptographic features
    qr_data, qr_image = qrlp1.generate_single_qr(
        user_data={"integration_test": True},
        sign_data=True,
        encrypt_data=True
    )

    # Verify with second instance
    qr_json = qr_data.to_json()
    results = qrlp2.verify_qr_data(qr_json)

    # All verifications should pass
    assert results['valid_json'] == True
    assert results['hmac_verified'] == True
    assert results['signature_verified'] == True
    assert results['identity_verified'] == True
    assert results['encrypted'] == True
```

## Performance Optimization

### Caching
```python
# Real caching: QRGenerator keeps a bounded dict of rendered images keyed by
# payload hash + style + error-correction level (see src/qr_generator.py).
qrlp = QRLiveProtocol()

# Inspect / clear the QR image cache
print(len(qrlp.qr_generator.cache))
qrlp.qr_generator.cache.clear()

# BlockchainVerifier caches per-chain block info in cached_blocks
print(qrlp.blockchain_verifier.cached_blocks.keys())
qrlp.blockchain_verifier.cached_blocks.clear()
```

There is no `_qr_cache`, `_crypto_cache`, `_cache_ttl`, or
`_cleanup_expired_caches` on `QRLiveProtocol` in this codebase — caching lives
in `QRGenerator.cache` and `BlockchainVerifier.cached_blocks`.

## Future Enhancements

### Advanced Features
1. **Multi-signature support** - Multiple parties can sign QR data
2. **Zero-knowledge proofs** - Prove data validity without revealing content
3. **Hardware security modules** - HSM integration for key storage
4. **Blockchain anchoring** - Store QR hashes on blockchain for immutability

### Performance Improvements
1. **Async operations** - Non-blocking cryptographic operations
2. **GPU acceleration** - Hardware-accelerated QR generation
3. **Distributed caching** - Redis-based cache for multi-instance deployments
4. **CDN integration** - Content delivery network for global distribution

This document provides concrete, implementable patterns for developing the QRLiveProtocol core module with cryptographic security, comprehensive testing, and production-ready features.



## Actual Implemented Crypto Pipeline (v1.2.0)

`verify_qr_data()` returns the keys shown above plus `replayed`, `valid`, and
`trust_mode` (`none`, `local_signature`, or `public_signature`). The `valid`
flag requires valid JSON, time within drift tolerance, blockchain OK (when
required), HMAC or signature authenticity, and a non-replayed nonce.

The cryptographic enhancement pipeline in `QRLiveProtocol._apply_cryptographic_enhancements` follows this order:

1. **Sign** — `QRSignatureManager.create_signed_qr_data()` adds `digital_signature`, `signing_key_id`, `signature_algorithm`
2. **HMAC** — `HMACManager.create_integrity_checked_qr()` adds `_hmac`, `_hmac_key_id`, `_hmac_algorithm`, `_integrity_checked_at`
3. **Encrypt** (optional) — `DataEncryptor.encrypt_qr_payload()` encrypts sensitive fields and adds `_encrypted_fields`, `_encryption_key_id`, `_encrypted_at`

The HMAC covers the signature (applied after signing). Encryption covers the HMAC (applied after HMAC).

### New Types (v1.2.0)
- `VerificationResult` dataclass — typed replacement for the verification dict
- `QRData.to_dict()` — returns clean dict without None entries
- `QRData.__repr__` / `QRData.__str__` — debugging output
- `QRData.from_json()` / `QRData.from_dict()` — ignore unknown fields for forward compatibility

### Exception Renaming (v1.1.0)
- `KeyError` was renamed to `KeyManagementError` in `crypto/exceptions.py` to avoid shadowing Python's builtin
- `HMACError` is now exported from `crypto/__init__.py` and `src/__init__.py`

### Security Headers (v1.2.0)
- Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Referrer-Policy
  added to all web responses via Flask `after_request` hook

### Connection Pooling (v1.2.0)
- `BlockchainVerifier` uses `requests.Session` for keep-alive HTTP connections
