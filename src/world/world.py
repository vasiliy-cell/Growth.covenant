from src.world.Grid_world.map import Map
from src.world.Grid_world.reward_for_objects import REWARDS


class World:
    def __init__(self, size=8, empty_ratio=0.8, refill=None):
        self.size = size
        self.empty_ratio = empty_ratio
        self.map = None

        # Refill rules (see world.refill in config.yml)
        refill = refill or {}
        self.refill_every = refill.get("every", 5)
        self.refill_threshold = refill.get("threshold", 0.2)
        self.refill_amount = refill.get("amount", 5)

    # --- generate world using provided RNG (ONCE per run) ---
    def generate(self, rng):
        # World is responsible for creating its map
        self.map = Map(size=self.size, empty_ratio=self.empty_ratio, rng=rng)

    def get_cell(self, position):
        x, y = position
        return self.map.get_cell(x, y)

    def get_reward(self, position):
        cell = self.get_cell(position)
        return REWARDS[cell]

    def clear_cell(self, position):
        x, y = position
        self.map.set_cell(x, y, 0)

    def non_empty_ratio(self):
        return self.map.non_empty_ratio()

    # --- keeping the world alive instead of regenerating it ---
    def maybe_refill(self, step, exclude=None):
        """
        Every refill_every steps: if colored cells dropped below
        refill_threshold, add refill_amount random objects.
        The map is NOT generated from scratch.

        Returns how many cells were added (0 if nothing happened).
        """
        if self.map is None:
            return 0

        if self.refill_every <= 0 or step % self.refill_every != 0:
            return 0

        if self.map.non_empty_ratio() >= self.refill_threshold:
            return 0

        return self.map.refill(self.refill_amount, exclude=exclude)

    def print(self):
        if self.map:
            self.map.print_map()
