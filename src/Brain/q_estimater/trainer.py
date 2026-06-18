import os
import torch
import torch.nn as nn
import torch.optim as optim


class DQNTrainer:

    def __init__(
        self,
        model,
        lr=0.001,
        gamma=0.99,
        save_path="models/mlp.pth"
    ):
        print("TRAINER-1")

        self.model = model
        self.gamma = gamma
        self.save_path = save_path

        print("TRAINER-2")

        self.loss_fn = nn.MSELoss()

        print("TRAINER-3")

        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=lr
        )

        print("TRAINER-4")

        self._load_model()

        print("TRAINER-5")

    # -------------------------
    # LOAD MODEL
    # -------------------------
    def _load_model(self):
        print("LOAD-1")

        if os.path.exists(self.save_path):
            print(f"[MLP] Loading model from {self.save_path}")

            state = torch.load(self.save_path, map_location="cpu")
            self.model.load_state_dict(state)

            print("LOAD-2 DONE")

        else:
            print("[MLP] No saved model found. Starting fresh.")

    # -------------------------
    # SAVE MODEL
    # -------------------------
    def save(self):
        print("[MLP] Saving model...")

        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

        torch.save(
            self.model.state_dict(),
            self.save_path
        )

        print("[MLP] Saved.")

    # -------------------------
    # DQN UPDATE
    # -------------------------
    def update(self, state, action, reward, next_state, done):

        # Q(s, a)
        q_values = self.model(state)
        current_q = q_values[action]

        # max Q(s')
        with torch.no_grad():
            next_q_values = self.model(next_state)
            next_q = torch.max(next_q_values)

        # target
        if done:
            target_q = torch.tensor(reward, dtype=torch.float32)
        else:
            target_q = reward + self.gamma * next_q

        current_q = current_q.squeeze()

        loss = self.loss_fn(current_q, target_q)

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        return loss.item()