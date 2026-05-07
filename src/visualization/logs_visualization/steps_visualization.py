import os
import json
import matplotlib.pyplot as plt
import numpy as np
from log_selector import choose_files

LOG_DIR = "logs"


def count_steps(files):
    steps = []

    for file in files:
        path = os.path.join(LOG_DIR, file)

        count = 0
        with open(path) as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "step":
                    count += 1

        steps.append(count)

    return steps


def main():
    files = choose_files()
    if not files:
        return

    steps = count_steps(files)

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