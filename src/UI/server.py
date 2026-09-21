"""
The panel: a local web app for watching runs and starting them.

    ./panel.sh          (or: PYTHONPATH=. python src/UI/server.py)

It binds to 127.0.0.1 and nothing else. It can start processes and delete
data, so it is a tool on your own machine, not a service - there is no
authentication here because there is nobody else to authenticate.

The panel only ever READS what a run writes: finished parquet parts and a
small live.json. A run does not know the panel exists and does not slow
down because somebody opened it.
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from typing import Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.persistence.checkpoint_store import CheckpointStore
from src.persistence.run_log import RunLog
from src.UI import reports
from src.UI.launcher import Launcher

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
HOST, PORT = "127.0.0.1", 8000


def load_config():
    with open(os.path.join(REPO_ROOT, "config.yml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


CONFIG = load_config()
LOGS_DIR = os.path.join(REPO_ROOT, CONFIG.get("logging", {}).get("dir", "logs"))

# The panel's own files - never inside logs/. A run writes its heartbeat to
# live/, the live view asks a run to slow down through watch/.
PANEL_DIR = os.path.join(REPO_ROOT, CONFIG.get("logging", {}).get("panel_dir", ".panel"))
LIVE_DIR = os.path.join(PANEL_DIR, "live")
WATCH_DIR = os.path.join(PANEL_DIR, "watch")

# How long a watch request holds without being renewed. The live view
# renews it every two seconds; a tab that vanished lets it lapse.
WATCH_HOLD = 6.0
ARCHIVE_DIR = os.path.join(REPO_ROOT, CONFIG.get("logging", {}).get("archive_dir", "archives"))

STORE = CheckpointStore(
    directory=os.path.join(REPO_ROOT, CONFIG.get("checkpoints", {}).get("dir", "checkpoints")),
    keep=int(CONFIG.get("checkpoints", {}).get("keep", 5)),
)

app = FastAPI(title="Growth.covenant", docs_url=None, redoc_url=None)
launcher = Launcher(console_dir=os.path.join(PANEL_DIR, "consoles"))


@app.middleware("http")
async def never_stale(request, call_next):
    """
    Every file is revalidated on every load.

    A panel that serves yesterday's javascript against today's api breaks
    in ways that look like bugs in both, so nothing here is cached - on
    localhost the cost of that is nothing.
    """
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


# -----------------------------
# REQUESTS
# -----------------------------
class LaunchRequest(BaseModel):
    episodes: int = 100
    agents: int = 1
    species: str = "clons"
    # Optional, not `int = None`: pydantic 2 reads the latter as a required
    # integer and turns an empty seed field into a 422.
    seed: Optional[int] = None
    label: str = ""
    pin: bool = False
    repeat: int = 1


class ContinueRequest(BaseModel):
    episodes: int = 100


class WatchRequest(BaseModel):
    speed: int = 0


class RenameRequest(BaseModel):
    label: str = ""


class CompareRequest(BaseModel):
    worlds: list
    metric: str = "shaped_reward"


class ArchiveRequest(BaseModel):
    note: str
    delete: bool = False


def reader_for(world):
    try:
        return reports.open_world(LOGS_DIR, world)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail=f"No world at {world}")


# -----------------------------
# WORLDS
# -----------------------------
@app.get("/api/worlds")
def worlds():
    return {"worlds": reports.catalog(LOGS_DIR, STORE, LIVE_DIR)}


@app.get("/api/facets")
def facets():
    return reports.facets(LOGS_DIR)


@app.get("/api/worlds/{world:path}/details")
def world_details(world: str):
    return reports.details(reader_for(world), LIVE_DIR)


@app.get("/api/worlds/{world:path}/rewards")
def world_rewards(world: str):
    return reports.rewards(reader_for(world))


@app.get("/api/worlds/{world:path}/learning")
def world_learning(world: str):
    return reports.learning(reader_for(world))


@app.get("/api/worlds/{world:path}/family")
def world_family(world: str):
    return reports.family(reader_for(world))


@app.get("/api/worlds/{world:path}/stream")
async def world_stream(world: str, request: Request):
    """
    The world's live frames, pushed as they are written.

    The run rewrites live.json and knows nothing else; this watches the
    file and sends every new version down one open connection - no request
    per frame, so a frame costs a file read and a few kilobytes.
    """
    world_id = reader_for(world).world_id
    path = os.path.join(LIVE_DIR, f"{world_id}.json")

    async def frames():
        last = None

        while not await request.is_disconnected():
            try:
                changed = os.stat(path).st_mtime_ns
            except FileNotFoundError:
                changed = None

            if changed is not None and changed != last:
                last = changed
                live = reports.read_live(LIVE_DIR, world_id)

                if live is not None:
                    yield f"data: {json.dumps(live)}\n\n"

            await asyncio.sleep(0.012)

    return StreamingResponse(frames(), media_type="text/event-stream")


@app.post("/api/worlds/{world:path}/watch")
def watch_world(world: str, request: WatchRequest):
    """
    Ask a running world to slow down to `speed` steps a second, for the
    next few seconds. The live view keeps renewing this while it is open;
    speed 0 - or simply stopping the renewals - lets the run go back to
    full speed.
    """
    world_id = reader_for(world).world_id
    path = os.path.join(WATCH_DIR, f"{world_id}.json")

    if request.speed <= 0:
        if os.path.exists(path):
            os.remove(path)
        return {"speed": 0}

    os.makedirs(WATCH_DIR, exist_ok=True)
    temporary = path + ".writing"

    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"speed": request.speed, "until": time.time() + WATCH_HOLD}, handle)

    os.replace(temporary, path)

    return {"speed": request.speed}


def running_pid(reader):
    """The pid of the run writing this world right now, or None."""
    live = reports.read_live(LIVE_DIR, reader.world_id)

    return live["pid"] if live and live["running"] else None


@app.post("/api/worlds/{world:path}/stop")
def stop_world(world: str):
    """
    Stop a running world early. SIGTERM, which the runner turns into its
    crash path - so it writes a checkpoint on the way out and the world can
    be continued later.
    """
    pid = running_pid(reader_for(world))

    if pid is None:
        raise HTTPException(status_code=409, detail="That world is not running")

    # Only ever signal a process that really is one of our runs: a pid in
    # a stale heartbeat could by now belong to anything.
    try:
        command = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="]).decode()
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=409, detail="That run has already ended")

    if "src/run.py" not in command:
        raise HTTPException(status_code=409, detail="That pid is not a run any more")

    os.kill(pid, signal.SIGTERM)

    return {"stopped": pid}


@app.post("/api/worlds/{world:path}/keep")
def keep_world(world: str):
    """
    Pin the world's newest checkpoint, so the rotation never takes it and
    the world can always be continued.
    """
    reader = reader_for(world)
    checkpoint = reports.latest_checkpoint(reader, reports.checkpoints_by_run(STORE))

    if checkpoint is None:
        raise HTTPException(status_code=404, detail="This world has no checkpoint left to keep")

    if not checkpoint["pinned"]:
        STORE.pin(checkpoint["name"])

    return {"kept": checkpoint["name"]}


@app.post("/api/worlds/{world:path}/rename")
def rename_world(world: str, request: RenameRequest):
    """
    Give a world a new name: the label in its run.json, and its folder.

    A running world cannot be renamed - its run rewrites run.json from
    memory on every flush and would quietly put the old name back.
    """
    reader = reader_for(world)

    if running_pid(reader) is not None:
        raise HTTPException(status_code=409, detail="Stop the run first: it keeps rewriting its own name")

    label = request.label.strip() or None
    header = dict(reader.header)
    header["label"] = label

    header_path = os.path.join(reader.path, "run.json")
    temporary = header_path + ".writing"

    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(header, handle, indent=2)

    os.replace(temporary, header_path)

    # The folder follows the name. A continued run finds a world by the id
    # at the front of the folder name, so only the part after it changes.
    target = os.path.join(os.path.dirname(reader.path), RunLog.folder_name(reader.world_id, label))

    if target != reader.path:
        os.rename(reader.path, target)

    return {"id": os.path.relpath(target, LOGS_DIR), "label": label}


@app.post("/api/worlds/{world:path}/continue")
def continue_world(world: str, request: ContinueRequest):
    """
    Carry a world on from its newest checkpoint. The runner takes the
    seed, the species and the population from the checkpoint itself, so
    all that is asked here is how much longer, and whether to watch.
    """
    reader = reader_for(world)
    checkpoint = reports.latest_checkpoint(reader, reports.checkpoints_by_run(STORE))

    if checkpoint is None:
        raise HTTPException(status_code=404, detail="This world has no checkpoint")

    launched = launcher.submit({
        "episodes": request.episodes,
        "resume": checkpoint["path"],
        "label": reader.label,
    })

    return {"launched": launched, "checkpoint": checkpoint}


@app.post("/api/worlds/{world:path}/archive")
def archive_world(world: str, request: ArchiveRequest):
    """
    Pack a world into archives/ with the note beside it, and only then -
    if asked - delete the original. The note is not optional: an unnamed
    tarball is a tarball nobody ever opens again.
    """
    if not request.note.strip():
        raise HTTPException(status_code=400, detail="An archive needs a note")

    reader = reader_for(world)
    name = os.path.basename(reader.path)

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    archive_path = os.path.join(ARCHIVE_DIR, f"{name}.tar.gz")

    if os.path.exists(archive_path):
        raise HTTPException(status_code=409, detail=f"Already archived: {name}")

    note_path = os.path.join(ARCHIVE_DIR, f"{name}.note.json")

    with open(note_path, "w", encoding="utf-8") as handle:
        json.dump({
            "note": request.note,
            "world_id": reader.world_id,
            "label": reader.label,
            "archived_at": time.time(),
            "source": reader.path,
        }, handle, indent=2)

    temporary = archive_path + ".writing"

    with tarfile.open(temporary, "w:gz") as tar:
        tar.add(reader.path, arcname=name)
        tar.add(note_path, arcname=os.path.join(name, "NOTE.json"))

    os.replace(temporary, archive_path)

    if request.delete:
        with tarfile.open(archive_path) as tar:
            if not tar.getnames():
                raise HTTPException(status_code=500, detail="Empty archive")

        shutil.rmtree(reader.path)

    return {"archive": os.path.relpath(archive_path, REPO_ROOT), "deleted": request.delete}


@app.delete("/api/worlds/{world:path}")
def delete_world(world: str):
    """Straight deletion, with nothing kept. The panel asks twice."""
    reader = reader_for(world)
    live = reports.read_live(LIVE_DIR, reader.world_id)

    if live and live["running"]:
        raise HTTPException(status_code=409, detail="That run is still going")

    shutil.rmtree(reader.path)

    return {"deleted": os.path.relpath(reader.path, REPO_ROOT)}


@app.post("/api/compare")
def compare(request: CompareRequest):
    try:
        return reports.compare(LOGS_DIR, request.worlds, request.metric)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"No world at {error}")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/api/metrics")
def metrics():
    return {
        key: {"name": name, "description": description, "higher_is_better": better}
        for key, (name, description, better) in reports.METRICS.items()
    }


# -----------------------------
# RUNS
# -----------------------------
@app.get("/api/runs")
def runs():
    return launcher.summary()


@app.post("/api/runs")
def launch(request: LaunchRequest):
    return {"launched": launcher.submit(request.dict())}


@app.get("/api/runs/{identifier}/world")
def run_world(identifier: str):
    """
    Which world a launched run is writing.

    A render window is opened the moment Start is pressed - a browser only
    allows a new window as the direct answer to a click - but the world id
    is minted inside the run a second later. The window asks here until
    the run's heartbeat names its world.
    """
    run = launcher.get(identifier)

    if run is None:
        raise HTTPException(status_code=404, detail="No such run")

    summary = run.summary()

    if summary["pid"] is not None:
        for live in reports.live_all(LOGS_DIR, LIVE_DIR):
            if live.get("pid") == summary["pid"]:
                return {"world": live["id"], "state": summary["state"]}

    return {"world": None, "state": summary["state"]}


@app.delete("/api/runs/{identifier}")
def stop(identifier: str):
    stopped = launcher.stop(identifier)

    if stopped is None:
        raise HTTPException(status_code=404, detail="No such run")

    return stopped


@app.get("/api/runs/{identifier}/console")
def console(identifier: str):
    run = launcher.get(identifier)

    if run is None:
        raise HTTPException(status_code=404, detail="No such run")

    return {"console": run.tail()}


@app.post("/api/runs/clear")
def clear():
    launcher.clear_finished()

    return launcher.summary()


@app.get("/api/config")
def config():
    """The config as it stands, so the launch form can offer its values."""
    return {"config": load_config(), "cpus": os.cpu_count()}


# -----------------------------
# THE PAGE
# -----------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main():
    print(f"Panel: http://{HOST}:{PORT}")
    print(f"Logs:  {LOGS_DIR}")

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
