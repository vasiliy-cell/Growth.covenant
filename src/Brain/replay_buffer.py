import random
from collections import deque


class ReplayBuffer:

    def __init__(self, capacity):
        # deque с maxlen сам вытесняет старые transitions, когда буфер
        # переполняется — ничего вручную чистить не нужно.
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        return states, actions, rewards, next_states, dones

    def __len__(self):
        return len(self.buffer)