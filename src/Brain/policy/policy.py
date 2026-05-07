from src.Brain.policy.argmax import argmax
from src.Brain.policy.epsilon_greedy import epsilon_greedy


class Policy:
    def __init__(self, config):
        """
        Policy is a strategy dispatcher.
        It does NOT contain magic numbers.
        Everything comes from config.
        """

        self.mode = config["policy"]
        self.epsilon = config["epsilon"]

    def select_action(self, q_values, available_actions):
        """
        Delegates action selection to specific strategy
        """

        if self.mode == "argmax":
            return argmax(q_values, available_actions)

        elif self.mode == "epsilon_greedy":
            return epsilon_greedy(
                q_values=q_values,
                available_actions=available_actions,
                epsilon=self.epsilon
            )

        else:
            raise ValueError(f"Unknown policy mode: {self.mode}")