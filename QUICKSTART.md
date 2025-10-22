# QR Live Protocol - Quick Start Guide

## 🚀 Modern Setup and Launch

To get QRLP running with a live QR code display using modern Python tooling:

```bash
# Modern setup with uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e .[dev]
python main.py
```

Or for the traditional approach:

```bash
# Traditional pip setup
python3 -m venv venv
source venv/bin/activate
pip install -e .[dev]
python main.py
```

This setup will:
1. ✅ Create modern virtual environment with uv
2. 📦 Install all dependencies with dependency resolution
3. 🔧 Set up the QRLP package for development
4. 🌐 Start the web server
5. 📱 Begin live QR generation (updates every 1 second!)
6. 🌍 Automatically open your browser to view the live display

## 🎯 What You'll See

The browser will open to `http://localhost:8080` showing:
- **Live QR Code** updating every second
- **Real-time timestamp** from synchronized time servers
- **Identity hash** from your system fingerprint
- **Blockchain verification** (Bitcoin, Ethereum current block hashes)
- **Verification status** and statistics
- **Raw data display** showing all encoded information

## 🎥 For Livestreaming (OBS Studio)

1. In OBS Studio, add a **Browser Source**
2. Set URL to: `http://localhost:8080/viewer`
3. Set dimensions: Width: 800, Height: 600
4. The QR code will now appear in your stream, updating live!

## ⚙️ Command Options

```bash
# Full setup and demo (default)
python main.py

# Don't auto-open browser
python main.py --no-browser

# Use custom port
python main.py --port 9000

# Alternative: Use uv for everything
uv venv && source .venv/bin/activate && uv pip install -e .[dev] && python main.py
```

## 🔍 What's in the QR Code

Each QR code contains JSON data with:
```json
{
  "timestamp": "2025-01-11T15:30:45.123Z",
  "sequence_number": 123,
  "identity_hash": "abc123def456...",
  "blockchain_hashes": {
    "bitcoin": "00000000000000000008a...",
    "ethereum": "0x1234567890abcdef..."
  },
  "time_server_verification": [
    {"server": "pool.ntp.org", "offset": 0.002},
    {"server": "time.google.com", "offset": 0.001}
  ],
  "format_version": "1.0.0"
}
```

## 🛑 Stopping the Demo

Press **Ctrl+C** to cleanly stop the demo. This will:
- Stop QR generation
- Shut down the web server
- Display final statistics
- Clean up temporary files

## 🔧 Advanced Usage

### CLI Commands (after setup)
```bash
# Start live QR generation
qrlp live

# Generate single QR code
qrlp generate --output my_qr.png

# Verify QR data
qrlp verify '{"timestamp":"2025-01-11T..."}'

# Check system status
qrlp status

# Initialize config file
qrlp config-init --output config.json

# Use setup script for quick installation
./setup.sh
```

### Direct Python Usage
```python
from src import QRLiveProtocol, QRLPConfig

# Create with custom settings
config = QRLPConfig()
config.update_interval = 0.5  # Update every 0.5 seconds

qrlp = QRLiveProtocol(config)

# Generate single QR
qr_data, qr_image = qrlp.generate_single_qr()

# Start live generation
qrlp.start_live_generation()
```

### Setup Script Usage
```bash
# Quick setup with setup.sh
./setup.sh

# Or install uv and use it
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv && source .venv/bin/activate && uv pip install -e .[dev]
```

## 📊 Monitoring

Visit these URLs while the demo is running:
- `http://localhost:8080` - Main interface
- `http://localhost:8080/viewer` - Clean viewer for streaming
- `http://localhost:8080/admin` - Admin panel with statistics
- `http://localhost:8080/api/status` - JSON status endpoint
- `http://localhost:8080/api/verify` - QR verification endpoint

## 🆘 Troubleshooting

### Dependencies Not Installing
```bash
# Update pip first
python3 -m pip install --upgrade pip

# Then run setup with uv (recommended)
uv venv && source .venv/bin/activate && uv pip install -e .[dev]

# Or traditional pip approach
python3 -m venv venv && source venv/bin/activate && pip install -e .[dev]
```

### Port Already in Use
```bash
# Use different port
python main.py --port 8081
```

### Browser Doesn't Open
```bash
# Disable auto-open and manually navigate
python main.py --no-browser
# Then open: http://localhost:8080
```

### Permission Issues
```bash
# Install for user only
pip install --user -r requirements.txt
python main.py
```

### uv Not Available
```bash
# Install uv first
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv

# Then use uv for setup
uv venv && source .venv/bin/activate && uv pip install -e .[dev]
```

## 🎉 Success Indicators

You'll know everything is working when you see:
1. ✅ Dependency installation messages
2. 🌐 "Web server started on port 8080"
3. 📱 "QR #1 | 2025-01-11T... | Identity: abc123... | Blockchain: 2 chains"
4. 🌍 Browser opens automatically showing live QR codes
5. QR codes visibly changing every second

Enjoy your live, cryptographically verified QR codes! 🔲✨ 