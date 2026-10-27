#!/usr/bin/env bash
# Periodic log push, so a result is not only ever seen at the very end of
# a 40000-episode run. STUB for the destination: until the server exists
# and you decide the real transport, --dest is a local path and this just
# mirrors logs/ into it with rsync - swap --dest for user@host:/path (or
# whatever rclone remote you pick later) and nothing else here changes.
#
# Triggers on EPISODE PROGRESS, not wall clock: every run_pass.sh launch
# already prints "Episode N/TOTAL" once per logging window to its console
# log (.ai/pipeline/p*/*/console/*.log) - this just tails those files.
# Shipping is a full `logs/` mirror each time, not a diff of one world,
# because rsync only moves what changed anyway and a single pass over
# everything is simpler than tracking per-world byte ranges.
#
#   ./scripts/pipeline/ship_logs.sh --every-episodes 10000 --dest ~/Desktop/Growth.covenant-live-sync &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVERY_EPISODES=10000
POLL_SECONDS=60
DEST="$HOME/Desktop/Growth.covenant-live-sync"
STATE_DIR="$REPO_ROOT/.ai/pipeline/ship_state"
STATUS_LOG="$REPO_ROOT/.ai/pipeline/ship_logs.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --every-episodes) EVERY_EPISODES="$2"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$STATE_DIR" "$(dirname "$STATUS_LOG")"

log() { echo "$(date "+%F %T") $1" >> "$STATUS_LOG"; }

ship() {
  mkdir -p "$DEST"
  # Local stub: plain rsync mirror. A remote --dest (user@host:/path) works
  # with the exact same command once you have one - rsync does not care.
  rsync -a "$REPO_ROOT/logs/" "$DEST/logs/" 2>&1 | tee -a "$STATUS_LOG" >/dev/null
  rsync -a "$REPO_ROOT/.ai/pipeline/" "$DEST/pipeline-state/" 2>&1 | tee -a "$STATUS_LOG" >/dev/null
  log "shipped (mirror of logs/ -> $DEST)"
}

echo "ship_logs: every ${EVERY_EPISODES} episodes, polling every ${POLL_SECONDS}s, dest=$DEST (stub: local rsync mirror)"

while true; do
  shopt -s nullglob
  CONSOLE_LOGS=("$REPO_ROOT"/.ai/pipeline/p*/*/console/*.log)
  shopt -u nullglob

  should_ship=0

  for f in "${CONSOLE_LOGS[@]}"; do
    current="$(grep -o 'Episode [0-9]\+' "$f" | tail -1 | grep -o '[0-9]\+' || true)"
    [[ -z "$current" ]] && continue

    state_file="$STATE_DIR/$(basename "$f").last"
    last=0
    [[ -f "$state_file" ]] && last="$(cat "$state_file")"

    if (( current - last >= EVERY_EPISODES )); then
      should_ship=1
      echo "$current" > "$state_file"
    fi
  done

  if [[ "$should_ship" -eq 1 ]]; then
    ship
  fi

  sleep "$POLL_SECONDS"
done
