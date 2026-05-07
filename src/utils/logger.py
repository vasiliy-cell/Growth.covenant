import json
import os
from datetime import datetime, timezone


class Logger:
    def __init__(
        self,
        log_dir="logs",
        episode_name=None,
        max_logs=10000
    ):
        self.base_log_dir = log_dir
        self.max_logs = max_logs

        # подпапка по дате
        date_folder = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.log_dir = os.path.join(self.base_log_dir, date_folder)

        os.makedirs(self.log_dir, exist_ok=True)

        # cleanup старых логов
        self._cleanup_old_logs()

        if episode_name is None:
            episode_name = datetime.now(timezone.utc).strftime(
                "episode_%Y-%m-%d_%H-%M-%S_%f"
            )

        self.file_path = os.path.join(self.log_dir, f"{episode_name}.jsonl")

        self.file = open(self.file_path, "w", encoding="utf-8")

        self.total_reward = 0
        self.steps = 0

    def _cleanup_old_logs(self):
        all_logs = []

        # ищем все jsonl во всех подпапках
        for root, _, files in os.walk(self.base_log_dir):
            for file in files:
                if file.endswith(".jsonl"):
                    all_logs.append(os.path.join(root, file))

        # сортировка по времени изменения
        all_logs.sort(key=os.path.getmtime)

        # удаляем самые старые
        excess = len(all_logs) - self.max_logs + 1

        if excess > 0:
            for old_file in all_logs[:excess]:
                try:
                    os.remove(old_file)
                except Exception as e:
                    print(f"Failed to delete {old_file}: {e}")

    def _write(self, data):
        self.file.write(json.dumps(data) + "\n")

        # чтобы логи не терялись при краше
        self.file.flush()

    # --- лог seed ---
    def log_seed(self, seed, episode_seed):
        data = {
            "type": "seed_info",
            "global_seed": seed,
            "episode_seed": episode_seed
        }

        self._write(data)

    # --- лог шага ---
    def log_step(
        self,
        step,
        position,
        action,
        reward,
        shaped_reward=None,
        intrinsic_reward=None,
        available_actions=None
    ):
        """
        Logs a single step.

        reward: environment reward
        shaped_reward: total reward after shaping (optional)
        intrinsic_reward: curiosity reward (optional)
        """

        # choose what to accumulate as total reward
        used_reward = shaped_reward if shaped_reward is not None else reward

        self.total_reward += used_reward
        self.steps += 1

        data = {
            "type": "step",
            "step": step,
            "position": position,
            "action": action,
            "reward": reward,
            "available_actions": available_actions
        }

        # optional fields (only if provided)
        if shaped_reward is not None:
            data["shaped_reward"] = shaped_reward

        if intrinsic_reward is not None:
            data["intrinsic_reward"] = intrinsic_reward

        self._write(data)

    # --- конец эпизода ---
    def end_episode(self):
        summary = {
            "type": "episode_summary",
            "total_reward": self.total_reward,
            "steps": self.steps
        }

        self._write(summary)
        self.file.close()

    def __repr__(self):
        return f"Logger(file_path={self.file_path})"