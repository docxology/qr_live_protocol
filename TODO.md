# QRLP TODO — Upcoming Improvements

Last updated: 2026-08-31
Current version: from pyproject.toml (`grep '^version' pyproject.toml` -> 1.5.0 as of 2026-08-31; note the v1.6.0 section below describes completed in-tree work not yet released — CHANGELOG has no 1.6.0 entry)
Test suite / coverage: NOT restated here — canonical source is a live run (`python -m pytest tests/ --no-cov -q | tail -1`); README badge states last-verified numbers

---

## Completed (this pass — v1.6.0 optical-delivery hardening)

### Major
- [x] **High-fps dynamic optical throughput optimization** —
  `src/optical_throughput.py`: dynamic frame cadence (`adapt`, floor/ceiling),
  payload symbol reuse (per-payload cache), batch pre-encode + bounded FIFO
  drain, latency averaging, and a performance report. 99% coverage.
- [x] **Fault-tolerant frame recovery algorithms** —
  `src/frame_recovery.py`: receiver-side re-ordering, gap detection, gap
  recovery within a retransmission window, unrecoverable-gap stream resets,
  and isolateable stats snapshots. 100% coverage.
- [x] **End-to-end live simulator suite** —
  `src/live_simulator.py` + `qrlp simulate-live`: deterministic optical
  channel model (drop/reorder), wires throughput controller + frame recovery
  into a full delivery loop, emits JSON/human reports. 97% coverage.
  Tests: `tests/test_live_simulator.py`, `tests/test_optical_throughput.py`,
  `tests/test_frame_recovery.py`, plus CLI integration tests.

### Medium
- [x] **Extended key rotation mechanisms** —
  `KeyManager.archive_key` / `KeyManager.rotate_signing_key` (archive instead
  of destroy) and `qrlp keys rotate --archive-dir/--trust-store/--issuer` for
  continued verification of previously signed QRs.
- [x] **Stream error resilience** —
  `tests/test_async_core_resilience.py` exercising batch partial-failure,
  stream cancellation/data/callback errors, live-gen start/stop, network
  degradation, and performance optimization paths.
- [x] **WebSocket protocol benchmarks** —
  `QRLiveWebServer.benchmark_websocket_throughput` (in-process, no network)
  and `qrlp benchmark-ws --iterations N [--json-output]`.

### Minor
- [x] Typing annotations: implicit-Optional `= None` → `= None` in
  `core.py`/`async_core.py`; added `from __future__ import annotations` and
  forward-ref annotations where forward class references were unresolved.
- [x] CLI formatting + lint: new `simulate-live` / `benchmark-ws` commands;
  `ruff` config added to `pyproject.toml`; whole tree now passes
  `uv run ruff check` clean; upgraded `examples/`, `main.py`, `run_all.py`,
  and tests to pass lint (removed dead/malformed demo code).
- [x] Documentation: README + docs/API.md sections for recovery, throughput,
  simulator, and key-rotation trust continuity.

---

## Minor Improvements

### Documentation
- [ ] Add a dedicated `docs/OPTICAL_DELIVERY.md` guide with latency/fps tuning.
- [ ] Document `benchmark-ws` percentile interpretation and CI usage.
- [ ] Add a "key rotation runbook" (rotate → archive → trust store → verify).

### Typing & Tooling
- [ ] Run `mypy --strict` and close remaining gaps (new modules already typed).
- [ ] Add more typing annotations to `examples/` and `run_all.py`.
- [ ] Enforce `ruff` + import sorting in CI via a lint job.

### CLI Formatting
- [ ] Add `--no-color`/`--plain` output flag for script-friendly CLI.
- [ ] Consistent `--json-output` envelope for all status/health commands.

---

## Medium Improvements

### Key Rotation & Key Lifecycle
- [ ] Add `qrlp keys list --archived` and `qrlp keys restore <key_id>`.
- [ ] Add scheduled/automated rotation policy (age- or usage-based) + CLI `keys
      policy`.
- [ ] Add trust-store diff/merge command for multi-verifier deployments.

### Stream & Transport Resilience
- [ ] Surface partial-failure counts from `batch_generate_qr_async` (not just
      successful subset).
