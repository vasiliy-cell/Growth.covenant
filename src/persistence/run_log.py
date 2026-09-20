import hashlib
import json
import os
import platform
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from src.persistence import log_schema
from src.persistence.checkpoint import git_commit


class PartWriter:
    """
    One table, written as a folder of finished files.

    Parquet cannot be appended to a row at a time: a writer holds the file
    open and only puts the footer on at close, so a run that is killed
    leaves a file no reader will open. So a table is a FOLDER of parts,
    each one closed and complete the moment it is written. A crash costs
    the rows still in memory and nothing that is already on disk.

    Each part is written to a temporary name and renamed into place, so a
    crash during the write cannot leave a half file for a reader to trip
    over either.
    """

    def __init__(self, directory, schema, session, max_rows=50000):
        self.directory = directory
        self.schema = schema
        self.session = session
        self.max_rows = max_rows

        self.rows = []
        self.parts = 0
        self.total = 0

    def append(self, row):
        self.rows.append(row)
        self.total += 1

        if len(self.rows) >= self.max_rows:
            self.flush()

    def flush(self):
        """Closes the current part. Returns its path, or None if empty."""
        if not self.rows:
            return None

        os.makedirs(self.directory, exist_ok=True)

        table = pa.Table.from_pylist(self.rows, schema=self.schema)

        name = f"part-s{self.session:03d}-{self.parts:06d}.parquet"
        path = os.path.join(self.directory, name)
        temporary = path + ".writing"

        pq.write_table(table, temporary, compression="zstd")
        os.replace(temporary, path)

        self.rows = []
        self.parts += 1

        return path


