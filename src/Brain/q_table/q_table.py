import os
import numpy as np


class QTable:
    def __init__(self, action_size=8, checkpoint_path="/models/qtable_checkpoint.npy"):

        if isinstance(action_size, dict):
            action_size = action_size.get("action_size", 8)

        self.action_size = action_size
        self.checkpoint_path = checkpoint_path

        self.q_table = self._load_or_create()

    # -----------------------------
    # LOAD / CREATE
    # -----------------------------
    def _load_or_create(self):
        if os.path.exists(self.checkpoint_path):
            print(f"[QTable] Loading checkpoint: {self.checkpoint_path}")
            try:
                return np.load(self.checkpoint_path, allow_pickle=True).item()
            except:
                print("[QTable] Corrupted checkpoint → resetting")
                return {}

        print("[QTable] Creating new Q-table")
        return {}

    # -----------------------------
    # GET
    # -----------------------------
    def get_row(self, state_key):
        if state_key not in self.q_table:
            self.q_table[state_key] = np.zeros(self.action_size)
        return self.q_table[state_key]

    # -----------------------------
    # SET
    # -----------------------------
    def set(self, state_key, action, value):
        if state_key not in self.q_table:
            self.q_table[state_key] = np.zeros(self.action_size)

        self.q_table[state_key][action] = value

    # -----------------------------
    # SAVE
    # -----------------------------
    def save(self):
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        np.save(self.checkpoint_path, self.q_table, allow_pickle=True)
        print(f"[QTable] Saved to {self.checkpoint_path}")

    def __repr__(self):
        return f"QTable(states={len(self.q_table)}, actions={self.action_size})"