"""
Прогоняет несколько независимых тренировок подряд без ручного ввода.

Каждый ран:
  1. получает новый global seed (время в микросекундах),
  2. обучается episodes эпизодов через src.run.main(),
  3. читает logs/*.jsonl, усредняет env_reward по последним --tail эпизодам
     рана (curiosity beta затухает по ходу рана, поэтому среднее по ВСЕМ
     эпизодам смешивает "разогрев" с выученной политикой -- усреднение по
     хвосту даёт честную оценку того, чему агент реально научился),
  4. сравнивает среднее с порогом -> вердикт GOOD/BAD,
  5. дописывает запись рана (seed, среднее по хвосту, среднее по всему рану,
     вердикт) в results/runs_summary.jsonl (этот файл НЕ удаляется между
     ранами),
  6. удаляет logs/ и models/mlp.pth и переходит к следующему рану.

Запуск из корня репозитория:
    PYTHONPATH=. python scripts/auto_train.py --runs 5 --episodes 40000
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
MODEL_PATH = os.path.join(REPO_ROOT, "models", "mlp.pth")
TEMP_DATA_DIR = os.path.join(REPO_ROOT, "temp_data")
RESULTS_DIR = os.path.join(TEMP_DATA_DIR, "results")
RESULTS_PATH = os.path.join(RESULTS_DIR, "runs_summary.jsonl")
CONSOLE_LOG_PATH = os.path.join(RESULTS_DIR, "auto_train_console.log")


class Tee:
    """Duplicates writes to the original stream and a log file in temp_data/results."""

    def __init__(self, stream, file):
        self.stream = stream
        self.file = file

    def write(self, data):
        self.stream.write(data)
        self.file.write(data)

    def flush(self):
        self.stream.flush()
        self.file.flush()


def make_seed():
    return int(time.time() * 1e6)


def clean_run_artifacts():
    if os.path.isdir(LOGS_DIR):
        shutil.rmtree(LOGS_DIR)
    os.makedirs(LOGS_DIR, exist_ok=True)
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)


def collect_episode_rewards(metric):
    """
    Каждый episode-файл: первая строка seed_info даёт episode_seed (порядковый
    номер эпизода в ране), где-то дальше -- episode_summary с самой наградой.
    Возвращает список (episode_index, reward), отсортированный по индексу.
    """
    episodes = []
    for fname in os.listdir(LOGS_DIR):
        if not fname.endswith(".jsonl"):
            continue
        episode_index = None
        reward = None
        with open(os.path.join(LOGS_DIR, fname), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("type") == "seed_info":
                    episode_index = obj.get("episode_seed")
                elif obj.get("type") == "episode_summary" and obj.get(metric) is not None:
                    reward = obj[metric]
        if episode_index is not None and reward is not None:
            episodes.append((episode_index, reward))
    episodes.sort(key=lambda pair: pair[0])
    return episodes


def average(values):
    if not values:
        return None
    return sum(values) / len(values)


def run_once(run_index, episodes, metric, threshold, tail):
    from src.run import main as run_training

    seed = make_seed()
    print(f"\n=== RUN {run_index}: episodes={episodes} seed={seed} ===", flush=True)

    run_training(episodes=episodes, seed=seed)

    episode_rewards = collect_episode_rewards(metric)
    all_rewards = [r for _, r in episode_rewards]
    tail_rewards = [r for _, r in episode_rewards[-tail:]]

    avg_tail = average(tail_rewards)
    avg_all = average(all_rewards)
    verdict = "GOOD" if avg_tail is not None and avg_tail >= threshold else "BAD"

    record = {
        "run": run_index,
        "seed": seed,
        "episodes_requested": episodes,
        "episodes_logged": len(episode_rewards),
        "metric": metric,
        "tail": tail,
        "avg_reward_tail": avg_tail,
        "avg_reward_all": avg_all,
        "threshold": threshold,
        "verdict": verdict,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(
        f"=== RUN {run_index} RESULT: avg_{metric} tail(last {tail})="
        f"{avg_tail if avg_tail is None else round(avg_tail, 3)}, "
        f"all(n={len(episode_rewards)})={avg_all if avg_all is None else round(avg_all, 3)} "
        f"-> {verdict} ===",
        flush=True,
    )

    clean_run_artifacts()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--episodes", type=int, default=40000)
    parser.add_argument("--metric", default="env_reward", choices=["env_reward", "training_reward"])
    parser.add_argument("--threshold", type=float, default=45.0)
    parser.add_argument("--tail", type=int, default=2000, help="average over last N episodes of each run")
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    # src/ modules mix `from src.x import y` and `from x import y` styles,
    # which only resolve together when both the repo root and src/ are on
    # sys.path (normally satisfied by running `python src/run.py` directly).
    sys.path.insert(0, REPO_ROOT)
    sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    console_log = open(CONSOLE_LOG_PATH, "a", encoding="utf-8")
    sys.stdout = Tee(sys.stdout, console_log)

    clean_run_artifacts()

    results = []
    for i in range(1, args.runs + 1):
        results.append(run_once(i, args.episodes, args.metric, args.threshold, args.tail))

    print("\n=== FINAL SUMMARY ===")
    for r in results:
        avg_str = "n/a" if r["avg_reward_tail"] is None else f"{r['avg_reward_tail']:.3f}"
        print(f"run {r['run']}: seed={r['seed']} avg_{r['metric']}_tail{r['tail']}={avg_str} -> {r['verdict']}")
    good = sum(1 for r in results if r["verdict"] == "GOOD")
    print(f"\n{good}/{len(results)} runs GOOD (threshold={args.threshold})")
    print(f"Full history: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
