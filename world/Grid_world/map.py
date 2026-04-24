# import numpy as np

# from world.Grid_world.objects import OBJECTS


# class Map:
#     def __init__(self, size=8, empty_ratio=0.8, rng=None):
#         self.size = size
#         self.empty_ratio = empty_ratio
#         self.object_ids = list(OBJECTS.keys())

#         if rng is None:
#             raise ValueError("Map requires rng for reproducibility")

#         self.rng = rng
#         self.grid = self._generate()

#     def _generate(self):
#         total_cells = self.size * self.size

#         empty_count = int(total_cells * self.empty_ratio)

#         non_empty_ids = [obj for obj in self.object_ids if obj != 0]

#         remaining = total_cells - empty_count

#         cells = [0] * empty_count

#         if non_empty_ids:
#             per_object = remaining // len(non_empty_ids)
#             remainder = remaining % len(non_empty_ids)

#             for obj in non_empty_ids:
#                 count = per_object
#                 if remainder > 0:
#                     count += 1
#                     remainder -= 1

#                 cells.extend([obj] * count)

#         cells = cells[:total_cells]

#         # Ensure every object appears at least once
#         for obj in non_empty_ids:
#             if obj not in cells:
#                 idx = self.rng.randint(0, total_cells - 1)
#                 cells[idx] = obj

#         # Shuffle cells using RNG
#         self.rng.shuffle(cells)

#         grid = np.array(cells).reshape((self.size, self.size))

#         return grid

#     def get_cell(self, x, y):
#         return self.grid[y, x]

#     def print_map(self):
#         for row in self.grid:
#             print(" ".join(map(str, row)))




# ===========================================================================================
#                       random one below
# ===========================================================================================




import numpy as np

from world.Grid_world.objects import OBJECTS


class Map:
    def __init__(self, size=8, empty_ratio=0.8, rng=None):
        self.size = size
        self.empty_ratio = empty_ratio
        self.object_ids = list(OBJECTS.keys())

        if rng is None:
            raise ValueError("Map requires rng for reproducibility")

        self.rng = rng
        self.grid = self._generate()

    def _generate(self):
        total_cells = self.size * self.size

        empty_count = int(total_cells * self.empty_ratio)

        non_empty_ids = [obj for obj in self.object_ids if obj != 0]

        remaining = total_cells - empty_count

        cells = [0] * empty_count

        if non_empty_ids:
            per_object = remaining // len(non_empty_ids)
            remainder = remaining % len(non_empty_ids)

            for obj in non_empty_ids:
                count = per_object
                if remainder > 0:
                    count += 1
                    remainder -= 1

                cells.extend([obj] * count)

        cells = cells[:total_cells]

        # Ensure every object appears at least once
        for obj in non_empty_ids:
            if obj not in cells:
                idx = self.rng.randint(0, total_cells - 1)
                cells[idx] = obj

        # Shuffle cells using RNG
        self.rng.shuffle(cells)

        grid = np.array(cells).reshape((self.size, self.size))

        return grid

    def get_cell(self, x, y):
        return self.grid[y, x]

    def print_map(self):
        for row in self.grid:
            print(" ".join(map(str, row)))