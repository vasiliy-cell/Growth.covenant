import torch
from src.Brain.brain import Brain
from src.Brain.policy.policy import Policy


class FakeModel:
    def __init__(self):
        self.called = False
        self.last_state = None

    def __call__(self, state):
        self.called = True
        self.last_state = state
        # Policy.select_action делает q_values[available_actions] —
        # это тензорная индексация, обычный список тут не подходит.
        return torch.tensor([0.0, 1.0, 0.5])


class FakeTrainer:
    def __init__(self):
        self.policy_net = FakeModel()
        self.last_update = None

    def update(self, states, actions, rewards, next_states, dones):
        self.last_update = {
            "states": states,
            "actions": actions,
            "rewards": rewards,
            "next_states": next_states,
            "dones": dones
        }

def test_brain_calls_model():
    trainer = FakeTrainer()
    # epsilon=0.0 -> чистый exploitation, без рандома
    policy = Policy(epsilon=0.0)
    brain = Brain(trainer, policy)
    brain.choose_action("test", [0, 1, 2])
    assert trainer.policy_net.called is True


def test_brain_passes_state_to_model():
    trainer = FakeTrainer()
    policy = Policy(epsilon=0.0)
    brain = Brain(trainer, policy)
    state = "X"
    brain.choose_action(state, [0, 1, 2])
    assert trainer.policy_net.last_state == state


def test_brain_returns_best_action():
    trainer = FakeTrainer()
    policy = Policy(epsilon=0.0)
    brain = Brain(trainer, policy)
    # q_values = [0.0, 1.0, 0.5] -> argmax среди доступных [0,1,2] это индекс 1
    action = brain.choose_action("state", [0, 1, 2])
    assert action == 1


def test_brain_learn_calls_update():
    trainer = FakeTrainer()
    policy = Policy(epsilon=0.0)
    brain = Brain(trainer, policy)
    brain.learn(
        states=["s"],
        actions=[2],
        rewards=[5],
        next_states=["s2"],
        dones=[False]
    )
    assert trainer.last_update == {
        "states": ["s"],
        "actions": [2],
        "rewards": [5],
        "next_states": ["s2"],
        "dones": [False]
    }