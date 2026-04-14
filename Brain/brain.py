from Brain.FakeBrain import FakeBrain


class Brain:
    def __init__(self):
        # здесь потом можно легко заменить мозг
        self.impl = FakeBrain()

    def choose_action(self, observation):
        """
        observation: объект Observation
        """
        return self.impl.choose_action(observation)