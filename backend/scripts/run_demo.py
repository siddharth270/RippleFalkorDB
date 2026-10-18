"""Run a reproducible simulation and export the actual evidence trace."""

import argparse
import json
from pathlib import Path

from ripple.simulator.runtime import run_scenario

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("scenario", nargs="?", default="healthy_5")
    p.add_argument("--adapter", choices=["mock", "cyberwave"], default="mock")
    p.add_argument("--output", default="../eval/results/demo.json")
    args = p.parse_args()
    data = run_scenario(args.scenario, adapter=args.adapter)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2))
    print(
        json.dumps(
            {
                "graph": data["graph"],
                "metrics": data["metrics"],
                "chosen_plan": data["result"]["chosen_plan"],
                "output": str(output),
            },
            indent=2,
        )
    )
