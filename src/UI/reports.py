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

import numpy as np
import pyarrow.compute as pc
import pyarrow.dataset as ds

from src.persistence import log_schema
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
# COHORTS: who a chart is about
# -----------------------------
# Every chart can be asked about children only, adults only, or about the
# agents that lived a certain number of steps. Both questions are answered
# out of the log alone - the core is not asked to write anything new.


def childhood_length(reader):
    """`life.max_childhood_steps` as the newest session of this world had it."""
    for session in reversed(reader.sessions):
        life = (session.get("config") or {}).get("life", {})

        if life.get("max_childhood_steps") is not None:
            return int(life["max_childhood_steps"])

    return 0


def cohorts(reader):
    """
    Per agent: the age its childhood ended at, and how long it lived.

    Childhood is the core's own notion (`Life.is_child`): it lasts
    `max_childhood_steps`, but BREEDING ends it on the spot, because an
    agent that has fed itself up to the reproduction threshold has shown it
    can forage. The logs do not carry that moment as a column - and they do
    not need to: they carry every birth, and the age an agent was when its
    FIRST child was born is exactly the age its childhood ended at.

    Lifespan is the death row for whoever has one, and the last age logged
    for whoever is still walking around.
    """
    births = reader.births()
    childhood = childhood_length(reader)

    born = {}
    adult_at = {}
    children = {}

    if births.num_rows:
        ids = births["agent_id"].to_pylist()
        steps = births["step"].to_pylist()
        parents = births["parents"].to_pylist()
        born = dict(zip(ids, steps))

        for agent_id, step, mothers in zip(ids, steps, parents):
            for parent in mothers or []:
                children.setdefault(parent, []).append(agent_id)

                if parent not in born:
                    continue

                age = step - born[parent]

                if age < adult_at.get(parent, float("inf")):
                    adult_at[parent] = age

    # min(first birth, max_childhood_steps), the way Life.adulthood reads it
    adulthood = {
        agent_id: min(adult_at.get(agent_id, childhood), childhood)
        for agent_id in born
    }

    lifespan = {}
    deaths = reader.deaths()

    if deaths.num_rows:
        lifespan = dict(zip(deaths["agent_id"].to_pylist(), deaths["lifespan"].to_pylist()))

    # Whoever has no death row is still walking around, and how long it has
    # lived so far is the oldest age any window ever logged for it.
    buried = set(lifespan)
    windows = reader.episode_agents()

    if windows.num_rows:
        encoded = pc.dictionary_encode(windows["agent_id"]).combine_chunks()
        codes = encoded.indices.to_numpy(zero_copy_only=False)
        names = encoded.dictionary.to_pylist()
        oldest = np.zeros(len(names), dtype=np.int64)
        np.maximum.at(oldest, codes, windows["age"].to_numpy(zero_copy_only=False).astype(np.int64))

        for name, age in zip(names, oldest):
            if name not in buried:
                lifespan[name] = int(age)

    return {
        "childhood": childhood,
        "born": born,
        "adulthood": adulthood,
        "lifespan": lifespan,
        "children": children,
    }


def life_rules(reader):
    """
    The `life` / `energy` numbers this world was run with.

    The newest session wins, the same way `cohorts` takes childhood from it:
    a world continued under a different leak is describing the rules it is
    living under now.
    """
    for session in reversed(reader.sessions):
        config = session.get("config") or {}

        if config:
            life = config.get("life", {})
            energy = config.get("energy", {})

            return {
                "base": float(energy.get("energy_leak", 0.0)),
                "every": int((life.get("aging") or {}).get("every", 0) or 0),
                "amount": float((life.get("aging") or {}).get("amount", 0.0)),
                "childhood": int(life.get("max_childhood_steps", 0) or 0),
            }

    return {"base": 0.0, "every": 0, "amount": 0.0, "childhood": 0}


