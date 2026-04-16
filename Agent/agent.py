from Agent.State.position import Position
from Agent.State.observation import Observation

from Agent.Actions.movement.movements import apply_movement
from Agent.Actions.movement.available_movements import get_available_movements


class Agent:
    def __init__(self, world):
        self.position = Position()
        self.world = world

    # --- move agent ---
    def move(self, action):
        new_pos = apply_movement(self.position.get(), action)
        self.position.update(new_pos)

    # --- get current position ---
    def get_position(self):
        return self.position.get()

    # --- get available actions (IMPORTANT: separate from observation) ---
    def get_available_actions(self):
        pos = self.get_position()
        return get_available_movements(pos, self.world.size)

    # --- build observation (what agent sees) ---
    def get_state(self):
        pos = self.get_position()

        local = self.get_local_view(
            self.world.map.grid,
            pos,
            size=7
        )

        return Observation(pos, local)

    def __repr__(self):
        return f"Agent(position={self.position})"

    # --- local perception window ---
    @staticmethod
    def get_local_view(grid, position, size=7):
        x, y = position
        half = size // 2

        view = []

        for dy in range(-half, half + 1):
            row = []
            for dx in range(-half, half + 1):
                nx, ny = x + dx, y + dy

                if 0 <= nx < len(grid[0]) and 0 <= ny < len(grid):
                    row.append(grid[ny][nx])
                else:
                    row.append(-1)  # outside world

            view.append(row)

        return view