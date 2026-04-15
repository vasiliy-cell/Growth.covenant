import json
import os
import numpy as np
import matplotlib.pyplot as plt


LOG_DIR = "logs"
GRID_SIZE = 8


def load_positions():
    grid = np.zeros((GRID_SIZE, GRID_SIZE))

    for file in os.listdir(LOG_DIR):
        if file.endswith(".jsonl"):
            with open(os.path.join(LOG_DIR, file)) as f:
                for line in f:
                    data = json.loads(line)

                    if data["type"] == "step":
                        x, y = data["position"]

                        #  защита от вложенных списков
                        if isinstance(x, list):
                            x, y = x

                        x = int(x)
                        y = int(y)

                        grid[x][y] += 1

    return grid


def main():
    heatmap = load_positions()

    # приводим к системе:
    # (0,0) = верхний левый
    heatmap = np.flipud(heatmap)

    # чуть выше окно, но не раздуваем
    fig, ax = plt.subplots(figsize=(6, 7))

    im = ax.imshow(heatmap)

    #  X сверху (как ты хотел)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position('top')

    ax.set_title("Agent Position Heatmap", pad=15)

    ax.set_xlabel("X →")
    ax.set_ylabel("Y ↓")

    ax.set_xticks(range(GRID_SIZE))
    ax.set_yticks(range(GRID_SIZE))

    fig.colorbar(im)

    plt.tight_layout()  #  чтобы ничего не резалось

    plt.show()


if __name__ == "__main__":
    main()