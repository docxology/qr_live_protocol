# QRLP Frequently Asked Questions

## General Questions

### What is QR Live Protocol (QRLP)?

QRLP is a system for generating and displaying live QR codes with local integrity checks and optional public-key authenticity verification. It's designed for livestreaming and official video releases where viewers need timing context and a verifier can be configured with the issuer's trusted public key.

### Who should use QRLP?

- **Content Creators** - YouTubers, Twitch streamers, podcasters
- **News Organizations** - Live broadcasts requiring authenticity
- **Corporate Communications** - Official announcements and presentations
- **Legal/Compliance** - Time-stamped document verification
- **Educational Institutions** - Lecture recordings and webinars
- **Event Organizers** - Live event authentication

### Is QRLP free to use?

Yes! QRLP is completely open source and free to use. There are no licensing fees, subscription costs, or usage limits.

## Technical Questions

### How does the verification work?

QRLP uses multiple verification layers:

1. **Time Verification** - Synchronizes with multiple time servers (NTP, HTTP APIs)
2. **Blockchain Verification** - Retrieves current block hashes from Bitcoin, Ethereum, etc.
3. **Identity Verification** - Cryptographic hash of system/file identity
4. **Format Verification** - JSON schema and data integrity checks

Anyone can verify a QR code by checking these components against public sources.

### What blockchain networks are supported?

Currently supported:
- **Bitcoin** - Latest block hash
- **Ethereum** - Latest block hash
- **Litecoin** - Latest block hash (optional)
- **Dogecoin** - Latest block hash (optional)

Support for additional networks is planned for future versions.

### How often do QR codes update?

By default, every 5 seconds. This is configurable from 1 second to several minutes depending on your needs. Faster updates provide better verification granularity but use more resources.

### What data is stored in the QR codes?

Each QR code contains:
- **Timestamp** - Precise generation time (ISO format)
- **Identity Hash** - Cryptographic identifier of the generator
- **Blockchain Hashes** - Current block hashes from enabled networks
- **Time Server Data** - Verification from multiple time sources
- **Sequence Number** - Incremental counter
- **User Data** - Optional custom data you specify

### How large are the QR codes?

QR code size depends on:
- **Data amount** - More blockchain networks = larger codes
- **Error correction level** - Higher levels create denser codes
- **Box size** - Display pixel size (configurable)

Typical sizes: 25x25 to 40x40 modules (250x250 to 400x400 pixels at default settings)

## Installation & Setup

### What are the system requirements?

- **Python**: 3.8 or higher
- **Memory**: 512MB RAM minimum
- **Disk**: ~100MB for installation
- **Network**: Internet connection for blockchain/time verification
- **OS**: macOS, Linux, or Windows

### How do I install QRLP?

The easiest method:
```bash
git clone https://github.com/docxology/qr_live_protocol.git
cd qr_live_protocol
python main.py
```

This automatically handles dependencies and setup. See [Installation Guide](INSTALLATION.md) for detailed instructions.

### Can I run QRLP without internet?

Yes, but with limitations:
- No blockchain verification (uses cached data)
- No time server synchronization (uses local time)
- Verification will indicate reduced authenticity
- All other features work normally

### Does QRLP work on Raspberry Pi?

Yes! QRLP runs well on Raspberry Pi 3B+ and newer models. Recommended:
- Raspberry Pi 4 with 2GB+ RAM
- Fast microSD card (Class 10)
- Stable internet connection

## Usage Questions

### How do I integrate with OBS Studio?

1. Start QRLP: `python main.py`
2. In OBS, add "Browser Source"
3. Set URL to: `http://localhost:8080/viewer`
4. Set Width: 800, Height: 600
5. Check "Shutdown source when not visible"

The QR codes will update automatically in your stream.

### Can I customize the QR code appearance?

Yes! You can configure:
- **Colors** - Fill and background colors
- **Size** - Box size and border thickness
- **Error correction** - L, M, Q, H levels
- **Styles** - Live, professional, minimal themes

See [Configuration Guide](CONFIGURATION.md) for details.

### How do I verify QR codes from viewers?

Viewers can:
1. **Scan with phone** - See the JSON payload directly
2. **API verification** - Use QRLP's `/api/verify` endpoint backed by a configured verifier
3. **Public-key verification** - Verify signed QR data with the issuer's trusted public key
4. **Third-party tools** - Import verification logic into other applications

A normal QR scanner can read the payload, but it does not prove authenticity by itself.

### Can I add custom data to QR codes?

Yes! You can include custom data like:
- Event information
- Video metadata
- User identifiers
- Tracking codes
- Any JSON-serializable data

Example:
```python
custom_data = {
    "event": "My Live Stream",
    "video_id": "abc123",
    "topic": "QRLP Demo"
}
qr_data, qr_image = qrlp.generate_single_qr(user_data=custom_data)
```

## Streaming & Production

### Will QRLP slow down my stream?

No. QRLP is designed to be lightweight:
- **CPU usage**: <5% on modern systems
- **Memory**: ~50MB base usage
- **Network**: Minimal (only blockchain/time API calls)
- **Browser source**: Optimized for OBS performance

### Can multiple streamers use the same setup?

Each QRLP instance should have unique identity. You can:
- Run separate instances on different ports
- Use different identity files for each streamer
- Configure custom user data to distinguish streams

### What happens if QRLP crashes during a stream?

