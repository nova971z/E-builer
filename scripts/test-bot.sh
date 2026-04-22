#!/bin/bash
# Test suite for JARVIS Autonomous Bot
# Usage: ./scripts/test-bot.sh [base_url]

BASE="${1:-http://localhost:5000}"
PASS=0
FAIL=0
TOTAL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_route() {
    local method="$1"
    local path="$2"
    local expect="$3"
    local body="$4"
    local desc="${method} ${path}"
    TOTAL=$((TOTAL + 1))

    if [ "$method" = "POST" ] && [ -n "$body" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE}${path}" \
            -H "Content-Type: application/json" -d "$body" --max-time 10 2>/dev/null)
    elif [ "$method" = "POST" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE}${path}" \
            -H "Content-Type: application/json" --max-time 10 2>/dev/null)
    else
        status=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}${path}" --max-time 10 2>/dev/null)
    fi

    if [ "$status" = "$expect" ]; then
        echo -e "  ${GREEN}PASS${NC}  ${desc} → ${status}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC}  ${desc} → ${status} (expected ${expect})"
        FAIL=$((FAIL + 1))
    fi
}

test_json_field() {
    local path="$1"
    local field="$2"
    local desc="GET ${path} has '${field}'"
    TOTAL=$((TOTAL + 1))

    resp=$(curl -s "${BASE}${path}" --max-time 10 2>/dev/null)
    if echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '${field}' in d" 2>/dev/null; then
        echo -e "  ${GREEN}PASS${NC}  ${desc}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC}  ${desc}"
        FAIL=$((FAIL + 1))
    fi
}

test_security() {
    local desc="$1"
    local path="$2"
    local body="$3"
    local expect="$4"
    TOTAL=$((TOTAL + 1))

    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE}${path}" \
        -H "Content-Type: application/json" -d "$body" --max-time 10 2>/dev/null)

    if [ "$status" = "$expect" ]; then
        echo -e "  ${GREEN}PASS${NC}  ${desc} → ${status}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC}  ${desc} → ${status} (expected ${expect})"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo -e "${YELLOW}=== JARVIS Bot Test Suite ===${NC}"
echo ""

# --- SERVER HEALTH ---
echo -e "${YELLOW}[1/8] Server Health${NC}"
test_route "GET" "/api/status" 200

# --- MARKET DATA ---
echo -e "\n${YELLOW}[2/8] Market Data Routes${NC}"
test_route "GET" "/api/candles?symbol=BTCUSDT&interval=1h&limit=10" 200
test_route "GET" "/api/price?symbol=BTCUSDT" 200
test_route "GET" "/api/orderbook?symbol=BTCUSDT" 200
test_route "GET" "/api/trades?symbol=BTCUSDT" 200
test_route "GET" "/api/ticker" 200

# --- INDICATORS & INTELLIGENCE ---
echo -e "\n${YELLOW}[3/8] Intelligence Routes${NC}"
test_route "GET" "/api/indicators?symbol=BTCUSDT&interval=1h" 200
test_route "GET" "/api/dip-top?symbol=BTCUSDT" 200
test_route "GET" "/api/whales?symbol=BTCUSDT" 200
test_route "GET" "/api/funding?symbol=BTCUSDT" 200
test_route "GET" "/api/fear-greed" 200
test_route "GET" "/api/sentiment?symbol=BTCUSDT" 200

# --- BOT ROUTES ---
echo -e "\n${YELLOW}[4/8] Bot Routes${NC}"
test_route "GET" "/api/bot/status" 200
test_route "GET" "/api/bot/strategies" 200
test_json_field "/api/bot/status" "running"
test_json_field "/api/bot/status" "config"

# --- RISK ROUTES ---
echo -e "\n${YELLOW}[5/8] Risk Routes${NC}"
test_route "GET" "/api/risk/circuit-breakers" 200
test_route "GET" "/api/risk/portfolio" 200

# --- MACRO ROUTES ---
echo -e "\n${YELLOW}[6/8] Macro Routes${NC}"
test_route "GET" "/api/macro" 200
test_route "GET" "/api/macro/calendar" 200
test_route "GET" "/api/macro/geopolitical" 200

# --- PERFORMANCE & ALERTS ---
echo -e "\n${YELLOW}[7/8] Performance & Alert Routes${NC}"
test_route "GET" "/api/performance" 200
test_route "GET" "/api/performance/equity" 200
test_route "GET" "/api/performance/breakdown" 200
test_route "GET" "/api/performance/recommendations" 200
test_route "GET" "/api/alerts" 200
test_route "POST" "/api/alerts/test" 200
test_route "GET" "/api/execution/stats" 200

# --- SECURITY TESTS ---
echo -e "\n${YELLOW}[8/8] Security Tests${NC}"
test_route "GET" "/api/candles?symbol=../etc/passwd" 400
test_security "Webhook URL validation" "/api/alerts/webhook" '{"url":"javascript:alert(1)"}' "400"
test_security "Empty webhook rejected" "/api/alerts/webhook" '{"url":""}' "400"
test_route "GET" "/api/performance/export" 200
test_route "GET" "/api/alerts?limit=5&priority=CRITICAL" 200

# --- RESULTS ---
echo ""
echo -e "${YELLOW}========================================${NC}"
if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}ALL ${PASS}/${TOTAL} TESTS PASSED${NC}"
else
    echo -e "  ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC} out of ${TOTAL}"
fi
echo -e "${YELLOW}========================================${NC}"
echo ""

exit $FAIL
