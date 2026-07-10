# QR Live Protocol (QRLP)

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://pypi.org/project/qr-live-protocol/)

A comprehensive, source-available system for generating live QR codes with local integrity checks and optional public-key authenticity verification for livestreaming, official video releases, and content verification.

## 🌟 What is QRLP?

QRLP (QR Live Protocol) creates **live, verifiable QR codes** for stream overlays and official releases. Each QR code can contain:

- ⏰ **Live timestamps** from multiple synchronized time servers
- 🔗 **Current blockchain hashes** from Bitcoin, Ethereum, and other networks as freshness context
- 🆔 **Issuer identity metadata** plus optional trusted public-key signatures
- 📊 **Real-time statistics** and verification status

HMAC fields are local integrity checks for a QRLP operator or verifier with the same secret. Public authenticity requires a signed QR payload and a verifier configured with the issuer's trusted public key.

## 🚀 Quick Start

### Modern Setup with uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/docxology/qr_live_protocol.git
cd qr_live_protocol

# Create virtual environment with uv (fast, modern package manager)
uv venv
source .venv/bin/activate

# Install the package with development dependencies
uv pip install -e .[dev]

# Start live QR generation
qrlp live

# Start the improvement dashboard
qrlp dashboard

# Or run the comprehensive demo
python main.py
```

This automatically:
- ✅ Creates modern virtual environment with uv
- 📦 Installs all dependencies with dependency resolution
- 🌐 Starts web server with live QR display
- 📱 Opens browser interface automatically
- ⏰ Begins live QR generation with real-time updates

### Alternative: pip Installation

```bash
# 1. Create virtual environment (traditional way)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install the package
pip install -e .[dev]

# 3. Start live QR display
qrlp live

# 4. Generate single QR code
qrlp generate --output qr_code.png

# 5. Run comprehensive demo
python main.py
```

## ✨ Key Features

| Feature | Description | Use Case |
|---------|-------------|----------|
| 🔲 **Live QR Generation** | Real-time QR codes that update automatically | Livestream overlays, live events |
| 🧩 **Explicit Chunking** | Oversized payloads fail clearly and can be split into recoverable QR chunks | Large signed payloads, offline transfer |
| ⏰ **Multi-Source Time Sync** | Synchronized timestamps from NTP servers + HTTP APIs | Precise timing verification |
| 🔗 **Blockchain Verification** | Live block hashes from Bitcoin, Ethereum, Litecoin, Dogecoin | Cryptographic proof of timing |
| 🆔 **Identity Management** | Unique fingerprints based on system + file signatures | Authenticate content creators |
| 🌐 **Web Interface** | Beautiful, responsive live display with WebSocket updates | Easy integration with streaming software |
| 📱 **OBS Integration** | Optimized browser source for OBS Studio | Professional livestreaming |
| 🔐 **Cryptographic Security** | HMAC integrity + optional trusted digital signatures | Tamper detection and issuer verification |
| 📊 **Real-time Monitoring** | Live statistics and performance metrics | Production monitoring |

### Why QRLP?

**🔒 Explicit Trust Model**: Local HMAC checks detect tampering for shared-secret deployments; trusted public keys enable third-party signature verification

**⏱️ Real-Time Authenticity**: Live updates prove content is happening *right now*, not pre-recorded

**🌐 Scanner Compatibility**: Standard QR scanners can read the payload; authenticity checks require QRLP verification tooling

**📺 Streamer-Friendly**: One-click OBS integration, no complex setup needed

**🏢 Operator-Friendly**: Local web display, CLI workflows, and configurable verification settings for professional broadcasting experiments

## 🏗️ System Architecture

QRLP is built with a modular, extensible architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    QRLiveProtocol                           │
│                (Main Coordinator)                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │QRGenerator  │  │TimeProvider │  │BlockchainVerifier   │  │
│  │- QR styles  │  │- NTP sync   │  │- Multi-chain APIs   │  │
│  │- Caching    │  │- HTTP APIs  │  │- Hash caching       │  │
│  │- Text overlay│  │- Fallbacks  │  │- Error resilience   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │IdentityMgr  │  │WebServer    │  │CryptoManager        │  │
│  │- System     │  │- Flask      │  │- HMAC integrity     │  │
│  │  fingerprint│  │- WebSocket  │  │- Digital signatures │  │
│  │- File hashes│  │- Real-time  │  │- Encryption support │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐        ┌─────────────────┐
│   OBS Studio    │        │ Mobile Apps     │
│ Browser Source  │        │ QR Scanners     │
│ Stream Overlays │        │ Verification    │
└─────────────────┘        └─────────────────┘
```

