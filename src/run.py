from src.environment.env import GridWorldEnv
from src.Agent.identity import new_run_id
from src.Brain.brain import Brain
from src.Brain.q_estimater.mlp import MLP
from src.Brain.q_estimater.trainer import DQNTrainer
from src.Brain.policy.policy import Policy
from src.Brain.reward_shaping.reward_shaping import RewardShaping
from src.Brain.reward_shaping.intrinsic_rewards.curiosity.curiosity import Curiosity
from src.utils.td_estimator import TDErrorLogger
from src.persistence.logger import Logger
from src.Brain.replay_buffer import ReplayBuffer

import os
import yaml
import numpy as np
import random
import time
import torch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config.yml")

def load_config(path=CONFIG_PATH):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def make_seed():
    return int(time.time() * 1e6)

def choose_seed():
    """
    'r' / empty -> random. A number -> fixed seed for the whole run.
    """
    user_input = input("Enter global seed (number or 'r' for random): ").strip()
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


def capture_rng_states(master_rng):
    """
    Snapshot of every rng that can influence the run:
      - master_rng: python random.Random used by the world (map generation
        and refills),
      - numpy global rng,
      - torch global rng (used by the policy for exploration) and cuda rng
        if there is one.

    There are no per-episode local seeds anymore, so these snapshots are the
    only way to replay the run from an arbitrary logging window.

    Restoring a snapshot `s` from logs/rng/<run>.jsonl:
        rng.setstate((s["python_random"]["version"],
                      tuple(s["python_random"]["state"]),
                      s["python_random"]["gauss_next"]))
        np.random.set_state((s["numpy"]["algorithm"],
                             np.array(s["numpy"]["keys"], dtype="uint32"),
                             s["numpy"]["pos"], s["numpy"]["has_gauss"],
                             s["numpy"]["cached_gaussian"]))
        torch.set_rng_state(torch.ByteTensor(list(bytes.fromhex(s["torch"]))))
    """
    np_state = np.random.get_state()
    py_state = master_rng.getstate()  # (version, 625-int internal state, gauss_next)

    states = {
        "python_random": {
            "version": py_state[0],
            "state": list(py_state[1]),
            "gauss_next": py_state[2],
        },
        "numpy": {
            "algorithm": np_state[0],
            "keys": np_state[1].tolist(),
            "pos": int(np_state[2]),
            "has_gauss": int(np_state[3]),
            "cached_gaussian": float(np_state[4]),
        },
        # byte tensor -> hex, twice as compact as a list of ints
        "torch": torch.get_rng_state().numpy().tobytes().hex(),
    }

    if torch.cuda.is_available():
        states["torch_cuda"] = [
            state.numpy().tobytes().hex()
            for state in torch.cuda.get_rng_state_all()
        ]

    return states


def encode_observation(obs):
    x, y = obs.position
    flat = []
    for row in obs.local_view:
        for cell in row:
            flat.append(cell)
    return torch.tensor([x, y] + flat, dtype=torch.float32)


