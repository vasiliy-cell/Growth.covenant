from src.environment.env import GridWorldEnv
from src.Agent.identity import new_run_id
from src.Brain.BrainManager import BrainManager
from src.persistence.checkpoint import Checkpoint
from src.persistence.checkpoint_store import CheckpointStore
from src.persistence.checkpoint_writer import CheckpointWriter
from src.persistence.run_log import RunLog

from src.Genome.types.reuse import reuse
from src.utils.rng import RunRandom


import argparse
import os
import signal
import yaml
import numpy as np
import torch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config.yml")

def load_config(path=CONFIG_PATH):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def apply_overrides(config, overrides):
    """
    --set life.childhood_steps=2000, for a run that differs from the file
    in one place and should not have the file edited for it.

    The value goes through yaml, so 2000 is an int, 0.2 is a float and
    true is a bool - the same reader that produced the rest of the config.

    The overrides land in BOTH copies of the config in this process: the
    one read here and the module-level one in src/Genome/types/reuse.py
    that the world reads. One process must not hold two different
    opinions about its own rules.
    """
    from src.Genome.types import reuse

    for override in overrides or []:
        key, _, raw = str(override).partition("=")
        value = yaml.safe_load(raw)

        for target in (config, reuse.config):
            node = target
            parts = key.strip().split(".")

            for part in parts[:-1]:
                node = node.setdefault(part, {})

            node[parts[-1]] = value

    return config


def stop_gracefully(signum, frame):
    """
    A panel that stops a run should not cost it its checkpoint.

    SIGTERM kills a process where it stands, so the runner would never
    reach the rescue checkpoint it writes on the way out. Turning the
    signal into an exception puts the stop on the same path as a crash -
    which is the path that saves everything.
    """
    raise KeyboardInterrupt(f"stopped by signal {signum}")

def make_seed():
    return RunRandom.new_seed()

def choose_seed():
    user_input = input("Enter global seed (number or 'r' / empty for random): ").strip()
    if user_input.lower() in ["r", ""]:
        return make_seed()
    try:
        return int(user_input)
    except ValueError:
        return make_seed()

def choose_episodes(episode_length):
    """
    Episodes are asked here, not read from config: only their length is a
    config value. An episode is a logging window, so this number only decides
    how long the run is and how often summaries are flushed.
    """
    print(f"1 episode = {episode_length} steps")

    user_input = input("Enter number of episodes: ").strip()

    try:
        return int(user_input)
    except ValueError:
        print("Invalid input, falling back to 1 episode")
        return 1


def choose_agent_count(default=1):
    """
    How many agents share the world.

    Asked in the terminal like the number of episodes: it is the parameter
    you change between two experiments, so it belongs next to the run
    length and not buried in the config. config.yml only supplies the
    default offered here.
    """
    user_input = input(f"Enter number of agents [{default}]: ").strip()

    if not user_input:
        return default

    try:
        count = int(user_input)
    except ValueError:
        print(f"Invalid input, falling back to {default}")
        return default

    if count < 1:
        print(f"A world needs at least one agent, falling back to {default}")
        return default

    return count


def choose_species(default="clons"):
    """
    How agents reproduce this run - an experiment knob, so it is asked in the
    terminal like the agent count, not buried in config.
    """
    print("How do agents reproduce?")
    print("  1) clons       - asexual: energy-gated cloning")
    print("  2) non_linear  - sexual: BLX-a blend of two nearby parents")
    print("  3) mendel  - sexual: has dominance of genes the most biologicaly inspired of all")
    choice = input(f"Enter choice (1/2/3) [{default}]: ").strip()
    if choice == "1":
        return "clons"
    if choice == "2":
        return "non_linear"
    if choice == "3":
        return "mendel"
    return default


