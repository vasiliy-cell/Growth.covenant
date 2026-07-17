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


def load_grad_norms(files):

    avg_grad_norms = []    # per-episode avg_grad_norm из episode_summary
    step_grad_norms = []   # per-step grad_norm из всех "step" записей (сквозной, для micro-view)

    missing_avg_grad_norm = 0
    total_summaries = 0

    for file in files:

        path = os.path.join(LOG_DIR, file)
        print(f"Loading {path}")

        with open(path, encoding="utf-8") as f:

            for line in f:

                data = json.loads(line)
                dtype = data.get("type")

                if dtype == "step":
                    if "grad_norm" in data and data["grad_norm"] is not None:
                        step_grad_norms.append(data["grad_norm"])
                    continue

                if dtype != "episode_summary":
                    continue

                total_summaries += 1

                avg_grad_norm = data.get("avg_grad_norm")
                if avg_grad_norm is None:
                    missing_avg_grad_norm += 1
                else:
                    avg_grad_norms.append(avg_grad_norm)

    if total_summaries > 0:
        print()
        print("=" * 50)
        print(f"episode_summary всего: {total_summaries}")
        print(f"из них БЕЗ avg_grad_norm: {missing_avg_grad_norm} "
              f"({100 * missing_avg_grad_norm / total_summaries:.1f}%)")
        print(f"step-записей с grad_norm: {len(step_grad_norms)}")
        if missing_avg_grad_norm == total_summaries:
            print("!! avg_grad_norm отсутствует ВООБЩЕ во всех summary — "
                  "проверь, что trainer возвращает grad_norm и logger.log_step(grad_norm=...) вызывается.")
        print("=" * 50)

    return (
        np.array(avg_grad_norms),
        np.array(step_grad_norms),
    )


def plot_series(ax, x, values, label, color=None):

    ax.plot(x, values, alpha=0.25, linewidth=1, label=f"{label} raw", color=color)

    smooth = moving_average(values)

    if len(values) >= MA_WINDOW:
        smooth_x = np.arange(MA_WINDOW - 1, len(values))
    else:
        smooth_x = x

    ax.plot(smooth_x, smooth, linewidth=3, label=f"{label} MA", color=color)


def create_table(ax, avg_grad_norms, step_grad_norms):

    def stats_row(name, arr):
        if len(arr) == 0:
            return [name, "-", "-", "-"]
        return [
            name,
            f"{np.mean(arr):.4f}",
            f"{np.max(arr):.4f}",
            f"{np.min(arr):.4f}",
        ]

    rows = [
        stats_row("Avg grad norm / ep", avg_grad_norms),
        stats_row("Grad norm / step", step_grad_norms),
    ]

    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=["Grad Norm", "Mean", "Max", "Min"],
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

    avg_grad_norms, step_grad_norms = load_grad_norms(files)

    if len(avg_grad_norms) == 0 and len(step_grad_norms) == 0:
        print("No gradient norm data found")
        return

    print()
    print("Episodes with avg_grad_norm:", len(avg_grad_norms))
    print("Total step-level grad_norm points:", len(step_grad_norms))

    fig, (ax_top, ax_bottom, ax_table) = plt.subplots(
        3, 1,
        figsize=(11, 10),
        gridspec_kw={"height_ratios": [3, 3, 1]},
    )

    # --- верхний график: grad norm по эпизодам (макро-тренд обучения) ---
    if len(avg_grad_norms) > 0:
        x_ep = np.arange(len(avg_grad_norms))
        plot_series(ax_top, x_ep, avg_grad_norms, "Avg grad norm / episode", color="tab:blue")
        ax_top.set_title("Gradient Norm per Episode")
        ax_top.set_xlabel("Episode")
        ax_top.set_ylabel("Avg grad norm")
        ax_top.grid(alpha=0.3)
        ax_top.legend()
    else:
        ax_top.axis("off")
        ax_top.text(0.5, 0.5, "Нет avg_grad_norm в episode_summary", ha="center", va="center")

    # --- нижний график: сквозной grad norm по шагам (микро-view, шумный) ---
    if len(step_grad_norms) > 0:
        x_step = np.arange(len(step_grad_norms))
        plot_series(ax_bottom, x_step, step_grad_norms, "Grad norm / step", color="tab:purple")
        ax_bottom.set_title("Gradient Norm per Training Step (across loaded episodes)")
        ax_bottom.set_xlabel("Step (сквозной индекс по всем загруженным файлам)")
        ax_bottom.set_ylabel("Grad norm")
        ax_bottom.grid(alpha=0.3)
        ax_bottom.legend()
    else:
        ax_bottom.axis("off")
        ax_bottom.text(0.5, 0.5, "Нет per-step grad_norm в логах", ha="center", va="center")

    create_table(ax_table, avg_grad_norms, step_grad_norms)

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
