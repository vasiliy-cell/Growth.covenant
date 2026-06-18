import torch
import torch.nn as nn


class MLP(nn.Module):

    def __init__(
        self,
        obs_size,
        hidden_size=64,
        action_size=8
    ):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(obs_size, hidden_size),
            nn.ReLU(),

            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),

            nn.Linear(hidden_size, action_size)
        )

    def forward(self, observation):
        return self.network(observation)