
from Agent.Actions.movement.available_movements import MOVEMENTS


def apply_movement(position, movement_id):
    dx, dy = MOVEMENTS[movement_id]

    x, y = position

    new_x = x + dx
    new_y = y + dy

    return (new_x, new_y)