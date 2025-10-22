# QRLP Streaming Integration Guide

## Overview

QRLP is designed specifically for livestreaming applications where authenticity verification is crucial. This guide covers integration with popular streaming software and platforms.

## OBS Studio Integration

### Quick Setup

1. **Start QRLP**
   ```bash
   python main.py
   # Or: qrlp live
   ```

2. **Add Browser Source in OBS**
   - Click **Sources** → **+** → **Browser Source**
   - Create new source named "QRLP Viewer"
   - Set URL: `http://localhost:8080/viewer`
   - Set Width: `800`, Height: `600`
   - Check "Shutdown source when not visible"
   - Check "Refresh browser when scene becomes active"

3. **Position and Style**
   - Resize and position the QR overlay as needed
   - Use **Filters** → **Color Correction** to adjust appearance
   - Add **Chroma Key** filter if using green screen mode

### Advanced OBS Configuration

#### Performance Optimization

```
Browser Source Settings:
✅ Width: 800px
✅ Height: 600px  
✅ FPS: 30 (matches your stream)
✅ Shutdown source when not visible: ON
✅ Refresh browser when scene becomes active: ON
❌ Use hardware acceleration: OFF (can cause issues)
```

#### User Input Integration

QRLP now supports real-time user input that gets included in QR codes:

1. **Access the main interface** at `http://localhost:8080`
2. **Enter custom messages** in the "User Input" section
3. **Save messages** - they'll be included in all subsequent QR codes
4. **Real-time updates** - Changes appear immediately in the viewer

This is perfect for:
- **Live Q&A sessions** - Include current question
- **Event information** - Add event details or announcements  
- **Viewer engagement** - Include social media handles or calls-to-action
- **Context data** - Add stream topic or current segment info

#### Enhanced Blockchain Display

The viewer now shows complete blockchain information:
- **Full hashes** instead of truncated versions
- **Copy buttons** for easy verification
- **Better formatting** for readability
- **Multiple chain support** with clear labeling

#### Multiple QR Layouts

Create different scenes for different QR placements:

1. **Corner Overlay** - Small QR in corner (300x300)
2. **Full Display** - Large QR center screen (600x600)
3. **Sidebar** - QR in side panel (400x400)
4. **Picture-in-Picture** - QR over webcam (250x250)

#### Custom CSS Styling

Add custom CSS to browser source:

```css
/* Hide background for transparency */
body { background: transparent !important; }

/* Custom QR positioning */
#qr-container {
    border-radius: 15px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    background: rgba(255,255,255,0.9);
    padding: 10px;
}

/* Animated border */
#qr-container {
    border: 3px solid #00ff00;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { border-color: #00ff00; }
    50% { border-color: #ff0000; }
    100% { border-color: #00ff00; }
}
```

### OBS Filters and Effects

#### Green Screen Background

Configure QRLP for green screen:
```json
{
  "web_settings": {
    "viewer_background_color": "#00ff00",
    "qr_background_transparent": true
  }
}
```

Add **Chroma Key** filter in OBS:
- Key Color Type: Green
- Similarity: 400
- Smoothness: 80

#### Professional Styling

Add these OBS filters to the browser source:
1. **Color Correction** - Enhance contrast
2. **Sharpen** - Improve QR readability  
3. **Drop Shadow** - Add depth
4. **Color Key** - Remove backgrounds

## Streamlabs OBS Integration

### Setup Process

1. **Add Browser Source**
   - Sources → Add Source → Browser Source
   - URL: `http://localhost:8080/viewer`
   - Width: 800, Height: 600
   - Enable "Shutdown source when not visible"

2. **Widget Styling**
   - Use Streamlabs' widget editor
   - Apply custom CSS for branding
   - Configure transparency and positioning

### Streamlabs Specific Features

