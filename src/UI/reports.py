"""
Logs in, chart-ready json out.

Everything the panel draws is computed here and nowhere else: the browser
receives numbers it can plot and never learns what a parquet part is.

Two rules keep the panel quick on a directory full of long runs:

  - a catalog never reads a table. Row counts come out of parquet
    footers, sizes out of the filesystem, everything else out of run.json,
  - a chart reads the per-episode tables, which have one row per window.
    The step table is millions of rows and is not what a chart is made of.
"""

import json
import os
import time

import pyarrow.dataset as ds

from src.persistence.log_reader import RunLogReader

# A live.json older than this belongs to a run that is no longer with us.
LIVE_TIMEOUT = 20.0


def folder_size(path):
    total = 0

    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass

    return total


def read_live(live_dir, world_id):
    """
    The heartbeat of a world, or None if it never had one.

    Heartbeats live with the panel's own files (logging.panel_dir), one
    per world and named after it - never in the world's log folder.
    """
    live_path = os.path.join(live_dir, f"{world_id}.json")

    if not os.path.isfile(live_path):
        return None

    try:
        with open(live_path, encoding="utf-8") as handle:
            live = json.load(handle)
    except (OSError, ValueError):
        return None

    live["age"] = time.time() - live.get("updated_at", 0)
    live["running"] = not live.get("finished") and live["age"] < LIVE_TIMEOUT

    return live


# -----------------------------
# CHECKPOINTS
# -----------------------------
def checkpoints_by_run(store):
    """
    Every checkpoint on disk, grouped by the run that wrote it.

    A world's sessions each have a run id, and a checkpoint is named after
    the run that wrote it - so this is the one listing a whole catalog
    needs, read once instead of once per world.
    """
    grouped = {}

    for checkpoint in store.list():
        grouped.setdefault(checkpoint["run_id"], []).append(checkpoint)

    return grouped


def latest_checkpoint(reader, grouped):
    """The newest checkpoint any session of this world wrote, or None."""
    found = [
        checkpoint
        for session in reader.sessions
        for checkpoint in grouped.get(session.get("run_id"), [])
    ]

    if not found:
        return None

    best = max(found, key=lambda checkpoint: (checkpoint["step"], checkpoint["saved_at"]))

    return {
        "path": best["path"],
        "name": best["name"],
        "step": best["step"],
        "pinned": best["pinned"],
    }


# -----------------------------
# CATALOG
# -----------------------------
def catalog(logs_dir, store=None, live_dir=None):
    """Every world on disk, newest first, without opening a table."""
    worlds = []
    grouped = checkpoints_by_run(store) if store is not None else {}

    for reader in RunLogReader.find(logs_dir):
        sessions = reader.sessions
        live = read_live(live_dir, reader.world_id) if live_dir else None
        population = last_population(reader)

        worlds.append({
            "id": os.path.relpath(reader.path, logs_dir),
            "path": reader.path,
            "world_id": reader.world_id,
            "label": reader.label,
            "series": reader.series,
            "species": reader.header.get("species"),
            "created_at": reader.created_at,
            "sessions": len(sessions),
            "seeds": [session.get("seed") for session in sessions],
            "episodes": reader.count("episode_population"),
            "last_step": max(
                [session.get("to_step") or 0 for session in sessions] or [0]
            ),
            "deaths": reader.count("deaths"),
            "size": folder_size(reader.path),
            "genes": len(reader.genes),
            "commit": reader.header.get("commit"),
            "running": bool(live and live["running"]),
            "population": population,
            # Nobody alive and nothing running: there is nothing to watch,
            # stop or continue, and the panel must not pretend otherwise.
            "extinct": population == 0 and not (live and live["running"]),
            "checkpoint": latest_checkpoint(reader, grouped),
            "live": {
                "step": live["step"],
                "agents": live["agents"],
                "steps_per_second": live.get("steps_per_second"),
            } if live else None,
        })

    return worlds


