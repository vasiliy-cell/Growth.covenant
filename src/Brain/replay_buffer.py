import random


class ReplayBuffer:
    """
    One agent's memory, sampled with one agent's stream.

    rng: this agent's python stream (src/utils/rng.py). It used to be the
    global `random` module, which the run never seeded - so which
    transitions a mind learned from was the one thing in the project that
    a seed could not reproduce.

    The storage is a ring: a list that fills up to capacity and is then
    overwritten at `start`, the oldest slot. A deque with maxlen did this
    by itself, but READING the middle of a deque walks its links - O(n)
    per pick - and sample() picks from the middle on every update of every
    mind. The ring keeps the deque's order (oldest first, through `start`),
    and sample() draws INDICES with the same stream: random.sample spends
    the stream by length and count alone, so the picks are exactly the
    ones the deque would have given.
    """

    def __init__(self, capacity, rng=None):
        self.capacity = capacity
        self.buffer = []
        self.start = 0  # the oldest slot, once the ring is full
        self.rng = rng if rng is not None else random.Random()

    def push(self, state, action, reward, next_state, done):
        if len(self.buffer) < self.capacity:
            self.buffer.append((state, action, reward, next_state, done))
        else:
            self.buffer[self.start] = (state, action, reward, next_state, done)
            self.start = (self.start + 1) % self.capacity

    def sample(self, batch_size):
        size = len(self.buffer)
        picks = self.rng.sample(range(size), batch_size)

        batch = [self.buffer[(self.start + index) % size] for index in picks]
        states, actions, rewards, next_states, dones = zip(*batch)

        return states, actions, rewards, next_states, dones

    # -----------------------------
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        """
        Every transition this mind still remembers, oldest first.

        By far the heaviest thing in a checkpoint - thousands of tensors per
        agent - which is why the run only writes it on milestone
        checkpoints and leaves it out of the frequent ones.

        The sampling stream is NOT in here: it is a named stream of the run
        (src/utils/rng.py) and is saved once, with all the others.
        """
        return {
            "capacity": self.capacity,
            "transitions": self.buffer[self.start:] + self.buffer[:self.start],
        }

    def load_state(self, state):
        self.capacity = state["capacity"]
        self.buffer = list(state["transitions"])[-self.capacity:]
        self.start = 0

    def __len__(self):
        return len(self.buffer)
