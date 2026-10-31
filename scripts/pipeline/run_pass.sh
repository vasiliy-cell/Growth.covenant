#!/usr/bin/env bash
# Runs one whole pass (baseline + the 6 groups, or pass 2 once its TODOs
# are filled in): every experiment of that pass, every fixed seed (or a
# handful, in --mode smoke).
#
# AS MANY SEEDS IN PARALLEL AS THERE ARE CORES, NEVER MORE. Each run.py
# process is pinned to one thread (OMP_NUM_THREADS=1 MKL_NUM_THREADS=1),
# so one seed per core uses the box fully; the owner's own prior tests
# found that oversubscribing past the core count makes every simulation
# slow down NONLINEARLY (not just share the same total throughput), so
# --parallel is hard-capped at `nproc` here, never raised past it even if
# asked. Experiments themselves still run one after another - with 15
# seeds and a double-digit core count both common here, one experiment's
# whole batch already saturates the box; there is nothing left over to
# gain from overlapping two experiments too.
#
#   ./scripts/pipeline/run_pass.sh --pass 1 --mode smoke
#   ./scripts/pipeline/run_pass.sh --pass 1 --mode full
#   ./scripts/pipeline/run_pass.sh --pass 1 --mode full --parallel 8
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
LEG="good"
EPISODES_OVERRIDE=""
SMOKE_SEEDS=1
PARALLEL=""
ONLY=""
ARCHIVE_AFTER=0
DELETE_AFTER_ARCHIVE=0
STOP_FLAG="$REPO_ROOT/.ai/pipeline/STOP"
YES=0

usage() {
  echo "Usage: $0 --pass {1|2} --mode {smoke|full} [--leg good|bad]" >&2
  echo "          [--episodes N] [--smoke-seeds N] [--parallel N] [--only NAME]" >&2
  echo "          [--archive-after [--delete-after-archive]] [--yes]" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pass) PASS="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --leg) LEG="$2"; shift 2 ;;
    --episodes) EPISODES_OVERRIDE="$2"; shift 2 ;;
    --smoke-seeds) SMOKE_SEEDS="$2"; shift 2 ;;
    --parallel) PARALLEL="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --archive-after) ARCHIVE_AFTER=1; shift ;;
    --delete-after-archive) DELETE_AFTER_ARCHIVE=1; shift ;;
    --yes) YES=1; shift ;;
    *) usage ;;
  esac
done

NPROC="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)"

if [[ -z "$PARALLEL" ]]; then
  PARALLEL="$NPROC"
elif [[ "$PARALLEL" -gt "$NPROC" ]]; then
  echo "--parallel $PARALLEL > $NPROC cores on this box - oversubscribing measured" >&2
  echo "SLOWER, not faster, in the owner's own tests. Capping at $NPROC." >&2
  PARALLEL="$NPROC"
fi

[[ "$PASS" == "1" || "$PASS" == "2" ]] || usage
[[ "$MODE" == "smoke" || "$MODE" == "full" ]] || usage

source "$REPO_ROOT/scripts/pipeline/seeds.sh"

if [[ "$PASS" == "1" ]]; then
  source "$REPO_ROOT/scripts/pipeline/experiments_pass1.sh"
  EXPERIMENTS=("${EXPERIMENTS_PASS1[@]}")
else
  [[ "$LEG" == "good" || "$LEG" == "bad" ]] || usage
  source "$REPO_ROOT/scripts/pipeline/experiments_pass2.sh"
  if [[ "$LEG" == "good" ]]; then
    EXPERIMENTS=("${EXPERIMENTS_PASS2_GOOD[@]}")
  else
    EXPERIMENTS=("${EXPERIMENTS_PASS2_BAD[@]}")
  fi
fi

