import json
import os
import numpy as np
import matplotlib.pyplot as plt


LOG_DIR = "logs"
GRID_SIZE = 8


def get_log_files():
    files = sorted(
        [f for f in os.listdir(LOG_DIR) if f.endswith(".jsonl")]
    )
    return files


def choose_files():
    files = get_log_files()

    if not files:
        print("No logs")
        return []

    print("\nChoose mode:")
    print("1 - All logs")
    print("2 - Only the latest")
    print("3 - Last N logs")

    choice = input("Your choice: ").strip()

    if choice == "1":
        return files

    elif choice == "2":
        return [files[-1]]

    elif choice == "3":
        try:
            n = int(input("How many last logs to use: "))
            return files[-n:]
        except:
            print("Invalid input")
            return []

    else:
        print("Unknown choice")
        return []


def load_positions(selected_files):
    grid = np.zeros((GRID_SIZE, GRID_SIZE))

    for file in selected_files:
        with open(os.path.join(LOG_DIR, file)) as f:
            for line in f:
                data = json.loads(line)

                if data["type"] == "step":
                    x, y = data["position"]

                    if isinstance(x, list):
                        x, y = x

                    x = int(x)
                    y = int(y)

                    grid[x][y] += 1

    return grid


def main():
    selected_files = choose_files()

    if not selected_files:
        return

    print(f"\n Using {len(selected_files)} log(s):")
    for f in selected_files:
        print(" -", f)

    heatmap = load_positions(selected_files)

    fig, ax = plt.subplots(figsize=(6, 7))

    im = ax.imshow(heatmap)

    ax.xaxis.tick_top()
    ax.xaxis.set_label_position('top')

    ax.set_title("Agent Position Heatmap", pad=15)

    ax.set_xlabel("X →")
    ax.set_ylabel("Y ↓")

    ax.set_xticks(range(GRID_SIZE))
    ax.set_yticks(range(GRID_SIZE))

    fig.colorbar(im)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()