def leak_per_row(reader, table, who):
    """
    What each per-agent window cost its agent in energy, just to be alive.

    This is `Life.leak` written in arrays: the base cost of a tick, plus one
    `aging.amount` for every full `aging.every` ticks of ADULT life - and a
    child pays the base cost and nothing more. The rules are read out of the
    session's own config, so a world run with a different leak reports its
    own, and the core is not asked to log anything.

    An age here is the age at the END of the window, and aging moves in
    steps of hundreds of ticks against a window of twenty, so the cost of a
    window is that tick price times the ticks the agent was there for.
    """
    rules = life_rules(reader)

    encoded = pc.dictionary_encode(table["agent_id"]).combine_chunks()
    codes = encoded.indices.to_numpy(zero_copy_only=False)
    names = encoded.dictionary.to_pylist()

    adulthood = np.array(
        [who["adulthood"].get(name, rules["childhood"]) for name in names],
        dtype=np.int64,
    )

    ages = table["age"].to_numpy(zero_copy_only=False).astype(np.int64)
    steps = table["steps"].to_numpy(zero_copy_only=False).astype(np.float64)

    grown = ages - adulthood[codes]
    aged = np.zeros(len(ages), dtype=np.float64)

    if rules["every"] > 0 and rules["amount"]:
        aged = np.maximum(grown, 0) // rules["every"] * rules["amount"]

    per_tick = rules["base"] + np.where(grown >= 0, aged, 0.0)

    return per_tick * steps


def keep_agents(who, min_steps, max_steps):
    """Which agents a filter leaves in, by how long they ended up living."""
    lifespan = who["lifespan"]

    def long_enough(agent_id):
        lived = lifespan.get(agent_id)

        if lived is None:
            return min_steps in (None, 0)

        if min_steps is not None and lived < min_steps:
            return False

        if max_steps is not None and lived > max_steps:
            return False

        return True

    return {agent_id for agent_id in who["born"] if long_enough(agent_id)}


def by_agent(table, who, allowed, cohort):
    """
    Which rows of a per-agent table a filter leaves in, as one boolean array.

    The agent column is dictionary-encoded first, so every lookup happens
    once per agent instead of once per row: a long run has hundreds of
    thousands of update rows and a chart that has to be redrawn while the
    run is going cannot afford a dictionary lookup on each of them.

    A row is a child's row while the agent's age is below the age its
    childhood ended at - the same comparison `Life.is_child` makes.
    """
    encoded = pc.dictionary_encode(table["agent_id"]).combine_chunks()
    codes = encoded.indices.to_numpy(zero_copy_only=False)
    names = encoded.dictionary.to_pylist()

    keep = np.ones(len(codes), dtype=bool)

    if allowed is not None:
        keep &= np.array([name in allowed for name in names], dtype=bool)[codes]

    if cohort in ("child", "adult"):
        childhood = who["childhood"]
        adulthood = np.array(
            [who["adulthood"].get(name, childhood) for name in names], dtype=np.int64
        )
        child = ages_of(table, who, names, codes) < adulthood[codes]
        keep &= child if cohort == "child" else ~child

    return keep


def ages_of(table, who, names, codes):
    """
    How old each row's agent was when the row was written.

    A per-window row carries its own age. An update row does not - but it
    carries the step it happened on, and an age is that step minus the
    agent's birth.
    """
    if "age" in table.schema.names:
        return table["age"].to_numpy(zero_copy_only=False).astype(np.int64)

    born = np.array([who["born"].get(name, 0) for name in names], dtype=np.int64)

    return table["step"].to_numpy(zero_copy_only=False).astype(np.int64) - born[codes]


def slots_for(episodes, order):
    """
    Which place on the chart's episode axis each row belongs to.

    Two sessions of one world can honestly claim the same episode number -
    a world resumed from an older checkpoint replays it - and the axis holds
    one column per row of the population table, so the later session wins
    the slot, exactly as it does in the unfiltered chart.
    """
    order = np.asarray(order, dtype=np.int64)
    lookup = np.full(int(order.max()) + 2, -1, dtype=np.int64)
    lookup[order] = np.arange(len(order))

    episodes = np.asarray(episodes, dtype=np.int64)
    episodes = np.clip(episodes, 0, len(lookup) - 1)

    return lookup[episodes]


def sums_per_slot(slots, values, keep, size):
    return np.bincount(slots[keep], weights=values[keep], minlength=size)[:size]