class RunLog:
    """
    Everything one world writes down, for as long as that world exists.

    THE FOLDER IS THE WORLD, not the process. A run continued from a
    checkpoint writes into the same folder as the run it continues,
    because it is the same world and the same life story - it only opens a
    new SESSION, and run.json lists them with the steps and episodes each
    one covered. Continue a world ten times and run.json has ten entries.

    Two halves, and they are meant to be read in this order:

      run.json - how to repeat this: seed, config, commit, schema version,
        which species of DNA and which genes, how long an episode is, the
        versions of the libraries it ran on,
      the tables - what happened: steps, gradient updates, episode
        summaries, births and deaths, snapshots of the map.

    Nothing here deletes anything, ever. A log is deleted by a human who
    has decided the experiment is over (scripts/logs.py archives one with
    a note attached, which is the polite way to need the space back).
    """

    def __init__(
        self,
        directory,
        world_id,
        run_id,
        seed,
        episode_length,
        config,
        species,
        gene_names,
        label=None,
        resumed_from=None,
        max_rows=50000,
        world_snapshot_every=100,
        rng_world_every=1,
        rng_agents_every=100,
    ):
        self.path = self.folder_for(directory, world_id, label)
        os.makedirs(self.path, exist_ok=True)

        self.world_id = world_id
        self.run_id = run_id
        self.episode_length = episode_length
        self.world_snapshot_every = world_snapshot_every
        self.rng_world_every = rng_world_every
        self.rng_agents_every = rng_agents_every

        self.header_path = os.path.join(self.path, "run.json")
        self.header = self._read_header()
        self.session = len(self.header["sessions"])

        self.header["sessions"].append({
            "session": self.session,
            "run_id": run_id,
            "seed": seed,
            "commit": git_commit(),
            "started_at": time.time(),
            "resumed_from": resumed_from,
            "config": config,
            "from_step": None,
            "to_step": None,
            "from_episode": None,
            "to_episode": None,
        })

        if self.session == 0:
            self.header.update({
                "schema_version": log_schema.SCHEMA_VERSION,
                "world_id": world_id,
                "label": label,
                "created_at": time.time(),
                "episode_length": episode_length,
                "species": species,
                "genes": sorted(gene_names),
                "config": config,
                "commit": git_commit(),
                "versions": {
                    "python": platform.python_version(),
                    "numpy": np.__version__,
                    "pyarrow": pa.__version__,
                    "torch": self._torch_version(),
                },
            })

        self.births_schema = log_schema.births(gene_names)

        self.tables = {
            "steps": self._table("steps", log_schema.STEPS, max_rows),
            "updates": self._table("updates", log_schema.UPDATES, max_rows),
            "episode_agents": self._table(
                "episodes/agents", log_schema.EPISODE_AGENTS, max_rows
            ),
            "episode_population": self._table(
                "episodes/population", log_schema.EPISODE_POPULATION, max_rows
            ),
            "births": self._table("events/births", self.births_schema, max_rows),
            "deaths": self._table("events/deaths", log_schema.DEATHS, max_rows),
            "world_grid": self._table("world/grid", log_schema.WORLD_GRID, max_rows),
            "world_agents": self._table(
                "world/agents", log_schema.WORLD_AGENTS, max_rows
            ),
        }

        self.rng_directory = os.path.join(self.path, "rng")

        # The window being accumulated, and the run-long rolling hash that
        # makes two runs of one seed comparable with a grep.
        self.episode = 0
        self.first_step = None
        self.last_step = None
        self._fingerprint = hashlib.blake2b(digest_size=8)
        self._start_window(time.time())

        self._write_header()

    # -----------------------------
    # WHERE IT ALL LIVES
    # -----------------------------
    @staticmethod
    def folder_for(directory, world_id, label=None):
        """
        The folder of a world: found by its id, named with its label.

        A continuation only knows the world id, never the label somebody
        typed months ago, so the id is the key and the label is decoration
        on the end of it.
        """
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                if name == world_id or name.startswith(world_id + "_"):
                    return os.path.join(directory, name)

        if label:
            safe = "".join(
                character if character.isalnum() or character in "-_" else "-"
                for character in label
            ).strip("-")

            if safe:
                return os.path.join(directory, f"{world_id}_{safe}")

        return os.path.join(directory, world_id)

    def _table(self, name, schema, max_rows):
        return PartWriter(
            os.path.join(self.path, *name.split("/")),
            schema,
            session=self.session,
            max_rows=max_rows,
        )

    @staticmethod
    def _torch_version():
        try:
            import torch

            return torch.__version__
        except ImportError:
            return None

    # -----------------------------
    # HEADER
    # -----------------------------
    def _read_header(self):
        if os.path.isfile(self.header_path):
            with open(self.header_path, encoding="utf-8") as handle:
                return json.load(handle)

        return {"sessions": []}

    def _write_header(self):
        """Rewritten whole, atomically: it is small and always current."""
        temporary = self.header_path + ".writing"

        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self.header, handle, indent=2, default=_jsonable)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, self.header_path)

    @property
    def _session(self):
        return self.header["sessions"][self.session]

    # -----------------------------
    # STEP
    # -----------------------------
    def log_step(self, step, agent_id, position, action, env_reward,
                 intrinsic_reward, shaped_reward, energy, age):
        now = time.time()

        row = {
            "step": step,
            "session": self.session,
            "wall_clock": now,
            "agent_id": agent_id,
            "x": position[0],
            "y": position[1],
            "action": action,
            "env_reward": env_reward,
            "intrinsic_reward": intrinsic_reward,
            "shaped_reward": shaped_reward,
            "energy": energy,
            "age": age,
        }

        self.tables["steps"].append(row)
        self._count_step(step, agent_id, env_reward, intrinsic_reward, shaped_reward)

        # Everything a step decided, in the order it was decided - two runs
        # of one seed print the same digest, and the first window where
        # they differ is where they diverged.
        self._fingerprint.update(
            f"{step}|{agent_id}|{action}|{env_reward}|{shaped_reward}"
            f"|{position[0]},{position[1]}".encode("utf-8")
        )

    def _count_step(self, step, agent_id, env_reward, intrinsic_reward, shaped_reward):
        if self.first_step is None:
            self.first_step = step
            if self._session["from_step"] is None:
                self._session["from_step"] = step
                self._session["from_episode"] = self.episode

        self.last_step = step

        window = self._window_agents.setdefault(agent_id, _empty_sums())
        window["steps"] += 1
        window["env_reward"] += env_reward
        window["intrinsic_reward"] += intrinsic_reward
        window["shaped_reward"] += shaped_reward

        self._window["steps"] += 1
        self._window["env_reward"] += env_reward
        self._window["intrinsic_reward"] += intrinsic_reward
        self._window["shaped_reward"] += shaped_reward

    # -----------------------------
    # LEARNING
    # -----------------------------
    def log_update(self, step, agent_id, training_step, metrics,
                   curiosity_beta, epsilon, buffer_size):
        self.tables["updates"].append({
            "step": step,
            "session": self.session,
            "wall_clock": time.time(),
            "agent_id": agent_id,
            "training_step": training_step,
            "loss": metrics["loss"],
            "grad_norm": metrics["grad_norm"],
            "td_error": metrics["td_error"],
            "target_q": metrics["target_q"],
            "q_prediction": metrics["q_prediction"],
            "curiosity_beta": curiosity_beta,
            "epsilon": epsilon,
            "buffer_size": buffer_size,
        })

        self._window["updates"] += 1
        self._window["loss"] += metrics["loss"]
        self._window["td_error"] += abs(metrics["td_error"])

    # -----------------------------
    # LIFE AND DEATH
    # -----------------------------
    def log_birth(self, step, agent_id, index, parents, energy,
                  genotype, phenotype):
        row = {
            "step": step,
            "session": self.session,
            "wall_clock": time.time(),
            "agent_id": agent_id,
            "index": index,
            "parents": list(parents or []),
            "energy": energy,
            "genotype_json": json.dumps(genotype, default=_jsonable, sort_keys=True),
        }

        for name in self.births_schema.names:
            if name.startswith("phen_"):
                row[name] = _number(phenotype.get(name[len("phen_"):]))

        self.tables["births"].append(row)
        self._window["births"] += 1

    def log_death(self, step, record):
        """record: the whole life, as env._reap hands it over."""
        self.tables["deaths"].append({
            "step": step,
            "session": self.session,
            "wall_clock": time.time(),
            "agent_id": record["agent_id"],
            "index": record["index"],
            "parents": list(record["parents"] or []),
            "birth_step": record["birth_step"],
            "death_step": record["death_step"],
            "lifespan": record["lifespan"],
            "cumulative_reward": record["cumulative_reward"],
            "num_offspring": record["num_offspring"],
            "cause_of_death": record["cause_of_death"],
            "energy": record["energy"],
            "genotype_json": json.dumps(
                record.get("genotype"), default=_jsonable, sort_keys=True
            ),
        })

        self._window["deaths"] += 1

    # -----------------------------
    # THE MAP
    # -----------------------------
    def log_world(self, step, grid, positions):
        """
        The map as objects only, plus the bodies standing on it as their
        own rows. Painting the agents into the grid would hide whatever
        cell each of them is standing on, and that cell is the thing you
        came to the snapshot to see.
        """
        now = time.time()
        grid = np.asarray(grid, dtype=np.int8)

        self.tables["world_grid"].append({
            "step": step,
            "session": self.session,
            "wall_clock": now,
            "size": grid.shape[0],
            "grid": grid.reshape(-1).tolist(),
        })

        for agent_id, (x, y) in positions.items():
            self.tables["world_agents"].append({
                "step": step,
                "session": self.session,
                "agent_id": agent_id,
                "x": x,
                "y": y,
            })

    def should_snapshot(self, step):
        return (
            self.world_snapshot_every > 0
            and step % self.world_snapshot_every == 0
        )

    # -----------------------------
    # RNG
    # -----------------------------
    def log_rng(self, rng, step):
        """
        The world's streams every window, the agents' rarely.

        An agent's streams are about 16 KB a snapshot and they are random
        numbers, so they do not compress. Fifty agents every window would
        be gigabytes of a log nobody reads - and the checkpoints carry the
        full state of every stream anyway.
        """
        if self.rng_world_every > 0 and self.episode % self.rng_world_every == 0:
            self._write_rng("world", rng.state("world"), step)

        if self.rng_agents_every > 0 and self.episode % self.rng_agents_every == 0:
            self._write_rng("agents", rng.state("agents"), step)

    def _write_rng(self, name, state, step):
        os.makedirs(self.rng_directory, exist_ok=True)

        record = {
            "session": self.session,
            "episode": self.episode,
            "step": step,
            "seed": state["seed"],
            "streams": state["streams"],
        }

        with open(
            os.path.join(self.rng_directory, f"{name}.jsonl"), "a", encoding="utf-8"
        ) as handle:
            handle.write(json.dumps(record, default=_jsonable) + "\n")
            handle.flush()

    # -----------------------------
    # WINDOW
    # -----------------------------
    def _start_window(self, now):
        self._window_started = now
        self._window_agents = {}
        self._window = _empty_sums()
        self.first_step = None

    def end_episode(self, step, agents, non_empty_ratio):
        """
        Closes the logging window: one row per agent, one for everybody.

        agents: {agent_id: {"epsilon", "curiosity_beta", "energy", "age"}}
        as the minds stand at the end of the window.

        Returns the population row, which is also what the terminal prints.
        """
        now = time.time()
        start = self.first_step if self.first_step is not None else step

        for agent_id, sums in self._window_agents.items():
            state = agents.get(agent_id, {})

            self.tables["episode_agents"].append({
                "episode": self.episode,
                "session": self.session,
                "step_start": start,
                "step_end": step,
                "agent_id": agent_id,
                "steps": sums["steps"],
                "env_reward": sums["env_reward"],
                "intrinsic_reward": sums["intrinsic_reward"],
                "shaped_reward": sums["shaped_reward"],
                "epsilon": _number(state.get("epsilon")),
                "curiosity_beta": _number(state.get("curiosity_beta")),
                "energy": _number(state.get("energy")),
                "age": int(state.get("age") or 0),
            })

        epsilons = [
            state["epsilon"] for state in agents.values()
            if state.get("epsilon") is not None
        ]
        betas = [
            state["curiosity_beta"] for state in agents.values()
            if state.get("curiosity_beta") is not None
        ]
        updates = self._window["updates"]

        summary = {
            "episode": self.episode,
            "session": self.session,
            "step_start": start,
            "step_end": step,
            "wall_clock": now,
            "duration": now - self._window_started,
            "agents": len(agents),
            "births": int(self._window["births"]),
            "deaths": int(self._window["deaths"]),
            "steps": int(self._window["steps"]),
            "env_reward": self._window["env_reward"],
            "intrinsic_reward": self._window["intrinsic_reward"],
            "shaped_reward": self._window["shaped_reward"],
            "updates": int(updates),
            "mean_loss": self._window["loss"] / updates if updates else None,
            "mean_td_error": self._window["td_error"] / updates if updates else None,
            "mean_epsilon": sum(epsilons) / len(epsilons) if epsilons else None,
            "mean_curiosity_beta": sum(betas) / len(betas) if betas else None,
            "non_empty_ratio": non_empty_ratio,
            "fingerprint": self._fingerprint.hexdigest(),
        }

        self.tables["episode_population"].append(summary)

        self.episode += 1
        self._session["to_step"] = step
        self._session["to_episode"] = self.episode
        self._start_window(now)

        return summary

    # -----------------------------
    # DISK
    # -----------------------------
    def flush(self):
        """Closes a part of every table, so a crash costs only what is
        still in memory."""
        for table in self.tables.values():
            table.flush()

        if self.last_step is not None:
            self._session["to_step"] = self.last_step

        self._write_header()

    def close(self):
        self._session["finished_at"] = time.time()
        self.flush()

    def __repr__(self):
        return (
            f"RunLog(path={self.path}, session={self.session}, "
            f"episode={self.episode})"
        )


def _empty_sums():
    return {
        "steps": 0,
        "env_reward": 0.0,
        "intrinsic_reward": 0.0,
        "shaped_reward": 0.0,
        "updates": 0,
        "loss": 0.0,
        "td_error": 0.0,
        "births": 0,
        "deaths": 0,
    }


def _number(value):
    """None stays None - a missing value is not a zero."""
    return None if value is None else float(value)


def _jsonable(value):
    """numpy numbers are not json, and a genotype is full of them."""
    if isinstance(value, np.generic):
        return value.item()

    if isinstance(value, np.ndarray):
        return value.tolist()

    return str(value)
