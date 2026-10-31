#!/usr/bin/env bash
# Packs every world of one finished experiment (scripts/logs.py archive,
# the project's own mechanism - nothing new invented here), in place, on
# whichever machine the simulation actually ran on. Nothing here knows
# about Desktop folders or remote hosts - that is fetch_results.sh's job,
# running on the Mac, pulling these .tar.gz files (over SSH if the
# simulation ran on the rented box) into the clean per-seed tree.
#
# --delete removes the logs/ copy once the archive is read back
# (scripts/logs.py archive already verifies the tarball before deleting
# anything) - worth it on the rented box, where disk is the scarce thing.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PASS=""; NAME=""; SERIES=""; SEEDS_COUNT=""; DELETE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pass) PASS="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --series) SERIES="$2"; shift 2 ;;
    --seeds) SEEDS_COUNT="$2"; shift 2 ;;
    --delete) DELETE=1; shift ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

[[ -n "$PASS" && -n "$NAME" && -n "$SERIES" ]] || {
  echo "Usage: $0 --pass N --name NAME --series SERIES [--seeds N] [--delete]" >&2
  exit 1
}

shopt -s nullglob
MATCHES=("$REPO_ROOT"/logs/"${SERIES}"/*_"${SERIES}"-s[0-9][0-9])
shopt -u nullglob

if [[ ${#MATCHES[@]} -eq 0 ]]; then
  echo "deliver.sh: no logs/${SERIES}/*_${SERIES}-s?? folders found - nothing to pack" >&2
  exit 0
fi

echo "deliver.sh: packing ${#MATCHES[@]} world(s) for ${NAME} -> $REPO_ROOT/archives/"

# scripts/logs.py archive takes a NAME SELECTOR, but its name-substring
# branch has a pre-existing bug (find() does os.path.basename(world)
# where world is a RunLogReader, not a path - crashes with a TypeError on
# anything that is not a plain number). Not ours to fix on the side here
# (CLAUDE.md: report, don't patch in passing; the owner has seen this one
# and does not need it fixed right now) - worked around by always
# selecting through the NUMBER from `list`, which never touches that
# branch. Re-listed fresh before EVERY archive call, not once for the
# whole loop: --delete removes a world, which can shift every other
# world's number in the next `list` (sorted newest-first) - a number
# captured before that deletion would then point at the wrong world.
for dir in "${MATCHES[@]}"; do
  base="$(basename "$dir")"
  seed_tag="${base##*-}"   # "s07" out of "..._p1-good_baseline-s07"

  if [[ -f "$REPO_ROOT/archives/${base}.tar.gz" ]]; then
    echo "  already archived: $base"
    continue
  fi

  number="$(PYTHONPATH=. .venv/bin/python scripts/logs.py list \
    | grep -E "^[[:space:]]*[0-9]+\. ${base}[[:space:]]" \
    | sed -E 's/^[[:space:]]*([0-9]+)\..*/\1/')"

  if [[ -z "$number" ]]; then
    echo "deliver.sh: $base not found in \`scripts/logs.py list\` - skipping" >&2
    continue
  fi

  PYTHONPATH=. .venv/bin/python scripts/logs.py archive "$number" \
    --note "pass${PASS} ${NAME} ${seed_tag} (${SEEDS_COUNT:-?} seeds total)" \
    $([[ "$DELETE" -eq 1 ]] && echo --delete)

  echo "  -> $REPO_ROOT/archives/${base}.tar.gz"
done
