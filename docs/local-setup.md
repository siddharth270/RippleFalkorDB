# Complete local reproduction

This is the submission's alternative to a public live deployment. It runs the complete graph-based decision loop locally; Cyberwave is optional. Start with the commands in the [README](../README.md).

## Prerequisites and dependency installation

Use Docker Desktop (macOS/Windows) or Docker Engine with Compose v2 (Linux), Git, uv, and Node.js 22 LTS/npm. Use WSL2 for the POSIX shell commands on Windows. First setup needs network access to clone source, pull the FalkorDB image and install packages. The mock demo does not require API credentials or a hosted service after dependencies are installed.

- Check Docker: `docker info` and `docker compose version`.
- Check Python tooling: `uv --version`. `uv sync --locked --python 3.12` can download/manage Python 3.12.
- Check JavaScript tooling: `node --version` and `npm --version`.
- `backend/uv.lock` and `frontend/package-lock.json` pin application dependency resolutions. Use `uv sync --locked` and `npm ci` rather than regenerating locks.
- The current Compose configuration uses `falkordb/falkordb:latest`; the database image is not pinned by digest. Record the image digest for any benchmark that requires identical database binaries.

Run `docker compose up -d falkordb` from the repository root. Start the backend **from backend/** so its configuration finds `backend/.env`. Start the frontend **from frontend/**. Keep both application terminals open.

## Addresses

- Dashboard: http://127.0.0.1:5173
- API health: http://127.0.0.1:8000/api/health
- Interactive API documentation: http://127.0.0.1:8000/docs
- FalkorDB Browser: http://127.0.0.1:3000
- Redis protocol for the backend: localhost:6379

Vite proxies `/api` and WebSocket traffic to port 8000. The API is not served by Vite itself. Defaults work without an environment file.

## First-run acceptance check

Select Limited standby · 5 units / Local simulated inspector / Full Ripple. Start the run. Expect the plan `reduce_load_then_restore`, recovery Verified, flow/demand 5/4, seven inspections and zero verification failures. Open Dependencies, expand rejected plans, and inspect the recorded explanation. Export the JSON trace before starting another run.

Every start uses a fresh scenario graph. You do not need to reset equipment manually. The replay slider reviews dashboard event snapshots; it does not rewind the Cyberwave twin. Refreshing the page clears its current client view, and restarting the backend clears its in-memory run index.

For failure behavior, select Stuck bypass valve and run again: recovery must be Not recovered with one verification failure. For topology change, compare Standby ready · 8 units (8/7, direct restoration) with New critical load · 9 units (8/6 after shedding B).

## Inspect the database

A CLI demo prints its generated graph name, for example `ripple_demo_<unique-id>`. In the FalkorDB Browser, select that graph. The following read-only queries use actual runtime labels:

```cypher
MATCH (a:Asset)-[r:FEEDS]->(b:Asset)
RETURN a, r, b
```

```cypher
MATCH (d:Decision)-[r:CONSIDERED|SELECTED|REJECTED]->(p:Plan)
RETURN d, r, p
```

```cypher
MATCH (d:Decision)-[:BASED_ON]->(o:Observation)-[:ABOUT]->(a:Asset)
RETURN d.id, a.id, o.property, o.value, o.source, o.observed_at
```

```cypher
MATCH (a:ExecutionAttempt)-[:VERIFIED_BY]->(o:Observation)
RETURN a.status, a.expected, o.property, o.value
```

Candidate branch graphs are intentionally short-lived and deleted after evaluation. Inspect the persisted decision/plan records for the retained rationale. Do not expect graph copies to remain in the Browser after a completed run.

## Troubleshooting

- **Docker connection error:** start Docker and wait until `docker info` succeeds, then retry Compose.
- **Database unavailable:** check `docker compose ps` and `docker compose logs --tail=60 falkordb`. Confirm port 6379 is available. After recovery, refresh the dashboard to recheck health.
- **Port 6379 occupied:** stop only your own conflicting service, or set `FALKORDB_PORT=6380 docker compose up -d falkordb` and set `FALKORDB_PORT=6380` in `backend/.env`. Do not disrupt another project's database.
- **Port 8000 occupied:** check whether Ripple is already running. If changing the backend port, also change the `/api` target in `frontend/vite.config.ts` and restart Vite.
- **Vite chooses a different port:** use the URL printed by Vite or free port 5173. Update any bookmarked URL accordingly.
- **Module import errors:** run `uv sync --locked --python 3.12` and invoke scripts as `uv run python -m scripts.run_demo`, from `backend/`.
- **WebSocket interruption:** the backend may still be running. Do not start an overlapping run; wait for it to finish and retry. The demo is single-process and is not resilient across server restarts.
- **Cyberwave authentication/configuration error:** verify your key and environment/twin IDs in `backend/.env` without sharing the key, run the setup script for your own environment and restart the backend. Use Local simulated inspector to reproduce graph logic independently.
- **Twin visible but not walking:** expected. The current integration updates and reads back twin positions; gait simulation is not part of this demo.

## Stopping and data handling

Press Ctrl+C in the backend and frontend terminals. Run `docker compose stop falkordb` from the repository root to stop the database without deleting its local data. Generated demo graphs are retained; evaluation runs clean up only their own graphs. `backend/.env`, database storage, virtual environments, installed packages and generated evaluation output are excluded by `.gitignore`.

## Deployment status

There is no publicly hosted Ripple application in this submission. The Cyberwave environment is an account-controlled integration, not a public deployment of the whole application. The local instructions above are the supported reproduction route. A public service would need authentication, persistent run storage, isolated worker/control ownership, credential management and appropriate database/network isolation before deployment.
