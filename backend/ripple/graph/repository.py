"""Typed functions that run named queries. The ONLY module that executes runtime Cypher.

Every function maps 1:1 to a file in graph/queries/ (see docs/queries.md). Rows come back as
dicts keyed by the query's RETURN aliases.
"""

from typing import Any

from falkordb import Graph

from ripple.evidence.models import Observation
from ripple.graph.query_loader import load_query

Row = dict[str, Any]


def _run(
    graph: Graph, name: str, params: dict[str, Any] | None = None, *, write: bool
) -> list[Row]:
    query = load_query(name)
    result = graph.query(query, params) if write else graph.ro_query(query, params)
    columns = [h[1] for h in result.header]
    return [dict(zip(columns, row, strict=True)) for row in result.result_set]


def _one(rows: list[Row]) -> Row | None:
    return rows[0] if rows else None


# --- evidence -------------------------------------------------------------------
def insert_observation(graph: Graph, observation: Observation) -> int:
    """Persist an Observation with provenance; return the new StateRevision number."""
    rows = _run(graph, "evidence/insert_observation", observation.model_dump(), write=True)
    if not rows:
        raise ValueError(f"Unknown asset {observation.asset_id!r} for observation {observation.id}")
    return int(rows[0]["revision"])


def latest_observation(graph: Graph, asset_id: str, prop: str) -> Row | None:
    """Most recent observation of `prop` on `asset_id`, or None if never observed."""
    return _one(
        _run(
            graph,
            "evidence/latest_observation",
            {"asset_id": asset_id, "property": prop},
            write=False,
        )
    )


def inspection_points_for(graph: Graph, asset_id: str, prop: str) -> list[Row]:
    """Inspection points (with location and coordinates) that can observe `prop` on `asset_id`."""
    params = {"asset_id": asset_id, "property": prop}
    return _run(graph, "evidence/inspection_points_for", params, write=False)


def stale_evidence(
    graph: Graph, now: float, windows: dict[str, float], default_window: float
) -> list[Row]:
    """Decision-relevant (asset, property) pairs that are missing or older than their window."""
    params = {"now": now, "windows": windows, "default_window": default_window}
    return _run(graph, "evidence/stale_evidence", params, write=False)


# --- actions --------------------------------------------------------------------
def action_prerequisites(graph: Graph, action_id: str) -> list[Row]:
    """Conditions an action requires, with the asset each is on."""
    return _run(graph, "actions/action_prerequisites", {"action_id": action_id}, write=False)


def action_effects(graph: Graph, action_id: str) -> list[Row]:
    """Declared effects (asset, property, value) of an action."""
    return _run(graph, "actions/action_effects", {"action_id": action_id}, write=False)


def create_attempt(
    graph: Graph,
    attempt_id: str,
    action_id: str,
    incident_id: str,
    asset_id: str,
    prop: str,
    expected: Any,
    sent_at: float,
) -> None:
    """Record that a command was sent (status 'sent')."""
    params = {
        "id": attempt_id,
        "action_id": action_id,
        "incident_id": incident_id,
        "asset_id": asset_id,
        "property": prop,
        "expected": expected,
        "sent_at": sent_at,
    }
    if not _run(graph, "actions/create_attempt", params, write=True):
        raise ValueError(f"Unknown action {action_id!r} or incident {incident_id!r}")


def update_attempt(graph: Graph, attempt_id: str, status: str, ack_at: float) -> None:
    """Record the command acknowledgement ('acked' or 'rejected')."""
    _run(
        graph,
        "actions/update_attempt",
        {"id": attempt_id, "status": status, "ack_at": ack_at},
        write=True,
    )


def verify_attempt(graph: Graph, attempt_id: str, observation_id: str, status: str) -> None:
    """Link an attempt to the observation that verified ('verified') or refuted ('failed') it."""
    params = {"id": attempt_id, "observation_id": observation_id, "status": status}
    _run(graph, "actions/verify_attempt", params, write=True)


# --- robot ----------------------------------------------------------------------
def robot_location(graph: Graph, robot_id: str) -> Row | None:
    """Current verified Location of the robot."""
    return _one(_run(graph, "robot/robot_location", {"robot_id": robot_id}, write=False))


def set_robot_location(graph: Graph, robot_id: str, location_id: str, now: float) -> None:
    """Move the robot's AT edge. Call only after verified arrival."""
    params = {"robot_id": robot_id, "location_id": location_id, "now": now}
    if not _run(graph, "robot/set_robot_location", params, write=True):
        raise ValueError(f"Unknown robot {robot_id!r} or location {location_id!r}")


def inspection_targets(graph: Graph, robot_id: str, ip_id: str) -> list[Row]:
    """(asset, property) readable at `ip_id`; empty unless the robot is AT its location."""
    return _run(
        graph, "robot/inspection_targets", {"robot_id": robot_id, "ip_id": ip_id}, write=False
    )


