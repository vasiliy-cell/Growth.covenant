#!/usr/bin/env bash
# Watches the rented server over SSH for the three things that would
# otherwise waste paid-for compute time unnoticed:
#
#   1. reachability: can we even SSH in right now (crash / network down)?
#   2. liveness: is the training loop still making progress, or stuck?
#      Read from the newest console log under .ai/pipeline/p*/*/console/
#      on the remote - run_pass.sh already writes one line per episode
#      there, so "no new line in N minutes" IS "long stall", with no
#      extra instrumentation needed on the remote end.
#   3. disk: a "young account" rented box can be disk-tight. Below
#      --min-free-gb this writes the REMOTE STOP flag (the same file
#      run_pass.sh checks before every seed) so no new simulation
#      starts - it never deletes anything by itself.
#
#   ./scripts/pipeline/watchdog_remote.sh --host root@2.29.143.204 \
#       --remote-root /root/Growth.covenant \
#       --stall-minutes 15 --min-free-gb 5 --poll-seconds 120 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST=""
KEY=""
REMOTE_ROOT=""
STALL_MINUTES=15
MIN_FREE_GB=5
POLL_SECONDS=120
STATUS_LOG="$REPO_ROOT/.ai/pipeline/watchdog_remote.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    --stall-minutes) STALL_MINUTES="$2"; shift 2 ;;
    --min-free-gb) MIN_FREE_GB="$2"; shift 2 ;;
    --poll-seconds) POLL_SECONDS="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$HOST" || -z "$REMOTE_ROOT" ]]; then
  echo "Usage: $0 --host user@ip --remote-root /path/to/Growth.covenant" >&2
  echo "          [--stall-minutes N] [--min-free-gb N] [--poll-seconds N]" >&2
  exit 1
fi

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=3)
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

echo "watchdog_remote: watching $HOST:$REMOTE_ROOT, stall floor ${STALL_MINUTES}m, disk floor ${MIN_FREE_GB}GB, every ${POLL_SECONDS}s"

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

  free_gb="$(ssh "${SSH_OPTS[@]}" "$HOST" \
    "df -Pk '$REMOTE_ROOT' | awk 'NR==2 { printf \"%d\", \$4/1024/1024 }'" \
    2>/dev/null || echo "")"

  if [[ -n "$free_gb" && "$free_gb" -lt "$MIN_FREE_GB" ]]; then
    stop_written="$(ssh "${SSH_OPTS[@]}" "$HOST" \
      "f='$REMOTE_ROOT/.ai/pipeline/STOP'; [ -f \"\$f\" ] && echo already || { mkdir -p \"\$(dirname \"\$f\")\" && echo 'disk: ${free_gb} GB free < ${MIN_FREE_GB} GB floor' > \"\$f\" && echo written; }" \
      2>/dev/null || echo "")"

    if [[ "$stop_written" == "written" ]]; then
      notify "LOW REMOTE DISK: ${free_gb} GB free (floor ${MIN_FREE_GB} GB) - remote STOP flag written, no new simulation will start"
    fi
  fi

  sleep "$POLL_SECONDS"
done