def means_per_slot(slots, values, keep, size):
    """A mean per slot, and None where the filter left the slot empty."""
    real = keep & ~np.isnan(values)
    totals = np.bincount(slots[real], weights=values[real], minlength=size)[:size]
    counts = np.bincount(slots[real], minlength=size)[:size]

    return [
        float(total / count) if count else None
        for total, count in zip(totals, counts)
    ]


# -----------------------------
# CHARTS
# -----------------------------
def column(table, name):
    return table[name].to_pylist() if name in table.schema.names else []


def rewards(reader, cohort="all", min_steps=None, max_steps=None, leak=False):
    """
    Every kind of reward on one chart, per logging window.

    env is what the world paid, intrinsic is what curiosity added, shaped
    is what the networks actually learned from - the gap between the first
    and the last is the whole story of how much of this run is curiosity.

    Unfiltered, the numbers come straight off the population table - one
    row per window, the cheapest read in the log. A filter turns the same
    chart into a question about a part of the population, and then the
    per-agent windows are added up instead. Births and deaths always count
    the whole world: an event belongs to the world, not to a cohort.

    `leak` adds a fourth line: what being alive COST the population that
    window, as a negative number, so what came in and what went out are read
    on one axis. It is computed per agent and is not free, so it is only
    computed when the chart is actually showing it.
    """
    population = reader.episode_population()
    filtered = cohort != "all" or min_steps is not None or max_steps is not None

    out = {
        "episodes": column(population, "episode"),
        "steps": column(population, "step_end"),
        "env": column(population, "env_reward"),
        "intrinsic": column(population, "intrinsic_reward"),
        "shaped": column(population, "shaped_reward"),
        "agents": column(population, "agents"),
        "births": column(population, "births"),
        "deaths": column(population, "deaths"),
        "sessions": column(population, "session"),
        "cohort": cohort,
        "filtered": False,
        "leak": None,
    }

    if not (filtered or leak) or not out["episodes"]:
        return out

    windows = reader.episode_agents()

    if windows.num_rows == 0:
        return out

    who = cohorts(reader)
    allowed = keep_agents(who, min_steps, max_steps)
    keep = by_agent(windows, who, allowed, cohort)

    order = out["episodes"]
    size = len(order)
    slots = slots_for(windows["episode"].to_numpy(zero_copy_only=False), order)
    inside = slots >= 0
    keep &= inside

    def summed(name):
        values = windows[name].to_numpy(zero_copy_only=False).astype(np.float64)
        return sums_per_slot(slots, values, keep, size).tolist()

    if leak:
        spent = sums_per_slot(slots, leak_per_row(reader, windows, who), keep, size)
        out["leak"] = (-spent).tolist()

    if not filtered:
        return out

    out.update({
        "env": summed("env_reward"),
        "intrinsic": summed("intrinsic_reward"),
        "shaped": summed("shaped_reward"),
        "agents": np.bincount(slots[keep], minlength=size)[:size].tolist(),
        "filtered": True,
    })

    return out


def learning(reader, cohort="all", min_steps=None, max_steps=None):
    """
    What the gradient did, per window.

    Unfiltered this is the population row again. Filtered, it is the update
    table: an update carries the agent and the step it happened on, and an
    agent's age on that step is the step minus its birth - which is all a
    cohort needs to be told apart.
    """
    population = reader.episode_population()
    filtered = cohort != "all" or min_steps is not None or max_steps is not None

    out = {
        "episodes": column(population, "episode"),
        "loss": column(population, "mean_loss"),
        "td_error": column(population, "mean_td_error"),
        "updates": column(population, "updates"),
        "epsilon": column(population, "mean_epsilon"),
        "curiosity_beta": column(population, "mean_curiosity_beta"),
        "sessions": column(population, "session"),
        "cohort": cohort,
        "filtered": False,
    }

    if not filtered or not out["episodes"]:
        return out

    table = reader.updates()

    if table.num_rows == 0:
        return out

    who = cohorts(reader)
    allowed = keep_agents(who, min_steps, max_steps)
    keep = by_agent(table, who, allowed, cohort)

    order = out["episodes"]
    size = len(order)

    # An update lands in the window that was open on its step.
    ends = np.asarray(column(population, "step_end"), dtype=np.int64)
    steps = table["step"].to_numpy(zero_copy_only=False).astype(np.int64)
    slots = np.clip(np.searchsorted(ends, steps, side="left"), 0, size - 1)

    def averaged(name):
        values = table[name].to_numpy(zero_copy_only=False).astype(np.float64)
        return means_per_slot(slots, values, keep, size)

    out.update({
        "loss": averaged("loss"),
        "td_error": averaged("td_error"),
        "epsilon": averaged("epsilon"),
        "curiosity_beta": averaged("curiosity_beta"),
        "updates": np.bincount(slots[keep], minlength=size)[:size].tolist(),
        "filtered": True,
    })

    return out


