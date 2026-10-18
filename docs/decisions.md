# Decisions (ADR-lite)

## D-001 — Python tooling: uv, Python 3.12
- **Context:** Local Python is 3.14; some wheels lag new releases.
- **Options:** pip+venv; uv; poetry.
- **Decision:** uv, `requires-python >=3.11`, pin 3.12 via `.python-version`.
- **Why:** fast, lockfile, one tool; 3.12 avoids wheel gaps.

## D-002 — LLM provider: Claude (Anthropic SDK)
- **Context:** Agent layer needs tool calling; validators are deterministic and have final say.
- **Decision:** Anthropic SDK, model configured via `LLM_MODEL`.
- **Why:** native tool use; provider only affects `agent/orchestrator.py`.

## D-003 — Cypher lives in `.cypher` files, loaded by name
- **Context:** Submission must show "the queries the product depends on"; judges must find them fast.
- **Options:** inline strings in Python; `.cypher` files + loader.
- **Decision:** one file per query under `graph/queries/<area>/`, header comment
  (purpose, parameters, returns, used-by), loaded via `query_loader.py`, called only from `repository.py`.
- **Why:** single auditable surface; makes the "graph is load-bearing" claim checkable.

## D-004 — Cyberwave budget: proof + demo only (revised: see end)
- **Context:** 50 API credits total; per-call cost not documented publicly. `affect("sim"/"mujoco")` starts billable MuJoCo runs.
- **Decision:** Dev, tests and the full evaluation run on `MockRobotAdapter`. Cyberwave used for the 0.2 proof and the final demo only, in `affect("playground")`. Measure credits per proof run; reserve ~half for demo recording.
- **Why:** eval (3 configs × 6 scenarios) on Cyberwave could exhaust the budget; mock keeps dev unblocked.