def last_population(reader):
    """
    How many agents the world had at the end of its last logged episode,
    or None if it has not closed one yet.

    Only two columns of one small table are read - the catalog asks this of
    every world every few seconds.
    """
    path = os.path.join(reader.path, "episodes", "population")

    if not os.path.isdir(path) or not os.listdir(path):
        return None

    table = ds.dataset(path, format="parquet").to_table(columns=["step_end", "agents"])

    if table.num_rows == 0:
        return None

    last = max(range(table.num_rows), key=lambda row: table["step_end"][row].as_py())

    return table["agents"][last].as_py()


def open_world(logs_dir, world):
    """A world by the id the catalog handed out (its path under logs/)."""
    path = os.path.normpath(os.path.join(logs_dir, world))

    if not os.path.isfile(os.path.join(path, "run.json")):
        raise FileNotFoundError(world)

    return RunLogReader(path)


def details(reader, live_dir=None):
    header = dict(reader.header)

    return {
        "world_id": reader.world_id,
        "label": reader.label,
        "series": reader.series,
        "species": header.get("species"),
        "genes": reader.genes,
        "episode_length": header.get("episode_length"),
        "versions": header.get("versions"),
        "commit": header.get("commit"),
        "created_at": reader.created_at,
        "config": header.get("config"),
        "sessions": reader.sessions,
        "counts": {
            "episodes": reader.count("episode_population"),
            "steps": reader.count("steps"),
            "updates": reader.count("updates"),
            "deaths": reader.count("deaths"),
            "snapshots": reader.count("world_grid"),
        },
        "live": read_live(live_dir, reader.world_id) if live_dir else None,
    }


# -----------------------------
# CHARTS
# -----------------------------
def column(table, name):
    return table[name].to_pylist() if name in table.schema.names else []


def rewards(reader):
    """
    Every kind of reward on one chart, per logging window.

    env is what the world paid, intrinsic is what curiosity added, shaped
    is what the networks actually learned from - the gap between the first
    and the last is the whole story of how much of this run is curiosity.
    """
    table = reader.episode_population()

    return {
        "episodes": column(table, "episode"),
        "steps": column(table, "step_end"),
        "env": column(table, "env_reward"),
        "intrinsic": column(table, "intrinsic_reward"),
        "shaped": column(table, "shaped_reward"),
        "agents": column(table, "agents"),
        "births": column(table, "births"),
        "deaths": column(table, "deaths"),
        "sessions": column(table, "session"),
    }


def learning(reader):
    """What the gradient did, per window."""
    table = reader.episode_population()

    return {
        "episodes": column(table, "episode"),
        "loss": column(table, "mean_loss"),
        "td_error": column(table, "mean_td_error"),
        "updates": column(table, "updates"),
        "epsilon": column(table, "mean_epsilon"),
        "curiosity_beta": column(table, "mean_curiosity_beta"),
        "sessions": column(table, "session"),
    }


def family(reader):
    """
    The whole population as a tree: a node per agent, an edge per parent.

    Births carry the genotype and the phenotype, deaths carry how the life
    ended, and an agent with no death row is simply still alive - so a node
    holds everything hovering over it should show.
    """
    births = reader.births().to_pylist()
    deaths = {row["agent_id"]: row for row in reader.deaths().to_pylist()}

    nodes = []
    edges = []

    for birth in births:
        agent_id = birth["agent_id"]
        death = deaths.get(agent_id)

        phenotype = {
            name[len("phen_"):]: value
            for name, value in birth.items()
            if name.startswith("phen_")
        }

        nodes.append({
            "id": agent_id,
            "index": birth["index"],
            "parents": birth["parents"],
            "birth_step": birth["step"],
            "energy_at_birth": birth["energy"],
            "phenotype": phenotype,
            "genotype": json.loads(birth["genotype_json"] or "null"),
            "alive": death is None,
            "death_step": death["death_step"] if death else None,
            "lifespan": death["lifespan"] if death else None,
            "cumulative_reward": death["cumulative_reward"] if death else None,
            "offspring": death["num_offspring"] if death else None,
            "cause_of_death": death["cause_of_death"] if death else None,
        })

        for parent in birth["parents"]:
            edges.append({"source": parent, "target": agent_id})

    known = {node["id"] for node in nodes}

    return {
        "nodes": nodes,
        # A parent that predates this log (a world continued from a
        # checkpoint whose births were written in another session) would
        # otherwise leave an edge pointing at nothing.
        "edges": [edge for edge in edges if edge["source"] in known],
    }


