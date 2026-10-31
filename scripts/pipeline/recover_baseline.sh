#!/usr/bin/env bash
# One-off recovery after checkpoints.keep=5 (meant for one run at a time)
# let 10 of 15 baseline seeds' checkpoints get evicted by each other's
# periodic saves before they could be used - see reproducibility.md /
# the owner's chat history for the full story. In order, this:
#
#   1. pulls the 5 PINNED checkpoints (the ones that survived - s11-s15,
#      already resumed and running on their own, untouched here) to the
#      Mac as a standing backup.
#   2. pulls the 10 orphaned worlds (crashed before 40000 episodes, not a
#      usable result on their own) into a clearly separate Desktop folder,
#      then moves - never deletes - them out of logs/p1-good_baseline/ on
#      the remote, so a freshly launched same-seed run does not collide
#      with them under fetch_results.sh's eyes.
#   3. launches those same 10 seeds again from episode 0, with
#      checkpoints.keep=30 (room for every seed in this experiment at
#      once, so the eviction race cannot happen again).
#
# Run from the Mac:
#   ./scripts/pipeline/recover_baseline.sh --host root@2.29.143.204 --remote-root /root/Growth.covenant
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST=""; KEY=""; REMOTE_ROOT=""; DEST_ROOT="$HOME/Desktop"; EPISODES=40000

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    --dest-root) DEST_ROOT="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

[[ -n "$HOST" && -n "$REMOTE_ROOT" ]] || {
  echo "Usage: $0 --host user@ip --remote-root /path [--key file] [--dest-root PATH]" >&2
  exit 1
}

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=3)
[[ -n "$KEY" ]] && SSH_OPTS+=(-i "$KEY")
RSH="ssh ${SSH_OPTS[*]}"

# idx|seed|checkpoint-filename-on-remote (s11-s15, already resumed - backup only)
ALIVE=(
  "11|2083014961|20261028-165004-5b0444_step000607713.pt"
  "12|703876974|20261028-165003-058f46_step000611388.pt"
  "13|2738809320|20261028-165004-b161bc_step000623614.pt"
  "14|4232660768|20261028-165003-4ce3c7_step000625500.pt"
  "15|2482739106|20261028-165004-1646cb_step000612455.pt"
)

# idx|seed (s01-s10 - checkpoint gone, restart from episode 0)
DEAD=(
  "01|1290435116"
  "02|4253778242"
  "03|301112939"
  "04|2753460196"
  "05|1809987412"
  "06|914445736"
  "07|2151682457"
  "08|2974571302"
  "09|588057067"
  "10|1226380944"
)

echo "=== step 1: backing up the 5 surviving checkpoints to $DEST_ROOT/baseline_checkpoints ==="
mkdir -p "$DEST_ROOT/baseline_checkpoints"
for row in "${ALIVE[@]}"; do
  IFS='|' read -r idx seed file <<< "$row"
  rsync -a -e "$RSH" "$HOST:$REMOTE_ROOT/checkpoints/pinned/$file" \
    "$DEST_ROOT/baseline_checkpoints/seed-${seed}.pt"
  echo "  seed $seed -> $DEST_ROOT/baseline_checkpoints/seed-${seed}.pt"
done

echo "=== step 2: moving the 10 orphaned worlds to $DEST_ROOT/baseline_incomplete ==="
mkdir -p "$DEST_ROOT/baseline_incomplete"
ssh "${SSH_OPTS[@]}" "$HOST" "mkdir -p '$REMOTE_ROOT/logs/_archived_incomplete'"
for row in "${DEAD[@]}"; do
  IFS='|' read -r idx seed <<< "$row"
  remote_dir=$(ssh "${SSH_OPTS[@]}" "$HOST" \
    "ls -d '$REMOTE_ROOT/logs/p1-good_baseline/'*"-s${idx}" 2>/dev/null | head -1")

  if [[ -z "$remote_dir" ]]; then
    echo "  seed $seed (s$idx): nothing found on remote, skipping" >&2
    continue
  fi

  final_dir="$DEST_ROOT/baseline_incomplete/seed-${seed}"
  rm -rf "$final_dir"
  rsync -a -e "$RSH" "$HOST:$remote_dir/" "$final_dir/"
  ssh "${SSH_OPTS[@]}" "$HOST" "mv '$remote_dir' '$REMOTE_ROOT/logs/_archived_incomplete/'"
  echo "  seed $seed -> $final_dir (remote copy archived, not deleted)"
done

echo "=== step 3: relaunching the 10 dead seeds from episode 0, checkpoints.keep=30 ==="

REMOTE_SCRIPT="$(mktemp)"
{
  echo "cd '$REMOTE_ROOT'"
  echo "mkdir -p .ai/pipeline/p1/good_baseline/restart_console"
  for row in "${DEAD[@]}"; do
    IFS='|' read -r idx seed <<< "$row"
    label="p1-good_baseline-s${idx}"
    cat <<EOF
nohup bash -c '
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python src/run.py \
    --episodes $EPISODES --seed $seed --agents 20 --species clons \
    --set "genome.evolve=[]" --set "checkpoints.keep=30" \
    --label "$label" --series "p1-good_baseline" --resume "" --no-pin \
    > ".ai/pipeline/p1/good_baseline/restart_console/s${idx}_${seed}.log" 2>&1
  echo "\$(date "+%F %T") s${idx} seed $seed exit \$?" >> ".ai/pipeline/p1/good_baseline/restart_done.txt"
' < /dev/null > /dev/null 2>&1 &
disown
EOF
  done
} > "$REMOTE_SCRIPT"

ssh "${SSH_OPTS[@]}" "$HOST" "bash -s" < "$REMOTE_SCRIPT"
rm -f "$REMOTE_SCRIPT"

for row in "${DEAD[@]}"; do
  IFS='|' read -r idx seed <<< "$row"
  echo "  launched s$idx seed $seed"
done

echo "=== done. 5 continuing (s11-s15, keep=20) + 10 restarted fresh (s01-s10, keep=30) ==="
