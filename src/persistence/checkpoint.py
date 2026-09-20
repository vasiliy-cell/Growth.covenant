import subprocess
from datetime import datetime

# Bumped whenever the shape of a record changes in a way that makes an
# older file unreadable. A refusal with a version number in it is a far
# better afternoon than a resume that silently reads garbage.
SCHEMA_VERSION = 2


def git_commit():
    """The commit this run was made by, or None outside a git checkout."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except (OSError, subprocess.CalledProcessError):
        return None


class Checkpoint:
    """
    Everything a run needs to carry on being itself.

    Not a model file: a model file answers "what did it learn", a
    checkpoint answers "where was everybody and what happens next". It
    holds the world (the map as it has been eaten, the refill clock), the
    population (positions, energy, age, DNA), one full mind per agent
    (weights, target net and its counter, Adam, epsilon, curiosity visit
    counts, optionally the replay buffer) and the state of every named rng
    stream.

    It also holds the config and the git commit it was made by. A resume
    reads the live config, not this one - that is how a run is continued
    with a longer childhood or a cheaper leak - but when the two differ the
    runner says so, because an experiment whose rules changed halfway
    through and never said so is a lost experiment.

    RESTORE ORDER IS PART OF THE FORMAT. The rng states go back LAST,
    after the world is rebuilt and every network exists, because building
    things is itself something that can draw. Put the streams back first
    and the construction walks them forward again, and a run resumes a few
    numbers off from where it was saved - the kind of bug that looks like
    bad luck for a week.
    """

    # -----------------------------
    # CAPTURE
    # -----------------------------
    @staticmethod
    def capture(env, brains, rng, run, config, with_replay=True):
        """
        run: what the runner knows and the world does not - run id, seed,
             the global step and the logging window we are in.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "commit": git_commit(),
            "config": config,
            "run": dict(run),
            "rng": rng.state(),
            "env": env.state(),
            "brains": {
                agent_id: brain.full_state(with_replay=with_replay)
                for agent_id, brain in brains.items()
            },
            "has_replay": with_replay,
        }

    # -----------------------------
    # RESTORE
    # -----------------------------
    @staticmethod
    def restore(record, env, make_brains, rng):
        """
        Puts a captured run back into a freshly built one.

        env must be built but untouched - no start(). The minds cannot be
        built before the world is back (the size of a network input comes
        from an observation), so they are built here, through make_brains,
        which is also what keeps the whole order in one place.

        Returns (run, observations, brains).
        """
        Checkpoint.check(record, env)

        # 1. The world, exactly as it was eaten.
        observations = env.restore(record["env"])

        # 2. The minds, built to the shape the DNA was read into back then
        #    - the phenotypes came back with the world, so nothing is read
        #    a second time and no network comes out a different size.
        brains = make_brains(observations)

        phenotypes = {
            agent_id: env.make_phenotype(agent_id)
            for agent_id in env.agents.ids()
        }
        brains.sync(env.agents, phenotypes)

        # 3. What those minds had become.
        for agent_id, state in record["brains"].items():
            if agent_id in brains:
                brains.get(agent_id).load_state(state)

        # 4. The streams, LAST: everything above is construction, and
        #    construction is allowed to draw.
        rng.load_state(record["rng"])

        return dict(record["run"]), observations, brains

    # -----------------------------
    # READING A RECORD
    # -----------------------------
    @staticmethod
    def check(record, env):
        version = record.get("schema_version")

        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Checkpoint schema {version} cannot be read by this "
                f"version of the project (expected {SCHEMA_VERSION})"
            )

        saved_species = record["env"]["species"]
        live_species = env.species_name

        if saved_species != live_species:
            raise ValueError(
                f"This checkpoint was written by {saved_species} and is "
                f"being resumed as {live_species}: a genotype only means "
                f"something to the species that wrote it"
            )

    @staticmethod
    def config_drift(record, config):
        """
        Which top-level config sections changed since the checkpoint.

        Not an error - continuing a run with different rules is a thing you
        may well want. It is only something nobody should discover later
        from a graph that bends for no reason.
        """
        saved = record.get("config") or {}

        sections = set(saved) | set(config)

        return sorted(
            section for section in sections
            if saved.get(section) != config.get(section)
        )

    @staticmethod
    def describe(record):
        """One line for a human choosing what to resume."""
        run = record["run"]
        agents = len(record["env"]["population"]["agents"])

        return (
            f"run {run['run_id']} | step {run['step']} | "
            f"{agents} agents | seed {run['seed']} | "
            f"{record['env']['species']} | saved {record['saved_at']}"
            + ("" if record.get("has_replay") else " | no replay buffers")
        )
