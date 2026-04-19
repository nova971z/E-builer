#!/usr/bin/env bash
set -euo pipefail

# J.A.R.V.I.S. Trading System — Start Server
# Usage: ./scripts/start.sh [--port PORT] [--bg]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/.jarvis.pid"
LOG_FILE="$PROJECT_DIR/jarvis.log"
DEFAULT_PORT=5000

port="$DEFAULT_PORT"
background=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) port="$2"; shift 2 ;;
        --bg)   background=true; shift ;;
        -h|--help)
            echo "Usage: $0 [--port PORT] [--bg]"
            echo "  --port PORT  Server port (default: $DEFAULT_PORT)"
            echo "  --bg         Run in background"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Check Python dependencies ---
echo "[JARVIS] Checking Python dependencies..."
missing=()
for pkg in flask flask_cors requests cryptography; do
    if ! python3 -c "import $pkg" 2>/dev/null; then
        missing+=("$pkg")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "[JARVIS] Missing packages: ${missing[*]}"
    echo "[JARVIS] Installing..."
    pip3 install --break-system-packages -q flask flask-cors requests cryptography 2>/dev/null \
        || pip3 install -q flask flask-cors requests cryptography
    echo "[JARVIS] Dependencies installed."
fi

# --- Kill existing process on target port ---
existing_pid=$(lsof -ti :"$port" 2>/dev/null || true)
if [[ -n "$existing_pid" ]]; then
    echo "[JARVIS] Killing existing process on port $port (PID: $existing_pid)..."
    kill "$existing_pid" 2>/dev/null || true
    sleep 1
fi

# Also kill via PID file if stale
if [[ -f "$PID_FILE" ]]; then
    old_pid=$(cat "$PID_FILE")
    if kill -0 "$old_pid" 2>/dev/null; then
        echo "[JARVIS] Killing previous instance (PID: $old_pid)..."
        kill "$old_pid" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

# --- Verify server.py exists ---
if [[ ! -f "$PROJECT_DIR/server.py" ]]; then
    echo "[JARVIS] ERROR: server.py not found in $PROJECT_DIR"
    exit 1
fi

# --- Start server ---
cd "$PROJECT_DIR"
export FLASK_PORT="$port"

if $background; then
    echo "[JARVIS] Starting server on port $port (background)..."
    nohup python3 server.py > "$LOG_FILE" 2>&1 &
    server_pid=$!
    echo "$server_pid" > "$PID_FILE"
    sleep 2

    if kill -0 "$server_pid" 2>/dev/null; then
        echo "[JARVIS] Server running — PID: $server_pid"
        echo "[JARVIS] Log: $LOG_FILE"
        echo "[JARVIS] Dashboard: http://localhost:$port"
    else
        echo "[JARVIS] ERROR: Server failed to start. Check $LOG_FILE"
        exit 1
    fi
else
    echo "[JARVIS] Starting server on port $port (foreground)..."
    echo "[JARVIS] Dashboard: http://localhost:$port"
    echo "[JARVIS] Press Ctrl+C to stop."
    echo ""
    python3 server.py
fi
