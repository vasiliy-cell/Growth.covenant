import random
from src.Brain.policy.argmax import argmax


class EpsilonGreedy:
    def __init__(self, config):
        self.epsilon_start = config["epsilon"]
        self.decay = config["epsilon_decay"]
        self.epsilon_min = config.get("epsilon_min", 0.01)

        self.episode = 0
        self.epsilon = self.epsilon_start

    def next_episode(self):
        self.episode += 1

        self.epsilon = self.epsilon_start * (self.decay ** self.episode)

        if self.epsilon < self.epsilon_min:
            self.epsilon = self.epsilon_min

    def select_action(self, q_values, available_actions):
        if not available_actions:
            raise ValueError("No available actions")

        # exploration
        if random.random() < self.epsilon:
            return random.choice(available_actions)

        # exploitation
        return argmax(q_values, available_actions)