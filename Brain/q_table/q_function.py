
class QFunction:
    def __init__(self, q_table):
        # Reference to memory (Q-table)
        self.q_table = q_table

    # ACTION SELECTION 
    def select_action(self, state_index, available_actions):
        """
        Currently: greedy over Q-table OR fallback random
        (logic will live later in policy / rewriter)
        """

        q_values = self.q_table.get_row(state_index)

        # filter only allowed actions
        masked_values = [
            q_values[a] if a in available_actions else -float("inf")
            for a in range(len(q_values))
        ]

        best_action = max(range(len(masked_values)), key=lambda a: masked_values[a])

        # fallback if everything is invalid
        if best_action not in available_actions:
            return available_actions[0]

        return best_action

    # READ Q
    def get_q(self, state_index, action):
        return self.q_table.get(state_index, action)

    # WRITE Q 
    def set_q(self, state_index, action, value):
        self.q_table.set(state_index, action, value)

    # SAVE

    def save(self):
        self.q_table.save()

    def __repr__(self):
        return f"QFunction(q_table={self.q_table})"