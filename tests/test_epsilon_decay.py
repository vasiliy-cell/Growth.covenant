from src.Brain.policy.epsilon_greedy import EpsilonGreedy


def test_epsilon_decay():
    config = {
        "epsilon": 1.0,
        "epsilon_decay": 0.5,
        "epsilon_min": 0.1
    }

    policy = EpsilonGreedy(config)

    assert policy.epsilon == 1.0

    policy.next_episode()
    assert policy.epsilon == 0.5

    policy.next_episode()
    assert policy.epsilon == 0.25