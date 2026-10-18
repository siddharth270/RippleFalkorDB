# Cypher queries and graph algorithms

Source of truth: [backend/ripple/graph/queries](../backend/ripple/graph/queries/). Each `.cypher` file documents its purpose, parameters, return shape and caller. Runtime queries are executed through [repository.py](../backend/ripple/graph/repository.py); seeding and schema setup have their own graph modules. Architecture tests enforce graph-access and hidden-truth boundaries.

## Operations that determine the product behavior

1. **Multi-hop impact analysis:** upstream and downstream `FEEDS` traversals identify shared machines and critical services. Alternate-supply queries return paths and their valves; reachability alone does not prove adequate supply.
2. **Evidence lookup:** retrieve the latest observation for each asset/property. Python freshness rules determine whether it is usable. Inspection-target queries enforce robot co-location before sensing.
3. **Inspection selection:** [inspection_ranker.py](../backend/ripple/planning/inspection_ranker.py) scores inspections using plans blocked by missing evidence, affected critical services, distinguishable hypotheses and route cost. Weights are transparent heuristics, not learned information gain.
4. **Weighted routing:** `robot/route_to_inspection_point.cypher` calls FalkorDB `algo.SPpaths` with `ADJACENT_TO`, `weightProp: 'cost'`, `relDirection: 'both'`, and `pathCount: 1`. Same-location inspection returns zero travel cost.
5. **Candidate construction:** [candidates.py](../backend/ripple/planning/candidates.py) reads the action catalog and supply paths and builds bounded cooling-domain sequences, including optional shedding before restoration.
6. **Counterfactual evaluation:** [branching.py](../backend/ripple/graph/branching.py) invokes `GRAPH.COPY` through the SDK; [evaluator.py](../backend/ripple/planning/evaluator.py) checks each action and projects declared effects as branch-local observations. Cleanup runs on success or exception. This command is not a `.cypher` query.
7. **Constraint checks:** [validator.py](../backend/ripple/planning/validator.py) checks all required conditions using graph evidence; [capacity.py](../backend/ripple/planning/capacity.py) checks supply versus active demand using graph topology.
8. **Auditable outcomes:** decision records preserve considered plans and rejection reasons; verification queries link attempts to fresh observations. Explanations query these persisted records rather than generate unsupported claims.

## Complete query catalog

### Actions

- [actions/action_effects.cypher](../backend/ripple/graph/queries/actions/action_effects.cypher) — Declared effects of an Action (what it should change, on which asset).
- [actions/action_prerequisites.cypher](../backend/ripple/graph/queries/actions/action_prerequisites.cypher) — Every Condition an Action REQUIRES, with the asset each condition is on.
- [actions/catalog.cypher](../backend/ripple/graph/queries/actions/catalog.cypher) — Action catalog and declared effects for bounded candidate generation.
- [actions/create_attempt.cypher](../backend/ripple/graph/queries/actions/create_attempt.cypher) — Record that a command was SENT (not that it worked): invariant #3.
- [actions/update_attempt.cypher](../backend/ripple/graph/queries/actions/update_attempt.cypher) — Record the command acknowledgement (a receipt, still not proof of effect).
- [actions/verify_attempt.cypher](../backend/ripple/graph/queries/actions/verify_attempt.cypher) — Link an attempt to the Observation that confirmed (or refuted) its effect.

### Evidence

- [evidence/insert_observation.cypher](../backend/ripple/graph/queries/evidence/insert_observation.cypher) — Persist one Observation (never overwrite), link it to its asset, producer and incident,
- [evidence/inspection_points_for.cypher](../backend/ripple/graph/queries/evidence/inspection_points_for.cypher) — Where can the robot go to observe this asset property? (inspection point + its location)
- [evidence/latest_observation.cypher](../backend/ripple/graph/queries/evidence/latest_observation.cypher) — Current belief about one asset property = its most recent Observation (DP1).
- [evidence/stale_evidence.cypher](../backend/ripple/graph/queries/evidence/stale_evidence.cypher) — Decision-relevant evidence (properties named by evidence Conditions) that is missing or older

### Hypotheses

- [hypotheses/distinguishing_inspections.cypher](../backend/ripple/graph/queries/hypotheses/distinguishing_inspections.cypher) — Inspection points that would discriminate between an incident's open hypotheses, most discriminating first.
- [hypotheses/hypothesis_expectations.cypher](../backend/ripple/graph/queries/hypotheses/hypothesis_expectations.cypher) — Which open hypotheses of an incident predict something about this (asset, property), and what.
- [hypotheses/instantiate_hypotheses.cypher](../backend/ripple/graph/queries/hypotheses/instantiate_hypotheses.cypher) — Copy every HypothesisTemplate into open Hypotheses for an incident, with their EXPECTS patterns
- [hypotheses/open_hypotheses.cypher](../backend/ripple/graph/queries/hypotheses/open_hypotheses.cypher) — Open hypotheses for an incident with counts of supporting / contradicting observations (evidence, not causation).
- [hypotheses/record_hypothesis_evidence.cypher](../backend/ripple/graph/queries/hypotheses/record_hypothesis_evidence.cypher) — Link an Observation to a Hypothesis as SUPPORTS or CONTRADICTS (evidence, not causation).