def main(render_fn=None, episodes=None, seed=None, agent_count=None):
    config = load_config()

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
    if agent_count is None:
        agent_count = choose_agent_count(
            int(config.get("agents", {}).get("count", 1))
        )
    print(f"agents = {agent_count}")

    if seed is None:
        seed = choose_seed()
    print(f"SEED: {seed}")

    # Minted once per run and shared by the whole population: every agent id
    # of this run is built on it, which is what keeps ids unique across all
    # the runs the project will ever make.
    run_id = new_run_id()
    print(f"RUN: {run_id}")

    # One rng for the whole run: the map, the refills and everything else
    # draw from it, and its state is snapshotted per episode.
    master_rng = random.Random(seed)
    np.random.seed(seed % (2 ** 32))
    torch.manual_seed(seed % (2 ** 63))

    world_cfg = config.get("world", {})
    env = GridWorldEnv(
        size=world_cfg.get("size", 64),
        rng=master_rng,
        empty_ratio=world_cfg.get("empty_ratio", 0.8),
        refill=world_cfg.get("refill", {}),
        agent_count=agent_count,
        run_id=run_id,
    )

    # The world is built exactly once - from here on it only gets updated.
    # start() hands back one observation per agent, keyed by agent id.
    observations = env.start()

    # Every agent has the same field of view, so any of them defines the
    # network input size.
    obs_size = len(encode_observation(next(iter(observations.values()))))

    mlp = MLP(obs_size=obs_size, action_size=8)
    trainer = DQNTrainer(
        model=mlp,
        config=config
    )

    policy_cfg = config.get("policy", {})
    policy = Policy(
        epsilon=policy_cfg.get("epsilon", 1.0),
        epsilon_decay=policy_cfg.get("epsilon_decay", 0.995),
        epsilon_min=policy_cfg.get("epsilon_min", 0.01)
    )

    # One brain for the whole population: every agent acts with it and every
    # agent feeds it. The env knows nothing about brains - it only takes
    # actions - so giving each agent its own is a change here and nowhere
    # else.
    brain = Brain(trainer, policy)

    # One curiosity counter for the whole population as well: novelty is
    # something the group discovers, so a cell another agent already visited
    # is no longer new. Per-agent counters would send everybody rushing into
    # the same "unexplored" corner at once.
    reward_shaping = RewardShaping(
        curiosity=Curiosity(config["curiosity"]) if "curiosity" in config else None
    )

    # --- Replay buffer / batching ---
    # buffer_size: max number of stored transitions (old ones are evicted)
    # batch_size: how many transitions are used per training update
    # min_buffer_size: how many steps to collect BEFORE training starts -
    #   without this warmup sample() would keep returning the same few
    #   transitions, which does not decorrelate anything.
    buffer_cfg = config.get("replay_buffer", {})
    buffer_size = buffer_cfg.get("buffer_size", 10_000)
    batch_size = buffer_cfg.get("batch_size", 32)
    min_buffer_size = buffer_cfg.get("min_buffer_size", batch_size)

    replay_buffer = ReplayBuffer(capacity=buffer_size)

    # --- logging ---
    logging_cfg = config.get("logging", {})
    rng_snapshot_every = int(logging_cfg.get("rng_snapshot_every", 1))

    logger = Logger(log_dir=logging_cfg.get("log_dir", "logs"))
    logger.log_run_start(
        seed=seed,
        extra={
            "run_id": run_id,
            "episodes": episodes,
            "episode_length": episode_length,
            "total_steps": total_steps,
            "agents": agent_count,
            "world_size": world_cfg.get("size", 64),
            "world_refill": world_cfg.get("refill", {}),
        },
    )

    if rng_snapshot_every > 0:
        logger.log_rng(capture_rng_states(master_rng), step=0)

    episode_reward = 0.0

    try:
        for step in range(1, total_steps + 1):
            available_actions = env.get_available_actions()

            states = {
                agent_id: encode_observation(observation)
                for agent_id, observation in observations.items()
            }

            # One forward pass per agent. At ~50 agents that is cheap; if the
            # population ever grows a lot, this is the place to push the
            # whole population through the network in a single batch.
            actions = {
                agent_id: brain.choose_action(state, available_actions[agent_id])
                for agent_id, state in states.items()
            }

            # One call = one tick of the world in which everybody moves.
            next_observations, env_rewards, info = env.step(actions)

            # Every agent contributes its own transition to the SHARED replay
            # buffer, so the population collects experience N times faster
            # than a single agent did.
            # done is always False: the process is continuous, there is no
            # terminal state to cut the bootstrap on.
            transitions = {}

            for agent_id in actions:
                next_observation = next_observations[agent_id]
                env_reward = env_rewards[agent_id]

                shaped_reward, intrinsic_reward = reward_shaping.compute(
                    next_observation, env_reward
                )

                replay_buffer.push(
                    state=states[agent_id],
                    action=actions[agent_id],
                    reward=shaped_reward,
                    next_state=encode_observation(next_observation),
                    done=False
                )

                transitions[agent_id] = (
                    env_reward, shaped_reward, intrinsic_reward
                )
                episode_reward += shaped_reward

            # Train on a batch only once the buffer is warm enough.
            # Until then metrics = None -> the logger simply gets no
            # loss/td_error/etc for this step (as designed in Logger: the
            # average is computed only over steps where a value existed).
            #
            # One update per TICK, not per agent: the population fills the
            # buffer N times faster, so the same cadence now means N times
            # more experience collected per gradient step than before.
            if len(replay_buffer) >= min_buffer_size:
                batch = replay_buffer.sample(batch_size)
                metrics = brain.learn(*batch)
            else:
                metrics = None

            # The train metrics describe the tick, not any single agent -
            # there is one shared brain and one update behind all of them.
            for agent_id, rewards in transitions.items():
                env_reward, shaped_reward, intrinsic_reward = rewards

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

            observations = next_observations

            if render_fn is not None:
                render_fn(env, info)

            # --- logging window boundary ---
            # Nothing here touches the world or the agent position: only the
            # log file, epsilon and curiosity.
            if step % episode_length == 0:
                episode_index = logger.episode

                print(
                    f"Episode {episode_index + 1}/{episodes} | step={step} | "
                    f"reward={episode_reward:.2f} | "
                    f"per_agent={episode_reward / len(env.agents):.2f} | "
                    f"epsilon={policy.epsilon:.4f} | "
                    f"filled={info['non_empty_ratio']:.3f}"
                )

                logger.end_episode(
                    beta=reward_shaping.curiosity.beta if reward_shaping.curiosity is not None else None
                )

                policy.next_episode()

                if reward_shaping.curiosity is not None:
                    reward_shaping.reset()

                if rng_snapshot_every > 0 and logger.episode % rng_snapshot_every == 0:
                    logger.log_rng(capture_rng_states(master_rng), step=step)

                episode_reward = 0.0
    finally:
        # Flush whatever is left of an unfinished window, then close the file.
        if logger.steps > 0:
            logger.end_episode(
                beta=reward_shaping.curiosity.beta if reward_shaping.curiosity is not None else None
            )
        logger.close()

    trainer.save()
    print("Training finished")


if __name__ == "__main__":
    main()
