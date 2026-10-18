"""Bounded cooling-domain candidates, grounded in graph actions and supply paths.

Domain policy: consider isolation, a standby path, optional noncritical shedding,
then degraded shedding. IDs and eligible actions are discovered from the graph.
This is deliberately not a general-purpose planner.
"""

from itertools import combinations

from ripple.graph import repository


def generate_candidates(graph, trigger="machine_a", max_len=4):
    catalog = repository.action_catalog(graph)
    closes = [a for a in catalog if a["property"] == "position" and a["value"] == "closed"]
    sheds = [a for a in catalog if a["kind"] == "load" and a["value"] is False]
    plans = {}
    for close in closes:
        direct = "isolate_primary_now" if not plans else f"isolate_{close['asset_id']}"
        plans[direct] = [close["action_id"]]
        for path in repository.alternate_supplies(graph, trigger):
            if close["asset_id"] in path["valves_on_path"]:
                continue
            starters = [
                a
                for a in catalog
                if a["asset_id"] == path["supply_id"]
                and a["property"] == "running"
                and a["value"] is True
            ]
            opens = [
                a
                for a in catalog
                if a["asset_id"] in path["valves_on_path"]
                and a["property"] == "position"
                and a["value"] == "open"
            ]
            if not starters or len(opens) != len(path["valves_on_path"]):
                continue
            restore = [
                starters[0]["action_id"],
                *[a["action_id"] for a in opens],
                close["action_id"],
            ]
            if len(restore) <= max_len:
                name = (
                    "restore_via_standby"
                    if "restore_via_standby" not in plans
                    else f"restore_{path['supply_id']}"
                )
                plans[name] = restore
            for count in range(1, min(len(sheds), max_len - len(restore)) + 1):
                for group in combinations(sheds, count):
                    name = (
                        "reduce_load_then_restore"
                        if "reduce_load_then_restore" not in plans
                        else "reduce_" + "_".join(a["asset_id"] for a in group)
                    )
                    plans[name] = [*[a["action_id"] for a in group], *restore]
    if sheds:
        plans["shed_noncritical_load"] = [a["action_id"] for a in sheds][:max_len]
    return plans
