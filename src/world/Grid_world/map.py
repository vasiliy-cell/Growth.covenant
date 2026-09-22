import numpy as np
from src.world.Grid_world.objects import OBJECTS

class Map:
    """
    grid: an existing map to carry on with, instead of generating one.

    A restored map must not be generated first and overwritten after: a
    generation shuffles the whole world stream, and a run that resumes
    would carry on from a different place in it than the run that saved it.
    """

    def __init__(self, size=8, empty_ratio=0.8, rng=None, grid=None):
        self.size = size
        self.empty_ratio = empty_ratio
        self.object_ids = list(OBJECTS.keys())
        self.non_empty_ids = [obj for obj in self.object_ids if obj != 0]

        if rng is None:
            raise ValueError("Map requires rng for reproducibility")

        self.rng = rng
        self.grid = self._generate() if grid is None else np.array(grid)

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
    def count(self, obj):
        """How many cells hold this kind of object right now."""
        return int(np.count_nonzero(self.grid == obj))

    def refill(self, obj, amount, exclude=None):
        """
        Drop `amount` objects of kind `obj` into random EMPTY cells.
        The map is never regenerated, only topped up, so everything the
        agent already ate elsewhere stays eaten.

        exclude: iterable of (x, y) cells that must stay untouched (every
                 agent position: otherwise an object would pop up right
                 under somebody's feet).

        Returns how many cells were actually filled.
        """
        if amount <= 0 or not self.non_empty_ids:
            return 0

        empty_cells = np.argwhere(self.grid == 0)  # list of (y, x)

        if exclude:
            keep = np.ones(len(empty_cells), dtype=bool)

            for ex_x, ex_y in exclude:
                keep &= ~(
                    (empty_cells[:, 0] == ex_y) & (empty_cells[:, 1] == ex_x)
                )

            empty_cells = empty_cells[keep]

        if len(empty_cells) == 0:
            return 0

        count = min(amount, len(empty_cells))

        # sample without replacement -> never fill the same cell twice
        indexes = self.rng.sample(range(len(empty_cells)), count)

        for i in indexes:
            y, x = empty_cells[i]
            self.grid[y, x] = obj

        return count

    # -----------------------------
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        """Plain lists, so a checkpoint does not depend on a numpy version."""
        return self.grid.tolist()

    def print_map(self):
        for row in self.grid:
            print(" ".join(map(str, row)))