def heatmap(reader, recent_share=0.2):
    """
    How often a cell of the map had a body standing on it.

    Read from the world snapshots, not from the step table: the snapshots
    are every `world_snapshot_every`-th tick of every agent, which is tens
    of thousands of rows instead of millions, and a heat map of where a
    population lives does not get truer by counting every tick of it.

    Two grids come back, because they answer different questions: `all` is
    the whole run, `recent` only its last fifth - a population that has
    just walked into the corners looks exactly like one that never left
    the middle, if you only ever add the two up.
    """
    table = reader.world_agents()
    size = world_size(reader)

    if table.num_rows == 0 or size <= 0:
        return {"size": 0, "all": [], "recent": [], "steps": [], "samples": 0}

    step = table["step"].to_numpy()
    x = table["x"].to_numpy().astype(int)
    y = table["y"].to_numpy().astype(int)

    inside = (x >= 0) & (x < size) & (y >= 0) & (y < size)
    first, last = int(step.min()), int(step.max())
    from_step = last - int((last - first) * recent_share)

    def grid(mask):
        counts = np.zeros((size, size), dtype=np.int64)
        np.add.at(counts, (y[mask], x[mask]), 1)
        return counts.tolist()

    return {
        "size": size,
        "all": grid(inside),
        "recent": grid(inside & (step >= from_step)),
        "steps": [first, last],
        "recent_from": from_step,
        "samples": int(inside.sum()),
    }


def world_size(reader):
    """The side of the map, as the run that wrote this log had it."""
    for session in reversed(reader.sessions):
        size = (session.get("config") or {}).get("world", {}).get("size")

        if size:
            return int(size)

    return 0


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


