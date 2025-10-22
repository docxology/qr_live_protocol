# QRLiveProtocol Core Module

## Overview

The core module of QR Live Protocol (QRLP) provides the main coordination functionality for generating live, cryptographically verifiable QR codes. This module orchestrates all QRLP components including QR generation, time synchronization, blockchain verification, identity management, and cryptographic operations.

## Architecture

```
QRLiveProtocol (Main Coordinator)
├── QRGenerator (QR code creation and styling)
├── TimeProvider (NTP and HTTP time synchronization)
├── BlockchainVerifier (Multi-chain block hash verification)
├── IdentityManager (System and file-based identity hashing)
├── KeyManager (RSA/ECDSA key generation and management)
├── QRSignatureManager (Digital signature creation and verification)
├── DataEncryptor (AES-256 encryption for sensitive data)
└── HMACManager (HMAC-SHA256 integrity verification)
```

## Key Features

### 🔲 Live QR Generation
- Real-time QR code generation with configurable update intervals
- Multiple QR styles (live, professional, minimal)
- Text overlays with verification information
- Support for custom user data inclusion

### ⏰ Time Synchronization
- Multi-server NTP synchronization for accurate timestamps
- HTTP time API fallbacks for redundancy
- Configurable time drift tolerance
- Median offset calculation for robustness

### 🔗 Blockchain Verification
- Support for Bitcoin, Ethereum, Litecoin, and Dogecoin
- Real-time block hash retrieval and caching
- Configurable cache duration and retry logic
- API endpoint redundancy for reliability

### 🆔 Identity Management
- System fingerprinting (hostname, MAC address, etc.)
- File hash integration for document verification
- Custom data support for specific use cases
- Export/import capabilities for identity portability

### 🔐 Cryptographic Security
- **HMAC-SHA256** for data integrity verification (always applied)
- **RSA/ECDSA digital signatures** for authenticity proof (optional)
- **AES-256-GCM encryption** for sensitive field protection (optional)
- Secure key generation and management with encrypted storage

## Usage Examples

### Basic QR Generation
```python
from src import QRLiveProtocol

# Initialize with default configuration
qrlp = QRLiveProtocol()

# Generate basic QR code
qr_data, qr_image = qrlp.generate_single_qr()
print(f"Generated QR #{qr_data.sequence_number} at {qr_data.timestamp}")

# Verify the QR data
verification = qrlp.verify_qr_data(qr_data.to_json())
assert verification['hmac_verified'] == True  # HMAC always verified
```

### Cryptographically Enhanced QR
```python
# Generate key for signing
public_key, private_key = qrlp.key_manager.generate_keypair(
    algorithm="rsa", key_size=2048, purpose="qr_signing"
)

# Generate signed QR
user_data = {"event": "livestream", "topic": "QRLP Demo"}
qr_data, qr_image = qrlp.generate_signed_qr(user_data)

# Verify signature
verification = qrlp.verify_qr_data(qr_data.to_json())
assert verification['signature_verified'] == True
assert verification['identity_verified'] == True
```

### Encrypted QR Data
```python
# Generate encrypted QR with sensitive data
sensitive_data = {"user_id": "secret_user_123", "private_info": "classified"}
qr_data, qr_image = qrlp.generate_encrypted_qr(sensitive_data)

# Verify encryption and decryption
verification = qrlp.verify_qr_data(qr_data.to_json())
assert verification['encrypted'] == True
assert verification['hmac_verified'] == True

# Access decrypted data (requires proper key)
if verification['encrypted']:
    decrypted_data = qrlp.encryptor.decrypt_qr_payload(qr_data.__dict__)
    print(f"Decrypted: {decrypted_data['user_data']}")
```

### Live Generation with Callbacks
```python
# Set up callback for QR updates
def handle_qr_update(qr_data, qr_image):
    print(f"New QR generated: #{qr_data.sequence_number}")
    # Save image to file
    with open(f"qr_{qr_data.sequence_number}.png", "wb") as f:
        f.write(qr_image)

qrlp.add_update_callback(handle_qr_update)

# Start live generation (runs in background thread)
qrlp.start_live_generation()

# Generate QR codes continuously...
# Press Ctrl+C to stop
```

