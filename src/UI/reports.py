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


def read_live(path):
    """The heartbeat of a world, or None if it never had one."""
    live_path = os.path.join(path, "live.json")

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
# CATALOG
# -----------------------------
def catalog(logs_dir):
    """Every world on disk, newest first, without opening a table."""
    worlds = []

    for reader in RunLogReader.find(logs_dir):
        sessions = reader.sessions
        live = read_live(reader.path)

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
            "live": {
                "step": live["step"],
                "agents": live["agents"],
                "steps_per_second": live.get("steps_per_second"),
            } if live else None,
        })

    return worlds


def open_world(logs_dir, world):
    """A world by the id the catalog handed out (its path under logs/)."""
    path = os.path.normpath(os.path.join(logs_dir, world))

    if not os.path.isfile(os.path.join(path, "run.json")):
        raise FileNotFoundError(world)

    return RunLogReader(path)


def details(reader):
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
        "live": read_live(reader.path),
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


def live_all(logs_dir):
    """Every heartbeat on disk, the running ones first."""
    found = []

    for reader in RunLogReader.find(logs_dir):
        live = read_live(reader.path)

        if live is None:
            continue

        live["id"] = os.path.relpath(reader.path, logs_dir)
        found.append(live)

    return sorted(
        found,
        key=lambda live: (not live["running"], -live.get("updated_at", 0)),
    )
