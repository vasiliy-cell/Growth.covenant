class QTableRewriter:
    def __init__(self, q_table, config):
        self.q_table = q_table

        self.alpha = config["learning_rate"]
        self.gamma = config["gamma"]

    def update(self, state, action, reward, next_state, done):
        """
        Q-learning update:
        Q(s,a) = Q(s,a) + α * (r + γ * max Q(s',a') - Q(s,a))
        """

        state_key = state
        next_state_key = next_state

        # current Q
        current_q = self.q_table.get_row(state_key)[action]

        # next max Q
        if done:
            max_next_q = 0
        else:
            max_next_q = max(self.q_table.get_row(next_state_key))

        # Q-learning formula
        new_q = current_q + self.alpha * (
            reward + self.gamma * max_next_q - current_q
        )

        # write back
        self.q_table.set(state_key, action, new_q)




