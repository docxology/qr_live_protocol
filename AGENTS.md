# QR Live Protocol

Python 3.11+ package for rotating QR payloads, issuer verification and local OBS overlays. The development interpreter is pinned in `.python-version`. The project uses CC BY-NC-SA 4.0.

- `src/core.py` orchestrates generation and verification. `src/serializer.py`, `src/crypto/` and `src/trust.py` define wire and trust behavior.
- `src/web_server.py` serves the overlay, API and Socket.IO endpoints; the browser templates are in `templates/`.
- `src/async_core.py` delegates to the synchronous protocol. The optical simulator and recovery components live in `src/`.
- `pyproject.toml` owns package metadata and dependencies. Use `uv sync --locked --extra dev` for development.
- Run `python -m pytest --no-cov` in the prepared project environment. Tests should mock network providers and use temporary key directories.
- Keep user-facing docs under `docs/` and register guides in `docs/INDEX.md`. Preserve generated demo artifacts and keep new local key material out of tracked files.
