import json
import os
from collections import Counter
import matplotlib.pyplot as plt


LOG_DIR = "logs"


def load_actions():
    counter = Counter()

    for file in os.listdir(LOG_DIR):
        if file.endswith(".jsonl"):
            with open(os.path.join(LOG_DIR, file)) as f:
                for line in f:
                    data = json.loads(line)

                    if data["type"] == "step":
                        action = data["action"]

                        #  приводим к строке безопасно
                        counter[str(action)] += 1

    return counter


def main():
    counter = load_actions()

    if not counter:
        print("No actions found in logs")
        return

    actions = list(counter.keys())   #  ломаем порядок
    counts = [counter[a] for a in actions]

    plt.figure()
    plt.bar(actions, counts)

    plt.title("Action Distribution")
    plt.xlabel("Action")
    plt.ylabel("Count")

    plt.grid(axis="y")

    plt.show()


if __name__ == "__main__":
    main()