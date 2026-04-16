import random

class FakeBrain:
    def choose_action(self, state, available_actions):

        if not available_actions:
            raise ValueError("No available actions")

        return random.choice(available_actions)