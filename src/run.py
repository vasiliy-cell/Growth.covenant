from src.environment.env import GridWorldEnv
from src.Agent.identity import new_run_id
from src.Brain.BrainManager import BrainManager
from src.persistence.checkpoint import Checkpoint
from src.persistence.checkpoint_store import CheckpointStore
from src.persistence.checkpoint_writer import CheckpointWriter
from src.persistence.logger import Logger

from src.Genome.types.reuse import reuse
from src.utils.rng import RunRandom


import os
import yaml
import numpy as np
import torch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config.yml")

def load_config(path=CONFIG_PATH):
    with open(path, "r") as f:
        return yaml.safe_load(f)

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


def choose_pin(default=False):
    """
    Whether this run's last checkpoint survives the rotation.

    Rolling checkpoints overwrite each other on purpose - most runs are
    not worth a 100 MB file a week later. The ones that are get said so
    here, and are never deleted.
    """
    answer = input("Keep this run's final checkpoint forever? [y/N]: ").strip()

    return answer.lower().startswith("y") if answer else default


def capture_rng_states(rng):
    """
    A snapshot of every stream this run has actually used.

    There are no per-episode seeds and no global generators to chase
    anymore: the run draws from named streams (src/utils/rng.py), so one
    call to rng.state() is the whole of its randomness. Restoring it is
    RunRandom.load_state(snapshot) - that, plus the brains, is everything a
    run needs to continue instead of starting over.
    """
    return rng.state()


def population_summary(brains):
    """
    Epsilon and curiosity belong to the individual now, so a run summary can
    only show the population mean.

    Agents are born and die at different times now, so these numbers drift
    apart on their own - newborns exploring while the veterans around them
    exploit - and the mean is the only honest single number to print.

    An empty population is not an error: the last window of an extinct run
    still has to be flushed, and it simply has nothing to average.
    """
    summaries = [brain.summary() for brain in brains]

    if not summaries:
        return 0.0, None

    epsilon = sum(s["epsilon"] for s in summaries) / len(summaries)

    betas = [
        s["curiosity_beta"] for s in summaries
        if s["curiosity_beta"] is not None
    ]
    beta = sum(betas) / len(betas) if betas else None

    return epsilon, beta


def encode_observation(obs):
    x, y = obs.position
    flat = []
    for row in obs.local_view:
        for cell in row:
            flat.append(cell)
    return torch.tensor([x, y] + flat, dtype=torch.float32)


def main(render_fn=None, episodes=None, seed=None, agent_count=None,
         species=None, resume=None, pin=None):
    """
    resume: path of a checkpoint to carry on, "" to force a new world,
            None to ask.
    pin:    whether this run's final checkpoint is kept forever (None asks).
    """
    config = load_config()

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
    logging_cfg = config.get("logging", {})
    rng_snapshot_every = int(logging_cfg.get("rng_snapshot_every", 1))

    logger = Logger(
        log_dir=logging_cfg.get("log_dir", "logs"),
        flush_every=int(logging_cfg.get("flush_every", 100)),
    )
    logger.log_run_start(
        seed=seed,
        extra={
            "run_id": run_id,
            "world_id": world_id,
            "resumed_from": os.path.basename(resume) if resume else None,
            "resumed_at_step": start_step,
            "episodes": episodes,
            "episode_length": episode_length,
            "total_steps": total_steps,
            "agents": agent_count,
            "world_size": world_cfg.get("size", 64),
            "world_refill": world_cfg.get("refill", {}),
            "life": config.get("life", {}),
            "energy": config.get("energy", {}),
        },
    )

    if rng_snapshot_every > 0:
        logger.log_rng(capture_rng_states(rng), step=0)

    episode_reward = 0.0

    # --- checkpoints ---
    every_steps = int(checkpoints_cfg.get("every_steps", 500))
    replay_every = int(checkpoints_cfg.get("replay_every", 5))

    written = 0
    last_step = start_step

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
                    "episode": logger.episode,
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
            for agent_id in actions:
                env_reward = env_rewards[agent_id]

                # Starved on this very tick: the world removed the body
                # before it could see where its move led. There is no next
                # observation to shape a reward from and no mind left to
                # train, so the step is only written down.
                if agent_id not in next_observations:
                    logger.log_step(
                        step=step,
                        position=observations[agent_id].position,
                        action=actions[agent_id],
                        reward=env_reward,
                    )
                    episode_reward += env_reward
                    continue

                brain = brains.get(agent_id)
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

                # None while this agent's buffer is still warming up -> the
                # logger simply gets no loss/td_error for the step (as
                # designed in Logger: an average is computed only over the
                # steps where a value existed).
                metrics = brain.learn()

                log_kwargs = dict(
                    step=step,
                    position=observations[agent_id].position,
                    action=actions[agent_id],
                    reward=env_reward,
                    shaped_reward=shaped_reward,
                    intrinsic_reward=intrinsic_reward,
                )
                if metrics is not None:
                    log_kwargs.update(
                        loss=metrics["loss"],
                        td_error=metrics["td_error"],
                        grad_norm=metrics["grad_norm"],
                        target_q=metrics["target_q"],
                        q_prediction=metrics["q_prediction"],
                    )

                logger.log_step(**log_kwargs)

                episode_reward += shaped_reward

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
            # log file, epsilon and curiosity.
            if step % episode_length == 0:
                episode_index = logger.episode

                mean_epsilon, mean_beta = population_summary(brains)

                print(
                    f"Episode {episode_index + 1}/{episodes} | step={step} | "
                    f"reward={episode_reward:.2f} | "
                    f"per_agent={episode_reward / len(env.agents):.2f} | "
                    f"epsilon={mean_epsilon:.4f} | "
                    f"filled={info['non_empty_ratio']:.3f}"
                )

                logger.end_episode(beta=mean_beta)

                # Every mind decays its OWN epsilon and clears its OWN
                # curiosity: the schedule belongs to the individual, so an
                # agent born late still starts out exploring.
                brains.next_episode()

                if rng_snapshot_every > 0 and logger.episode % rng_snapshot_every == 0:
                    logger.log_rng(capture_rng_states(rng), step=step)

                episode_reward = 0.0

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
        # Flush whatever is left of an unfinished window, then close the file.
        if logger.steps > 0:
            logger.end_episode(beta=population_summary(brains)[1])
        logger.close()

    final = write_checkpoint(last_step, with_replay=True, pinned=bool(pin))
    print(f"Checkpoint: {final}{' [pinned]' if pin else ''}")

    saved = archive.save_all(brains)
    print(f"Saved {len(saved)} brains to {archive.directory}")
    print("Training finished")


if __name__ == "__main__":
    main()
