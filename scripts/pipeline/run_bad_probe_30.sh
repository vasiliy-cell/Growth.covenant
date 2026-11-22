#!/usr/bin/env bash
# Second-batch bad-baseline run WITH probe, for ALL THREE species in a row,
# on HALF of the new 30-seed batch (seeds_30.sh) - the half this machine
# was given (server or mac). Exists because the first-15-seed comparison
# was too noisy per species to say anything; this widens the sample.
#
# Same bad genes as before (gamma 0.5 / scale 0.2, hidden 40, buffer 1000),
# same evolve set, probe on. 2000 episodes this time (3000 was judged too
# expensive for the extra statistical power it bought).
#
#   ./scripts/pipeline/run_bad_probe_30.sh server   # SERVER_SEEDS, 2000 ep
#   ./scripts/pipeline/run_bad_probe_30.sh mac       # MAC_SEEDS, 2000 ep
#   ./scripts/pipeline/run_bad_probe_30.sh server 200 --parallel 8   # smoke
#   ./scripts/pipeline/run_bad_probe_30.sh third 2000 --species clons,mendel
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
source "$REPO_ROOT/scripts/pipeline/seeds_30.sh"

HALF="${1:?need: all | server | mac | extra | extra2 | third}"
EPISODES="${2:-2000}"
PARALLEL_OVERRIDE=""
SPECIES_LIST="clons,mendel,non_linear"
shift 2 2>/dev/null || shift $#
while [[ $# -gt 0 ]]; do
  case "$1" in
    --parallel) PARALLEL_OVERRIDE="$2"; shift 2 ;;
    --species) SPECIES_LIST="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

case "$HALF" in
  all)    SEEDS=("${SERVER_SEEDS[@]}" "${MAC_SEEDS[@]}") ;;
  server) SEEDS=("${SERVER_SEEDS[@]}") ;;
  mac)    SEEDS=("${MAC_SEEDS[@]}") ;;
  extra)  SEEDS=("${EXTRA_SEEDS[@]}") ;;
  extra2) SEEDS=("${SECOND_EXTRA_SEEDS[@]}") ;;
  third)  SEEDS=("${THIRD_BATCH_SEEDS[@]}") ;;
  *) echo "bad half: $HALF (want all|server|mac|extra|extra2|third)" >&2; exit 1 ;;
esac

IFS=',' read -r -a SPECIES_ARR <<< "$SPECIES_LIST"

EVOLVE="genome.evolve=[hidden_layers,hidden_size,gamma,learning_rate,target_update_freq,max_norm,buffer_size,batch_size,epsilon,epsilon_decay,epsilon_min,curiosity_beta,curiosity_decay]"

NPROC="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 8)"
PARALLEL="${PARALLEL_OVERRIDE:-$NPROC}"
if [[ "$PARALLEL" -gt "$NPROC" ]]; then PARALLEL="$NPROC"; fi

STOP_FLAG="$REPO_ROOT/.ai/pipeline/STOP"

echo "=== bad-probe-30-$HALF / episodes $EPISODES / seeds ${#SEEDS[@]} / parallel $PARALLEL (of $NPROC cores) / species: ${SPECIES_ARR[*]} in turn ==="

for SPECIES in "${SPECIES_ARR[@]}"; do
  SERIES="bad-probe-30-${HALF}-${SPECIES}"
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
          --label "$label" --series "'"$SERIES"'" --resume "" --no-pin --probe \
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

echo "=== bad-probe-30-$HALF all species done ==="
