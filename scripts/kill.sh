#!/usr/bin/env bash
set -euo pipefail

# J.A.R.V.I.S. Trading System — Kill Server
# Usage: ./scripts/kill.sh [--port PORT]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/.jarvis.pid"
DEFAULT_PORT=5000

port="$DEFAULT_PORT"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) port="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--port PORT]"
            echo "  --port PORT  Server port to kill (default: $DEFAULT_PORT)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

killed=false

# --- Kill via PID file ---
if [[ -f "$PID_FILE" ]]; then
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        echo "[JARVIS] Stopping server (PID: $pid)..."
        kill "$pid"
        sleep 1
        # Force kill if still alive
        if kill -0 "$pid" 2>/dev/null; then
            echo "[JARVIS] Force killing (PID: $pid)..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        killed=true
    fi
    rm -f "$PID_FILE"
    echo "[JARVIS] PID file removed."
fi

# --- Kill via port ---
port_pid=$(lsof -ti :"$port" 2>/dev/null || true)
if [[ -n "$port_pid" ]]; then
    echo "[JARVIS] Killing process on port $port (PID: $port_pid)..."
    kill "$port_pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$port_pid" 2>/dev/null; then
        kill -9 "$port_pid" 2>/dev/null || true
    fi
    killed=true
fi

# --- Cleanup ---
rm -f "$PROJECT_DIR/.jarvis.pid"

if $killed; then
    echo "[JARVIS] Server stopped."
else
    echo "[JARVIS] No running server found."
fi
