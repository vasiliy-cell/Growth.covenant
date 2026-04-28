from src.Brain.brain import Brain


class FakeQ:
    """
    Фейковая Q-функция для тестирования Brain.
    Мы не хотим использовать реальную QTable,
    нам важно только отследить вызовы.
    """

    def __init__(self):
        self.called = False
        self.received_state = None
        self.received_actions = None

    def select_action(self, state, actions):
        self.called = True
        self.received_state = state
        self.received_actions = actions
        return 1  # фиксированный ответ для предсказуемости


class FakeQWithUpdate:
    """
    Отдельный фейк для проверки метода learn()
    """

    def __init__(self):
        self.last_update = None

    def update(self, **kwargs):
        self.last_update = kwargs


# -----------------------------
# TESTS
# -----------------------------


def test_brain_calls_q_function():
    fake_q = FakeQ()
    brain = Brain(fake_q)

    state = "test_state"
    actions = [0, 1, 2]

    brain.choose_action(state, actions)

    assert fake_q.called is True


def test_brain_passes_correct_data_to_q():
    fake_q = FakeQ()
    brain = Brain(fake_q)

    state = "test_state"
    actions = [0, 1, 2]

    brain.choose_action(state, actions)

    assert fake_q.received_state == state
    assert fake_q.received_actions == actions


def test_brain_returns_action_from_q():
    fake_q = FakeQ()
    brain = Brain(fake_q)

    action = brain.choose_action("state", [0, 1, 2])

    assert action == 1


def test_brain_learn_passes_experience_correctly():
    fake_q = FakeQWithUpdate()
    brain = Brain(fake_q)

    brain.learn(
        state="s",
        action=2,
        reward=5,
        next_state="s2",
        done=False
    )

    assert fake_q.last_update == {
        "state": "s",
        "action": 2,
        "reward": 5,
        "next_state": "s2",
        "done": False
    }