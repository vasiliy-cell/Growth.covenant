from environment.env import GridWorldEnv
from utils.logger import Logger

from Brain.brain import Brain
from Brain.q_table.q_function import QFunction

import yaml
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

    # --- RNG ---
    master_rng = random.Random(seed)

    # --- ENV ---
    env = GridWorldEnv(size=8, max_steps=20, rng=master_rng)

    # --- LOAD CONFIG ---
    with open("Brain/config.yml", "r") as f:
        config = yaml.safe_load(f)

    # --- INIT Q SYSTEM ---
    q_function = QFunction(config)
    brain = Brain(q_function)


    #        TRAIN LOOP
    for episode in range(episodes):

        episode_seed = master_rng.randint(0, 1_000_000)

        observation = env.reset(seed=episode_seed)

        logger = Logger()
        logger.log_seed(seed=seed, episode_seed=episode_seed)

        total_reward = 0
        done = False
        step = 0

        while not done:

            state = observation
            available_actions = env.agent.get_available_actions()

            # --- choose action ---
            action = brain.choose_action(state, available_actions)

            # --- step env ---
            next_observation, reward, done, info = env.step(action)

            # --- LEARNING ---
            brain.learn(
                state=state,
                action=action,
                reward=reward,
                next_state=next_observation,
                done=done
            )

            observation = next_observation
            total_reward += reward

            # --- logging ---
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

    # --- SAVE MODEL ---
    q_function.save()

    print("\nTraining finished. Q-table saved.")


if __name__ == "__main__":
    main()


