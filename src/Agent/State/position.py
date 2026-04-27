class Position:
    def __init__(self, x=1, y=1):
        self.x = x
        self.y = y

    def get(self):
        return (self.x, self.y)

    def set(self, x, y):
        self.x = x
        self.y = y

    def update(self, new_position):
        self.x, self.y = new_position

    def __repr__(self):
        return f"Position(x={self.x}, y={self.y})"