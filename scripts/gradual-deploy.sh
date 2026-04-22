#!/bin/bash
# Gradual Deployment Phases for JARVIS Autonomous Bot
# Usage: ./scripts/gradual-deploy.sh [phase]
# Phases: 1=observe, 2=paper, 3=micro, 4=gradual, 5=production

BASE="http://localhost:5000"
PHASE="${1:-status}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[DEPLOY]${NC} $1"; }

check_server() {
    if ! curl -sf "${BASE}/api/status" > /dev/null 2>&1; then
        echo -e "${RED}Server not running. Start it first: python3 server.py${NC}"
        exit 1
    fi
}

show_status() {
    check_server
    echo -e "\n${CYAN}=== JARVIS Deployment Status ===${NC}\n"

    STATUS=$(curl -s "${BASE}/api/bot/status")
    RUNNING=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('running',False))" 2>/dev/null)
    MODE=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('config',{}).get('mode','?'))" 2>/dev/null)
    TRADES=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('state',{}).get('trades_today',0))" 2>/dev/null)

    echo -e "  Bot running: ${RUNNING}"
    echo -e "  Mode:        ${MODE}"
    echo -e "  Trades today: ${TRADES}"

    PERF=$(curl -s "${BASE}/api/performance")
    TOTAL=$(echo "$PERF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_trades',0))" 2>/dev/null)
    WR=$(echo "$PERF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('win_rate',0))" 2>/dev/null)
    PF=$(echo "$PERF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('profit_factor',0))" 2>/dev/null)

    echo -e "  Total trades: ${TOTAL}"
    echo -e "  Win rate:     ${WR}%"
    echo -e "  Profit factor: ${PF}"

    echo ""
    echo -e "${CYAN}Deployment Phases:${NC}"
    echo "  1 - OBSERVATION  (bot logs signals, does NOT trade)"
    echo "  2 - PAPER        (paper trades, real signals)"
    echo "  3 - MICRO LIVE   (\$5-10 real, BTC/ETH only)"
    echo "  4 - GRADUAL      (\$25-50, more symbols)"
    echo "  5 - PRODUCTION   (full config)"
    echo ""
    echo "Usage: $0 [1-5]"
    echo ""
}

apply_config() {
    local config="$1"
    local desc="$2"
    log "Applying phase: ${desc}"
    RESULT=$(curl -sf -X POST "${BASE}/api/bot/config" \
        -H "Content-Type: application/json" \
        -d "$config" 2>/dev/null)
    if echo "$RESULT" | python3 -c "import sys,json; assert json.load(sys.stdin).get('success')" 2>/dev/null; then
        log "Config applied successfully"
    else
        warn "Config may not have applied fully: ${RESULT}"
    fi
}

