# QR Live Protocol

QRLP generates rotating QR codes for livestream overlays and recorded releases.
A verifier can check freshness and authenticate signed payload bytes with a
trusted issuer key. Those checks describe the QR payload.

Install the locked package with Python 3.11 or newer and uv:

```sh
uv sync --locked
```

Start at the [documentation index](docs/INDEX.md). Use the
[offline walkthrough](docs/OFFLINE.md) to generate and verify a QR with
temporary local keys, or the [streaming guide](docs/STREAMING.md) to set up an
OBS Browser Source. The [technical note](docs/manuscript/README.md) records
what the offline example establishes.

Source available under [CC BY-NC-SA 4.0](LICENSE).
