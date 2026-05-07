import json
import os
import numpy as np
import matplotlib.pyplot as plt
from log_selector import choose_files

LOG_DIR = "logs"
GRID_SIZE = 8


def load_positions(files):
    grid = np.zeros((GRID_SIZE, GRID_SIZE))

    for file in files:
        path = os.path.join(LOG_DIR, file)

        with open(path) as f:
            for line in f:
                data = json.loads(line)

                if data["type"] == "step":
                    x, y = data["position"]

                    if isinstance(x, list):
                        x, y = x

                    grid[int(x)][int(y)] += 1

    return grid


def main():
    files = choose_files()
    if not files:
        return

    print("\nUsing:")
    for f in files:
        print(" -", f)

    heatmap = load_positions(files)

    plt.figure(figsize=(6, 6))
    plt.imshow(heatmap)

    plt.title("Agent Position Heatmap")
    plt.colorbar()

    plt.xticks(range(GRID_SIZE))
    plt.yticks(range(GRID_SIZE))

    plt.show()


if __name__ == "__main__":
    main()