### Component Responsibilities

- **QRLiveProtocol**: Main coordinator orchestrating all components
- **QRGenerator**: Creates QR codes with multiple styles and text overlays
- **TimeProvider**: Synchronizes with NTP servers and HTTP time APIs
- **BlockchainVerifier**: Retrieves current block hashes from multiple chains
- **IdentityManager**: Creates unique fingerprints from system and file data
- **WebServer**: Provides real-time web interface with WebSocket updates
- **CryptoManager**: Handles HMAC integrity, digital signatures, and encryption

## Project Structure

```
qr_live_protocol/
├── src/                    # Main source code
│   ├── __init__.py        # Package initialization
│   ├── core.py            # QRLiveProtocol main class
│   ├── qr_generator.py    # QR code generation
│   ├── time_provider.py   # Time synchronization
│   ├── blockchain_verifier.py  # Blockchain verification
│   ├── identity_manager.py     # Identity management
│   ├── web_server.py      # Flask web interface
│   ├── config.py          # Configuration management
│   ├── cli.py             # Command-line interface
│   └── __main__.py        # Module entry point
├── docs/                  # Documentation
│   └── README.md          # Comprehensive documentation
├── examples/              # Example scripts
│   └── livestream_demo.py # Full demonstration
├── templates/             # Web templates
│   └── index.html         # Main web interface
├── pyproject.toml         # Modern Python project configuration
├── requirements.txt       # Legacy dependencies (for compatibility)
├── setup.py              # Legacy setup (deprecated, use pyproject.toml)
├── setup.sh              # Quick setup script with uv
├── main.py               # Modern demo launcher
├── .gitignore            # Git ignore patterns
└── README.md             # This file
```

### Modern Python Packaging

QRLP now uses **pyproject.toml** for modern Python packaging:

- **✅ Modern standards** - Follows PEP 621 and latest packaging standards
- **✅ Better dependency resolution** - No version conflicts
- **✅ Development tools** - Integrated linting, formatting, and testing
- **✅ Optional dependencies** - Clean separation of dev and production deps
- **✅ uv compatible** - Optimized for the fastest Python package manager

## 📖 Usage Examples

### 🎯 Livestreaming Setup (OBS Studio)

```bash
# 1. Start QRLP server
qrlp live --port 8080 --interval 2

# 2. Add browser source in OBS:
#    - URL: http://localhost:8080/viewer
#    - Width: 800, Height: 600
#    - Check "Shutdown source when not visible"

# 3. Position QR overlay in your stream
# 4. Go live - viewers can scan QR for verification!
```

**For Professional Streaming:**
```bash
# Controlled-network configuration for professional use
qrlp --config production.json live --identity-file ./company-key.pem
```

### 🔧 Custom Integration Examples

#### Python API Integration
```python
from src import QRDataTooLargeError, QRGenerator, QRLiveProtocol, QRLPConfig

# Initialize with custom settings
config = QRLPConfig()
config.update_interval = 1.0  # Fast updates for live events
config.blockchain_settings.enabled_chains = {"bitcoin", "ethereum", "litecoin"}

qrlp = QRLiveProtocol(config)

# Generate QR with custom data
event_data = {
    "event": "Product Launch",
    "presenter": "CEO",
    "timestamp": "2025-01-11T15:30:00Z"
}

qr_data, qr_image = qrlp.generate_single_qr(user_data=event_data)

# Large payloads must use explicit QR chunking
large_payload = "large payload" * 1000
try:
    large_qr = qrlp.qr_generator.generate_qr_image(large_payload)
except QRDataTooLargeError:
    chunks = qrlp.qr_generator.generate_chunked_payloads(large_payload)
    recovered = QRGenerator.reassemble_chunked_payloads(chunks)
    assert recovered == large_payload

# Add callback for real-time updates
def on_qr_update(qr_data, qr_image):
    # Save QR image or send to streaming platform
    with open(f"qr_{qr_data.sequence_number}.png", "wb") as f:
        f.write(qr_image)
    print(f"Generated QR #{qr_data.sequence_number}")

qrlp.add_update_callback(on_qr_update)
qrlp.start_live_generation()
```

