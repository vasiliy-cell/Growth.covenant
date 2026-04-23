from Brain.policy.policy import Policy
from Brain.q_table.q_table import QTable
from Brain.q_table.q_table_rewriter import QTableRewriter


class QFunction:
    def __init__(self, config):

        self.q_table = QTable(
            action_size=config.get("action_size", 8)
        )

        self.rewriter = QTableRewriter(
            self.q_table,
            config
        )

        self.policy = Policy(
            mode=config.get("policy", "argmax")
        )

    # -----------------------------
    # ACTION SELECTION
    # -----------------------------
    def select_action(self, state, available_actions):

        state_key = state.to_key()

        q_values = self.q_table.get_row(state_key)

        action = self.policy.select_action(
            q_values,
            available_actions
        )

        return action

    # -----------------------------
    # LEARNING
    # -----------------------------
    def update(self, state, action, reward, next_state, done):

        self.rewriter.update(
            state=state.to_key(),
            action=action,
            reward=reward,
            next_state=next_state.to_key(),
            done=done
        )

    # -----------------------------
    # SAVE
    # -----------------------------
    def save(self):
        self.q_table.save()

    def __repr__(self):
        return "QFunction(QTable + Policy + Rewriter)"