#!/usr/bin/env bash
# Puts this repo on the rented box and builds its venv there. Re-run any
# time (rsync is incremental, pip installs are idempotent) - useful again
# after the box is torn down and rented fresh for pass 2.
#
#   ./scripts/pipeline/provision_remote.sh --host root@2.29.143.204 \
#       --remote-root /root/Growth.covenant
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

HOST=""; KEY=""; REMOTE_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done

[[ -n "$HOST" && -n "$REMOTE_ROOT" ]] || {
  echo "Usage: $0 --host user@ip --remote-root /path [--key file]" >&2
  exit 1
}

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=3)
[[ -n "$KEY" ]] && SSH_OPTS+=(-i "$KEY")

echo "provision_remote: rsyncing repo -> $HOST:$REMOTE_ROOT"
ssh "${SSH_OPTS[@]}" "$HOST" "mkdir -p '$REMOTE_ROOT'"
rsync -av --delete \
  --exclude .venv --exclude logs --exclude checkpoints --exclude models \
  --exclude archives --exclude .panel --exclude .pytest_cache \
  --exclude .ai/pipeline/fetch_staging --exclude '*.pyc' --exclude __pycache__ \
  -e "ssh ${SSH_OPTS[*]}" \
  "$REPO_ROOT/" "$HOST:$REMOTE_ROOT/"

echo "provision_remote: building venv (python3, CPU-only torch wheel - this project never calls .cuda())"
ssh "${SSH_OPTS[@]}" "$HOST" "
  set -e
  cd '$REMOTE_ROOT'
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip --quiet
  # Two separate calls on purpose: --index-url replaces PyPI for the
  # WHOLE command, not just the package it is written next to - numpy/
  # PyYAML/pyarrow are not on download.pytorch.org and would 404 if
  # given on the same line as torch's CPU-only index.
  .venv/bin/pip install --quiet 'numpy==2.0.2' 'PyYAML==6.0.3' 'pyarrow==21.0.0' pytest
  .venv/bin/pip install --quiet torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
  echo 'venv ready:'
  .venv/bin/python --version
  .venv/bin/python -c 'import torch, numpy, pyarrow, yaml; print(\"torch\", torch.__version__, \"numpy\", numpy.__version__, \"pyarrow\", pyarrow.__version__, \"cuda available:\", torch.cuda.is_available())'
"

echo "provision_remote: running the test suite"
ssh "${SSH_OPTS[@]}" "$HOST" "cd '$REMOTE_ROOT' && PYTHONPATH=. .venv/bin/python -m pytest -q"

echo "provision_remote: chmod pipeline scripts"
ssh "${SSH_OPTS[@]}" "$HOST" "chmod +x '$REMOTE_ROOT'/scripts/pipeline/*.sh"

echo "provision_remote: done"