#### Webhook Integration
```python
# Integrate with streaming platforms
import requests

def stream_callback(qr_data, qr_image):
    # Send to streaming platform API
    requests.post('https://api.platform.com/overlay', json={
        'stream_id': 'your_stream_id',
        'qr_data': qr_data.to_json(),
        'qr_image': qr_image.decode('latin1')  # Base64 encode if needed
    })

qrlp.add_update_callback(stream_callback)
```

### 🔍 Verification Examples

#### Manual QR Verification
```bash
# Generate a signed QR and verifier trust material
qrlp generate \
  --format both \
  --output qr_data \
  --user-data '{"event":"launch"}' \
  --sign \
  --public-key-output issuer.pem \
  --trust-record-output trust.json

# Verify on another machine/process with only trusted public-key material
qrlp verify --file qr_data.json --trust-store trust.json

# Output shows:
# ✓ Valid JSON: True
# ✓ Signature verified: True
# ✓ Time verified: True (within 30s tolerance)
# ✓ Trust mode: public_signature
# ✓ Overall: VALID
```

#### Programmatic Verification
```python
# Verify in your application
from src import QRLiveProtocol

qrlp = QRLiveProtocol()

# QR JSON from scanner
qr_json = '{"timestamp":"2025-01-11T15:30:45Z","identity_hash":"abc123..."}'

results = qrlp.verify_qr_data(qr_json)

if results['valid_json'] and results['identity_verified']:
    print("✅ Content is authentic!")
else:
    print("❌ Verification failed - possible forgery")
```

## ⚙️ Configuration

QRLP supports multiple configuration methods (in order of precedence):

1. **Command-line arguments** (highest priority)
2. **Environment variables** (`QRLP_*`)
3. **Configuration files** (JSON/YAML)
4. **Default values** (lowest priority)

### Quick Configuration

```bash
# Generate default configuration
qrlp config-init --output config.json

# Start with custom settings
qrlp live --interval 2 --port 8080 --host 0.0.0.0

# Environment variables
export QRLP_UPDATE_INTERVAL=1
export QRLP_WEB_PORT=8080
qrlp live
```

### Example Configurations

#### 🚀 Livestreaming Setup
```json
{
  "update_interval": 2.0,
  "qr_settings": {
    "error_correction_level": "M",
    "box_size": 12,
    "border_size": 6
  },
  "web_settings": {
    "host": "0.0.0.0",
    "port": 8080,
    "auto_open_browser": true,
    "cors_enabled": true
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum"],
    "cache_duration": 180
  }
}
```

#### 🔒 High-Security Setup
```json
{
  "update_interval": 10.0,
  "qr_settings": {
    "error_correction_level": "H"
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum", "litecoin"],
    "cache_duration": 60,
    "retry_attempts": 5
  },
  "identity_settings": {
    "identity_file": "/secure/path/identity.key",
    "include_system_info": true,
    "hash_algorithm": "sha512"
  },
  "verification_settings": {
    "max_time_drift": 30.0,
    "require_blockchain": true,
    "require_time_server": true
  }
}
```

## Dependencies

Core dependencies:
- `qrcode[pil]` - QR code generation
- `Flask` + `Flask-SocketIO` - Web interface
- `requests` - HTTP APIs
- `ntplib` - NTP time synchronization
- `click` - Command-line interface
- `bleach` - HTML sanitization
- `cryptography` - Cryptographic operations

**Development Tools:**
- `uv` - Modern Python package manager (recommended)
- `pytest` + `pytest-cov` - Testing framework
- `black` - Code formatting
- `flake8` - Code linting
- `mypy` - Type checking

## 🎯 Use Cases

| Use Case | Description | QRLP Solution |
|----------|-------------|---------------|
| **🎥 Livestreaming** | Prove streams are live, not pre-recorded | Real-time QR updates with live timestamps |
| **📰 News Broadcasting** | Add verifiable context to live reports | Signed issuer payloads with freshness context |
| **🏢 Corporate Communications** | Verify official announcements | Custom identity with file-based signatures |
| **⚖️ Legal Proceedings** | Timestamp evidence collection | Cryptographic proof with audit trails |
| **🎓 Educational Content** | Verify lecture authenticity | Institution-branded QR codes |
| **🏟️ Live Events** | Prove event timing and attendance | Custom data integration with event details |
| **💼 Business Meetings** | Authenticate video conferences | Participant verification with identity management |

