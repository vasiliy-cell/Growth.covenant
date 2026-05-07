import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import yaml

# ---------------------------------------------------
# PROJECT ROOT
# ---------------------------------------------------
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../")
)
sys.path.append(PROJECT_ROOT)

from src.Brain.q_table.q_function import QFunction


# ---------------------------------------------------
# ACTIONS
# ---------------------------------------------------
ACTIONS = {
    0: (0, -1),
    1: (0, 1),
    2: (-1, 0),
    3: (1, 0),
    4: (-1, -1),
    5: (1, -1),
    6: (-1, 1),
    7: (1, 1),
}


# ---------------------------------------------------
# VISUALIZATION
# ---------------------------------------------------
def visualize_q_values(q_table, grid_size=8):

    fig, ax = plt.subplots(figsize=(8, 8))

    states_drawn = 0

    for state_key, q_values in q_table.q_table.items():

        position, _ = state_key
        x, y = position

        if np.all(q_values == 0):
            continue

        best_action = int(np.argmax(q_values))
        best_q = np.max(q_values)

        dx, dy = ACTIONS[best_action]

        ax.arrow(
            y,
            x,
            dy * 0.35,
            dx * 0.35,
            head_width=0.12,
            head_length=0.12,
            fc="black",
            ec="black",
            length_includes_head=True
        )

        ax.text(
            y,
            x,
            f"{best_q:.1f}",
            fontsize=7,
            ha="center",
            va="center"
        )

        states_drawn += 1

    ax.set_title(f"Q Policy | states={states_drawn}")

    ax.set_xlim(-0.5, grid_size - 0.5)
    ax.set_ylim(-0.5, grid_size - 0.5)

    ax.set_xticks(range(grid_size))
    ax.set_yticks(range(grid_size))

    ax.invert_yaxis()
    ax.grid(True)

    plt.show()

# ---------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------
if __name__ == "__main__":

    print("Loading config...")

    config_path = os.path.join(PROJECT_ROOT, "Brain/config.yml")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    print("Loading QFunction...")

    q_function = QFunction(config)

    print("Q-table states:", len(q_function.q_table.q_table))

    visualize_q_values(q_function.q_table)