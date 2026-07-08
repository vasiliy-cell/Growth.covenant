import os
import torch
import torch.nn as nn
import torch.optim as optim
from copy import deepcopy

class DQNTrainer:

    def __init__(
        self,
        model,
        config
    ):
        self.training_step = 0
        self.policy_net = model
        self.gamma = config["trainer"]["gamma"]
        self.target_update_freq = config["trainer"]["target_update_freq"]
        self.save_path = config["trainer"]["save_path"]


        print("TRAINER-1")

        self.policy_net = model
        self.target_net = deepcopy(self.policy_net)
        self.target_net.eval()
        for param in self.target_net.parameters():
            param.requires_grad = False


        print("TRAINER-2")

        self.loss_fn = nn.MSELoss()

        print("TRAINER-3")

        self.optimizer = optim.Adam(
            self.policy_net.parameters(),
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
            self.policy_net.load_state_dict(state)
            
            self.target_net.load_state_dict(
                self.policy_net.state_dict()
            )

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
            self.policy_net.state_dict(),
            self.save_path
        )

        print("[MLP] Saved.")

    # -------------------------
    # DQN UPDATE
    # -------------------------
    def update(self, state, action, reward, next_state, done):

        # Q(s, a)
        q_values = self.policy_net(state)
        current_q = q_values[action]

        # max Q(s')
        with torch.no_grad():
            next_q_values = self.target_net(next_state)
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

        self.training_step += 1

        if self.training_step % self.target_update_freq == 0:
            self.update_target_network()
        

        return loss.item()
    def update_target_network(self):
        self.target_net.load_state_dict(
            self.policy_net.state_dict()
    )
