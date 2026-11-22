#!/usr/bin/env bash
# Bad-baseline convergence run: start the g50h40 bad genes, let evolution
# work, watch the genes climb toward good over ~3500 episodes. 15 fixed
# seeds, non_linear, all genes evolving EXCEPT alpha / sigma / min_buffer_size.
#
# The bad baseline is pinned entirely by --set here (gamma 0.5 / scale 0.2,
# hidden_size 40, buffer_size 1000), so it does not depend on whatever the
# live config.yml happens to hold. Checkpoint-safety flags (keep=30,
# every_steps=0) are the fix for the concurrent-prune race from before.
#
#   ./scripts/pipeline/run_bad_g50h40.sh            # all 15 seeds, 3500 ep
#   ./scripts/pipeline/run_bad_g50h40.sh 100        # smoke: 100 ep
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/pipeline/seeds.sh"

EPISODES="${1:-3500}"
SERIES="bad-g50h40"
EVOLVE="genome.evolve=[hidden_layers,hidden_size,gamma,learning_rate,target_update_freq,max_norm,buffer_size,batch_size,epsilon,epsilon_decay,epsilon_min,curiosity_beta,curiosity_decay]"

NPROC="$(nproc 2>/dev/null || echo 8)"
PARALLEL="$NPROC"                 # 15 seeds <= cores here, so one parallel wave

CONSOLE_DIR="$REPO_ROOT/.ai/pipeline/${SERIES}/console"
DONE_FILE="$REPO_ROOT/.ai/pipeline/${SERIES}/done.txt"
STOP_FLAG="$REPO_ROOT/.ai/pipeline/STOP"
mkdir -p "$CONSOLE_DIR"

echo "=== $SERIES / episodes $EPISODES / seeds ${#SEEDS[@]} / parallel $PARALLEL (of $NPROC cores) / non_linear ==="

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
        --episodes '"$EPISODES"' --seed "$seed" --agents 20 --species non_linear \
        --set "'"$EVOLVE"'" \
        --set "genome.genes.gamma.mean=0.5" --set "genome.genes.gamma.scale=0.2" \
        --set "genome.genes.hidden_size.mean=40" --set "genome.genes.buffer_size.mean=1000" \
        --set "checkpoints.keep=30" --set "checkpoints.every_steps=0" \
        --label "$label" --series "'"$SERIES"'" --resume "" --no-pin \
        > "'"$CONSOLE_DIR"'/s${idx}_${seed}.log" 2>&1 < /dev/null
      status=$?
      echo "$(date "+%F %T") s${idx} seed $seed exit $status" >> "'"$DONE_FILE"'"
      if [[ "$status" -ne 0 ]]; then
        echo "!!! '"$SERIES"' seed $seed exited $status - see '"$CONSOLE_DIR"'/s${idx}_${seed}.log" >&2
      fi
      exit "$status"
    '

echo "=== $SERIES all seeds done ==="
