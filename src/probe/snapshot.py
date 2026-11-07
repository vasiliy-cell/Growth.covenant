import os
from datetime import datetime

from src.persistence.checkpoint import git_commit
from src.persistence.checkpoint_store import CheckpointStore

# Bumped whenever the shape of a snapshot changes in a way that makes an
# older file unreadable.
SCHEMA_VERSION = 1

# Under the world's own log folder: probe/snapshots/ holds what the run
# copied, probe/step_<step>/<agent_id>/ one log per probe world.
PROBE_DIR = "probe"
SNAPSHOTS_DIR = "snapshots"


class ProbeRecorder:
    """
    Every `every` episodes, a copy of Q living adults - and nothing else.

    A snapshot is a passive record. It does not touch the map, it does not
    touch a body, and the only stream it draws from is its own
    (`rng.python("probe")`), so a run with snapshots takes exactly the
    steps the same run takes without them.

    What it keeps of an agent is what that agent needs to exist again in a
    probe world (src/probe/runner.py): the weights of its policy net, its
    phenotype (and the genotype, for the record), and where its epsilon
    and curiosity strength had got to. Not its energy, age or visit
    counts: a probe world has no metabolism and an untouched map.

    Snapshots fall on the grid k*N of the world's episodes. Fewer adults
    than Q: wait `rescue` episodes and try ONCE more, then take everybody
    there is - or nobody, if there is nobody. The grid does not move
    because of a rescue: the next snapshot is still at (k+1)*N.

    A rescue that is still waiting when the run stops is simply lost; it
    is not part of any checkpoint.
    """

    def __init__(self, directory, every, count, rescue, rng):
        self.directory = directory
        self.every = every
        self.count = count
        self.rescue = rescue
        self.rng = rng

        # The episode a rescue attempt is due at, None when none is waiting.
        self.pending = None

    @classmethod
    def from_config(cls, config, directory, rng):
        """None when snapshots are off (probe.every_episodes = 0)."""
        probe_cfg = config.get("probe") or {}
        every = int(probe_cfg.get("every_episodes") or 0)

        if every <= 0:
            return None

        missing = [
            key for key in ("agents", "rescue_episodes", "episodes")
            if probe_cfg.get(key) is None
        ]
        if missing:
            raise ValueError(f"probe.every_episodes is on but probe has no {missing}")

        count = int(probe_cfg["agents"])
        if count < 1:
            raise ValueError(f"probe.agents must be at least 1, not {count}")

        return cls(
            directory=directory,
            every=every,
            count=count,
            rescue=int(probe_cfg["rescue_episodes"]),
            rng=rng.python("probe"),
        )

    # -----------------------------
    # LOGGING WINDOW BOUNDARY
    # -----------------------------
    def end_episode(self, episode, step, env, brains, run, config):
        """
        Called once a window has closed; `episode` is how many windows the
        world has closed so far. Returns the snapshot's path, or None.
        """
        if episode % self.every == 0:
            # A rescue still waiting when the grid comes round again is
            # replaced by the grid's own attempt.
            self.pending = None
            return self._attempt(episode, step, env, brains, run, config, rescue=True)

        if self.pending == episode:
            self.pending = None
            return self._attempt(episode, step, env, brains, run, config, rescue=False)

        return None

    def _attempt(self, episode, step, env, brains, run, config, rescue):
        adults = [agent for agent in env.agents if not agent.is_child()]

        if len(adults) >= self.count:
            chosen = self.rng.sample(adults, self.count)
        elif rescue and self.rescue > 0:
            self.pending = episode + self.rescue
            print(
                f"[probe @ step {step}] {len(adults)}/{self.count} adults, "
                f"trying again at episode {self.pending}"
            )
            return None
        else:
            chosen = adults

        if not chosen:
            print(f"[probe @ step {step}] no adults, no snapshot")
            return None

        return self._write(chosen, episode, step, env, brains, run, config)

    # -----------------------------
    # RECORD
    # -----------------------------
    def _write(self, chosen, episode, step, env, brains, run, config):
        record = {
            "schema_version": SCHEMA_VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "commit": git_commit(),
            "world_id": run["world_id"],
            "seed": run["seed"],
            "step": step,
            "episode": episode,
            "episode_length": run["episode_length"],
            "config": config,
            # The world the minds were sized and raised in: a probe world
            # has to be the same size and seen through the same window.
            "size": env.size,
            "view_size": env.agents.view_size,
            "species": env.species_name,
            "evolve": env.evolve,
            "requested": self.count,
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "index": agent.index,
                    "genotype": env.genomes.get_genotype(agent.agent_id),
                    "phenotype": env.make_phenotype(agent.agent_id),
                    "policy_net": brains.get(agent.agent_id).trainer.state_dict(),
                    "epsilon": brains.get(agent.agent_id).summary()["epsilon"],
                    "curiosity_beta": brains.get(agent.agent_id).summary()["curiosity_beta"],
                }
                for agent in chosen
            ],
        }

        os.makedirs(self.directory, exist_ok=True)
        path = os.path.join(self.directory, f"step_{step:09d}.pt")
        CheckpointStore._write(record, path)

        print(
            f"[probe @ step {step}] {len(chosen)}/{self.count} adults "
            f"-> {os.path.basename(path)}"
        )

        return path
