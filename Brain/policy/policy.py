from Brain.policy.argmax import argmax


class Policy:
    def __init__(self, mode="argmax"):
        """
        mode:
            - "argmax" (default)
            - later: "epsilon_greedy", etc.
        """
        self.mode = mode

    def select_action(self, q_values, available_actions):
        """
        q_values: array of Q-values for current state
        available_actions: allowed actions

        returns: action
        """

        if self.mode == "argmax":
            return argmax(q_values, available_actions)

        else:
            raise ValueError(f"Unknown policy mode: {self.mode}")