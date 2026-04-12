import numpy as np
import random

from objects import OBJECTS


class Map:
    def __init__(self, size=8, empty_ratio=0.8):
        self.size = size
        self.empty_ratio = empty_ratio
        self.object_ids = list(OBJECTS.keys())

        self.grid = self._generate()

    def _generate(self):
        total_cells = self.size * self.size

        # --- 1. считаем пустые клетки ---
        empty_count = int(total_cells * self.empty_ratio)

        # --- 2. НЕ пустые объекты ---
        non_empty_ids = [obj for obj in self.object_ids if obj != 0]

        remaining = total_cells - empty_count

        # --- 3. создаём базовый список ---
        cells = [0] * empty_count

        # --- 4. распределяем остальные строго по количеству ---
        if non_empty_ids:
            per_object = remaining // len(non_empty_ids)
            remainder = remaining % len(non_empty_ids)

            for obj in non_empty_ids:
                count = per_object
                if remainder > 0:
                    count += 1
                    remainder -= 1

                cells.extend([obj] * count)

        # --- 5. ЖЁСТКИЙ ФИКС: обрезаем лишнее ---
        cells = cells[:total_cells]

        # --- 6. гарантия наличия каждого объекта ---
        for obj in non_empty_ids:
            if obj not in cells:
                idx = random.randint(0, total_cells - 1)
                cells[idx] = obj

        # --- 7. перемешиваем ---
        random.shuffle(cells)

        # --- 8. reshape ---
        grid = np.array(cells).reshape((self.size, self.size))

        return grid

    def get_cell(self, x, y):
        return self.grid[y, x]

    def print_map(self):
        for row in self.grid:
            print(" ".join(map(str, row)))


# if __name__ == "__main__":
#     m = Map(size=8)
#     m.print_map()