```css
/* Streamlabs-optimized CSS */
.qr-widget {
    position: absolute;
    top: 20px;
    right: 20px;
    z-index: 1000;
    background: rgba(0,0,0,0.8);
    border-radius: 10px;
    padding: 15px;
}

.qr-title {
    color: #ffffff;
    font-family: 'Streamlabs Sans', sans-serif;
    text-align: center;
    margin-bottom: 10px;
}
```

## XSplit Integration

### Adding QRLP to XSplit

1. **Add Webpage Source**
   - Sources → Add → Web page
   - URL: `http://localhost:8080/viewer`
   - Resolution: 800x600
   - Enable "Use transparent background"

2. **Positioning and Scaling**
   - Drag to desired position
   - Use corner handles to resize
   - Right-click → Properties for fine-tuning

### XSplit Performance Tips

- Enable "Hardware acceleration" in XSplit settings
- Set webpage refresh rate to match stream framerate
- Use "Static" mode if QR updates are infrequent

## Platform-Specific Configurations

### YouTube Live

Optimized settings for YouTube Live:

```json
{
  "update_interval": 2.0,
  "qr_settings": {
    "error_correction_level": "M",
    "box_size": 10,
    "border_size": 4
  },
  "web_settings": {
    "viewer_show_title": true,
    "viewer_show_timestamp": true,
    "viewer_show_verification": true
  }
}
```

### Twitch

Configuration for Twitch streaming:

```json
{
  "update_interval": 1.0,
  "qr_settings": {
    "error_correction_level": "H",
    "box_size": 12,
    "border_size": 6
  },
  "blockchain_settings": {
    "enabled_chains": ["bitcoin", "ethereum"],
    "cache_duration": 120
  }
}
```

### Facebook Live

Facebook Live optimizations:

```json
{
  "update_interval": 5.0,
  "qr_settings": {
    "error_correction_level": "Q",
    "box_size": 14
  },
  "web_settings": {
    "viewer_theme": "facebook",
    "viewer_show_logo": false
  }
}
```

## Mobile Streaming

### iOS (via Restream, etc.)

1. **Setup QRLP on computer**
2. **Use mobile hotspot or same WiFi**
3. **Configure mobile streaming app**
   - Add overlay URL: `http://[computer-ip]:8080/viewer`
   - Position overlay appropriately
   - Test before going live

### Android Streaming Apps

Compatible with:
- **Restream Studio**
- **Streamlabs Mobile**
- **OBS Camera**
- **CameraFi Live**

Configuration:
```bash
# Allow external connections
qrlp live --host 0.0.0.0 --port 8080

# Find your computer's IP
# On macOS/Linux: ifconfig | grep inet
# On Windows: ipconfig
```

## Professional Broadcasting

### Hardware Considerations

For professional setups:

**Recommended Hardware:**
- **CPU**: Intel i7/AMD Ryzen 7 or better
- **RAM**: 16GB minimum, 32GB preferred
- **Network**: Wired ethernet connection
- **Storage**: SSD for better performance

**Dedicated Streaming PC Setup:**
1. Run QRLP on streaming PC
2. Use NDI or capture card for main PC
3. Configure network settings for cross-PC communication

### Production Workflow

```bash
# 1. Pre-stream setup
qrlp status                    # Verify system health
qrlp generate --test          # Test QR generation

# 2. Start live generation
qrlp live --config production.json

# 3. Monitor during stream
tail -f ~/.qrlp/logs/qrlp.log  # Watch logs

# 4. Post-stream verification
qrlp verify [qr-data-from-stream]
```

### Backup and Redundancy

For critical broadcasts:

1. **Run Multiple QRLP Instances**
   ```bash
   # Primary
   qrlp live --port 8080 --identity-file primary.key
   
   # Backup  
   qrlp live --port 8081 --identity-file backup.key
   ```

2. **Configure OBS Scene Switching**
   - Primary scene with port 8080
   - Backup scene with port 8081
   - Hotkey switching between scenes

3. **Network Monitoring**
   ```bash
   # Monitor connectivity
   ping -c 1 time.nist.gov && echo "Time servers OK"
   curl -s https://api.blockcypher.com/v1/btc/main | jq .height
   ```

