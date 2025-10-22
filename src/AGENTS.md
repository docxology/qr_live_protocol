# Core Module Agent Guidelines

## Development Philosophy

**"Show not tell"** - Implement real QR Live Protocol functionality with comprehensive cryptographic verification, not just descriptions.

**Modular design** - Each function has single responsibility with clear interfaces.

**Test-first development** - Write tests before implementation to ensure correctness.

## Key Patterns

### Core QRLiveProtocol Class

```python
# Real implementation pattern
class QRLiveProtocol:
    """Main coordinator for QR Live Protocol operations."""

    def __init__(self, config: QRLPConfig = None):
        """Initialize QRLP with optional configuration."""
        self.config = config or QRLPConfig()

        # Initialize all components
        self.qr_generator = QRGenerator(self.config.qr_settings)
        self.time_provider = TimeProvider(self.config.time_settings)
        self.blockchain_verifier = BlockchainVerifier(self.config.blockchain_settings)
        self.identity_manager = IdentityManager(self.config.identity_settings)

        # Cryptographic components
        self.key_manager = KeyManager()
        self.signature_manager = QRSignatureManager(self.key_manager)
        self.encryptor = DataEncryptor()
        self.hmac_manager = HMACManager()

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
        qr_data = QRData(**qr_data_dict)
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
# Real error handling pattern
def generate_single_qr(self, user_data=None, sign_data=True, encrypt_data=False):
    """Generate QR with comprehensive error handling."""
    try:
        # Core generation logic
        qr_data, qr_image = self._generate_qr_core(user_data, sign_data, encrypt_data)

        # Update statistics and callbacks
        self._update_generation_stats()

        return qr_data, qr_image

    except CryptoError as e:
        # Log cryptographic errors
        self._log_error("crypto_error", e)
        # Continue with reduced functionality
        return self._generate_basic_qr(user_data)

    except Exception as e:
        # Log unexpected errors
        self._log_error("generation_error", e)
        raise QRLiveProtocolError(f"QR generation failed: {e}")
```

### 3. Testing Requirements
- Unit tests for all public methods
- Integration tests for component interaction
- Performance tests for load scenarios
- Security tests for cryptographic operations

### 4. Configuration Management
```python
# Real configuration pattern
class QRLiveProtocol:
    def __init__(self, config: QRLPConfig = None):
        self.config = config or QRLPConfig()

        # Validate configuration
        issues = self.config.validate()
        if issues:
            raise ConfigurationError(f"Invalid configuration: {issues}")

        # Initialize with validated config
        self._initialize_components()
```

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
    """Real update loop with proper error handling."""
    while self._running:
        try:
            # Generate QR with all features
            qr_data, qr_image = self.generate_single_qr(
                sign_data=self.config.verification_settings.require_blockchain,
                encrypt_data=self.config.security_settings.encrypt_qr_data
            )

            # Notify all callbacks
            for callback in self._callbacks:
                try:
                    callback(qr_data, qr_image)
                except Exception as e:
                    self._log_error("callback_error", e)

            # Sleep for configured interval
            time.sleep(self.config.update_interval)

        except Exception as e:
            self._log_error("update_loop_error", e)
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
        qr_data = QRData(**verification_data)
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
# Real validation pattern
@validator
def validate_qr_data_input(data: str) -> str:
    """Validate QR data input with security checks."""
    if not isinstance(data, str):
        raise ValidationError("QR data must be string")

    if len(data) > MAX_QR_SIZE:
        raise ValidationError("QR data too large")

    # Parse and validate JSON structure
    try:
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            raise ValidationError("QR data must be JSON object")
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid QR data JSON: {e}")

    return data
```

### Error Handling
```python
# Real error handling pattern
def secure_qr_generation(self, user_data: Optional[Dict] = None) -> tuple[QRData, bytes]:
    """Generate QR with comprehensive error handling."""
    try:
        # Validate inputs
        if user_data:
            validate_user_data(user_data)

        # Generate with all security features
        return self.generate_single_qr(user_data, sign_data=True, encrypt_data=True)

    except ValidationError as e:
        # Log validation errors
        self._log_security_event("validation_error", e)
        raise

    except CryptoError as e:
        # Log cryptographic errors
        self._log_security_event("crypto_error", e)
        # Continue with reduced functionality
        return self.generate_single_qr(user_data, sign_data=False, encrypt_data=False)

    except Exception as e:
        # Log unexpected errors
        self._log_security_event("unexpected_error", e)
        raise QRLiveProtocolError(f"QR generation failed: {e}")
```

## Testing Strategy

### Unit Tests
```python
# Real unit test pattern
def test_qr_generation_with_cryptography():
    """Test QR generation with all cryptographic features."""
    qrlp = QRLiveProtocol()

    # Generate key for testing
    public_key, private_key = qrlp.key_manager.generate_keypair("rsa", 2048)

    # Generate cryptographically enhanced QR
    qr_data, qr_image = qrlp.generate_single_qr(
        user_data={"test": "data"},
        sign_data=True,
        encrypt_data=True
    )

    # Verify cryptographic features are applied
    qr_dict = qr_data.__dict__
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

### Caching Strategy
```python
# Real caching pattern
class QRLiveProtocol:
    def __init__(self, config):
        self.config = config

        # Initialize caches
        self._qr_cache = {}
        self._crypto_cache = {}

        # Cache settings
        self._cache_ttl = 60  # 1 minute
        self._max_cache_size = 1000

    def _get_cached_qr(self, cache_key: str) -> Optional[bytes]:
        """Get cached QR image if still valid."""
        if cache_key in self._qr_cache:
            cached_time, qr_image = self._qr_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return qr_image

            # Remove expired cache entry
            del self._qr_cache[cache_key]

        return None

    def _cache_qr(self, cache_key: str, qr_image: bytes):
        """Cache QR image for future use."""
        if len(self._qr_cache) >= self._max_cache_size:
            # Remove oldest entries (simple LRU)
            oldest_key = min(self._qr_cache.keys(),
                           key=lambda k: self._qr_cache[k][0])
            del self._qr_cache[oldest_key]

        self._qr_cache[cache_key] = (time.time(), qr_image)
```

### Memory Management
```python
# Real memory management pattern
def _cleanup_expired_caches(self):
    """Clean up expired cache entries."""
    current_time = time.time()

    # Clean QR cache
    expired_keys = [
        key for key, (cached_time, _) in self._qr_cache.items()
        if current_time - cached_time > self._cache_ttl
    ]
    for key in expired_keys:
        del self._qr_cache[key]

    # Clean crypto cache
    expired_crypto = [
        key for key, (cached_time, _) in self._crypto_cache.items()
        if current_time - cached_time > self._crypto_cache_ttl
    ]
    for key in expired_crypto:
        del self._crypto_cache[key]
```

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

