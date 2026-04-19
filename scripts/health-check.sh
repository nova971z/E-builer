#!/usr/bin/env bash
set -euo pipefail

# J.A.R.V.I.S. Trading System — Health Check
# Usage: ./scripts/health-check.sh [--port PORT] [--verbose]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEFAULT_PORT=5000

port="$DEFAULT_PORT"
verbose=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)    port="$2"; shift 2 ;;
        --verbose) verbose=true; shift ;;
        -h|--help)
            echo "Usage: $0 [--port PORT] [--verbose]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

BASE="http://localhost:$port"
passed=0
failed=0
total=0

check_route() {
    local method="$1"
    local path="$2"
    local label="$3"
    local data="${4:-}"
    total=$((total + 1))

    local http_code
    local body

    if [[ "$method" == "GET" ]]; then
        body=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${BASE}${path}" 2>/dev/null || echo "000")
    else
        body=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 -X POST \
            -H "Content-Type: application/json" \
            -d "$data" "${BASE}${path}" 2>/dev/null || echo "000")
    fi

    http_code="$body"

    if [[ "$http_code" =~ ^(200|201)$ ]]; then
        printf "  \033[32m✓\033[0m %-35s %s\n" "$label" "$http_code"
        passed=$((passed + 1))
    elif [[ "$http_code" == "000" ]]; then
        printf "  \033[31m✗\033[0m %-35s %s\n" "$label" "TIMEOUT/UNREACHABLE"
        failed=$((failed + 1))
    else
        printf "  \033[33m~\033[0m %-35s %s\n" "$label" "$http_code"
        # 4xx/5xx from external API proxies are acceptable — server is running
        if [[ "$http_code" =~ ^(502|503)$ ]]; then
            passed=$((passed + 1))
        else
            failed=$((failed + 1))
        fi
    fi

    if $verbose && [[ "$method" == "GET" ]]; then
        local resp
        resp=$(curl -s --max-time 5 "${BASE}${path}" 2>/dev/null | head -c 200)
        echo "      → ${resp:0:200}"
    fi
}

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     J.A.R.V.I.S. Health Check — port $port     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# --- Server connectivity ---
echo "[System]"
check_route GET "/api/status" "System status"

# --- Market data ---
echo ""
echo "[Market Data]"
check_route GET "/api/candles?symbol=BTCUSDT&interval=1h&limit=5" "Candles (BTC 1h)"
check_route GET "/api/price?symbol=BTCUSDT" "Price (BTC)"
check_route GET "/api/orderbook?symbol=BTCUSDT&limit=5" "Order book (BTC)"
check_route GET "/api/trades?symbol=BTCUSDT" "Recent trades (BTC)"
check_route GET "/api/ticker" "Ticker (multi-pair)"

# --- Indicators + Intelligence ---
echo ""
echo "[Intelligence]"
check_route GET "/api/indicators?symbol=BTCUSDT&interval=1h" "Indicators (BTC 1h)"
check_route GET "/api/dip-top?symbol=BTCUSDT" "Dip/Top detector"
check_route GET "/api/whales?symbol=BTCUSDT" "Whale tracking"

# --- Sentiment ---
echo ""
echo "[Sentiment]"
check_route GET "/api/funding?symbol=BTCUSDT" "Funding rate"
check_route GET "/api/fear-greed" "Fear & Greed index"
check_route GET "/api/sentiment?symbol=BTCUSDT" "Sentiment (OI/LS)"

# --- News + Calendar ---
echo ""
echo "[News & Calendar]"
check_route GET "/api/news" "News feed"
check_route GET "/api/calendar" "Economic calendar"

# --- Trading ---
echo ""
echo "[Trading]"
check_route GET "/api/positions" "Positions"
check_route GET "/api/balance" "Balance"
check_route GET "/api/paper/status" "Paper status"
check_route GET "/api/paper/history" "Paper history"

# --- Monitoring ---
echo ""
echo "[Monitoring]"
check_route GET "/api/killswitch/status" "Kill switch status"
check_route GET "/api/drawdown" "Drawdown"
check_route GET "/api/journal" "Trade journal"
check_route GET "/api/exchanges/list" "Exchanges list"

# --- Static ---
echo ""
echo "[Static Assets]"
check_route GET "/" "Dashboard HTML"

# --- Summary ---
echo ""
echo "──────────────────────────────────────────────"
printf "Total: %d | \033[32mPassed: %d\033[0m | \033[31mFailed: %d\033[0m\n" "$total" "$passed" "$failed"
echo ""

if [[ $failed -eq 0 ]]; then
    echo "🟢 All systems operational."
    exit 0
elif [[ $failed -le 3 ]]; then
    echo "🟡 Degraded — some external APIs may be unreachable."
    exit 0
else
    echo "🔴 Critical — $failed routes failed."
    exit 1
fi
