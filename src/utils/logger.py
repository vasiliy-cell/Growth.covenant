import json
import os
from datetime import datetime


class Logger:
    """
    Run-scoped logger.

    The run is one continuous process, so there is ONE log file per run
    instead of one file per episode. An episode is just a logging window:
    every `episode_length` steps we flush an `episode_summary` line and start
    accumulating the next window in the same file.

    Line types:
      run_info        - once, at the start (global seed + run params)
      step            - one per step (`step` is the GLOBAL step index)
      episode_summary - one per logging window (same fields as before, so all
                        existing visualizers keep working unchanged)

    Full RNG states go to a separate file, logs/rng/<run_name>.jsonl, because
    they are big and would drown the main log. The `rng` subdirectory is
    ignored by log_selector, which only picks up *.jsonl files directly in
    logs/.
    """

    def __init__(self, log_dir="logs", run_name=None):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        if run_name is None:
            run_name = datetime.now().strftime(
                "run_%Y-%m-%d_%H-%M-%S_%f"
            )

        self.run_name = run_name
        self.file_path = os.path.join(self.log_dir, f"{run_name}.jsonl")
        self.file = open(self.file_path, "w", encoding="utf-8")

        self.rng_dir = os.path.join(self.log_dir, "rng")
        self.rng_path = os.path.join(self.rng_dir, f"{run_name}.jsonl")
        self.rng_file = None

        # index of the current logging window
        self.episode = 0
        self.total_steps = 0

        self._reset_window()

    # -----------------------------
    # WINDOW ACCUMULATORS
    # -----------------------------
    def _reset_window(self):
        self.episode_start_step = self.total_steps

        # totals for the current logging window
        self.env_reward = 0.0
        self.training_reward = 0.0
        self.intrinsic_reward = 0.0
        self.steps = 0

        # All metrics below accumulate the same way: not every step has a
        # train update (e.g. while the buffer is warming up), so the average
        # is computed only over the steps where a value was actually passed.
        self._loss_sum = 0.0
        self._loss_count = 0

        self._td_error_sum = 0.0
        self._td_error_count = 0

        self._grad_norm_sum = 0.0
        self._grad_norm_count = 0

        self._target_q_sum = 0.0
        self._target_q_count = 0

        self._q_prediction_sum = 0.0
        self._q_prediction_count = 0

    # -----------------------------
    # RUN HEADER
    # -----------------------------
    def log_run_start(self, seed, extra=None):
        """
        seed:  global seed of the whole run (there are no per-episode seeds
               anymore - reproducibility comes from the rng snapshots)
        extra: arbitrary dict with run params (total_steps, episode_length,
               world size, ...)
        """
        data = {
            "type": "run_info",
            "run_name": self.run_name,
            "global_seed": seed,
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }

        if extra:
            data.update(extra)

        self.file.write(json.dumps(data) + "\n")

    # -----------------------------
    # RNG SNAPSHOT
    # -----------------------------
    def log_rng(self, states, step=None):
        """
        states: dict of rng states (python random / numpy / torch / ...),
                already converted to JSON-serializable values.

        Written at the START of a logging window, so the snapshot is enough to
        replay the run from that point.
        """
        if self.rng_file is None:
            os.makedirs(self.rng_dir, exist_ok=True)
            self.rng_file = open(self.rng_path, "w", encoding="utf-8")

        record = {
            "type": "rng_state",
            "episode": self.episode,
            "step": self.total_steps if step is None else step,
            "rng": states,
        }

        self.rng_file.write(json.dumps(record) + "\n")

    # -----------------------------
    # STEP
    # -----------------------------
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
        grad_norm=None,
        target_q=None,
        q_prediction=None,
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

        if td_error is not None:
            self._td_error_sum += abs(td_error)
            self._td_error_count += 1

        if grad_norm is not None:
            self._grad_norm_sum += grad_norm
            self._grad_norm_count += 1

        if target_q is not None:
            self._target_q_sum += target_q
            self._target_q_count += 1

        if q_prediction is not None:
            self._q_prediction_sum += q_prediction
            self._q_prediction_count += 1

        self.steps += 1
        self.total_steps += 1

        data = {
            "type": "step",
            "step": step,
            "episode": self.episode,
            "position": position,
            "action": action,
            "reward": reward,
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
        if grad_norm is not None:
            data["grad_norm"] = grad_norm
        if target_q is not None:
            data["target_q"] = target_q
        if q_prediction is not None:
            data["q_prediction"] = q_prediction

        self.file.write(json.dumps(data) + "\n")

    # -----------------------------
    # WINDOW SUMMARY
    # -----------------------------
    def end_episode(self, beta=None, extra=None):
        """
        Closes the current logging window: writes the summary and starts a new
        window in the SAME file (nothing in the world is reset by this call).

        beta:  current curiosity.beta (optional, useful to diagnose how the
               exploration bonus fades)
        extra: arbitrary dict with extra summary fields - hyperparameters,
               commit hash, experiment name and so on, without changing the
               signature every time something new is needed
        """
        summary = {
            "type": "episode_summary",
            "episode": self.episode,
            "step_start": self.episode_start_step,
            "step_end": self.total_steps,
            "env_reward": self.env_reward,
            "episode_reward": self.training_reward,  # total shaped reward of the window
            "training_reward": self.training_reward,
            "intrinsic_reward": self.intrinsic_reward,
            "steps": self.steps,
            "avg_loss": (
                self._loss_sum / self._loss_count
                if self._loss_count > 0 else None
            ),
            "avg_td_error": (
                self._td_error_sum / self._td_error_count
                if self._td_error_count > 0 else None
            ),
            "avg_grad_norm": (
                self._grad_norm_sum / self._grad_norm_count
                if self._grad_norm_count > 0 else None
            ),
            "avg_target_q": (
                self._target_q_sum / self._target_q_count
                if self._target_q_count > 0 else None
            ),
            "avg_q_prediction": (
                self._q_prediction_sum / self._q_prediction_count
                if self._q_prediction_count > 0 else None
            ),
        }

        if beta is not None:
            summary["curiosity_beta"] = beta

        if extra:
            summary.update(extra)

        self.file.write(json.dumps(summary) + "\n")

        self.episode += 1
        self._reset_window()

    # -----------------------------
    # CLOSE (end of the run)
    # -----------------------------
    def close(self):
        if not self.file.closed:
            self.file.close()

        if self.rng_file is not None and not self.rng_file.closed:
            self.rng_file.close()