if [[ -n "$ONLY" ]]; then
  FILTERED=()
  for spec in "${EXPERIMENTS[@]}"; do
    [[ "$spec" == "${ONLY}|"* ]] && FILTERED+=("$spec")
  done
  if [[ ${#FILTERED[@]} -eq 0 ]]; then
    echo "--only $ONLY matches no experiment in pass $PASS" >&2
    exit 1
  fi
  EXPERIMENTS=("${FILTERED[@]}")
fi

if [[ "$PASS" == "2" && "$LEG" == "bad" ]]; then
  if [[ ${#EXPERIMENTS[@]} -eq 0 ]]; then
    echo "Pass 2 (bad leg) is still a skeleton: experiments_pass2.sh's" >&2
    echo "EXPERIMENTS_PASS2_BAD has no uncommented experiments. Fill in" >&2
    echo "bad_baseline.yml first (see the comments in that file)." >&2
    exit 1
  fi

  BAD_BASELINE="$REPO_ROOT/research/Which inheritance mechanisms of hyberparametres give rise to increasingly optimized agents?/bad_baseline.yml"
  if [[ ! -f "$BAD_BASELINE" ]]; then
    echo "Missing $BAD_BASELINE - the bad leg needs the owner's deliberately" >&2
    echo "worsened gene means written there first. Refusing to guess them." >&2
    exit 1
  fi

  echo "Pass 2 (bad leg) runs with config.yml REPLACED by bad_baseline.yml for" >&2
  echo "its whole duration (run.py has no --config flag; this is the" >&2
  echo "established way to switch the live config - see experiments_pass2.sh)." >&2
  if [[ "$YES" -ne 1 ]]; then
    read -r -p "Overwrite config.yml with bad_baseline.yml now? [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
  fi
  cp "$REPO_ROOT/config.yml" "$REPO_ROOT/.ai/pipeline/config.yml.before-pass2-bad.bak"
  cp "$BAD_BASELINE" "$REPO_ROOT/config.yml"
  echo "config.yml replaced. Previous copy saved to .ai/pipeline/config.yml.before-pass2-bad.bak"
fi

if [[ "$MODE" == "smoke" ]]; then
  EPISODES="${EPISODES_OVERRIDE:-10}"
  RUN_SEEDS=("${SEEDS[@]:0:$SMOKE_SEEDS}")
else
  EPISODES="${EPISODES_OVERRIDE:-40000}"
  RUN_SEEDS=("${SEEDS[@]}")
fi

mkdir -p "$REPO_ROOT/.ai/pipeline"

echo "=== pass $PASS / mode $MODE / episodes $EPISODES / seeds ${#RUN_SEEDS[@]} / parallel $PARALLEL (of $NPROC cores) ==="

for spec in "${EXPERIMENTS[@]}"; do
  [[ -z "$spec" ]] && continue

  IFS='|' read -r NAME SPECIES EVOLVE DEST_SUBDIR <<< "$spec"
  # pass 2's good and bad legs reuse the same experiment names (clons,
  # non_linear, mendel) on the same 15 seeds - LEG goes into both the
  # series (so world folders/labels s01..s15 never collide) and the local
  # bookkeeping path (so console logs/done.txt don't collide either).
  if [[ "$PASS" == "2" ]]; then
    SERIES="p${PASS}-${LEG}-${NAME}"
    PIPELINE_SUBDIR="p${PASS}-${LEG}/${NAME}"
  else
    SERIES="p${PASS}-${NAME}"
    PIPELINE_SUBDIR="p${PASS}/${NAME}"
  fi

  if [[ -n "$EVOLVE" ]]; then
    EVOLVE_SET="genome.evolve=[${EVOLVE}]"
  else
    EVOLVE_SET="genome.evolve=[]"
  fi

  CONSOLE_DIR="$REPO_ROOT/.ai/pipeline/${PIPELINE_SUBDIR}/console"
  DONE_FILE="$REPO_ROOT/.ai/pipeline/${PIPELINE_SUBDIR}/done.txt"
  mkdir -p "$CONSOLE_DIR"

  echo "--- experiment: $NAME (species=$SPECIES, evolve=[$EVOLVE]) series=$SERIES, ${#RUN_SEEDS[@]} seed(s), up to $PARALLEL at once ---"

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

  echo "--- $NAME done (fetch_results.sh/ship_logs.sh, running on the Mac, mirror its logs to the Desktop tree - dest_subdir: $DEST_SUBDIR) ---"

  # Archiving is OFF by default on purpose: scripts/logs.py archive adds
  # a compressed COPY next to the raw logs/ folder - on a disk-constrained
  # rented box that is more disk used, not less, until something deletes
  # the original too. --delete-after-archive does that, but only do it
  # once the Mac side has actually pulled this experiment's logs - this
  # script has no way to know that from here (ship_logs.sh runs
  # independently, over SSH, possibly from a dead session by then).
  if [[ "$ARCHIVE_AFTER" -eq 1 ]]; then
    "$REPO_ROOT/scripts/pipeline/deliver.sh" --pass "$PASS" --name "$NAME" --series "$SERIES" \
      --seeds "${#RUN_SEEDS[@]}" \
      $([[ "$DELETE_AFTER_ARCHIVE" -eq 1 ]] && echo --delete)
  fi
done

echo "=== pass $PASS / mode $MODE finished ==="
