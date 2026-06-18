from src.Brain.brain import Brain


class FakeModel:
    def __init__(self):
        self.called = False
        self.last_state = None

    def __call__(self, state):
        self.called = True
        self.last_state = state
        return [0.0, 1.0, 0.5]


class FakeTrainer:
    def __init__(self):
        self.model = FakeModel()
        self.last_update = None

    def update(self, state, action, reward, next_state, done):
        self.last_update = {
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state,
            "done": done
        }


def test_brain_calls_model():
    trainer = FakeTrainer()
    brain = Brain(trainer, epsilon=0.0)  # 🔥 важно

    brain.choose_action("test", [0, 1, 2])

    assert trainer.model.called is True


def test_brain_passes_state_to_model():
    trainer = FakeTrainer()
    brain = Brain(trainer, epsilon=0.0)  # 🔥 важно

    state = "X"
    brain.choose_action(state, [0, 1, 2])

    assert trainer.model.last_state == state


def test_brain_returns_best_action():
    trainer = FakeTrainer()
    brain = Brain(trainer, epsilon=0.0)

    action = brain.choose_action("state", [0, 1, 2])

    assert action == 1


def test_brain_learn_calls_update():
    trainer = FakeTrainer()
    brain = Brain(trainer)

    brain.learn(
        state="s",
        action=2,
        reward=5,
        next_state="s2",
        done=False
    )

    assert trainer.last_update == {
        "state": "s",
        "action": 2,
        "reward": 5,
        "next_state": "s2",
        "done": False
    }