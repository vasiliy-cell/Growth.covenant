#!/usr/bin/env bash
# Bad-baseline run WITH the isolated-fitness probe, for ONE reproduction
# species. The main run is the g50h40 bad baseline (gamma 0.5 / scale 0.2,
# hidden 40, buffer 1000, all genes evolving except alpha/sigma/
# min_buffer_size); the probe is on, so --probe runs each snapshot adult
# alone in an empty world right after a seed finishes. The probe reward is
# the homeostasis-free skill signal to compare species on.
#
# Series is per-species (bad-probe-<species>), so clons / mendel /
# non_linear never collide, on the server or in the Desktop tree.
#
#   ./scripts/pipeline/run_bad_probe.sh clons           # 15 seeds, 3000 ep
#   ./scripts/pipeline/run_bad_probe.sh mendel 3000
#   ./scripts/pipeline/run_bad_probe.sh non_linear 300  # smoke
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/pipeline/seeds.sh"

SPECIES="${1:?need a species: clons | mendel | non_linear}"
EPISODES="${2:-3000}"
case "$SPECIES" in clons|mendel|non_linear) ;; *) echo "bad species: $SPECIES" >&2; exit 1 ;; esac

SERIES="bad-probe-${SPECIES}"
EVOLVE="genome.evolve=[hidden_layers,hidden_size,gamma,learning_rate,target_update_freq,max_norm,buffer_size,batch_size,epsilon,epsilon_decay,epsilon_min,curiosity_beta,curiosity_decay]"

NPROC="$(nproc 2>/dev/null || echo 8)"
PARALLEL="$NPROC"

CONSOLE_DIR="$REPO_ROOT/.ai/pipeline/${SERIES}/console"
DONE_FILE="$REPO_ROOT/.ai/pipeline/${SERIES}/done.txt"
STOP_FLAG="$REPO_ROOT/.ai/pipeline/STOP"
mkdir -p "$CONSOLE_DIR"

echo "=== $SERIES / species $SPECIES / episodes $EPISODES / seeds ${#SEEDS[@]} / parallel $PARALLEL (of $NPROC cores) + PROBE ==="

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
        --label "$label" --series "'"$SERIES"'" --resume "" --no-pin --probe \
        > "'"$CONSOLE_DIR"'/s${idx}_${seed}.log" 2>&1 < /dev/null
      status=$?
      echo "$(date "+%F %T") s${idx} seed $seed exit $status" >> "'"$DONE_FILE"'"
      if [[ "$status" -ne 0 ]]; then
        echo "!!! '"$SERIES"' seed $seed exited $status - see '"$CONSOLE_DIR"'/s${idx}_${seed}.log" >&2
      fi
      exit "$status"
    '

echo "=== $SERIES all seeds done (probe worlds inside each logs/<world>/probe/) ==="