def choose_checkpoint(store):
    """
    Which run to carry on, or none of them.

    The listing is printed before anything is built, because a resumed run
    takes its seed, its species and its world from the checkpoint - by the
    time those are asked for it is too late to change your mind.
    """
    found = store.list()

    if not found:
        return None

    print("Continue an earlier run?")
    print("  0) no, build a new world")

    for number, checkpoint in enumerate(found, start=1):
        print(
            f"  {number}) {checkpoint['name']}"
            f"{'  [pinned]' if checkpoint['pinned'] else ''}"
            f"  step {checkpoint['step']}"
            f"  {checkpoint['size'] / 1e6:.1f} MB"
            f"  {checkpoint['saved_at']:%Y-%m-%d %H:%M}"
        )

    answer = input(f"Enter choice (0-{len(found)}) [0]: ").strip()

    if not answer or answer == "0":
        return None

    try:
        return found[int(answer) - 1]["path"]
    except (ValueError, IndexError):
        print("Invalid input, building a new world")
        return None


def choose_label():
    """
    What this experiment is, in words, for whoever opens the folder in a
    month. It names the log folder and goes into its header - an empty
    answer is fine, the world id already makes the folder unique.
    """
    return input("Name for this experiment (optional): ").strip()


def choose_pin(default=False):
    """
    Whether this run's last checkpoint survives the rotation.

    Rolling checkpoints overwrite each other on purpose - most runs are
    not worth a 100 MB file a week later. The ones that are get said so
    here, and are never deleted.
    """
    answer = input("Keep this run's final checkpoint forever? [y/N]: ").strip()

    return answer.lower().startswith("y") if answer else default


def population_state(env, brains):
    """
    Where every living mind stands, for the end of a logging window.

    Keyed by the population and not by the registry of minds: a body that
    starved this tick still has a brain until the next sync, and it is not
    part of the population any more.
    """
    state = {}

    for agent in env.agents:
        if agent.agent_id not in brains:
            continue

        summary = brains.get(agent.agent_id).summary()

        state[agent.agent_id] = {
            "epsilon": summary["epsilon"],
            "curiosity_beta": summary["curiosity_beta"],
            "energy": agent.energy,
            "age": agent.age,
        }

    return state


def encode_observation(obs):
    x, y = obs.position
    flat = []
    for row in obs.local_view:
        for cell in row:
            flat.append(cell)
    return torch.tensor([x, y] + flat, dtype=torch.float32)


