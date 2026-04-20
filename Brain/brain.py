class Brain:
    def __init__(self, q_function):
        self.q_function = q_function

    def choose_action(self, state, available_actions):
        return self.q_function.select_action(state, available_actions)