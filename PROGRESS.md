# Progress

## Current step
**Milestone 4 and the core Milestone 5 simulation demo are implemented.** See the [submission guide](docs/submission.md) for judge setup and current scope.

## Log

### 2026-10-15 — Session 1
- **Done:** Stack confirmed (uv / Python 3.12, FastAPI, Pydantic v2, pytest, FalkorDB in Docker,
  Claude for agent layer, React+TS+Vite with graph-viz lib TBD). Repo scaffolded per CLAUDE.md §4:
  stubs, boilerplate, process docs only.
- **Tested:** nothing yet.
- **Open issues:**
  - Verify FalkorDB image tag/ports and `GRAPH.COPY` availability against current docs.
  - Verify FalkorDB shortest-path support (needed for `robot/route_to_inspection_point`).
  - Cyberwave SDK package name/capabilities unknown until 0.2.
  - Graph-viz library choice deferred to Milestone 5.
- **Next:** `docker compose up`, implement `graph/client.py`, round-trip one node from Python.

### 2026-10-17 — Session 2
- **Done (0.1):** Docker Desktop + FalkorDB up; uv installed, `uv sync` OK. `graph/client.py`
  (`get_db` cached shared client, `get_graph`), conftest fixtures (session ping that fails loudly;
  per-test `test_<name>_<hex>` graph with tolerant teardown), `test_asset_round_trip`.
- **Tested:** `uv run pytest -m integration` → 1 passed; no leftover graphs.
- **Open:** explain-back answers for 0.1 owed; fail-first run not confirmed.
- **Next:** 0.2 Cyberwave proof.
- **0.2 in progress:** SDK read (v0.7.3); decisions D-004 (credit budget), D-005 (open-loop + verify, coords in graph). Proof script pending run.
- **0.2 result:** blocked: playground accepts commands but robot doesn't move and no pose returns (D-006).
  Scripts: `backend/scripts/cyberwave_proof.py`, `list_assets.py`. Action: ask Cyberwave team.
- **0.2 DONE:** reposition proof passes (D-007): before (0,0) → after (1.5,-0.5) via independent REST readback.
  Locomotion unresolved (D-006) — question for Cyberwave team.
- **0.3 DONE (AI-written on request):** `robot/base.py` (`Pose`, `RobotAdapter` Protocol, `arrived`),
  `robot/mock_adapter.py` (teleport + `fail_next_moves`), `tests/unit/test_robot_adapter.py` (5 tests).
- **Tested:** `uv run pytest` → 6 passed, 2 skipped (architecture stubs); ruff clean.
- **Open:** `CyberwaveRobotAdapter` (edit_position per D-007) not yet written; explain-back for 0.1/0.2 owed.
- **0.4 drafted:** `docs/graph-model.md` v1 + `docs/graph-model-preview.cypher` + `scripts/load_model_preview.py`
  (27 nodes / 51 rels in `model_preview`; impact + robot-location queries return expected rows).
- **0.4 DONE:** DP1–DP5 accepted (D-008).
- **Next:** Milestone 1 vertical slice.

- **1.1 DONE:** seed from scenario YAML (templates + whitelist), `ensure_schema`, seed tests.
- **Milestone 1 code (AI-written on request):** scenario loader with `extends`, evidence models + freshness,
  repository (12 runtime queries), simulator (ground truth, header flow, controls, location-gated sensors),
  validator `check_action`, orchestrator vertical slice, architecture tests, scenario tests (D-012).
- **Tested:** with the completed queries (verification overlay) → 24 passed. In-repo `.cypher` bodies pending.
- **Next:** paste queries → `uv run pytest` green → Milestone 2 (impact queries, capacity check).
- **M1 DONE:** all queries pasted; `uv run pytest` → 24 passed. M2–M4 queries pasted (not yet wired).
- **Housekeeping:** AI_USAGE.md removed at Siddharth's request; README carries a one-line AI disclosure. A collaborator handoff was added at that stage; it has since been removed from the judging submission.
- **Next:** M2 — wire impact queries, implement `planning/capacity.py`, reject "isolate primary now".

### 2026-10-17 — Milestones 2 & 3
- **M2 DONE (D-013):** impact queries wired; `planning/capacity.py`; 4 candidate plans; "isolate primary now"
  rejected with "available 0 < demand 7 … would cut critical service line_a"; healthy_5 → reduce load then restore;
  service verification by observed header flow (standby_down = degraded, not recovered).
- **M3 DONE (D-014):** hypotheses (templates → per-incident, SUPPORTS/CONTRADICTS), decision relevance score,
  decision-driven inspection loop, hop-by-hop routing via `algo.SPpaths`, `stale_evidence`, `stale_valve` + `stuck_valve` scenarios.
- **Tested:** `uv run pytest` → 35 passed.
- **Next:** M4 — GRAPH.COPY branch per candidate plan, Decision provenance, explanations from `decision_trace`.


## 2026-10-18 — M4 and simulation demo
Implemented graph copies, graph-driven candidate generation, persisted explanations, six-scenario evaluation, dashboard and Cyberwave scene. Initial expanded regression: 43 tests passed. Cyberwave healthy_5: recovered, seven inspections, zero verification failures. See docs/demo-script.md for the script and remaining proposal gaps. Changes remain local.
