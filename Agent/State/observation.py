class Observation:
    def __init__(self, position, local_view):
        self.position = position
        self.local_view = local_view

    def to_key(self):
        return (
            self.position,
            tuple(tuple(row) for row in self.local_view)
        )