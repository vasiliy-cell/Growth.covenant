import json
import os
from collections import Counter
import matplotlib.pyplot as plt
from log_selector import choose_files

LOG_DIR = "logs"


def load_actions(files):
    counter = Counter()

    for file in files:
        path = os.path.join(LOG_DIR, file)

        with open(path) as f:
            for line in f:
                data = json.loads(line)

                if data["type"] == "step":
                    counter[str(data["action"])] += 1

    return counter


def main():
    files = choose_files()
    if not files:
        return

    counter = load_actions(files)

    if not counter:
        print("No actions found")
        return

    plt.figure()

    plt.bar(counter.keys(), counter.values())
    plt.title("Action Distribution")
    plt.xlabel("Action")
    plt.ylabel("Count")
    plt.grid(axis="y")

    plt.show()


if __name__ == "__main__":
    main()