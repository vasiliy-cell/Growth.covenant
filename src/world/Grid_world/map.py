import numpy as np
from world.Grid_world.objects import OBJECTS

class Map:
    def __init__(self, size=8, empty_ratio=0.8, rng=None):
        self.size = size
        self.empty_ratio = empty_ratio
        self.object_ids = list(OBJECTS.keys())
        self.non_empty_ids = [obj for obj in self.object_ids if obj != 0]

        if rng is None:
            raise ValueError("Map requires rng for reproducibility")

        self.rng = rng
        self.grid = self._generate()

    def _generate(self):
        total_cells = self.size * self.size

        empty_count = int(total_cells * self.empty_ratio)

        non_empty_ids = self.non_empty_ids

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

    def set_cell(self, x, y, value):
        self.grid[y, x] = value

    # -----------------------------
    # FILL STATE
    # -----------------------------
    def count_non_empty(self):
        return int(np.count_nonzero(self.grid))

    def non_empty_ratio(self):
        return self.count_non_empty() / float(self.size * self.size)

    # -----------------------------
    # REFILL
    # -----------------------------
    def refill(self, amount, exclude=None):
        """
        Drop `amount` random objects into random EMPTY cells.
        The map is never regenerated, only topped up, so everything the
        agent already ate elsewhere stays eaten.

        exclude: (x, y) cell that must stay untouched (the agent position:
                 otherwise an object would pop up right under its feet).

        Returns how many cells were actually filled.
        """
        if amount <= 0 or not self.non_empty_ids:
            return 0

        empty_cells = np.argwhere(self.grid == 0)  # list of (y, x)

        if exclude is not None:
            ex_x, ex_y = exclude
            empty_cells = empty_cells[
                ~((empty_cells[:, 0] == ex_y) & (empty_cells[:, 1] == ex_x))
            ]

        if len(empty_cells) == 0:
            return 0

        count = min(amount, len(empty_cells))

        # sample without replacement -> never fill the same cell twice
        indexes = self.rng.sample(range(len(empty_cells)), count)

        for i in indexes:
            y, x = empty_cells[i]
            self.grid[y, x] = self.rng.choice(self.non_empty_ids)

        return count

    def print_map(self):
        for row in self.grid:
            print(" ".join(map(str, row)))
