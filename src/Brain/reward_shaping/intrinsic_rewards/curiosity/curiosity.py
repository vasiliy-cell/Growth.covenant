import numpy as np
from collections import defaultdict


class Curiosity:
    def __init__(self, beta, decay=1.0):
        """
        beta  - initial curiosity strength
        decay - decay per episode
        """
        self.beta_start = beta
        self.beta = self.beta_start

        self.decay = decay

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
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        """
        What this agent has already seen, and how loudly novelty still pays.

        The visit counts are the expensive half and they cannot be left out:
        without them a resumed agent finds the whole map new again and its
        intrinsic reward jumps back to where it was at birth.
        """
        return {
            "beta": self.beta,
            "beta_start": self.beta_start,
            "decay": self.decay,
            "visit_counts": dict(self.visit_counts),
        }

    def load_state(self, state):
        self.beta = state["beta"]
        self.beta_start = state["beta_start"]
        self.decay = state["decay"]

        self.visit_counts.clear()
        self.visit_counts.update(state["visit_counts"])

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