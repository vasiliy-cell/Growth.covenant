import random

import pytest

from src.environment.env import GridWorldEnv
from src.world.Grid_world.objects import AGENT_CELL
from src.Agent.State.position import Position
from src.utils.rng import RunRandom

# Action ids, see src/Agent/Actions/movement/available_movements.py
UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3


def make_env(size=12, seed=0, agent_count=2):
    env = GridWorldEnv(size=size, rng=RunRandom(seed), agent_count=agent_count)
    env.start()
    return env


def place(env, *positions):
    """Puts the agents on exact cells and returns their ids, in spawn order."""
    ids = env.agents.ids()

    for agent_id, position in zip(ids, positions):
        env.agents.get(agent_id).move_to(position)

    return ids


# -----------------------------
# MOVEMENT CONFLICTS
# -----------------------------
def test_agent_cannot_step_onto_an_occupied_cell():
    env = make_env()
    mover, blocker = place(env, (0, 0), (1, 0))

    env.step({mover: RIGHT})

    assert env.agents.get(mover).get_position() == (0, 0)
    assert env.agents.get(blocker).get_position() == (1, 0)


def test_a_leaving_cell_is_still_blocked_this_tick():
    """
    The occupancy snapshot is taken before anybody moves, so a column of
    agents crawls forward one cell per tick instead of sliding as a whole.
    """
    env = make_env()
    follower, leader = place(env, (0, 0), (1, 0))

    env.step({follower: RIGHT, leader: RIGHT})

    assert env.agents.get(leader).get_position() == (2, 0)
    assert env.agents.get(follower).get_position() == (0, 0)


def test_only_one_agent_wins_a_contested_cell():
    env = make_env()
    left, right = place(env, (0, 0), (2, 0))

    env.step({left: RIGHT, right: LEFT})

    positions = [
        env.agents.get(left).get_position(),
        env.agents.get(right).get_position(),
    ]

    assert positions.count((1, 0)) == 1
    assert sorted(positions) in ([(0, 0), (1, 0)], [(1, 0), (2, 0)])


def test_contested_cell_winner_comes_from_the_run_rng():
    """Same seed, same winner - the draw is part of the reproducible run."""
    winners = []

    for _ in range(2):
        env = make_env(seed=7)
        left, right = place(env, (0, 0), (2, 0))
        env.step({left: RIGHT, right: LEFT})
        winners.append(env.agents.get(left).get_position() == (1, 0))

    assert winners[0] == winners[1]


def test_bodies_never_overlap_during_a_run():
    env = make_env(size=8, agent_count=12)
    rng = random.Random(3)

    for _ in range(200):
        actions = {
            agent_id: rng.choice(available)
            for agent_id, available in env.get_available_actions().items()
        }
        env.step(actions)

        positions = list(env.agents.positions().values())
        assert len(set(positions)) == len(positions)


def test_spawning_into_a_full_world_fails_loudly():
    with pytest.raises(RuntimeError):
        make_env(size=2, agent_count=5)


# -----------------------------
# VISION
# -----------------------------
def test_a_neighbour_shows_up_in_the_local_view():
    env = make_env()
    watcher, neighbour = place(env, (5, 5), (6, 5))

    observation = env.get_states()[watcher]

    # 7x7 window: the center is the agent itself, the neighbour sits one
    # cell to the right of it.
    assert observation.local_view[3][4] == AGENT_CELL
    assert observation.local_view[3][3] != AGENT_CELL


def test_the_window_is_as_wide_as_the_view_size():
    env = GridWorldEnv(size=12, rng=RunRandom(0), agent_count=2, view_size=9)
    env.start()
    watcher, neighbour = place(env, (5, 5), (6, 5))

    observation = env.get_states()[watcher]

    assert len(observation.local_view) == 9
    assert all(len(row) == 9 for row in observation.local_view)
    assert observation.local_view[4][5] == AGENT_CELL


def test_a_resume_sees_through_the_window_it_was_saved_with():
    """
    The networks of a world are sized to its window, so a checkpoint must
    bring the window back - and one written before the window was a
    setting was made with the old hardcoded 7x7.
    """
    saved = GridWorldEnv(size=12, rng=RunRandom(0), agent_count=1, view_size=9)
    saved.start()
    state = saved.state()

    resumed = GridWorldEnv(size=12, rng=RunRandom(0), agent_count=1, view_size=53)
    observation = next(iter(resumed.restore(state).values()))
    assert len(observation.local_view) == 9

    del state["view_size"]
    legacy = GridWorldEnv(size=12, rng=RunRandom(0), agent_count=1, view_size=53)
    observation = next(iter(legacy.restore(state).values()))
    assert len(observation.local_view) == 7


def test_the_map_view_never_shows_bodies():
    env = make_env()
    watcher, neighbour = place(env, (5, 5), (6, 5))

    observation = env.get_states()[watcher]

    assert AGENT_CELL not in [cell for row in observation.map_view for cell in row]


# -----------------------------
# CURIOSITY KEY
# -----------------------------
def test_curiosity_key_ignores_other_agents():
    """
    A state must stay the same state when a neighbour walks past, otherwise
    the visit count never rises and the intrinsic reward never decays.
    """
    env = make_env()
    watcher, neighbour = place(env, (5, 5), (6, 5))

    with_neighbour = env.get_states()[watcher]

    env.agents.get(neighbour).move_to((9, 9))
    without_neighbour = env.get_states()[watcher]

    assert with_neighbour.to_key() == without_neighbour.to_key()
    assert with_neighbour.local_view != without_neighbour.local_view


# -----------------------------
# SEED COMPATIBILITY
# -----------------------------
def test_a_spawn_is_drawn_from_the_population_stream_alone():
    """
    Where a body appears depends on the seed and on nothing else. The map
    is generated from its own stream, so however many cells it shuffled
    first, the spawn lands where the population stream says it does.
    """
    seed, size = 12345, 16

    expected = Position.random(size, RunRandom(seed).python("population")).get()

    env = GridWorldEnv(size=size, rng=RunRandom(seed), agent_count=1)
    env.start()

    assert env.agents.all()[0].get_position() == expected


# -----------------------------
# NETWORK INPUT
# -----------------------------
def test_the_network_sees_the_window_one_hot_and_not_the_position():
    from src.run import CELL_CHANNELS, encode_observation
    from src.world.Grid_world.objects import AGENT_CELL

    env = make_env()
    watcher, neighbour = place(env, (5, 5), (6, 5))
    env.world.map.grid[5][4] = 1                      # food left of the watcher

    observation = env.get_states()[watcher]
    encoded = encode_observation(observation).reshape(len(CELL_CHANNELS), 7, 7)

    assert encoded.shape[0] * 49 == len(encode_observation(observation))
    assert encoded[CELL_CHANNELS.index(1), 3, 2] == 1
    assert encoded[CELL_CHANNELS.index(AGENT_CELL), 3, 4] == 1
    assert encoded[:, 3, 4].sum() == 1                # one kind per cell
