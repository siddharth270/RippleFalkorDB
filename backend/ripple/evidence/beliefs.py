"""Current belief about an asset property, derived from graph evidence (DP1).

belief = latest Observation (via repository) judged by per-property freshness. During planning,
a `predicted` overlay of declared action effects can stand in for evidence that a plan's
earlier steps will create; predicted values are always labelled as such, never as observed.
"""

from dataclasses import dataclass
from typing import Any, Literal

from falkordb import Graph

from ripple.evidence.freshness import is_fresh
from ripple.graph import repository

Status = Literal["fresh", "stale", "missing", "predicted"]
Predicted = dict[tuple[str, str], Any]  # (asset_id, property) -> predicted value


@dataclass(frozen=True)
class Belief:
    asset_id: str
    property: str
    value: Any
    status: Status
    source: str | None = None
    observed_at: float | None = None

    @property
    def usable(self) -> bool:
        """Fresh evidence or a planning prediction; stale/missing values must not drive decisions."""
        return self.status in ("fresh", "predicted")


def belief(
    graph: Graph, asset_id: str, prop: str, now: float, predicted: Predicted | None = None
) -> Belief:
    if predicted and (asset_id, prop) in predicted:
        return Belief(asset_id, prop, predicted[(asset_id, prop)], "predicted", "predicted")
    latest = repository.latest_observation(graph, asset_id, prop)
    if latest is None:
        return Belief(asset_id, prop, None, "missing")
    status: Status = (
        "predicted"
        if latest["source"] == "predicted"
        else "fresh"
        if is_fresh(prop, latest["observed_at"], now)
        else "stale"
    )
    return Belief(asset_id, prop, latest["value"], status, latest["source"], latest["observed_at"])


def compare(op: str, observed: Any, expected: Any) -> bool:
    """Evaluate `observed <op> expected`; numeric ops coerce to float."""
    if op == "=":
        if isinstance(observed, (int, float)) and isinstance(expected, (int, float)):
            return float(observed) == float(expected)
        return observed == expected
    numeric = {"<": float.__lt__, "<=": float.__le__, ">": float.__gt__, ">=": float.__ge__}
    if op not in numeric:
        raise ValueError(f"Unsupported condition op {op!r}")
    return numeric[op](float(observed), float(expected))
