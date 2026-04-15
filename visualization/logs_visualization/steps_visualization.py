import json
import os
import matplotlib.pyplot as plt
import numpy as np


LOG_DIR = "logs"


def load_steps():
    steps = []

    files = sorted(os.listdir(LOG_DIR))

    for file in files:
        if file.endswith(".jsonl"):
            count = 0

            with open(os.path.join(LOG_DIR, file)) as f:
                for line in f:
                    data = json.loads(line)
                    if data["type"] == "step":
                        count += 1

            steps.append(count)

    return steps


def main():
    steps = load_steps()

    episodes = np.arange(len(steps))

    plt.figure()
    plt.plot(episodes, steps, marker="o")

    plt.title("Steps per Episode")
    plt.xlabel("Episode")
    plt.ylabel("Steps")

    plt.xticks(episodes)  #  фикс дробных значений

    plt.grid()
    plt.show()


if __name__ == "__main__":
    main()