from src.Brain.policy.argmax import argmax
from src.Brain.policy.epsilon_greedy import EpsilonGreedy


class Policy:
    def __init__(self, config):
        """
        Policy is a strategy dispatcher.
        It does NOT contain magic numbers.
        Everything comes from config.
        """

        policy_cfg = config["policy"]

        self.mode = policy_cfg["mode"]
        self.epsilon = policy_cfg["epsilon"]

        # FIX: создаём объект стратегии один раз
        self.epsilon_greedy = EpsilonGreedy(policy_cfg)

    def select_action(self, q_values, available_actions):
        """
        Delegates action selection to specific strategy
        """

        if self.mode == "argmax":
            return argmax(q_values, available_actions)

        elif self.mode == "epsilon_greedy":
            return self.epsilon_greedy.select_action(
                q_values,
                available_actions
            )

        else:
            raise ValueError(f"Unknown policy mode: {self.mode}")