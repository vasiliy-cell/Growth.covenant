import torch


class Policy:
    """
    Epsilon-greedy, and the coin it tosses is its own.

    generator: this agent's torch stream (src/utils/rng.py). Without it the
    draws come from the global torch generator, which every agent in the
    world would be sharing - one more birth and everybody's exploration
    shifts. None keeps the global generator, for a test that does not care.
    """

    def __init__(
        self,
        epsilon=1.0,
        epsilon_decay=0.995,
        epsilon_min=0.01,
        generator=None
    ):
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.generator = generator

    def next_episode(self):

        self.epsilon *= self.epsilon_decay

        if self.epsilon < self.epsilon_min:
            self.epsilon = self.epsilon_min

    # -----------------------------
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        """
        Where this agent's exploration schedule has got to.

        The generator is NOT in here: it is a named stream of the run
        (src/utils/rng.py) and is saved once, with all the others.
        """
        return {
            "epsilon": self.epsilon,
            "epsilon_decay": self.epsilon_decay,
            "epsilon_min": self.epsilon_min,
        }

    def load_state(self, state):
        self.epsilon = state["epsilon"]
        self.epsilon_decay = state["epsilon_decay"]
        self.epsilon_min = state["epsilon_min"]

    def select_action(
        self,
        q_values,
        available_actions
    ):

        if not available_actions:
            raise ValueError("No available actions")

        # exploration
        if torch.rand(1, generator=self.generator).item() < self.epsilon:

            random_index = torch.randint(
                len(available_actions),
                (1,),
                generator=self.generator
            ).item()

            return available_actions[random_index]

        # exploitation
        available_q = q_values[available_actions]

        best_index = torch.argmax(
            available_q
        ).item()

        return available_actions[best_index]