"""Local simulation API. One active run prevents concurrent control of one twin."""

import asyncio
import threading
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ripple.graph.client import get_db
from ripple.simulator.runtime import run_scenario, scenario_catalog

app = FastAPI(title="Ripple simulation")
runs = {}
lock = threading.Lock()


class RunRequest(BaseModel):
    scenario: Literal[
        "healthy_8", "healthy_5", "standby_down", "stale_valve", "stuck_valve", "new_load"
    ] = "healthy_5"
    mode: Literal["full_ripple", "graph_no_inspection", "local_baseline"] = "full_ripple"
    adapter: Literal["mock", "cyberwave"] = "mock"
    paced: bool = True


@app.get("/api/health")
def health():
    try:
        get_db().connection.ping()
    except Exception:
        raise HTTPException(
            503, "FalkorDB unavailable; start docker compose up -d falkordb"
        ) from None
    return {"status": "ok", "database": "FalkorDB"}


@app.get("/api/scenarios")
def scenarios():
    return scenario_catalog()


@app.post("/api/runs", status_code=202)
def start(body: RunRequest):
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "A simulation is already running")
    run_id = uuid4().hex[:12]
    runs[run_id] = {"id": run_id, "status": "running", "events": []}

    def worker():
        try:
            data = run_scenario(
                body.scenario,
                mode=body.mode,
                adapter=body.adapter,
                delay=0.2 if body.paced else 0,
                graph_name=f"ripple_demo_{run_id}",
                emit=lambda event: runs[run_id]["events"].append(event),
            )
            runs[run_id].update(data)
            runs[run_id]["status"] = "done"
        except Exception as error:
            # No credentials or raw SDK errors in the public stream.
            runs[run_id].update(
                status="error",
                error=(
                    f"Run failed ({type(error).__name__}); "
                    "check database and adapter configuration."
                ),
            )
            import traceback

            traceback.print_exc()
        finally:
            lock.release()

    threading.Thread(target=worker, daemon=True).start()
    return {"id": run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    if run_id not in runs:
        raise HTTPException(404, "Unknown run")
    return runs[run_id]


@app.websocket("/api/stream/{run_id}")
async def stream(ws: WebSocket, run_id: str):
    await ws.accept()
    if run_id not in runs:
        await ws.close(code=1008)
        return
    cursor = 0
    try:
        while True:
            run = runs[run_id]
            batch = run["events"][cursor:]
            for event in batch:
                await ws.send_json({"kind": "event", "event": event})
            cursor += len(batch)
            if run["status"] != "running":
                await ws.send_json(
                    {"kind": "finished", "run": {k: v for k, v in run.items() if k != "events"}}
                )
                await ws.close()
                return
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
