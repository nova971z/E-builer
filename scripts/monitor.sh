#!/bin/bash
# Monitoring script for JARVIS Trading System
# Run via cron: */5 * * * * /path/to/scripts/monitor.sh
# Usage: ./scripts/monitor.sh

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT=5000
PID_FILE="$BASE_DIR/.jarvis.pid"
LOG_FILE="$BASE_DIR/monitor.log"
MAX_DB_SIZE_MB=500
MAX_DISK_PCT=90
MAX_MEM_PCT=90

ts() { date '+%Y-%m-%d %H:%M:%S'; }

alert() {
    echo "[$(ts)] ALERT: $1" >> "$LOG_FILE"
    # Attempt to send alert via the bot's own alert system
    curl -sf -X POST "http://localhost:${PORT}/api/alerts/test" \
        -H "Content-Type: application/json" > /dev/null 2>&1
}

ISSUES=0

# 1. Check if server process is running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "[$(ts)] Server not running (PID $PID dead) — restarting" >> "$LOG_FILE"
        alert "Server process died — restarting"
        cd "$BASE_DIR" && nohup python3 server.py > /dev/null 2>&1 &
        echo $! > "$PID_FILE"
        ISSUES=$((ISSUES + 1))
    fi
else
    # No PID file — check if anything is on the port
    if ! curl -sf "http://localhost:${PORT}/api/status" > /dev/null 2>&1; then
        echo "[$(ts)] No PID file and server not responding — starting" >> "$LOG_FILE"
        cd "$BASE_DIR" && nohup python3 server.py > /dev/null 2>&1 &
        echo $! > "$PID_FILE"
        ISSUES=$((ISSUES + 1))
    fi
fi

# 2. Check if server is responsive
if ! curl -sf "http://localhost:${PORT}/api/status" > /dev/null 2>&1; then
    echo "[$(ts)] Server not responding to /api/status" >> "$LOG_FILE"
    alert "Server not responding"
    ISSUES=$((ISSUES + 1))
fi

# 3. Check disk space
DISK_PCT=$(df "$BASE_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_PCT" -gt "$MAX_DISK_PCT" ] 2>/dev/null; then
    echo "[$(ts)] Disk usage high: ${DISK_PCT}%" >> "$LOG_FILE"
    alert "Disk usage: ${DISK_PCT}%"
    ISSUES=$((ISSUES + 1))
fi

# 4. Check memory usage
MEM_PCT=$(free | awk '/Mem:/ {printf "%d", $3/$2*100}')
if [ "$MEM_PCT" -gt "$MAX_MEM_PCT" ] 2>/dev/null; then
    echo "[$(ts)] Memory usage high: ${MEM_PCT}%" >> "$LOG_FILE"
    alert "Memory usage: ${MEM_PCT}%"
    ISSUES=$((ISSUES + 1))
fi

# 5. Check database size
if [ -f "$BASE_DIR/jarvis.db" ]; then
    DB_SIZE_MB=$(du -m "$BASE_DIR/jarvis.db" | cut -f1)
    if [ "$DB_SIZE_MB" -gt "$MAX_DB_SIZE_MB" ] 2>/dev/null; then
        echo "[$(ts)] Database large: ${DB_SIZE_MB}MB" >> "$LOG_FILE"
        alert "Database size: ${DB_SIZE_MB}MB"
        ISSUES=$((ISSUES + 1))
    fi
fi

# 6. Log status
if [ "$ISSUES" -eq 0 ]; then
    echo "[$(ts)] OK — server healthy, disk=${DISK_PCT}%, mem=${MEM_PCT}%" >> "$LOG_FILE"
fi

# Keep log file manageable
if [ -f "$LOG_FILE" ]; then
    tail -1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

exit $ISSUES
