"""Three explicit policies by six scenarios; metrics are measured, not promised."""

import json
from pathlib import Path

from ripple.graph.client import get_db
from ripple.simulator.runtime import MODES, SCENARIOS, run_scenario

if __name__ == "__main__":
    rows = []
    for mode in MODES:
        for scenario in SCENARIOS:
            run = run_scenario(scenario, mode=mode)
            rows.append(
                {
                    "mode": mode,
                    "scenario": scenario,
                    "chosen_plan": run["result"]["chosen_plan"],
                    **run["metrics"],
                }
            )
            # Evaluation graphs are owned disposable runs; demo graphs remain inspectable.
            get_db().select_graph(run["graph"]).delete()
    out = Path("../eval/results/evaluation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "notes": "Synthetic discrete simulation. Wall time includes queries; no physical outage-duration metric.",
                "rows": rows,
            },
            indent=2,
        )
    )
    print(json.dumps(rows, indent=2))
