def argmax(q_values, available_actions):
    """
    Select action with highest Q-value among available actions

    q_values: array-like, Q-values for all actions
    available_actions: list of allowed actions

    returns: action (int)
    """

    if not available_actions:
        raise ValueError("No available actions")

    # Filter only available actions
    best_action = available_actions[0]
    best_value = q_values[best_action]

    for action in available_actions:
        if q_values[action] > best_value:
            best_value = q_values[action]
            best_action = action

    return best_action