def route_to_inspection_point(graph: Graph, robot_id: str, inspection_point_id: str) -> Row | None:
    """Cheapest ADJACENT_TO route (algo.SPpaths): {locations, waypoints, cost}; None if unreachable."""
    params = {"robot_id": robot_id, "ip_id": inspection_point_id}
    return _one(_run(graph, "robot/route_to_inspection_point", params, write=False))


# --- impact ---------------------------------------------------------------------
def affected_assets(graph: Graph, asset_id: str) -> list[Row]:
    """Assets downstream of `asset_id` along FEEDS, with hop distance."""
    return _run(graph, "impact/affected_assets", {"asset_id": asset_id}, write=False)


def upstream_assets(graph: Graph, asset_id: str) -> list[Row]:
    """Assets `asset_id` depends on upstream along FEEDS, nearest first."""
    return _run(graph, "impact/upstream_assets", {"asset_id": asset_id}, write=False)


def alternate_supplies(
    graph: Graph, asset_id: str, exclude_supply_id: str | None = None
) -> list[Row]:
    """Supplies with a FEEDS path to `asset_id` (+ valves on the path). Reachability, not sufficiency."""
    params = {"asset_id": asset_id, "exclude_supply_id": exclude_supply_id}
    return _run(graph, "impact/alternate_supplies", params, write=False)


def critical_services_affected(graph: Graph, asset_id: str) -> list[Row]:
    """Critical services provided by machines downstream of `asset_id`."""
    return _run(graph, "impact/critical_services_affected", {"asset_id": asset_id}, write=False)


def downstream_machines(graph: Graph, asset_id: str) -> list[Row]:
    """Machines fed by `asset_id`, with demand and criticality."""
    return _run(graph, "impact/downstream_machines", {"asset_id": asset_id}, write=False)


# --- hypotheses -----------------------------------------------------------------
def instantiate_hypotheses(graph: Graph, incident_id: str) -> int:
    """Create the incident's open Hypotheses from the scenario's templates; return how many."""
    rows = _run(
        graph, "hypotheses/instantiate_hypotheses", {"incident_id": incident_id}, write=True
    )
    return int(rows[0]["n"]) if rows else 0


def open_hypotheses(graph: Graph, incident_id: str) -> list[Row]:
    """Open hypotheses with supporting / contradicting observation counts."""
    return _run(graph, "hypotheses/open_hypotheses", {"incident_id": incident_id}, write=False)


def distinguishing_inspections(graph: Graph, incident_id: str) -> list[Row]:
    """Inspection points that discriminate between open hypotheses, most discriminating first."""
    params = {"incident_id": incident_id}
    return _run(graph, "hypotheses/distinguishing_inspections", params, write=False)


def hypothesis_expectations(graph: Graph, incident_id: str, asset_id: str, prop: str) -> list[Row]:
    """Open hypotheses that predict a value for (asset, property): {hypothesis_id, op, value}."""
    params = {"incident_id": incident_id, "asset_id": asset_id, "property": prop}
    return _run(graph, "hypotheses/hypothesis_expectations", params, write=False)


def record_hypothesis_evidence(
    graph: Graph, observation_id: str, hypothesis_id: str, supports: bool, rule: str
) -> str:
    """Create SUPPORTS or CONTRADICTS (contradicted -> 'rejected'); return the hypothesis status."""
    params = {
        "observation_id": observation_id,
        "hypothesis_id": hypothesis_id,
        "supports": supports,
        "rule": rule,
    }
    rows = _run(graph, "hypotheses/record_hypothesis_evidence", params, write=True)
    return rows[0]["status"] if rows else "unknown"


# --- provenance -----------------------------------------------------------------
def open_incident(graph: Graph, incident_id: str, asset_id: str, now: float) -> str:
    """Create an Incident concerning the alarming asset; return its id."""
    params = {"id": incident_id, "asset_id": asset_id, "now": now}
    rows = _run(graph, "provenance/open_incident", params, write=True)
    if not rows:
        raise ValueError(f"Unknown asset {asset_id!r}")
    return rows[0]["id"]


def create_decision(graph: Graph, decision: Any) -> str:
    """Persist a Decision with CONSIDERED/REJECTED/SELECTED/BASED_ON edges (Milestone 4)."""
    return _run(graph, "provenance/create_decision", decision, write=True)[0]["id"]


def decision_trace(graph: Graph, decision_id: str) -> list[Row]:
    """Full provenance trace of a Decision (Milestone 4)."""
    return _run(graph, "provenance/decision_trace", {"decision_id": decision_id}, write=False)


def action_catalog(graph: Graph) -> list[Row]:
    return _run(graph, "actions/catalog", write=False)


def decision_context(graph: Graph) -> Row:
    return _run(graph, "provenance/context", write=False)[0]


def scene(graph: Graph, now: float | None = None) -> dict:
    from ripple.evidence.freshness import is_fresh

    evidence = _run(graph, "ui/evidence", write=False)
    if now is not None:
        for observation in evidence:
            observation["fresh"] = is_fresh(
                observation["property"], observation["observed_at"], now
            )
    return {
        "nodes": _run(graph, "ui/nodes", write=False),
        "edges": _run(graph, "ui/edges", write=False),
        "evidence": evidence,
    }
