# Brain/q_table/q_function.py

from Brain.q_table.q_table import QTable
from Brain.q_table.q_table_rewriter import QTableRewriter


class QFunction:
    def __init__(self, config):
        self.q_table = QTable()
        self.rewriter = QTableRewriter(self.q_table, config)

    # --- get Q values for state ---
    def get_q_values(self, state):
        return self.q_table.get_row(state)

    # --- get Q value for specific (state, action) ---
    def get_q_value(self, state, action):
        return self.q_table.get(state, action)

    # --- update Q-table (delegates to rewriter) ---
    def update(self, state, action, reward, next_state, done):
        self.rewriter.update(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done
        )

    # --- save model ---
    def save(self):
        self.q_table.save()