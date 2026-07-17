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
        self.max_norm = config["trainer"]["max_norm"]

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
    # DQN UPDATE (batched)
    # -------------------------
    def update(self, states, actions, rewards, next_states, dones):
        """
        states, next_states: tuple/list из B тензоров формы (obs_size,)
        actions: tuple/list из B int
        rewards: tuple/list из B float
        dones:   tuple/list из B bool
        """

        # Собираем batch в единые тензоры формы (B, obs_size) и (B,)
        states = torch.stack(states)                                    # (B, obs_size)
        next_states = torch.stack(next_states)                          # (B, obs_size)
        actions = torch.tensor(actions, dtype=torch.long)               # (B,)
        rewards = torch.tensor(rewards, dtype=torch.float32)            # (B,)
        dones = torch.tensor(dones, dtype=torch.float32)                # (B,)

        # Q(s, a) для всего батча разом
        q_values = self.policy_net(states)                              # (B, action_size)
        current_q = q_values.gather(1, actions.unsqueeze(1)).squeeze(1)  # (B,)

        # Double DQN: policy_net ВЫБИРАЕТ действие, target_net ОЦЕНИВАЕТ его
        with torch.no_grad():
            next_actions = self.policy_net(next_states).argmax(dim=1)                  # (B,)
            next_q_values = self.target_net(next_states)                               # (B, action_size)
            next_q = next_q_values.gather(1, next_actions.unsqueeze(1)).squeeze(1)      # (B,)

            # (1 - dones) обнуляет bootstrap-часть для терминальных состояний —
            # батчевый эквивалент прежнего if done: target_q = reward
            target_q = rewards + self.gamma * next_q * (1.0 - dones)

        loss = self.loss_fn(current_q, target_q)

        self.optimizer.zero_grad()
        loss.backward()

        grad_norm = torch.nn.utils.clip_grad_norm_(
            self.policy_net.parameters(), max_norm=self.max_norm
        ).item()

        self.optimizer.step()

        self.training_step += 1

        if self.training_step % self.target_update_freq == 0:
            self.update_target_network()

        # Для логгера отдаём средние по батчу значения — по одному числу
        # на train-update, а не по B чисел на каждый шаг.
        td_error_batch = (target_q - current_q).detach()

        return {
            "loss": loss.item(),
            "td_error": td_error_batch.mean().item(),
            "grad_norm": grad_norm,
            "target_q": target_q.mean().item(),
            "q_prediction": current_q.mean().item(),
        }

    def update_target_network(self):
        self.target_net.load_state_dict(
            self.policy_net.state_dict()
        )