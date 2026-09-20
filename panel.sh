#!/bin/bash
# The control panel: watch runs, read their logs, start new ones.
#
#   ./panel.sh            -> http://127.0.0.1:8000
#
# Uses the project venv, like run.sh does: the system python has none of
# the dependencies.
export PYTHONPATH=$PYTHONPATH:$(pwd)

PY="./.venv/bin/python3"

if [ ! -x "$PY" ]; then
    echo "❌ No venv at .venv - create one and pip install -r requirements.txt"
    exit 1
fi

# Everything the panel needs beyond the simulation itself.
if ! $PY -c "import fastapi, uvicorn, pyarrow" 2>/dev/null; then
    echo "📦 Installing missing dependencies..."
    $PY -m pip install -q -r requirements.txt || exit 1
fi

echo "🎛  Panel: http://127.0.0.1:8000  (ctrl-c to stop)"
$PY src/UI/server.py
