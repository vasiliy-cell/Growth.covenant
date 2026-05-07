import os
import json
import matplotlib.pyplot as plt
import numpy as np
from log_selector import choose_files

LOG_DIR = "logs"


def load_rewards(files):
    rewards = []

    for file in files:
        path = os.path.join(LOG_DIR, file)

        total = 0
        with open(path) as f:
            for line in f:
                data = json.loads(line)

                if data["type"] == "step":
                    total += data["reward"]

        rewards.append(total)

    return rewards


def main():
    files = choose_files()
    if not files:
        return

    rewards = load_rewards(files)

    x = np.arange(len(rewards))
    avg = np.mean(rewards) if rewards else 0

    plt.figure()
    plt.plot(x, rewards, marker="o")

    plt.title("Total Reward per Episode")
    plt.xlabel("Episode")
    plt.ylabel("Reward")

    plt.text(
        0.02, 0.95,
        f"Avg: {avg:.2f}",
        transform=plt.gca().transAxes
    )

    plt.grid()
    plt.show()


if __name__ == "__main__":
    main()