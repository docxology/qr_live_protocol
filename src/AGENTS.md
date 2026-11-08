# QRLP implementation guide

Use the repository's [AGENTS.md](../AGENTS.md) for setup and verification.

- `core.py` coordinates generation and verification. Generation signs the payload, adds an HMAC, optionally encrypts sensitive fields, and renders the QR.
- `serializer.py` defines compact wire JSON and sorted signing JSON. The decoder rejects duplicate object keys and non-finite numbers. Keep unknown fields in the raw payload for authenticity checks even when the `QRData` view drops them.
- `crypto/` implements signing, verification, HMAC, encryption, and on-disk key storage. See the [crypto guide](crypto/README.md) for wire compatibility and key handling.
- `trust.py` associates issuer/key-ID pairs with public signing keys supplied by the verifier. A key in the payload itself does not grant trust.
- `qr_generator.py` handles rendering, capacity, and chunked payloads. Rendering styles and labels leave the wire payload unchanged.
- `time_provider.py`, `blockchain_verifier.py`, and `time_stamper.py` supply distinct evidence. A recent block hash is chain context. An OpenTimestamps commitment covers the exact wire bytes, and the local proof path stays out of those bytes.
- `web_server.py` and `async_core.py` expose the core behavior over HTTP and through an asynchronous adapter.

Keep security checks and result fields consistent across the CLI, web server, and Python APIs. `VerificationResult` defines the diagnostic shape returned by `verify_qr_data()`. A payload must pass authenticity and time checks, plus configured chain and replay policy, to be accepted. Only accepted payloads can consume replay nonces. With replay protection enabled, an authenticated payload also needs a non-empty nonce.

If a caller requests encryption, propagate failure before publishing any QR. Preserve compatibility with existing wire signatures and ciphertext when changing the crypto internals. Exercise the normal entry point with a regression for security and wire changes. Tests that use online evidence should inject a transport or use fixtures.
