# QR Live Protocol

<p align="center">
  <a href="LICENSE"><img alt="License: CC BY-NC 4.0" src="https://img.shields.io/badge/license-CC%20BY--NC%204.0-blue"></a>
  <img alt="Requires Python 3.11 or newer" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white">
</p>

QRLP generates rotating QR codes for OBS, livestream overlays, and recorded releases. A code can carry an issuer ID, event ID, timestamp, sequence number, and application data. A verifier can check the payload's freshness and authenticate it using a trusted public key.

QRLP requires Python 3.11 or newer. The checkout pins its development interpreter with `.python-version` and locks dependencies with `uv.lock`. See [installation](docs/INSTALLATION.md) for pip, optional dependencies, and wheel builds.

```sh
uv sync --locked --extra dev
uv run --no-sync qrlp live
```

Add <http://localhost:8080/overlay?details=1> as a transparent OBS Browser Source. Use the text form on `/viewer` to change the caption in subsequent QRs, and `/improve` for diagnostics. The built-in browser views use a same-origin event stream and do not need CDN JavaScript. [Streaming guide](docs/STREAMING.md)

## Generate and verify a signed QR

```sh
qrlp generate --sign --issuer-id studio.example --format both --output release \
  --user-data '{"title":"Episode 1"}' --trust-record-output issuer.json
qrlp verify --file release.json --trust-store issuer.json --json-output --strict
```

The output includes `release.png` and `release.json`. Give the verifier `issuer.json` over an independently authenticated channel. A trust file handed out with an untrusted QR does not establish its issuer. For older recordings, set an explicit `--tolerance` appropriate to the event; widening it weakens freshness checks. `--strict` makes invalid verification exit with status 1. The default exit behavior reports results without treating an invalid QR as a command failure.

| Signal | What it establishes |
| --- | --- |
| Trusted public-key signature | The payload matches the bytes signed by the registered issuer key. |
| Local signature or HMAC | The local verifier has the matching signing key or HMAC secret. |
| Timestamp, expiry, nonce | Freshness under the verifier's clock, policy, and in-process replay history. |
| Recent block hashes | Context that may match current provider observations. |
| OpenTimestamps | An optional detached receipt for the exact payload bytes; anchoring must be checked independently. |

A QR does not prove that an entire video or stream is authentic. A genuine QR can be copied to another stream. Bind a meaningful event or content commitment and establish the issuer independently. See [security and trust](SECURITY.md).

## Offline setup

Save this as `offline.json` to use the local clock and skip blockchain requests:

```json
{
  "time_settings": {"time_servers": []},
  "blockchain_settings": {"enabled_chains": []},
  "web_settings": {"auto_open_browser": false}
}
```

Then run `qrlp --config offline.json live`, or put the same global option before `generate` and `verify`. The local clock is a fallback; it does not become an external time source.

## Python usage

```python
from src import QRLPConfig, QRLiveProtocol

config = QRLPConfig()
config.time_settings.time_servers = []
config.blockchain_settings.enabled_chains = set()

protocol = QRLiveProtocol(config)
payload, png = protocol.generate_signed_qr({"event": "demo"})
result = protocol.verify_qr_data(payload.to_json())
assert result["valid"]
```

Use `payload.to_json()` for wire bytes. `payload.to_dict()` also includes any local proof metadata. The [API reference](docs/API.md) covers async use, QR chunk recovery, HTTP, Socket.IO, and verification fields.

## Package map

Generated on 2026-11-12 from the `import` statements under `src/`. An arrow from A to B means code in A imports B; arrows already implied by a longer path are left out, so the picture shows layering rather than every edge. It shows 14 of the package's 18 top-level parts: the largest ones that import or are imported by others.

```mermaid
flowchart LR
    accTitle: Internal dependency map of the src package in qr_live_protocol
    accDescr: Generated from import statements in src. Each box is a subpackage or module of the package; an arrow from A to B means code in A imports B; arrows already implied by a longer path are omitted. Most-imported: config, core, frame_recovery.
    n_crypto["crypto/"]
    n_web_server["web_server.py"]
    n_cli["cli.py"]
    n_core["core.py"]
    n_qr_generator["qr_generator.py"]
    n_async_core["async_core.py"]
    n_identity_manager["identity_manager.py"]
    n_blockchain_verifier["blockchain_verifier.py"]
    n_config["config.py"]
    n_time_stamper["time_stamper.py"]
    n_time_provider["time_provider.py"]
    n_optical_throughput["optical_throughput.py"]
    n_live_simulator["live_simulator.py"]
    n_frame_recovery["frame_recovery.py"]
    n_web_server --> n_core
    n_async_core --> n_core
    n_blockchain_verifier --> n_config
    n_cli --> n_live_simulator
    n_cli --> n_web_server
    n_core --> n_blockchain_verifier
    n_core --> n_crypto
    n_core --> n_identity_manager
    n_core --> n_qr_generator
    n_core --> n_time_provider
    n_core --> n_time_stamper
    n_identity_manager --> n_config
    n_live_simulator --> n_frame_recovery
    n_live_simulator --> n_optical_throughput
    n_qr_generator --> n_config
    n_time_provider --> n_config
```

## Development

```sh
uv sync --locked --extra dev
uv run --no-sync python -m pytest --no-cov
uv run --no-sync qrlp simulate-live --frames 200 --drop-rate 0.15 --seed 42 --json-output
uv run --no-sync qrlp benchmark-ws --iterations 200 --json-output
uv run --no-sync python examples/comprehensive_demo.py
uv build
```

The comprehensive demo verifies signed and encrypted QR payloads with separate key stores and writes public artifacts to a new directory. The simulator models drops and reordering; it cannot measure the readability of a physical display and camera. The WebSocket benchmark measures in-process payload preparation, not network throughput.

| Area | Entry point |
| --- | --- |
| Protocol and cryptography | [src/core.py](src/core.py), [src/crypto/](src/crypto/) |
| Browser overlay and control server | [src/web_server.py](src/web_server.py), [templates/](templates/) |
| Optical delivery and simulation | [src/qr_generator.py](src/qr_generator.py), [src/live_simulator.py](src/live_simulator.py) |
| Installation, settings, and integration | [Documentation index](docs/INDEX.md) |
| Releases and compatibility | [Changelog](CHANGELOG.md) |

Source available under [CC BY-NC-SA 4.0](LICENSE).
