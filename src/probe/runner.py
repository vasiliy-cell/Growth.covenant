import glob
import os
import shutil

import numpy as np
import torch

from src.Agent.identity import new_run_id
from src.Brain.BrainManager import BrainManager
from src.environment.env import GridWorldEnv
from src.persistence.checkpoint_store import CheckpointStore
from src.persistence.run_log import RunLog
from src.probe import snapshot
from src.probe.snapshot import PROBE_DIR, SNAPSHOTS_DIR
from src.run import encode_observation
from src.utils.rng import RunRandom

# A probe world is written here first and renamed into place when it is
# whole, so a folder with a run.json in it is always a finished one.
STAGING_DIR = ".writing"


def snapshots_of(world_path):
    """Every snapshot a run left in its world's folder, oldest first."""
    return sorted(
        glob.glob(os.path.join(world_path, PROBE_DIR, SNAPSHOTS_DIR, "step_*.pt"))
    )


def run_probes(world_path):
    """
    Every agent of every snapshot of one world, one probe world each, one
    after another. A probe world that is already on disk is skipped, so
    an interrupted batch is carried on by running it again.
    """
    paths = snapshots_of(world_path)

    if not paths:
        print(f"No probe snapshots in {world_path}")
        return []

    written = []

    for path in paths:
        record = CheckpointStore.load(path)

        if record.get("schema_version") != snapshot.SCHEMA_VERSION:
            raise ValueError(
                f"Probe snapshot schema {record.get('schema_version')} cannot "
                f"be read by this version (expected {snapshot.SCHEMA_VERSION})"
            )

        directory = os.path.join(
            world_path, PROBE_DIR, f"step_{record['step']:09d}"
        )

        for entry in record["agents"]:
            folder = os.path.join(directory, entry["agent_id"])

            if os.path.isfile(os.path.join(folder, "run.json")):
                print(f"[probe] {os.path.relpath(folder, world_path)} already done")
                continue

            written.append(
                probe_world(record, entry, directory, os.path.basename(path))
            )

    return written


