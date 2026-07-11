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


def load_losses(files):

    avg_losses = []       # per-episode avg_loss из episode_summary
    step_losses = []      # per-step loss из всех "step" записей (сквозной, для micro-view)
    betas = []             # curiosity beta по эпизодам, если есть

    missing_avg_loss = 0
    total_summaries = 0

    for file in files:

        path = os.path.join(LOG_DIR, file)
        print(f"Loading {path}")

        with open(path, encoding="utf-8") as f:

            for line in f:

                data = json.loads(line)
                dtype = data.get("type")

                if dtype == "step":
                    if "loss" in data and data["loss"] is not None:
                        step_losses.append(data["loss"])
                    continue

                if dtype != "episode_summary":
                    continue

                total_summaries += 1

                avg_loss = data.get("avg_loss")
                if avg_loss is None:
                    missing_avg_loss += 1
                else:
                    avg_losses.append(avg_loss)

                if "curiosity_beta" in data and data["curiosity_beta"] is not None:
                    betas.append(data["curiosity_beta"])

    if total_summaries > 0:
        print()
        print("=" * 50)
        print(f"episode_summary всего: {total_summaries}")
        print(f"из них БЕЗ avg_loss: {missing_avg_loss} "
              f"({100 * missing_avg_loss / total_summaries:.1f}%)")
        print(f"step-записей с loss: {len(step_losses)}")
        if missing_avg_loss == total_summaries:
            print("!! avg_loss отсутствует ВООБЩЕ во всех summary — "
                  "проверь, что brain.learn() возвращает loss и main.py "
                  "передаёт его в logger.log_step(loss=...).")
        print("=" * 50)

    return (
        np.array(avg_losses),
        np.array(step_losses),
        np.array(betas),
    )


def plot_series(ax, x, values, label, color=None):

    ax.plot(x, values, alpha=0.25, linewidth=1, label=f"{label} raw", color=color)

    smooth = moving_average(values)

    if len(values) >= MA_WINDOW:
        smooth_x = np.arange(MA_WINDOW - 1, len(values))
    else:
        smooth_x = x

    ax.plot(smooth_x, smooth, linewidth=3, label=f"{label} MA", color=color)


def create_table(ax, avg_losses, step_losses):

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
        stats_row("Avg loss / ep", avg_losses),
        stats_row("Loss / step", step_losses),
    ]

    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=["Loss", "Mean", "Max", "Min"],
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

    avg_losses, step_losses, betas = load_losses(files)

    if len(avg_losses) == 0 and len(step_losses) == 0:
        print("No loss data found")
        return

    print()
    print("Episodes with avg_loss:", len(avg_losses))
    print("Total step-level loss points:", len(step_losses))

    fig, (ax_top, ax_bottom, ax_table) = plt.subplots(
        3, 1,
        figsize=(11, 10),
        gridspec_kw={"height_ratios": [3, 3, 1]},
    )

    # --- верхний график: loss по эпизодам (макро-тренд обучения) ---
    if len(avg_losses) > 0:
        x_ep = np.arange(len(avg_losses))
        plot_series(ax_top, x_ep, avg_losses, "Avg loss / episode", color="tab:red")
        ax_top.set_title("Loss per Episode")
        ax_top.set_xlabel("Episode")
        ax_top.set_ylabel("Avg loss")
        ax_top.grid(alpha=0.3)
        ax_top.legend()
    else:
        ax_top.axis("off")
        ax_top.text(0.5, 0.5, "Нет avg_loss в episode_summary", ha="center", va="center")

    # --- нижний график: сквозной loss по шагам (микро-view, шумный) ---
    if len(step_losses) > 0:
        x_step = np.arange(len(step_losses))
        plot_series(ax_bottom, x_step, step_losses, "Loss / step", color="tab:orange")
        ax_bottom.set_title("Loss per Training Step (across loaded episodes)")
        ax_bottom.set_xlabel("Step (сквозной индекс по всем загруженным файлам)")
        ax_bottom.set_ylabel("Loss")
        ax_bottom.grid(alpha=0.3)
        ax_bottom.legend()
    else:
        ax_bottom.axis("off")
        ax_bottom.text(0.5, 0.5, "Нет per-step loss в логах", ha="center", va="center")

    create_table(ax_table, avg_losses, step_losses)

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()