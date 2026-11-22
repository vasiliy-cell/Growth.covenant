#!/usr/bin/env bash
# Generic round runner for the overnight loop: reads seeds from a file (one
# per line), runs the given species list, episodes, probe on/off.
#
#   run_generic_round.sh <seed_file> <series_prefix> <episodes> <probe|noprobe> <species1> [species2 ...]
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SEED_FILE="$1"; SERIES_PREFIX="$2"; EPISODES="$3"; PROBE_MODE="$4"; shift 4
SPECIES_LIST=("$@")

mapfile -t SEEDS < "$SEED_FILE"
EVOLVE="genome.evolve=[hidden_layers,hidden_size,gamma,learning_rate,target_update_freq,max_norm,buffer_size,batch_size,epsilon,epsilon_decay,epsilon_min,curiosity_beta,curiosity_decay]"
NPROC="$(nproc 2>/dev/null || echo 8)"
PROBE_FLAG="--no-probe"
[ "$PROBE_MODE" = "probe" ] && PROBE_FLAG="--probe"

for SPECIES in "${SPECIES_LIST[@]}"; do
  SERIES="${SERIES_PREFIX}-${SPECIES}"
  CONSOLE_DIR=".ai/pipeline/${SERIES}/console"
  DONE_FILE=".ai/pipeline/${SERIES}/done.txt"
  mkdir -p "$CONSOLE_DIR"

  idx=0
  for seed in "${SEEDS[@]}"; do idx=$((idx + 1)); printf '%02d %s\n' "$idx" "$seed"; done \
    | xargs -P "$NPROC" -n 2 bash -c '
        idx="$0"; seed="$1"
        label="'"$SERIES"'-s${idx}"
        OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python src/run.py \
          --episodes '"$EPISODES"' --seed "$seed" --agents 20 --species '"$SPECIES"' \
          --set "'"$EVOLVE"'" \
          --set "genome.genes.gamma.mean=0.5" --set "genome.genes.gamma.scale=0.2" \
          --set "genome.genes.hidden_size.mean=40" --set "genome.genes.buffer_size.mean=1000" \
          --set "checkpoints.keep=30" --set "checkpoints.every_steps=0" \
          --label "$label" --series "'"$SERIES"'" --resume "" --no-pin '"$PROBE_FLAG"' \
          > "'"$CONSOLE_DIR"'/s${idx}_${seed}.log" 2>&1 < /dev/null
        status=$?
        echo "$(date "+%F %T") s${idx} seed $seed exit $status" >> "'"$DONE_FILE"'"
        exit "$status"
      '
done
