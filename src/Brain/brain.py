import torch


class Brain:
    def __init__(self, trainer, epsilon=0.1):
        self.trainer = trainer
        self.model = trainer.model
        self.epsilon = epsilon

    def choose_action(self, state, available_actions):
        import random

        if random.random() < self.epsilon:
            return random.choice(available_actions)

        with torch.no_grad():
            q_values = self.model(state)
            q_values = q_values.tolist()

        best_action = max(available_actions, key=lambda a: q_values[a])
        return best_action

    def learn(self, state, action, reward, next_state, done):
        self.trainer.update(state, action, reward, next_state, done)