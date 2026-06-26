import os
import json
import matplotlib.pyplot as plt
import numpy as np
from log_selector import choose_files

LOG_DIR = "logs"


def load_rewards(files):
    env_rewards = []
    training_rewards = []
    intrinsic_rewards = []

    for file in files:
        path = os.path.join(LOG_DIR, file)

        with open(path) as f:
            for line in f:
                data = json.loads(line)

                if data["type"] == "episode_summary":
                    env_rewards.append(data["env_reward"])
                    training_rewards.append(data["training_reward"])
                    intrinsic_rewards.append(data["intrinsic_reward"])
                    break

    return env_rewards, training_rewards, intrinsic_rewards


def main():
    files = choose_files()
    if not files:
        return

    env_rewards, training_rewards, intrinsic_rewards = load_rewards(files)

    x = np.arange(len(env_rewards))

    plt.figure(figsize=(8, 5))

    plt.plot(
        x,
        env_rewards,
        marker="o",
        label="Environment Reward"
    )

    plt.plot(
        x,
        training_rewards,
        marker="o",
        label="Training Reward"
    )

    plt.plot(
        x,
        intrinsic_rewards,
        marker="o",
        label="Intrinsic Reward"
    )

    avg_env = np.mean(env_rewards) if env_rewards else 0

    plt.title("Rewards per Episode")
    plt.xlabel("Episode")
    plt.ylabel("Reward")

    plt.text(
        0.02,
        0.95,
        f"Avg Env: {avg_env:.2f}",
        transform=plt.gca().transAxes
    )

    plt.grid()
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()