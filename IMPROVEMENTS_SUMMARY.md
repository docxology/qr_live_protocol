# QRLP Improvements Summary

**Version:** 1.4.0  
**Date:** 2026-07-22  
**Status:** Production-Ready  

## Executive Summary

This document summarizes all improvements made to the QR Live Protocol (QRLP) system
across versions 1.0.1 and 1.1.0, including security fixes, bug fixes, code quality
improvements, and comprehensive test suite expansion.

## v1.1.0 Changes

### Security
- Renamed `KeyError` to `KeyManagementError` in crypto exceptions (was shadowing Python builtin)
- Removed MD5 hash algorithm support (cryptographically broken)
- Removed `--break-system-packages` from setup.py
- Fixed rate limiter thread safety
- Replaced deprecated `datetime.utcnow()`

### Bug Fixes
- Fixed 7 bugs across core.py, blockchain_verifier.py, signer.py, config.py, async_core.py
- Fixed QRData.from_json forward compatibility
- Fixed blockchain_verifier race condition
- Made aiofiles import optional

### Code Quality
- Replaced all print() with proper logging (9 source files)
- Added HMACError to public API
- Fixed _logger placement in 6 files
- Added pytest-asyncio, aiofiles, psutil to dependencies

### Test Suite
- 547 tests (up from 165)
- 88% coverage (up from 67%)
- 13 new test files
- 0 failures

## v1.0.1 Changes

### Web Interface
- Red theme redesign (black background, red accents)
- Interactive custom input section
- QR data display with all fields
- Real-time WebSocket updates
- CORS support
- Admin dashboard

### Security
- HMAC-SHA256 integrity checking
- Digital signatures (RSA/ECDSA)
- AES-256-GCM field encryption
- Trust store for public-key verification
- Admin token authentication
- Rate limiting middleware
- Input validation and HTML sanitization

### QR Code Generation
- Explicit chunking protocol (`qrlp.chunk.v1`)
- Validated reassembly with checksum
- Multiple error correction levels
- Style presets (live, professional, minimal)
- Text overlay for live display
- Cache management

### Error Recovery
- Circuit breaker pattern (CLOSED -> OPEN -> HALF_OPEN)
- Retry with exponential backoff
- Resilience manager for all operations
- Async operation support
