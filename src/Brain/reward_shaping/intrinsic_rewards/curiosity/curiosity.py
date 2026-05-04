import numpy as np
from collections import defaultdict


class Curiosity:
    def __init__(self, config: dict):
        """
        config:
            beta  - initial curiosity strength
            decay - decay per episode (optional)
        """
        self.beta_start = config["beta"]
        self.beta = self.beta_start

        self.decay = config.get("decay", 1.0)

        # state visit counter
        self.visit_counts = defaultdict(int)

    # -----------------------------
    # STATE → KEY
    # -----------------------------
    def _state_to_key(self, state):
        """
        Convert state into a hashable key
        Priority:
        1. state.to_key()  (best, consistent with Q-table)
        2. numpy array → tuple
        3. fallback → string
        """

        # preferred way (your system already uses this)
        if hasattr(state, "to_key"):
            return state.to_key()

        # numpy observation
        if isinstance(state, np.ndarray):
            return tuple(state.flatten())

        # fallback
        return str(state)

    # -----------------------------
    # STEP
    # -----------------------------
    def step(self, state):
        """
        Called each step.
        Returns intrinsic reward.
        """

        key = self._state_to_key(state)

        # increment visit count
        self.visit_counts[key] += 1
        N = self.visit_counts[key]

        # curiosity reward
        r_curiosity = self.beta * (1.0 / np.sqrt(N))

        return r_curiosity

    # -----------------------------
    # RESET (per episode)
    # -----------------------------
    def reset(self):
        """
        Called at the start of each episode
        """

        # clear episodic memory
        self.visit_counts.clear()

        # apply decay once per episode
        self.beta *= self.decay