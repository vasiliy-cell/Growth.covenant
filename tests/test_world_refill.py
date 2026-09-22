import random

import numpy as np

from src.world.world import World

FOOD, DANGER = 1, 2


def make_world(size=20):
    world = World(size=size, empty_ratio=0.7, refill={"every": 5, "threshold": 0.15})
    world.generate(rng=random.Random(0))
    return world


def test_food_and_danger_each_start_at_their_share():
    world = make_world()
    target = int(0.15 * 20 * 20)

    assert world.map.count(FOOD) == target
    assert world.map.count(DANGER) == target


def test_eaten_food_comes_back_without_danger_taking_its_place():
    world = make_world()
    target = int(0.15 * 20 * 20)

    world.map.grid[world.map.grid == FOOD] = 0

    world.maybe_refill(step=5)

    assert world.map.count(FOOD) == target
    assert world.map.count(DANGER) == target


def test_nothing_is_refilled_between_checks_or_under_a_body():
    world = make_world()
    world.map.grid[world.map.grid == FOOD] = 0

    assert world.maybe_refill(step=4) == 0

    body = tuple(int(v) for v in np.argwhere(world.map.grid == 0)[0][::-1])
    world.maybe_refill(step=5, exclude={body})

    assert world.get_cell(body) == 0
