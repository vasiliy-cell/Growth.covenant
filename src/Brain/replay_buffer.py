import random
from collections import deque


class ReplayBuffer:
    """
    One agent's memory, sampled with one agent's stream.

    rng: this agent's python stream (src/utils/rng.py). It used to be the
    global `random` module, which the run never seeded - so which
    transitions a mind learned from was the one thing in the project that
    a seed could not reproduce.
    """

    def __init__(self, capacity, rng=None):
        # deque с maxlen сам вытесняет старые transitions, когда буфер
        # переполняется — ничего вручную чистить не нужно.
        self.buffer = deque(maxlen=capacity)
        self.rng = rng if rng is not None else random.Random()

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size):
        batch = self.rng.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        return states, actions, rewards, next_states, dones

    # -----------------------------
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        """
        Every transition this mind still remembers.

        By far the heaviest thing in a checkpoint - thousands of tensors per
        agent - which is why the run only writes it on milestone
        checkpoints and leaves it out of the frequent ones.

        The sampling stream is NOT in here: it is a named stream of the run
        (src/utils/rng.py) and is saved once, with all the others.
        """
        return {
            "capacity": self.buffer.maxlen,
            "transitions": list(self.buffer),
        }

    def load_state(self, state):
        self.buffer = deque(state["transitions"], maxlen=state["capacity"])

    def __len__(self):
        return len(self.buffer)