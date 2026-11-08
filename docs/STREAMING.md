# Streaming integration

## OBS Studio integration

1. Run `qrlp live --no-browser`.
2. Add a **Browser** source in OBS at `http://localhost:8080/overlay?details=1`. Start with an 800 × 800 browser viewport. This draws a 600 px white card, including its quiet zone, over a transparent background. Set the source's OBS page permissions to **No access to OBS**.
3. Add your webcam below the Browser Source and position the QR away from your face. For a 1920 × 1080 scene, put the webcam on the left and the overlay viewport on the right. Leave the Browser Source at its native scale when possible.
4. Scan the QR from a recording or a preview at the resolution and bitrate viewers will see.
5. Use the form on `http://localhost:8080/viewer` to change the text included in subsequent codes. If configured, enter the admin token there.

The overlay receives updates through native Server-Sent Events. Add `?details=1` for a compact title or event label, issuer, and public caption. Use plain `/overlay` for the QR alone. The operator form and diagnostics are separate at `/viewer` and `/improve`.

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

## Record a webcam take with signed metadata

Keep the title, take ID, and other public labels compact. A config such as the following signs the metadata and keeps it readable at the recording resolution. The viewer form can change the caption between takes. To change other config fields, restart the producer before the next take.

```json
{
  "update_interval": 5,
  "live_user_data": {
    "title": "Proof in the Frame",
    "series": "QR Webcam Lab",
    "take": "01",
    "tags": ["webcam", "signed"],
    "user_text": "Rolling signed frames"
  },
  "security_settings": {
    "issuer_id": "studio.example",
    "event_id": "webcam-lab",
    "sign_qr_data": true,
    "signature_algorithm": "ecdsa",
    "qr_ttl_seconds": 120
  }
}
```

Record a short local clip with the same resolution, scene layout, and encoder settings as your final take. Extract a still from a settled frame and decode the QR from that still. For example, `ffmpeg -ss 3 -i clip.mkv -frames:v 1 frame.png` writes a frame at about three seconds. Check the decoded title, take ID, and message. Verify the exact text against your pinned public key before it expires. For a 120-second test expiry, use an explicit `--tolerance 120` if verification will take more than 30 seconds. [OBS Browser Source settings](https://obsproject.com/kb/browser-source).

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
