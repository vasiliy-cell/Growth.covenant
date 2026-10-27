#!/usr/bin/env bash
# Watches local free disk space while a pass is running. Logs land on
# whatever volume --path is on (default: this repo's own volume, since
# that is where logs/, archives/ and the delivered results all sit).
#
# On low space: writes .ai/pipeline/STOP (run_pass.sh refuses to start the
# NEXT experiment while it exists - it never kills a run already going,
# and it never deletes anything by itself) and fires a local notification.
# Remove the flag by hand once you have freed space.
#
#   ./scripts/pipeline/watchdog_disk.sh --min-free-gb 20 --poll-seconds 120 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WATCH_PATH="$REPO_ROOT"
MIN_FREE_GB=20
POLL_SECONDS=120
STOP_FLAG="$REPO_ROOT/.ai/pipeline/STOP"
STATUS_LOG="$REPO_ROOT/.ai/pipeline/watchdog_disk.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) WATCH_PATH="$2"; shift 2 ;;
    --min-free-gb) MIN_FREE_GB="$2"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$(dirname "$STATUS_LOG")"

notify() {
  local msg="$1"
  echo "$(date "+%F %T") $msg" >> "$STATUS_LOG"
  echo "$msg" >&2
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$msg\" with title \"Growth.covenant watchdog\"" >/dev/null 2>&1 || true
  fi
}

free_gb() {
  # df -Pk: POSIX output, 1024-byte blocks, portable across macOS/Linux.
  df -Pk "$WATCH_PATH" | awk 'NR==2 { printf "%d", $4 / 1024 / 1024 }'
}

echo "watchdog_disk: watching $WATCH_PATH, floor ${MIN_FREE_GB} GB, every ${POLL_SECONDS}s"

while true; do
  free="$(free_gb)"

  if [[ "$free" -lt "$MIN_FREE_GB" ]]; then
    if [[ ! -f "$STOP_FLAG" ]]; then
      mkdir -p "$(dirname "$STOP_FLAG")"
      echo "disk: ${free} GB free < ${MIN_FREE_GB} GB floor, at $(date)" > "$STOP_FLAG"
      notify "LOW DISK: ${free} GB free (floor ${MIN_FREE_GB} GB) - STOP flag written, no new experiment will start"
    fi
  fi

  sleep "$POLL_SECONDS"
done
