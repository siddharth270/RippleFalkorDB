"""Idempotent setup in an explicitly chosen Cyberwave environment; never starts billing."""

import argparse
import json

from cyberwave import Cyberwave
from dotenv import load_dotenv, set_key

from ripple.graph import repository
from ripple.graph.client import get_db
from ripple.graph.seed import seed_from_scenario
from ripple.scenario import SCENARIOS_DIR

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment", required=True, help="Exact environment UUID or unified slug"
    )
    args = parser.parse_args()
    load_dotenv(".env")
    cw = Cyberwave()
    try:
        env = cw.environments.get(args.environment)
        env_id = str(env.uuid)
        cw.config.environment_id = env_id
        assets = cw.assets.list()
        go2 = next(a for a in assets if a.registry_id == "unitree/go2")
        cube = next((a for a in assets if a.registry_id == "cyberwave/generic_cube"), None)
        twins = {t.name: t for t in cw.twins.list(environment_id=env_id)}
        name = "Ripple Inspector"
        twin = twins.get(name)
        if twin is None:
            twin = cw.twins.create(
                str(go2.uuid),
                env_id,
                name=name,
                description="Ripple inspection twin. Verified repositioning, not walking.",
                position_x=0,
                position_y=0,
                position_z=0,
            )
        set_key(".env", "CYBERWAVE_ENVIRONMENT_ID", env_id)
        set_key(".env", "CYBERWAVE_WORKSPACE_ID", str(env.workspace_uuid))
        set_key(".env", "CYBERWAVE_TWIN_ID", str(twin.uuid))
        # Seed a dedicated visualization graph; scene placement reads graph facts.
        graph = get_db().select_graph("ripple_cyberwave_layout")
        seed_from_scenario(graph, SCENARIOS_DIR / "healthy_8.yaml")
        scene = repository.scene(graph)
        locs = {n["id"]: n["properties"] for n in scene["nodes"] if "Location" in n["labels"]}
        used = {}
        equipment = []
        if cube:
            for n in scene["nodes"]:
                if "Asset" not in n["labels"]:
                    continue
                loc = next(
                    e["target"]
                    for e in scene["edges"]
                    if e["type"] == "LOCATED_IN" and e["source"] == n["id"]
                )
                idx = used.get(loc, 0)
                used[loc] = idx + 1
                pos = locs[loc]
                title = "Ripple · " + n["properties"]["name"]
                t = twins.get(title)
                if t is None:
                    t = cw.twins.create(
                        str(cube.uuid),
                        env_id,
                        name=title,
                        description="Synthetic Ripple equipment marker; operational state comes from FalkorDB.",
                        position_x=float(pos["x"]) + (idx - 0.5) * 1.0,
                        position_y=float(pos["y"]) + 0.8,
                        position_z=0,
                        scale_x=0.6,
                        scale_y=0.6,
                        scale_z=1.0,
                        fixed_base=True,
                    )
                equipment.append(str(t.uuid))
        print(
            json.dumps(
                {
                    "environment": env_id,
                    "url": "https://cyberwave.com/" + env.slug,
                    "twin": str(twin.uuid),
                    "equipment_markers": len(equipment),
                    "mode": "editor twin repositioning; no billable simulation started",
                },
                indent=2,
            )
        )
    finally:
        cw.disconnect()
