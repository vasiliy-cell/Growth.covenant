import json
import os
import matplotlib.pyplot as plt
import numpy as np


LOG_DIR = "logs"


def get_log_files():
    files = sorted(
        [f for f in os.listdir(LOG_DIR) if f.endswith(".jsonl")],
        key=lambda x: os.path.getmtime(os.path.join(LOG_DIR, x))
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
    print("4 - First N logs")

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

    elif choice == "4":
        try:
            n = int(input("Enter number of first logs: "))
            return files[:n]
        except:
            print("Invalid input")
            return []

    else:
        print("Unknown choice")
        return []


def load_rewards(selected_files):
    rewards = []

    for file in selected_files:
        total_reward = 0

        with open(os.path.join(LOG_DIR, file)) as f:
            for line in f:
                data = json.loads(line)
                if data["type"] == "step":
                    total_reward += data["reward"]

        rewards.append(total_reward)

    return rewards


def main():
    selected_files = choose_files()

    if not selected_files:
        return

    print(f"\nUsing {len(selected_files)} log file(s):")
    for f in selected_files:
        print(f" - {f}")

    rewards = load_rewards(selected_files)

    episodes = np.arange(len(rewards))

    avg_reward = np.mean(rewards) if rewards else 0

    plt.figure()
    plt.plot(episodes, rewards, marker="o")

    plt.title("Total Reward per Episode")
    plt.xlabel("Episode")
    plt.ylabel("Total Reward")

    plt.xticks(episodes)

    # average reward text
    plt.text(
        0.02,
        0.95,
        f"Avg Reward: {avg_reward:.2f}",
        transform=plt.gca().transAxes,
        verticalalignment='top'
    )

    plt.grid()
    plt.show()


if __name__ == "__main__":
    main()