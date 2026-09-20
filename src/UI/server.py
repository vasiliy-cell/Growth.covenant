"""
The panel: a local web app for watching runs and starting them.

    PYTHONPATH=. python src/UI/server.py        # then open the printed url

It binds to 127.0.0.1 and nothing else. It can start processes and delete
data, so it is a tool on your own machine, not a service - there is no
authentication here because there is nobody else to authenticate.

The panel only ever READS the logs, and it reads them as files: finished
parquet parts and a small live.json. A run does not know the panel exists
and does not slow down because somebody opened it.
"""

import os
import shutil
import sys
import tarfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.UI import reports
from src.UI.launcher import Launcher

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def load_config():
    with open(os.path.join(REPO_ROOT, "config.yml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


CONFIG = load_config()
LOGS_DIR = os.path.join(REPO_ROOT, CONFIG.get("logging", {}).get("dir", "logs"))
ARCHIVE_DIR = os.path.join(
    REPO_ROOT, CONFIG.get("logging", {}).get("archive_dir", "archives")
)

app = FastAPI(title="Growth.covenant", docs_url=None, redoc_url=None)
launcher = Launcher(parallel=2)


class LaunchRequest(BaseModel):
    episodes: int = 100
    agents: int = 1
    species: str = "clons"
    seed: int = None
    label: str = ""
    series: str = ""
    live_every: int = 20
    pin: bool = False
    resume: str = ""
    repeat: int = 1
    overrides: list = []


class ArchiveRequest(BaseModel):
    note: str
    delete: bool = False


class ParallelRequest(BaseModel):
    parallel: int


# -----------------------------
# CATALOG AND CHARTS
# -----------------------------
@app.get("/api/worlds")
def worlds():
    return {"logs_dir": LOGS_DIR, "worlds": reports.catalog(LOGS_DIR)}


def reader_for(world):
    try:
        return reports.open_world(LOGS_DIR, world)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail=f"No world at {world}")


@app.get("/api/worlds/{world:path}/rewards")
def world_rewards(world: str):
    return reports.rewards(reader_for(world))


@app.get("/api/worlds/{world:path}/learning")
def world_learning(world: str):
    return reports.learning(reader_for(world))


@app.get("/api/worlds/{world:path}/family")
def world_family(world: str):
    return reports.family(reader_for(world))


@app.get("/api/worlds/{world:path}/details")
def world_details(world: str):
    return reports.details(reader_for(world))


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
        import json

        json.dump({
            "note": request.note,
            "world_id": reader.world_id,
            "label": reader.label,
            "series": reader.series,
            "archived_at": time.time(),
            "source": reader.path,
        }, handle, indent=2)

    temporary = archive_path + ".writing"

    with tarfile.open(temporary, "w:gz") as tar:
        tar.add(reader.path, arcname=name)
        tar.add(note_path, arcname=os.path.join(name, "NOTE.json"))

    os.replace(temporary, archive_path)

    deleted = False

    if request.delete:
        with tarfile.open(archive_path) as tar:
            if not tar.getnames():
                raise HTTPException(status_code=500, detail="Empty archive")

        shutil.rmtree(reader.path)
        deleted = True

    return {
        "archive": os.path.relpath(archive_path, REPO_ROOT),
        "size": os.path.getsize(archive_path),
        "deleted": deleted,
    }


@app.delete("/api/worlds/{world:path}")
def delete_world(world: str):
    """Straight deletion, with nothing kept. The panel asks twice."""
    reader = reader_for(world)
    path = reader.path

    if reports.read_live(path) and reports.read_live(path)["running"]:
        raise HTTPException(status_code=409, detail="That run is still going")

    shutil.rmtree(path)

    return {"deleted": os.path.relpath(path, REPO_ROOT)}


# -----------------------------
# LIVE
# -----------------------------
@app.get("/api/live")
def live():
    return {"worlds": reports.live_all(LOGS_DIR)}


# -----------------------------
# RUNS
# -----------------------------
@app.get("/api/runs")
def runs():
    return launcher.summary()


@app.post("/api/runs")
def launch(request: LaunchRequest):
    return {"launched": launcher.submit(request.dict())}


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


@app.post("/api/parallel")
def parallel(request: ParallelRequest):
    launcher.parallel = max(1, min(request.parallel, (os.cpu_count() or 2) * 2))

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


@app.exception_handler(FileNotFoundError)
def missing(request, error):
    return JSONResponse(status_code=404, content={"detail": str(error)})


def main():
    host, port = "127.0.0.1", 8000

    print(f"Panel: http://{host}:{port}")
    print(f"Logs:  {LOGS_DIR}")

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
