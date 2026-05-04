import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from Brain.reward_shaping.intrinsic_rewards.curiosity.curiosity import Curiosity
def test_new_state_has_high_reward():
    config = {"beta": 1.0}
    c = Curiosity(config)

    state = "A"

    r1 = c.step(state)  # first visit
    r2 = c.step(state)  # second visit

    assert r1 > r2


def test_curiosity_decay_formula():
    config = {"beta": 1.0}
    c = Curiosity(config)

    state = "A"

    r1 = c.step(state)  # N=1 → 1.0
    r2 = c.step(state)  # N=2 → ~0.707

    assert abs(r1 - 1.0) < 1e-6
    assert abs(r2 - (1 / (2 ** 0.5))) < 1e-6



def test_reset_clears_counts():
    config = {"beta": 1.0}
    c = Curiosity(config)

    state = "A"

    c.step(state)
    c.reset()

    r = c.step(state)

    assert r == 1.0  # снова как первый раз


def test_beta_decay():
    config = {"beta": 1.0, "decay": 0.5}
    c = Curiosity(config)

    c.reset()  # episode 1 → beta = 0.5
    assert abs(c.beta - 0.5) < 1e-6

    c.reset()  # episode 2 → beta = 0.25
    assert abs(c.beta - 0.25) < 1e-6


def test_same_state_same_key():
    config = {"beta": 1.0}
    c = Curiosity(config)

    state = "A"

    c.step(state)
    c.step(state)

    assert c.visit_counts["A"] == 2