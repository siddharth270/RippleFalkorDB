"""Evaluate sequences in real FalkorDB snapshots; no live-state predictions."""

from uuid import uuid4

from ripple.evidence.models import Observation
from ripple.graph import repository
from ripple.graph.branching import snapshot
from ripple.planning.validator import ValidationResult, check_action


def evaluate_plan(graph, actions, now):
    result = ValidationResult()
    with snapshot(graph) as branch:
        for i, action in enumerate(actions):
            check = check_action(branch, action, now + i * 0.001)
            result.merge(check, prefix=f"{action} -> ")
            if check.rejected:
                break
            # Conditional projection: missing evidence remains missing in the result;
            # it cannot become executable merely because later effects are projected.
            for effect in repository.action_effects(branch, action):
                repository.insert_observation(
                    branch,
                    Observation(
                        id=f"prediction_{uuid4().hex}",
                        asset_id=effect["asset_id"],
                        property=effect["property"],
                        value=effect["value"],
                        source="predicted",
                        observed_at=now + (i + 1) * 0.001,
                        ingested_at=now + (i + 1) * 0.001,
                    ),
                )
    return result
