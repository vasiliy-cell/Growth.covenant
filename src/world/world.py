from src.world.Grid_world.map import Map
from src.world.Grid_world.reward_for_objects import REWARDS


class World:
    def __init__(self, size=8, empty_ratio=0.8, refill=None):
        self.size = size
        self.empty_ratio = empty_ratio
        self.map = None

        # Refill rules (see world.refill in config.yml). The threshold is
        # the share of the map EACH kind of object is kept at, not the
        # share of all of them together.
        refill = refill or {}
        self.refill_every = refill.get("every", 5)
        self.refill_threshold = refill.get("threshold", 0.15)

    # --- generate world using provided RNG (ONCE per run) ---
    def generate(self, rng):
        # World is responsible for creating its map
        self.map = Map(size=self.size, empty_ratio=self.empty_ratio, rng=rng)

    # --- or carry on with the map a checkpoint remembered ---
    def restore(self, state, rng):
        """
        Puts back the map exactly as it was, eaten cells and all.

        Nothing is generated here: a map that grew from a checkpoint must
        look like the one that was saved, not like a fresh one with the
        same seed - the run that saved it had been eating from it for
        hours.
        """
        self.size = state["size"]
        self.empty_ratio = state["empty_ratio"]

        self.map = Map(
            size=self.size,
            empty_ratio=self.empty_ratio,
            rng=rng,
            grid=state["grid"],
        )

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
        Every refill_every steps: every kind of object (food, danger) that
        dropped below refill_threshold of the map is topped back up to it.
        The map is NOT generated from scratch.

        Each kind is counted on its own. Counted together, the danger that
        agents learn to walk around kept the total up while the food was
        eaten, the refill never fired, and the map drifted towards one
        food per two dangers - until touching anything was a losing bet.

        exclude: iterable of (x, y) cells to leave alone - the positions of
                 every agent, so nothing spawns under a body.

        Returns how many cells were added (0 if nothing happened).
        """
        if self.map is None:
            return 0

        if self.refill_every <= 0 or step % self.refill_every != 0:
            return 0

        target = int(self.refill_threshold * self.size * self.size)
        added = 0

        for obj in self.map.non_empty_ids:
            missing = target - self.map.count(obj)

            if missing > 0:
                added += self.map.refill(obj, missing, exclude=exclude)

        return added

    # -----------------------------
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        return {
            "size": self.size,
            "empty_ratio": self.empty_ratio,
            "grid": self.map.state() if self.map is not None else None,
        }

    def print(self):
        if self.map:
            self.map.print_map()
