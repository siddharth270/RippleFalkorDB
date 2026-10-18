"""The core loop: observe -> update evidence -> query dependencies -> identify uncertainty ->
inspect -> evaluate plans -> validate -> execute -> verify.

Simulation implementation:
- Dependencies, prerequisites, capacity topology, inspection points, routes, hypotheses and
  effects all come from graph queries (repository).
- Candidate plans are generated from graph actions and evaluated in GRAPH.COPY branches.
- Decision-driven inspection: the robot inspects only while a more-preferred plan is still
  undecided, and picks the inspection point with the best decision relevance score.
- Sensing and actuation are injected callables, so this module never touches the simulator's
  hidden truth (invariant #2).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from falkordb import Graph

from ripple.agent.explanations import explain
from ripple.evidence.beliefs import belief, compare
from ripple.evidence.freshness import DEFAULT_WINDOW_S, FRESHNESS_WINDOWS_S
from ripple.evidence.hypotheses import classify
from ripple.evidence.models import Observation
from ripple.graph import repository
from ripple.planning.candidates import generate_candidates
from ripple.planning.evaluator import evaluate_plan
from ripple.planning.inspection_ranker import rank_inspections
from ripple.planning.validator import ValidationResult, check_action
from ripple.robot.base import Pose, RobotAdapter, arrived

MAX_DIAGNOSIS_ROUNDS = 6
MAX_RECHECK_ROUNDS = 3
MOVE_RETRIES = 2

Sense = Callable[[str], list[Observation]]  # inspection_point_id -> observations
Actuate = Callable[[str, str, Any], dict[str, Any]]  # (asset_id, property, value) -> ack


class RobotMoveFailed(Exception):
    """The robot did not verifiably arrive (after retries), or the target is unreachable."""


@dataclass
class IncidentResult:
    incident_id: str
    chosen_plan: str | None = None
    rejected: dict[str, list[str]] = field(default_factory=dict)  # plan -> reasons
    impact: dict[str, Any] = field(default_factory=dict)
    stale_at_start: list[dict[str, Any]] = field(default_factory=list)
    inspections: list[dict[str, Any]] = field(default_factory=list)  # {ip_id, purpose, travel_cost}
    rankings: list[list[dict[str, Any]]] = field(default_factory=list)  # per diagnosis round
    attempts: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    service: dict[str, Any] = field(default_factory=dict)
    travel_cost: float = 0.0
    recovered: bool = False
    decision_id: str | None = None
    explanation: str = ""
    evaluations: list[dict] = field(default_factory=list)

    def inspected(self, purpose: str | None = None) -> list[str]:
        return [i["ip_id"] for i in self.inspections if purpose is None or i["purpose"] == purpose]


class Orchestrator:
    def __init__(
        self,
        graph: Graph,
        robot: RobotAdapter,
        sense: Sense,
        actuate: Actuate,
        clock: Callable[[], float],
        robot_id: str = "robot_1",
        on_event: Callable | None = None,
        mode: str = "full_ripple",
    ) -> None:
        self.graph = graph
        self.robot = robot
        self.sense = sense
        self.actuate = actuate
        self.clock = clock
        self.robot_id = robot_id
        self.on_event = on_event or (lambda event: None)
        self.mode = mode
        self.plans = {}

    def run_incident(self, trigger_asset_id: str) -> IncidentResult:
        """Handle an alarm on `trigger_asset_id`; return what was traced, inspected, chosen, verified."""
        result = IncidentResult(incident_id=f"inc_{uuid4().hex[:8]}")
        repository.open_incident(self.graph, result.incident_id, trigger_asset_id, self.clock())
        repository.instantiate_hypotheses(self.graph, result.incident_id)
        result.impact = self._trace_dependencies(trigger_asset_id)
        result.stale_at_start = repository.stale_evidence(
            self.graph, self.clock(), FRESHNESS_WINDOWS_S, DEFAULT_WINDOW_S
        )

        self.plans = generate_candidates(self.graph, trigger_asset_id)
        self.on_event({"type": "impact", "impact": result.impact, "stale": result.stale_at_start})
        plan = self._choose_plan(result)
        self._record_decision(result, plan)
        result.chosen_plan = plan
        if plan is not None:
            executed = self._execute(self.plans[plan], result)
            served = self._verify_service(result)
            result.recovered = executed and served
        result.hypotheses = repository.open_hypotheses(self.graph, result.incident_id)
        self.on_event(
            {"type": "complete", "recovered": result.recovered, "service": result.service}
        )
        return result

    def _record_decision(self, result, selected):
        context = repository.decision_context(self.graph)
        result.decision_id = f"decision_{uuid4().hex}"
        repository.create_decision(
            self.graph,
            {
                "id": result.decision_id,
                "incident_id": result.incident_id,
                "made_at": self.clock(),
                "revision": context["revision"],
                "summary": "Selected " + selected
                if selected
                else "No feasible plan with available evidence.",
                "observation_ids": context["observation_ids"],
                "plans": [
                    {
                        "name": name,
                        "actions": actions,
                        "selected": name == selected,
                        "rejected_reason": "; ".join(result.rejected[name])
                        if name in result.rejected and name != selected
                        else None,
                    }
                    for name, actions in self.plans.items()
                ],
            },
        )
        result.explanation = explain(repository.decision_trace(self.graph, result.decision_id))
        self.on_event(
            {"type": "decision", "chosen_plan": selected, "explanation": result.explanation}
        )

    # --- dependencies (M2) --------------------------------------------------------
    def _trace_dependencies(self, trigger: str) -> dict[str, Any]:
        """Multi-hop: which supplies feed the alarming machine, who else shares them, what's critical."""
        upstream = repository.upstream_assets(self.graph, trigger)
        supplies = repository.alternate_supplies(self.graph, trigger)
        shared, critical = set(), set()
        for s in supplies:
            shared |= {
                m["machine_id"] for m in repository.downstream_machines(self.graph, s["supply_id"])
            }
            critical |= {
                c["service_id"]
                for c in repository.critical_services_affected(self.graph, s["supply_id"])
            }
        header = next((u["asset_id"] for u in upstream if "Header" in u["labels"]), None)
        return {
            "upstream": [u["asset_id"] for u in upstream],
            "supplies": [s["supply_id"] for s in supplies],
            "header": header,
            "shared_with": sorted(shared - {trigger}),
            "critical_services": sorted(critical),
        }

    # --- decision-driven inspection (M3) ------------------------------------------
    def _choose_plan(self, result: IncidentResult) -> str | None:
        """Pick the most-preferred feasible plan, inspecting only what could change that choice."""
        unobtainable: set[str] = set()
        for _ in range(MAX_DIAGNOSIS_ROUNDS):
            evaluations = {
                name: evaluate_plan(self.graph, actions, self.clock())
                for name, actions in self.plans.items()
                if name not in unobtainable
            }
            rows = [
                {
                    "name": name,
                    "actions": self.plans[name],
                    "status": "rejected"
                    if ev.rejected
                    else "feasible"
                    if ev.ok
                    else "needs evidence",
                    "reasons": ev.reasons,
                }
                for name, ev in evaluations.items()
            ]
            result.evaluations = rows
            self.on_event({"type": "branches", "plans": rows})
            undecided: dict[str, ValidationResult] = {}
            for name, ev in evaluations.items():
                if ev.rejected:
                    result.rejected[name] = ev.violations
                elif ev.ok:
                    if not undecided:
                        return name
                    break  # a fallback exists, but a preferred plan is still undecided
                else:
                    undecided[name] = ev
            if not undecided:
                return None

            if self.mode == "graph_no_inspection":
                for name, ev in undecided.items():
                    result.rejected[name] = ["inspection disabled: " + "; ".join(ev.notes)]
                    unobtainable.add(name)
                continue
            ranked = rank_inspections(
                self.graph,
                self.robot_id,
                result.incident_id,
                {name: ev.missing for name, ev in undecided.items()},
            )
            result.rankings.append([c.summary() for c in ranked])
            self.on_event({"type": "inspection_ranking", "ranking": result.rankings[-1]})
            if not ranked or ranked[0].blocks == 0:
                # No reachable inspection can resolve the undecided plans: give up on them.
                for name, ev in undecided.items():
                    result.rejected[name] = ["evidence unobtainable: " + "; ".join(ev.notes)]
                    unobtainable.add(name)
                continue
            self._inspect_at(ranked[0].ip_id, "diagnosis", result)
        return None

    def _inspect_at(self, ip_id: str, purpose: str, result: IncidentResult) -> list[Observation]:
        """Route to an inspection point, sense, record evidence (and hypothesis links when diagnosing)."""
        travel = self._go_to(ip_id)
        observations = self.sense(ip_id)
        for obs in observations:
            obs.incident_id = result.incident_id
            repository.insert_observation(self.graph, obs)
            if purpose == "diagnosis":
                self._link_hypotheses(obs, result)
        result.inspections.append({"ip_id": ip_id, "purpose": purpose, "travel_cost": travel})
        result.travel_cost += travel
        self.on_event(
            {
                "type": "inspection",
                "ip_id": ip_id,
                "purpose": purpose,
                "observations": [o.model_dump() for o in observations],
            }
        )
        return observations

    def _inspect_item(
        self, asset_id: str, prop: str, purpose: str, result: IncidentResult
    ) -> list[Observation]:
        """Inspect (asset, property) at the cheapest reachable inspection point covering it."""
        best, best_cost = None, float("inf")
        for ip in repository.inspection_points_for(self.graph, asset_id, prop):
            route = repository.route_to_inspection_point(self.graph, self.robot_id, ip["ip_id"])
            if route is not None and route["cost"] < best_cost:
                best, best_cost = ip["ip_id"], route["cost"]
        if best is None:
            return []
        return self._inspect_at(best, purpose, result)

    def _link_hypotheses(self, obs: Observation, result: IncidentResult) -> None:
        for exp in repository.hypothesis_expectations(
            self.graph, result.incident_id, obs.asset_id, obs.property
        ):
            relation, rule = classify(obs, exp)
            repository.record_hypothesis_evidence(
                self.graph, obs.id, exp["hypothesis_id"], relation == "SUPPORTS", rule
            )

    def _go_to(self, ip_id: str) -> float:
        """Follow the cheapest ADJACENT_TO route hop by hop; move AT only after verified arrival (DP4)."""
        route = repository.route_to_inspection_point(self.graph, self.robot_id, ip_id)
        if route is None:
            raise RobotMoveFailed(f"{ip_id} is unreachable from {self.robot_id}")
        for location_id, (x, y) in zip(route["locations"][1:], route["waypoints"][1:], strict=True):
            target = Pose(x, y)
            for _ in range(MOVE_RETRIES):
                self.robot.move_to(target)
                if arrived(self.robot.current_pose(), target):
                    repository.set_robot_location(
                        self.graph, self.robot_id, location_id, self.clock()
                    )
                    self.on_event({"type": "move", "location_id": location_id, "x": x, "y": y})
                    break
            else:
                raise RobotMoveFailed(f"{self.robot_id} did not reach {location_id}")
        return float(route["cost"])

    # --- execution + verification -------------------------------------------------
    def _recheck(self, action_id: str, result: IncidentResult) -> ValidationResult:
        """Invariant #4: re-validate against real evidence right before acting; inspect what's missing."""
        check = check_action(self.graph, action_id, self.clock())
        for _ in range(MAX_RECHECK_ROUNDS):
            if check.ok or check.rejected or not check.missing:
                return check
            for asset_id, prop in check.missing:
                self._inspect_item(asset_id, prop, "recheck", result)
            check = check_action(self.graph, action_id, self.clock())
        return check

    def _execute(self, actions: list[str], result: IncidentResult) -> bool:
        for action_id in actions:
            check = self._recheck(action_id, result)
            if not check.ok:
                result.attempts.append(
                    {"action": action_id, "status": "rejected", "reasons": check.reasons}
                )
                return False
            for effect in repository.action_effects(self.graph, action_id):
                if not self._attempt(action_id, effect, result):
                    return False
        return True

    def _attempt(self, action_id: str, effect: dict[str, Any], result: IncidentResult) -> bool:
        asset_id, prop, expected = effect["asset_id"], effect["property"], effect["value"]
        attempt_id = f"att_{uuid4().hex[:8]}"
        repository.create_attempt(
            self.graph,
            attempt_id,
            action_id,
            result.incident_id,
            asset_id,
            prop,
            expected,
            self.clock(),
        )
        ack = self.actuate(asset_id, prop, expected)
        status = "acked" if ack["accepted"] else "rejected"
        repository.update_attempt(self.graph, attempt_id, status, ack["acked_at"])

        observed = [
            o
            for o in self._inspect_item(asset_id, prop, "verification", result)
            if o.asset_id == asset_id and o.property == prop
        ]
        status = "unverified"
        if observed:
            status = "verified" if compare("=", observed[0].value, expected) else "failed"
            repository.verify_attempt(self.graph, attempt_id, observed[0].id, status)
        result.attempts.append(
            {
                "action": action_id,
                "asset": asset_id,
                "property": prop,
                "expected": expected,
                "status": status,
            }
        )
        self.on_event({"type": "verification", **result.attempts[-1]})
        return ack["accepted"] and status == "verified"

    def _verify_service(self, result: IncidentResult) -> bool:
        """Operational check (invariant #3): observed header flow must cover running machines' demand."""
        header = result.impact.get("header")
        if header is None:
            return False
        flows = [
            o for o in self._inspect_item(header, "flow", "service", result) if o.property == "flow"
        ]
        required, now = 0.0, self.clock()
        for m in repository.downstream_machines(self.graph, header):
            running = belief(self.graph, m["machine_id"], "running", now)
            if not running.usable or running.value is True:
                required += float(m["demand"])
        flow = float(flows[0].value) if flows else None
        result.service = {"header": header, "flow": flow, "required": required}
        return flow is not None and flow >= required
