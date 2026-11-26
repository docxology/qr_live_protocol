# Quick start

From the checkout root, install the locked package and open the overlay:

```sh
uv sync --locked
uv run --no-sync qrlp live
```

Visit <http://localhost:8080/viewer> to edit the public caption. In OBS, add
an 800 × 800 Browser Source at <http://localhost:8080/overlay?details=1>.
Open <http://localhost:8080/improve> for diagnostics.

To keep the browser closed, pass `--no-browser`. To disable external clock
and chain providers, use the configuration in the
[offline walkthrough](OFFLINE.md). That walkthrough also verifies a
signed payload in a separate local CLI process.

Use `qrlp --help` or `qrlp COMMAND --help` to see options. The [streaming
guide](STREAMING.md) covers the OBS setup in more detail.
