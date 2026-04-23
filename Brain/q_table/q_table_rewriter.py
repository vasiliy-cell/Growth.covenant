# Brain/q_table/q_table_rewriter.py

class QTableRewriter:
    def __init__(self, q_table, config):
        self.q_table = q_table

        # hyperparameters
        self.alpha = config["learning_rate"]   # learning rate
        self.gamma = config["gamma"]           # discount factor

    def update(self, state, action, reward, next_state, done):
        """
        Q-learning update:
        Q(s,a) = Q(s,a) + α * (r + γ * max Q(s',a') - Q(s,a))
        """

        # --- current Q ---
        current_q = self.q_table.get(state, action)

        # --- max Q for next state ---
        if done:
            max_next_q = 0
        else:
            next_q_values = self.q_table.get_row(next_state)
            max_next_q = max(next_q_values)

        # --- Q-learning formula ---
        new_q = current_q + self.alpha * (
            reward + self.gamma * max_next_q - current_q
        )

        # --- write back ---
        self.q_table.set(state, action, new_q)
