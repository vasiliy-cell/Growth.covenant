import json
import os
import matplotlib.pyplot as plt
import numpy as np


LOG_DIR = "logs"


def get_log_files():
    files = sorted(
        [f for f in os.listdir(LOG_DIR) if f.endswith(".jsonl")]
    )
    return files


def choose_files():
    files = get_log_files()

    if not files:
        print("No log files found")
        return []

    print("\nSelect mode:")
    print("1 - All logs")
    print("2 - Last log only")
    print("3 - Last N logs")

    choice = input("Enter choice: ").strip()

    if choice == "1":
        return files

    elif choice == "2":
        return [files[-1]]

    elif choice == "3":
        try:
            n = int(input("Enter number of last logs: "))
            return files[-n:]
        except:
            print("Invalid input")
            return []

    else:
        print("Unknown choice")
        return []


def load_steps(selected_files):
    steps = []

    for file in selected_files:
        count = 0

        with open(os.path.join(LOG_DIR, file)) as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "step":
                    count += 1

        steps.append(count)

    return steps


def main():
    selected_files = choose_files()

    if not selected_files:
        return

    print(f"\nUsing {len(selected_files)} log file(s):")
    for f in selected_files:
        print(f" - {f}")

    steps = load_steps(selected_files)

    episodes = np.arange(len(steps))

    plt.figure()
    plt.plot(episodes, steps, marker="o")

    plt.title("Steps per Episode")
    plt.xlabel("Episode")
    plt.ylabel("Steps")

    plt.xticks(episodes)

    plt.grid()
    plt.show()


if __name__ == "__main__":
    main()