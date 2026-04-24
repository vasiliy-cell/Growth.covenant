def argmax(q_values, available_actions):
    best_action = available_actions[0]
    best_value = q_values[best_action]

    for action in available_actions:
        if q_values[action] > best_value:
            best_value = q_values[action]
            best_action = action

    return best_action