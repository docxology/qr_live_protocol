# QRLP package

The public Python entry points are exported by `src/__init__.py`. See the [API reference](../docs/API.md) for usage examples.

| Path | Responsibility |
| --- | --- |
| `core.py`, `serializer.py` | Payload assembly, wire encoding, signing pipeline and verification policy. |
| `crypto/`, `trust.py` | Cryptographic primitives, local key store and external issuer trust. |
| `config.py`, `cli.py` | Application settings, CLI commands and live startup. |
| `time_provider.py`, `blockchain_verifier.py` | Current time and block-tip observations. |
| `time_stamper.py`, `time_stamper_integration.py` | Detached OpenTimestamps receipt submission and digest checks. |
| `async_core.py`, `error_recovery.py` | Async adapter, retry, and circuit breaker helpers. |
| `qr_generator.py`, `live_simulator.py` | Symbol rendering, bounded chunk recovery, and modeled optical delivery. |
| `web_server.py` | Overlay, controls, diagnostics, SSE, and Socket.IO. |

Keep authentication over wire data separate from local display and proof metadata. Avoid adding alternate generation or verification paths that bypass the synchronous coordinator.