def main(render_fn=None, episodes=None, seed=None, agent_count=None,
         species=None, resume=None, pin=None, label=None, series=None,
         live_every=None, overrides=None):
    """
    resume:     path of a checkpoint to carry on, "" to force a new world,
                None to ask.
    pin:        whether this run's final checkpoint is kept (None asks).
    label:      a name for the experiment, used for the log folder (None
                asks on a new world; a continued one has its folder).
    series:     a name this run shares with its siblings; it nests the log
                folder and is written into run.json.
    live_every: how often to rewrite live.json for whoever is watching.
    overrides:  ["life.childhood_steps=2000", ...] for this run only.
    """
    config = apply_overrides(load_config(), overrides)

    # --- new world, or an old one continued? ---
    # This comes first because a resumed run takes its seed, its species,
    # its world and its population from the checkpoint - there is nothing
    # left to ask about once one is chosen.
    checkpoints_cfg = config.get("checkpoints", {})
    store = CheckpointStore(
        directory=checkpoints_cfg.get("dir", "checkpoints"),
        keep=int(checkpoints_cfg.get("keep", 5)),
    )
    store.prepare()

    if resume is None:
        resume = choose_checkpoint(store)

    record = CheckpointStore.load(resume) if resume else None

    if record is not None:
        print(f"Continuing {Checkpoint.describe(record)}")

        drift = Checkpoint.config_drift(record, config)
        if drift:
            print(
                "WARNING: config changed since this checkpoint: "
                + ", ".join(drift)
            )

        seed = record["run"]["seed"]
        species = record["env"]["species"]
        world_id = record["run"]["world_id"]
        start_step = record["run"]["step"]
    else:
        world_id = None
        start_step = 0

    # --- run length ---
    # Episodes no longer exist as a world mechanic: they are just logging
    # windows. Their length comes from config.yml, their count is asked in
    # the terminal.
    run_cfg = config.get("run", {})
    episode_length = int(run_cfg.get("episode_length", 20))

    if episodes is None:
        episodes = choose_episodes(episode_length)
    else:
        print(f"1 episode = {episode_length} steps")

    total_steps = episodes * episode_length

    print(f"episodes = {episodes} -> total steps = {total_steps}")

    # --- population ---
    # A continued world brings its own population, its own species and its
    # own seed: asking for them again could only contradict the checkpoint.
    if record is None:
        if agent_count is None:
            agent_count = choose_agent_count(
                int(config.get("agents", {}).get("count", 1))
            )
        print(f"agents = {agent_count}")

        if species is None:
            species = choose_species(config.get("genome", {}).get("type", "clons"))
        print(f"reproduction: {species}")

        if seed is None:
            seed = choose_seed()
    else:
        agent_count = len(record["env"]["population"]["agents"])
        print(f"agents = {agent_count} (from the checkpoint)")
        print(f"reproduction: {species}")

    print(f"SEED: {seed}")

    if label is None:
        label = choose_label() if record is None else None

    if pin is None:
        pin = choose_pin()

    # Minted once per run and shared by the whole population: every agent id
    # of this run is built on it, which is what keeps ids unique across all
    # the runs the project will ever make.
    run_id = new_run_id()
    print(f"RUN: {run_id}")

    # The world keeps the id it was born with: agent ids are built on it,
    # so a continued world goes on minting ids in the same lineage while
    # the logs and the checkpoints of THIS process carry the new run id.
    world_id = world_id or run_id

    # One seed for the whole run, and every stream grown from it by name:
    # the map, the population, the movement draws, the genome and, per
    # agent, its weights, its exploration and its replay sampling.
    rng = RunRandom(seed)

    # Belt and braces: nothing in the project should reach for a global
    # generator anymore, but if something does, it must at least land on
    # the same numbers for the same seed.
    np.random.seed(seed % (2 ** 32))
    torch.manual_seed(seed % (2 ** 63))

    # warn_only: an op with no deterministic kernel should cost a warning,
    # not an hours-long run. On CPU the maths here is deterministic
    # regardless; this is what keeps that true on a GPU.
    if bool(run_cfg.get("deterministic", True)):
        torch.use_deterministic_algorithms(True, warn_only=True)

    world_cfg = config.get("world", {})
    env = GridWorldEnv(
        size=(
            record["env"]["world"]["size"] if record is not None
            else world_cfg.get("size", 64)
        ),
        rng=rng,
        empty_ratio=world_cfg.get("empty_ratio", 0.8),
        refill=world_cfg.get("refill", {}),
        agent_count=agent_count,
        run_id=world_id,
        species_name=species,
    )

    # --- minds ---
    # One brain per agent, each with its own network, replay buffer,
    # epsilon and curiosity. Nothing about learning is shared, which is the
    # entire point: without a private mind an agent has no identity to
    # grow.
    #
    # Because each agent stores exactly one transition per tick, every
    # setting under replay_buffer in config.yml keeps the meaning it had
    # when a single agent lived in the world.
    archive = CheckpointWriter(
        models_dir=checkpoints_cfg.get("models_dir", "models"),
        run_id=run_id,
    )

    def make_brains(observations):
        """Every agent has the same field of view, so any of them sizes the
        network input. An empty world (everybody starved before the save)
        still has to build a manager, so fall back on the view itself."""
        obs_size = (
            len(encode_observation(next(iter(observations.values()))))
            if observations else 2 + 7 * 7
        )

        return BrainManager(
            config=config,
            obs_size=obs_size,
            action_size=len(env.get_action_space()),
            checkpoints=archive,
            rng=rng,
        )

    if record is None:
        # The world is built exactly once - from here on it only gets
        # updated. start() hands back one observation per agent.
        observations = env.start()
        brains = make_brains(observations)
    else:
        # Everything comes back in one place, in one order, because the
        # order is part of the format: world, then minds, then - last of
        # all - the rng streams. See Checkpoint.restore.
        _, observations, brains = Checkpoint.restore(
            record, env, make_brains, rng
        )

    # --- logging ---
    # The folder belongs to the WORLD, not to this process: a continued run
    # writes into the same one and only opens a new session in its header.
    logging_cfg = config.get("logging", {})
    flush_every_steps = int(logging_cfg.get("flush_every_steps", 1000))

    log = RunLog(
        directory=logging_cfg.get("dir", "logs"),
        world_id=world_id,
        run_id=run_id,
        seed=seed,
        episode_length=episode_length,
        config=config,
        species=species,
        gene_names=list(config.get("genome", {}).get("genes", {})),
        label=label,
        resumed_from=os.path.basename(resume) if resume else None,
        series=series,
        max_rows=int(logging_cfg.get("max_rows_per_part", 50000)),
        world_snapshot_every=int(logging_cfg.get("world_snapshot_every", 100)),
        rng_world_every=int(logging_cfg.get("rng_world_every_episodes", 1)),
        rng_agents_every=int(logging_cfg.get("rng_agents_every_episodes", 100)),
        live_every=(
            int(logging_cfg.get("live_every_steps", 20))
            if live_every is None else int(live_every)
        ),
    )
    log.episode = record["run"]["episode"] if record is not None else 0

    print(f"LOG: {log.path} (session {log.session})")

    # --- checkpoints ---
    every_steps = int(checkpoints_cfg.get("every_steps", 500))
    replay_every = int(checkpoints_cfg.get("replay_every", 5))

    written = 0
    last_step = start_step

    # Windows closed by THIS process. The log counts episodes for the whole
    # life of the world, so on a continued run the two numbers differ and
    # both are worth seeing: one is progress, the other is history.
    window = 0

    def write_checkpoint(step, with_replay, pinned=False):
        """The whole run in one file: world, bodies, minds, streams."""
        return store.save(
            Checkpoint.capture(
                env,
                brains,
                rng,
                run={
                    "run_id": run_id,
                    "world_id": world_id,
                    "seed": seed,
                    "step": step,
                    "episode": log.episode,
                    "episode_length": episode_length,
                },
                config=config,
                with_replay=with_replay,
            ),
            run_id=run_id,
            step=step,
            pinned=pinned,
        )

    try:
        for step in range(start_step + 1, start_step + total_steps + 1):
            last_step = step
            # Minds follow the population: whoever was born this tick gets
            # one, whoever is gone has theirs written down and dropped.
            #
            # A genotype is read ONCE, for the body that is about to be
            # given a mind. Reading it again every step cost a config file
            # per agent per step and, worse, spent a draw of that agent's
            # stream on a phenotype nobody was going to use.
            phenotypes = {
                agent_id: env.make_phenotype(agent_id)
                for agent_id in env.agents.ids()
                if agent_id not in brains
            }
            brains.sync(env.agents, phenotypes)

            available_actions = env.get_available_actions()

            states = {
                agent_id: encode_observation(observation)
                for agent_id, observation in observations.items()
            }

            # One forward pass per agent, through that agent's own network.
            actions = {
                agent_id: brains.get(agent_id).choose_action(
                    state, available_actions[agent_id]
                )
                for agent_id, state in states.items()
            }

            # One call = one tick of the world in which everybody moves.
            next_observations, env_rewards, info = env.step(actions)

            # Each agent remembers and learns on its own: its own curiosity
            # values the step, its own buffer stores it, its own network
            # takes the gradient. Nothing crosses between agents.
            # done is always False: the world is continuous and has no
            # terminal state to cut the bootstrap on. Death does not make
            # one either - a starved agent is removed, and the transition
            # that killed it is simply never stored.
            bodies = {record["agent_id"]: record for record in info["deaths"]}

            for agent_id in actions:
                env_reward = env_rewards[agent_id]
                dead = bodies.get(agent_id)

                # Starved on this very tick: the world removed the body
                # before it could see where its move led. There is no next
                # observation to shape a reward from and no mind left to
                # train, so the step is written down and nothing is stored.
                if agent_id not in next_observations:
                    log.log_step(
                        step=step,
                        agent_id=agent_id,
                        position=observations[agent_id].position,
                        action=actions[agent_id],
                        env_reward=env_reward,
                        intrinsic_reward=0.0,
                        shaped_reward=env_reward,
                        energy=dead["energy"] if dead else 0.0,
                        age=dead["lifespan"] if dead else 0,
                    )
                    continue

                brain = brains.get(agent_id)
                agent = env.agents.get(agent_id)
                next_observation = next_observations[agent_id]

                shaped_reward, intrinsic_reward = brain.shape_reward(
                    next_observation, env_reward
                )

                brain.remember(
                    state=states[agent_id],
                    action=actions[agent_id],
                    reward=shaped_reward,
                    next_state=encode_observation(next_observation),
                    done=False
                )

                # None while this agent's buffer is still warming up: a
                # step happens, no gradient does, and the updates table
                # simply has no row for this tick.
                metrics = brain.learn()

                log.log_step(
                    step=step,
                    agent_id=agent_id,
                    position=observations[agent_id].position,
                    action=actions[agent_id],
                    env_reward=env_reward,
                    intrinsic_reward=intrinsic_reward,
                    shaped_reward=shaped_reward,
                    energy=agent.energy,
                    age=agent.age,
                )

                if metrics is not None:
                    summary = brain.summary()

                    log.log_update(
                        step=step,
                        agent_id=agent_id,
                        training_step=brain.trainer.training_step,
                        metrics=metrics,
                        curiosity_beta=summary["curiosity_beta"],
                        epsilon=summary["epsilon"],
                        buffer_size=len(brain.replay_buffer),
                    )

            # --- events ---
            # A newborn is read here and not on the next tick's sync: the
            # phenotype is cached, so this is the same reading its mind
            # will be built from, and the log gets the body's whole
            # description at the moment it appears.
            for birth in info["births"]:
                log.log_birth(
                    step=step,
                    agent_id=birth["agent_id"],
                    index=birth["index"],
                    parents=birth["parents"],
                    energy=birth["energy"],
                    genotype=birth["genotype"],
                    phenotype=env.make_phenotype(birth["agent_id"]),
                )

            for death in info["deaths"]:
                log.log_death(step=step, record=death)

            if log.should_snapshot(step):
                log.log_world(
                    step=step,
                    grid=env.world.map.grid,
                    positions=env.agents.positions(),
                )

            # What somebody watching the panel sees. Cheap, and the
            # simulation never learns whether anybody is watching.
            if log.should_live(step):
                log.log_live(
                    step=step,
                    grid=env.world.map.grid,
                    positions=env.agents.positions(),
                    agents=len(env.agents),
                    reward=log.window_reward,
                    epsilon=log.window_epsilon(brains),
                )

            observations = next_observations

            if render_fn is not None:
                render_fn(env, info)

            # --- extinction ---
            # Nothing acts, nothing learns and nothing can be born again:
            # once the last body starves the run has no reason to keep
            # ticking, so it ends here instead of at total_steps.
            if len(env.agents) == 0:
                print(f"Extinct at step {step}: the last agent starved")
                break

            # --- logging window boundary ---
            # Nothing here touches the world or the agent position: only the
            # log, epsilon and curiosity.
            if step % episode_length == 0:
                # The streams go down BEFORE the counter moves, so a
                # snapshot is labelled with the window it belongs to - and
                # the very first window is one of them.
                log.log_rng(rng, step=step)

                summary = log.end_episode(
                    step=step,
                    agents=population_state(env, brains),
                    non_empty_ratio=info["non_empty_ratio"],
                )

                window += 1

                print(
                    f"Episode {window}/{episodes} "
                    f"(world {summary['episode']}) | "
                    f"step={step} | "
                    f"reward={summary['shaped_reward']:.2f} | "
                    f"per_agent={summary['shaped_reward'] / max(summary['agents'], 1):.2f} | "
                    f"epsilon={summary['mean_epsilon'] or 0.0:.4f} | "
                    f"pop={summary['agents']} "
                    f"(+{summary['births']}/-{summary['deaths']}) | "
                    f"filled={summary['non_empty_ratio']:.3f}"
                )

                # Every mind decays its OWN epsilon and clears its OWN
                # curiosity: the schedule belongs to the individual, so an
                # agent born late still starts out exploring.
                brains.next_episode()

            # --- checkpoint ---
            # The replay buffers are most of the weight of a file, so only
            # every replay_every-th checkpoint carries them: the cheap ones
            # are for crashes, the heavy ones for picking a run back up
            # days later.
            if every_steps > 0 and step % every_steps == 0:
                written += 1
                path = write_checkpoint(
                    step,
                    with_replay=(
                        replay_every > 0 and written % replay_every == 0
                    ),
                )
                print(f"[checkpoint @ step {step}] {os.path.basename(path)}")

            # --- log to disk ---
            # Closes a part of every table. Whatever is still in memory is
            # all a kill -9 can cost from here on.
            if flush_every_steps > 0 and step % flush_every_steps == 0:
                log.flush()
    except BaseException:
        # Whatever went wrong, hours of training must not go with it. This
        # is the one checkpoint that carries everything, replay included.
        #
        # The tick it died on may be half applied - some bodies moved, no
        # rewards paid - so this file is a rescue, not a clean boundary.
        # The rolling pool still holds the last periodic checkpoint, and
        # that one is always a whole tick.
        path = write_checkpoint(last_step, with_replay=True)
        print(f"[crash @ step {last_step}] checkpoint written: {path}")
        raise
    finally:
        # Close whatever is left of an unfinished window, then the log.
        if log.window_steps > 0:
            log.end_episode(
                step=last_step,
                agents=population_state(env, brains),
                non_empty_ratio=env.world.non_empty_ratio(),
            )

        log.close()

    final = write_checkpoint(last_step, with_replay=True, pinned=bool(pin))
    print(f"Checkpoint: {final}{' [pinned]' if pin else ''}")

    saved = archive.save_all(brains)
    print(f"Saved {len(saved)} brains to {archive.directory}")
    print("Training finished")


