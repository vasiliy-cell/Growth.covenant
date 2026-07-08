import os
import json
import numpy as np
import matplotlib.pyplot as plt

from log_selector import choose_files


LOG_DIR = "logs"

MA_WINDOW = 25


def moving_average(data, window=MA_WINDOW):
    """
    Moving average для сглаживания RL графиков
    """
    data = np.asarray(data)

    if len(data) < window:
        return data

    return np.convolve(
        data,
        np.ones(window) / window,
        mode="valid"
    )


def load_rewards(files):

    env_rewards = []
    training_rewards = []
    intrinsic_rewards = []

    # диагностика: сколько episode_summary реально не содержали intrinsic_reward
    missing_intrinsic = 0
    total_summaries = 0

    for file in files:

        path = os.path.join(LOG_DIR, file)
        print(f"Loading {path}")

        with open(path, encoding="utf-8") as f:

            for line in f:

                data = json.loads(line)

                if data.get("type") != "episode_summary":
                    continue

                total_summaries += 1

                env_rewards.append(data["env_reward"])
                training_rewards.append(data["training_reward"])

                if "intrinsic_reward" in data:
                    intrinsic_rewards.append(data["intrinsic_reward"])
                else:
                    missing_intrinsic += 1
                    intrinsic_rewards.append(0.0)

    # Явная сводка вместо потерянного WARNING в потоке принтов
    if total_summaries > 0:
        print()
        print("=" * 50)
        print(f"episode_summary всего: {total_summaries}")
        print(f"из них БЕЗ intrinsic_reward: {missing_intrinsic} "
              f"({100 * missing_intrinsic / total_summaries:.1f}%)")
        if missing_intrinsic == total_summaries:
            print("!! intrinsic_reward отсутствует ВООБЩЕ во всех summary — "
                  "проблема в логгере, который пишет episode_summary, "
                  "а не в этом скрипте.")
        elif missing_intrinsic > 0:
            print("!! intrinsic_reward отсутствует частично — "
                  "возможно, логика записи intrinsic непоследовательна между эпизодами.")
        print("=" * 50)

    return (
        np.array(env_rewards),
        np.array(training_rewards),
        np.array(intrinsic_rewards),
    )


def plot_reward(ax, x, rewards, label):

    ax.plot(x, rewards, alpha=0.25, linewidth=1, label=f"{label} raw")

    smooth = moving_average(rewards)

    if len(rewards) >= MA_WINDOW:
        smooth_x = np.arange(MA_WINDOW - 1, len(rewards))
    else:
        smooth_x = x

    ax.plot(smooth_x, smooth, linewidth=3, label=f"{label} MA")


def create_table(ax, env_rewards, training_rewards, intrinsic_rewards):

    rows = [
        ["Env", f"{np.mean(env_rewards):.2f}", f"{np.max(env_rewards):.2f}", f"{np.min(env_rewards):.2f}"],
        ["Training", f"{np.mean(training_rewards):.2f}", f"{np.max(training_rewards):.2f}", f"{np.min(training_rewards):.2f}"],
        ["Intrinsic", f"{np.mean(intrinsic_rewards):.2f}", f"{np.max(intrinsic_rewards):.2f}", f"{np.min(intrinsic_rewards):.2f}"],
    ]

    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=["Reward", "Mean", "Max", "Min"],
        cellLoc="center",
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)


def main():

    files = choose_files()

    if not files:
        return

    env_rewards, training_rewards, intrinsic_rewards = load_rewards(files)

    if len(env_rewards) == 0:
        print("No episode_summary found")
        return

    print()
    print("Episodes loaded:", len(env_rewards))
    print("Intrinsic first values:", intrinsic_rewards[:10])

    x = np.arange(len(env_rewards))

    # Отдельные оси для графика и для таблицы — больше никакого наезда
    fig, (ax_plot, ax_table) = plt.subplots(
        2, 1,
        figsize=(11, 8),
        gridspec_kw={"height_ratios": [4, 1]},
    )

    plot_reward(ax_plot, x, env_rewards, "Environment")
    plot_reward(ax_plot, x, training_rewards, "Training")
    plot_reward(ax_plot, x, intrinsic_rewards, "Intrinsic")

    ax_plot.set_title("Reward Evolution")
    ax_plot.set_xlabel("Episode")
    ax_plot.set_ylabel("Reward")
    ax_plot.grid(alpha=0.3)
    ax_plot.legend()

    create_table(ax_table, env_rewards, training_rewards, intrinsic_rewards)

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()