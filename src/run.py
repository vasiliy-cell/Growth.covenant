from src.environment.env import GridWorldEnv
from src.utils.logger import Logger

from src.Brain.brain import Brain

from src.Brain.q_estimater.mlp import MLP
from src.Brain.q_estimater.trainer import DQNTrainer

from src.Brain.reward_shaping.reward_shaping import RewardShaping
from src.Brain.reward_shaping.intrinsic_rewards.curiosity.curiosity import Curiosity

from src.utils.td_estimator import TDErrorLogger, TDTransition

import yaml
import random
import time
import torch


def make_seed():
    return int(time.time() * 1e6)


def choose_seed():
    user_input = input("Enter seed (number or 'r' for random): ").strip()

    if user_input.lower() == "r" or user_input == "":
        return make_seed()

    try:
        return int(user_input)
    except ValueError:
        return make_seed()


def encode_observation(obs):
    x, y = obs.position

    flat = []
    for row in obs.local_view:
        for cell in row:
            flat.append(cell)

    return torch.tensor([x, y] + flat, dtype=torch.float32)


def main(render_fn=None):
    episodes = int(input("Enter number of episodes: "))

    seed = choose_seed() if episodes == 1 else make_seed()
    print(f"Using SEED: {seed}")

    master_rng = random.Random(seed)
    env = GridWorldEnv(size=8, max_steps=20, rng=master_rng)

    with open("src/Brain/config.yml", "r") as f:
        config = yaml.safe_load(f)

    dummy_obs = env.reset(seed=0)
    obs_size = len(encode_observation(dummy_obs))

    action_size = 8
    mlp = MLP(
        obs_size=obs_size,
        action_size=action_size
    )

    trainer = DQNTrainer(
        model=mlp,
        lr=config.get("lr", 0.001),
        gamma=config["gamma"],
        save_path="models/mlp.pth"
    )

    brain = Brain(trainer)

    td_logger = TDErrorLogger(gamma=config["gamma"])

    curiosity = Curiosity(config["curiosity"]) if "curiosity" in config else None
    reward_shaping = RewardShaping(curiosity=curiosity)

    for episode in range(episodes):

        observation = env.reset(seed=master_rng.randint(0, 1_000_000))

        logger = Logger()
        logger.log_seed(seed=seed, episode_seed=0)

        done = False
        step = 0
        total_reward = 0

        while not done:
            state = encode_observation(observation)
            action = brain.choose_action(state, env.agent.get_available_actions())
            next_obs, env_reward, done, info = env.step(action)
            shaped_reward, intrinsic_reward = reward_shaping.compute(
                next_obs,
                env_reward
            )

            next_state = encode_observation(next_obs)

            brain.learn(
                state=state,
                action=action,
                reward=shaped_reward,
                next_state=next_state,
                done=done
            )

            td_error = td_logger.compute_from_values(
                reward=env_reward,
                current_q=0.0,
                next_q=0.0,
                done=done
            )

            total_reward += shaped_reward

            logger.log_step(
                step=step,
                position=info["position"],
                action=action,
                reward=env_reward,
                shaped_reward=shaped_reward,
                intrinsic_reward=intrinsic_reward,
                td_error=td_error,
                available_actions=info["available_actions"]
            )

            observation = next_obs
            step += 1

        logger.end_episode()
        print(f"Episode {episode+1} | reward={total_reward}")

    trainer.save()
    print("Training finished")