### Cross-Instance Verification
```python
# Generate QR with first instance
qrlp1 = QRLiveProtocol()
qr_data, qr_image = qrlp1.generate_single_qr({"test": "cross_instance"})

# Verify with second instance (simulates external verification)
qrlp2 = QRLiveProtocol()
qrlp2.key_manager = qrlp1.key_manager  # Share key manager

verification = qrlp2.verify_qr_data(qr_data.to_json())
assert verification['hmac_verified'] == True
assert verification['identity_verified'] == True
```

## Configuration

### Basic Configuration
```python
from src.config import QRLPConfig

config = QRLPConfig()
config.update_interval = 2.0  # Update every 2 seconds
config.qr_settings.error_correction_level = "H"  # High error correction

qrlp = QRLiveProtocol(config)
```

### Cryptographic Configuration
```python
config = QRLPConfig()

# QR settings for better visibility
config.qr_settings.box_size = 12
config.qr_settings.border_size = 6

# Blockchain verification (optional but recommended)
config.blockchain_settings.enabled_chains = {"bitcoin", "ethereum"}
config.blockchain_settings.cache_duration = 300  # 5 minutes

# Time synchronization settings
config.time_settings.time_servers = [
    "time.nist.gov",
    "pool.ntp.org",
    "time.google.com"
]
config.time_settings.update_interval = 60.0  # Update every minute

# Identity settings
config.identity_settings.auto_generate = True
config.identity_settings.include_system_info = True

qrlp = QRLiveProtocol(config)
```

### Security Configuration
```python
config = QRLPConfig()

# Enable all security features
config.verification_settings.require_blockchain = True
config.verification_settings.require_time_server = True
config.verification_settings.max_time_drift = 30.0  # 30 second tolerance

# Web server security (if using web interface)
config.web_settings.cors_enabled = True  # Enable CORS for API access

qrlp = QRLiveProtocol(config)
```

## API Reference

### QRLiveProtocol Class

#### Initialization
```python
QRLiveProtocol(config: QRLPConfig = None)
```
Initialize QRLP with optional configuration. Uses default configuration if none provided.

#### Core Methods

**`generate_single_qr(user_data=None, sign_data=True, encrypt_data=False)`**
Generate a single QR code with current verification data.

**`generate_signed_qr(user_data=None, signing_key_id=None)`**
Generate a QR code with digital signature using specified key.

**`generate_encrypted_qr(user_data=None, encryption_key_id=None)`**
Generate a QR code with encrypted sensitive data.

**`verify_qr_data(qr_json: str) -> Dict[str, bool]`**
Verify QR code data integrity and authenticity.

**`start_live_generation()`**
Start continuous QR code generation in background thread.

**`stop_live_generation()`**
Stop continuous QR code generation.

**`add_update_callback(callback)`**
Add callback function for QR update events.

**`get_statistics() -> Dict`**
Get performance and usage statistics.

### Verification Results

The `verify_qr_data()` method returns a dictionary with verification status:

```python
{
    "valid_json": True,           # JSON parsing successful
    "identity_verified": True,    # Identity hash matches
    "time_verified": True,        # Timestamp within tolerance
    "blockchain_verified": True,  # Blockchain hashes current
    "signature_verified": True,   # Digital signature valid
    "hmac_verified": True,        # HMAC integrity check passed
    "encrypted": False            # Data was encrypted
}
```

## Error Handling

### Exception Hierarchy
```python
QRLiveProtocolError(Exception)
├── ConfigurationError(ValueError)     # Invalid configuration
├── CryptoError(Exception)            # Cryptographic operation failed
│   ├── KeyError(CryptoError)         # Key management error
│   ├── SignatureError(CryptoError)   # Signature operation error
│   └── EncryptionError(CryptoError)  # Encryption operation error
└── ValidationError(ValueError)        # Input validation error
```

### Error Handling Patterns
```python
try:
    qr_data, qr_image = qrlp.generate_single_qr(user_data)
except ConfigurationError as e:
    print(f"Configuration issue: {e}")
    # Fix configuration and retry
except CryptoError as e:
    print(f"Cryptographic error: {e}")
    # Continue with reduced functionality
    qr_data, qr_image = qrlp.generate_single_qr(user_data, sign_data=False)
except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle unexpected errors gracefully
```

## Performance Considerations

### Response Times
- **QR Generation**: < 100ms for basic generation
- **Cryptographic Operations**: < 50ms for signing/encryption
- **Verification**: < 20ms for full verification
- **Memory Usage**: ~50MB base + 10MB per 1000 cached QRs

