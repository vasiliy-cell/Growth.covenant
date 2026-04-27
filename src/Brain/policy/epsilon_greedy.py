import random
from Brain.policy.argmax import argmax


def epsilon_greedy(q_values, available_actions, epsilon):
    """
    With probability epsilon -> random action
    Otherwise -> best action (argmax)
    """

    if not available_actions:
        raise ValueError("No available actions")

    # --- exploration ---
    if random.random() < epsilon:
        return random.choice(available_actions)

    # --- exploitation ---
    return argmax(q_values, available_actions)