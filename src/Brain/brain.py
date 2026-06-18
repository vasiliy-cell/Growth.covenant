import torch


class Brain:
    def __init__(self, trainer, epsilon=0.1):
        self.trainer = trainer
        self.model = trainer.model
        self.epsilon = epsilon

    def choose_action(self, state, available_actions):
        import random
        import torch

        if random.random() < self.epsilon:
            return random.choice(available_actions)

        # ALWAYS call model directly from trainer
        q_values = self.trainer.model(state)

        # convert safely
        if hasattr(q_values, "tolist"):
            q_values = q_values.tolist()

        best_action = max(
            available_actions,
            key=lambda a: q_values[a]
        )

        return best_action
    def learn(self, state, action, reward, next_state, done):
        self.trainer.update(state, action, reward, next_state, done)