# Quick start

From the checkout root:

```sh
uv sync --locked
uv run --no-sync qrlp live
```

Visit <http://localhost:8080/viewer> to edit the public caption. In OBS, add an 800 × 800 **Browser** source pointing at <http://localhost:8080/overlay?details=1>. The dashboard is at `/improve`. To bind to another local port and keep the browser closed:

```sh
uv run --no-sync qrlp live --port 9000 --no-browser
```

To create and check an independently verifiable payload:

```sh
uv run --no-sync qrlp generate --sign --issuer-id studio.example --format both \
  --output release --trust-record-output issuer.json
uv run --no-sync qrlp verify --file release.json --trust-store issuer.json --strict
```

Register the issuer key through an authenticated channel before using it for verification. A QR timestamp ages out under the default 30-second freshness policy, so run these commands close together. If external requests are unavailable, use the [offline configuration](README.md#offline-setup).

Use `qrlp --help` and `qrlp COMMAND --help` for CLI options, the [configuration guide](docs/CONFIGURATION.md) for persistent settings, and the [streaming guide](docs/STREAMING.md) to check the final OBS scene.
