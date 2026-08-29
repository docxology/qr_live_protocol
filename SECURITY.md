# Security Policy — QR Live Protocol (QRLP)

> Status: this file was created by the 2026-08-29 docs audit because
> `docs/INDEX.md` and `docs/COGNITIVE_SECURITY.md` referenced it extensively but
> it did not exist. It contains only facts verified from repo files; sections
> marked TODO-OWNER need the maintainer's input.

## Reporting security vulnerabilities

TODO-OWNER: add a reporting contact/channel. Not documented in repo — needs owner input.

## Security measures

Verified from repo files:

- QRLP is licensed CC BY-NC-SA 4.0 (root `README.md` badge) — non-commercial use restriction.
- `.env.example` exists at the repo root; secrets are expected in `.env`, which is
  gitignored (`.gitignore`). Never commit real credentials.
- Python 3.9+ (root `README.md` badge).

## Threat model

See [Cognitive Security framework](docs/COGNITIVE_SECURITY.md) in this repository
for QRLP's cognitive-security framing. A dedicated technical threat model is
TODO-OWNER: not documented in repo — needs owner input.
