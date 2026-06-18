import torch
import torch.nn as nn
import torch.optim as optim


class MLP(nn.Module):

    def __init__(
        self,
        obs_size,
        hidden_size=64,
        action_size=8,
        lr=0.001
    ):
        super().__init__()

        self.network = nn.Sequential(

            nn.Linear(
                obs_size,
                hidden_size
            ),

            nn.ReLU(),

            nn.Linear(
                hidden_size,
                hidden_size
            ),

            nn.ReLU(),

            nn.Linear(
                hidden_size,
                action_size
            )
        )

        self.loss_fn = nn.MSELoss()

        self.optimizer = optim.Adam(
            self.parameters(),
            lr=lr
        )

    def forward(
        self,
        observation
    ):
        return self.network(
            observation
        )

    def update(
        self,
        current_q,
        target_q
    ):

        target_q = torch.tensor(
            target_q,
            dtype=torch.float32
        )

        loss = self.loss_fn(
            current_q,
            target_q
        )

        self.optimizer.zero_grad()

        loss.backward()

        self.optimizer.step()

        return loss.item()