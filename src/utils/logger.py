import json
import os
from datetime import datetime


class Logger:
    def __init__(self, log_dir="logs", episode_name=None):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        if episode_name is None:
            episode_name = datetime.now().strftime(
                "episode_%Y-%m-%d_%H-%M-%S_%f"
            )

        self.file_path = os.path.join(self.log_dir, f"{episode_name}.jsonl")
        self.file = open(self.file_path, "w", encoding="utf-8")

        # totals for episode
        self.env_reward = 0.0
        self.training_reward = 0.0
        self.intrinsic_reward = 0.0
        self.steps = 0

        # loss копится отдельно: не на каждом env-шаге обязательно есть
        # train-update (например, пока буфер не заполнен), поэтому считаем
        # среднее только по шагам, где loss реально был передан.
        self._loss_sum = 0.0
        self._loss_count = 0

    def log_seed(self, seed, episode_seed):
        self.file.write(json.dumps({
            "type": "seed_info",
            "global_seed": seed,
            "episode_seed": episode_seed
        }) + "\n")

    def log_step(
        self,
        step,
        position,
        action,
        reward,
        shaped_reward=None,
        intrinsic_reward=None,
        td_error=None,
        loss=None,
        available_actions=None
    ):
        used_reward = shaped_reward if shaped_reward is not None else reward

        # accumulate totals
        self.env_reward += reward
        self.training_reward += used_reward

        if intrinsic_reward is not None:
            self.intrinsic_reward += intrinsic_reward

        if loss is not None:
            self._loss_sum += loss
            self._loss_count += 1

        self.steps += 1

        data = {
            "type": "step",
            "step": step,
            "position": position,
            "action": action,
            "reward": reward,
            "available_actions": available_actions
        }

        if shaped_reward is not None:
            data["shaped_reward"] = shaped_reward
        if intrinsic_reward is not None:
            data["intrinsic_reward"] = intrinsic_reward
        if td_error is not None:
            data["td_error"] = td_error
            data["abs_td_error"] = abs(td_error)
        if loss is not None:
            data["loss"] = loss

        self.file.write(json.dumps(data) + "\n")

    def end_episode(self, beta=None, extra=None):
        """
        beta: текущее значение curiosity.beta на конец эпизода (опционально,
              нужно для диагностики затухания exploration bonus)
        extra: произвольный dict с доп. полями для summary — гиперпараметры
               рана, commit hash, имя эксперимента и т.п., без изменения
               сигнатуры метода каждый раз, когда что-то новое понадобится
        """
        summary = {
            "type": "episode_summary",
            "env_reward": self.env_reward,
            "training_reward": self.training_reward,
            "intrinsic_reward": self.intrinsic_reward,
            "steps": self.steps,
            "avg_loss": (
                self._loss_sum / self._loss_count
                if self._loss_count > 0 else None
            ),
        }

        if beta is not None:
            summary["curiosity_beta"] = beta

        if extra:
            summary.update(extra)

        self.file.write(json.dumps(summary) + "\n")
        self.file.close()