import os
import json
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter

from log_selector import choose_files


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
LOG_DIR = "logs"
GRID_SIZE = 8


# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------
def load_data(files):

    rewards = []
    heatmap = np.zeros((GRID_SIZE, GRID_SIZE))
    action_counter = Counter()

    for file in files:

        path = os.path.join(LOG_DIR, file)

        total_reward = 0

        with open(path) as f:

            for line in f:

                data = json.loads(line)

                if data["type"] != "step":
                    continue

                # -----------------------------
                # reward
                # -----------------------------
                total_reward += data["reward"]

                # -----------------------------
                # position
                # -----------------------------
                x, y = data["position"]

                if isinstance(x, list):
                    x, y = x

                heatmap[int(x)][int(y)] += 1

                # -----------------------------
                # action
                # -----------------------------
                action = str(data["action"])
                action_counter[action] += 1

        rewards.append(total_reward)

    return rewards, heatmap, action_counter


# ---------------------------------------------------
# DASHBOARD
# ---------------------------------------------------
def main():

    files = choose_files()

    if not files:
        return

    print(f"\nUsing {len(files)} log(s)")

    rewards, heatmap, action_counter = load_data(files)

    # ---------------------------------------------------
    # FIGURE
    # ---------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # ===================================================
    # TOTAL REWARD
    # ===================================================
    ax = axes[0]

    episodes = np.arange(len(rewards))

    ax.plot(episodes, rewards, marker="o")

    avg_reward = np.mean(rewards) if rewards else 0

    ax.set_title(f"Total Reward\navg={avg_reward:.2f}")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Reward")

    ax.grid(True)

    # ===================================================
    # ACTION DISTRIBUTION
    # ===================================================
    ax = axes[1]

    actions = list(action_counter.keys())
    counts = list(action_counter.values())

    ax.bar(actions, counts)

    ax.set_title("Action Distribution")
    ax.set_xlabel("Action")
    ax.set_ylabel("Count")

    ax.grid(axis="y")

    # ===================================================
    # HEATMAP
    # ===================================================
    ax = axes[2]

    im = ax.imshow(heatmap)

    ax.set_title("Position Heatmap")

    ax.set_xticks(range(GRID_SIZE))
    ax.set_yticks(range(GRID_SIZE))

    fig.colorbar(im, ax=ax)

    # ===================================================
    # SHOW
    # ===================================================
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------
# ENTRY
# ---------------------------------------------------
if __name__ == "__main__":
    main()