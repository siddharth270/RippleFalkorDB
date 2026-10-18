"""Demo composition root. Hidden truth stays inside simulator; UI sees graph evidence only."""

import time
from dataclasses import asdict
from uuid import uuid4

from ripple.agent.orchestrator import Orchestrator
from ripple.config import get_settings
from ripple.graph import repository
from ripple.graph.client import get_db
from ripple.graph.seed import seed_from_scenario
from ripple.robot.base import Pose, arrived
from ripple.robot.mock_adapter import MockRobotAdapter
from ripple.scenario import SCENARIOS_DIR, load_scenario
from ripple.simulator import controls, sensors
from ripple.simulator.ground_truth import GroundTruth

SCENARIOS = ("healthy_8", "healthy_5", "standby_down", "stale_valve", "stuck_valve", "new_load")
MODES = ("full_ripple", "graph_no_inspection", "local_baseline")


def run_scenario(
    name, *, mode="full_ripple", adapter="mock", emit=None, delay=0.0, graph_name=None
):
    if name not in SCENARIOS or mode not in MODES or adapter not in ("mock", "cyberwave"):
        raise ValueError("Unsupported scenario, mode, or adapter")
    graph = get_db().select_graph(graph_name or f"ripple_demo_{uuid4().hex[:12]}")
    path = SCENARIOS_DIR / f"{name}.yaml"
    seed_from_scenario(graph, path)
    truth = GroundTruth.from_scenario(path)
    client = None
    if adapter == "cyberwave":
        from cyberwave import Cyberwave

        from ripple.robot.cyberwave_adapter import CyberwaveRobotAdapter

        settings = get_settings()
        if not all(
            (
                settings.cyberwave_api_key,
                settings.cyberwave_environment_id,
                settings.cyberwave_twin_id,
            )
        ):
            raise ValueError(
                "Cyberwave API key, environment ID and twin ID must be set in backend/.env"
            )
        client = Cyberwave(
            api_key=settings.cyberwave_api_key,
            workspace_id=settings.cyberwave_workspace_id,
            environment_id=settings.cyberwave_environment_id,
        )
        robot = CyberwaveRobotAdapter(
            client, settings.cyberwave_twin_id, settings.cyberwave_environment_id
        )
        robot.move_to(Pose(0, 0))
        if not arrived(robot.current_pose(), Pose(0, 0)):
            client.disconnect()
            raise RuntimeError("Cyberwave starting pose could not be verified")
    else:
        robot = MockRobotAdapter(start=Pose(0, 0))
    logical_time = 1000.0
    events = []

    def event(data):
        nonlocal logical_time
        logical_time += 1.0
        row = {
            "index": len(events),
            "time": logical_time,
            **data,
            "scene": repository.scene(graph, now=logical_time),
        }
        events.append(row)
        if emit:
            emit(row)
        if delay:
            time.sleep(delay)

    def clock():
        return logical_time

    started = time.perf_counter()
    try:
        event({"type": "started", "scenario": name, "adapter": adapter, "mode": mode})
        agent = Orchestrator(
            graph,
            robot,
            sense=lambda ip: sensors.read(graph, truth, "robot_1", ip, clock()),
            actuate=lambda asset, prop, value: controls.apply_effect(
                truth, asset, prop, value, clock()
            ),
            clock=clock,
            on_event=event,
            mode=mode,
        )
        if mode == "local_baseline":
            # Explicit reactive comparison: blindly isolates the primary branch.
            # Use the same execution/observation plumbing, bypassing planner checks only.
            from ripple.agent.orchestrator import IncidentResult

            result = IncidentResult(
                incident_id=f"inc_{uuid4().hex[:8]}", chosen_plan="isolate_primary_now"
            )
            repository.open_incident(graph, result.incident_id, "machine_a", clock())
            result.impact = agent._trace_dependencies("machine_a")
            action = next(
                a
                for a in repository.action_catalog(graph)
                if a["property"] == "position" and a["value"] == "closed"
            )
            event(
                {
                    "type": "baseline",
                    "message": "Reactive baseline: isolate primary without dependency checks",
                }
            )
            agent._attempt(action["action_id"], action, result)
            result.recovered = agent._verify_service(result)
            event({"type": "complete", "recovered": result.recovered, "service": result.service})
        else:
            result = agent.run_incident("machine_a")
        return {
            "scenario": name,
            "mode": mode,
            "adapter": adapter,
            "graph": graph.name,
            "result": asdict(result),
            "events": events,
            "metrics": {
                "wall_time_s": round(time.perf_counter() - started, 3),
                "inspection_count": len(result.inspections),
                "travel_cost": result.travel_cost,
                "recovered": result.recovered,
                "verification_failures": sum(a["status"] == "failed" for a in result.attempts),
            },
        }
    finally:
        if client:
            client.disconnect()


def scenario_catalog():
    return [
        {"id": name, "description": load_scenario(SCENARIOS_DIR / f"{name}.yaml")["description"]}
        for name in SCENARIOS
    ]