def parse_args():
    """
    Everything the prompts ask, as flags.

    A flag that is not given stays None, which is exactly what makes the
    prompt appear - so `python src/run.py` is still the interactive run it
    has always been, and the panel launches the same runner with every
    answer already filled in.
    """
    parser = argparse.ArgumentParser(description="Run the world.")

    parser.add_argument("--episodes", type=int, help="logging windows to run")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--agents", type=int, dest="agent_count")
    parser.add_argument("--species", choices=["clons", "non_linear", "mendel"])
    parser.add_argument("--label", help="name of the experiment")
    parser.add_argument("--series", help="name this run shares with its siblings")
    parser.add_argument("--resume", help="checkpoint to carry on ('' = new world)")
    parser.add_argument("--pin", dest="pin", action="store_true", default=None,
                        help="keep this run's final checkpoint forever")
    parser.add_argument("--no-pin", dest="pin", action="store_false")
    parser.add_argument("--live-every", type=int, dest="live_every",
                        help="rewrite live.json every N steps (0 = off)")
    parser.add_argument("--set", action="append", dest="overrides", default=[],
                        metavar="KEY=VALUE",
                        help="override one config value, e.g. energy.energy_leak=0.2")

    return parser.parse_args()


if __name__ == "__main__":
    # A stop from the panel arrives as SIGTERM. Turning it into an
    # exception sends it down the same path a crash takes, and that path
    # writes a checkpoint on the way out.
    signal.signal(signal.SIGTERM, stop_gracefully)

    main(**vars(parse_args()))
