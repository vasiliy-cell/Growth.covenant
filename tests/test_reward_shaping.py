from src.Brain.reward_shaping.reward_shaping import RewardShaping


def test_food_is_learned_louder_than_the_world_pays_it():
    shaping = RewardShaping(food_bonus=5)

    assert shaping.compute(None, 5) == (10, 5)


def test_danger_and_empty_cells_get_no_bonus():
    shaping = RewardShaping(food_bonus=5)

    assert shaping.compute(None, -5) == (-5, 0.0)
    assert shaping.compute(None, 0) == (0, 0.0)
