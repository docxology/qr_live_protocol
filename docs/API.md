# QRLP API reference

## Python API

```python
from src import QRLPConfig, QRLiveProtocol, TrustStore

config = QRLPConfig()
config.time_settings.time_servers = []
config.blockchain_settings.enabled_chains = set()
config.security_settings.issuer_id = "studio.example"

producer = QRLiveProtocol(config)
payload, image = producer.generate_signed_qr({"title": "Episode 1"})
payload_bytes = payload.to_json().encode("utf-8")

trusted_keys = TrustStore()
trusted_keys.add_public_key(
    payload.issuer_id,
    payload.signing_key_id,
    producer.key_manager.export_public_key(payload.signing_key_id),
    payload.signature_algorithm,
)
receiver = QRLiveProtocol(config, trust_store=trusted_keys)
assert receiver.verify_qr_data(payload_bytes.decode("utf-8"))["valid"]
```

In an independent receiver, load trusted key material from a controlled source with `TrustStore.from_file()` or `add_public_key_file()`. Use a separate verifier key directory when testing cross-operator trust.

### QRLiveProtocol

| Method | Behavior |
| --- | --- |
| `generate_single_qr(user_data=None, sign_data=None, encrypt_data=None, signing_key_id=None, encryption_key_id=None, *, style=None, include_text=False)` | Returns a `(QRData, bytes)` pair. `None` uses configured signing or encryption defaults. |
| `generate_signed_qr(user_data=None, signing_key_id=None)` | Signs explicitly. |
| `generate_encrypted_qr(user_data=None, encryption_key_id=None)` | Signs and encrypts protected fields. Raises if encryption fails. |
| `verify_qr_data(qr_json)` | Parses, decrypts as needed, verifies authenticity, then applies freshness and policy checks. Returns a result dictionary. |
| `start_live_generation()` / `stop_live_generation()` | Control the background generation loop. An in-flight provider request is bounded by its own timeout. |
| `add_update_callback(callback)` / `remove_update_callback(callback)` | Register or remove a callback accepting `(QRData, image_bytes)`. |
| `set_user_data_callback(callback)` | Supplies a string or `None` for future frames. |
| `get_current_qr_data()` / `get_statistics()` | Inspect the latest payload or component counters. |

`QRData.to_json()` emits the exact compact QR wire text, without the local OpenTimestamps proof path. `QRData.to_dict()` is a diagnostic view and can include local proof metadata. `QRData.from_json()` supports forward-compatible typed reading; `verify_qr_data()` checks authenticity against the full wire object, including unknown fields.

### Verification result

| Field | Meaning |
| --- | --- |
| `valid_json` | Payload decoded and had the required verification fields. Failed decryption also makes this false. |
| `signature_verified` / `hmac_verified` | The corresponding authenticity check passed. |
| `trust_mode` | `public_signature`, `local_signature`, `local_hmac`, or `none`. |
| `identity_verified` | The local identity hash matched, or the configured trusted issuer key verified the signature. |
| `time_verified` | The timestamp is within configured drift and has not passed its expiry, if present. `require_time_server` checks for issuer-reported time evidence in the payload. |
| `blockchain_verified` | At least one hash matched a current provider observation for an authenticated, timely payload. |
| `encrypted` | The payload declared encrypted fields. |
| `replayed` | The nonce was accepted previously within the enabled replay window. |
| `valid` | Authenticity and freshness passed, along with required blockchain and replay policy. |
| `error` | Optional diagnostic for rejected inputs. |

