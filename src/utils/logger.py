

import json
import os
from datetime import datetime


class Logger:
    def __init__(self, log_dir="logs", episode_name=None):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        if episode_name is None:
            episode_name = datetime.now().strftime("episode_%Y-%m-%d_%H-%M-%S_%f")
        self.file_path = os.path.join(self.log_dir, f"{episode_name}.jsonl")

        self.file = open(self.file_path, "w", encoding="utf-8")

        self.total_reward = 0
        self.steps = 0

    # --- лог seed ---
    def log_seed(self, seed, episode_seed):
        data = {
            "type": "seed_info",
            "global_seed": seed,
            "episode_seed": episode_seed
        }
        self.file.write(json.dumps(data) + "\n")

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

        self.file.write(json.dumps(data) + "\n")

    # --- конец эпизода ---
    def end_episode(self):
        summary = {
            "type": "episode_summary",
            "total_reward": self.total_reward,
            "steps": self.steps
        }

        self.file.write(json.dumps(summary) + "\n")
        self.file.close()

    def __repr__(self):
        return f"Logger(file_path={self.file_path})"