### Optimization Strategies
```python
# Caching for performance
qrlp = QRLiveProtocol()
qrlp._qr_cache_ttl = 60      # Cache QR images for 1 minute
qrlp._max_cache_size = 1000  # Limit cache size

# Reduce update frequency for better performance
config = QRLPConfig()
config.update_interval = 5.0  # Update every 5 seconds instead of 1
```

### Memory Management
```python
# Monitor memory usage
import psutil
process = psutil.Process()
memory_mb = process.memory_info().rss / 1024 / 1024

# Clean caches if memory usage is high
if memory_mb > 200:  # 200MB threshold
    qrlp._cleanup_expired_caches()
```

## Security Best Practices

### Key Management
```python
# Generate keys for different purposes
key_manager = qrlp.key_manager

# Signing key for QR authenticity
signing_key_id = key_manager.generate_keypair(
    algorithm="rsa", key_size=2048, purpose="qr_signing"
)[1]  # Returns (public, private) tuple

# Encryption key for sensitive data
encryption_key_id = key_manager.generate_keypair(
    algorithm="rsa", key_size=2048, purpose="qr_encryption"
)[1]

# List and manage keys
keys = key_manager.list_keys()
for key_id, key_info in keys.items():
    print(f"Key {key_id}: {key_info.algorithm} {key_info.key_size}bit, "
          f"used {key_info.usage_count} times")
```

### Input Validation
```python
# Always validate inputs before processing
def safe_qr_generation(qrlp, user_data):
    # Validate user data
    if not isinstance(user_data, dict):
        raise ValueError("User data must be a dictionary")

    if len(str(user_data)) > 1000:
        raise ValueError("User data too large")

    # Generate with validated data
    return qrlp.generate_single_qr(user_data)
```

### Secure Configuration
```python
# Use secure configuration for production
config = QRLPConfig()

# Enable all security features
config.verification_settings.require_blockchain = True
config.verification_settings.require_time_server = True
config.verification_settings.max_time_drift = 30.0

# Use strong identity verification
config.identity_settings.include_system_info = True
config.identity_settings.hash_algorithm = "sha256"

# Secure web server settings (if using web interface)
config.web_settings.cors_enabled = False  # Disable CORS for production
config.web_settings.debug = False        # Disable debug mode

qrlp = QRLiveProtocol(config)
```

## Integration Examples

### Flask Web Application
```python
from flask import Flask, jsonify
from src import QRLiveProtocol

app = Flask(__name__)
qrlp = QRLiveProtocol()

@app.route('/api/qr/current')
def get_current_qr():
    """Get current QR code data and image."""
    qr_data, qr_image = qrlp.generate_single_qr()
    return jsonify({
        'data': qr_data.__dict__,
        'image_base64': base64.b64encode(qr_image).decode()
    })

@app.route('/api/verify', methods=['POST'])
def verify_qr():
    """Verify QR code data."""
    qr_json = request.json['qr_data']
    results = qrlp.verify_qr_data(qr_json)
    return jsonify(results)

if __name__ == '__main__':
    qrlp.start_live_generation()
    app.run(port=8080)
```

### OBS Studio Integration
```python
# For livestreaming integration
qrlp = QRLiveProtocol()

# Generate QR for current stream
stream_data = {"stream_id": "my_livestream", "title": "QRLP Demo"}
qr_data, qr_image = qrlp.generate_signed_qr(stream_data)

# Save QR image for OBS browser source
with open("current_qr.png", "wb") as f:
    f.write(qr_image)

# OBS Studio: Add Browser Source pointing to current_qr.png
# QR updates every few seconds with new signatures
```

### Batch Processing
```python
# Generate multiple QR codes for batch processing
qrlp = QRLiveProtocol()

qr_codes = []
for i in range(10):
    qr_data, qr_image = qrlp.generate_single_qr({"batch": i, "item": f"item_{i}"})
    qr_codes.append((qr_data, qr_image))

    # Verify each QR
    verification = qrlp.verify_qr_data(qr_data.to_json())
    assert verification['hmac_verified'] == True

print(f"Generated and verified {len(qr_codes)} QR codes")
```

## Testing

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/test_core/ -v
pytest tests/test_crypto/ -v
pytest tests/test_integration/ -v

# Run with coverage
pytest --cov=src tests/

