# Submission guide

## Source code

Intended team repository: https://github.com/siddharth270/RippleFalkorDB

The submitted branch must include the current M4/M5 implementation and these documents. A local working tree is not a published submission. Verify the repository is publicly readable in a signed-out browser after pushing the submission commit. GitHub publication and visibility must be confirmed separately from successful local validation.

## Setup and data model

The root [README](../README.md) contains the clone/start commands, graph diagram, scenario outcomes and optional Cyberwave setup. [Local setup](local-setup.md) adds prerequisites, troubleshooting, database inspection and shutdown instructions. [Graph model](graph-model.md) describes the implemented labels, properties, relationships, evidence semantics, decisions and indexes.

## Queries and algorithms

[Query catalog](queries.md) links every Cypher file and explains the graph operations the product depends on. The query source is in `backend/ripple/graph/queries/`. FalkorDB multi-hop traversal, `algo.SPpaths` and `GRAPH.COPY` are used in the running product; capacity and inspection relevance are application algorithms over their results.

## Deployment/reproduction route

Submit the complete local setup route. There is no public hosted Ripple application. `localhost` addresses are local endpoints, and the team's authenticated Cyberwave environment is not a public deployment of the whole system. The mock adapter allows judges to run all six scenarios without API keys.

## Recommended judge walkthrough

1. Clone and start the services using the README.
2. Run Limited standby · 5 units / Local simulated inspector / Full Ripple.
3. Inspect Dependencies, rejected plans, recorded decision and the verified 5/4 result.
4. Run Stuck bypass valve: expect no recovery and one failed verification.
5. Compare Standby ready · 8 units (direct restoration, 8/7) against New critical load · 9 units (load shedding then restoration, 8/6).
6. Run `uv run pytest -q` and `uv run python -m scripts.evaluate` from backend with FalkorDB running.
7. Optionally connect a Cyberwave environment using the setup script. Position updates are independently checked; sensor values remain synthetic.

## Evidence and video

The evaluation runner regenerates `eval/results/evaluation.json`; CLI runs and the dashboard export full traces. Generated results are intentionally gitignored. The [demo narration](demo-script.md) describes the demonstration and limitations. The final edited video is prepared separately from this repository submission; add its actual share URL in the submission form when ready.

## Active implementation versus retained scaffolding

The working API is `backend/ripple/api/main.py`; the working dashboard is `frontend/src/App.tsx`; the working evaluator is `backend/scripts/evaluate.py` (run as `python -m scripts.evaluate` from backend). Earlier placeholders remain in `backend/ripple/api/routes/`, `frontend/src/components/`, `frontend/src/api/client.ts`, and `eval/run_eval.py`; these are not the demo entry points. `backend/ripple/agent/tools.py` and `mcp_server.py` are unfinished optional LLM/MCP scaffolding and are outside the demonstrated deterministic runtime.

## Validation on 18 October 2026

The full backend suite passed: **44 tests**. The frontend production build passed with Vite 6.4.4. All local links in the README and submission/setup/model/query documents resolved. The query catalog covers all **33 Cypher files**. These checks validate the local implementation; repository publication and deployment status are separate concerns.
