# QRLP TODO — Upcoming Improvements

Last updated: 2026-08-19
Current version: 1.5.0
Test suite: 752 tests, 0 failures (1 skipped: PyYAML optional)
Coverage: 89%

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
