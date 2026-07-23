# QRLP API Reference

Complete reference for integrating QRLP into your applications with Python, REST, and WebSocket APIs.

## 📋 Table of Contents

- [Python API](#python-api)
  - [QRLiveProtocol Class](#qrliveprotocol-class)
  - [QRData Class](#qrdata-class)
  - [Configuration Classes](#configuration-classes)
- [REST API](#rest-api)
- [WebSocket API](#websocket-api)
- [Command Line Interface](#command-line-interface)
- [Integration Examples](#integration-examples)
- [Error Handling](#error-handling)
- [Performance Considerations](#performance-considerations)

## 🐍 Python API

The primary interface for integrating QRLP into Python applications.

### QRLiveProtocol Class

The main coordinator class that orchestrates all QRLP components including QR generation, time synchronization, blockchain verification, and identity management.

#### Constructor

```python
from src import QRLiveProtocol, QRLPConfig

# Initialize with default configuration
qrlp = QRLiveProtocol()

# Initialize with custom configuration
config = QRLPConfig()
config.update_interval = 2.0
config.blockchain_settings.enabled_chains = {"bitcoin", "ethereum"}
qrlp = QRLiveProtocol(config)

# Initialize with configuration file
config = QRLPConfig.from_file("custom_config.json")
qrlp = QRLiveProtocol(config)
```

**Parameters:**
- `config` (QRLPConfig, optional): Configuration object. Uses defaults if None.

**Raises:**
- `ConfigurationError`: If configuration is invalid
- `ImportError`: If required dependencies are missing

#### Core Methods

##### `start_live_generation()`

Start continuous QR code generation in a background thread with automatic updates.

```python
# Start live generation (non-blocking)
qrlp.start_live_generation()

# QRLP will now generate QR codes every update_interval seconds
# Use callbacks to handle updates (see add_update_callback)
```

**Behavior:**
- Runs in background thread to avoid blocking
- Updates QR codes at configured intervals
- Triggers callbacks on each update
- Continues until `stop_live_generation()` is called

**Example with Callback:**
```python
def on_qr_update(qr_data, qr_image):
    print(f"New QR generated: #{qr_data.sequence_number}")
    # Save to file, send to API, etc.
    with open(f"qr_{qr_data.sequence_number}.png", "wb") as f:
        f.write(qr_image)

qrlp.add_update_callback(on_qr_update)
qrlp.start_live_generation()
```

##### `stop_live_generation()`

Stop continuous QR code generation and cleanup background thread.

```python
qrlp.stop_live_generation()
# Background thread stops gracefully
# All callbacks are preserved for next start
```

##### `generate_single_qr(user_data=None, sign_data=True, encrypt_data=False)`

Generate a single QR code with current verification data and optional cryptographic enhancements.

**Parameters:**
- `user_data` (dict, optional): Custom data to include in QR code payload
- `sign_data` (bool, optional): Apply digital signature (default: True)
- `encrypt_data` (bool, optional): Encrypt sensitive fields (default: False)

**Returns:**
- `tuple[QRData, bytes]`: (QR data object, QR image as PNG bytes)

**Examples:**

```python
# Basic QR generation
qr_data, qr_image = qrlp.generate_single_qr()

# With custom event data
event_data = {
    "event": "Product Launch",
    "presenter": "CEO",
    "timestamp": "2025-01-11T15:30:00Z"
}
qr_data, qr_image = qrlp.generate_single_qr(event_data)

# With user text (from web interface)
user_data = {"user_text": "Welcome to my livestream!"}
qr_data, qr_image = qrlp.generate_single_qr(user_data)

# Maximum security (signed + encrypted)
qr_data, qr_image = qrlp.generate_single_qr(
    user_data={"sensitive": "data"},
    sign_data=True,
    encrypt_data=True
)
```

##### `verify_qr_data(qr_json)`

Comprehensive verification of QR code data with multi-layered security checks.

**Parameters:**
- `qr_json` (str): JSON string extracted from QR code

**Returns:**
- `dict`: Detailed verification results with all security checks

**Verification Layers:**
- **JSON Validation**: Structural integrity check
- **HMAC Verification**: Local/shared-secret integrity check
- **Digital Signature**: Public-key verification when the verifier trusts the issuer key
- **Identity Verification**: Local identity match or trusted signed issuer
- **Time Verification**: Timestamp within acceptable drift and optional expiry window
- **Blockchain Context**: Current block hash comparison when configured; not an on-chain content commitment
- **Encryption Check**: Detects if data was encrypted

```python
# Basic verification
qr_json = '{"timestamp":"2025-01-16T...","identity_hash":"abc123..."}'
results = qrlp.verify_qr_data(qr_json)

print(f"Valid JSON: {results['valid_json']}")
print(f"Identity verified: {results['identity_verified']}")
print(f"Time verified: {results['time_verified']}")
print(f"Blockchain verified: {results['blockchain_verified']}")
print(f"HMAC verified: {results['hmac_verified']}")
print(f"Signature verified: {results['signature_verified']}")
print(f"Encrypted: {results['encrypted']}")
print(f"Overall valid: {results['valid']}")
print(f"Trust mode: {results['trust_mode']}")

# Complete verification example
def verify_qr_completely(qr_json):
    results = qrlp.verify_qr_data(qr_json)

    if not results['valid_json']:
        return False, "Invalid JSON structure"

    if not results['hmac_verified']:
        return False, "Data integrity compromised"

    if not results['identity_verified']:
        return False, "Identity verification failed"

    if not results['time_verified']:
        return False, "Timestamp outside acceptable window"

    return results['valid'], "QR code accepted" if results['valid'] else "QR code rejected"
```

**Verification Results Dictionary:**
```python
{
    "valid_json": bool,           # JSON parsing successful
    "identity_verified": bool,    # Identity hash matches
    "time_verified": bool,        # Timestamp within drift tolerance
    "blockchain_verified": bool,  # Blockchain hashes current
    "signature_verified": bool,   # Digital signature valid (if present)
    "hmac_verified": bool,        # HMAC integrity check passed
    "encrypted": bool,           # Data was encrypted
    "valid": bool,               # Overall verifier decision
    "trust_mode": str,           # none/local_hmac/local_signature/public_signature
    "error": str                 # Error message (if valid_json=False)
}
```

#### Event Handling

##### `add_update_callback(callback)`

Register a callback function to be invoked whenever a new QR code is generated during live operation.

**Parameters:**
- `callback` (Callable[[QRData, bytes], None]): Function that receives (qr_data, qr_image_bytes)

**Callback Signature:**
```python
def my_callback(qr_data: QRData, qr_image: bytes) -> None:
    """Handle QR code updates."""
    # Process the new QR code
    print(f"Generated QR #{qr_data.sequence_number}")

    # Save to file
    with open(f"qr_{qr_data.sequence_number}.png", "wb") as f:
        f.write(qr_image)

    # Send to external service
    send_to_streaming_platform(qr_data, qr_image)

    # Update database
    save_to_database(qr_data)
```

**Multiple Callbacks:**
```python
# Add multiple handlers
qrlp.add_update_callback(save_to_disk_handler)
qrlp.add_update_callback(send_to_api_handler)
qrlp.add_update_callback(update_database_handler)

# Start live generation - all callbacks will be triggered
qrlp.start_live_generation()
```

##### `remove_update_callback(callback)`

Remove a previously registered callback function.

**Parameters:**
- `callback` (Callable): The callback function to remove

##### `set_user_data_callback(callback)`

Set a callback function to dynamically provide user data for each QR generation.

**Parameters:**
- `callback` (Callable[[], Optional[str]]): Function that returns user input string or None

**Example:**
```python
def get_live_user_input():
    """Get user input from web interface or external source."""
    # This could read from a file, database, or web request
    return get_latest_chat_message() or None

qrlp.set_user_data_callback(get_live_user_input)
qrlp.start_live_generation()
# Now each QR will include current user input
```

#### Monitoring & Statistics

##### `get_statistics()`

Retrieve comprehensive performance and usage statistics for monitoring and debugging.

**Returns:**
- `dict`: Statistics dictionary with component-level metrics

**Statistics Structure:**
```python
{
    "running": bool,                    # Whether live generation is active
    "total_updates": int,              # Total QR codes generated
    "sequence_number": int,            # Current sequence number
    "last_update_time": float,         # Unix timestamp of last update
    "current_qr_data": dict or None,   # Most recent QR data (if available)

    # Component statistics
    "time_provider_stats": {
        "success_rate": float,         # NTP synchronization success rate
        "active_servers": int,         # Currently responding time servers
        "last_sync": float             # Last successful synchronization
    },

    "blockchain_stats": {
        "success_rate": float,         # Blockchain API success rate
        "cached_chains": list,         # Currently cached blockchain networks
        "last_update": float           # Last blockchain data update
    },

    "identity_stats": {
        "hash_generations": int,       # Identity hash generation count
        "file_count": int,             # Files included in identity
        "last_hash": str               # Last generated identity hash
    },

    "crypto_stats": {
        "keys_count": int,             # Number of cryptographic keys
        "signature_count": int,        # Digital signatures created
        "encryption_enabled": bool,    # Whether encryption is active
        "hmac_enabled": bool           # Whether HMAC is active (always True)
    }
}
```

**Usage Example:**
```python
# Monitor QRLP performance
stats = qrlp.get_statistics()

print("=== QRLP Status ===")
print(f"Running: {'✅' if stats['running'] else '❌'}")
print(f"Updates: {stats['total_updates']}")
print(f"Sequence: #{stats['sequence_number']}")

print("\n=== Component Health ===")
print(f"Time sync: {stats['time_provider_stats']['success_rate']:.1%}")
print(f"Blockchain: {stats['blockchain_stats']['success_rate']:.1%}")
print(f"Active chains: {stats['blockchain_stats']['cached_chains']}")

# Check for issues
if stats['time_provider_stats']['success_rate'] < 0.8:
    print("⚠️  Time synchronization issues detected")

if not stats['blockchain_stats']['cached_chains']:
    print("⚠️  No blockchain data available")
```

### QRData Class

Data structure representing the complete payload of a QR code, including freshness metadata, issuer identity, and optional cryptographic checks.

#### Attributes

```python
@dataclass
class QRData:
    timestamp: str                    # ISO 8601 timestamp (e.g., "2025-01-11T15:30:45.123456Z")
    identity_hash: str               # SHA-256 hash of system/file identity
    blockchain_hashes: Dict[str, str] # Blockchain network -> latest block hash mapping
    time_server_verification: Dict   # Time server responses and verification status
    user_data: Optional[Dict] = None  # Custom user data
    sequence_number: int = 0         # Incremental sequence number for this QR
    issuer_id: Optional[str] = None   # Public issuer identifier for signature verification
    event_id: Optional[str] = None    # Event or stream namespace
    content_hash: Optional[str] = None # SHA-256 of user_data
    expires_at: Optional[str] = None  # Optional expiry timestamp
    nonce: Optional[str] = None       # Random nonce for replay resistance

    # Cryptographic enhancement fields
    digital_signature: Optional[str] = None      # Digital signature of QR data
    signing_key_id: Optional[str] = None        # ID of key used for signing
    signature_algorithm: Optional[str] = None   # Signature algorithm ("rsa" or "ecdsa")
    _hmac: Optional[str] = None                 # HMAC for integrity verification
    _hmac_key_id: Optional[str] = None          # HMAC key identifier
    _hmac_algorithm: Optional[str] = None       # HMAC algorithm (e.g., "sha256")
    _integrity_checked_at: Optional[str] = None # When integrity was last checked
    _encrypted_fields: Optional[List[str]] = None # List of encrypted field names
    _encryption_key_id: Optional[str] = None    # Encryption key identifier
    _data_key_id: Optional[str] = None          # Data encryption key ID
    _encrypted_at: Optional[str] = None         # Encryption timestamp
```

#### Core Methods

##### `to_json()`

Convert QRData to compact JSON string suitable for QR code encoding.

```python
qr_data = QRData(...)
json_str = qr_data.to_json()
# Returns: '{"timestamp":"2025-01-11T15:30:45Z","identity_hash":"abc123..."}'

# Use for QR generation
qr_image = qrlp.qr_generator.generate_qr_image(json_str)
```

**Notes:**
- Uses compact JSON formatting (no extra whitespace)
- Only includes non-None values for smaller QR codes
- Safe for QR encoding (deterministic output)
- Signed payload verification canonicalizes the JSON before checking signatures

##### `from_json(json_str)`

Create QRData instance from JSON string (class method).

```python
# Reconstruct from QR scan
qr_json = '{"timestamp":"2025-01-11T15:30:45Z","identity_hash":"abc123..."}'
qr_data = QRData.from_json(qr_json)

print(f"Timestamp: {qr_data.timestamp}")
print(f"Identity: {qr_data.identity_hash[:16]}...")
```

**Raises:**
- `json.JSONDecodeError`: If JSON is malformed
- `TypeError`: If required fields are missing
- `ValueError`: If field values are invalid

### QRGenerator Large Payload Handling

`generate_qr_image()` generates one QR code and raises `QRDataTooLargeError` when the payload cannot fit in a single version-40 QR code at the configured error correction level. Use the explicit chunk API for large payloads:

```python
from src import QRGenerator, QRDataTooLargeError
from src.config import QRSettings

generator = QRGenerator(QRSettings(error_correction_level="M"))
payload = "large payload" * 1000

try:
    image = generator.generate_qr_image(payload)
except QRDataTooLargeError:
    chunk_payloads = generator.generate_chunked_payloads(payload)
    images = generator.generate_chunked_qr_codes(payload)
    recovered = QRGenerator.reassemble_chunked_payloads(chunk_payloads)
    assert recovered == payload
```

Chunk payloads are JSON records with `protocol`, `chunk_index`, `total_chunks`, `data_size`, `data_sha256`, and base64 chunk data. Reassembly rejects malformed, duplicated, missing, incompatible, or checksum-invalid chunks.


### VerificationResult Class

The `VerificationResult` dataclass (added in v1.2.0) provides a typed result
for QR data verification, replacing the previously untyped dictionary.

```python
from src import VerificationResult

# Returned by QRLiveProtocol.verify_qr_data()
result = qrlp.verify_qr_data(qr_json)
# result is a dict with keys: valid_json, identity_verified, time_verified,
# blockchain_verified, signature_verified, hmac_verified, encrypted, valid,
# trust_mode, error

# VerificationResult dataclass can be used directly:
from src.core import VerificationResult
vr = VerificationResult(valid_json=True, valid=True, trust_mode="public_signature")
print(vr.to_dict())
```

### Crypto Exception Classes

QRLP exports the following exception classes from `src.crypto`:

- `CryptoError` — base exception for all crypto operations
- `KeyManagementError` — key management errors (renamed from `KeyError` in v1.1.0)
- `SignatureError` — digital signature errors
- `EncryptionError` — encryption/decryption errors
- `HMACError` — HMAC operation errors (exported since v1.1.0)

### Configuration Classes

Comprehensive configuration system for customizing QRLP behavior across all components.

#### QRLPConfig

Main configuration container that holds all settings for QRLP components.

```python
from src.config import QRLPConfig

# Create default configuration
config = QRLPConfig()

# Customize core settings
config.update_interval = 5.0                    # Seconds between QR updates
config.verification_settings.max_time_drift = 30.0  # Max acceptable time difference

# Configure QR appearance
config.qr_settings.box_size = 12               # QR code pixel size
config.qr_settings.error_correction_level = "M"  # Error correction: L, M, Q, H
config.qr_settings.border_size = 4             # Border width in boxes
config.qr_settings.fill_color = "black"        # QR foreground color
config.qr_settings.back_color = "white"        # QR background color

# Configure web interface
config.web_settings.port = 8080                # Web server port
config.web_settings.host = "localhost"         # Bind address
config.web_settings.auto_open_browser = True   # Auto-open browser on start
config.web_settings.cors_enabled = False       # Enable CORS for API access

# Configure blockchain verification
config.blockchain_settings.enabled_chains = {"bitcoin", "ethereum"}
config.blockchain_settings.cache_duration = 300  # Cache blockchain data (seconds)
config.blockchain_settings.timeout = 10.0       # API timeout
config.blockchain_settings.retry_attempts = 3   # Retry failed requests

# Configure time synchronization
config.time_settings.time_servers = [
    "time.nist.gov", "pool.ntp.org", "time.google.com"
]
config.time_settings.update_interval = 60.0     # Time sync frequency
config.time_settings.timeout = 5.0             # Time server timeout

# Configure identity management
config.identity_settings.identity_file = None   # Custom identity file
config.identity_settings.auto_generate = True   # Generate identity automatically
config.identity_settings.include_system_info = True  # Include system fingerprint
config.identity_settings.hash_algorithm = "sha256"   # Hash algorithm for identity

# Advanced settings
config.logging_settings.level = "INFO"         # Logging level
config.logging_settings.log_file = None        # Log file path
config.security_settings.encrypt_qr_data = False  # Encrypt QR payloads
config.security_settings.sign_qr_data = False     # Apply digital signatures by default
config.security_settings.issuer_id = "issuer-1"   # Public issuer identifier
config.security_settings.key_dir = "./keys"       # Local signing key directory
config.verification_settings.require_blockchain = False  # Require blockchain verification
```

#### Configuration Loading

**From File:**
```python
# Load from JSON file
config = QRLPConfig.from_file("config.json")

# Load from YAML file (requires PyYAML)
config = QRLPConfig.from_file("config.yaml")

# Load from environment variables
config = QRLPConfig.from_env()
```

**Validation:**
```python
# Check configuration validity
issues = config.validate()
if issues:
    print("Configuration issues:")
    for issue in issues:
        print(f"  - {issue}")
```

#### Nested Configuration Classes

##### QRSettings
Controls QR code generation and appearance.

```python
config.qr_settings.error_correction_level = "M"  # L(7%), M(15%), Q(25%), H(30%)
config.qr_settings.box_size = 10                 # Pixels per QR module
config.qr_settings.border_size = 4               # Border width in modules
config.qr_settings.fill_color = "#000000"        # Foreground color (hex or name)
config.qr_settings.back_color = "#ffffff"        # Background color
config.qr_settings.image_format = "PNG"          # Output image format
config.qr_settings.max_data_size = 2000          # Chunk size for explicit chunk APIs
```

##### WebSettings
Controls the web server and interface behavior.

```python
config.web_settings.host = "0.0.0.0"            # Bind address (0.0.0.0 for all interfaces)
config.web_settings.port = 8080                 # Server port
config.web_settings.auto_open_browser = True    # Auto-open browser on startup
config.web_settings.cors_enabled = False        # Enable CORS for API access
config.web_settings.cors_allowed_origins = []   # Specific trusted CORS origins
config.web_settings.admin_token = None          # Optional token for state changes
config.web_settings.rate_limit_per_minute = 120 # Basic in-memory request cap
config.web_settings.debug = False               # Enable debug mode
```

##### BlockchainSettings
Controls blockchain network integration and caching.

```python
config.blockchain_settings.enabled_chains = {
    "bitcoin", "ethereum", "litecoin"  # Networks to verify
}
config.blockchain_settings.cache_duration = 300  # Cache duration in seconds
config.blockchain_settings.timeout = 10.0       # API request timeout
config.blockchain_settings.retry_attempts = 3   # Retry count for failed requests
config.blockchain_settings.api_endpoints = {    # Custom API endpoints (optional)
    "bitcoin": "https://api.blockcypher.com/v1/btc/main",
    "ethereum": "https://api.blockcypher.com/v1/eth/main"
}
```

##### TimeSettings
Controls time synchronization and NTP server configuration.

```python
config.time_settings.time_servers = [           # NTP servers for synchronization
    "time.nist.gov", "pool.ntp.org", "time.google.com", "time.cloudflare.com"
]
config.time_settings.update_interval = 60.0     # Sync frequency in seconds
config.time_settings.timeout = 5.0             # Server timeout
config.time_settings.local_fallback = True      # Use system time as fallback
config.time_settings.timezone = "UTC"           # Display timezone
```

##### IdentitySettings
Controls identity generation and file inclusion.

```python
config.identity_settings.identity_file = "/path/to/identity.pem"  # Custom key file
config.identity_settings.auto_generate = True   # Generate identity if no file
config.identity_settings.include_system_info = True  # Include system fingerprint
config.identity_settings.include_file_hash = True     # Include identity file hash
config.identity_settings.hash_algorithm = "sha256"    # Hash algorithm: sha256, sha512, md5
```

##### VerificationSettings
Controls verification requirements and tolerances.

```python
config.verification_settings.max_time_drift = 300.0     # Max time difference (seconds)
config.verification_settings.require_blockchain = False # Require blockchain verification
config.verification_settings.require_time_server = False # Require time server verification
config.verification_settings.min_verifications = 1      # Minimum successful checks
```

##### SecuritySettings
Controls cryptographic security features.

```python
config.security_settings.encrypt_qr_data = False         # Encrypt QR payloads
config.security_settings.encryption_key = None          # Optional encryption key
config.security_settings.sign_qr_data = True            # Apply digital signatures by default
config.security_settings.key_dir = "./keys"             # Local key storage directory
config.security_settings.issuer_id = "issuer-1"         # Public issuer identifier
config.security_settings.event_id = "default"           # Event/session identifier
config.security_settings.signing_key_id = None          # Optional preferred key
config.security_settings.signature_algorithm = "rsa"    # rsa or ecdsa
config.security_settings.qr_ttl_seconds = None          # Defaults to max_time_drift
```

##### LoggingSettings
Controls logging behavior and output.

```python
config.logging_settings.level = "INFO"         # DEBUG, INFO, WARNING, ERROR, CRITICAL
config.logging_settings.log_file = None        # Log file path (None for console only)
config.logging_settings.max_file_size = 10485760  # Max log file size (10MB)
config.logging_settings.backup_count = 5       # Number of backup log files
config.logging_settings.format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## REST API

When running the web server, QRLP provides REST endpoints.

### Base URL
`http://localhost:8080` (default)

### Endpoints

#### `GET /api/status`
Get system status and statistics.

**Response:**
```json
{
  "is_running": true,
  "page_views": 42,
  "websocket_connections": 2,
  "qr_updates_sent": 156,
  "server_url": "http://localhost:8080",
  "current_qr_available": true
}
```

#### `GET /api/qr/current`
Get current QR code data and image.

**Response:**
```json
{
  "qr_data": {
    "timestamp": "2025-01-16T19:30:45.123Z",
    "identity_hash": "abc123def456...",
    "blockchain_hashes": {
      "bitcoin": "00000000000000000008a...",
      "ethereum": "0x1234567890abcdef..."
    },
    "time_server_verification": {...},
    "sequence_number": 123,
    "user_data": null
  },
  "qr_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "timestamp": "2025-01-16T19:30:45.456Z"
}
```

#### `POST /api/verify`
Verify QR code data with the server's configured verifier. The endpoint no longer treats syntactically valid JSON as authentic by itself.

**Request:**
```json
{
  "qr_data": "{\"timestamp\":\"2025-01-16T...\",\"identity_hash\":\"abc123...\"}"
}
```

**Response:**
```json
{
  "valid": true,
  "timestamp": "2025-01-16T19:30:45.789Z",
  "data_length": 768,
  "valid_json": true,
  "identity_verified": true,
  "time_verified": true,
  "blockchain_verified": false,
  "signature_verified": true,
  "hmac_verified": false,
  "encrypted": false,
  "trust_mode": "public_signature"
}
```

`valid` is true when the payload parses, time checks pass, required blockchain checks pass if configured, and either a trusted public signature or local HMAC/signature verifies. An unsigned `{}` response returns `valid: false`.

#### `GET /improve`
Render the improvement dashboard. This page summarizes implementation readiness, key/trust state, current QR state, and local smoke-test results.

#### `GET /api/improve/status`
Return dashboard-ready status JSON.

**Response:**
```json
{
  "readiness": {
    "passed": 5,
    "total": 5,
    "score": 1.0,
    "state": "ready"
  },
  "features": [
    {"name": "signed_qr_generation", "ok": true, "severity": "pass"},
    {"name": "public_key_trust_store", "ok": true, "severity": "pass"}
  ],
  "trust": {"trusted_key_count": 0, "trusted_keys": []},
  "keys": {"signing_key_count": 0, "signing_keys": []}
}
```

#### `POST /api/improve/smoke-test`
Run a deterministic local smoke test without external time or blockchain calls. The test generates a signed QR payload, trusts its public key, verifies it, and validates QR chunk reassembly.

**Response:**
```json
{
  "success": true,
  "signed_round_trip": {
    "valid": true,
    "trust_mode": "public_signature",
    "signature_verified": true
  },
  "chunk_recovery": {
    "valid": true,
    "chunk_count": 4
  }
}
```

#### `GET /api/user-data`
Get current user input data.

**Response:**
```json
{
  "user_data": "User's custom message text"
}
```

#### `POST /api/user-data`
Update user input data to be included in QR codes.

**Request:**
```json
{
  "user_text": "Custom message to include in QR codes"
}
```

**Response:**
```json
{
  "success": true,
  "message": "User data updated successfully",
  "user_data": "Custom message to include in QR codes"
}
```

**Error Response:**
```json
{
  "error": "User data too long (max 500 characters)"
}
```

## WebSocket API

Real-time updates via Socket.IO.

### Connection
```javascript
const socket = io('http://localhost:8080');
```

### Events

#### `connect`
Triggered when client connects to server.

```javascript
socket.on('connect', function() {
    console.log('Connected to QRLP server');
});
```

#### `qr_update`
Triggered when new QR code is generated.

```javascript
socket.on('qr_update', function(data) {
    console.log('New QR data:', data.qr_data);
    console.log('QR image:', data.qr_image);
});
```

#### `request_qr_update`
Request current QR code data.

```javascript
socket.emit('request_qr_update');
```

#### `update_user_data`
Send user data update to server.

```javascript
socket.emit('update_user_data', {
    user_text: "Custom message for QR codes"
});
```

#### `user_data_updated`
Triggered when user data is updated (broadcasted to all clients).

```javascript
socket.on('user_data_updated', function(data) {
    console.log('User data updated:', data.user_data);
    console.log('Timestamp:', data.timestamp);
});
```

#### `user_data_error`
Triggered when user data update fails.

```javascript
socket.on('user_data_error', function(error) {
    console.log('User data error:', error.error);
});
```

## Command Line Interface

### Global Options

- `--config, -c`: Configuration file path
- `--debug, -d`: Enable debug mode
- `--help, -h`: Show help message

### Commands

#### `qrlp live`
Start live QR generation with web interface.

```bash
# Basic usage
qrlp live

# Custom port and host
qrlp live --port 8081 --host 0.0.0.0

# No auto-browser
qrlp live --no-browser

# Custom update interval
qrlp live --interval 2.0

# With identity file
qrlp live --identity-file ./my-key.pem
```

**Options:**
- `--port`: Web server port (default: 8080)
- `--host`: Web server host (default: localhost)
- `--no-browser`: Don't auto-open browser
- `--interval`: Update interval in seconds
- `--identity-file`: Path to identity file

#### `qrlp dashboard`
Start QRLP and open the improvement dashboard at `/improve`.

```bash
# Basic usage
qrlp dashboard

# Start without opening a browser
qrlp dashboard --no-browser

# Custom port and interval
qrlp dashboard --port 8090 --interval 2.0
```

**Options:**
- `--port`: Web server port (default: 8080)
- `--host`: Web server host (default: localhost)
- `--no-browser`: Don't auto-open browser
- `--interval`: Update interval in seconds
- `--identity-file`: Path to identity file

#### `qrlp generate`
Generate single QR code.

```bash
# Basic generation
qrlp generate

# Save to file
qrlp generate --output qr_code.png

# With custom style
qrlp generate --style professional --include-text

# JSON data only
qrlp generate --format json --output data.json

# Both image and JSON
qrlp generate --format both --output qr_code

# Signed QR with verifier trust material
qrlp generate \
  --format both \
  --output qr_code \
  --user-data '{"event":"launch"}' \
  --sign \
  --public-key-output issuer.pem \
  --trust-record-output trust.json
```

**Options:**
- `--output, -o`: Output file path
- `--style`: QR style (live, professional, minimal)
- `--include-text`: Add text overlay
- `--format`: Output format (image, json, both)
- `--user-data`: JSON object to include in the QR payload
- `--sign/--no-sign`: Override signed QR generation
- `--key-id`: Signing key ID to use
- `--issuer-id`: Issuer ID embedded in signed payloads
- `--public-key-output`: Write signing public key PEM
- `--trust-record-output`: Write JSON trust store for verifier use

#### `qrlp verify`
Verify QR code data.

```bash
# Verify JSON string
qrlp verify '{"timestamp":"2025-01-16T...","identity_hash":"abc123..."}'

# Verify from file
qrlp verify --file qr_data.json

# Verify with public trust material
qrlp verify --file qr_data.json --trust-store trust.json

# Detailed output as JSON
qrlp verify --file qr_data.json --trust-store trust.json --json-output
```

**Options:**
- `--file, -f`: Read data from file
- `--public-key`: Trusted issuer public key PEM
- `--trust-store`: JSON trust store with issuer public keys
- `--issuer`: Issuer ID for `--public-key`
- `--key-id`: Signing key ID for `--public-key`
- `--json-output`: Print raw verification JSON
- `--verbose, -v`: Show raw verification JSON after summary

#### `qrlp keys`
Manage local signing keys.

```bash
qrlp keys generate --public-key-output issuer.pem
qrlp keys list
qrlp keys export-public <key-id> --output issuer.pem
```

#### `qrlp trust`
Manage JSON trust stores for external verification.

```bash
qrlp trust add --issuer issuer-1 --key-id <key-id> --public-key issuer.pem --store trust.json
qrlp trust list trust.json
```

#### `qrlp status`
Show current system status.

```bash
qrlp status
```

#### `qrlp config-init`
Create configuration file.

```bash
# Default location
qrlp config-init

# Custom location
qrlp config-init --output ./config.json

# With comments
qrlp config-init --with-comments
```

## Integration Examples

### Flask Integration

```python
from flask import Flask, jsonify
from src import QRLiveProtocol

app = Flask(__name__)
qrlp = QRLiveProtocol()

@app.route('/qr/generate')
def generate_qr():
    qr_data, qr_image = qrlp.generate_single_qr()
    return jsonify({
        'data': qr_data.__dict__,
        'image_base64': base64.b64encode(qr_image).decode()
    })

if __name__ == '__main__':
    qrlp.start_live_generation()
    app.run()
```

### FastAPI Integration

```python
from fastapi import FastAPI
from src import QRLiveProtocol
import base64

app = FastAPI()
qrlp = QRLiveProtocol()

@app.get("/qr/current")
async def get_current_qr():
    qr_data, qr_image = qrlp.generate_single_qr()
    return {
        "data": qr_data.__dict__,
        "image": base64.b64encode(qr_image).decode()
    }

@app.on_event("startup")
async def startup_event():
    qrlp.start_live_generation()
```

### Django Integration

```python
# views.py
from django.http import JsonResponse
from src import QRLiveProtocol
import base64

qrlp = QRLiveProtocol()
qrlp.start_live_generation()

def get_qr_code(request):
    qr_data, qr_image = qrlp.generate_single_qr()
    return JsonResponse({
        'data': qr_data.__dict__,
        'image': base64.b64encode(qr_image).decode()
    })
```

## Error Handling

### Common Exceptions

```python
from src.exceptions import QRLPError, ConfigurationError, BlockchainError

try:
    qrlp = QRLiveProtocol(config)
    qr_data, qr_image = qrlp.generate_single_qr()
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except BlockchainError as e:
    print(f"Blockchain verification failed: {e}")
except QRLPError as e:
    print(f"QRLP error: {e}")
```

### HTTP Error Responses

#### 400 Bad Request
```json
{
  "error": "Invalid QR data format",
  "details": "JSON parsing failed"
}
```

#### 404 Not Found
```json
{
  "error": "No QR data available",
  "message": "QR generation not started"
}
```

#### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "message": "Blockchain API temporarily unavailable"
}
```

## Performance Considerations

### Memory Usage
- Base memory usage: ~50MB
- Additional ~10MB per 1000 cached QR codes
- Blockchain cache: ~5MB per chain

### CPU Usage
- QR generation: ~1-5ms per QR code
- Blockchain verification: ~100-500ms (cached: ~1ms)
- Time synchronization: ~50-200ms (cached: ~1ms)

### Network Usage
- Blockchain API calls: ~1KB per request
- Time server queries: ~100 bytes per request
- Web interface: ~50KB initial load, ~5KB per QR update

### Optimization Tips

1. **Increase cache duration** for blockchain data
2. **Reduce update interval** for better performance
3. **Disable unused blockchain chains**
4. **Use local time servers** when possible
5. **Configure appropriate error correction level**

---

For more examples and advanced usage, see the [examples/](../examples/) directory.
