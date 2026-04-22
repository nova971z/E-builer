#!/bin/bash
# Deployment script for JARVIS Trading System
# Usage: ./scripts/deploy.sh

set -e

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE_DIR"
BACKUP_DIR="$BASE_DIR/backups"
PID_FILE="$BASE_DIR/.jarvis.pid"
PORT=5000
MAX_WAIT=30

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[DEPLOY]${NC} $1"; }
fail() { echo -e "${RED}[DEPLOY]${NC} $1"; exit 1; }

# 1. Backup database
log "Backing up database..."
mkdir -p "$BACKUP_DIR"
if [ -f "$BASE_DIR/jarvis.db" ]; then
    STAMP=$(date +%Y%m%d_%H%M%S)
    cp "$BASE_DIR/jarvis.db" "$BACKUP_DIR/jarvis_pre_deploy_${STAMP}.db"
    ls -t "$BACKUP_DIR"/jarvis_*.db 2>/dev/null | tail -n +11 | xargs -r rm
    log "Database backed up"
else
    warn "No database found — fresh install"
fi

# 2. Pull latest code
log "Pulling latest code..."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    BEFORE=$(git rev-parse HEAD)
    git pull origin "$(git branch --show-current)" || warn "Git pull failed — using local code"
    AFTER=$(git rev-parse HEAD)
    if [ "$BEFORE" != "$AFTER" ]; then
        log "Updated: $(git log --oneline ${BEFORE}..${AFTER} | wc -l) new commits"
    else
        log "Already up to date"
    fi
else
    warn "Not a git repo — skipping pull"
fi

# 3. Install/update dependencies
log "Installing dependencies..."
pip3 install -q -r requirements.txt 2>/dev/null || warn "pip install had warnings"

# 4. Syntax check
log "Checking syntax..."
python3 -m py_compile server.py || fail "Syntax error in server.py — aborting deploy"

# 5. Graceful restart
log "Stopping existing server..."
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID"
        for i in $(seq 1 $MAX_WAIT); do
            kill -0 "$OLD_PID" 2>/dev/null || break
            sleep 1
        done
        kill -0 "$OLD_PID" 2>/dev/null && kill -9 "$OLD_PID" 2>/dev/null
    fi
    rm -f "$PID_FILE"
fi
# Kill anything else on the port
fuser -k ${PORT}/tcp 2>/dev/null || true
sleep 1

log "Starting server..."
nohup python3 server.py > /dev/null 2>&1 &
echo $! > "$PID_FILE"
log "Server PID: $(cat "$PID_FILE")"

# 6. Health check
log "Waiting for server..."
for i in $(seq 1 15); do
    if curl -sf "http://localhost:${PORT}/api/status" > /dev/null 2>&1; then
        log "Server is healthy"
        break
    fi
    if [ "$i" = "15" ]; then
        fail "Health check failed after 15s — rolling back"
        # Rollback: restore DB and restart old code
        if [ -f "$BACKUP_DIR/jarvis_pre_deploy_${STAMP}.db" ]; then
            cp "$BACKUP_DIR/jarvis_pre_deploy_${STAMP}.db" "$BASE_DIR/jarvis.db"
        fi
        if [ "$BEFORE" != "$AFTER" ] 2>/dev/null; then
            git checkout "$BEFORE" 2>/dev/null
        fi
        fail "Rollback complete — investigate manually"
    fi
    sleep 1
done

# 7. Quick route check
ROUTES_OK=0
for route in "/api/status" "/api/bot/status" "/api/performance" "/api/alerts"; do
    if curl -sf "http://localhost:${PORT}${route}" > /dev/null 2>&1; then
        ROUTES_OK=$((ROUTES_OK + 1))
    else
        warn "Route ${route} not responding"
    fi
done

log "Deploy complete — ${ROUTES_OK}/4 routes verified"
echo ""
