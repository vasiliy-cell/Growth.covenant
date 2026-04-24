class Observation:
    def __init__(self, position, local_view):
        self.position = position
        self.local_view = local_view

    def to_key(self):
        return (
            self.position,
            tuple(tuple(row) for row in self.local_view)
        )

    def __repr__(self):
        return (
            f"Observation("
            f"pos={self.position}, "
            f"local_shape={len(self.local_view)}x{len(self.local_view[0])}"
            f")"
        )