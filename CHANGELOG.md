# Changelog

All notable changes to QR Live Protocol (QRLP) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-07-22

### Security
- Added HMAC key rotation — `HMACManager` now has `key_store`, `add_key()`, and `rotate_key()`
- Added encryption key rotation — `DataEncryptor` now has `key_store`, `add_key()`, and `rotate_key()`
- Added PBKDF2-HMAC-SHA256 key derivation for `KeyManager` — optional `password` parameter derives
  the master key using 600,000 iterations with a stored salt (backward compatible with random key)
- Added WebSocket input validation — `handle_user_data_update` now uses `SecurityValidator.validate_user_text`

### Architecture
- Added `QRData.from_dict()` classmethod — inverse of `to_dict()`, accepts a dict and filters to known fields

### Tests
- **602 tests** (up from 567), **0 failures**.
- Added `tests/test_coverage_gaps.py` — 35 tests for CLI live/dashboard (subprocess), web_server
  broadcast/stop, config YAML, signer message methods, error_recovery async functions, async_core
  optimization, core _update_loop error path, QR generator style fallbacks, HMAC type handling.

### Documentation
- Updated `docs/API.md` with `VerificationResult` class, crypto exception classes (`KeyManagementError`, `HMACError`)
- Updated `src/AGENTS.md` with actual crypto pipeline (Sign -> HMAC -> Encrypt), new types, exception renames
- Updated `docs/AUTHENTICATION_CHALLENGES.md` with forward-compatible QR payload documentation
- Updated `docs/INSTALLATION.md` with `pytest-asyncio` and optional dependencies

### Code Quality
- Removed 5 remaining unused imports (asdict, QRSignatureManager, DataEncryptor from async_core.py,
  Tuple from blockchain_verifier.py, hmac from encryptor.py)
- Added PyYAML to test dependencies for YAML config test coverage
- Updated `.gitignore` for `.master_salt` file

## [1.2.0] - 2026-07-22

### Architecture
- Added `VerificationResult` dataclass to replace the untyped dict returned by
  `verify_qr_data` — enables cleaner API and type checking. Exported from `src`.
- Added `QRData.to_dict()` method — returns a clean dict without None entries,
  suitable for JSON serialization or API responses.
- Added `QRData.__repr__` and `QRData.__str__` for better debugging output.

### Security
- Added Content-Security-Policy headers to all web responses (CSP, X-Content-Type-Options,
  X-Frame-Options, Referrer-Policy).

### Performance
- Added `requests.Session` connection pooling to `BlockchainVerifier` — uses
  keep-alive connections for all blockchain API calls instead of creating a new
  connection per request.

### Code Quality
- Removed 29 unused imports across 9 source files (async_core, blockchain_verifier,
  core, crypto/encryptor, crypto/key_manager, crypto/signer, identity_manager,
  time_provider, web_server).

### New CLI Commands
- `qrlp config-validate <path>` — validate a configuration file without starting QRLP.
- `qrlp status --json-output` — output status as machine-readable JSON.

### Tests
- **567 tests** (up from 547), **0 failures**.
- Added `tests/test_v12_features.py` — 20 tests for VerificationResult, QRData.to_dict/__repr__,
  config-validate, status --json, CSP headers, and connection pooling.

## [1.1.0] - 2026-07-22

### Security Fixes
- **CRITICAL**: Renamed `KeyError` to `KeyManagementError` in `crypto/exceptions.py` — the
  previous name shadowed Python's built-in `KeyError`, which could cause unexpected behavior
  in any code path where crypto exceptions were imported.
- Removed MD5 hash algorithm support from `IdentityManager` — MD5 is cryptographically broken
  and should not be used for identity verification. Unknown algorithms now fall back to SHA-256.
- Removed `--break-system-packages` flag from `setup.py` auto-install path, which could silently
  modify the system Python installation.
- Fixed `web_server.py` rate limiter thread safety — the `request_log` dict was accessed without
  a lock from concurrent request threads. Added a `threading.Lock` to protect the rate-limit
  window computation.
- Replaced `datetime.utcnow()` (deprecated in Python 3.12+) with `datetime.now(timezone.utc)`
  throughout `web_server.py` (12 occurrences).

### Bug Fixes
- Fixed redundant `datetime.now(timezone.utc)` call in `core.py` `verify_qr_data` — the `now`
  variable was computed but not used for the time difference calculation.
- Fixed `blockchain_verifier.py` `_update_if_needed` race condition — the `_updating` flag was
  checked with `hasattr` (which returned False after the first update) instead of `getattr`,
  potentially spawning multiple background update threads. Added `_update_all_chains_safe`
  wrapper that clears the flag in a `finally` block.
- Fixed `QRData.from_json` to handle unknown fields gracefully — previously crashed with
  `TypeError` on forward-compatible QR payloads containing new fields. Now filters to known
  dataclass fields only.
- Fixed `signer.py` double canonicalization — `create_signed_qr_data` and `verify_signed_qr_data`
  both canonicalized the payload before passing to `sign_qr_with_key`/`verify_qr_signature`,
  which canonicalized again. While idempotent, this was wasteful and could mask bugs.
