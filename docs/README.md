# QR Live Protocol (QRLP) Documentation

## Overview

The QR Live Protocol (QRLP) is a system for generating and displaying live QR codes with local HMAC integrity checks and optional public-key issuer verification. It's designed for livestreaming and official video releases where QR payloads need timing context and authenticity checks against trusted issuer keys.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Architecture](#architecture)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Security](#security)
- [Examples](#examples)
- [FAQ](#faq)
- [Contributing](#contributing)

## Quick Start

### 1. Installation

```bash
# Install QRLP (when available on PyPI)
pip install qr-live-protocol

# Or install from source with modern setup
git clone https://github.com/docxology/qr_live_protocol.git
cd qr_live_protocol

# Modern setup with uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e .[dev]

# Start live QR display
qrlp live
```

### 2. Start Live QR Display

```bash
# Start QRLP with default settings
qrlp live

# Start with custom port and no auto-browser
qrlp live --port 8080 --no-browser

# Start with custom identity file
qrlp live --identity-file ./my-identity.pem
```

### 3. Generate Single QR Code

```bash
# Generate QR code and save as PNG
qrlp generate --output qr_code.png

# Generate with JSON data
qrlp generate --format both --output verification_qr

# Generate with specific style
qrlp generate --style professional --include-text

# Generate signed QR plus trust-store material
qrlp generate --format both --output verification_qr --sign \
  --public-key-output issuer.pem \
  --trust-record-output trust.json

# Verify with trusted public key material
qrlp verify --file verification_qr.json --trust-store trust.json
```

## Architecture

QRLP consists of several key components:

### Core Components

1. **QRLiveProtocol** - Main coordinator that orchestrates all components
2. **QRGenerator** - Handles QR code creation and styling
3. **TimeProvider** - Manages time synchronization with multiple servers
4. **BlockchainVerifier** - Retrieves blockchain hashes for verification
5. **IdentityManager** - Manages user identity and file hashing
6. **QRLiveWebServer** - Provides web interface for live display

### Component Diagram

```
┌─────────────────────┐
│   QRLiveProtocol    │
├─────────────────────┤
│ - Coordinates all   │
│ - Manages callbacks │
│ - Live generation   │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌─────────────┐
│QRGenerator│  │TimeProvider │
├─────────┤  ├─────────────┤
│- Images │  │- NTP sync   │
│- Styles │  │- HTTP APIs  │
│- Cache  │  │- Fallback   │
└─────────┘  └─────────────┘
    │             │
    ▼             ▼
┌────────────┐ ┌──────────────┐
│Blockchain  │ │Identity      │
│Verifier    │ │Manager       │
├────────────┤ ├──────────────┤
│- Multi-    │ │- File hashes │
│  chain     │ │- System info │
│- Caching   │ │- Custom data │
└────────────┘ └──────────────┘
```

## Usage

### Command Line Interface

QRLP provides a comprehensive CLI for all operations:

```bash
# Main commands
qrlp live           # Start live QR generation with web interface
qrlp dashboard      # Start the improvement dashboard
qrlp generate       # Generate single QR code
qrlp verify         # Verify QR code data
qrlp keys           # Manage signing keys
qrlp trust          # Manage verifier trust stores
qrlp status         # Show current status and statistics
qrlp config-init    # Create configuration file
qrlp add-file       # Add file to identity

# Global options
--config, -c        # Configuration file path
--debug, -d         # Enable debug mode
```

### Python API

```python
from src import QRDataTooLargeError, QRGenerator, QRLiveProtocol, QRLPConfig

# Initialize with default configuration
qrlp = QRLiveProtocol()

# Generate single QR code
qr_data, qr_image = qrlp.generate_single_qr()

# Generate recoverable chunks when a payload exceeds single-QR capacity
large_payload = "large payload" * 1000
try:
    image = qrlp.qr_generator.generate_qr_image(large_payload)
except QRDataTooLargeError:
    chunks = qrlp.qr_generator.generate_chunked_payloads(large_payload)
    assert QRGenerator.reassemble_chunked_payloads(chunks) == large_payload

# Start live generation
qrlp.start_live_generation()

# Add callback for updates
def handle_update(qr_data, qr_image):
    print(f"New QR: #{qr_data.sequence_number}")

qrlp.add_update_callback(handle_update)
```

### Web Interface

The web interface provides:

- **Live QR Display** - Real-time QR code updates
- **Verification Information** - Time, blockchain, identity verification
- **Statistics** - Connection status, update counts
- **Controls** - Manual update requests, download, copy data

Access at: `http://localhost:8080` (default)

## Configuration

### Configuration File

Create a configuration file for customized behavior:

```bash
# Generate default configuration
qrlp config-init --output config.json
```

Example configuration:

```json
{
  "update_interval": 5.0,
  "qr_settings": {
    "error_correction_level": "M",
    "box_size": 10,
    "border_size": 4
  },
  "web_settings": {
    "host": "localhost",
    "port": 8080,
    "auto_open_browser": true
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum"],
    "cache_duration": 300
  },
  "time_settings": {
    "time_servers": [
      "time.nist.gov",
      "pool.ntp.org"
    ],
    "timeout": 5.0
  }
}
```

### Environment Variables

QRLP supports configuration via environment variables:

```bash
export QRLP_UPDATE_INTERVAL=10
export QRLP_WEB_PORT=8080
export QRLP_WEB_HOST=0.0.0.0
export QRLP_IDENTITY_FILE=/path/to/identity.json
export QRLP_LOG_LEVEL=DEBUG
```

## Security

### Identity Management

QRLP creates unique identity hashes based on:

- System information (hostname, MAC address, etc.)
- File hashes (configurable files)
- Custom data (user-defined)
- Creation timestamp

### Verification Layers

1. **Time Verification** - Timestamp drift checks and optional time-server evidence
2. **Blockchain Context** - Current block hashes from configured chains
3. **Issuer Verification** - Trusted public-key signatures when configured
4. **Format and Integrity Verification** - JSON structure plus HMAC/signature checks

### Best Practices

1. **Use HTTPS** - Always use HTTPS in production
2. **Secure Identity Files** - Protect identity files with appropriate permissions
3. **Trusted Public Keys** - Configure verifier trust roots for public authenticity
4. **Monitor Verification** - Check that all verification layers are working

## Examples

### Basic Live Streaming Setup

```bash
# Start QRLP for livestreaming
qrlp live --port 8080 --interval 10

# In OBS or streaming software:
# Add Browser Source: http://localhost:8080/viewer
```

### Custom Identity with Files

```python
from src import QRLiveProtocol, QRLPConfig

# Configure identity with specific files
config = QRLPConfig()
config.identity_settings.identity_file = "my_key.pem"

qrlp = QRLiveProtocol(config)

# Add additional files to identity
qrlp.identity_manager.add_file_to_identity("document.pdf", "document")
qrlp.identity_manager.add_file_to_identity("video.mp4", "video")

# Generate QR with file-based identity
qr_data, qr_image = qrlp.generate_single_qr()
```

### Verification Workflow

```python
import json
from src import QRLiveProtocol

# Initialize verifier
qrlp = QRLiveProtocol()

# QR data from scanning
qr_json = '{"timestamp":"2025-01-11T...","identity_hash":"abc123..."}'

# Verify the QR data
results = qrlp.verify_qr_data(qr_json)

print(f"Valid JSON: {results['valid_json']}")
print(f"Identity verified: {results['identity_verified']}")
print(f"Time verified: {results['time_verified']}")
print(f"Blockchain verified: {results['blockchain_verified']}")
```

### Integration with Flask App

```python
from flask import Flask
from src import QRLiveProtocol

app = Flask(__name__)
qrlp = QRLiveProtocol()

@app.route('/api/qr/current')
def get_current_qr():
    qr_data, qr_image = qrlp.generate_single_qr()
    return {
        'data': qr_data.__dict__,
        'image': base64.b64encode(qr_image).decode()
    }

@app.route('/api/verify', methods=['POST'])
def verify_qr():
    qr_json = request.json['qr_data']
    results = qrlp.verify_qr_data(qr_json)
    return results
```

## API Reference

### QRLiveProtocol Class

#### Methods

- `__init__(config: QRLPConfig = None)` - Initialize with configuration
- `start_live_generation()` - Start continuous QR generation
- `stop_live_generation()` - Stop QR generation
- `generate_single_qr(user_data: Dict = None)` - Generate one QR code
- `verify_qr_data(qr_json: str)` - Verify QR code data
- `get_statistics()` - Get performance statistics

#### Events/Callbacks

- `add_update_callback(callback)` - Add callback for QR updates
- `remove_update_callback(callback)` - Remove callback

### QRData Structure

```python
@dataclass
class QRData:
    timestamp: str              # ISO format timestamp
    identity_hash: str          # SHA-256 identity hash
    blockchain_hashes: Dict     # Chain -> block hash mapping
    time_server_verification: Dict  # Server verification data
    user_data: Dict = None     # Optional user data
    sequence_number: int = 0    # Sequential number
```

## FAQ

### Q: How often do QR codes update?

A: By default, every 5 seconds. Configurable via `update_interval` setting.

### Q: What blockchain networks are supported?

A: Bitcoin, Ethereum, Litecoin, and Dogecoin. Configurable via `blockchain_settings.enabled_chains`.

### Q: Can I use custom time servers?

A: Yes, configure `time_settings.time_servers` with your preferred NTP servers.

### Q: How do I integrate with OBS for livestreaming?

A: Add a Browser Source pointing to `http://localhost:8080/viewer`.

### Q: What happens if internet connection is lost?

A: QRLP can fall back to local time and cached blockchain data. Verification flags indicate which checks passed; public authenticity still depends on a valid trusted signature or local integrity secret.

### Q: Can I customize QR code appearance?

A: Yes, use the `qr_settings` configuration and style options (`live`, `professional`, `minimal`).

### Q: How do I backup my identity?

A: Use `qrlp.identity_manager.export_identity(file_path)` to save identity data.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Development Setup

```bash
git clone https://github.com/docxology/qr_live_protocol.git
cd qr_live_protocol

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
flake8 src/
```

## License

CC BY-NC-SA 4.0 - see [LICENSE](../LICENSE) file for details.

## Support

- GitHub Issues: [Report bugs](https://github.com/docxology/qr_live_protocol/issues)
- Documentation: [Full docs](https://qrlp.readthedocs.io/)
- Email: contact@qrlp.org
