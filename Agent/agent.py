from Agent.State.position import Position
from Agent.State.observation import Observation

from Agent.Actions.movement.movements import apply_movement
from Agent.Actions.movement.available_movements import get_available_movements


class Agent:
    def __init__(self, world):
        self.position = Position()
        self.world = world

    # --- движение ---
    def move(self, action):
        new_pos = apply_movement(self.position.get(), action)
        self.position.update(new_pos)

    # --- получить позицию ---
    def get_position(self):
        return self.position.get()

    # --- получить observation (состояние для мозга) ---
    def get_state(self):
        pos = self.get_position()

        available = get_available_movements(pos, self.world.size)

        return Observation(pos, available)

    def __repr__(self):
        return f"Agent(position={self.position})"