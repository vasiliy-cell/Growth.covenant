import matplotlib.pyplot as plt
import numpy as np
from log_selector import choose_files
from episode_grouping import group_steps_by_episode


def count_steps(files):
    # One file holds the whole run, so episodes come from the `episode` field
    # of each step, not from the file list.
    return [len(steps) for _, steps in group_steps_by_episode(files)]


def main():
    files = choose_files()
    if not files:
        return

    steps = count_steps(files)

    if not steps:
        print("No steps found")
        return

    x = np.arange(1, len(steps) + 1)

    plt.figure()
    plt.plot(x, steps, marker="o")

    plt.title("Steps per Episode")
    plt.xlabel("Episode")
    plt.ylabel("Steps")
    plt.grid()

    plt.show()


if __name__ == "__main__":
    main()
