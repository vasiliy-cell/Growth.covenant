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

        self.policy_net = model
        self.target_net = deepcopy(self.policy_net)
        self.target_net.eval()
        for param in self.target_net.parameters():
            param.requires_grad = False



        self.loss_fn = nn.MSELoss()

        self.optimizer = optim.Adam(
            self.policy_net.parameters(),
            lr=config.get("learning_rate", 0.001)

        )
        self._load_model()

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

        # Double DQN: policy_net ВЫБИРАЕТ лучшее действие, target_net ОЦЕНИВАЕТ его
        with torch.no_grad():
            next_action = self.policy_net(next_state).argmax()
            next_q_values = self.target_net(next_state)
            next_q = next_q_values[next_action]

        # target
        if done:
            target_q = torch.tensor(reward, dtype=torch.float32)
        else:
            target_q = reward + self.gamma * next_q

        current_q = current_q.squeeze()

        td_error = (target_q - current_q).item()

        loss = self.loss_fn(current_q, target_q)

        self.optimizer.zero_grad()
        loss.backward()

        # считаем норму градиента ДО optimizer.step(), max_norm=1e10 —
        # практически без ограничения, просто чтобы получить число.
        # Если позже решишь реально клиппить градиенты — поставь сюда
        # разумное значение (например 1.0 или 10.0) вместо 1e10.
        grad_norm = torch.nn.utils.clip_grad_norm_(
            self.policy_net.parameters(), max_norm=1e10
        ).item()

        self.optimizer.step()

        self.training_step += 1

        if self.training_step % self.target_update_freq == 0:
            self.update_target_network()

        return {
            "loss": loss.item(),
            "td_error": td_error,
            "grad_norm": grad_norm,
            "target_q": target_q.item(),
            "q_prediction": current_q.item(),
        }

    def update_target_network(self):
        self.target_net.load_state_dict(
            self.policy_net.state_dict()
        )