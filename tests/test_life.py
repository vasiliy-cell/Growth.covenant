from src.Agent.life import Life
from src.environment.env import GridWorldEnv
from src.utils.rng import RunRandom


def make_life(**overrides):
    """Short, harsh rules - a whole life fits into a handful of ticks."""
    settings = dict(
        childhood_steps=3,
        base_leak=1.0,
        aging_every=2,
        aging_amount=0.5,
        death_energy=0.0,
    )
    settings.update(overrides)
    return Life(**settings)


def make_env(life, size=12, seed=0, agent_count=2):
    env = GridWorldEnv(
        size=size, rng=RunRandom(seed), agent_count=agent_count, life=life
    )
    env.start()
    return env


def stand_still(env):
    """One tick in which nobody moves: STAY is not an action, so send none."""
    return env.step({})


# -----------------------------
# PERIODS
# -----------------------------
def test_childhood_lasts_exactly_childhood_steps():
    life = make_life(childhood_steps=3)

    assert life.is_child(0)
    assert life.is_child(2)
    assert not life.is_child(3)


def test_a_child_survives_any_amount_of_hunger():
    life = make_life(childhood_steps=3)

    assert not life.is_dead(age=2, energy=-1000.0)


def test_an_adult_dies_at_the_threshold_and_not_above_it():
    life = make_life(childhood_steps=3, death_energy=0.0)

    assert life.is_dead(age=3, energy=0.0)
    assert life.is_dead(age=3, energy=-0.1)
    assert not life.is_dead(age=3, energy=0.1)


# -----------------------------
# AGING
# -----------------------------
def test_the_leak_grows_by_one_step_per_aging_period():
    life = make_life(base_leak=1.0, aging_every=2, aging_amount=0.5)

    assert life.leak(0) == 1.0
    assert life.leak(1) == 1.0
    assert life.leak(2) == 1.5
    assert life.leak(5) == 2.0


def test_aging_can_be_switched_off():
    life = make_life(aging_every=0)

    assert life.leak(1000) == life.base_leak


# -----------------------------
# BIRTH
# -----------------------------
def test_a_body_is_born_with_its_start_energy():
    env = make_env(make_life(start_energy=42.0))

    # read before the first tick: nothing has been spent or eaten yet
    assert all(agent.energy == 42.0 for agent in env.agents)


# -----------------------------
# IN THE WORLD
# -----------------------------
def test_an_agent_ages_one_tick_per_step():
    env = make_env(make_life(childhood_steps=1000))

    stand_still(env)
    stand_still(env)

    assert all(agent.age == 2 for agent in env.agents)


def test_nobody_dies_during_childhood():
    env = make_env(make_life(childhood_steps=1000, base_leak=1000.0))

    for _ in range(5):
        _, _, info = stand_still(env)

    assert info["died"] == []
    assert info["alive"] == 2


def test_a_death_carries_the_whole_life_out_with_it():
    """
    Nothing else in the logs can answer "what happened to this one"
    without a join across a million rows.
    """
    env = make_env(make_life(childhood_steps=1, base_leak=1000.0))

    stand_still(env)
    _, _, info = stand_still(env)

    death = info["deaths"][0]

    assert death["agent_id"] in info["died"]
    assert death["cause_of_death"] == "starvation"
    assert death["death_step"] == 2
    assert death["lifespan"] == 1
    assert death["num_offspring"] == 0
    assert death["parents"] == []
    assert "genotype" in death


def test_a_birth_names_its_parents_and_counts_them(tmp_path):
    """A lineage cannot be reconstructed from anything else afterwards."""
    env = make_env(make_life(childhood_steps=10 ** 9))

    for agent in env.agents:
        agent.energy = 10000.0

    _, _, info = stand_still(env)

    assert info["births"], "well fed agents must reproduce"

    birth = info["births"][0]
    parent_id = birth["parents"][0]

    assert env.agents.get(birth["agent_id"]).birth_step == 1
    assert env.agents.get(parent_id).offspring >= 1


def test_a_starving_adult_leaves_the_run():
    # a leak nothing on the map can pay for, so the outcome does not depend
    # on what the bodies happen to be standing on
    env = make_env(make_life(childhood_steps=1, base_leak=1000.0))

    # tick 1 makes them adults, tick 2 kills whoever did not find food
    stand_still(env)
    _, _, info = stand_still(env)

    assert info["died"], "a starving adult must not survive the tick"
    assert info["alive"] == len(env.agents)
    assert all(agent_id not in env.agents for agent_id in info["died"])


def test_the_dead_are_gone_from_observations_and_rewards():
    env = make_env(make_life(childhood_steps=0, base_leak=1000.0))

    observations, rewards, info = stand_still(env)

    assert info["died"], "adults born into this leak cannot survive a tick"

    # the tick a body dies it still earns what it stood on: the reward is
    # what killed it or failed to save it, so it is reported...
    assert set(rewards) >= set(info["died"])
    # ...but it has no next observation, it is not there to have one
    assert all(agent_id not in observations for agent_id in info["died"])


def test_a_well_fed_adult_keeps_living():
    env = make_env(make_life(childhood_steps=0))

    # fed, but well under energy.reproduction_threshold: this test is about
    # staying alive, not about filling the world with children
    for agent in env.agents:
        agent.energy = 100.0

    for _ in range(5):
        _, _, info = stand_still(env)

    assert info["died"] == []
    assert info["alive"] == 2
