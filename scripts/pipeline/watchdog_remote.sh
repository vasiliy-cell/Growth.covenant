#!/usr/bin/env bash
# STUB - needs the rented server's SSH details before it does anything
# real. Fill in --host (and --key if not your default) once you have
# access, and this already does the two things asked for:
#
#   1. reachability: can we even SSH in right now (crash / network down)?
#   2. liveness: is the training loop still making progress, or stuck?
#      Liveness is read from the newest console log under
#      .ai/pipeline/p*/*/console/ on the REMOTE side - run_pass.sh already
#      writes one line per episode there, so "no new line in N minutes"
#      IS "long stall", with no extra instrumentation needed on the
#      remote end.
#
#   ./scripts/pipeline/watchdog_remote.sh --host user@1.2.3.4 \
#       --remote-root /home/user/Growth.covenant \
#       --stall-minutes 15 --poll-seconds 120 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST=""
KEY=""
REMOTE_ROOT=""
STALL_MINUTES=15
POLL_SECONDS=120
STATUS_LOG="$REPO_ROOT/.ai/pipeline/watchdog_remote.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    --stall-minutes) STALL_MINUTES="$2"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$HOST" || -z "$REMOTE_ROOT" ]]; then
  echo "watchdog_remote.sh is a stub until the server exists." >&2
  echo "Needs --host user@ip and --remote-root /path/to/Growth.covenant on it." >&2
  exit 1
fi

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)
[[ -n "$KEY" ]] && SSH_OPTS+=(-i "$KEY")

mkdir -p "$(dirname "$STATUS_LOG")"

notify() {
  local msg="$1"
  echo "$(date "+%F %T") $msg" >> "$STATUS_LOG"
  echo "$msg" >&2
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$msg\" with title \"Growth.covenant watchdog\"" >/dev/null 2>&1 || true
  fi
}

echo "watchdog_remote: watching $HOST:$REMOTE_ROOT, stall floor ${STALL_MINUTES}m, every ${POLL_SECONDS}s"

while true; do
  if ! ssh "${SSH_OPTS[@]}" "$HOST" "echo ok" >/dev/null 2>&1; then
    notify "SERVER UNREACHABLE: $HOST did not answer SSH"
    sleep "$POLL_SECONDS"
    continue
  fi

  # Newest line across every console log on the remote, with its age in
  # minutes - `find ... -printf` is GNU find; most rented Linux boxes have
  # it, unlike this Mac's BSD find, which is exactly why this stays remote.
  newest_age="$(ssh "${SSH_OPTS[@]}" "$HOST" \
    "find '$REMOTE_ROOT/.ai/pipeline' -name '*.log' -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | awk '{ print (systime()-\$1)/60 }'" \
    2>/dev/null || echo "")"

  if [[ -z "$newest_age" ]]; then
    notify "SERVER: no console logs found yet under $REMOTE_ROOT/.ai/pipeline"
  elif (( $(echo "$newest_age > $STALL_MINUTES" | bc -l 2>/dev/null || echo 0) )); then
    notify "SERVER STALLED: newest console log line is ${newest_age%.*} minutes old (floor ${STALL_MINUTES}m)"
  fi

  sleep "$POLL_SECONDS"
done
