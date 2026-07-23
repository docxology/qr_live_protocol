# QRLP TODO — Upcoming Improvements

Last updated: 2026-07-22  
Current version: 1.2.0  
Test suite: 567 tests, 87% coverage, 0 failures

---

## Completed (v1.1.0 + v1.2.0)

### Code Cleanup
- [x] Remove 29 unused imports across 9 source modules
- [x] Remove unused `socket` and `struct` imports from `time_provider.py`
- [x] Remove unused `send_from_directory` import from `web_server.py`
- [x] Remove unused `hashlib` import from `blockchain_verifier.py`
- [x] Remove unused `Tuple` import from `crypto/encryptor.py` and `time_provider.py`
- [x] Remove unused `Union` import from `core.py` and `async_core.py`
- [x] Remove unused `threading` import from `async_core.py`
- [x] Remove unused `asdict` import from `async_core.py` and `blockchain_verifier.py`
- [x] Remove unused `hashes` and `hmac` imports from `crypto/encryptor.py`
- [x] Remove unused `hashes`, `hashlib`, `padding`, `utils` from `crypto/key_manager.py` and `crypto/signer.py`
- [x] Remove unused mock fixtures from `conftest.py` (mock_time_provider, mock_blockchain_verifier, mock_identity_manager)
- [x] Remove placeholder comments from `_get_key_by_id` in `hmac.py` and `encryptor.py`
- [x] Remove all `MagicMock` / `AsyncMock` usage from tests — replaced with real instances or real local HTTP server

### Architecture
- [x] Add `VerificationResult` dataclass to replace untyped dict from `verify_qr_data`
- [x] Add `QRData.to_dict()`, `__repr__`, `__str__` methods
- [x] Export `VerificationResult` from `src` package

### Security
- [x] Add Content-Security-Policy headers to all web responses (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy)

### Performance
- [x] Add `requests.Session` connection pooling to `BlockchainVerifier`

### New CLI Commands
- [x] `qrlp config-validate <path>` — validate config without starting QRLP
- [x] `qrlp status --json-output` — machine-readable JSON status

---

## Minor Improvements (v1.2.1)

### Test Coverage Gaps (87% -> 95%+ target)
- [ ] Add tests for `cli.py` `live` and `dashboard` commands (lines 58-111, 126-173) — block indefinitely; use subprocess with timeout
- [ ] Add tests for `web_server.py` `_run_server` method (lines 644-686) — starts a real server; test with a real Flask test client on a random port
- [ ] Add tests for `web_server.py` WebSocket event handlers (lines 587-609) — `handle_connect`, `handle_disconnect`, `handle_qr_request`, `handle_user_data_update`
- [ ] Add tests for `web_server.py` `_broadcast_qr_update` and `_send_qr_update_to_client` (lines 613-626)
- [ ] Add tests for `config.py` `from_file` YAML path (lines 185-192) and `web` alias (line 200)
- [ ] Add tests for `qr_generator.py` styled image fallback paths (lines 305-323) when `STYLED_QR_AVAILABLE` is False
- [ ] Add tests for `signer.py` `sign_message` and `verify_message` methods (lines 122-128, 137-138)
- [ ] Add tests for `error_recovery.py` `resilient_qr_generation_async` and `resilient_verification_async` (lines 715-758)
- [ ] Add tests for `async_core.py` optimization internals — `optimize_performance_async`, `apply_optimizations_async` (lines 523-539, 569-583)
- [ ] Add tests for `core.py` `_update_loop` error path (line 567-570) and `remove_update_callback` (line 145)

### Documentation
- [ ] Update `docs/INSTALLATION.md` to reference v1.2.0 and mention `pytest-asyncio` requirement
- [ ] Update `docs/COGNITIVE_SECURITY.md` with the `KeyManagementError` rename
- [ ] Update `docs/AUTHENTICATION_CHALLENGES.md` with the forward-compatible `QRData.from_json` behavior
- [ ] Update `docs/API.md` with `HMACError` export, `KeyManagementError` rename, and `VerificationResult` dataclass
- [ ] Update `src/AGENTS.md` to reflect the actual implemented crypto pipeline (Sign -> HMAC -> Encrypt)
- [ ] Update `ASSESSMENT.md` coverage numbers (87% total, module-by-module table)

---

## Medium Improvements (v1.3.0)

