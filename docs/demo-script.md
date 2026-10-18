# Ripple simulation demo

## Thesis
A robot should gather evidence before changing a shared system. Ripple uses FalkorDB to discover which services an intervention affects, decide what evidence is missing, compare intervention sequences in isolated graph copies, and verify the result after acting.

## Three-minute walkthrough

### 0:00–0:25 — The problem
Show the facility view. Say: “The primary cooling supply has failed. Closing its valve seems obvious, but both machines depend on the same cooling header. An apparently local fix can interrupt a critical service.”

### 0:25–1:15 — Evidence before intervention
Select **Limited standby · 5 units**, **Full Ripple**, and **Cyberwave**. Keep the Cyberwave Graph-Hacks tab beside the dashboard. Click **Inject fault & run**.
Say: “Ripple queries the dependency graph and finds that the machines need seven units. It cannot assume the standby is healthy, that the bypass is open, or that its capacity is sufficient. It ranks inspections by whether their results could change the plan, then moves to the inspection points.”
Point to inspection events and the changing candidate statuses. Cyberwave shows SDK-driven twin repositioning; sensor readings come from the synthetic facility model and are permitted only at verified inspection locations.

### 1:15–1:55 — The graph changes the decision
Show the plan cards and Dependencies view. Say: “Each sequence is evaluated in a real FalkorDB GRAPH.COPY branch. Predicted effects stay in the branch; they do not become observations in the live graph. Five units cannot support seven units of demand. Ripple first sheds the low-priority machine, then activates standby, opens the bypass, and isolates primary.”
Expected: **reduce_load_then_restore**, observed flow **5**, remaining demand **4**, **recovered**, zero verification failures. The recorded Cyberwave run used seven inspections.

### 1:55–2:25 — Proof, not an acknowledgement
Select **Stuck bypass valve** and **Mock** for a fast second run. Say: “An accepted command is not proof of a changed world. This valve acknowledges the command but stays closed. A fresh observation catches the mismatch, stops the sequence, and reports no recovery.”
Expected: one verification failure and **not recovered**. The current implementation stops; it does not automatically replan after this failure.

### 2:25–2:50 — Topology changes, planner stays the same
Select **New critical load · 9 units**, run with Mock. Say: “A third machine was added in scenario data. With nine units of demand and eight of standby capacity, the same planner now sheds the low-priority load before restoration.”
Expected: **reduce_load_then_restore**, observed flow **8**, remaining demand **6**, recovered. Compare with **Standby ready · 8 units**, which restores directly for demand seven.

### 2:50–3:00 — Close
Show the persisted decision explanation and replay slider. Say: “Ripple records the evidence context, state revision, chosen sequence, and rejected alternatives. We can replay how it arrived at the intervention and whether the world actually changed.”

## Rehearsal checklist
1. Start FalkorDB, the backend on port 8000, and the dashboard on port 5173 using README.
2. Open http://127.0.0.1:5173 and https://cyberwave.com/s-team-9/envs/graph-hacks while signed in.
3. Keep Cyberwave in Edit mode. This demo does not need a billable cloud physics instance.
4. Run one healthy_5 Cyberwave rehearsal; confirm 5/4 recovery, seven inspections, zero failures.
5. Use Mock if the external SDK is unavailable. State the adapter change explicitly.
6. Download the dashboard trace after the run; the replay slider reviews saved event snapshots.

## What is actually implemented
- Graph topology and multi-hop impact analysis; freshness-aware observations and evidence links to fault hypotheses.
- Inspection selection by a transparent decision-relevance heuristic; shortest-path navigation over graph locations.
- Bounded, domain-specific candidate generation from graph actions, assets and effects.
- Real GRAPH.COPY branches, branch-local predicted observations, prerequisite/capacity validation and branch cleanup.
- Persisted Decision records and explanations read back from the decision trace.
- Fresh post-action verification, including the acknowledged-but-stuck valve failure.
- Six scenarios, three policy configurations, a WebSocket dashboard, event replay and JSON export.
- A dedicated Go2 twin and seven synthetic equipment markers in the user's Cyberwave environment; SDK position updates checked by REST readback.

## Boundaries to state clearly
This is an application-level facility simulation connected to a Cyberwave digital twin. It does not demonstrate walking, collision-aware navigation, valve manipulation, camera perception, fluid dynamics or thermal physics. Equipment markers are simple geometry. The new-load scenario is reflected in the dashboard graph; the static Cyberwave marker scene currently represents the base facility. Readings are synthetic, and graph copies are counterfactual state checks, not physics simulations.

The planner is deterministic and domain-specific. LLM/MCP integration remains unfinished. Verification failure stops execution; automatic recovery replanning is not implemented. State revision is recorded, but there is no atomic multi-operator actuation lock. Logical event times are not physical outage-duration measurements.

The 18-run policy comparison is a deterministic diagnostic matrix, not a statistical benchmark. The local baseline deliberately isolates without inspecting; the graph-without-inspection policy can choose a degraded fallback. Do not describe these as optimized competing systems.

## Validation recorded on 2026-10-18
43 automated tests passed before final documentation/polish. The complete 18-run matrix recovered four of six scenarios with Full Ripple; standby_down and stuck_valve correctly reported no recovery. Both limited comparison policies recovered zero of six. The healthy_5 Cyberwave run recovered with seven inspections, travel cost 78 graph units, zero verification failures, and 13.974 seconds of observed wall time. Network latency makes this time non-repeatable; it is not simulated outage time.

Evidence files: eval/results/evaluation.json and eval/results/cyberwave-demo.json. Final local regression results are reported with the delivered changes.