# Run performance tests
pytest tests/test_performance/ -v
```

### Test Structure
```python
# Unit tests for individual components
tests/test_core/test_qrlive_protocol.py
tests/test_crypto/test_key_manager.py
tests/test_crypto/test_signer.py

# Integration tests for component interaction
tests/test_integration/test_full_workflow.py

# Performance tests
tests/test_performance/test_load.py

# Security tests
tests/test_security/test_crypto_security.py
```

## Troubleshooting

### Common Issues

**QR Generation Fails**
```python
# Check configuration
config = QRLPConfig()
issues = config.validate()
if issues:
    print(f"Configuration issues: {issues}")

# Check component initialization
qrlp = QRLiveProtocol(config)
stats = qrlp.get_statistics()
print(f"Component status: {stats}")
```

**Verification Fails**
```python
# Debug verification process
qr_data, qr_image = qrlp.generate_single_qr()
qr_json = qr_data.to_json()

# Step-by-step verification
results = qrlp.verify_qr_data(qr_json)
print(f"Verification results: {results}")

# Check specific failure reasons
if not results['hmac_verified']:
    print("HMAC verification failed - data may be corrupted")
if not results['identity_verified']:
    print("Identity verification failed - wrong identity hash")
```

**Performance Issues**
```python
# Monitor performance
import time
start = time.time()

for i in range(100):
    qr_data, qr_image = qrlp.generate_single_qr()

end = time.time()
avg_time = (end - start) / 100
print(f"Average generation time: {avg_time:.3f}s")

# Optimize if too slow
if avg_time > 0.1:
    config = QRLPConfig()
    config.update_interval = 2.0  # Reduce update frequency
    config.blockchain_settings.cache_duration = 600  # Longer cache
    qrlp = QRLiveProtocol(config)
```

## Advanced Features

### Custom Cryptographic Operations
```python
# Direct cryptographic operations
key_manager = qrlp.key_manager
encryptor = qrlp.encryptor
hmac_manager = qrlp.hmac_manager

# Generate custom key
key_id = key_manager.generate_keypair("ecdsa", 256, "custom_signing")[1]

# Encrypt sensitive data
sensitive_data = {"api_key": "secret_key_123"}
encrypted = encryptor.encrypt_sensitive_data(sensitive_data)

# Create HMAC for integrity
data_hmac = hmac_manager.generate_hmac(sensitive_data)[0]

# Verify HMAC
is_valid = hmac_manager.verify_hmac(sensitive_data, data_hmac)
assert is_valid == True
```

### Multi-Signature Support (Future)
```python
# Framework for multi-signature support
def create_multi_signed_qr(qr_data, signing_keys):
    """Create QR with multiple signatures (future feature)."""
    signatures = []

    for key_id in signing_keys:
        signature, _ = signature_manager.sign_qr_with_key(qr_data, key_id)
        signatures.append((key_id, signature))

    # Combine signatures in QR data
    multi_signed_data = qr_data.copy()
    multi_signed_data['multi_signatures'] = signatures

    return multi_signed_data
```

### Hardware Security Module Integration (Future)
```python
# Framework for HSM integration
class HSMKeyManager(KeyManager):
    """Key manager with HSM support (future feature)."""

    def __init__(self, hsm_config):
        super().__init__()
        self.hsm = HardwareSecurityModule(hsm_config)

    def generate_keypair(self, algorithm="rsa", key_size=2048, purpose="general"):
        """Generate key pair using HSM."""
        # Use HSM for secure key generation
        return self.hsm.generate_keypair(algorithm, key_size, purpose)
```

## Contributing

### Development Workflow
1. **Write failing test first** - Define expected behavior
2. **Implement minimal functionality** - Make test pass
3. **Add cryptographic enhancements** - Integrate security features
4. **Ensure comprehensive error handling** - Cover all edge cases
5. **Update documentation** - Document new features and usage

### Code Review Checklist
- [ ] All public methods have proper type hints
- [ ] Comprehensive error handling with specific exception types
- [ ] Cryptographic operations are properly integrated
- [ ] Tests pass and provide good coverage
- [ ] Documentation is accurate and complete
- [ ] Security considerations are addressed
- [ ] Performance impact is acceptable

### Testing Guidelines
- Write unit tests for all new functionality
- Include integration tests for component interaction
- Add performance tests for optimization validation
- Create security tests for cryptographic operations
- Test error conditions and edge cases

This core module provides the foundation for all QRLP functionality with comprehensive cryptographic security, extensive testing, and production-ready features.

