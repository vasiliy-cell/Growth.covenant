from src.Brain.reward_shaping.intrinsic_rewards.curiosity.curiosity import Curiosity


def test_new_state_has_high_reward():
    c = Curiosity(beta=1.0)

    r1 = c.step("A")
    r2 = c.step("A")

    assert r1 > r2


def test_curiosity_decay_formula():
    c = Curiosity(beta=1.0)

    r1 = c.step("A")
    r2 = c.step("A")

    assert abs(r1 - 1.0) < 1e-6
    assert abs(r2 - (1 / (2 ** 0.5))) < 1e-6


def test_counts_outlive_the_logging_window():
    """
    Cleared every window, novelty never ran out: twenty steps later every
    cell was new again and curiosity paid beta on every step for ever.
    """
    c = Curiosity(beta=1.0)

    c.step("A")
    c.next_episode()

    assert c.step("A") < 1.0
    assert c.visit_counts["A"] == 2


def test_beta_decay():
    c = Curiosity(beta=1.0, decay=0.5)

    c.next_episode()
    assert abs(c.beta - 0.5) < 1e-6

    c.next_episode()
    assert abs(c.beta - 0.25) < 1e-6


def test_same_state_same_key():
    c = Curiosity(beta=1.0)

    c.step("A")
    c.step("A")

    assert c.visit_counts["A"] == 2