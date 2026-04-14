from world.Grid_world.map import Map

class World:
    def __init__(self, size=8):
        self.size = size
        self.map = None

    def generate(self):
        self.map = Map(size=self.size)

    def get_cell(self, position):
        x, y = position
        return self.map.get_cell(x, y)

    def print(self):
        if self.map:
            self.map.print_map()
