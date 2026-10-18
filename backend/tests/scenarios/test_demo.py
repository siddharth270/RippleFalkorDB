import pytest
from fastapi.testclient import TestClient

from ripple.graph import repository
from ripple.graph.branching import snapshot
from ripple.graph.seed import seed_from_scenario
from ripple.planning.evaluator import evaluate_plan
from ripple.scenario import SCENARIOS_DIR
from ripple.simulator.runtime import run_scenario


@pytest.mark.integration
def test_branches_cleanup_on_exception_and_never_pollute_live(graph, db):
    seed_from_scenario(graph, SCENARIOS_DIR / "healthy_8.yaml")
    before = set(db.list_graphs())
    with pytest.raises(RuntimeError):
        with snapshot(graph) as branch:
            assert branch.name != graph.name
            raise RuntimeError("injected branch failure")
    assert set(db.list_graphs()) == before
    ev = evaluate_plan(graph, ["activate_standby", "open_bypass", "isolate_primary"], 1000)
    assert ev.missing
    assert set(db.list_graphs()) == before
    assert graph.ro_query(
        "MATCH (o:Observation {source:'predicted'}) RETURN count(o)"
    ).result_set == [[0]]


@pytest.mark.integration
@pytest.mark.parametrize(
    "scenario,plan,recovered",
    [
        ("healthy_8", "restore_via_standby", True),
        ("healthy_5", "reduce_load_then_restore", True),
        ("standby_down", "shed_noncritical_load", False),
        ("stale_valve", "restore_via_standby", True),
        ("stuck_valve", "restore_via_standby", False),
        ("new_load", "reduce_load_then_restore", True),
    ],
)
def test_demo_outcomes_and_persisted_provenance(graph, scenario, plan, recovered):
    data = run_scenario(scenario, graph_name=graph.name)
    result = data["result"]
    assert result["chosen_plan"] == plan
    assert result["recovered"] is recovered
    trace = repository.decision_trace(graph, result["decision_id"])[0]
    assert [p["plan"] for p in trace["plans"] if p["selected"]] == [plan]
    assert all(o["source"] != "predicted" for o in trace["evidence"])
    assert any(e["type"] == "move" for e in data["events"])
    if scenario == "stale_valve":
        assert any(o.get("fresh") is False for o in data["events"][0]["scene"]["evidence"])
    if scenario == "new_load":
        assert result["service"]["required"] == 6
        assert result["impact"]["shared_with"] == ["machine_b", "machine_c"]
    if scenario == "stuck_valve":
        assert data["metrics"]["verification_failures"] == 1


@pytest.mark.integration
def test_api_run_websocket_and_validation():
    from ripple.api.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/runs", json={"scenario": "../../etc/passwd"}).status_code == 422
        started = client.post("/api/runs", json={"scenario": "healthy_5", "paced": False})
        assert started.status_code == 202
        run_id = started.json()["id"]
        with client.websocket_connect("/api/stream/" + run_id) as stream:
            while True:
                packet = stream.receive_json()
                if packet["kind"] == "finished":
                    break
        assert packet["run"]["status"] == "done"
        assert packet["run"]["result"]["recovered"]
        from ripple.graph.client import get_db

        get_db().select_graph(packet["run"]["graph"]).delete()


def test_branch_copy_retries_only_transient_fork_contention(monkeypatch):
    from unittest.mock import Mock

    from redis.exceptions import ResponseError

    monkeypatch.setattr("ripple.graph.branching.time.sleep", lambda _: None)
    source, branch = Mock(), Mock()
    source.name = "test"
    source.copy.side_effect = [ResponseError("could not fork"), branch]
    with snapshot(source) as copied:
        assert copied is branch
    assert source.copy.call_count == 2
    branch.delete.assert_called_once()
    source.copy.reset_mock()
    source.copy.side_effect = ResponseError("permission denied")
    with pytest.raises(ResponseError, match="permission denied"):
        with snapshot(source):
            pass
    assert source.copy.call_count == 1