- QR codes stop updating but stream continues
- Last generated QR remains visible
- Restart QRLP to resume updates
- Consider monitoring tools for production use

### Can I use QRLP for pre-recorded videos?

Yes! QRLP can:
- Generate QR codes for specific timestamps
- Create verification data for video segments
- Provide authenticity proof for recorded content
- Export QR sequences for video editing

## Security & Privacy

### Is my personal data transmitted anywhere?

QRLP does not intentionally upload identity files or raw system fingerprints, but it can contact configured external services:
- Public blockchain APIs for latest block data
- Public time servers for clock checks
- Local system info for identity hashing, stored only in the generated hash

External services can still observe ordinary request metadata such as source IP address and timing. Disable blockchain/time-server integrations in config if you need a fully local mode.

### Can the identity hash be reverse-engineered?

The identity hash uses SHA-256 cryptography and includes:
- System information (hostname, MAC address)
- File contents (if specified)
- Random components

While technically secure, avoid including sensitive files in identity generation.

### How secure is the verification system?

QRLP separates trust layers:
- **HMAC** detects tampering only for verifiers with the same private HMAC secret.
- **Digital signatures** provide public authenticity when the verifier trusts the issuer public key.
- **Timestamps and optional blockchain hashes** provide freshness context, not independent proof of issuer identity.
- **Open source** code makes the verification logic auditable.

### Can QR codes be forged?

Tampering with a signed or HMAC-protected QR payload is detected. A forged QR is still possible if a verifier trusts the wrong public key, accepts unsigned data, or treats blockchain freshness context as issuer identity. Use trusted public keys for public verification.
- Coordinating time server responses (practically impossible)

## Performance & Troubleshooting

### QRLP is using too much CPU/memory

Try these optimizations:
- Increase `update_interval` (less frequent updates)
- Reduce `enabled_chains` (fewer blockchain networks)
- Increase `cache_duration` (less frequent API calls)
- Use lower QR error correction level

### Blockchain verification keeps failing

Common solutions:
- Check internet connection
- Try different blockchain APIs in configuration
- Increase timeout values
- Disable problematic chains temporarily

### Web interface won't load

Check these issues:
- Port 8080 availability (try different port)
- Firewall settings
- Browser cache (try incognito mode)
- QRLP startup logs for errors

### QR codes aren't updating

Troubleshooting steps:
1. Check QRLP logs for errors
2. Verify network connectivity
3. Restart QRLP service
4. Check configuration file syntax
5. Try manual QR generation: `qrlp generate`

## Development & Integration

### Can I integrate QRLP into my application?

Yes! QRLP provides multiple integration options:
- **Python API** - Import as library
- **REST API** - HTTP endpoints
- **WebSocket API** - Real-time updates
- **CLI tools** - Command-line interface

See [API Documentation](API.md) for details.

### Does QRLP support other programming languages?

Currently Python-native, but you can integrate via:
- REST API (any language with HTTP support)
- WebSocket API (most modern languages)
- CLI tools (shell/subprocess calls)

Additional language SDKs are planned for future versions.

### Can I contribute to QRLP development?

Absolutely! We welcome:
- **Code contributions** - Bug fixes, new features
- **Documentation** - Improvements and translations
- **Testing** - Bug reports and testing
- **Ideas** - Feature requests and feedback

See [Contributing Guide](CONTRIBUTING.md) to get started.

### Is there a plugin system?

Not yet, but it's planned for version 2.0. Current extension options:
- Custom callbacks for QR updates
- Configuration file customization
- REST API integration
- Custom identity files

## Licensing & Legal

### What license is QRLP released under?

QRLP is released under CC BY-NC-SA 4.0, which allows:
- ✅ Non-commercial sharing
- ✅ Non-commercial modification
- ✅ Distribution under the same license
- ✅ Private use
- ❌ Commercial use without separate permission
- ❌ Warranty/liability

### Can I use QRLP commercially?

Not under the default license. CC BY-NC-SA 4.0 is non-commercial, so commercial or business use requires separate permission or a separate commercial license.

### Are there any usage restrictions?

Yes. The default license requires attribution, non-commercial use, and ShareAlike distribution for adaptations. Also:
- Do not use QRLP commercially without separate permission
- Consider contributing improvements back to the public repository
- Respect blockchain network terms of service

### What about patent concerns?

We're not aware of any relevant patents, but we can't provide legal advice. Consult with legal counsel for commercial deployments if concerned.

## Support & Community

### Where can I get help?

- **Documentation** - Check this FAQ and other docs
- **GitHub Issues** - Report bugs and request features
- **GitHub Discussions** - Community Q&A
- **Email Support** - contact@qrlp.org for complex issues

### How do I report bugs?

1. Check if it's already reported in GitHub Issues
2. Create new issue with:
   - Clear description of problem
   - Steps to reproduce
   - System information
   - Log files (if applicable)
   - Expected vs actual behavior

### Is there a community forum?

Yes! Use [GitHub Discussions](https://github.com/docxology/qr_live_protocol/discussions) for:
- General questions
- Usage tips
- Feature discussions
- Community showcase

### How can I stay updated?

- **Watch** the GitHub repository for notifications
- **Star** the project to show support
- **Follow** release announcements
- **Join** community discussions

---

**Still have questions?** Create an issue on [GitHub](https://github.com/docxology/qr_live_protocol/issues) or contact us at contact@qrlp.org!
