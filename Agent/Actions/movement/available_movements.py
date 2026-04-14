MOVEMENTS = {
    0: (0, -1),   # up
    1: (0, 1),    # down
    2: (-1, 0),   # left
    3: (1, 0),    # right
    4: (-1, -1),  # up-left
    5: (1, -1),   # up-right
    6: (-1, 1),   # down-left
    7: (1, 1),    # down-right
}


def get_available_movements(position, world_size):
    x, y = position

    available = []
    
    for move_id, (dx, dy) in MOVEMENTS.items():
        new_x = x + dx
        new_y = y + dy

        # проверка границ
        if 0 <= new_x < world_size and 0 <= new_y < world_size:
            available.append(move_id)

    return available