### Impact

- [impact/affected_assets.cypher](../backend/ripple/graph/queries/impact/affected_assets.cypher) — Every asset downstream of a given asset along FEEDS (multi-hop impact), with hop distance.
- [impact/alternate_supplies.cypher](../backend/ripple/graph/queries/impact/alternate_supplies.cypher) — Supplies other than the faulted one with a FEEDS path to a target asset, and the valves on that path.
- [impact/critical_services_affected.cypher](../backend/ripple/graph/queries/impact/critical_services_affected.cypher) — Critical services provided by machines downstream of a given asset.
- [impact/downstream_machines.cypher](../backend/ripple/graph/queries/impact/downstream_machines.cypher) — Machines fed (directly or multi-hop) by an asset, with their cooling demand and criticality.
- [impact/upstream_assets.cypher](../backend/ripple/graph/queries/impact/upstream_assets.cypher) — Everything an asset depends on upstream along FEEDS (reverse multi-hop), nearest first.

### Provenance

- [provenance/context.cypher](../backend/ripple/graph/queries/provenance/context.cypher) — Capture source revision and non-predicted evidence IDs at decision time.
- [provenance/create_decision.cypher](../backend/ripple/graph/queries/provenance/create_decision.cypher) — Persist a Decision: TRIGGERED_BY incident, one Plan per candidate with CONSIDERED, plus SELECTED
- [provenance/decision_trace.cypher](../backend/ripple/graph/queries/provenance/decision_trace.cypher) — Everything recorded about a Decision, for explanations (invariant #5: text derived only from this).
- [provenance/open_incident.cypher](../backend/ripple/graph/queries/provenance/open_incident.cypher) — Open an Incident concerning the asset that raised the alarm.

### Robot

- [robot/inspection_targets.cypher](../backend/ripple/graph/queries/robot/inspection_targets.cypher) — Location gate for sensing: what can be read at an inspection point, ONLY if the robot is
- [robot/robot_location.cypher](../backend/ripple/graph/queries/robot/robot_location.cypher) — The robot's current verified Location (DP4).
- [robot/route_to_inspection_point.cypher](../backend/ripple/graph/queries/robot/route_to_inspection_point.cypher) — Cheapest ADJACENT_TO route (by cost) from the robot's location to an inspection point,
- [robot/set_robot_location.cypher](../backend/ripple/graph/queries/robot/set_robot_location.cypher) — Move the robot's AT edge. Called ONLY after arrival is verified by pose readback (DP4).

### Seed

- [seed/create_nodes.cypher](../backend/ripple/graph/queries/seed/create_nodes.cypher) — Batch-create nodes that share one label set.
- [seed/create_relationships.cypher](../backend/ripple/graph/queries/seed/create_relationships.cypher) — Batch-create relationships of one type between nodes matched by id.

### Ui

- [ui/edges.cypher](../backend/ripple/graph/queries/ui/edges.cypher) — Operational topology, placement and robot routes for visualization.
- [ui/evidence.cypher](../backend/ripple/graph/queries/ui/evidence.cypher) — Known observations only, never simulator truth.
- [ui/nodes.cypher](../backend/ripple/graph/queries/ui/nodes.cypher) — Known-world graph nodes for the demo, excluding historical observations.

## Example: weighted route

The complete query handles same-location routes and unreachable targets; its main path operation is:

```cypher
MATCH (:Robot {id: $robot_id})-[:AT]->(start:Location)
MATCH (:InspectionPoint {id: $ip_id})-[:LOCATED_IN]->(goal:Location)
WHERE start <> goal
CALL algo.SPpaths({sourceNode: start, targetNode: goal,
                   relTypes: ['ADJACENT_TO'], weightProp: 'cost',
                   relDirection: 'both', pathCount: 1})
YIELD path, pathWeight
RETURN [n IN nodes(path) | n.id] AS locations, pathWeight AS cost
```

## Example: prerequisites are explicit graph relationships

```cypher
MATCH (a:Action {id: $action_id})-[:REQUIRES]->(c:Condition)
OPTIONAL MATCH (c)-[:CONDITION_ON]->(asset:Asset)
RETURN c, asset
```

Finding a condition is not the same as satisfying it. Application validation checks values, freshness and computed capacity before execution.

## Reproduce and inspect

Run `uv run python -m scripts.run_demo healthy_5 --adapter mock` from `backend/`. It prints a graph name. Select that graph in the FalkorDB Browser and use the read-only queries in [local setup](local-setup.md#inspect-the-database). Do not run seed/delete queries against another run's graph. Candidate copies are temporary; decisions and execution evidence remain in the demo graph.
