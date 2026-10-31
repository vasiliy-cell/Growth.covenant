#!/usr/bin/env bash
# Periodic log push, so a result is not only ever seen at the very end of
# a 40000-episode run. Watches the REMOTE console logs for episode
# progress and calls fetch_results.sh (plain rsync mirror, see that
# script) whenever any experiment's running world has advanced another
# --every-episodes since it was last pulled.
#
#   ./scripts/pipeline/ship_logs.sh --pass 1 \
#       --host root@2.29.143.204 --remote-root /root/Growth.covenant &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PASS=""; LEG="good"; HOST=""; KEY=""; REMOTE_ROOT=""; DEST_ROOT="$HOME/Desktop"
EVERY_EPISODES=10000
POLL_SECONDS=60
STATE_DIR="$REPO_ROOT/.ai/pipeline/ship_state"
STATUS_LOG="$REPO_ROOT/.ai/pipeline/ship_logs.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pass) PASS="$2"; shift 2 ;;
    --leg) LEG="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    --dest-root) DEST_ROOT="$2"; shift 2 ;;
    --every-episodes) EVERY_EPISODES="$2"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

[[ "$PASS" == "1" || "$PASS" == "2" ]] || { echo "need --pass 1 or 2" >&2; exit 1; }
[[ -n "$HOST" && -n "$REMOTE_ROOT" ]] || {
  echo "Usage: $0 --pass {1|2} [--leg good|bad] --host user@ip --remote-root /path [--key file]" >&2
  echo "          [--dest-root PATH] [--every-episodes N] [--poll-seconds N]" >&2
  exit 1
}

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=3)
[[ -n "$KEY" ]] && SSH_OPTS+=(-i "$KEY")

if [[ "$PASS" == "1" ]]; then
  source "$REPO_ROOT/scripts/pipeline/experiments_pass1.sh"
  EXPERIMENTS=("${EXPERIMENTS_PASS1[@]}")
  PIPELINE_PREFIX="p1"
else
  [[ "$LEG" == "good" || "$LEG" == "bad" ]] || { echo "--leg must be good or bad" >&2; exit 1; }
  source "$REPO_ROOT/scripts/pipeline/experiments_pass2.sh"
  if [[ "$LEG" == "good" ]]; then
    EXPERIMENTS=("${EXPERIMENTS_PASS2_GOOD[@]}")
  else
    EXPERIMENTS=("${EXPERIMENTS_PASS2_BAD[@]}")
  fi
  PIPELINE_PREFIX="p2-${LEG}"
fi

mkdir -p "$STATE_DIR" "$(dirname "$STATUS_LOG")"
log() { echo "$(date "+%F %T") $1" | tee -a "$STATUS_LOG" >&2; }

log "ship_logs: watching $HOST:$REMOTE_ROOT, every ${EVERY_EPISODES} episodes, poll ${POLL_SECONDS}s"

while true; do
  for spec in "${EXPERIMENTS[@]}"; do
    [[ -z "$spec" ]] && continue
    IFS='|' read -r NAME SPECIES EVOLVE DEST_SUBDIR <<< "$spec"

    if [[ "$PASS" == "2" ]]; then
      SERIES="p${PASS}-${LEG}-${NAME}"
    else
      SERIES="p${PASS}-${NAME}"
    fi

    # The console dir has one log per seed; only the most recently
    # written one can possibly be the seed currently in progress (the
    # rest are already-finished seeds, static).
    current="$(ssh "${SSH_OPTS[@]}" "$HOST" \
      "f=\$(ls -t '$REMOTE_ROOT/.ai/pipeline/${PIPELINE_PREFIX}/${NAME}/console/'*.log 2>/dev/null | head -1); \
       [ -n \"\$f\" ] && tail -c 2000 \"\$f\" | grep -o 'Episode [0-9]\+' | tail -1" \
      2>/dev/null | grep -o '[0-9]\+' || true)"

    [[ -z "$current" ]] && continue

    state_file="$STATE_DIR/${SERIES}.last"
    last=0
    [[ -f "$state_file" ]] && last="$(cat "$state_file")"

    if (( current - last >= EVERY_EPISODES )); then
      log "$NAME: episode $current (was $last) - fetching"
      "$REPO_ROOT/scripts/pipeline/fetch_results.sh" --series "$SERIES" --name "$NAME" \
        --dest-subdir "$DEST_SUBDIR" --dest-root "$DEST_ROOT" \
        --host "$HOST" --remote-root "$REMOTE_ROOT" ${KEY:+--key "$KEY"} \
        >> "$STATUS_LOG" 2>&1 || log "$NAME: fetch failed, will retry next poll"
      echo "$current" > "$state_file"
    fi
  done

  sleep "$POLL_SECONDS"
done
