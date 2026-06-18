import torch


class Policy:

    def __init__(
        self,
        epsilon=1.0,
        epsilon_decay=0.995,
        epsilon_min=0.01
    ):
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min

    def next_episode(self):

        self.epsilon *= self.epsilon_decay

        if self.epsilon < self.epsilon_min:
            self.epsilon = self.epsilon_min

    def select_action(
        self,
        q_values,
        available_actions
    ):

        if not available_actions:
            raise ValueError("No available actions")

        # exploration
        if torch.rand(1).item() < self.epsilon:

            random_index = torch.randint(
                len(available_actions),
                (1,)
            ).item()

            return available_actions[random_index]

        # exploitation
        available_q = q_values[available_actions]

        best_index = torch.argmax(
            available_q
        ).item()

        return available_actions[best_index]