- [ ] Add jitter + burst (correlated loss) models to `OpticalChannelModel`.
- [ ] Add adaptive retransmission: derive `retransmission_window` from live
      loss statistics instead of a fixed config.
- [ ] Add reconnect/backoff handling for WebSocket drops in `web_server.py`.

### Benchmarks
- [ ] Add a `qrlp benchmark-live` that runs the full simulator headlessly and
      writes a CSV/JSON report to a file.
- [ ] Add multi-client WebSocket benchmark (simulated N socket clients).
- [ ] Add a decode-side benchmark using real QR readability checks when
      `pyzbar`/`cv2` are installed.

---

## Major Improvements

### Optical Delivery & Recovery
- [ ] **Fault-tolerant frame recovery with parity/ECC** — add XOR parity frames
      so a single lost frame within a group is reconstructible, not just
      re-requested.
- [ ] Payload compression (zlib/gzip) before encoding to raise usable payload
      per frame / reduce chunk count.
- [ ] QR payload versioning + on-chain content commitment.
- [ ] ECDH-based QR payload encryption and multi-signature payloads.

### Live Engineering
- [ ] Wire throughput controller + frame recovery into `async_core`/`core`
      production loops (opt-in), not just the simulator.
- [ ] OBS / browser-source optimized renderer with higher fps.
- [ ] Native mobile scanner SDK and GPU-accelerated encode path.

### Platform & Operations
- [ ] Docker container with health check; systemd unit; Kubernetes manifest.
- [ ] CI/CD (GitHub Actions) with lint + test + coverage gates.
- [ ] Prometheus metrics endpoint + OpenTelemetry tracing.
- [ ] SQLite-backed key store, audit logging, and multi-tenancy.
- [ ] Flask → FastAPI migration and `requests` → `httpx` replacement.

---

## Security Backlog
- [ ] Add SECURITY.md and Dependabot + CodeQL/Snyk scanning.
- [ ] Add QR revocation + decentralized identity (DIDs / verifiable credentials).

---
## Agent-ergonomics pass (2026-08-31) — findings from cold-start audit

Log: `REVIEW_LOG_2026-08-31.md`. All items below were implemented in this pass
(doc-only) unless marked deferred.

### Medium
- [x] **Version ambiguity** — TODO claimed "completed v1.6.0" work while
  pyproject/CHANGELOG say 1.5.0; header now points to pyproject as canonical and
  flags the unreleased-v1.6.0 state. Remaining decision (release cut or
  CHANGELOG entry) is a maintainer call, not a doc fix. Files: `TODO.md`,
  `pyproject.toml`, `CHANGELOG.md`.
- [x] **Test-count/coverage fact-class duplicated** (README badge, README prose,
  TODO header, AGENTS.md) — TODO/AGENTS now link to a live-run command;
  README prose carries the "last verified at v1.5.0" dating. Files: `README.md`,
  `TODO.md`, `AGENTS.md`.
- [x] **Transient root summaries unmarked** — IMPROVEMENTS_SUMMARY.md,
  IMPLEMENTATION_SUMMARY.md, ASSESSMENT.md, RELEASE_NOTES_v1.5.0.txt now carry
  historical-snapshot headers; entry docs never linked them (verified).

### Minor
- [x] `docs/INDEX.md` stale "Last Updated: January 2025" — dated 2026-08-31 with
  verification path; duplicated command/URL/file quick-reference blocks replaced
  with links to canonical README sections. Files: `docs/INDEX.md`.
- [x] README Testing prose "All tests use mocked network calls" blanket claim —
  softened to scoped, accurate statement. Files: `README.md`.
- [x] AGENTS.md verify line lacked dating/verification path — fixed.
  Files: `AGENTS.md`. (Note: AGENTS.md was untracked at dispatch — pre-existing
  local state, not committed by this pass.)

### Deferred
- [ ] **Add CI lint job** (pre-existing TODO entry, out of scope this pass: CI
  config edits are excluded by the shared frame).
- [ ] **Full fresh pytest verification of badge counts** — deferred: full-suite
  run on the external drive exceeded the lane time budget (collection alone
  >280s). Human check: `python -m pytest tests/ --no-cov -q | tail -1`.
