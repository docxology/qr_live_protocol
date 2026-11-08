# Streaming integration

## OBS Studio integration

1. Run `qrlp live --no-browser`.
2. Add a **Browser** source in OBS at `http://localhost:8080/viewer`. Start with an 800 × 600 source and scale it in the scene.
3. Keep a visible quiet zone around the QR and use dark modules on a light background. Avoid overlays, animation, and aggressive resampling over the code.
4. Scan the QR from a recording or a preview at the resolution and bitrate viewers will see.
5. Use the form on `http://localhost:8080/viewer` to change the text included in subsequent codes. If configured, enter the admin token there.

The page loads the current QR and listens for updates using native Server-Sent Events. It can run in an OBS browser without loading a third-party script. `/improve` shows service and feature status.

## Operating the display

Use `qrlp live --interval 10` for a slower cadence. Larger payloads and higher error correction need denser symbols. Keep user input short and test the final output with representative devices. For payloads that do not fit a single symbol, explicitly use the chunk API and a receiver that can collect the parts. The standard OBS overlay displays one QR at a time.

The default server is for a local operator and browser sources on the same machine. A remote viewer or public deployment needs a separately configured TLS and access-control layer, a private admin token, and a review of which HTTP endpoints and origins are exposed. The viewer URL contains public QR data; it does not require a signing key.

## Check a signed live frame

Generate a P-256 signing key with `qrlp keys generate --algorithm ecdsa --public-key-output issuer.pem`. Set `security_settings.sign_qr_data` to `true`, set `signature_algorithm` to `ecdsa`, and set `issuer_id` and `signing_key_id` to the expected issuer and the printed key ID. Run `qrlp --config live.json live --no-browser` with the same key directory. On the verifier, register the key before scanning.

```sh
qrlp trust add --issuer studio.example --key-id KEY_ID --algorithm ecdsa \
  --public-key issuer.pem --store trusted-issuers.json
qrlp verify --file scanned.json --trust-store trusted-issuers.json --strict --json-output
```

Wait for the viewer to show clock observations and chain hashes. Chain lookups warm in the background, so the first frame may have fewer hashes. Submit a short test message, then scan a later frame that displays it. Save the scanner's decoded text as `scanned.json`. For an automated PNG scan, capture the image and `qr_json` from the same `GET /api/qr/current` response and compare the decoded bytes to that `qr_json`. Check that `signature_verified` is true, `trust_mode` is `public_signature`, and `valid` is true.

New frames expire after 30 seconds with the defaults. For a slower workflow, set the producer's `security_settings.qr_ttl_seconds` and set an appropriate drift limit on the verifier before the test. A larger verifier tolerance still respects the signed expiry. For an OBS acceptance test, scan the composed scene or a recording at the resolution viewers will receive.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Browser Source cannot connect | Confirm the port printed by `qrlp live` and that OBS is on the same host. |
| Page stays on “Waiting for QR” | Check the terminal for provider timeouts, QR capacity errors, or a failed key configuration. Use the [offline profile](../README.md#offline-setup) to isolate provider failures. |
| Scan fails from a recording | Increase visible size and contrast, lower payload length, and check the platform's downscaled output. |
| Code is readable but verification fails | Check clock drift, expiry, trusted issuer/key ID, and decryption key. Use `qrlp verify --file payload.json --json-output --strict` to inspect the result. |
| Updating input returns unauthorized | Use the form on `/viewer` with the configured token. Cross-origin requests and unauthenticated updates on nonlocal bindings are restricted. |

## Custom web interface

`GET /api/qr/current` returns the current QR snapshot; `GET /api/qr/events` streams subsequent snapshots. See the [API reference](API.md#rest-api) for payloads and for the Socket.IO interface used by existing integrations.
