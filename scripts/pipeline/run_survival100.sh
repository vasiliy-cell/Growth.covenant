#!/usr/bin/env bash
# Cheap survival-only sweep: 100 new seeds, 500 episodes, NO probe (we only
# care whether the world died or not, and when - not how smart the minds
# got). Same bad genes as every other run in this research (g50h40), all
# three species in turn. Queued to run after whatever is already training
# on this box finishes.
#
#   ./scripts/pipeline/run_survival100.sh            # all 3 species, 500 ep
#   ./scripts/pipeline/run_survival100.sh 100 --parallel 8   # smoke
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/pipeline/seeds_survival100.sh"

EPISODES="${1:-500}"
PARALLEL_OVERRIDE=""
if [[ "${2:-}" == "--parallel" ]]; then PARALLEL_OVERRIDE="${3:-}"; fi

SEEDS=("${SURVIVAL_100_SEEDS[@]}")
EVOLVE="genome.evolve=[hidden_layers,hidden_size,gamma,learning_rate,target_update_freq,max_norm,buffer_size,batch_size,epsilon,epsilon_decay,epsilon_min,curiosity_beta,curiosity_decay]"

NPROC="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 8)"
PARALLEL="${PARALLEL_OVERRIDE:-$NPROC}"
if [[ "$PARALLEL" -gt "$NPROC" ]]; then PARALLEL="$NPROC"; fi

STOP_FLAG="$REPO_ROOT/.ai/pipeline/STOP"

echo "=== survival100 / episodes $EPISODES / seeds ${#SEEDS[@]} / parallel $PARALLEL (of $NPROC cores) / species: clons, mendel, non_linear in turn / NO PROBE ==="

for SPECIES in clons mendel non_linear; do
  SERIES="survival100-${SPECIES}"
  CONSOLE_DIR="$REPO_ROOT/.ai/pipeline/${SERIES}/console"
  DONE_FILE="$REPO_ROOT/.ai/pipeline/${SERIES}/done.txt"
  mkdir -p "$CONSOLE_DIR"

  echo "--- $SERIES: ${#SEEDS[@]} seeds, up to $PARALLEL at once ---"

  idx=0
  for seed in "${SEEDS[@]}"; do idx=$((idx + 1)); printf '%02d %s\n' "$idx" "$seed"; done \
    | xargs -P "$PARALLEL" -n 2 bash -c '
        idx="$0"; seed="$1"
        if [[ -f "'"$STOP_FLAG"'" ]]; then
          echo "STOP flag present - not starting seed $seed." >&2; exit 1
        fi
        label="'"$SERIES"'-s${idx}"
        echo "    ['"$SERIES"' $idx/'"${#SEEDS[@]}"'] seed $seed ..."
        OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python src/run.py \
          --episodes '"$EPISODES"' --seed "$seed" --agents 20 --species '"$SPECIES"' \
          --set "'"$EVOLVE"'" \
          --set "genome.genes.gamma.mean=0.5" --set "genome.genes.gamma.scale=0.2" \
          --set "genome.genes.hidden_size.mean=40" --set "genome.genes.buffer_size.mean=1000" \
          --set "checkpoints.keep=30" --set "checkpoints.every_steps=0" \
          --label "$label" --series "'"$SERIES"'" --resume "" --no-pin --no-probe \
          > "'"$CONSOLE_DIR"'/s${idx}_${seed}.log" 2>&1 < /dev/null
        status=$?
        echo "$(date "+%F %T") s${idx} seed $seed exit $status" >> "'"$DONE_FILE"'"
        if [[ "$status" -ne 0 ]]; then
          echo "!!! '"$SERIES"' seed $seed exited $status - see '"$CONSOLE_DIR"'/s${idx}_${seed}.log" >&2
        fi
        exit "$status"
      '
  echo "--- $SERIES done ---"
done

echo "=== survival100 all species done ==="
