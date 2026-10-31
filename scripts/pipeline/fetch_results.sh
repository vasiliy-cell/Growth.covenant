#!/usr/bin/env bash
# Mirrors one experiment's world folders (logs/<series>/<world>) into the
# clean per-seed tree the owner asked for - directly, no archive/unpack
# step: rsync only ever sees finished, renamed-into-place parquet parts
# (see CLAUDE.md on how this project writes logs), so a mirror taken at
# any moment is a safe, partial-but-honest copy, never a torn one. Safe
# to call repeatedly while a world is still being written - that is
# exactly what ship_logs.sh does, periodically, mid-run - or once, after
# the whole experiment is done.
#
#   <dest-root>/<dest-subdir>/seed-<seed>/   (run.json, steps/, ...)
#
# idx -> seed comes from this project's own fixed, ordered seed list
# (seeds.sh), not from guessing or re-deriving it: label s07 IS seeds.sh
# index 7, always, by construction (run_pass.sh never reorders it).
#
#   ./scripts/pipeline/fetch_results.sh --pass 1 --name good_baseline \
#       --dest-subdir baseline \
#       --host root@2.29.143.204 --remote-root /root/Growth.covenant
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PASS=""; NAME=""; SERIES_OVERRIDE=""; DEST_SUBDIR=""; DEST_ROOT="$HOME/Desktop"
HOST=""; KEY=""; REMOTE_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pass) PASS="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --series) SERIES_OVERRIDE="$2"; shift 2 ;;
    --dest-subdir) DEST_SUBDIR="$2"; shift 2 ;;
    --dest-root) DEST_ROOT="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

[[ -n "$NAME" && -n "$DEST_SUBDIR" ]] || {
  echo "Usage: $0 --series SERIES --name NAME --dest-subdir PATH [--dest-root PATH]" >&2
  echo "          (or legacy: --pass N --name NAME, series becomes p<N>-<name>)" >&2
  echo "          [--host user@ip --remote-root /path [--key file]]" >&2
  exit 1
}

source "$REPO_ROOT/scripts/pipeline/seeds.sh"

# --series is authoritative when given (pass 2's good/bad legs reuse the
# same NAME on both legs, so --pass/--name alone cannot tell them apart).
# --pass/--name alone still works for pass 1, where NAME is unique already.
if [[ -n "$SERIES_OVERRIDE" ]]; then
  SERIES="$SERIES_OVERRIDE"
elif [[ -n "$PASS" ]]; then
  SERIES="p${PASS}-${NAME}"
else
  echo "need --series, or --pass + --name" >&2
  exit 1
fi
TARGET_DIR="$DEST_ROOT/$DEST_SUBDIR"
mkdir -p "$TARGET_DIR"

sync_one() {
  local world="$1" src="$2"
  local idx="${world##*-s}"
  idx=$((10#$idx))   # 10#: strip a leading zero without bash reading "08" as invalid octal
  local seed="${SEEDS[$((idx - 1))]}"
  local final_dir="$TARGET_DIR/seed-${seed}"
  local world_id="${world%%_*}"   # everything before the first "_" - the run's own id, not the label
  local marker="$final_dir/.fetched_world_id"

  mkdir -p "$final_dir"

  # seed-<seed>/ is reused across re-runs of the same experiment (a fresh
  # world every time, --resume "" - see run_pass.sh), but has no world_id
  # of its own once renamed. Without this check a stale folder from an
  # earlier/demo run would silently MERGE two different worlds' parquet
  # parts under one name - refuse instead, and say so.
  if [[ -f "$marker" ]] && [[ "$(cat "$marker")" != "$world_id" ]]; then
    echo "  !! $final_dir already holds a DIFFERENT world ($(cat "$marker")) - not merging $world_id into it. Remove that folder by hand first if you mean to replace it." >&2
    return 1
  fi

  # This connection stalls mid-transfer often enough to need its own
  # retry, separate from SSH's keepalive (which only proves the session
  # is alive, not that data is still flowing) - --timeout aborts rsync
  # itself when no bytes move for that long, so a stall becomes a quick
  # failure here instead of an hours-long silent hang.
  local attempt ok=0
  for attempt in 1 2 3 4 5; do
    if [[ -n "$HOST" ]]; then
      rsync -a --timeout=30 -e "ssh ${SSH_OPTS[*]}" "$HOST:$src/" "$final_dir/" && { ok=1; break; }
    else
      rsync -a "$src/" "$final_dir/" && { ok=1; break; }
    fi
    echo "  retry $attempt/5 for $world after a stall/drop" >&2
  done

  # Found the hard way: 5 drops in a row on attempt 5 used to fall off the
  # end of this loop and print success anyway - the seed came out missing
  # thousands of parquet parts with nothing in the log to say so. Treat
  # "every attempt failed" as failure, loudly, not quietly as done.
  if [[ "$ok" -ne 1 ]]; then
    echo "  !! $world: all 5 attempts failed - NOT marking as fetched. Re-run fetch_results.sh for this series to retry." >&2
    return 1
  fi

  echo "$world_id" > "$marker"
  echo "  seed $seed <- $src/"
}

if [[ -n "$HOST" ]]; then
  [[ -n "$REMOTE_ROOT" ]] || { echo "--host needs --remote-root" >&2; exit 1; }
  SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=3)
  [[ -n "$KEY" ]] && SSH_OPTS+=(-i "$KEY")

  WORLD_DIRS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && WORLD_DIRS+=("$line")
  done < <(ssh "${SSH_OPTS[@]}" "$HOST" "ls '$REMOTE_ROOT/logs/$SERIES/' 2>/dev/null" || true)

  if [[ ${#WORLD_DIRS[@]} -eq 0 ]]; then
    echo "fetch_results: nothing under $HOST:$REMOTE_ROOT/logs/$SERIES/ yet" >&2
    exit 0
  fi

  echo "fetch_results: pulling ${#WORLD_DIRS[@]} world(s) from $HOST -> $TARGET_DIR"
  FAILED=()
  for world in "${WORLD_DIRS[@]}"; do
    sync_one "$world" "$REMOTE_ROOT/logs/$SERIES/$world" || FAILED+=("$world")
  done
  if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo "fetch_results: ${#FAILED[@]} world(s) FAILED after 5 attempts each - re-run this command to retry them:" >&2
    printf '  %s\n' "${FAILED[@]}" >&2
    exit 1
  fi
else
  shopt -s nullglob
  WORLD_PATHS=("$REPO_ROOT"/logs/"$SERIES"/*-s[0-9][0-9])
  shopt -u nullglob

  if [[ ${#WORLD_PATHS[@]} -eq 0 ]]; then
    echo "fetch_results: nothing under $REPO_ROOT/logs/$SERIES/ yet" >&2
    exit 0
  fi

  echo "fetch_results: copying ${#WORLD_PATHS[@]} world(s) from local logs/ -> $TARGET_DIR"
  for dir in "${WORLD_PATHS[@]}"; do
    sync_one "$(basename "$dir")" "$dir"
  done
fi
