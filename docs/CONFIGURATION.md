# Configuration

QRLP selects configuration in this order:

1. An explicit global `qrlp --config PATH COMMAND` loads the JSON or YAML file over defaults.
2. Without a file, supported `QRLP_*` environment variables override defaults. The CLI also accepts `QRLP_ENCRYPTION_KEY` with a file when the file does not set that key.
3. Options on the selected command override the fields they address.

No default configuration file is searched for. YAML requires the `full` extra. The older `web` section is accepted; canonical `web_settings` wins when both sections set the same field. Unknown keys are ignored for compatibility; known fields with the wrong shape are rejected.

```sh
qrlp config-init --output config.json
qrlp config-validate config.json
qrlp --config config.json live --no-browser
```

## Configuration file format

Generate a complete template with `config-init`. This smaller example disables external data sources, signs live QR payloads, and uses a short expiry:

```json
{
  "update_interval": 5,
  "time_settings": {"time_servers": [], "local_fallback": true},
  "blockchain_settings": {"enabled_chains": []},
  "web_settings": {"host": "localhost", "port": 8080, "auto_open_browser": false},
  "security_settings": {
    "issuer_id": "studio.example",
    "event_id": "episode-1",
    "sign_qr_data": true,
    "signature_algorithm": "ecdsa",
    "qr_ttl_seconds": 30
  }
}
```

| Section | Settings |
| --- | --- |
| `qr_settings` | Error correction `L`, `M`, `Q`, or `H`; border, scale, colors, image format, and the chunk planner's data budget. |
| `time_settings` | NTP hostnames or explicit HTTP(S) JSON clock URLs, timeout, update interval, local fallback, and optional OpenTimestamps calendar and proof directory. If fallback is off and no configured source succeeds, generation fails. |
| `blockchain_settings` | Enabled chains, timeout, and cache duration. The built-in chain handlers select their provider URLs; use an empty list to disable requests. |
| `identity_settings` | Optional identity file, hash algorithm, and which local details are used to calculate the identity fingerprint. |
| `web_settings` | Host, port, auto-open, optional CORS origin list, admin token, and request rate limit. Keep the default loopback binding for OBS on the same machine. |
| `verification_settings` | Time drift, optional blockchain/time-source checks, and replay-window settings. Replay memory is per verifier process. |
| `security_settings` | Issuer/event, signing algorithm and key ID, private key directory, optional expiry, optional field encryption and its shared key. |
| `logging_settings` | Level and file rotation settings for application logging. |

For encrypted CLI output, use `qrlp generate --encrypt --sign` and supply a key encoded as exactly 64 hexadecimal characters (32 bytes) via `QRLP_ENCRYPTION_KEY` or `security_settings.encryption_key`. Provide the same AES key and a trusted signing public key to the verifier. Keep the AES key out of version control and command-line arguments. The Python API can also accept an injected encryptor. The shared key is separate from issuer signing keys and local HMAC state.

## Environment variables

`QRLP_UPDATE_INTERVAL`, `QRLP_WEB_PORT`, `QRLP_WEB_HOST`, `QRLP_WEB_CORS_ENABLED`, `QRLP_WEB_ADMIN_TOKEN`, `QRLP_IDENTITY_FILE`, `QRLP_LOG_LEVEL`, `QRLP_ISSUER_ID`, `QRLP_EVENT_ID`, and `QRLP_ENCRYPTION_KEY`.

## Command line arguments

```sh
qrlp --config config.json live --host localhost --port 9000 --interval 10
qrlp --config config.json generate --sign --format both --output example
qrlp --config config.json verify --file example.json --tolerance 30 --strict
```

The `--config` and `--debug` options go before the subcommand. `qrlp COMMAND --help` lists options for that command.
