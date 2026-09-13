import torch
import torch.nn as nn


class MLP(nn.Module):
 
    def __init__(
        self,
        obs_size,
        hidden_size=64,
        action_size=8,
        hidden_layers=2,
    ):
        super().__init__()

        # Build a variable-depth network: `hidden_layers` blocks of
        # (Linear -> ReLU), then one output Linear. hidden_layers is a gene,
        # so the architecture itself now differs from agent to agent.
        layers = []
        in_features = obs_size
        for _ in range(hidden_layers):
            layers.append(nn.Linear(in_features, hidden_size))
            layers.append(nn.ReLU())
            in_features = hidden_size
        layers.append(nn.Linear(in_features, action_size))

        self.network = nn.Sequential(*layers)

    def forward(self, observation):
        return self.network(observation)