### Real-World Applications

#### News Organization Example
```bash
# BBC News using QRLP for live broadcast verification
qrlp live --identity-file ./bbc-news.key --interval 5

# Viewers scan QR to verify:
# - Broadcast is live (current timestamp)
# - From BBC when the payload is signed and the verifier trusts BBC's public key
# - Includes current blockchain hashes as freshness context
```

#### Corporate Earnings Call
```python
# Company earnings call with QRLP verification
from src import QRLiveProtocol

qrlp = QRLiveProtocol()
call_data = {
    "company": "TechCorp",
    "event": "Q4 Earnings Call",
    "quarter": "2025-Q4",
    "attendees": 150
}

qr_data, qr_image = qrlp.generate_single_qr(call_data)
# QR carries signed/local integrity metadata and timing context
```

## 🔒 Security & Trust

### Security and Trust Model

**Multi-Layered Verification:**
- **Time Verification**: Timestamp drift checks with optional time-server evidence
- **Blockchain Context**: Current block hashes from configured chains; this is not an on-chain content commitment
- **Issuer Metadata**: Stable issuer/key fields embedded in signed QR payloads
- **Digital Signatures**: Public authenticity when the verifier trusts the issuer public key
- **HMAC Integrity**: Local/shared-secret tamper detection, not public authenticity

**Attack Resistance:**
- **Tamper Detection**: HMAC and signatures fail when covered payload fields change
- **Replay Bounds**: Timestamps and optional expiry limit stale QR acceptance windows
- **Trust Separation**: Public verifiers use public keys; private HMAC secrets are not distributed
- **Fail-Closed Verification**: Malformed, expired, unsigned, or untrusted payloads are reported invalid

### Comparison with Alternatives

| Solution | QRLP | Watermarking | Blockchain-Only | Metadata-Based |
|----------|------|--------------|-----------------|----------------|
| **Real-time verification** | ✅ Live | ❌ Static | ❌ Manual | ❌ Offline |
| **QR readability** | ✅ Any QR scanner | ❌ Special software | ❌ Crypto wallet | ❌ File reader |
| **Tamper resistance** | ✅ Cryptographic | ⚠️ AI-removable | ✅ Immutable | ❌ Easily stripped |
| **No private verifier state for public signatures** | ✅ Trusted public key | ❌ External service | ❌ Blockchain deps | ❌ Metadata parsing |
| **Live streaming** | ✅ Real-time updates | ❌ Static marks | ❌ Post-processing | ❌ No live support |

**QRLP Advantage**: Standard QR payloads, explicit issuer-key trust, local integrity checks, and streaming-friendly updates.

## 📊 Performance & Scalability

### Performance Characteristics

- **QR Generation**: ~50-200ms per QR code (depending on complexity)
- **Memory Usage**: ~50MB base + 10MB per 1000 cached QRs
- **Network Usage**: ~1KB per blockchain API call, ~100 bytes per time sync
- **CPU Usage**: <5% on modern systems during normal operation

### Optimization Tips

**For High-Performance Streaming:**
```bash
# Faster updates for live events
qrlp live --interval 1.0

# Optimize blockchain caching through a config file
qrlp --config streaming.json live
```

**For Battery-Powered Devices:**
```bash
# Reduce update frequency; use a config file to limit enabled chains
qrlp --config battery.json live --interval 10.0
```

**For Enterprise Deployments:**
```json
{
  "web_settings": {
    "host": "0.0.0.0",
    "port": 8080
  },
  "blockchain_settings": {
    "cache_duration": 600,
    "timeout": 5.0
  },
  "time_settings": {
    "update_interval": 120.0
  }
}
```

### Monitoring & Analytics

QRLP provides built-in monitoring:
```bash
# Check system status and performance
qrlp status

# Monitor in real-time via web interface
# Visit http://localhost:8080/admin for detailed stats

# Run readiness checks and local signed-QR smoke tests
qrlp dashboard
# Visit http://localhost:8080/improve
```

