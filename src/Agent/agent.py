from src.Agent.State.position import Position
from src.Agent.State.observation import Observation

from src.Agent.Actions.movement.available_movements import get_available_movements
from src.Agent.Actions.movement.movements import MOVEMENTS


class Agent:
    def __init__(self, world):
        self.position = Position()
        self.world = world

    # -----------------------------
    # MOVE (SAFE + CONSISTENT)
    # -----------------------------
    def move(self, action):
        x, y = self.position.get()

        # если действие вообще не существует — игнор
        if action not in MOVEMENTS:
            return

        dx, dy = MOVEMENTS[action]
        nx, ny = x + dx, y + dy

        # hard bounds check (финальный барьер)
        if 0 <= nx < self.world.size and 0 <= ny < self.world.size:
            self.position.update((nx, ny))

    # -----------------------------
    # POSITION
    # -----------------------------
    def get_position(self):
        return self.position.get()

    # -----------------------------
    # AVAILABLE ACTIONS
    # -----------------------------
    def get_available_actions(self):
        return get_available_movements(
            self.get_position(),
            self.world.size
        )

    # -----------------------------
    # OBSERVATION (STATE)
    # -----------------------------
    def get_state(self):
        pos = self.get_position()

        local = self.get_local_view(
            self.world.map.grid,
            pos,
            size=7
        )
        return Observation(pos, local)

    # -----------------------------
    # LOCAL VIEW (VISION)
    # -----------------------------
    @staticmethod
    def get_local_view(grid, position, size=7):
        x, y = position
        half = size // 2

        view = []

        for dy in range(-half, half + 1):
            row = []
            for dx in range(-half, half + 1):
                nx, ny = x + dx, y + dy

                if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]):
                    row.append(grid[ny][nx])
                else:
                    row.append(-1)

            view.append(row)

        return view

    def __repr__(self):
        return f"Agent(position={self.position.get()})"