### Security Hardening
- [ ] Add CSRF protection for state-changing web endpoints (currently only admin token and rate limiting)
- [ ] Add input length validation for WebSocket `update_user_data` event (currently uses 500-char limit but doesn't use `SecurityValidator`)
- [ ] Add HMAC key rotation support — `HMACManager._get_key_by_id` only supports the master key
- [ ] Add encryption key rotation support — `DataEncryptor._get_key_by_id` always returns the master key
- [ ] Add key derivation function (PBKDF2/scrypt) for master key — currently stored as raw bytes in `~/.qrlp/keys/.master_key`

### Architecture
- [ ] Extract a `QRSerializer` class to centralize JSON serialization/deserialization logic (currently duplicated in `QRData.to_json`, `core.py`, `signer.py`, `hmac.py`)
- [ ] Add async NTP support to `async_core.py` — `_get_time_from_server_async` falls back to HTTP time API because NTP is sync-only; consider `aiontp` or raw UDP

### Feature Additions
- [ ] Add `qrlp verify --qr-image <path>` — scan a PNG QR image file and verify its payload (requires `pyzbar` + `opencv-python` from `[full]` extras)
- [ ] Add `qrlp keys rotate <key_id>` — generate a new key pair and update trust stores
- [ ] Add `qrlp export --format csv` — export QR generation history as CSV
- [ ] Add WebSocket authentication for admin operations (currently only HTTP routes check admin token)
- [ ] Add QR expiry notification callback — call a user callback when a QR payload expires
- [ ] Add batch verification — `qrlp verify --file batch.json` that verifies multiple QR payloads
- [ ] Add `QRData.from_dict()` classmethod — inverse of `to_dict()`

### Test Infrastructure
- [ ] Add `pytest --benchmark` benchmarks for QR generation, signing, and verification
- [ ] Add property-based tests with `hypothesis` for chunk round-trip (any string -> chunked -> reassembled == original)
- [ ] Add integration tests that start a real Flask server on a random port and test the full HTTP + WebSocket flow
- [ ] Add fuzz tests for `QRData.from_json` with random JSON payloads
- [ ] Add tests for `QRGenerator.verify_qr_readability` with real `pyzbar` (skip if not installed)

---

## Major Improvements (v2.0.0+)

### Protocol Enhancements
- [ ] Add QR payload versioning — embed a `protocol_version` field so future payloads can be parsed correctly by older verifiers
- [ ] Add on-chain content commitment — commit QR content hashes to a blockchain (currently blockchain hashes are freshness context only)
- [ ] Add decentralized identity — support DIDs/verifiable credentials instead of local identity hashes
- [ ] Add QR payload compression — use zlib/gzip for large payloads before chunking to reduce QR count
- [ ] Add QR payload encryption with ECDH — enable end-to-end encrypted QR payloads between specific recipients
- [ ] Add multi-signature QR payloads — require N-of-M signatures for high-trust scenarios
- [ ] Add QR revocation — publish a revocation list or use a distributed cache to revoke previously issued QR payloads

### Platform Support
- [ ] Add Docker container with health check and non-root user
- [ ] Add systemd service unit with socket activation
- [ ] Add Kubernetes manifest with liveness/readiness probes
- [ ] Add Prometheus metrics endpoint (`/metrics`) for monitoring
- [ ] Add OpenTelemetry tracing for distributed observability
- [ ] Add native mobile scanner SDK (iOS/Android) for QR verification
- [ ] Add OBS Studio plugin for native QR overlay (currently requires browser source)

### Infrastructure
- [ ] Add CI/CD pipeline with GitHub Actions (lint, test, build, publish)
- [ ] Add pre-commit hooks (black, flake8, mypy, pytest)
- [ ] Add semantic release automation
- [ ] Add PyPI publishing workflow
- [ ] Add ReadTheDocs documentation build
- [ ] Add SECURITY.md with responsible disclosure policy
- [ ] Add Dependabot configuration for dependency updates
- [ ] Add Snyk/CodeQL security scanning

### Architecture (v2.0.0)
- [ ] Migrate from Flask to FastAPI for native async support and automatic OpenAPI docs
- [ ] Replace `requests` with `httpx` for async HTTP in `BlockchainVerifier` and `TimeProvider`
- [ ] Add SQLite-backed key store — replace flat-file `key_metadata.json` with a proper database
- [ ] Add plugin system — allow third-party blockchain verifiers, time providers, and identity managers
- [ ] Add gRPC API for high-performance programmatic access
- [ ] Add WebSocket-based live QR streaming API (currently WebSocket is for web display only)
- [ ] Add multi-tenancy — support multiple issuers with isolated key stores and trust stores
- [ ] Add audit logging — record all QR generation, verification, and key operations to an append-only log