## 🚀 Getting Started (3 Steps)

### Step 1: Setup with uv (Recommended)
```bash
git clone https://github.com/docxology/qr_live_protocol.git
cd qr_live_protocol

# Modern setup with uv
uv venv
source .venv/bin/activate
uv pip install -e .[dev]
```

### Step 2: Configure (Optional)
```bash
# Customize for your use case
qrlp config-init --output my-config.json
# Edit my-config.json with your settings
```

### Step 3: Use
```bash
# Start live QR generation
qrlp --config my-config.json live

# Or use the simple demo launcher
python main.py

# Add to OBS: Browser Source → http://localhost:8080/viewer
# Start streaming with live verification!
```

**uv Benefits:**
- ⚡ **Faster installs** - Up to 10x faster than pip
- 🔒 **Better dependency resolution** - No conflicts
- 🛠️ **Modern tooling** - Built-in development tools
- 📦 **Lock files** - Reproducible builds

## 🤝 Contributing & Support

### Ways to Contribute

**🐛 Bug Reports**: [GitHub Issues](https://github.com/docxology/qr_live_protocol/issues)
**💡 Feature Requests**: [GitHub Discussions](https://github.com/docxology/qr_live_protocol/discussions)
**📝 Documentation**: Improve this README or other docs
**🔧 Code Contributions**: See [Contributing Guide](CONTRIBUTING.md)

### Getting Help

- **📖 Documentation**: Complete guides in `/docs`
- **❓ FAQ**: Common questions and troubleshooting in [FAQ.md](FAQ.md)
- **💬 Community**: Join discussions on GitHub
- **📧 Support**: contact@qrlp.org for complex issues

### Professional Services

For enterprise deployments and custom integrations:
- **Consulting**: Architecture review and deployment planning
- **Custom Development**: Tailored features and integrations
- **Training**: Team training and knowledge transfer
- **Support**: Priority support and maintenance

Contact: enterprise@qrlp.org

## 📄 License & Terms

**License**: [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

### What You Can Do
- ✅ **Use personally** - For livestreaming, content creation, personal projects
- ✅ **Share and distribute** - Copy and redistribute QRLP as needed
- ✅ **Modify and adapt** - Create derivatives for your use case
- ✅ **Study and learn** - Use as reference for your own implementations

### What You Cannot Do
- ❌ **Commercial use** - Cannot use for commercial/business purposes without permission
- ❌ **Remove attribution** - Must credit QRLP when used or modified
- ❌ **Sublicense** - Cannot relicense derivatives under different terms

### For Commercial Use
Contact us at **enterprise@qrlp.org** for:
- Commercial licensing options
- Enterprise support agreements
- Custom development services
- Professional deployment assistance

## 🌟 Project Status

**Current Version**: 1.0.1 (Stable)
**Active Development**: ✅ Yes
**Community Support**: ✅ GitHub Issues & Discussions
**Professional Support**: ✅ Available for enterprise users

### What's Next

**Version 2.0** (Q2 2025):
- Mobile apps for iOS and Android
- Enhanced cryptographic features
- Advanced streaming platform integrations
- Professional OBS plugin

**Version 3.0** (Q4 2025):
- Blockchain smart contract integration
- Advanced AI-powered verification
- Enterprise-grade security features
- Multi-platform SDKs

## 🙏 Acknowledgments

QRLP builds on the work of:
- **Python Cryptography Community** - For secure cryptographic implementations
- **QR Code Standards** - ISO/IEC 18004 QR code specifications
- **NTP Community** - Network Time Protocol standards and implementations
- **Blockchain Communities** - Bitcoin, Ethereum, and other blockchain networks

## 📞 Contact & Support

**📧 General Inquiries**: contact@qrlp.org
**🐛 Bug Reports**: [GitHub Issues](https://github.com/docxology/qr_live_protocol/issues)
**💬 Community**: [GitHub Discussions](https://github.com/docxology/qr_live_protocol/discussions)
**🏢 Enterprise**: enterprise@qrlp.org
**🐦 Social**: [@QRLiveProtocol](https://twitter.com/qrliveprotocol)

---

**QRLP**: Proving authenticity in a world of deepfakes and misinformation. 🛡️✨
