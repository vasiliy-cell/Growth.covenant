from src.Brain.policy.policy import Policy


def test_epsilon_decay():

    policy = Policy(
        epsilon=1.0,
        epsilon_decay=0.5,
        epsilon_min=0.1
    )

    assert abs(policy.epsilon - 1.0) < 1e-6

    policy.next_episode()
    assert abs(policy.epsilon - 0.5) < 1e-6

    policy.next_episode()
    assert abs(policy.epsilon - 0.25) < 1e-6

    policy.next_episode()
    policy.next_episode()
    policy.next_episode()

    assert policy.epsilon >= 0.1