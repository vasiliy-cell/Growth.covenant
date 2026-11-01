#!/usr/bin/env bash
# Direction 1, run LOCALLY on the Mac, as a quick culprit-hunt for the
# reward drop the owner saw (adults start ~25-30/episode, fall to ~10 over
# roughly the first 0-300 episodes, then sit there forever).
#
# One group of genes evolves, every other gene is frozen at its config mean
# - exactly the "leave-one-in" design of experiments_pass1.sh, but on ONE
# seed, FEW episodes, no Desktop plumbing: the parquet logs land straight in
# logs/<world_id>_d1-<group>/ (a --label, no --series, so nothing nests),
# and this script only adds console logs under .ai/pipeline/d1_local/.
#
#   ./scripts/pipeline/run_direction1_local.sh
#   ./scripts/pipeline/run_direction1_local.sh --episodes 250 --seed 1290435116
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

EPISODES=250
SEED=1290435116   # s01, the canonical first seed of this research (seeds.sh)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --episodes) EPISODES="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

# The 6 leave-one-in groups of experiments_pass1.sh, all non_linear. The
# clons good_baseline is NOT here - this hunt only compares the groups that
# actually evolve something.
#
# NOT named GROUPS: that is a special bash array (the current user's Unix
# group ids) whose assignment is silently ignored - using it would launch
# one run per group id, labelled with a number, every gene frozen.
#
# memory drops min_buffer_size (owner's call): it stays frozen at its mean,
# same as in direction 2 - evolving it can drift it negative and there is
# no clamp for it.
GENE_GROUPS=(
  "network_shape|hidden_layers,hidden_size"
  "gamma|gamma"
  "optimizer|learning_rate,target_update_freq,max_norm"
  "memory|buffer_size,batch_size"
  "exploration|epsilon,epsilon_decay,epsilon_min"
  "curiosity|curiosity_beta,curiosity_decay"
)

CONSOLE_DIR="$REPO_ROOT/.ai/pipeline/d1_local"
mkdir -p "$CONSOLE_DIR"

echo "=== direction 1 local hunt / episodes $EPISODES / seed $SEED / non_linear / ${#GENE_GROUPS[@]} groups in parallel ==="

pids=()
for spec in "${GENE_GROUPS[@]}"; do
  IFS='|' read -r NAME GENES <<< "$spec"
  echo "  launching d1-$NAME (evolve=[$GENES])"
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python src/run.py \
    --episodes "$EPISODES" --seed "$SEED" --agents 20 --species non_linear \
    --set "genome.evolve=[${GENES}]" --set "checkpoints.keep=30" --set "checkpoints.every_steps=0" \
    --label "d1-$NAME" --resume "" --no-pin \
    > "$CONSOLE_DIR/${NAME}.log" 2>&1 < /dev/null &
  pids+=("$!")
done

# Wait for all, report each exit so a crash is loud, not swallowed.
fail=0
i=0
for spec in "${GENE_GROUPS[@]}"; do
  IFS='|' read -r NAME GENES <<< "$spec"
  if wait "${pids[$i]}"; then
    echo "  d1-$NAME finished ok"
  else
    echo "  !!! d1-$NAME CRASHED - see $CONSOLE_DIR/${NAME}.log" >&2
    fail=1
  fi
  i=$((i + 1))
done

echo "=== direction 1 local hunt done (fail=$fail) ==="
exit "$fail"
