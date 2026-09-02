import torch
from src.Brain.brain import Brain
from src.Brain.policy.policy import Policy
from src.Brain.replay_buffer import ReplayBuffer
from src.Brain.reward_shaping.reward_shaping import RewardShaping


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


def make_brain(trainer, min_buffer_size=1, batch_size=1):
    # epsilon=0.0 -> чистый exploitation, без рандома
    return Brain(
        trainer=trainer,
        policy=Policy(epsilon=0.0),
        replay_buffer=ReplayBuffer(capacity=10),
        reward_shaping=RewardShaping(),
        batch_size=batch_size,
        min_buffer_size=min_buffer_size,
    )


def test_brain_calls_model():
    trainer = FakeTrainer()
    brain = make_brain(trainer)
    brain.choose_action("test", [0, 1, 2])
    assert trainer.policy_net.called is True


def test_brain_passes_state_to_model():
    trainer = FakeTrainer()
    brain = make_brain(trainer)
    state = "X"
    brain.choose_action(state, [0, 1, 2])
    assert trainer.policy_net.last_state == state


def test_brain_returns_best_action():
    trainer = FakeTrainer()
    brain = make_brain(trainer)
    # q_values = [0.0, 1.0, 0.5] -> argmax среди доступных [0,1,2] это индекс 1
    action = brain.choose_action("state", [0, 1, 2])
    assert action == 1


def test_brain_learns_from_its_own_memories():
    trainer = FakeTrainer()
    brain = make_brain(trainer)

    brain.remember(state="s", action=2, reward=5, next_state="s2", done=False)
    brain.learn()

    assert trainer.last_update == {
        "states": ("s",),
        "actions": (2,),
        "rewards": (5,),
        "next_states": ("s2",),
        "dones": (False,)
    }


def test_brain_does_not_learn_before_the_buffer_is_warm():
    trainer = FakeTrainer()
    brain = make_brain(trainer, min_buffer_size=3)

    brain.remember(state="s", action=0, reward=0, next_state="s2", done=False)

    assert brain.learn() is None
    assert trainer.last_update is None


def test_brain_ages_with_every_remembered_step():
    brain = make_brain(FakeTrainer())

    for _ in range(4):
        brain.remember(state="s", action=0, reward=0, next_state="s", done=False)

    assert brain.age == 4
    assert brain.summary()["age"] == 4
