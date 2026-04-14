
class Observation:
    def __init__(self, position, available_actions):
        self.position = position
        self.available_actions = available_actions

    def to_dict(self):
        return {
            "position": self.position,
            "available_actions": self.available_actions
        }

    def __repr__(self):
        return (
            f"Observation(position={self.position}, "
            f"available_actions={self.available_actions})"
        )