- Fixed `config.py` `from_env` double `os.getenv` calls — every environment variable was read
  twice (once in the `if` check, once in the assignment). Refactored to store the value in a
  local variable.
- Fixed `async_core.py` `_get_time_from_server_async` ignoring the `server` parameter — always
  queried `worldtimeapi.org` regardless of which NTP server was requested. The `server` parameter
  is now correctly used as the key in the returned dict.
- Fixed `_apply_cryptographic_enhancements` in `core.py` to use proper `logging.warning` instead
  of `print()` for encryption failure messages.
- Fixed `aiofiles` import in `async_core.py` — imported unconditionally but not in dependencies.
  Made the import optional with try/except.

### Improvements
- Replaced all `print()` calls with `_logger.info/warning/error()` across 9 source files.
  Each module now has its own named logger (`qrlp.core`, `qrlp.blockchain`, etc.).
- Added `HMACError` to the public API exports in `crypto/__init__.py` and `src/__init__.py`.
- Added `pytest-asyncio` to dev dependencies and configured `asyncio_mode = "auto"`.
- Added `aiofiles` and `psutil` to optional `[full]` dependencies.
- Updated `.gitignore` to exclude `.qrlp/`, `*.key`, `key_metadata.json`, `.master_key`.
- Fixed `_logger` placement in 6 source files — added proper blank lines before and after
  the logger initialization lines.

### Test Suite Expansion
- **547 tests** (up from 165), **88% total coverage** (up from 67%), **0 failures**.
- Added `tests/test_async_core.py` — 26 tests for async QR generation, batch operations,
  blockchain/time data, performance stats, and sync wrappers (0% -> 80% coverage).
- Added `tests/test_web_server_extended.py` — 35 tests for SecurityValidator, all HTTP routes,
  admin token protection, rate limiting, and CORS (66% -> 75% coverage).
- Added `tests/test_cli_extended.py` — 30 tests for all CLI commands via Click's CliRunner
  (57% -> 78% coverage).
- Added `tests/test_error_recovery_extended.py` — 35 tests for circuit breaker state
  transitions, async paths, retry logic, and resilience manager (70% -> 92% coverage).
- Added `tests/test_blockchain_verifier_extended.py` — 20 tests for chain handlers with
  mocked HTTP, API fallback, and update safety (33% -> 90% coverage).
- Added `tests/test_time_provider_extended.py` — 20 tests for NTP/HTTP time sync,
  timestamp verification, and force sync (85% -> 99% coverage).
- Added `tests/test_identity_manager_extended.py` — 25 tests for file management,
  export/import, hash caching, and identity change detection (85% -> 93% coverage).
- Added `tests/test_trust_extended.py` — 30 tests for TrustStore serialization,
  query, and edge cases (96% -> 100% coverage).
- Added `tests/test_core/test_core_extended.py` — 35 tests for encrypted QR, update loop,
  callbacks, verification, and key management (83% -> 95% coverage).
- Added `tests/test_qr_generator_internals.py` — 30 tests for text overlay, chunk
  encoding/decoding, cache eviction, and version estimation (62% -> 89% coverage).
- Added `tests/test_crypto/test_signer_extended.py` — tests for exception renaming,
  canonicalization, and RSA/ECDSA round-trip.
- Added `tests/test_config_env.py` — tests for all 9 environment variable mappings.
- Added `tests/test_core/test_qrdata_forward_compat.py` — tests for unknown-field filtering.

### Coverage by Module
| Module | Before | After |
|--------|--------|-------|
| `__init__.py` | 100% | 100% |
| `trust.py` | 96% | 100% |
| `time_provider.py` | 85% | 99% |
| `crypto/encryptor.py` | 94% | 96% |
| `core.py` | 83% | 95% |
| `crypto/key_manager.py` | 95% | 95% |
| `config.py` | 83% | 93% |
| `identity_manager.py` | 85% | 93% |
| `error_recovery.py` | 70% | 92% |
| `async_core.py` | 0% | 80% |
| `blockchain_verifier.py` | 33% | 90% |
| `qr_generator.py` | 62% | 89% |
| `crypto/hmac.py` | 86% | 87% |
| `crypto/signer.py` | 83% | 86% |
| `cli.py` | 57% | 78% |
| `web_server.py` | 66% | 75% |
| **TOTAL** | **67%** | **88%** |

## [1.0.1] - 2025-07-09

### Added
- Trust dashboard with public-key trust store integration
- Improvement smoke test endpoint (`/api/improve/smoke-test`)
- Explicit QR chunking protocol (`qrlp.chunk.v1`) with validated reassembly
- Admin token authentication for state-changing endpoints
- Per-client rate limiting middleware
- Content Security Policy and CORS configuration
- `SecurityValidator` for input validation and HTML sanitization

### Changed
- HMAC fields now prefixed with `_` to distinguish from public signature fields
- Signature canonicalization strips HMAC, encryption, and signature fields
- Trust model explicitly separates local HMAC from public-key signatures

### Fixed
- KeyManager private key decryption in `get_keypair()`
- HMAC preservation through the Sign -> HMAC -> Encrypt pipeline
- QR data size estimation and chunked QR handling for large payloads
