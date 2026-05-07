from src.world.Grid_world.map import Map
from src.world.Grid_world.reward_for_objects import REWARDS


class World:
    def __init__(self, size=8):
        self.size = size
        self.map = None

    # --- generate world using provided RNG ---
    def generate(self, rng):
        # World is responsible for creating its map
        self.map = Map(size=self.size, rng=rng)

    def get_cell(self, position):
        x, y = position
        return self.map.get_cell(x, y)

    def get_reward(self, position):
        cell = self.get_cell(position)
        return REWARDS[cell]

    def print(self):
        if self.map:
            self.map.print_map()