def probe_world(record, entry, directory, snapshot_name):
    """
    One agent, alone, in the world its run started from.

    The map is the one the run's seed generates at step 0 - untouched, not
    the map the run had eaten - and it lives by the run's own rules:
    the same cells pay the same rewards, are cleared on contact and are
    refilled on the same schedule. What is gone is the metabolism (no
    energy, leak, aging, starvation, birth: GridWorldEnv(metabolism=False))
    and the learning: the network is frozen, nothing is remembered and
    nothing is trained. Epsilon and curiosity start where the snapshot
    found them and decay every episode as they would have.

    The body takes the cell the seed's population stream gives the first
    body of the world, so every probe of one world starts on the same cell.

    It runs exactly `probe.episodes` episodes: there is no death to cut
    it short. Returns the folder of its log.
    """
    config = record["config"]
    seed = record["seed"]
    episode_length = int(record["episode_length"])
    total_steps = int(config["probe"]["episodes"]) * episode_length
    agent_id = entry["agent_id"]

    staging = os.path.join(directory, STAGING_DIR)
    # Only ever a probe world that was cut off halfway.
    shutil.rmtree(staging, ignore_errors=True)

    rng = RunRandom(seed)

    # The same belt and braces as the run itself.
    np.random.seed(seed % (2 ** 32))
    torch.manual_seed(seed % (2 ** 63))

    if bool(config.get("run", {}).get("deterministic", True)):
        torch.use_deterministic_algorithms(True, warn_only=True)

    world_cfg = config["world"]
    env = GridWorldEnv(
        size=record["size"],
        rng=rng,
        balance=world_cfg["balance"],
        refill=world_cfg.get("refill", {}),
        agent_count=1,
        run_id=record["world_id"],
        species_name=record["species"],
        view_size=record["view_size"],
        evolve=record["evolve"],
        metabolism=False,
    )

    # start() without the founders: the map from the world stream, as the
    # run generated it, and one body under the agent's own id and index.
    env.world.generate(rng=env.world_rng)
    env.agents._next_index = entry["index"]
    env.agents.spawn(1)
    env.genomes.put(agent_id, entry["genotype"])
    env.genomes.put_phenotype(agent_id, entry["phenotype"])

    observations = env.get_states()

    brains = BrainManager(
        config=config,
        obs_size=len(encode_observation(observations[agent_id])),
        action_size=len(env.get_action_space()),
        rng=rng,
    )
    brains.sync(env.agents, {agent_id: entry["phenotype"]})

    brain = brains.get(agent_id)
    brain.trainer.policy_net.load_state_dict(entry["policy_net"])
    brain.policy.epsilon = entry["epsilon"]
    brain.reward_shaping.curiosity.beta = entry["curiosity_beta"]

    logging_cfg = config.get("logging", {})
    flush_every_steps = int(logging_cfg.get("flush_every_steps", 1000))

    log = RunLog(
        directory=staging,
        world_id=agent_id,
        run_id=new_run_id(),
        seed=seed,
        episode_length=episode_length,
        config=config,
        species=record["species"],
        gene_names=list(config.get("genome", {}).get("genes", {})),
        max_rows=int(logging_cfg.get("max_rows_per_part", 50000)),
        world_snapshot_every=int(logging_cfg.get("world_snapshot_every", 100)),
        rng_world_every=int(logging_cfg.get("rng_world_every_episodes", 1)),
        rng_agents_every=int(logging_cfg.get("rng_agents_every_episodes", 100)),
        probe={
            "world_id": record["world_id"],
            "snapshot": snapshot_name,
            "step": record["step"],
            "episode": record["episode"],
            "agent_id": agent_id,
            "index": entry["index"],
            "episodes": int(config["probe"]["episodes"]),
            "epsilon": entry["epsilon"],
            "curiosity_beta": entry["curiosity_beta"],
        },
    )

    agent = env.agents.get(agent_id)

    log.log_birth(
        step=0,
        agent_id=agent_id,
        index=entry["index"],
        parents=[],
        energy=float("nan"),
        genotype=entry["genotype"],
        phenotype=entry["phenotype"],
    )

    encoded = {}

    for step in range(1, total_steps + 1):
        available_actions = env.get_available_actions()

        states = {
            agent_id: encoded[agent_id] if agent_id in encoded
            else encode_observation(observation)
            for agent_id, observation in observations.items()
        }
        encoded = {}

        actions = brains.choose_actions(states, available_actions)
        next_observations, env_rewards, info = env.step(actions)

        for agent_id in actions:
            shaped_reward, intrinsic_reward = brain.shape_reward(
                next_observations[agent_id], env_rewards[agent_id]
            )
            encoded[agent_id] = encode_observation(next_observations[agent_id])

            # No energy in a probe world: NaN, so it is never read as one.
            log.log_step(
                step=step,
                agent_id=agent_id,
                position=observations[agent_id].position,
                action=actions[agent_id],
                env_reward=env_rewards[agent_id],
                intrinsic_reward=intrinsic_reward,
                shaped_reward=shaped_reward,
                energy=float("nan"),
                age=agent.age,
            )

        if log.should_snapshot(step):
            log.log_world(
                step=step,
                grid=env.world.map.grid,
                positions=env.agents.positions(),
            )

        observations = next_observations

        if step % episode_length == 0:
            log.log_rng(rng, step=step)

            summary = brain.summary()
            log.end_episode(
                step=step,
                agents={
                    agent_id: {
                        "epsilon": summary["epsilon"],
                        "curiosity_beta": summary["curiosity_beta"],
                        "energy": float("nan"),
                        "age": agent.age,
                    }
                },
                non_empty_ratio=info["non_empty_ratio"],
            )

            brains.next_episode()

        if flush_every_steps > 0 and step % flush_every_steps == 0:
            log.flush()

    log.close()

    folder = os.path.join(directory, os.path.basename(log.path))
    os.replace(log.path, folder)
    os.rmdir(staging)

    print(
        f"[probe] {os.path.basename(directory)}/{agent_id}: "
        f"{log.episode} episodes, env reward {agent.total_reward:.1f}"
    )

    return folder
