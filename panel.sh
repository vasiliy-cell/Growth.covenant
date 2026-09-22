#!/bin/bash
# The control panel: watch runs, read their logs, start new ones.
#
#   ./panel.sh                 -> (re)starts the server and opens the panel
#   ./panel.sh --no-browser    -> just the server
#
# Uses the project venv, like run.sh does: the system python has none of
# the dependencies.
export PYTHONPATH=$PYTHONPATH:$(pwd)

PY="./.venv/bin/python3"
PORT=8000
URL="http://127.0.0.1:$PORT"

# Overridable so the opening can be tested without a window appearing.
OPEN_CMD="${OPEN_CMD:-open}"

OPEN_BROWSER=1
[ "$1" = "--no-browser" ] && OPEN_BROWSER=0

if [ ! -x "$PY" ]; then
    echo "❌ No venv at .venv - create one and pip install -r requirements.txt"
    exit 1
fi

# Everything the panel needs beyond the simulation itself.
if ! $PY -c "import fastapi, uvicorn, pyarrow" 2>/dev/null; then
    echo "📦 Installing missing dependencies..."
    $PY -m pip install -q -r requirements.txt || exit 1
fi

# --- always a fresh server ---
# An old panel still holding the port serves yesterday's api to today's
# page, and everything looks broken for reasons that are not in the code.
# So a running panel is stopped and started again, every time.
OLD=$(lsof -ti tcp:$PORT -sTCP:LISTEN 2>/dev/null)

if [ -n "$OLD" ]; then
    if ps -p "$OLD" -o command= | grep -q "src/UI/server.py"; then
        echo "♻️  Restarting the panel (was pid $OLD)"
        kill "$OLD"
        for _ in $(seq 1 40); do
            lsof -ti tcp:$PORT -sTCP:LISTEN >/dev/null 2>&1 || break
            sleep 0.1
        done
    else
        echo "❌ Port $PORT is taken by something else:"
        ps -p "$OLD" -o pid=,command=
        exit 1
    fi
fi

# --- which browser gets the panel ---
# The one you are looking at, if you are looking at a browser; otherwise
# the default one - which is also the answer when several are open and
# none is in front.
frontmost_browser() {
    local front
    front=$(osascript -e 'tell application "System Events" to get name of first application process whose frontmost is true' 2>/dev/null)

    case "$(echo "$front" | tr '[:upper:]' '[:lower:]')" in
        *safari*|*chrome*|*chromium*|*firefox*|*arc*|*brave*|*edge*|*vivaldi*|*opera*|*orion*|*zen*)
            echo "$front"
            ;;
    esac
}

open_panel() {
    # Wait for the port to answer: a browser pointed at a server that is
    # still starting shows an error page, and nobody reloads it. Loading
    # torch alone can take twenty seconds on a cold start.
    echo "⏳ Waiting for the server to start..."
    for _ in $(seq 1 240); do
        curl -s -o /dev/null --max-time 1 "$URL" && break
        sleep 0.25
    done

    local browser
    browser=$(frontmost_browser)

    if [ -n "$browser" ]; then
        echo "🌐 Opening in $browser"
        $OPEN_CMD -a "$browser" "$URL"
    else
        echo "🌐 Opening in the default browser"
        $OPEN_CMD "$URL"
    fi
}

echo "🎛  Panel: $URL  (ctrl-c to stop)"

$PY src/UI/server.py &
SERVER=$!

# However this script ends - ctrl-c, a signal, an error - the server goes
# with it instead of being left behind holding the port.
trap 'kill $SERVER 2>/dev/null' INT TERM EXIT

[ "$OPEN_BROWSER" = "1" ] && open_panel

wait $SERVER
