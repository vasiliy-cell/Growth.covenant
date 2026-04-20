import numpy as np
import os


class QTable:
    def __init__(self, state_size, action_size=8, checkpoint_path="Brain/models/qtable_checkpoint.npy"):
        self.state_size = state_size
        self.action_size = action_size
        self.checkpoint_path = checkpoint_path

        self.q_table = self._load_or_create()

    # -----------------------------
    # INIT / LOAD
    # -----------------------------
    def _load_or_create(self):
        if os.path.exists(self.checkpoint_path):
            print(f"[QTable] Loading checkpoint: {self.checkpoint_path}")
            return np.load(self.checkpoint_path, allow_pickle=True)

        print("[QTable] Creating new Q-table")
        return np.zeros((self.state_size, self.action_size))

    # -----------------------------
    # SAVE
    # -----------------------------
    def save(self):
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        np.save(self.checkpoint_path, self.q_table)
        print(f"[QTable] Saved to {self.checkpoint_path}")

    # -----------------------------
    # ACCESS ONLY (NO LOGIC)
    # -----------------------------
    def get(self, state_index, action):
        return self.q_table[state_index][action]

    def set(self, state_index, action, value):
        self.q_table[state_index][action] = value

    def get_row(self, state_index):
        return self.q_table[state_index]

    # -----------------------------
    # DEBUG
    # -----------------------------
    def __repr__(self):
        return f"QTable(shape={self.q_table.shape})"