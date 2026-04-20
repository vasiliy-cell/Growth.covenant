from environment.env import GridWorldEnv
from Brain.brain import Brain
from utils.logger import Logger

import random
import time


def make_seed():
    return int(time.time() * 1e6)


def choose_seed():
    user_input = input("Enter seed (number or 'r' for random): ").strip()

    if user_input.lower() == "r" or user_input == "":
        return make_seed()

    try:
        return int(user_input)
    except ValueError:
        print("Invalid input, using random seed.")
        return make_seed()


def main():

    episodes = int(input("Enter number of episodes: "))

    # --- choose seed ---
    if episodes == 1:
        seed = choose_seed()
    else:
        seed = make_seed()

    print(f"Using SEED: {seed}")

    # --- main RNG ---
    master_rng = random.Random(seed)

    env = GridWorldEnv(size=8, max_steps=10, rng=master_rng)
    brain = Brain()

    for episode in range(episodes):

        #  разные сиды на эпизоды
        episode_seed = master_rng.randint(0, 1_000_000)

        observation = env.reset(seed=episode_seed)

        logger = Logger()
        logger.log_seed(seed=seed, episode_seed=episode_seed)

        total_reward = 0
        done = False
        step = 0

        while not done:

            available_actions = env.agent.get_available_actions()

            action = brain.choose_action(observation, available_actions)

            observation, reward, done, info = env.step(action)

            total_reward += reward

            logger.log_step(
                step=step,
                position=info["position"],
                action=action,
                reward=reward,
                available_actions=info["available_actions"]
            )

            step += 1

        logger.end_episode()

        print(f"Episode {episode + 1}/{episodes} | total_reward={total_reward}")


if __name__ == "__main__":
    main()