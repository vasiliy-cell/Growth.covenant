import os
import json
import numpy as np
import matplotlib.pyplot as plt

from log_selector import choose_files


LOG_DIR = "logs"

MA_WINDOW = 25


def moving_average(data, window=MA_WINDOW):
    data = np.asarray(data)

    if len(data) < window:
        return data

    return np.convolve(
        data,
        np.ones(window) / window,
        mode="valid"
    )


def load_target_vs_prediction(files):

    target_q = []
    q_prediction = []

    missing = 0
    total_summaries = 0

    for file in files:

        path = os.path.join(LOG_DIR, file)

        with open(path, encoding="utf-8") as f:

            for line in f:

                data = json.loads(line)

                if data.get("type") != "episode_summary":
                    continue

                total_summaries += 1

                t = data.get("avg_target_q")
                q = data.get("avg_q_prediction")

                if t is None or q is None:
                    missing += 1
                    continue

                target_q.append(t)
                q_prediction.append(q)

    if total_summaries > 0:
        print()
        print("=" * 50)
        print(f"episode_summary всего: {total_summaries}")
        print(f"из них БЕЗ avg_target_q/avg_q_prediction: {missing} "
              f"({100 * missing / total_summaries:.1f}%)")
        print("=" * 50)

    return np.array(target_q), np.array(q_prediction)


def plot_series(ax, x, values, label, color):

    ax.plot(x, values, alpha=0.25, linewidth=1, color=color, label=f"{label} raw")

    smooth = moving_average(values)

    if len(values) >= MA_WINDOW:
        smooth_x = np.arange(MA_WINDOW - 1, len(values))
    else:
        smooth_x = x

    ax.plot(smooth_x, smooth, linewidth=3, color=color, label=f"{label} MA")


def create_table(ax, target_q, q_prediction):

    gap = target_q - q_prediction

    rows = [
        ["Target Q", f"{np.mean(target_q):.2f}", f"{np.max(target_q):.2f}", f"{np.min(target_q):.2f}"],
        ["Q prediction", f"{np.mean(q_prediction):.2f}", f"{np.max(q_prediction):.2f}", f"{np.min(q_prediction):.2f}"],
        ["Gap (target - pred)", f"{np.mean(gap):.2f}", f"{np.max(gap):.2f}", f"{np.min(gap):.2f}"],
    ]

    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=["Metric", "Mean", "Max", "Min"],
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

    target_q, q_prediction = load_target_vs_prediction(files)

    if len(target_q) == 0:
        print("No avg_target_q / avg_q_prediction found in episode_summary")
        return

    print()
    print("Episodes loaded:", len(target_q))

    x = np.arange(len(target_q))

    fig, (ax_plot, ax_gap, ax_table) = plt.subplots(
        3, 1,
        figsize=(11, 10),
        gridspec_kw={"height_ratios": [3, 2, 1]},
    )

    # --- верхний график: target_q и q_prediction на одной оси ---
    plot_series(ax_plot, x, target_q, "Target Q", color="tab:blue")
    plot_series(ax_plot, x, q_prediction, "Q prediction", color="tab:red")

    ax_plot.set_title("Target Q vs Q Prediction (per episode avg)")
    ax_plot.set_xlabel("Episode")
    ax_plot.set_ylabel("Q value")
    ax_plot.grid(alpha=0.3)
    ax_plot.legend()

    # --- нижний график: разрыв между ними — сходится или расходится ---
    gap = target_q - q_prediction
    ax_gap.plot(x, gap, alpha=0.3, linewidth=1, color="tab:purple", label="gap raw")

    gap_smooth = moving_average(gap)
    if len(gap) >= MA_WINDOW:
        gap_x = np.arange(MA_WINDOW - 1, len(gap))
    else:
        gap_x = x
    ax_gap.plot(gap_x, gap_smooth, linewidth=3, color="tab:purple", label="gap MA")

    ax_gap.axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.5)
    ax_gap.set_title("Gap = Target Q - Q Prediction (0 = идеальная сходимость)")
    ax_gap.set_xlabel("Episode")
    ax_gap.set_ylabel("Gap")
    ax_gap.grid(alpha=0.3)
    ax_gap.legend()

    create_table(ax_table, target_q, q_prediction)

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()