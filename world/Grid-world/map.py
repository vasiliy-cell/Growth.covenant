import numpy as np

class Map:
    def __init__(self, size=8):
        self.size = size
        self.grid = self._generate()

    def _generate(self):
        return np.random.choice([0, 1, 2], size=(self.size, self.size))