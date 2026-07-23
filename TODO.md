# QRLP TODO — Upcoming Improvements

Last updated: 2026-07-23  
Current version: 1.4.0  
Test suite: 602 tests, 0 failures

---

## Completed (v1.1.0 + v1.2.0 + v1.3.0)

### Code Cleanup
- [x] Remove 29+ unused imports across 9 source modules
- [x] Remove unused mock fixtures from conftest.py
- [x] Remove placeholder comments from _get_key_by_id in hmac.py and encryptor.py
- [x] Remove all MagicMock/AsyncMock usage from tests

### Architecture
- [x] Add VerificationResult dataclass
- [x] Add QRData.to_dict(), __repr__, __str__ methods
- [x] Add QRData.from_dict() classmethod
- [x] Export VerificationResult from src package

### Security
- [x] Add Content-Security-Policy headers to all web responses
- [x] Add HMAC key rotation (key_store, add_key, rotate_key)
- [x] Add encryption key rotation (key_store, add_key, rotate_key)
- [x] Add PBKDF2-HMAC-SHA256 key derivation for KeyManager
- [x] Add WebSocket input validation using SecurityValidator

### Performance
- [x] Add requests.Session connection pooling to BlockchainVerifier

### New CLI Commands
- [x] qrlp config-validate <path>
- [x] qrlp status --json-output

### Test Coverage Gaps
- [x] Tests for cli live/dashboard (subprocess)
- [x] Tests for web_server broadcast/stop
- [x] Tests for config YAML and web alias
- [x] Tests for signer sign_message/verify_message (RSA+ECDSA)
- [x] Tests for error_recovery async resilient functions
- [x] Tests for async_core optimization internals
- [x] Tests for core _update_loop error path
- [x] Tests for QR generator style fallbacks
- [x] Tests for HMAC type handling

### Documentation
- [x] Update docs/API.md with VerificationResult and crypto exceptions
- [x] Update src/AGENTS.md with crypto pipeline
- [x] Update docs/AUTHENTICATION_CHALLENGES.md with forward-compat QR payloads
- [x] Update docs/INSTALLATION.md with pytest-asyncio and optional deps
- [x] Update ASSESSMENT.md with coverage table

---

## Minor Improvements (v1.4.0)

### Architecture
- [ ] Extract a QRSerializer class to centralize JSON serialization/deserialization logic
- [ ] Add async NTP support to async_core.py

### Feature Additions
- [ ] Add `qrlp keys rotate <key_id>` — generate a new key pair and update trust stores
- [ ] Add batch verification — `qrlp verify --file batch.json`
- [ ] Add QR expiry notification callback
- [ ] Add WebSocket authentication for admin operations

### Test Infrastructure
- [ ] Add property-based tests with hypothesis for chunk round-trip
- [ ] Add real Flask server integration tests on random port
- [ ] Add fuzz tests for QRData.from_json with random JSON payloads
- [ ] Add tests for QRGenerator.verify_qr_readability with real pyzbar (skip if not installed)

---

## Major Improvements (v2.0.0+)

### Protocol Enhancements
- [ ] Add QR payload versioning
- [ ] Add on-chain content commitment
- [ ] Add decentralized identity (DIDs/verifiable credentials)
- [ ] Add QR payload compression (zlib/gzip)
- [ ] Add QR payload encryption with ECDH
- [ ] Add multi-signature QR payloads
- [ ] Add QR revocation

### Platform Support
- [ ] Add Docker container with health check
- [ ] Add systemd service unit
- [ ] Add Kubernetes manifest
- [ ] Add Prometheus metrics endpoint
- [ ] Add OpenTelemetry tracing
- [ ] Add native mobile scanner SDK
- [ ] Add OBS Studio plugin

### Infrastructure
- [ ] Add CI/CD pipeline with GitHub Actions
- [ ] Add pre-commit hooks
- [ ] Add semantic release automation
- [ ] Add PyPI publishing workflow
- [ ] Add ReadTheDocs documentation build
- [ ] Add SECURITY.md
- [ ] Add Dependabot configuration
- [ ] Add Snyk/CodeQL security scanning

### Architecture (v2.0.0)
- [ ] Migrate from Flask to FastAPI
- [ ] Replace requests with httpx
- [ ] Add SQLite-backed key store
- [ ] Add plugin system
- [ ] Add gRPC API
- [ ] Add WebSocket-based live QR streaming API
- [ ] Add multi-tenancy
- [ ] Add audit logging
