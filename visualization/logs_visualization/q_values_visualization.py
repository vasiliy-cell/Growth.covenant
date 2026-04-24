import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import yaml

# ---------------------------------------------------
# FIX: add project root to Python path
# ---------------------------------------------------
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../")
)
sys.path.append(PROJECT_ROOT)

from Brain.q_table.q_function import QFunction


# ---------------------------------------------------
# ACTIONS (same as environment)
# ---------------------------------------------------
ACTIONS = {
    0: (0, -1),   # up
    1: (0, 1),    # down
    2: (-1, 0),   # left
    3: (1, 0),    # right
    4: (-1, -1),  # up-left
    5: (1, -1),   # up-right
    6: (-1, 1),   # down-left
    7: (1, 1),    # down-right
}


# ---------------------------------------------------
# VISUALIZATION
# ---------------------------------------------------
def visualize_q_values(q_table, grid_size=8):
    plt.figure(figsize=(6, 6))

    states_drawn = 0

    for state_key, q_values in q_table.q_table.items():

        position, _ = state_key
        x, y = position

        if np.all(q_values == 0):
            continue

        best_action = int(np.argmax(q_values))
        dx, dy = ACTIONS[best_action]
        best_q = q_values[best_action]

        plt.arrow(
            x, y,
            dx * 0.3,
            dy * 0.3,
            head_width=0.2,
            head_length=0.2,
            fc="black",
            ec="black",
            length_includes_head=True
        )

        states_drawn += 1

    plt.title(f"Q-Policy Visualization | states={states_drawn}")
    plt.xlim(-0.5, grid_size - 0.5)
    plt.ylim(-0.5, grid_size - 0.5)
    plt.gca().invert_yaxis()
    plt.grid(True)

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