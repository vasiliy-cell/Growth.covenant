import json
import os
import matplotlib.pyplot as plt
import numpy as np


LOG_DIR = "logs"


def load_rewards():
    rewards = []

    files = sorted(os.listdir(LOG_DIR))

    for file in files:
        if file.endswith(".jsonl"):
            total_reward = 0

            with open(os.path.join(LOG_DIR, file)) as f:
                for line in f:
                    data = json.loads(line)
                    if data["type"] == "step":
                        total_reward += data["reward"]

            rewards.append(total_reward)

    return rewards


def main():
    rewards = load_rewards()

    episodes = np.arange(len(rewards))

    plt.figure()
    plt.plot(episodes, rewards, marker="o")

    plt.title("Total Reward per Episode")
    plt.xlabel("Episode")
    plt.ylabel("Total Reward")

    plt.xticks(episodes)  

    plt.grid()
    plt.show()


if __name__ == "__main__":
    main()