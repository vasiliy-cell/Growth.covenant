import os
import json
import matplotlib.pyplot as plt
import numpy as np
from log_selector import choose_files

LOG_DIR = "logs"


def load_td_metrics(files):
    td_per_episode = []
    abs_td_per_episode = []

    for file in files:
        path = os.path.join(LOG_DIR, file)

        td_values = []
        abs_td_values = []

        with open(path) as f:
            for line in f:
                data = json.loads(line)

                if data["type"] == "step" and "td_error" in data:
                    td_values.append(data["td_error"])
                    abs_td_values.append(data["abs_td_error"])

        # если вдруг пусто
        if len(td_values) == 0:
            td_per_episode.append(0)
            abs_td_per_episode.append(0)
        else:
            td_per_episode.append(np.mean(td_values))
            abs_td_per_episode.append(np.mean(abs_td_values))

    return td_per_episode, abs_td_per_episode


def main():
    files = choose_files()
    if not files:
        return

    td, abs_td = load_td_metrics(files)

    x = np.arange(len(files))

    avg_td = np.mean(td) if td else 0
    avg_abs_td = np.mean(abs_td) if abs_td else 0

    plt.figure()

    # --- signed TD ---
    plt.plot(x, td, marker="o", label="TD error (mean)")

    # --- absolute TD ---
    plt.plot(x, abs_td, marker="o", label="|TD error| (mean)")

    plt.title("TD Error per Episode")
    plt.xlabel("Episode")
    plt.ylabel("TD Error")

    # --- text info ---
    plt.text(
        0.02, 0.95,
        f"Avg TD: {avg_td:.3f}\nAvg |TD|: {avg_abs_td:.3f}",
        transform=plt.gca().transAxes
    )

    plt.grid()
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()