Replay protection is off by default. When enabled, a valid nonce is required and only accepted payloads consume a nonce. Process restarts clear this state. See [the threat model](../SECURITY.md#threat-model) for what these checks establish.

### Async API

```python
from src.async_core import AsyncQRLiveProtocol

async def first_frame(config):
    async with AsyncQRLiveProtocol(config) as protocol:
        return await protocol.generate_single_qr_async({"event": "demo"})
```

Async generation and verification use the same protocol and provider settings on worker threads. Async generation signs by default; pass `sign_data=None` to use the configuration default. Use `batch_generate_qr_async()` for a finite batch and `iter_qr_stream_async()` for streaming consumption. Close the instance with `aclose()` or an async context manager. `get_time_data_async()` returns configured clock observations. `get_blockchain_data_async()` may return no tips while the shared cache refreshes.

### Large QR payloads and optical recovery

```python
from src import QRGenerator, QRLPConfig

generator = QRGenerator(QRLPConfig().qr_settings)
parts = generator.generate_chunked_payloads("example payload" * 200)
images = [generator.generate_qr_image(part) for part in parts]
assert generator.reassemble_chunked_payloads(list(reversed(parts))) == "example payload" * 200
```

`generate_qr_image()` raises `QRDataTooLargeError` when a single code cannot fit. Chunk envelopes include group identity, index, total count, and payload digest. Recovery checks completeness and integrity; pass the reassembled QR wire data through normal verification for issuer authenticity. `FrameRecoveryController` separately tracks short delivery gaps and late frames. `LiveSimulator` exercises these delivery conditions with a seeded model.

### OpenTimestamps

```sh
qrlp stamp release.json --proof-dir proofs
qrlp verify-ots release.json proofs/PAYLOAD_DIGEST.ots --json-output
```

The stamp command writes the calendar receipt for the exact bytes. Keep the original JSON bytes; pretty-printing it changes the digest. `ots_verified` means the file digest matches and the receipt contains an attestation structure. `ots_chain_verified` stays false in QRLP. `ots_timestamp` is local sidecar receipt time, if present; the chain label is reported by the proof. Use the [OpenTimestamps client](https://github.com/opentimestamps/opentimestamps-client) and a trusted chain source to upgrade and independently verify the chain anchor.

## REST API

Default base URL: `http://localhost:8080`. The display routes are `/`, `/viewer`, `/admin`, and `/improve`.

| Method and path | Request or response |
| --- | --- |
| `GET /api/qr/current` | Current `{qr_data, qr_json, qr_image, timestamp}` snapshot. `qr_json` is exact wire text; `qr_data` is the parsed object. Image is a data URL; returns 404 before the first frame. |
| `GET /api/qr/events` | Server-Sent Events carrying the same snapshot; delivered as default `message` events. |
| `GET /api/status` | Listener and client counters. |
| `POST /api/verify` | JSON object `{"qr_data":"<wire JSON text>"}`. Returns the verification result plus request metadata. |
| `GET /api/improve/status` | Feature and service status, without admin credentials. |
| `POST /api/improve/smoke-test` | JSON object `{}`. Runs a local signed QR and chunk recovery check. |
| `GET /api/user-data` | Current public text as `{"user_data": ...}`. |
| `POST /api/user-data` | JSON object `{"user_text":"..." }`; an empty string clears it. |

Protected mutation endpoints accept `X-QRLP-Admin-Token` or `Authorization: Bearer ...`. Treat API request errors separately from a completed verification result with `valid: false`.

## Socket.IO API

The Socket.IO server uses the default namespace and path. Connect using a compatible client; the included browser pages use the SSE route instead.

- `qr_update`: same snapshot as the HTTP endpoint; sent on connection and as updates arrive.
- `request_qr_update`: request the current snapshot on this connection.
- `update_user_data`: submit `user_text` and, when required, `admin_token`.
- `user_data_updated` and `user_data_error`: success broadcast and caller error events.

## Command line interface

| Command | Purpose |
| --- | --- |
| `qrlp live` / `qrlp dashboard` | Run the same service and open the display or improvement view. |
| `qrlp generate` | Render and optionally export the QR wire JSON, issuer public PEM, and trust record. |
| `qrlp verify` | Check one payload, or `--batch --file FILE` with a JSON array. Use `--strict` for status 1 on invalid results and `--json-output` for JSON only. |
| `qrlp keys` / `qrlp trust` | Generate, list, export or rotate local keys; create and list trust records. |
| `qrlp config-init` / `qrlp config-validate` | Write defaults and check a configuration file. |
| `qrlp stamp` / `qrlp verify-ots` | Create and inspect OpenTimestamps receipts. |
| `qrlp simulate-live` / `qrlp benchmark-ws` | Simulate optical delivery or time in-process QR update preparation. |

Use `qrlp COMMAND --help` for command options.
