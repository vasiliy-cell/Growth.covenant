import numpy as np
import random

EMPTY = 0
FOOD = 1
DANGER = 2

class Map:
    def __init__(self, size=8):
        self.size = size
        self.grid = self._generate()

    def _generate(self):
        total_cells = self.size * self.size

        # считаем сколько каких клеток  
        empty_count = int(total_cells * 0.7)
        remaining = total_cells - empty_count

        # делим оставшиеся между объектами
        food_count = remaining // 2
        danger_count = remaining - food_count

        # создаём список всех клеток  
        cells = (
            [EMPTY] * empty_count +
            [FOOD] * food_count +
            [DANGER] * danger_count
        )

        # 3. гарантия наличия всех типов 
        # (на случай очень маленькой карты)
        if FOOD not in cells:
            cells[random.randint(0, total_cells - 1)] = FOOD

        if DANGER not in cells:
            cells[random.randint(0, total_cells - 1)] = DANGER

        #   4. перемешиваем  
        random.shuffle(cells)

        #   5. превращаем в grid  
        grid = np.array(cells).reshape((self.size, self.size))

        return grid

    def get_cell(self, x, y):
        return self.grid[y, x]

    def print_map(self):
        print(self.grid)


