import torch


class ObservationEncoder:

    def __init__(self, grid_size=8):
        self.grid_size = grid_size

    def encode(self, obs):
        x, y = obs.position
        flat_view = [cell for row in obs.local_view for cell in row]

        vector = [x, y] + flat_view

        return torch.tensor(vector, dtype=torch.float32)