import json
import os

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds

from src.persistence import log_schema


class RunLogReader:
    """
    Reads back what RunLog wrote, and is written in the same commit as it.

    The rule behind that: if you cannot load what you wrote, you did not
    write it. A format nobody has read back is a format that is wrong in
    some small way you will find out about in three months, with the
    experiment already run.

    A table is a folder of parquet parts, so reading one is reading a
    dataset, not a file - which is also why a run that was killed reads
    perfectly well: every part on disk is a finished file.

    Everything comes back as a pyarrow Table. It slices, filters and
    aggregates on its own, and `.to_pandas()` is there if pandas is
    installed - so the logs cost this project exactly one dependency.
    """

    TABLES = {
        "steps": ("steps", log_schema.STEPS),
        "updates": ("updates", log_schema.UPDATES),
        "episode_agents": ("episodes/agents", log_schema.EPISODE_AGENTS),
        "episode_population": ("episodes/population", log_schema.EPISODE_POPULATION),
        "deaths": ("events/deaths", log_schema.DEATHS),
        "world_grid": ("world/grid", log_schema.WORLD_GRID),
        "world_agents": ("world/agents", log_schema.WORLD_AGENTS),
    }

    def __init__(self, path):
        self.path = path

        with open(os.path.join(path, "run.json"), encoding="utf-8") as handle:
            self.header = json.load(handle)

    # -----------------------------
    # FINDING A WORLD
    # -----------------------------
    @classmethod
    def find(cls, directory="logs"):
        """
        Every world under a log directory, newest first.

        The walk is recursive because a world that belongs to a series
        lives one level down, in a folder named after it - and because
        somebody will eventually sort their logs into folders by hand,
        and should not lose them by doing so. A folder with a run.json in
        it is a world; anything else is just a folder.
        """
        if not os.path.isdir(directory):
            return []

        found = []

        for root, directories, files in os.walk(directory):
            if "run.json" in files:
                found.append(cls(root))

                # Nothing nests inside a world.
                directories[:] = []

        return sorted(found, key=lambda reader: reader.created_at, reverse=True)

    @property
    def series(self):
        return self.header.get("series")

    @property
    def world_id(self):
        return self.header.get("world_id")

    @property
    def label(self):
        return self.header.get("label")

    @property
    def created_at(self):
        return self.header.get("created_at", 0.0)

    @property
    def sessions(self):
        """Every time this world was picked up and carried on."""
        return self.header.get("sessions", [])

    @property
    def genes(self):
        return self.header.get("genes", [])

    # -----------------------------
    # TABLES
    # -----------------------------
    def table(self, name):
        folder, schema = self.TABLES[name]

        return self._read(folder, schema)

    def steps(self):
        return self.table("steps")

    def updates(self):
        return self.table("updates")

    def episode_agents(self):
        return self.table("episode_agents")

    def episode_population(self):
        return self.table("episode_population")

    def deaths(self):
        return self.table("deaths")

    def births(self):
        """The one schema that depends on the run: a column per gene."""
        return self._read("events/births", log_schema.births(self.genes))

    def world_grid(self):
        return self.table("world_grid")

    def world_agents(self):
        return self.table("world_agents")

    def _read(self, folder, schema):
        path = os.path.join(self.path, *folder.split("/"))

        if not os.path.isdir(path) or not os.listdir(path):
            # A table nothing was written to is an empty table, not a
            # missing one: a reader should never have to ask whether
            # anybody died before it can count the deaths.
            return schema.empty_table()

        return ds.dataset(path, format="parquet", schema=schema).to_table()

    # -----------------------------
    # CONVENIENCE
    # -----------------------------
    def grid_at(self, step):
        """One snapshot of the map, back in the shape it had on screen."""
        grid = self.world_grid()
        matches = grid.filter(pa.compute.equal(grid["step"], step))

        if matches.num_rows == 0:
            return None

        size = matches["size"][0].as_py()
        flat = matches["grid"][0].as_py()

        return np.array(flat, dtype=np.int8).reshape(size, size)

    def rng(self, scope="world"):
        """The rng snapshots, as they were written: one dict per window."""
        path = os.path.join(self.path, "rng", f"{scope}.jsonl")

        if not os.path.isfile(path):
            return []

        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def describe(self):
        population = self.episode_population()

        return (
            f"{os.path.basename(self.path)} | "
            f"{len(self.sessions)} session(s) | "
            f"{population.num_rows} episodes | "
            f"{self.table('steps').num_rows} step rows | "
            f"{self.deaths().num_rows} deaths"
        )

    def __repr__(self):
        return f"RunLogReader(path={self.path})"
