# Review Log — Agent-Ergonomics Deep Pass (2026-08-31)

Agent: qr-live-protocol fleet lane (shared frame at
/Users/4d/HermesWorkspace/agent-erg-fleet-20260831/SHARED_FRAME.md).

## Phase 0 — Preflight

- Branch: main; remote origin -> github.com/docxology/qr_live_protocol.git (fetch OK).
- Dirty files at dispatch: 33, all untracked AGENTS.md/README.md pairs from a
  prior doc pass (.github/, docs/manuscript/, examples/, output/, src/,
  templates/, tests/ subtrees). Treated as pre-existing; NOT touched or staged.
- Repo is symlinked from template/projects/ongoing/Cryptography/; this path is canonical.
- Inventory: entry docs README.md (777 lines) + AGENTS.md (untracked); docs/ hub
  with INDEX.md; TODO.md (backlog, dated 2026-08-19); CHANGELOG.md;
  IMPROVEMENTS_SUMMARY.md, IMPLEMENTATION_SUMMARY.md, ASSESSMENT.md,
  RELEASE_NOTES_v1.5.0.txt (transient-suspect); no review-log convention — this
  file created.

## Phase 1 — Cold-start audit

Task (a) status: FAIL — no doc states "current status" with a verification
command. README badges say 752 tests / 89% coverage with no date or check
command; TODO.md header repeats the same numbers (duplicated fact-class);
pyproject.toml says version = "1.5.0" but TODO.md says "Completed (this pass —
v1.6.0 ...)" — v1.6.0 work exists in-tree (optical_throughput.py,
frame_recovery.py, live_simulator.py confirmed present) with no v1.6.0 in
CHANGELOG or pyproject. A cold agent cannot tell what version the tree actually is.

Task (b) next actions: PASS — TODO.md is a good single backlog with Minor/
Medium/Major sections; IMPROVEMENTS_SUMMARY.md partially overlaps past-improvement
content with no supersede markers.

Task (c) primary verification: PASS — README Testing section gives
`python -m pytest tests/ --no-cov -q`; AGENTS.md says `uv run pytest` (752
tests). Verification cost is high on this external drive (a full --collect-only
run exceeded 280s in-lane); the command itself is correct and present.

Findings (each scoped into TODO.md in Phase 2):
- F1 (Medium): version ambiguity — TODO.md claims "v1.6.0 optical-delivery
  hardening" completed but pyproject/CHANGELOG are at 1.5.0; no supersede or
  release marker. Check: grep version pyproject.toml vs TODO.md.
- F2 (Medium): duplicated test-count/coverage fact-class in README badge, README
  Testing prose, and TODO.md header — no canonical home, no "as of" dating.
  Badge counts unverified this pass (full pytest run too slow for lane budget;
  re-verify with: python -m pytest tests/ --no-cov -q | tail -1).
- F3 (Medium): transient summaries (IMPROVEMENTS_SUMMARY.md,
  IMPLEMENTATION_SUMMARY.md, ASSESSMENT.md, RELEASE_NOTES_v1.5.0.txt) sit at
  root as if current; entry docs do not link them (good) but nothing marks them
  historical. Least-resource fix: add historical-status headers, keep files.
- F4 (Minor): docs/INDEX.md footer says "Last Updated: January 2025" while
  CHANGELOG entries are dated 2026-07. Stale claim.
- F5 (Minor): docs/INDEX.md duplicates command/URL quick-reference blocks that
  also exist in README — copy-rot risk; convert to links pointing at canonical
  homes.
- F6 (Minor): AGENTS.md (untracked) "Verify: uv run pytest (752 tests)" — no
  dating or verification path.
- F7 (Minor): README Testing prose asserts "All tests use mocked network calls"
  — unverified this pass; several test files do import unittest.mock (verified:
  tests/test_time_stamper.py and 3 others) but a blanket claim about all 752
  tests needs checking or softening. Softened to a scoped, honest statement.

## Phase 2 — Scope

All findings entered into TODO.md under a new dated section (append, not overwrite).

## Phase 3 — Implementation

Doc-only edits; see TODO.md "Agent-ergonomics pass (2026-08-31)" section for the
list. No source, CI, or version-bump changes.

## Phase 4 — Verify & close

Recorded below after verification.
