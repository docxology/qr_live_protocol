# Frequently asked questions

## What does a verified QR prove?

It means the payload passed the verifier's configured authenticity, freshness, and optional policy checks. A trusted public signature authenticates the payload to the registered issuer key. A captured QR may be shown on another stream, so check the expected event or content as well.

## Can I run offline?

Yes. Use the [offline configuration](../README.md#offline-setup). QR generation then uses the local clock without polling NTP or block tips. A public-key verification still works locally if you already trust the key and the payload satisfies the freshness policy.

## Why is a QR readable but invalid?

It may be unsigned for your trust setup, outside the accepted time window, expired, replayed, changed, or encrypted with an unavailable key. Use `qrlp verify --json-output --strict` and check the per-layer fields in the [API reference](API.md#verification-result).

## Why is there no code in OBS?

Check the printed server port, then open `/viewer` in a regular browser on the same machine. If the page loads but there is no frame, check the producer for provider or QR capacity errors. See [streaming troubleshooting](STREAMING.md#troubleshooting).

## Can I put a large document in a QR?

A single QR has a limited byte capacity that depends on its error correction level. Encode a small reference or digest when possible. If the full payload is needed, use the [chunk API](API.md#large-qr-payloads-and-optical-recovery) with a receiver that collects and verifies all parts.

## Can I verify a recording later?

You can validate the signed payload against an independently trusted key, but the normal `valid` result also checks freshness. A larger drift window changes that policy and does not override an explicit expiry. Keep a detached OpenTimestamps receipt and independently verify its anchor if you need long-term evidence of existence.
