# QRLP Installation Guide

Complete guide to installing and setting up the QR Live Protocol system for live QR code generation with cryptographic verification.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Post-Installation Setup](#post-installation-setup)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)
- [Advanced Installation](#advanced-installation)

## 🖥️ Prerequisites

### System Requirements

| Component | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| **Python** | 3.8+ | 3.10+ | Required for QRLP core functionality |
| **RAM** | 512MB | 2GB+ | For web interface and QR generation |
| **Disk** | 100MB | 500MB | Installation and cache storage |
| **Network** | Broadband | Stable | For blockchain and time server APIs |
| **OS** | macOS 10.15+<br>Linux (Ubuntu 18.04+)<br>Windows 10+ | Latest versions | Full compatibility |

### Network Requirements

**Required Connectivity:**
- ✅ Internet connection for blockchain verification
- ✅ NTP time server access (ports 123/UDP)
- ✅ HTTPS access to blockchain APIs (port 443/TCP)

**Optional but Recommended:**
- ✅ Git access for repository cloning
- ✅ Python package index (PyPI) access

### Required System Packages

#### macOS
```bash
# Install Homebrew (package manager)
curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash

# Install Python (if not already installed)
brew install python@3.11

# Optional: Install development tools
brew install git openssl
```

#### Ubuntu/Debian
```bash
# Update package index
sudo apt update

# Install Python and development tools
sudo apt install python3 python3-pip python3-venv python3-dev

# Install build dependencies
sudo apt install build-essential git libssl-dev libffi-dev

# Optional: Install for better performance
sudo apt install python3-numpy  # For image processing optimizations
```

#### Windows
1. **Install Python** from [python.org](https://python.org)
   - ✅ Check "Add Python to PATH"
   - ✅ Choose "Customize installation"
   - ✅ Enable "pip" and "py launcher"

2. **Install Git** from [git-scm.com](https://git-scm.com)
   - ✅ Choose "Git from the command line and also from 3rd-party software"
   - ✅ Add to PATH during installation

3. **Install Visual C++ Build Tools** (for some dependencies)
   - Download from [visualstudio.microsoft.com](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   - Install "Desktop development with C++" workload

#### Raspberry Pi / ARM Linux
```bash
# Update system
sudo apt update && sudo apt upgrade

# Install Python and tools
sudo apt install python3 python3-pip python3-venv python3-dev git

# Install for hardware acceleration (optional)
sudo apt install libatlas-base-dev  # For faster image processing

# Enable hardware interfaces if needed
sudo raspi-config  # Configure for your setup
```

## 🚀 Installation Methods

Choose the installation method that best fits your needs and environment.

### Method 1: Modern Setup with uv (Recommended)

**Best for:** First-time users, quick evaluation, development

```bash
# Clone repository
git clone https://github.com/your-org/qr_live_protocol.git
cd qr_live_protocol

# Modern setup with uv (fast, modern package manager)
uv venv
source .venv/bin/activate

# Install the package with development dependencies
uv pip install -e .[dev]

# Start live QR generation
qrlp live

# Or run the comprehensive demo
python main.py
```

**What happens:**
- ✅ **Modern Environment**: Creates virtual environment with uv
- 📦 **Fast Installation**: Installs all dependencies with dependency resolution
- 🔧 **Development Setup**: Configures QRLP for development use
- 🌐 **Web Server**: Starts Flask server on port 8080
- 📱 **Live QR Generation**: Begins real-time QR code generation
- 🌍 **Browser**: Automatically opens web interface

**Expected Output:**
```bash
$ uv venv
$ source .venv/bin/activate
$ uv pip install -e .[dev]
$ qrlp live
🔲 QR Live Protocol (QRLP) - Modern Setup
==================================================
✅ uv is available
🏗️  Creating virtual environment...
📦 Installing QRLP with development dependencies...
🔍 Verifying installation...
✅ QRLP CLI is working!
🚀 Launching QRLP demo on port 8080
📡 Server will be available at: http://localhost:8080
🌐 Browser will open automatically in 3 seconds...
▶️  Starting livestream demo (Ctrl+C to stop)...
📱 QR codes will update every second with live data!
```

**uv Benefits:**
- ⚡ **10x faster installs** than pip
- 🔒 **Better dependency resolution** - no conflicts
- 🛠️ **Modern tooling** - built-in development tools
- 📦 **Lock files** - reproducible builds

### Method 2: Manual Installation

**Best for:** Advanced users, custom environments, production deployments

#### Step-by-Step Manual Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/qr_live_protocol.git
cd qr_live_protocol

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate    # Linux/macOS
# venv\Scripts\activate     # Windows

# 3. Upgrade pip (recommended)
pip install --upgrade pip

# 4. Install core dependencies
pip install -r requirements.txt

# 5. Install QRLP in development mode
pip install -e .[dev]

# 6. Verify installation
python3 -c "import src; print('✅ QRLP imported successfully')"

# 7. Test basic functionality
qrlp generate --output test_qr.png

# 8. Start web interface
qrlp live --no-browser
```

#### Manual Installation with Custom Configuration

```bash
# Install with specific Python version
python3.11 -m venv venv-py311
source venv-py311/bin/activate
pip install -r requirements.txt
pip install -e .[dev]

# Use custom configuration
qrlp live --config /path/to/config.json --port 8080
```

### Method 3: Docker Installation

**Best for:** Containerized environments, easy deployment, isolation

#### Using Pre-built Image (Recommended)

```bash
# Pull the official QRLP Docker image
docker pull qrliveprotocol/qrlp:latest

# Run with default settings
docker run -d --name qrlp -p 8080:8080 qrliveprotocol/qrlp

# Run with custom configuration
docker run -d --name qrlp \
  -p 8080:8080 \
  -v /host/config.json:/app/config.json \
  qrliveprotocol/qrlp --config /app/config.json
```

#### Building from Source

```bash
# Clone repository
git clone https://github.com/your-org/qr_live_protocol.git
cd qr_live_protocol

# Build Docker image
docker build -t qrlp:latest .

# Run container
docker run -d --name qrlp -p 8080:8080 qrlp:latest

# View logs
docker logs -f qrlp

# Access shell (for debugging)
docker exec -it qrlp /bin/bash
```

#### Docker Compose (Production)

```yaml
# docker-compose.yml
version: '3.8'
services:
  qrlp:
    image: qrliveprotocol/qrlp:latest
    ports:
      - "8080:8080"
    volumes:
      - ./config.json:/app/config.json
      - ./identity.pem:/app/identity.pem
    environment:
      - QRLP_WEB_HOST=0.0.0.0
      - QRLP_LOG_LEVEL=INFO
    restart: unless-stopped
```

```bash
# Deploy with Docker Compose
docker-compose up -d
```

### Method 4: Package Manager Installation

#### From PyPI (When Available)

```bash
# Install from Python Package Index
pip install qr-live-protocol

# Install with optional dependencies
pip install qr-live-protocol[dev,web]

# Start QRLP
qrlp live
```

#### From conda-forge (When Available)

```bash
# Using conda package manager
conda install -c conda-forge qr-live-protocol

# Or with mamba for faster solving
mamba install qr-live-protocol
```

### Method 5: Development Installation

**Best for:** Contributors, advanced users, custom modifications

```bash
# Clone for development
git clone https://github.com/your-org/qr_live_protocol.git
cd qr_live_protocol

# Install in development mode with test dependencies
pip install -e ".[dev,test]"

# Install additional development tools
pip install black flake8 mypy pytest-cov bandit

# Run tests to verify setup
pytest tests/ -v

# Run linting and formatting
make lint  # If Makefile available
# or manually:
black src/ tests/
flake8 src/ tests/
mypy src/

# Start development server
python -m src.cli live --debug
```

### Method 6: Platform-Specific Installation

#### Windows (Chocolatey)

```powershell
# Install with Chocolatey package manager
choco install python git

# Install QRLP
pip install qr-live-protocol
```

#### macOS (Homebrew)

```bash
# Install with Homebrew
brew install python@3.11 git

# Install QRLP
pip3 install qr-live-protocol
```

#### Linux (Snap)

```bash
# Install with Snap (Ubuntu/Debian)
sudo snap install qrlp --classic
```

## ✅ Verification

After installation, verify everything is working correctly:

### 1. Basic Import Test
```bash
# Test Python import
python3 -c "from src import QRLiveProtocol; print('✅ QRLP imported successfully')"

# Test CLI availability
qrlp --version
```

### 2. QR Generation Test
```bash
# Generate test QR code
qrlp generate --output test_qr.png

# Verify file was created
ls -la test_qr.png

# Generate JSON data only
qrlp generate --format json --output test_data.json
```

### 3. Web Interface Test
```bash
# Start web server (no auto-browser)
qrlp live --no-browser --port 8080

# Test web endpoints
curl -s http://localhost:8080/api/status | head -5

# Open browser manually to http://localhost:8080
```

### 4. System Status Check
```bash
# Check overall system health
qrlp status

# Expected output:
# QRLP Status:
#   Running: Yes
#   Total updates: 15
#   Sequence number: 15
#   Component Statistics:
#     Time provider: Success rate: 100.0%
#     Blockchain verifier: Success rate: 100.0%
```

### 5. Integration Test
```bash
# Test OBS integration (if OBS is installed)
# 1. Start QRLP: qrlp live --no-browser
# 2. Add browser source in OBS: http://localhost:8080/viewer
# 3. Verify QR codes update every few seconds
```

## 🔧 Troubleshooting

Common installation and setup issues with solutions:

### Python Version Issues

**Problem:** `python3: command not found` or wrong version
```bash
# Check Python version
python3 --version

# Should show: Python 3.8.0 or higher

# Solutions:
# 1. Install Python 3.8+ from python.org
# 2. Use pyenv: https://github.com/pyenv/pyenv
# 3. On Ubuntu: sudo apt install python3.8 python3.8-venv
```

**Problem:** `ImportError` or missing modules
```bash
# Upgrade pip first
pip install --upgrade pip

# Clear pip cache
pip cache purge

# Reinstall requirements
pip install -r requirements.txt

# Install specific problematic package
pip install qrcode[pil] flask flask-socketio requests ntplib click
```

### Virtual Environment Issues

**Problem:** `venv` module not available
```bash
# Install venv module
sudo apt install python3-venv  # Ubuntu/Debian
pip install virtualenv         # Alternative

# Use virtualenv instead
pip install virtualenv
virtualenv venv
source venv/bin/activate
```

**Problem:** Activation script not found
```bash
# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate

# Alternative activation
python -m venv venv && source venv/bin/activate
```

### Network and Connectivity Issues

**Problem:** Blockchain API failures
```bash
# Test connectivity
curl -s https://api.blockcypher.com/v1/btc/main | head -3

# Solutions:
# 1. Check internet connection
# 2. Try different DNS servers
# 3. Configure firewall to allow HTTPS outbound
# 4. Use VPN if in restricted network
```

**Problem:** Time server synchronization failures
```bash
# Test NTP connectivity
ntpq -p  # Show NTP server status

# Solutions:
# 1. Allow NTP outbound (UDP port 123)
# 2. Try different time servers in config
# 3. Check system time is roughly correct
```

### Permission Issues

**Problem:** `Permission denied` errors
```bash
# Make scripts executable
chmod +x main.py

# Run with proper permissions
python main.py

# If still issues, check file permissions
ls -la main.py
```

**Problem:** Cannot write to directories
```bash
# Create writable directory for QRLP data
mkdir -p ~/.qrlp
chmod 755 ~/.qrlp

# Or run as administrator (Windows)
# Right-click Command Prompt → Run as administrator
```

### Platform-Specific Issues

#### Windows Issues

**Problem:** `Microsoft Visual C++ 14.0 is required`
```bash
# Solution 1: Install Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
# Install "Desktop development with C++" workload

# Solution 2: Use pre-compiled wheels
pip install --only-binary=all qrcode[pil] flask
```

**Problem:** Path issues with spaces
```bash
# Use quotes around paths with spaces
python3 "C:\Program Files\Python\main.py"

# Or use short path names
# Rename directory to avoid spaces
```

#### macOS Issues

**Problem:** `System Integrity Protection` blocking
```bash
# Check SIP status
csrutil status

# If enabled, either:
# 1. Disable SIP (restart required)
# 2. Use user install: pip install --user
# 3. Use virtual environment in user directory
```

**Problem:** Homebrew Python conflicts
```bash
# Use system Python or specify path
/usr/bin/python main.py

# Or use Homebrew Python explicitly
/opt/homebrew/bin/python main.py
```

#### Linux Issues

**Problem:** `pip: command not found`
```bash
# Install pip for Python 3
sudo apt install python3-pip

# Or use package manager
python3 -m ensurepip
```

**Problem:** Missing development headers
```bash
# Install build dependencies
sudo apt install python3-dev build-essential
sudo apt install libssl-dev libffi-dev  # For cryptography
```

### Docker Issues

**Problem:** Docker daemon not running
```bash
# Start Docker service
sudo systemctl start docker  # Linux
# or manually start Docker Desktop

# Check status
sudo systemctl status docker
```

**Problem:** Port already in use
```bash
# Check what's using port 8080
lsof -i :8080

# Use different port
docker run -p 8081:8080 qrliveprotocol/qrlp
```

**Problem:** Container cannot access network
```bash
# Check Docker network
docker network ls

# Run with network access
docker run --network host qrliveprotocol/qrlp
```

### Performance Issues

**Problem:** QR generation too slow
```bash
# Reduce QR complexity
{
  "qr_settings": {
    "box_size": 8,
    "error_correction_level": "L"
  }
}

# Reduce blockchain networks
{
  "blockchain_settings": {
    "enabled_chains": ["bitcoin"]
  }
}
```

**Problem:** High memory usage
```bash
# Reduce cache durations
{
  "blockchain_settings": {
    "cache_duration": 60
  },
  "time_settings": {
    "update_interval": 300
  }
}
```

### Getting Help

1. **Check Logs**: Enable debug mode with `--debug` flag
2. **GitHub Issues**: Report bugs at [github.com/your-org/qr_live_protocol/issues](https://github.com/your-org/qr_live_protocol/issues)
3. **Documentation**: Full docs at [docs/README.md](README.md)
4. **Community**: Join discussions in GitHub Discussions

**Debug Command:**
```bash
# Run with full debug output
QRLP_LOG_LEVEL=DEBUG python main.py
```

## 🔧 Post-Installation Setup

### First Run Configuration

After successful installation, configure QRLP for your specific needs:

#### 1. Generate Configuration File
```bash
# Create default configuration
qrlp config-init --output ~/.qrlp/config.json

# Or create with comments for reference
qrlp config-init --with-comments --output config.json
```

#### 2. Customize Settings
Edit the generated configuration file to match your requirements:

```json
{
  "update_interval": 5.0,
  "qr_settings": {
    "box_size": 12,
    "error_correction_level": "M"
  },
  "web_settings": {
    "port": 8080,
    "host": "localhost"
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum"],
    "cache_duration": 300
  }
}
```

#### 3. Test Configuration
```bash
# Test with your configuration
qrlp live --config ~/.qrlp/config.json --no-browser

# Verify all components are working
qrlp status
```

### Environment Variables

Override configuration at runtime using environment variables:

```bash
# Core settings
export QRLP_UPDATE_INTERVAL=5      # QR update interval in seconds
export QRLP_WEB_PORT=8080          # Web server port
export QRLP_WEB_HOST=localhost     # Web server host
export QRLP_LOG_LEVEL=INFO         # Logging level

# QR settings
export QRLP_QR_BOX_SIZE=12         # QR code pixel size
export QRLP_QR_ERROR_CORRECTION_LEVEL=M  # L, M, Q, H

# Blockchain settings
export QRLP_BLOCKCHAIN_ENABLED_CHAINS=bitcoin,ethereum
export QRLP_BLOCKCHAIN_CACHE_DURATION=300

# Time settings
export QRLP_TIME_UPDATE_INTERVAL=60

# Identity settings
export QRLP_IDENTITY_FILE=/path/to/key.pem

# Start with environment overrides
qrlp live
```

## 🗑️ Uninstallation

### Complete Removal

#### From Source Installation
```bash
# 1. Stop any running QRLP processes
pkill -f qrlp

# 2. Remove virtual environment
rm -rf venv/

# 3. Remove QRLP directory
rm -rf qr_live_protocol/

# 4. Remove user data (optional)
rm -rf ~/.qrlp/

# 5. Remove from Python packages (if installed with pip -e)
pip uninstall qr-live-protocol
```

#### Docker Removal
```bash
# Stop and remove containers
docker stop qrlp
docker rm qrlp

# Remove images
docker rmi qrliveprotocol/qrlp

# Remove volumes (if any)
docker volume prune
```

#### Package Manager Removal
```bash
# PyPI
pip uninstall qr-live-protocol

# Homebrew (when available)
brew uninstall qrlp

# Snap
sudo snap remove qrlp
```

### Partial Cleanup

If you want to keep some data for reinstallation:

```bash
# Keep configuration but remove installation
rm -rf venv/ qr_live_protocol/

# Or keep user data
# ~/.qrlp/ contains identity files and logs
```

## 🚀 Advanced Installation

### Production Deployment

#### Systemd Service (Linux)

Create `/etc/systemd/system/qrlp.service`:

```ini
[Unit]
Description=QR Live Protocol
After=network.target

[Service]
Type=simple
User=qrlp
WorkingDirectory=/opt/qrlp
ExecStart=/opt/qrlp/venv/bin/python /opt/qrlp/main.py --config /opt/qrlp/production.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable qrlp
sudo systemctl start qrlp

# Monitor service
sudo systemctl status qrlp
sudo journalctl -u qrlp -f
```

#### Docker Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  qrlp:
    image: qrliveprotocol/qrlp:latest
    ports:
      - "8080:8080"
    volumes:
      - ./config:/app/config:ro
      - ./identity:/app/identity:ro
      - ./logs:/app/logs
    environment:
      - QRLP_WEB_HOST=0.0.0.0
      - QRLP_LOG_LEVEL=INFO
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Load Balancer Configuration (nginx)

```nginx
# /etc/nginx/sites-available/qrlp
upstream qrlp_backend {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name qrlp.yourdomain.com;

    location / {
        proxy_pass http://qrlp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for real-time updates
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Development Environment

#### VS Code Setup

1. **Install Extensions:**
   - Python (Microsoft)
   - Pylint
   - Python Docstring Generator
   - Bracket Pair Colorizer

2. **Workspace Settings** (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "files.associations": {
        "*.json": "jsonc"
    }
}
```

#### PyCharm Setup

1. **Configure Interpreter:**
   - File → Settings → Project → Python Interpreter
   - Add local virtual environment

2. **Enable Code Style:**
   - Install and configure Black code formatter
   - Enable type checking and linting

3. **Run Configuration:**
   - Add Python run config for `main.py`
   - Set working directory to project root

### Custom Installation Scripts

#### Automated Setup Script

Create `setup.sh` for automated installation:

```bash
#!/bin/bash
set -e

echo "🚀 QRLP Automated Setup"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
if [[ "$(printf '%s\n' "3.8" "$PYTHON_VERSION" | sort -V | head -n1)" != "3.8" ]]; then
    echo "❌ Python $PYTHON_VERSION found. Please use Python 3.8+"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"

# Clone repository
if [ ! -d "qr_live_protocol" ]; then
    echo "📥 Cloning repository..."
    git clone https://github.com/your-org/qr_live_protocol.git
fi

cd qr_live_protocol

# Setup virtual environment
if [ ! -d "venv" ]; then
    echo "🏗️ Creating virtual environment..."
    python3 -m venv venv
fi

echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Test installation
echo "🧪 Testing installation..."
python3 -c "from src import QRLiveProtocol; print('✅ QRLP installed successfully')"

# Generate default config
echo "⚙️ Generating default configuration..."
qrlp config-init --output config.json

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start QRLP:"
echo "  cd qr_live_protocol"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Or simply:"
echo "  qrlp live"
```

#### Windows Batch Setup

Create `setup.bat`:

```batch
@echo off
echo 🚀 QRLP Windows Setup

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo ✅ Python detected

REM Clone repository
if not exist "qr_live_protocol" (
    echo 📥 Cloning repository...
    git clone https://github.com/your-org/qr_live_protocol.git
)

cd qr_live_protocol

REM Setup virtual environment
if not exist "venv" (
    echo 🏗️ Creating virtual environment...
    python -m venv venv
)

echo 🔄 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📦 Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

REM Test installation
echo 🧪 Testing installation...
python -c "from src import QRLiveProtocol; print('✅ QRLP installed successfully')"

REM Generate config
echo ⚙️ Generating configuration...
qrlp config-init --output config.json

echo.
echo 🎉 Setup complete!
echo.
echo To start QRLP:
echo   cd qr_live_protocol
echo   call venv\Scripts\activate.bat
echo   python main.py
echo.
echo Or simply:
echo   qrlp live
pause
```

## 🔒 Security Considerations

### Production Security

1. **HTTPS Only:**
```bash
# Use reverse proxy with SSL
# Configure nginx with SSL certificates
# Never expose QRLP directly to internet without HTTPS
```

2. **Firewall Rules:**
```bash
# Only allow necessary ports
sudo ufw allow from 192.168.1.0/24 to any port 8080
sudo ufw allow from 127.0.0.1 to any port 8080
```

3. **User Permissions:**
```bash
# Run as dedicated user
sudo useradd -r -s /bin/false qrlp
sudo chown -R qrlp:qrlp /opt/qrlp
```

4. **Secret Management:**
```bash
# Store sensitive config in environment variables
export QRLP_IDENTITY_FILE=/secure/path/identity.pem
export QRLP_ENCRYPTION_KEY=$(cat /secure/encryption.key)
```

### Network Security

- **API Rate Limiting:** Implement rate limiting for web endpoints
- **Input Validation:** Validate all user inputs and file uploads
- **CORS Configuration:** Configure CORS appropriately for your use case
- **HTTPS Enforcement:** Redirect all HTTP traffic to HTTPS

### Data Protection

- **Identity Files:** Store identity files securely with appropriate permissions
- **Log Management:** Implement log rotation and retention policies
- **Backup Strategy:** Regular backups of configuration and identity data
- **Encryption at Rest:** Consider encrypting sensitive configuration files

---

**Need help with installation?** Check our [troubleshooting section](#troubleshooting) or [open an issue](https://github.com/your-org/qr_live_protocol/issues) on GitHub!

## Troubleshooting

### Common Issues

#### Permission Errors
```bash
# Solution 1: Use virtual environment
python3 -m venv venv
source venv/bin/activate
python main.py

# Solution 2: User installation
pip install --user -r requirements.txt
```

#### Port Already in Use
```bash
# Use different port
python main.py --port 8081
```

#### Dependencies Not Installing
```bash
# Update pip first
python3 -m pip install --upgrade pip

# Clear pip cache
pip cache purge

# Try installing manually
pip install Flask qrcode[pil] requests ntplib
```

#### Virtual Environment Issues on macOS
```bash
# If using externally managed Python
python3 -m venv --system-site-packages venv
source venv/bin/activate
python main.py
```

#### Network/Firewall Issues
```bash
# Allow connections through firewall
# macOS: System Preferences > Security & Privacy > Firewall
# Linux: sudo ufw allow 8080
# Windows: Windows Defender Firewall settings
```

### Getting Help

1. **Check Logs**: Enable debug mode with `--debug` flag
2. **GitHub Issues**: Report bugs at [github.com/your-org/qr_live_protocol/issues](https://github.com/your-org/qr_live_protocol/issues)
3. **Documentation**: Full docs at [docs/README.md](README.md)
4. **Community**: Join discussions in GitHub Discussions

## Uninstallation

### Remove QRLP
```bash
# If installed via pip
pip uninstall qr-live-protocol

# If installed from source
cd qr_live_protocol
pip uninstall -e .

# Remove configuration
rm -rf ~/.qrlp/
```

### Clean Virtual Environment
```bash
# Remove virtual environment
rm -rf venv/
```

## Security Considerations

### Network Security
- QRLP runs a web server on localhost by default
- For production use, consider HTTPS and firewall rules
- Blockchain API calls are read-only and safe

### Data Privacy
- Identity hashes are cryptographic and don't expose personal data
- No personal information is transmitted to external services
- All blockchain queries are anonymous

### Production Deployment
For production use:
1. Use a WSGI server (gunicorn, uwsgi)
2. Configure HTTPS with SSL certificates
3. Set up proper firewall rules
4. Monitor logs and performance
5. Consider using environment variables for sensitive configuration

## Next Steps

After successful installation:
1. Read the [Quick Start Guide](../QUICKSTART.md)
2. Explore [Configuration Options](CONFIGURATION.md)
3. Try [Examples](../examples/)
4. Set up [OBS Integration](STREAMING.md)
5. Check out the [API Reference](API.md)

---

**Need help?** Open an issue on [GitHub](https://github.com/your-org/qr_live_protocol/issues) or check our [FAQ](FAQ.md). 