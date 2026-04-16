from Brain.FakeBrain import FakeBrain


class Brain:
    def __init__(self):
        self.impl = FakeBrain()

    def choose_action(self, state, available_actions):
        return self.impl.choose_action(state, available_actions)