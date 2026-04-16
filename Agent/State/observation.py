class Observation:
    def __init__(self, position, local_view):
        self.position = position
        self.local_view = local_view

    def __repr__(self):
        return f"Observation(position={self.position})"