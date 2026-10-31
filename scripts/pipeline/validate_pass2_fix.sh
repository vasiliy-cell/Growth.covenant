#!/usr/bin/env bash
# One-off validation run for the batch_size/min_buffer_size replay-buffer
# fix (src/Genome/types/{mendelGenetics,reuse}.py) - NOT part of the real
# pass-2 experiment launcher (run_pass.sh). Deliberately a separate script
# so this short, throwaway check can never collide with, or be mistaken
# for, the real 40000-episode pass-2 good-baseline run:
#
#   - its own series name (p2check-<name>, not p2-good-<name>)
#   - its own local bookkeeping dir (.ai/pipeline/p2check/<name>/...)
#   - its own Desktop destination ("second research check/<name>", not
#     "second research/<name>")
#
# Reuses pass 2's good-baseline species/gene list (experiments_pass2.sh)
# and the fixed seed list (seeds.sh) so the only things that differ from
# a real run are the episode count and the seed count - just enough to
# see whether the fix holds and whether the reward curve looks sane,
# without paying for a full run first.
#
#   ./scripts/pipeline/validate_pass2_fix.sh
#   ./scripts/pipeline/validate_pass2_fix.sh --episodes 20000 --seeds 3
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

EPISODES=20000
NUM_SEEDS=3
PARALLEL=""
ONLY=""
STOP_FLAG="$REPO_ROOT/.ai/pipeline/STOP"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --episodes) EPISODES="$2"; shift 2 ;;
    --seeds) NUM_SEEDS="$2"; shift 2 ;;
    --parallel) PARALLEL="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

NPROC="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)"
if [[ -z "$PARALLEL" ]]; then
  PARALLEL="$NPROC"
elif [[ "$PARALLEL" -gt "$NPROC" ]]; then
  echo "--parallel $PARALLEL > $NPROC cores on this box - capping at $NPROC." >&2
  PARALLEL="$NPROC"
fi

source "$REPO_ROOT/scripts/pipeline/seeds.sh"
source "$REPO_ROOT/scripts/pipeline/experiments_pass2.sh"

RUN_SEEDS=("${SEEDS[@]:0:$NUM_SEEDS}")

echo "=== pass2 fix check / episodes $EPISODES / seeds ${#RUN_SEEDS[@]} / parallel $PARALLEL (of $NPROC cores) ==="

for spec in "${EXPERIMENTS_PASS2_GOOD[@]}"; do
  [[ -z "$spec" ]] && continue

  IFS='|' read -r NAME SPECIES EVOLVE _DEST_SUBDIR <<< "$spec"
  [[ -n "$ONLY" && "$NAME" != "$ONLY" ]] && continue

  SERIES="p2check-${NAME}"
  PIPELINE_SUBDIR="p2check/${NAME}"

  if [[ -n "$EVOLVE" ]]; then
    EVOLVE_SET="genome.evolve=[${EVOLVE}]"
  else
    EVOLVE_SET="genome.evolve=[]"
  fi

  CONSOLE_DIR="$REPO_ROOT/.ai/pipeline/${PIPELINE_SUBDIR}/console"
  DONE_FILE="$REPO_ROOT/.ai/pipeline/${PIPELINE_SUBDIR}/done.txt"
  mkdir -p "$CONSOLE_DIR"

  echo "--- check: $NAME (species=$SPECIES, evolve=[$EVOLVE]) series=$SERIES, ${#RUN_SEEDS[@]} seed(s), up to $PARALLEL at once ---"

  idx=0
  for seed in "${RUN_SEEDS[@]}"; do idx=$((idx + 1)); printf '%02d %s\n' "$idx" "$seed"; done \
    | xargs -P "$PARALLEL" -n 2 bash -c '
        idx="$0"; seed="$1"

        if [[ -f "'"$STOP_FLAG"'" ]]; then
          echo "STOP flag present ('"$STOP_FLAG"') - not starting '"$NAME"' seed $seed." >&2
          exit 1
        fi

        label="'"$SERIES"'-s${idx}"
        echo "    ['"$NAME"' $idx/'"${#RUN_SEEDS[@]}"'] seed $seed ..."

        OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python src/run.py \
          --episodes '"$EPISODES"' --seed "$seed" --agents 20 --species '"$SPECIES"' \
          --set "'"$EVOLVE_SET"'" --set "checkpoints.keep=30" --set "checkpoints.every_steps=0" \
          --label "$label" --series "'"$SERIES"'" --resume "" --no-pin \
          > "'"$CONSOLE_DIR"'/s${idx}_${seed}.log" 2>&1 < /dev/null
        status=$?

        echo "$(date "+%F %T") s${idx} seed $seed exit $status" >> "'"$DONE_FILE"'"

        if [[ "$status" -ne 0 ]]; then
          echo "!!! '"$NAME"' seed $seed exited $status - see '"$CONSOLE_DIR"'/s${idx}_${seed}.log" >&2
        fi
        exit "$status"
      '

  echo "--- $NAME check done ---"
done

echo "=== pass2 fix check finished ==="
