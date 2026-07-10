# QRLP Configuration Guide

Complete guide to configuring QRLP for your specific needs, from basic settings to advanced production deployments.

## 📋 Table of Contents

- [Configuration Methods](#configuration-methods)
- [Quick Setup](#quick-setup)
- [Configuration File](#configuration-file)
- [Environment Variables](#environment-variables)
- [Command Line Arguments](#command-line-arguments)
- [Configuration Examples](#configuration-examples)
- [Advanced Configuration](#advanced-configuration)
- [Validation & Troubleshooting](#validation--troubleshooting)

## 🛠️ Configuration Methods

QRLP supports multiple configuration methods with the following precedence (highest to lowest):

1. **🔧 Command line arguments** - Override any other setting
2. **🌍 Environment variables** - `QRLP_*` prefixed variables
3. **📄 Configuration file** - JSON/YAML files
4. **⚙️ Default values** - Built-in defaults

**Example precedence:**
```bash
# Command line overrides everything
QRLP_UPDATE_INTERVAL=10 qrlp live --interval 5  # Uses 5 seconds

# Environment variables override config file
QRLP_WEB_PORT=9000 qrlp --config custom.json live  # Uses port 9000
```

## 🚀 Quick Setup

### Generate Configuration File

```bash
# Create default configuration with comments
qrlp config-init --with-comments --output config.json

# Create minimal configuration
qrlp config-init --output minimal.json

# Create in specific directory
qrlp config-init --output ~/.qrlp/config.json
```

### Basic Command Line Configuration

```bash
# Start with common settings
qrlp live --port 8080 --interval 3 --host 0.0.0.0 --no-browser

# Debug mode with a custom identity file
qrlp --debug live --interval 1 --identity-file ./company.pem

# Use config files for blockchain/time/QR/security settings
qrlp --config production.json live
```

### Environment Variable Setup

```bash
# Set common environment variables
export QRLP_UPDATE_INTERVAL=5
export QRLP_WEB_PORT=8080
export QRLP_WEB_HOST=localhost
export QRLP_LOG_LEVEL=INFO

# Start with environment configuration
qrlp live
```

## 📄 Configuration File

### Creating Configuration Files

#### Basic Configuration
```bash
# Generate default configuration
qrlp config-init --output config.json

# Generate with detailed comments (recommended for learning)
qrlp config-init --with-comments --output config.json

# Create in specific location
qrlp config-init --output ~/.qrlp/qrlp.json
```

#### Multiple Configuration Files
```bash
# Development configuration
qrlp config-init --with-comments --output dev-config.json

# Production configuration
qrlp config-init --with-comments --output prod-config.json

# Testing configuration
qrlp config-init --with-comments --output test-config.json

# Use different configs for different environments
qrlp --config dev-config.json live   # Development
qrlp --config prod-config.json live  # Production
```

### Complete Configuration Reference

Here's the complete configuration schema with all available options:

```json
{
  "update_interval": 5.0,

  "qr_settings": {
    "error_correction_level": "M",
    "border_size": 4,
    "box_size": 10,
    "fill_color": "black",
    "back_color": "white",
    "image_format": "PNG",
    "max_data_size": 2000
  },

  "web_settings": {
    "host": "localhost",
    "port": 8080,
    "auto_open_browser": true,
    "template_dir": "templates",
    "static_dir": "static",
    "debug": false,
    "cors_enabled": false,
    "cors_allowed_origins": [],
    "admin_token": null,
    "rate_limit_per_minute": 120
  },

  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum"],
    "cache_duration": 300,
    "timeout": 10.0,
    "retry_attempts": 3,
    "api_endpoints": {}
  },

  "time_settings": {
    "time_servers": [
      "time.nist.gov",
      "pool.ntp.org",
      "time.google.com",
      "time.cloudflare.com"
    ],
    "update_interval": 60.0,
    "timeout": 5.0,
    "local_fallback": true,
    "timezone": "UTC"
  },

  "identity_settings": {
    "identity_file": null,
    "auto_generate": true,
    "include_system_info": true,
    "include_file_hash": true,
    "hash_algorithm": "sha256"
  },

  "verification_settings": {
    "max_time_drift": 300.0,
    "require_blockchain": false,
    "require_time_server": false,
    "min_verifications": 1
  },

  "security_settings": {
    "encrypt_qr_data": false,
    "encryption_key": null,
    "sign_qr_data": true,
    "private_key_file": null,
    "public_key_file": null,
    "key_dir": "./keys",
    "issuer_id": "issuer-1",
    "event_id": "default",
    "signing_key_id": null,
    "signature_algorithm": "rsa",
    "qr_ttl_seconds": null
  },

  "logging_settings": {
    "level": "INFO",
    "log_file": null,
    "max_file_size": 10485760,
    "backup_count": 5,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

### Configuration File Locations

QRLP looks for configuration files in this order:

1. **Command line specified**: `--config /path/to/config.json`
2. **Current directory**: `./config.json`, `./qrlp.json`
3. **User config directory**: `~/.qrlp/config.json`
4. **System config directory**: `/etc/qrlp/config.json`
5. **Built-in defaults**: Hardcoded fallback values

**Multiple File Formats:**
```bash
# JSON configuration (recommended)
qrlp config-init --output config.json

# YAML configuration (requires PyYAML)
qrlp config-init --format yaml --output config.yaml
pip install PyYAML  # If not already installed
```

### Configuration File Validation

```bash
# Check for specific issues
python3 -c "
from src.config import QRLPConfig
config = QRLPConfig.from_file('config.json')
issues = config.validate()
if issues:
    print('Configuration issues:')
    for issue in issues:
        print(f'  - {issue}')
else:
    print('✅ Configuration is valid')
"
```

## ⚙️ Configuration Options

### Core Settings

#### `update_interval`
**Type:** `float` | **Default:** `5.0` | **Range:** `0.1` - `3600.0`

Interval in seconds between QR code updates. Lower values = more responsive but higher resource usage.

```json
// Fast updates for live events
"update_interval": 1.0

// Slower updates for static displays
"update_interval": 30.0

// Very slow for minimal resource usage
"update_interval": 300.0
```

**Performance Impact:**
- `1.0s`: High-frequency updates, best for live streaming
- `5.0s`: Balanced performance, recommended default
- `30.0s`: Low resource usage, suitable for static displays
- `300.0s`: Minimal resource usage, for background operation

### QR Code Settings (`qr_settings`)

Controls the appearance and functionality of generated QR codes.

#### `error_correction_level`
**Type:** `string` | **Default:** `"M"` | **Options:** `"L"`, `"M"`, `"Q"`, `"H"`

Error correction level determines how much damage the QR code can sustain while remaining readable.

| Level | Correction | Use Case | QR Density |
|-------|------------|----------|------------|
| `"L"` | ~7% | Clean environments, digital displays | **Highest density** |
| `"M"` | ~15% | General purpose, recommended default | **High density** |
| `"Q"` | ~25% | Harsh environments, printing | **Medium density** |
| `"H"` | ~30% | Maximum reliability, damaged codes | **Lowest density** |

```json
// High-quality scanning (recommended)
"error_correction_level": "M"

// Maximum reliability for challenging conditions
"error_correction_level": "H"

// Maximum data density for clean environments
"error_correction_level": "L"
```

#### `box_size`
**Type:** `integer` | **Default:** `10` | **Range:** `1` - `50`

Size of each QR code module (dot) in pixels. Larger values create bigger, more readable QR codes.

```json
// Small QR codes for space-constrained displays
"box_size": 8

// Standard readable size (recommended)
"box_size": 10

// Large, highly readable QR codes
"box_size": 15

// Maximum size for excellent scanning
"box_size": 25
```

#### `border_size`
**Type:** `integer` | **Default:** `4` | **Range:** `0` - `10`

Width of the white border around the QR code in modules. More border improves scanning reliability.

```json
// Minimal border for maximum data density
"border_size": 2

// Standard border (recommended)
"border_size": 4

// Extra border for better scanning reliability
"border_size": 6
```

#### `fill_color` / `back_color`
**Type:** `string` | **Default:** `"black"` / `"white"`

QR code colors. Supports color names, hex codes, and RGB values.

```json
// Standard black on white
"fill_color": "black",
"back_color": "white"

// High contrast colors
"fill_color": "#000000",
"back_color": "#ffffff"

// Custom brand colors
"fill_color": "#1e3a8a",
"back_color": "#f8fafc"

// Inverted for dark themes
"fill_color": "white",
"back_color": "black"
```

#### `style`
**Type:** `string` | **Default:** `"live"` | **Options:** `"live"`, `"professional"`, `"minimal"`

QR code styling preset that affects colors, borders, and visual elements.

```json
// Standard live streaming style
"style": "live"

// Clean, professional appearance
"style": "professional"

// Minimal, distraction-free design
"style": "minimal"
```

#### `version`
**Type:** `integer` | **Default:** `null` | **Range:** `1` - `40`

QR code version (size). `null` means auto-select based on data size.

```json
// Auto-select version (recommended)
"version": null

// Force specific version
"version": 10

// Maximum version for complex data
"version": 40
```

### Web Server Settings (`web_settings`)

Controls the web interface and API server behavior.

#### `host`
**Type:** `string` | **Default:** `"localhost"` | **Options:** `"localhost"`, `"0.0.0.0"`, `"127.0.0.1"`

Network interface to bind the web server to.

```json
// Local access only (default)
"host": "localhost"

// All network interfaces (allows external access)
"host": "0.0.0.0"

// Specific interface only
"host": "192.168.1.100"
```

**Security Note:** Use `"0.0.0.0"` only when external access is required, and implement proper firewall rules.

#### `port`
**Type:** `integer` | **Default:** `8080` | **Range:** `1024` - `65535`

Port number for the web server. Must be available and not blocked by firewall.

```json
// Standard HTTP port (requires root/sudo)
"port": 80

// Standard HTTPS port (requires root/sudo)
"port": 443

// Common development ports
"port": 8080

// High-numbered port (recommended for non-root users)
"port": 3000
```

#### `auto_open_browser`
**Type:** `boolean` | **Default:** `true`

Automatically open web browser when starting the server.

```json
// Auto-open browser (default)
"auto_open_browser": true

// Manual browser opening only
"auto_open_browser": false
```

#### `cors_enabled`
**Type:** `boolean` | **Default:** `false`

Enable Cross-Origin Resource Sharing for API access from other domains.

```json
// Disable CORS (default, more secure)
"cors_enabled": false

// Enable CORS for web development
"cors_enabled": true
```

#### `debug`
**Type:** `boolean` | **Default:** `false`

Enable debug mode with verbose logging and development features.

```json
// Production mode (default)
"debug": false

// Development mode with detailed logging
"debug": true
```

#### `template_dir` / `static_dir`
**Type:** `string` | **Defaults:** `"templates"`, `"static"`

Directories used by the Flask web interface.

#### `cors_allowed_origins`
**Type:** `list[string]` | **Default:** `[]`

Allowed CORS origins when `cors_enabled` is true. Leave empty unless a specific trusted origin needs API access.

#### `admin_token`
**Type:** `string | null` | **Default:** `null`

Optional token required for state-changing web controls. Send it as `X-QRLP-Admin-Token` or `Authorization: Bearer <token>`.

#### `rate_limit_per_minute`
**Type:** `integer` | **Default:** `120`

Basic in-memory per-client request cap for the local web server. Use a reverse proxy for durable internet-facing limits.

### Blockchain Settings (`blockchain_settings`)

Controls blockchain network integration for verification and timestamp anchoring.

#### `enabled_chains`
**Type:** `array[string]` | **Default:** `["bitcoin", "ethereum"]` | **Options:** `"bitcoin"`, `"ethereum"`, `"litecoin"`, `"dogecoin"`

List of blockchain networks to include in QR codes for verification.

| Network | Block Time | Reliability | Use Case |
|---------|------------|-------------|----------|
| `"bitcoin"` | ~10 minutes | ✅ Highest | Maximum trust, global standard |
| `"ethereum"` | ~12 seconds | ✅ High | Smart contracts, fast verification |
| `"litecoin"` | ~2.5 minutes | ✅ Medium | Faster than Bitcoin, still reliable |
| `"dogecoin"` | ~1 minute | ⚠️ Lower | Fastest, but less established |

```json
// Single network for simplicity
"enabled_chains": ["bitcoin"]

// Multiple networks for maximum verification
"enabled_chains": ["bitcoin", "ethereum", "litecoin"]

// All available networks
"enabled_chains": ["bitcoin", "ethereum", "litecoin", "dogecoin"]

// Custom order (first in list appears first in QR)
"enabled_chains": ["ethereum", "bitcoin"]
```

#### `cache_duration`
**Type:** `float` | **Default:** `300.0` | **Range:** `30.0` - `3600.0`

How long to cache blockchain data in seconds before refreshing.

```json
// Short cache for live events (more frequent updates)
"cache_duration": 60.0

// Standard cache (recommended)
"cache_duration": 300.0

// Long cache for static displays (less API usage)
"cache_duration": 1800.0

// Maximum cache for minimal network usage
"cache_duration": 3600.0
```

#### `timeout`
**Type:** `float` | **Default:** `10.0` | **Range:** `1.0` - `60.0`

Timeout in seconds for blockchain API requests.

```json
// Fast timeout for responsive UI
"timeout": 5.0

// Standard timeout (recommended)
"timeout": 10.0

// Longer timeout for slow networks
"timeout": 30.0

// Maximum timeout for very slow connections
"timeout": 60.0
```

#### `retry_attempts`
**Type:** `integer` | **Default:** `3` | **Range:** `1` - `10`

Number of retry attempts for failed blockchain API requests.

```json
// No retries for fast failure
"retry_attempts": 1

// Standard retries (recommended)
"retry_attempts": 3

// More retries for unreliable networks
"retry_attempts": 5

// Maximum retries for very unreliable connections
"retry_attempts": 10
```

#### `api_endpoints`
**Type:** `dict[string, string]` | **Default:** `{}`

Custom API endpoints for blockchain networks (optional override).

```json
// Use default APIs (recommended)
"api_endpoints": {}

// Custom Bitcoin API
"api_endpoints": {
  "bitcoin": "https://api.blockcypher.com/v1/btc/main"
}

// Custom endpoints for all networks
"api_endpoints": {
  "bitcoin": "https://custom-bitcoin-api.com",
  "ethereum": "https://custom-ethereum-api.com",
  "litecoin": "https://custom-litecoin-api.com"
}
```

**Note:** Only use custom endpoints if you have specific requirements. Default APIs are well-tested and reliable.

### Time Settings (`time_settings`)

#### `time_servers`
**Type:** `array[string]`  
**Default:** `["time.nist.gov", "pool.ntp.org", "time.google.com", "time.cloudflare.com"]`  
**Description:** List of time servers for synchronization.

```json
"time_servers": [
  "0.pool.ntp.org",
  "1.pool.ntp.org",
  "time.nist.gov"
]
```

#### `update_interval`
**Type:** `float`  
**Default:** `60.0`  
**Description:** How often to update time synchronization.

#### `timeout`
**Type:** `float`  
**Default:** `5.0`  
**Description:** Timeout for time server requests.

### Identity Settings (`identity_settings`)

#### `identity_file`
**Type:** `string` or `null`  
**Default:** `null`  
**Description:** Path to file for identity generation.

```json
"identity_file": "/path/to/key.pem"
```

#### `auto_generate`
**Type:** `boolean`  
**Default:** `true`  
**Description:** Automatically generate identity if no file provided.

#### `include_system_info`
**Type:** `boolean`  
**Default:** `true`  
**Description:** Include system information in identity hash.

#### `hash_algorithm`
**Type:** `string`  
**Default:** `"sha256"`  
**Options:** `"sha256"`, `"sha512"`, `"md5"`  
**Description:** Hash algorithm for identity generation.

### Verification Settings (`verification_settings`)

#### `max_time_drift`
**Type:** `float`  
**Default:** `300.0`  
**Description:** Maximum allowed time drift in seconds for verification.

#### `require_blockchain`
**Type:** `boolean`  
**Default:** `false`  
**Description:** Require blockchain verification for valid QR codes.

#### `require_time_server`
**Type:** `boolean`  
**Default:** `false`  
**Description:** Require time server verification for valid QR codes.

## Environment Variables

`QRLPConfig.from_env()` currently supports this explicit environment subset:

```bash
# Core settings
export QRLP_UPDATE_INTERVAL=2.0

# Web settings
export QRLP_WEB_HOST=0.0.0.0
export QRLP_WEB_PORT=8080
export QRLP_WEB_CORS_ENABLED=false
export QRLP_WEB_ADMIN_TOKEN=change-me

# Identity settings
export QRLP_IDENTITY_FILE=/path/to/key.pem

# Issuer metadata
export QRLP_ISSUER_ID=issuer-1
export QRLP_EVENT_ID=live-event

# Logging
export QRLP_LOG_LEVEL=DEBUG
```

## Command Line Arguments

Most configuration options can be overridden via command line:

```bash
# Basic options
qrlp live --port 8081 --host 0.0.0.0 --interval 2.0

# No browser auto-open
qrlp live --no-browser

# Custom identity file
qrlp live --identity-file ./my-key.pem

# Debug mode
qrlp --debug live

# Custom configuration file
qrlp --config ./custom-config.json live
```

## 📋 Configuration Examples

Real-world configuration examples for different use cases and deployment scenarios.

### 🎥 Livestreaming Setup (OBS Studio)

**Optimized for live streaming with OBS browser source integration.**

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
    "cache_duration": 180,
    "timeout": 10.0,
    "retry_attempts": 3
  },
  "time_settings": {
    "time_servers": [
      "time.nist.gov",
      "pool.ntp.org",
      "time.google.com"
    ],
    "update_interval": 60.0,
    "timeout": 5.0
  }
}
```

**Command Line Equivalent:**
```bash
qrlp live --interval 2 --host 0.0.0.0 --port 8080 --viewer-qr-size large
```

### 🔒 High-Security Corporate Setup

**Maximum verification and security for enterprise deployments.**

```json
{
  "update_interval": 10.0,
  "qr_settings": {
    "error_correction_level": "H",
    "box_size": 15,
    "border_size": 8,
    "style": "professional"
  },
  "web_settings": {
    "host": "0.0.0.0",
    "port": 8080,
    "auto_open_browser": false,
    "cors_enabled": false,
    "debug": false
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum", "litecoin"],
    "cache_duration": 60,
    "timeout": 15.0,
    "retry_attempts": 5
  },
  "identity_settings": {
    "identity_file": "/secure/company-identity.pem",
    "auto_generate": false,
    "include_system_info": true,
    "hash_algorithm": "sha512"
  },
  "verification_settings": {
    "max_time_drift": 30.0,
    "require_blockchain": true,
    "require_time_server": true,
    "min_verifications": 1
  },
  "security_settings": {
    "encrypt_qr_data": true,
    "sign_qr_data": true,
    "key_dir": "/secure/qrlp-keys",
    "issuer_id": "company-live",
    "event_id": "earnings-call",
    "signature_algorithm": "rsa"
  },
  "logging_settings": {
    "level": "INFO",
    "log_file": "/var/log/qrlp/qrlp.log"
  }
}
```

### ⚡ Minimal Performance Setup

**Optimized for speed and minimal resource usage.**

```json
{
  "update_interval": 5.0,
  "qr_settings": {
    "error_correction_level": "L",
    "box_size": 8,
    "border_size": 2
  },
  "web_settings": {
    "host": "localhost",
    "port": 8080,
    "auto_open_browser": false
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin"],
    "cache_duration": 900,
    "timeout": 5.0,
    "retry_attempts": 1
  },
  "time_settings": {
    "time_servers": ["time.google.com"],
    "update_interval": 300.0,
    "timeout": 3.0,
    "local_fallback": true
  },
  "identity_settings": {
    "include_system_info": false,
    "hash_algorithm": "sha256"
  },
  "logging_settings": {
    "level": "WARNING"
  }
}
```

### 🧪 Development & Testing Setup

**Configuration optimized for development workflow and testing.**

```json
{
  "update_interval": 2.0,
  "qr_settings": {
    "error_correction_level": "M",
    "box_size": 10,
    "border_size": 4
  },
  "web_settings": {
    "host": "localhost",
    "port": 8080,
    "auto_open_browser": false,
    "cors_enabled": true,
    "debug": true
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin"],
    "cache_duration": 30,
    "timeout": 5.0,
    "retry_attempts": 1
  },
  "time_settings": {
    "time_servers": ["time.nist.gov", "pool.ntp.org"],
    "update_interval": 30.0,
    "timeout": 3.0,
    "local_fallback": true
  },
  "verification_settings": {
    "max_time_drift": 600.0,
    "require_blockchain": false,
    "require_time_server": false,
    "min_verifications": 1
  },
  "logging_settings": {
    "level": "DEBUG",
    "log_file": null
  }
}
```

### 📱 Mobile Streaming Setup

**Optimized for mobile devices and portable streaming setups.**

```json
{
  "update_interval": 3.0,
  "qr_settings": {
    "error_correction_level": "H",
    "box_size": 10,
    "border_size": 4
  },
  "web_settings": {
    "host": "0.0.0.0",
    "port": 8080,
    "auto_open_browser": false,
    "cors_enabled": true
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin"],
    "cache_duration": 600,
    "timeout": 15.0,
    "retry_attempts": 3
  },
  "time_settings": {
    "time_servers": [
      "time.google.com",
      "time.cloudflare.com",
      "pool.ntp.org"
    ],
    "update_interval": 120.0,
    "timeout": 5.0,
    "local_fallback": true
  },
  "identity_settings": {
    "include_system_info": false,
    "hash_algorithm": "sha256"
  }
}
```

### 🏢 Enterprise Controlled-Network Setup

**Configuration for controlled-network deployments. This is not a complete internet-facing hardening profile.**

```json
{
  "update_interval": 5.0,
  "qr_settings": {
    "error_correction_level": "M",
    "box_size": 12,
    "border_size": 6,
    "fill_color": "#1e40af",
    "back_color": "#f8fafc"
  },
  "web_settings": {
    "host": "0.0.0.0",
    "port": 8080,
    "auto_open_browser": false,
    "cors_enabled": false,
    "debug": false,
    "admin_token": "set-a-secret-token",
    "rate_limit_per_minute": 120
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum"],
    "cache_duration": 300,
    "timeout": 10.0,
    "retry_attempts": 3,
    "api_endpoints": {
      "bitcoin": "https://api.blockcypher.com/v1/btc/main",
      "ethereum": "https://api.blockcypher.com/v1/eth/main"
    }
  },
  "time_settings": {
    "time_servers": [
      "ntp.server1.com",
      "ntp.server2.com",
      "time.nist.gov"
    ],
    "update_interval": 60.0,
    "timeout": 5.0,
    "local_fallback": false
  },
  "identity_settings": {
    "identity_file": "/etc/qrlp/enterprise-identity.pem",
    "auto_generate": false,
    "include_system_info": true,
    "hash_algorithm": "sha512"
  },
  "verification_settings": {
    "max_time_drift": 60.0,
    "require_blockchain": true,
    "require_time_server": true,
    "min_verifications": 1
  },
  "security_settings": {
    "encrypt_qr_data": false,
    "sign_qr_data": true,
    "key_dir": "/etc/qrlp/keys",
    "issuer_id": "enterprise-live",
    "event_id": "enterprise-event",
    "signature_algorithm": "rsa"
  },
  "logging_settings": {
    "level": "INFO",
    "log_file": "/var/log/qrlp/enterprise.log",
    "max_file_size": 10485760,
    "backup_count": 10,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

## 🔧 Advanced Configuration

### Environment Variable Overrides

Only this environment-variable subset is currently loaded by `QRLPConfig.from_env()`:

```bash
# Core settings
export QRLP_UPDATE_INTERVAL=3.0
export QRLP_LOG_LEVEL=DEBUG

# Web settings
export QRLP_WEB_HOST=0.0.0.0
export QRLP_WEB_PORT=8080
export QRLP_WEB_CORS_ENABLED=false
export QRLP_WEB_ADMIN_TOKEN=change-me

# Identity and issuer metadata
export QRLP_IDENTITY_FILE=/path/to/identity.json
export QRLP_ISSUER_ID=issuer-1
export QRLP_EVENT_ID=live-event

# Start with environment overrides
qrlp live
```

### Configuration File Merging

When using multiple configuration sources, they merge in this order:

1. **Base defaults** (built-in)
2. **Configuration file** (`config.json`)
3. **Environment variables** (`QRLP_*`)
4. **Command line arguments** (highest priority)

**Example:**
```bash
# Config file sets interval to 5s, but command line overrides to 2s
qrlp live --interval 2  # Uses 2 seconds, not 5
```

### Custom Configuration Validation

```python
# Validate configuration in your application
from src.config import QRLPConfig

config = QRLPConfig.from_file('my-config.json')
issues = config.validate()

if issues:
    print("Configuration issues found:")
    for issue in issues:
        print(f"  - {issue}")
    exit(1)

# Configuration is valid
qrlp = QRLiveProtocol(config)
```

## 🔍 Validation & Troubleshooting

### Configuration Validation

QRLP automatically validates configuration values and provides helpful error messages:

```bash
# Configuration is validated before live mode starts
qrlp --config config.json live --no-browser

# Expected output for invalid config:
# Configuration issues found:
#   - update_interval must be positive
#   - QR error correction level must be L, M, Q, or H
```

### Common Configuration Issues

#### Issue: QR codes not updating
```json
// Problem: update_interval too high
"update_interval": 300.0  // 5 minutes between updates

// Solution: Reduce interval
"update_interval": 5.0    // 5 seconds between updates
```

#### Issue: Poor QR scanning
```json
// Problem: QR too small or low error correction
"box_size": 6,
"error_correction_level": "L"

// Solution: Increase size and error correction
"box_size": 12,
"error_correction_level": "M"
```

#### Issue: High resource usage
```json
// Problem: Too many blockchain networks and short cache
"enabled_chains": ["bitcoin", "ethereum", "litecoin", "dogecoin"],
"cache_duration": 30

// Solution: Reduce networks and increase cache
"enabled_chains": ["bitcoin"],
"cache_duration": 600
```

#### Issue: Network timeouts
```json
// Problem: Timeout too short for slow networks
"timeout": 5.0

// Solution: Increase timeout
"timeout": 15.0
```

### Performance Tuning

#### For Maximum Responsiveness
```json
{
  "update_interval": 1.0,
  "blockchain_settings": {
    "cache_duration": 30,
    "timeout": 5.0
  },
  "time_settings": {
    "update_interval": 15.0,
    "timeout": 2.0
  }
}
```

#### For Maximum Reliability
```json
{
  "update_interval": 10.0,
  "qr_settings": {
    "error_correction_level": "H"
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum", "litecoin"],
    "cache_duration": 120,
    "retry_attempts": 5
  }
}
```

#### For Minimal Resource Usage
```json
{
  "update_interval": 60.0,
  "blockchain_settings": {
    "enabled_chains": ["bitcoin"],
    "cache_duration": 1800
  },
  "time_settings": {
    "time_servers": ["time.google.com"],
    "update_interval": 600.0
  },
  "identity_settings": {
    "include_system_info": false
  }
}
```

---

**Need help with configuration?** Check the [troubleshooting section](#validation--troubleshooting) or see [real-world examples](https://github.com/docxology/qr_live_protocol/tree/main/examples) in the repository.