case "$PHASE" in
    1|observe)
        check_server
        echo -e "\n${CYAN}=== Phase 1: OBSERVATION ===${NC}"
        echo "Bot will analyze markets and log signals WITHOUT trading."
        echo "Run for at least 48 hours to validate signal quality."
        echo ""
        read -p "Proceed? (y/N) " confirm
        [ "$confirm" = "y" ] || exit 0
        apply_config '{
            "mode": "paper",
            "scan_interval": 120,
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "max_concurrent_positions": 0,
            "min_signal_score": 300,
            "min_confidence": 99,
            "allowed_regimes": ["STRONG_BULL", "STRONG_BEAR"],
            "strategy": "auto",
            "risk_per_trade_pct": 0.0,
            "max_trades_per_day": 0,
            "leverage_max": 1
        }' "Phase 1: Observation"
        log "Phase 1 active — bot will log signals only (no trades)"
        log "Monitor via: curl ${BASE}/api/bot/status"
        ;;

    2|paper)
        check_server
        echo -e "\n${CYAN}=== Phase 2: PAPER TRADING ===${NC}"
        echo "Bot will paper trade with real signals."
        echo "Target: 100 trades, profit factor > 1.2 before advancing."
        echo ""
        read -p "Proceed? (y/N) " confirm
        [ "$confirm" = "y" ] || exit 0
        apply_config '{
            "mode": "paper",
            "scan_interval": 120,
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "max_concurrent_positions": 2,
            "min_signal_score": 180,
            "min_confidence": 70,
            "allowed_regimes": ["STRONG_BULL", "STRONG_BEAR"],
            "strategy": "auto",
            "risk_per_trade_pct": 1.0,
            "daily_loss_limit_pct": 3.0,
            "max_trades_per_day": 5,
            "cooldown_after_loss": 600,
            "leverage_max": 5
        }' "Phase 2: Paper Trading"
        log "Phase 2 active — paper trading"
        log "Advance to Phase 3 when: 100+ trades AND profit_factor > 1.2"
        ;;

    3|micro)
        check_server
        echo -e "\n${CYAN}=== Phase 3: MICRO LIVE ===${NC}"
        echo "Bot will trade REAL money: \$5-10 per trade, BTC/ETH only."
        echo ""
        warn "THIS USES REAL FUNDS. Ensure exchange is configured."
        echo ""
        read -p "Proceed? (y/N) " confirm
        [ "$confirm" = "y" ] || exit 0
        apply_config '{
            "mode": "micro_live",
            "scan_interval": 120,
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "max_concurrent_positions": 2,
            "min_signal_score": 200,
            "min_confidence": 75,
            "allowed_regimes": ["STRONG_BULL", "STRONG_BEAR"],
            "strategy": "auto",
            "risk_per_trade_pct": 0.5,
            "daily_loss_limit_pct": 2.0,
            "max_trades_per_day": 3,
            "cooldown_after_loss": 900,
            "leverage_max": 3
        }' "Phase 3: Micro Live"
        log "Phase 3 active — MICRO LIVE (\$5-10 real trades)"
        log "Advance to Phase 4 when: 50+ live trades validated"
        ;;

    4|gradual)
        check_server
        echo -e "\n${CYAN}=== Phase 4: GRADUAL ===${NC}"
        echo "Bot will trade \$25-50 per trade, more symbols."
        echo ""
        warn "INCREASED RISK. Review Phase 3 performance first."
        echo ""
        read -p "Proceed? (y/N) " confirm
        [ "$confirm" = "y" ] || exit 0
        apply_config '{
            "mode": "micro_live",
            "scan_interval": 90,
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "max_concurrent_positions": 3,
            "min_signal_score": 180,
            "min_confidence": 70,
            "allowed_regimes": ["STRONG_BULL", "WEAK_BULL", "STRONG_BEAR", "WEAK_BEAR"],
            "strategy": "auto",
            "risk_per_trade_pct": 1.5,
            "daily_loss_limit_pct": 3.0,
            "max_trades_per_day": 8,
            "cooldown_after_loss": 600,
            "leverage_max": 5
        }' "Phase 4: Gradual"
        log "Phase 4 active — gradual scale-up"
        ;;

    5|production)
        check_server
        echo -e "\n${CYAN}=== Phase 5: PRODUCTION ===${NC}"
        echo "Full production configuration."
        echo ""
        warn "FULL RISK. This should only be enabled after extensive validation."
        echo ""
        read -p "Type 'PRODUCTION' to confirm: " confirm
        [ "$confirm" = "PRODUCTION" ] || { echo "Aborted."; exit 0; }
        apply_config '{
            "mode": "live",
            "scan_interval": 60,
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"],
            "max_concurrent_positions": 5,
            "min_signal_score": 150,
            "min_confidence": 60,
            "allowed_regimes": ["STRONG_BULL", "WEAK_BULL", "STRONG_BEAR", "WEAK_BEAR", "RANGE"],
            "strategy": "auto",
            "risk_per_trade_pct": 2.0,
            "daily_loss_limit_pct": 5.0,
            "max_trades_per_day": 15,
            "cooldown_after_loss": 300,
            "leverage_max": 10
        }' "Phase 5: Production"
        log "Phase 5 active — FULL PRODUCTION"
        warn "Monitor closely for the first 24-48 hours"
        ;;

    status|*)
        show_status
        ;;
esac
