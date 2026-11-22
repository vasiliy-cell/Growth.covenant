#!/usr/bin/env bash
# Fully autonomous overnight loop. No Claude/model calls - pure bash+python.
# Waits for batch7+batch8, then alternates new rounds between the
# mendel-non_linear probe front and the 3-pair survival front, based on
# overnight_ci_check.py's decision, until both are resolved or STOP_AT
# clock time is reached. Logs everything to .ai/pipeline/overnight.log.
set -uo pipefail

REPO="/Users/macbookairm4/projects/Growth.covenant"
HOST="root@62.238.127.235"
RR="/root/Growth.covenant"
SSHO="-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3"
DEST_ROOT="$HOME/Desktop/research"
LOG="$REPO/.ai/pipeline/overnight.log"
STOP_AT="09:00"
MAX_ROUNDS=8
ROUND_SIZE=30

cd "$REPO"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

wait_series() {
  while true; do
    n=$(ssh $SSHO "$HOST" "wc -l < $RR/.ai/pipeline/$1/done.txt 2>/dev/null" 2>/dev/null | tr -d ' ')
    n=${n:-0}
    [ "$n" -ge "$2" ] && break
    sleep 90
  done
}

fetch_series() {
  ./scripts/pipeline/fetch_results.sh --series "$1" --name "$1" \
    --dest-subdir "$2" --dest-root "$DEST_ROOT" \
    --host "$HOST" --remote-root "$RR" >> "$LOG" 2>&1
}

clean_contamination() {
  local base="$1"
  for d in "$base"/seed-*; do
    [ -d "$d" ] || continue
    s=$(basename "$d"); s="${s#seed-}"
    real=$(grep -o '"seed": [0-9]*' "$d/run.json" 2>/dev/null | head -1 | grep -o '[0-9]*')
    if [ -n "$real" ] && [ "$real" != "$s" ]; then
      if [ -d "$base/seed-$real" ]; then
        log "removing contaminated dup: $d (real=$real)"
        rm -rf "$d"
      else
        log "WARNING mismatch no correct copy: $d real=$real"
      fi
    fi
  done
}

log "=== overnight loop started ==="
log "waiting for batch7+batch8..."
wait_series batch7-mendel 50
wait_series batch7-non_linear 50
wait_series batch8-survival50-clons 50
wait_series batch8-survival50-mendel 50
wait_series batch8-survival50-non_linear 50
log "batch7+batch8 finished"

fetch_series batch7-mendel batch7-mn/mendel
fetch_series batch7-non_linear batch7-mn/non_linear
fetch_series batch8-survival50-clons batch8-survival50/clons
fetch_series batch8-survival50-mendel batch8-survival50/mendel
fetch_series batch8-survival50-non_linear batch8-survival50/non_linear
for d in batch7-mn/mendel batch7-mn/non_linear batch8-survival50/clons batch8-survival50/mendel batch8-survival50/non_linear; do
  clean_contamination "$DEST_ROOT/$d"
done
log "batch7+batch8 fetched and cleaned"

round=0
while [ "$round" -lt "$MAX_ROUNDS" ]; do
  now_hm=$(date '+%H:%M')
  decision=$(PYTHONPATH="$REPO" .venv/bin/python3 "$REPO/scripts/pipeline/overnight_ci_check.py" decide 2>>"$LOG")
  log "round $round decision: $decision (clock $now_hm)"

  if [ "$decision" = "DONE" ]; then log "both fronts resolved"; break; fi
  if [[ "$now_hm" > "$STOP_AT" ]]; then log "past stop-at $STOP_AT, not launching"; break; fi

  round=$((round + 1))
  SEEDFILE="$REPO/.ai/pipeline/overnight_seeds_r${round}.txt"
  PYTHONPATH="$REPO" .venv/bin/python3 "$REPO/scripts/pipeline/overnight_ci_check.py" seeds "$ROUND_SIZE" > "$SEEDFILE" 2>>"$LOG"
  NSEEDS=$(wc -l < "$SEEDFILE" | tr -d ' ')
  if [ "$NSEEDS" -lt "$ROUND_SIZE" ]; then log "ERROR: only $NSEEDS seeds generated, stopping"; break; fi
  log "round $round: $NSEEDS seeds for $decision"

  if [ "$decision" = "PROBE" ]; then
    SPECIES_LIST="mendel non_linear"; EPISODES=2000; PROBE_MODE="probe"
  else
    SPECIES_LIST="clons mendel non_linear"; EPISODES=500; PROBE_MODE="noprobe"
  fi
  SERIES_PREFIX="ovr${round}"

  rsync -az -e "ssh $SSHO" "$SEEDFILE" "$HOST:$RR/seeds_round.txt" >> "$LOG" 2>&1
  ssh $SSHO "$HOST" "cd $RR && mkdir -p .ai/pipeline && nohup ./scripts/pipeline/run_generic_round.sh seeds_round.txt $SERIES_PREFIX $EPISODES $PROBE_MODE $SPECIES_LIST > .ai/pipeline/run_${SERIES_PREFIX}.log 2>&1 < /dev/null & disown" >> "$LOG" 2>&1
  log "round $round launched ($SPECIES_LIST, $EPISODES ep, $PROBE_MODE)"

  for sp in $SPECIES_LIST; do
    wait_series "${SERIES_PREFIX}-${sp}" "$NSEEDS"
  done
  log "round $round finished on server"
  for sp in $SPECIES_LIST; do
    fetch_series "${SERIES_PREFIX}-${sp}" "overnight-r${round}/${sp}"
    clean_contamination "$DEST_ROOT/overnight-r${round}/${sp}"
  done
  log "round $round fetched and cleaned"
done

REPORT=$(PYTHONPATH="$REPO" .venv/bin/python3 "$REPO/scripts/pipeline/overnight_ci_check.py" report 2>>"$LOG")
log "FINAL REPORT: $REPORT"
log "=== overnight loop ended ==="
