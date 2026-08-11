import matplotlib.pyplot as plt
import numpy as np
from log_selector import choose_files
from episode_grouping import group_steps_by_episode


def load_td_metrics(files):
    td_per_episode = []
    abs_td_per_episode = []

    # One file holds the whole run, so episodes come from the `episode` field
    # of each step, not from the file list.
    for _, steps in group_steps_by_episode(files):

        td_values = [s["td_error"] for s in steps if "td_error" in s]
        abs_td_values = [s["abs_td_error"] for s in steps if "abs_td_error" in s]

        # empty window (e.g. buffer still warming up)
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

    if not td:
        print("No steps found")
        return

    x = np.arange(len(td))

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
