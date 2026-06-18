import torch
import torch.nn as nn


class DQNLoss:

    def __init__(self):
        self.loss_fn = nn.MSELoss()

    def compute(
        self,
        current_q,
        target_q
    ):
        target_q = torch.tensor(
            target_q,
            dtype=torch.float32
        )

        return self.loss_fn(
            current_q,
            target_q
        )