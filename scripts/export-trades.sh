#!/usr/bin/env bash
set -euo pipefail

# J.A.R.V.I.S. Trading System — Export Trades to CSV
# Usage: ./scripts/export-trades.sh [--port PORT] [--output DIR]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEFAULT_PORT=5000
OUTPUT_DIR="$PROJECT_DIR/exports"

port="$DEFAULT_PORT"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)   port="$2"; shift 2 ;;
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--port PORT] [--output DIR]"
            echo "  --port PORT    Server port (default: $DEFAULT_PORT)"
            echo "  --output DIR   Output directory (default: ./exports)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

BASE="http://localhost:$port"
timestamp=$(date +"%Y%m%d_%H%M%S")

# --- Verify server is running ---
if ! curl -s --max-time 3 "${BASE}/api/status" >/dev/null 2>&1; then
    echo "[JARVIS] ERROR: Server not reachable on port $port"
    echo "[JARVIS] Start the server first: ./scripts/start.sh"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# --- Export trades CSV ---
csv_file="$OUTPUT_DIR/trades_${timestamp}.csv"
http_code=$(curl -s -o "$csv_file" -w "%{http_code}" --max-time 10 "${BASE}/api/export/csv")

if [[ "$http_code" != "200" ]]; then
    echo "[JARVIS] ERROR: Export failed (HTTP $http_code)"
    rm -f "$csv_file"
    exit 1
fi

# --- Verify file ---
line_count=$(wc -l < "$csv_file")
file_size=$(stat -c%s "$csv_file" 2>/dev/null || stat -f%z "$csv_file" 2>/dev/null || echo "0")

if [[ "$line_count" -le 1 ]]; then
    echo "[JARVIS] Export complete but no trade data found."
    echo "[JARVIS] File: $csv_file (header only)"
else
    data_rows=$((line_count - 1))
    echo "[JARVIS] Export successful!"
    echo "[JARVIS] File: $csv_file"
    echo "[JARVIS] Trades: $data_rows rows ($(numfmt --to=iec "$file_size" 2>/dev/null || echo "${file_size}B"))"
fi

# --- Cleanup old exports (keep 20) ---
export_count=$(find "$OUTPUT_DIR" -name "trades_*.csv" -type f | wc -l)
if [[ "$export_count" -gt 20 ]]; then
    remove_count=$((export_count - 20))
    find "$OUTPUT_DIR" -name "trades_*.csv" -type f | sort | head -n "$remove_count" | while read -r old; do
        rm -f "$old"
    done
    echo "[JARVIS] Rotated $remove_count old export(s)."
fi