# -----------------------------
# COMPARISON
# -----------------------------
# What can be compared, and which way is better. A leaderboard of losses
# sorted like a leaderboard of rewards would crown the worst run.
METRICS = {
    "shaped_reward": ("Total reward", "what the networks learned from: world + curiosity, per episode", True),
    "env_reward": ("World reward", "food minus danger, what the world itself paid, per episode", True),
    "intrinsic_reward": ("Curiosity reward", "the bonus for visiting new places, per episode", True),
    "mean_loss": ("Loss", "mean training loss per episode", False),
    "mean_td_error": ("TD error", "mean |prediction - target| per episode", False),
    "agents": ("Population", "agents alive at the end of each episode", True),
    "births": ("Births", "agents born per episode", True),
    "deaths": ("Deaths", "agents that starved per episode", False),
    "mean_epsilon": ("Exploration", "mean epsilon: how often the agents act at random", False),
}


def compare(logs_dir, worlds, metric):
    """One series per world, on the same axis: the episode."""
    if metric not in METRICS:
        raise ValueError(f"Unknown metric {metric}")

    series = []

    for world in worlds:
        reader = open_world(logs_dir, world)
        table = reader.episode_population()

        series.append({
            "id": world,
            "label": reader.label or reader.world_id,
            "species": reader.header.get("species"),
            "seed": (reader.sessions[0] if reader.sessions else {}).get("seed"),
            "episodes": column(table, "episode"),
            "values": column(table, metric),
        })

    name, description, higher_is_better = METRICS[metric]

    return {
        "metric": metric,
        "name": name,
        "description": description,
        "higher_is_better": higher_is_better,
        "series": series,
    }


def live_all(logs_dir, live_dir):
    """Every heartbeat on disk that belongs to a world still in logs/."""
    found = []

    for reader in RunLogReader.find(logs_dir):
        live = read_live(live_dir, reader.world_id)

        if live is None:
            continue

        live["id"] = os.path.relpath(reader.path, logs_dir)
        found.append(live)

    return sorted(
        found,
        key=lambda live: (not live["running"], -live.get("updated_at", 0)),
    )


# -----------------------------
# FACETS
# -----------------------------
# Config sections that describe where files go, not what the experiment
# was. Two runs that differ only in a log directory are the same run.
NOT_EXPERIMENT = ("logging.", "checkpoints.")


def flatten(config, prefix=""):
    """{"energy": {"energy_leak": 0.5}} -> {"energy.energy_leak": 0.5}"""
    flat = {}

    for key, value in (config or {}).items():
        name = f"{prefix}{key}"

        if isinstance(value, dict):
            flat.update(flatten(value, name + "."))
        else:
            flat[name] = value

    return flat


def facets(logs_dir):
    """
    What the runs on disk actually differ in, as clickable filters.

    Nobody remembers that the leak is energy.energy_leak - so the panel
    never asks. Every config value that is not the same in all runs
    becomes a facet, with the values it takes as buttons, and a value
    that every run shares is not a filter at all and is left out.
    """
    params = {}

    for reader in RunLogReader.find(logs_dir):
        first = reader.sessions[0] if reader.sessions else {}
        config = first.get("config") or reader.header.get("config") or {}

        params[os.path.relpath(reader.path, logs_dir)] = {
            key: value
            for key, value in flatten(config).items()
            if not key.startswith(NOT_EXPERIMENT)
        }

    keys = sorted({key for flat in params.values() for key in flat})
    differing = {}

    for key in keys:
        seen = {}

        for flat in params.values():
            value = flat.get(key)
            seen[json.dumps(value, sort_keys=True)] = value

        if len(seen) > 1:
            differing[key] = sorted(seen.values(), key=_order)

    return {
        "facets": differing,
        "params": {
            world: {key: flat.get(key) for key in differing}
            for world, flat in params.items()
        },
    }


def _order(value):
    """Numbers by size, everything else by its text: 25 comes before 100."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return (1, 0, json.dumps(value, sort_keys=True))

    return (0, value, "")
