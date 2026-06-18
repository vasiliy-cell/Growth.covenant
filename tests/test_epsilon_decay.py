from src.Brain.policy.policy import Policy


def test_epsilon_decay():

    policy = Policy(
        epsilon=1.0,
        epsilon_decay=0.5,
        epsilon_min=0.1
    )

    assert policy.epsilon == 1.0

    policy.next_episode()
    assert policy.epsilon == 0.5

    policy.next_episode()
    assert policy.epsilon == 0.25

    policy.next_episode()
    policy.next_episode()
    policy.next_episode()

    assert policy.epsilon >= 0.1