## Advanced Integration

### Custom Web Interface

Create branded QR display:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Custom QRLP Viewer</title>
    <style>
        body { 
            background: linear-gradient(45deg, #1e3c72, #2a5298);
            font-family: 'Arial', sans-serif;
        }
        .qr-container {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            flex-direction: column;
        }
        .brand-logo {
            width: 150px;
            margin-bottom: 20px;
        }
        .qr-code {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.3);
        }
        .verification-info {
            color: white;
            text-align: center;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="qr-container">
        <img src="logo.png" class="brand-logo" alt="Brand Logo">
        <div id="qr-display" class="qr-code"></div>
        <div id="verification-info" class="verification-info"></div>
    </div>
    
    <script src="/socket.io/socket.io.js"></script>
    <script>
        const socket = io();
        
        socket.on('qr_update', function(data) {
            document.getElementById('qr-display').innerHTML = 
                `<img src="${data.qr_image}" alt="QR Code">`;
            document.getElementById('verification-info').innerHTML = 
                `Sequence: #${data.qr_data.sequence_number} | 
                 Chains: ${Object.keys(data.qr_data.blockchain_hashes).length}`;
        });
        
        // Request initial QR
        socket.emit('request_qr_update');
    </script>
</body>
</html>
```

### API Integration

Integrate with streaming platforms:

```python
import requests
from src import QRLiveProtocol

qrlp = QRLiveProtocol()

def stream_started_callback(qr_data, qr_image):
    # Send to streaming platform API
    requests.post('https://api.platform.com/overlay', {
        'stream_id': 'your_stream_id',
        'overlay_data': qr_data.to_json(),
        'overlay_image': qr_image
    })

qrlp.add_update_callback(stream_started_callback)
qrlp.start_live_generation()
```

### Webhook Integration

Set up webhooks for stream events:

```python
from flask import Flask, request
from src import QRLiveProtocol

app = Flask(__name__)
qrlp = QRLiveProtocol()

@app.route('/webhook/stream-start', methods=['POST'])
def stream_started():
    # Start QR generation when stream begins
    qrlp.start_live_generation()
    return {'status': 'QR generation started'}

@app.route('/webhook/stream-end', methods=['POST'])  
def stream_ended():
    # Stop QR generation when stream ends
    qrlp.stop_live_generation()
    return {'status': 'QR generation stopped'}

if __name__ == '__main__':
    app.run(port=9000)
```

## Troubleshooting

### Common Issues

#### Browser Source Not Loading
```bash
# Check QRLP is running
curl http://localhost:8080/viewer

# Check firewall settings
# macOS: System Preferences > Security & Privacy > Firewall
# Windows: Windows Defender Firewall settings
```

#### QR Codes Not Updating in Stream
```bash
# Verify WebSocket connections
curl http://localhost:8080/api/status | jq .websocket_connections

# Check OBS browser cache
# OBS: Right-click source > Refresh Cache
```

#### Performance Issues
```bash
# Monitor resource usage
top -p $(pgrep -f qrlp)

# Optimize configuration
{
  "update_interval": 5.0,
  "blockchain_settings": {
    "cache_duration": 600
  }
}
```

### Performance Optimization

For high-performance streaming:

1. **Increase cache durations**
2. **Reduce update frequency**  
3. **Use wired network connection**
4. **Close unnecessary applications**
5. **Monitor system resources**

### Quality Settings

Recommended settings by use case:

**Casual Streaming:**
- Update interval: 5 seconds
- Error correction: M
- Single blockchain (Bitcoin)

**Professional Broadcasting:**
- Update interval: 2 seconds  
- Error correction: H
- Multiple blockchains
- Backup systems

**High-Frequency Trading/Finance:**
- Update interval: 1 second
- Error correction: H
- All blockchain networks
- Hardware redundancy

---

Need help with streaming integration? Check our [FAQ](FAQ.md) or create an issue on [GitHub](https://github.com/your-org/qr_live_protocol/issues)! 