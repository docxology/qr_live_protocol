# Security and trust

## Threat model

QRLP checks what a QR payload contains and who could have signed it under the verifier's local trust settings. It does not authenticate a streaming platform, camera, viewer, or video by itself. A valid code can be copied to an unrelated stream. Authenticate the issuer key independently and agree on the event or content the QR is expected to identify.

An identity hash is a local fingerprint. An event ID and a content hash are signed context when present, but the verifier needs an independent expectation about the event or content to detect substitution. Current blockchain tips are observations from configured providers, not a timestamp anchor for a QR. `verify-ots` checks receipt structure and byte matching; a trusted chain check is a separate step.

## Security measures

- For cross-operator verification, sign the QR and register the issuer's public key against the expected issuer ID and key ID. Keep private key material, HMAC secrets, and encryption keys separate.
- HMAC verification needs the same secret. It cannot identify an issuer to a third party. A matching public signature can be verified without sharing private material.
- QR encryption protects selected fields, not the entire payload. Public timestamp, issuer, and sequence metadata can still be visible. Configured encryption fails if it cannot protect the fields. Give the decryption key only to intended recipients.
- Freshness uses the verifier's clock, drift limit, and optional expiration. Replay protection is an optional, in-memory check. It rejects previously accepted nonces within its configured window.
- Local private key exports and archives contain sensitive data. Legacy backup JSON can contain Base64-encoded private PEM. Protect file permissions, encrypt backups separately, and distribute only public material.

## Data protection

The QR, browser snapshot, and operator-entered display text should be treated as public. Do not enter secrets in the display controls. Default network use includes configured time and blockchain providers. When OpenTimestamps is enabled, a commitment is sent to a calendar. Use the [offline profile](README.md#offline-setup) to disable external time and blockchain requests.

## Best practices

Keep the web service bound to loopback for OBS on the same machine. A nonlocal service needs a TLS and access-control layer, a configured admin token, and explicit allowed origins if cross-origin reads are required. Avoid committing configuration files that contain keys or admin tokens. Store private keys with restricted permissions.

## Reporting security vulnerabilities

A private reporting channel is not documented. Use the repository's security reporting option if enabled. Avoid posting working exploit inputs, keys, or admin tokens to a public issue.
