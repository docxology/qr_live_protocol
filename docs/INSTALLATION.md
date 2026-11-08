# Installation

QRLP requires Python 3.11 or newer. The repository's `.python-version` selects its development interpreter; the library's supported version range is declared in `pyproject.toml`.

## Install from the checkout with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run this from the repository root:

```sh
uv sync --locked --extra dev
uv run --no-sync qrlp --version
uv run --no-sync qrlp --help
```

Omit `--extra dev` for a basic runtime; include it when running the async tests. On POSIX, `./setup.sh` is a wrapper for locked development setup. `uv sync --locked` refuses a stale lockfile; see [uv's locking guide](https://docs.astral.sh/uv/concepts/projects/sync/).

## Install with pip

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
qrlp --version
```

On Windows activate with `.venv\Scripts\Activate.ps1`. For development, install with `python -m pip install -e '.[dev]'`. The legacy `requirements.txt` delegates to this editable install. The two supported CLI names are `qrlp` and `qr-live-protocol`; `python -m src` also works.

## Optional dependencies

Use `uv sync --locked --extra full` or `python -m pip install '.[full]'` for YAML configuration, optional QR scanning, and memory statistics. The `pyzbar` scanner needs a native ZBar installation. The PNG generator does not need a camera, OpenCV, or ZBar.

## Build and test a distribution

```sh
uv build
uv run --no-sync python -m pytest --no-cov
```

Install the wheel in a fresh environment and run `qrlp --version`, `qrlp --help`, and `qrlp live --no-browser` from outside the checkout. The wheel includes the browser templates under the Python package. Use [offline settings](../README.md#offline-setup) to exercise the overlay without NTP or blockchain services.
