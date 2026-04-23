class Brain:
    def __init__(self, q_function):
        """
        Brain is just a coordinator.
        It does NOT contain learning logic.
        """
        self.q_function = q_function

    def choose_action(self, state, available_actions):
        """
        Select action using policy via QFunction
        """
        return self.q_function.select_action(state, available_actions)

    def learn(self, state, action, reward, next_state, done):
        """
        Pass experience to Q-learning system
        """
        self.q_function.update(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done
        )