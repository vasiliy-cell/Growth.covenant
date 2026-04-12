from Agent.State.position import Position
from Agent.Actions.movement.movements import apply_movement


class Body:
    def __init__(self):
        self.position = Position()

    def move(self, action):
        new_pos = apply_movement(self.position.get(), action)
        self.position.update(new_pos)

    def get_position(self):
        return self.position.get()

    def __repr__(self):
        return str(self.position)