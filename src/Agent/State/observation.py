class Observation:
    """
    What one agent sees at the end of a tick.

    Two views of the same window are kept because they answer different
    questions:

      local_view - what the network gets: the map with the other bodies
                   painted on top of it,
      map_view   - the same window with objects only, as if the population
                   did not exist.
    """

    def __init__(self, position, local_view, map_view):
        self.position = position
        self.local_view = local_view
        self.map_view = map_view

    def to_key(self):
        """
        The identity of a state for curiosity - built from map_view, never
        from local_view, and that is the whole point.

        Other agents move every single tick. A key that included them would
        come out different almost every time, the visit count would sit at 1
        forever, and the intrinsic reward would never decay - curiosity
        would quietly degenerate into a constant bonus that drowns the real
        reward. So for curiosity the agents do not exist: only the map does,
        and "have I been here before" means "have I seen this piece of the
        world before".
        """
        return (
            self.position,
            tuple(tuple(row) for row in self.map_view)
        )

    def __repr__(self):
        return (
            f"Observation("
            f"pos={self.position}, "
            f"local_shape={len(self.local_view)}x{len(self.local_view[0])}"
            f")"
        )