## D-005 — Robot movement: open-loop burst + single pose verification; coordinates in graph
- **Context:** SDK exposes velocity bursts (`move_forward`, `turn_*`) and `pose.get()`; no navigate-to-waypoint (`missions.py` is explicitly aspirational).
- **Options:** closed-loop correction (many calls), open-loop dead reckoning, `edit_position` teleport (editor layout, not locomotion).
- **Decision:** per hop, issue the burst, then one `pose.get()` to verify arrival within tolerance. Location `x, y` stored on `Location` nodes in FalkorDB; adapter receives target coordinates, holds no topology.
- **Why:** credit-cheap, honest ("commanded, then verified" — predicted ≠ observed), keeps the graph load-bearing (invariant #1).

## D-006 — Cyberwave proof result (0.2): blocked in playground; proceed on mock
- **Finding (2026-10-17):** SDK v0.7.3 authenticates, lists catalog, creates a Go2 twin in the Quickstart
  Environment, connects MQTT (mqtt.cyberwave.com:8883). But in `affect("playground")`:
  `pose.get()` returns no pose (view `.pose is None`), and `locomotion.move_forward` does not move the
  twin (observed in browser), even when reusing an existing twin whose controller policy is attached.
- **Narrowed down:** the browser environment defaults to LIVE (expects paired hardware). In SIMULATE,
  keyboard teleop (W) moves the same twin (`03a3e4d0…`, the only twin in the workspace), but SDK
  commands do not. Traced in SDK source: `affect("playground")` → runtime `simulation` → commands
  published on `cyberwave/twin/{uuid}/command` with `source_type="sim_tele"`. Hypothesis: browser
  playground simulates keyboard input locally and does not consume SDK MQTT commands. Unconfirmed;
  question for Cyberwave team.
- **Gotchas found:** `cw.twin("unitree/go2")` raised "not found" because `get_by_registry_id` swallows
  all exceptions (worked via asset UUID); `cw.twin(asset)` creates a NEW twin per call (reuse via `twin_id=`);
  `pose.get()` returns a live view (snapshot with `translation_dict()`).
- **Decision:** proceed with `MockRobotAdapter` (0.3). Ask Cyberwave team how to get locomotion + pose
  in playground; revisit the Cyberwave adapter if unblocked. Not claiming Cyberwave integration until proven.
- **Why:** CLAUDE.md 0.2 fallback; protect remaining credits; honest scope.

- **Update (MuJoCo):** `affect("sim", environment_id=..., duration=60)` starts MuJoCo at ~0.01 credits/min
  (~0.60/h) — credits are not the constraint (revises D-004's premise). MuJoCo started and reported
  running, but Go2 velocity commands still produced no pose (likely needs a locomotion controller; unconfirmed).

## D-007 — Cyberwave adapter moves the twin via `edit_position` (repositioning, not locomotion)
- **Context:** Locomotion + pose readback unresolved in playground and MuJoCo (D-006).
- **Proof (2026-10-17):** `twin.edit_position(x=1.5, y=-0.5)` then independent REST readback
  `cw.twins.get_raw(uuid).position_x/y` → (0,0) → (1.5,-0.5). Script: `backend/scripts/cyberwave_reposition_proof.py`.
- **Decision:** `CyberwaveRobotAdapter.move_to` = `edit_position` to the target Location's (x, y) from the graph;
  `current_pose` = REST readback. Described honestly as "twin repositioning", not walking.
  Dev/tests/eval on `MockRobotAdapter`; Cyberwave adapter for demo visualization.
- **Why:** deterministic, no MQTT/sim dependency, no sim credits; same `RobotAdapter` interface, so
  swapping in real locomotion later changes only `move_to`.

## D-008 — Graph model v1 (`docs/graph-model.md`): DP1–DP5 accepted by Siddharth
- DP1 state only as Observations · DP2 FEEDS + CONNECTED_TO both · DP3 InspectionPoint own label ·
  DP4 `(:Robot)-[:AT]->(:Location)` moved on verified arrival · DP5 branches write `source:"predicted"` Observations.
- **Status:** drafted by Claude; Siddharth reviewed and agreed with all five on 2026-10-17. Rationale per DP is in the graph-model.md table.

## D-009 — Run dev scripts as modules (`uv run python -m scripts.<name>`)
- **Context:** `.venv` lives under iCloud-synced `~/Documents`; macOS flags `_editable_impl_ripple.pth` as hidden and
  Python skips hidden `.pth` files, so `python scripts/x.py` can't import `ripple`.
- **Decision:** invoke scripts with `-m` from `backend/` (adds cwd to `sys.path`). Alternative: move repo out of iCloud.

## D-010 — Seeding Cypher: two template files + label/type whitelist
- **Context:** FalkorDB can't parameterise labels or relationship types (`SET n:$(x)` is a syntax error, verified).
- **Options:** one `.cypher` per label/type (~20 files); inline f-strings in seed.py; two templates with whitelist.
- **Decision (Siddharth):** `queries/seed/create_nodes.cypher` + `create_relationships.cypher` with `{labels}`/`{type}`
  placeholders, filled only from a whitelist derived from graph-model.md; values always passed as `$rows`.
- **Why:** Cypher stays auditable in files (D-003); whitelist prevents injection; batching via UNWIND.

## D-011 — Seed clears via graph delete, then ensure_schema
- **Decision (Siddharth):** `graph.delete()` (tolerating "empty key"), then idempotent `ensure_schema`, then nodes, then relationships.
- **Why:** truly clean slate; FalkorDB errors on re-creating an existing index ("already indexed", verified), so ensure_schema must tolerate it anyway.
- **Scenario files:** one YAML per scenario with `graph:` (known, seeded) and `truth:` (hidden, simulator only).

## D-012 — Milestone 1 vertical-slice design
- **Candidates:** fixed ordered list in `agent/orchestrator.py` (`restore_via_standby` → `shed_noncritical_load`).
  Honest scope: M1 proves "observation changes the action"; graph-driven candidates + branch evaluation come in M3/M4.
- **Graph-driven parts:** prerequisites (`REQUIRES/CONDITION_ON`), where to inspect (`INSPECTS/LOCATED_IN`),
  coordinates (`Location.x/y`), robot location (`AT`), declared effects (`AFFECTS`) — all via repository queries.
- **Hidden truth isolation:** orchestrator receives `sense(ip_id)` and `actuate(asset, prop, value)` callables;
  only the scenario runner wires them to `simulator.sensors` / `simulator.controls`. AST test enforces no
  `ripple.simulator` imports from agent/planning/evidence.
- **Location gate in Cypher:** `robot/inspection_targets` returns rows only if the robot is AT the IP's location.
- **Execution:** each effect → `ExecutionAttempt` (sent) → ack (acked) → re-inspect → `VERIFIED_BY` observation
  (verified/failed). A stuck valve is acked but fails verification (test).
- **Validator:** missing/stale evidence → `missing` list (robot inspects); fresh violating evidence → hard reject;
  `computed` conditions (capacity) are rejected as not-yet-implemented until M2.
- **Scenarios:** `extends:` lets `standby_down` / `healthy_5` reuse the healthy_8 graph and change only `truth:`,
  so differences in behaviour come from observations, not topology or code.
- **Freshness windows (synthetic):** position/running 120 s, flow/temperature 60 s, health/capacity 600 s.

## D-013 — Milestone 2: connected consequences + capacity
- **Candidate plans (preference order):** `isolate_primary_now` (the obvious local fix) → `restore_via_standby`
  → `reduce_load_then_restore` → `shed_noncritical_load` (approved degraded operation). Still a fixed list (D-012).
- **Impact trace (multi-hop):** `upstream_assets`, `alternate_supplies` (exclude may be null), `downstream_machines`,
  `critical_services_affected`. Result records shared machines and critical services at incident start.
- **Capacity check (`planning/capacity.py`, condition `c_capacity_ok`):** a supply path contributes only if
  supply health = ok, running = true, every valve on the path open, and *observed* capacity known (fresh or
  predicted). Demand = machines believed running; **no evidence ⇒ assume running (conservative)**.
  Decision-driven: a known-false gate zeroes the path without inspection; known ≥ demand ⇒ ok; known + nominal
  upper bound < demand ⇒ violation without inspection; otherwise request the missing evidence.
- **Violation text names the critical services cut** (from `critical_services_affected`), so "isolate primary now"
  is rejected *because* it would cut `line_a`.
- **Plan validation with predictions:** `validate_plan` passes each step the declared effects of earlier steps
  (`transition_model.with_effects`), labelled `predicted`. M4 swaps this overlay for GRAPH.COPY branches (DP5).
- **New prerequisite:** `isolate_primary REQUIRES c_primary_failed` (don't isolate a healthy supply).
- **Service verification:** after execution, the header's observed flow must cover running machines' demand;
  `standby_down` therefore ends **not recovered** (machine A unserved), i.e. degraded, reported honestly.

## D-014 — Milestone 3: evidence-driven planning
- **Hypotheses:** scenario defines `HypothesisTemplate` nodes with `EXPECTS {property, op, value}` and
  `DISTINGUISHED_BY`; `instantiate_hypotheses` copies them per incident. Diagnosis-phase observations are
  classified (match ⇒ `SUPPORTS`, mismatch ⇒ `CONTRADICTS` + status `rejected`). Evidence, not causation.
  Only diagnosis observations are classified (post-intervention state would otherwise "support" wrong hypotheses).
- **Decision relevance score** (`planning/inspection_ranker.py`): `3·blocks + 1·critical + 0.5·hypotheses − 0.05·travel`
  where blocks = undecided preferred plans waiting on that point's evidence. Transparent heuristic, not information gain.
- **Inspection policy:** inspect only while a *more-preferred* plan is undecided; travel only to the top-scoring
  point and only if blocks > 0; re-evaluate all plans after every inspection. Plans whose missing evidence no
  reachable point can provide are rejected as "evidence unobtainable".
- **Routing:** `route_to_inspection_point` uses FalkorDB `algo.SPpaths` (weighted by `ADJACENT_TO.cost`,
  undirected); the robot moves hop by hop and the `AT` edge moves only after each verified hop.
- **Stale evidence:** `stale_evidence` lists decision-relevant facts that are missing or older than their window
  (windows passed from `freshness.py`); `stale_valve` scenario proves an hour-old "bypass open" log is not trusted.
- **Scenario loader:** `extra_observations` lets a scenario add prior evidence while inheriting the base graph.


## D-015 — Branches, provenance and simulation delivery (2026-10-18)

Use real GRAPH.COPY for candidate evaluation; predicted observations exist only on disposable branches. Retry only the explicit Redis fork-contention error, with a bounded delay. Generate bounded cooling-domain candidates from graph actions rather than embedding the scenario list in the orchestrator. Record the current revision and available evidence context before execution, then render explanations from persisted records. This is not an atomic transaction spanning physical actuation.

Expose event snapshots through a local FastAPI/WebSocket demo and label stale evidence. Add a critical load in YAML as a topology generalization check. Compare three transparent deterministic policies across six scenarios; this is a diagnostic matrix, not a statistical benchmark.

Cyberwave uses a dedicated environment twin and seven equipment markers, with SDK repositioning independently read back through REST. Preserve the distinction between synthetic facility sensing, twin positioning, and physically simulated robotics. Do not start billable simulation for this path.
