# AGENTS.md — QRLP docs/

## Layout

Topic files in this directory: `INDEX.md` (navigation hub), `README.md`,
`INSTALLATION.md`, `CONFIGURATION.md`, `STREAMING.md`, `API.md`, `FAQ.md`,
`CONTRIBUTING.md`, `COGNITIVE_SECURITY.md`, and stream-specific notes
(`CodeStream_003-1.md`). Root-level companions: `QUICKSTART.md`, `README.md`,
`CHANGELOG.md`, `ISA.md`.

## Key modules (from repo root)

- `src/` — QRLP implementation (see `docs/API.md`).
- `main.py`, `run_all.py`, `setup.py`, `pyproject.toml` — entry points and packaging.
- `examples/`, `output/` — samples and run artifacts.

## Conventions observed

- `docs/INDEX.md` is the navigation hub; register new docs there.
- Links are relative; a previously-missing `SECURITY.md` (referenced ~20 times)
  now exists at repo root with verified-facts-only content.

## Maintenance

Hand-maintained Markdown. `docs/manuscript/MANUSCRIPT_STATUS.md` records the
manuscript posture.
