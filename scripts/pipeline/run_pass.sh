#!/usr/bin/env bash
# Runs one whole pass (good_baseline + the 6 groups, or pass 2 once its
# TODOs are filled in): every experiment of that pass, every fixed seed
# (or a handful, in --mode smoke), one species/--set per experiment.
#
# Experiments run ONE AFTER ANOTHER; within an experiment its seeds run in
# parallel (--parallel workers). That keeps "pack and deliver this
# experiment's logs" a clean step between two experiments, instead of a
# juggling act over several at once.
#
#   ./scripts/pipeline/run_pass.sh --pass 1 --mode smoke
#   ./scripts/pipeline/run_pass.sh --pass 1 --mode full --parallel 12
#
# --mode smoke:  --smoke-seeds seeds (default 1, always the FIRST ones of
#                the fixed 15 - never a random seed), --episodes 10. This
#                is a flags-and-wiring check, not a result worth reading.
# --mode full:   all 15 fixed seeds, --episodes 40000 (the run's own
#                default - override only if you mean it).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PASS=""
MODE=""
PARALLEL=""
EPISODES_OVERRIDE=""
SMOKE_SEEDS=1
DEST_ROOT="${DEST_ROOT:-$HOME/Desktop/Growth.covenant-results}"
DELETE_AFTER_ARCHIVE=0
STOP_FLAG="$REPO_ROOT/.ai/pipeline/STOP"
YES=0

usage() {
  echo "Usage: $0 --pass {1|2} --mode {smoke|full} [--parallel N]" >&2
  echo "          [--episodes N] [--smoke-seeds N] [--dest-root PATH]" >&2
  echo "          [--delete-after-archive] [--yes]" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pass) PASS="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --parallel) PARALLEL="$2"; shift 2 ;;
    --episodes) EPISODES_OVERRIDE="$2"; shift 2 ;;
    --smoke-seeds) SMOKE_SEEDS="$2"; shift 2 ;;
    --dest-root) DEST_ROOT="$2"; shift 2 ;;
    --delete-after-archive) DELETE_AFTER_ARCHIVE=1; shift ;;
    --yes) YES=1; shift ;;
    *) usage ;;
  esac
done

[[ "$PASS" == "1" || "$PASS" == "2" ]] || usage
[[ "$MODE" == "smoke" || "$MODE" == "full" ]] || usage

source "$REPO_ROOT/scripts/pipeline/seeds.sh"

if [[ "$PASS" == "1" ]]; then
  source "$REPO_ROOT/scripts/pipeline/experiments_pass1.sh"
  EXPERIMENTS=("${EXPERIMENTS_PASS1[@]}")
else
  source "$REPO_ROOT/scripts/pipeline/experiments_pass2.sh"
  EXPERIMENTS=("${EXPERIMENTS_PASS2[@]}")

  if [[ ${#EXPERIMENTS[@]} -eq 0 ]]; then
    echo "Pass 2 is still a skeleton: experiments_pass2.sh has no" >&2
    echo "uncommented experiments. Fill in WINNING_GENES and" >&2
    echo "bad_baseline.yml first (see the comments in that file)." >&2
    exit 1
  fi

  BAD_BASELINE="$REPO_ROOT/research/Which inheritance mechanisms of hyberparametres give rise to increasingly optimized agents?/bad_baseline.yml"
  if [[ ! -f "$BAD_BASELINE" ]]; then
    echo "Missing $BAD_BASELINE - pass 2 needs the owner's deliberately" >&2
    echo "worsened gene means written there first. Refusing to guess them." >&2
    exit 1
  fi

  echo "Pass 2 runs with config.yml REPLACED by bad_baseline.yml for its" >&2
  echo "whole duration (run.py has no --config flag; this is the" >&2
  echo "established way to switch the live config - see experiments_pass2.sh)." >&2
  if [[ "$YES" -ne 1 ]]; then
    read -r -p "Overwrite config.yml with bad_baseline.yml now? [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
  fi
  cp "$REPO_ROOT/config.yml" "$REPO_ROOT/.ai/pipeline/config.yml.before-pass2.bak"
  cp "$BAD_BASELINE" "$REPO_ROOT/config.yml"
  echo "config.yml replaced. Previous copy saved to .ai/pipeline/config.yml.before-pass2.bak"
fi

if [[ -z "$PARALLEL" ]]; then
  PARALLEL="$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)"
fi

if [[ "$MODE" == "smoke" ]]; then
  EPISODES="${EPISODES_OVERRIDE:-10}"
  RUN_SEEDS=("${SEEDS[@]:0:$SMOKE_SEEDS}")
else
  EPISODES="${EPISODES_OVERRIDE:-40000}"
  RUN_SEEDS=("${SEEDS[@]}")
fi

mkdir -p "$REPO_ROOT/.ai/pipeline"

echo "=== pass $PASS / mode $MODE / episodes $EPISODES / seeds ${#RUN_SEEDS[@]} / parallel $PARALLEL ==="

for spec in "${EXPERIMENTS[@]}"; do
  [[ -z "$spec" ]] && continue

  IFS='|' read -r NAME SPECIES EVOLVE <<< "$spec"
  SERIES="p${PASS}-${NAME}"

  if [[ -n "$EVOLVE" ]]; then
    EVOLVE_SET="genome.evolve=[${EVOLVE}]"
  else
    EVOLVE_SET="genome.evolve=[]"
  fi

  if [[ -f "$STOP_FLAG" ]]; then
    echo "STOP flag present ($STOP_FLAG) - not starting $NAME. Remove it to continue." >&2
    exit 1
  fi

  CONSOLE_DIR="$REPO_ROOT/.ai/pipeline/p${PASS}/${NAME}/console"
  DONE_FILE="$REPO_ROOT/.ai/pipeline/p${PASS}/${NAME}/done.txt"
  mkdir -p "$CONSOLE_DIR"

  echo "--- experiment: $NAME (species=$SPECIES, evolve=[$EVOLVE]) series=$SERIES ---"

  i=0
  for seed in "${RUN_SEEDS[@]}"; do i=$((i+1)); printf '%02d %s\n' "$i" "$seed"; done \
    | xargs -P "$PARALLEL" -n 2 bash -c '
        idx="$0"; seed="$1"
        label="'"$SERIES"'-s${idx}"
        OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python src/run.py \
          --episodes '"$EPISODES"' --seed "$seed" --agents 20 --species '"$SPECIES"' \
          --set "'"$EVOLVE_SET"'" \
          --label "$label" --series "'"$SERIES"'" --resume "" --no-pin \
          > "'"$CONSOLE_DIR"'/s${idx}_${seed}.log" 2>&1 < /dev/null
        echo "$(date "+%F %T") s${idx} seed $seed exit $?" >> "'"$DONE_FILE"'"
      '

  echo "--- $NAME done, delivering logs ---"
  "$REPO_ROOT/scripts/pipeline/deliver.sh" --pass "$PASS" --name "$NAME" --series "$SERIES" \
    --seeds "${#RUN_SEEDS[@]}" --dest-root "$DEST_ROOT" \
    $([[ "$DELETE_AFTER_ARCHIVE" -eq 1 ]] && echo --delete)
done

echo "=== pass $PASS / mode $MODE finished ==="