def agent(reader, agent_id):
    """
    One agent, whole: where it came from, what it was made of, what it
    earned, and every cell it ever stood on.

    The reward is given TWICE and labelled both times, because the two
    numbers answer different questions: `env` is what the world paid this
    body, `shaped` is what its network actually learned from - the world
    plus its own curiosity. A single "reward" would quietly be one of them.

    The heat map is this agent's own, read from the step table with a filter
    instead of from the world snapshots: one body's path through a few
    thousand ticks is too thin a thing to sample. That read costs a couple
    of seconds on a long run, and it is the only place in the panel that
    touches the step table at all.
    """
    births = reader.births()
    row = None

    if births.num_rows:
        for candidate in births.to_pylist():
            if candidate["agent_id"] == agent_id:
                row = candidate
                break

    if row is None:
        raise KeyError(agent_id)

    death = None

    for candidate in reader.deaths().to_pylist():
        if candidate["agent_id"] == agent_id:
            death = candidate
            break

    who = cohorts(reader)
    children = who["children"].get(agent_id, [])

    # When each child arrived, on the same axis the agent's life is drawn on:
    # a birth is the loudest thing that happens to a body that is not its
    # death, and it should be visible next to what the body earned.
    born = {}

    if births.num_rows:
        born = dict(zip(births["agent_id"].to_pylist(), births["step"].to_pylist()))

    population = reader.episode_population()
    ends = np.asarray(column(population, "step_end"), dtype=np.int64)
    numbers = column(population, "episode")

    def episode_of(step):
        if not len(ends):
            return None

        slot = int(np.searchsorted(ends, step, side="left"))

        return numbers[min(slot, len(numbers) - 1)]

    arrivals = [
        {"id": child, "step": born[child], "episode": episode_of(born[child])}
        for child in children
        if child in born
    ]

    windows = reader.episode_agents()
    earned = {"env": 0.0, "intrinsic": 0.0, "shaped": 0.0}
    steps_logged = 0
    last_age = None
    last_energy = None

    # Its whole life, window by window: the same three rewards the world
    # chart draws, plus what it was carrying and how much of its choosing
    # was still random.
    series = {
        "episodes": [], "steps": [], "env": [], "intrinsic": [], "shaped": [],
        "energy": [], "age": [], "epsilon": [], "curiosity_beta": [],
    }

    if windows.num_rows:
        table = windows.to_pydict()

        for index, owner in enumerate(table["agent_id"]):
            if owner != agent_id:
                continue

            earned["env"] += table["env_reward"][index]
            earned["intrinsic"] += table["intrinsic_reward"][index]
            earned["shaped"] += table["shaped_reward"][index]
            steps_logged += table["steps"][index]
            last_age = table["age"][index]
            last_energy = table["energy"][index]

            series["episodes"].append(table["episode"][index])
            series["steps"].append(table["steps"][index])
            series["env"].append(table["env_reward"][index])
            series["intrinsic"].append(table["intrinsic_reward"][index])
            series["shaped"].append(table["shaped_reward"][index])
            series["energy"].append(table["energy"][index])
            series["age"].append(table["age"][index])
            series["epsilon"].append(table["epsilon"][index])
            series["curiosity_beta"].append(table["curiosity_beta"][index])

    return {
        "id": agent_id,
        "index": row["index"],
        "parents": row["parents"],
        "birth_step": row["step"],
        "energy_at_birth": row["energy"],
        "genotype": json.loads(row["genotype_json"] or "null"),
        "phenotype": {
            name[len("phen_"):]: value
            for name, value in row.items()
            if name.startswith("phen_")
        },
        "alive": death is None,
        "death_step": death["death_step"] if death else None,
        "lifespan": death["lifespan"] if death else last_age,
        "cause_of_death": death["cause_of_death"] if death else None,
        "cumulative_reward": death["cumulative_reward"] if death else None,
        "children": children,
        "arrivals": arrivals,
        "offspring": len(children),
        "childhood_ended_at": who["adulthood"].get(agent_id, who["childhood"]),
        "childhood_length": who["childhood"],
        "bred_at": None if agent_id not in who["adulthood"] else (
            who["adulthood"][agent_id] if who["adulthood"][agent_id] < who["childhood"] else None
        ),
        "reward": earned,
        "series": series,
        "steps_logged": steps_logged,
        "last_age": last_age,
        "last_energy": last_energy,
        "heat": agent_heatmap(reader, agent_id),
    }


def agent_heatmap(reader, agent_id):
    """Where one body walked: a count per cell, out of its own step rows."""
    size = world_size(reader)
    path = os.path.join(reader.path, "steps")

    if size <= 0 or not os.path.isdir(path) or not os.listdir(path):
        return {"size": 0, "grid": [], "samples": 0}

    table = ds.dataset(path, format="parquet", schema=log_schema.STEPS).to_table(
        columns=["x", "y"],
        filter=ds.field("agent_id") == agent_id,
    )

    counts = np.zeros((size, size), dtype=np.int64)

    if table.num_rows:
        x = table["x"].to_numpy().astype(int)
        y = table["y"].to_numpy().astype(int)
        inside = (x >= 0) & (x < size) & (y >= 0) & (y < size)
        np.add.at(counts, (y[inside], x[inside]), 1)

    return {"size": size, "grid": counts.tolist(), "samples": int(counts.sum())}


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


def worlds_by_pid(logs_dir, live_dir):
    """
    Which world each launched process is writing, by pid.

    The queue asks this on every refresh, so it reads the handful of
    heartbeat files and matches them to folder names instead of opening
    every run.json in logs/.
    """
    if not os.path.isdir(live_dir) or not os.path.isdir(logs_dir):
        return {}

    folders = os.listdir(logs_dir)
    found = {}

    for name in os.listdir(live_dir):
        if not name.endswith(".json"):
            continue

        world_id = name[: -len(".json")]
        live = read_live(live_dir, world_id)

        if not live or live.get("pid") is None:
            continue

        # A log folder is the world id, plus the run's label if it had one.
        folder = next(
            (
                folder for folder in folders
                if folder == world_id or folder.startswith(f"{world_id}_")
            ),
            None,
        )

        if folder:
            found[live["pid"]] = folder

    return found


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
