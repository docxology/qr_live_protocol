# Verify a signed payload offline

This walkthrough uses a fictional issuer and disposable local signing
material. The issuing and verifying CLI processes use separate key
directories. The verifier receives the emitted public trust record.

From the repository root, install the locked dependencies:

```sh
uv sync --locked
```

Run the following block in a POSIX shell. Keep both CLI calls in the same
run so verification can use the default freshness window. The block removes
the temporary data after verification and retains only the PNG for rendering
the technical note.

```sh
(
  set -eu
  qrlp="$(pwd -P)/.venv/bin/qrlp"
  figure_dir="$(pwd -P)/output/figures"
  scratch="$(mktemp -d)"
  trap 'rm -rf "$scratch"' EXIT
  cd "$scratch"
  unset QRLP_ENCRYPTION_KEY

  python3 - <<'PY'
import json
from pathlib import Path

for role in ("issuer", "verifier"):
    config = {
        "time_settings": {"time_servers": [], "local_fallback": True, "ots_enabled": False},
        "blockchain_settings": {"enabled_chains": []},
        "identity_settings": {"include_system_info": False, "include_file_hash": False},
        "web_settings": {"auto_open_browser": False},
        "security_settings": {
            "issuer_id": "studio.example",
            "event_id": "local-demonstration",
            "signature_algorithm": "ecdsa",
            "key_dir": f"{role}-keys",
        },
    }
    Path(f"{role}.json").write_text(json.dumps(config))
PY

  "$qrlp" --config issuer.json generate --sign --format both --output release \
    --user-data '{"title":"Local demonstration"}' --trust-record-output trust.json
  "$qrlp" --config verifier.json verify --file release.json --trust-store trust.json \
    --json-output --strict > verification.json

  python3 - <<'PY'
import json
from pathlib import Path

result = json.loads(Path("verification.json").read_text())
assert result["valid"] and result["signature_verified"] and result["time_verified"]
assert result["trust_mode"] == "public_signature"
assert not result["blockchain_verified"]
print("PASS: trusted signature and local-clock freshness")
PY

  mkdir -p "$figure_dir"
  cp release.png "$figure_dir/offline-example.png"
)
```

Verification uses the system clock. In a real release, obtain the issuer's
public key through an independently authenticated channel before trusting
it. Use the signed JSON with `qrlp verify`; the PNG is the visual transport.
See [security and trust](../SECURITY.md) for the evidence boundary.
