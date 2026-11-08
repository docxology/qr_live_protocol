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
| `live_user_data` | Optional public JSON object included when generation is called without explicit metadata. The viewer form overrides `user_text` for later frames. Clearing the form restores its configured value. |
| `qr_settings` | Error correction `L`, `M`, `Q`, or `H`; border, scale, colors, image format, and the chunk planner's data budget. |
| `time_settings` | NTP hostnames or explicit HTTP(S) JSON clock URLs, timeout, update interval, local fallback, and optional OpenTimestamps calendar and proof directory. If fallback is off and no configured source succeeds, generation fails. |
| `blockchain_settings` | Enabled chains, `api_endpoints`, timeout, and cache duration. Use an empty chain list to disable requests. |
| `identity_settings` | Optional identity file, hash algorithm, and which local details are used to calculate the identity fingerprint. |
| `web_settings` | Host, port, auto-open, optional CORS origin list, admin token, and request rate limit. Keep the default loopback binding for OBS on the same machine. |
| `verification_settings` | Time drift, optional blockchain/time-source checks, and replay-window settings. Replay memory is per verifier process. |
| `security_settings` | Issuer/event, signing algorithm and key ID, private key directory, signed expiry, optional field encryption and its shared key. If `qr_ttl_seconds` is unset, the producer uses its own `max_time_drift` rounded down to whole seconds. |
| `logging_settings` | Level and file rotation settings for application logging. |

For encrypted CLI output, use `qrlp generate --encrypt --sign` and supply a key encoded as exactly 64 hexadecimal characters (32 bytes) via `QRLP_ENCRYPTION_KEY` or `security_settings.encryption_key`. Provide the same AES key and a trusted signing public key to the verifier. Keep the AES key out of version control and command-line arguments. The Python API can also accept an injected encryptor. The shared key is separate from issuer signing keys and local HMAC state.

## Live providers

QRLP queries `time.nist.gov` and `time.cloudflare.com` by default and refreshes its observations every 60 seconds. The overlay cadence is independent of clock refresh. Each process also enforces a four-second minimum between requests to the same NIST hostname. Keep leap-smearing clocks in their own configuration and use an assigned vendor zone when shipping the NTP Pool as a default. [NIST server guidance](https://tf.nist.gov/tf-cgi/servers.cgi), [Cloudflare NTP](https://developers.cloudflare.com/time-services/ntp/), [NTP Pool vendor guidance](https://www.ntppool.org/en/vendors.html).

An explicit HTTP clock URL must return a JSON `datetime` string with a UTC offset. Set `time_settings.time_servers` to an empty list to use the local clock, or disable `local_fallback` to require an external observation.

The default Bitcoin endpoint uses Blockstream Esplora, with mempool.space and BlockCypher as fallbacks. Ethereum and Litecoin use BlockCypher chain URLs. Older config files with the exact legacy Etherscan V1 default continue using BlockCypher. A custom Bitcoin value is an Esplora API base URL and QRLP uses it on its own. A custom Ethereum or Litecoin value is a full HTTP(S) chain-info URL returning a nonnegative integer `height` and a 64-digit hexadecimal `hash`. Ethereum hashes may have a `0x` prefix. [Esplora API](https://github.com/Blockstream/esplora/blob/master/API.md), [BlockCypher API](https://www.blockcypher.com/dev/ethereum/).

## Environment variables

`QRLP_UPDATE_INTERVAL`, `QRLP_WEB_PORT`, `QRLP_WEB_HOST`, `QRLP_WEB_CORS_ENABLED`, `QRLP_WEB_ADMIN_TOKEN`, `QRLP_IDENTITY_FILE`, `QRLP_LOG_LEVEL`, `QRLP_ISSUER_ID`, `QRLP_EVENT_ID`, and `QRLP_ENCRYPTION_KEY`.

## Command line arguments

```sh
qrlp --config config.json live --host localhost --port 9000 --interval 10
qrlp --config config.json generate --sign --format both --output example
qrlp --config config.json verify --file example.json --tolerance 30 --strict
```

The `--config` and `--debug` options go before the subcommand. `qrlp COMMAND --help` lists options for that command.
