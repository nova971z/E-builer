#!/usr/bin/env bash
set -euo pipefail

# J.A.R.V.I.S. Trading System — Database Backup
# Usage: ./scripts/backup.sh [--keep N]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_FILE="$PROJECT_DIR/jarvis.db"
BACKUP_DIR="$PROJECT_DIR/backups"
MAX_BACKUPS=10

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep) MAX_BACKUPS="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--keep N]"
            echo "  --keep N  Number of backups to retain (default: 10)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Verify database exists ---
if [[ ! -f "$DB_FILE" ]]; then
    echo "[JARVIS] No database found at $DB_FILE"
    echo "[JARVIS] Start the server first to create the database."
    exit 0
fi

# --- Create backup directory ---
mkdir -p "$BACKUP_DIR"

# --- Create backup with timestamp ---
timestamp=$(date +"%Y%m%d_%H%M%S")
backup_file="$BACKUP_DIR/jarvis_${timestamp}.db"

# Use SQLite .backup for safe copy (handles WAL mode)
if command -v sqlite3 &>/dev/null; then
    sqlite3 "$DB_FILE" ".backup '$backup_file'"
else
    cp "$DB_FILE" "$backup_file"
    # Also copy WAL/SHM if present
    [[ -f "${DB_FILE}-wal" ]] && cp "${DB_FILE}-wal" "${backup_file}-wal"
    [[ -f "${DB_FILE}-shm" ]] && cp "${DB_FILE}-shm" "${backup_file}-shm"
fi

# --- Verify backup ---
backup_size=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file" 2>/dev/null || echo "0")
if [[ "$backup_size" -eq 0 ]]; then
    echo "[JARVIS] ERROR: Backup file is empty!"
    rm -f "$backup_file"
    exit 1
fi

echo "[JARVIS] Backup created: $backup_file ($(numfmt --to=iec "$backup_size" 2>/dev/null || echo "${backup_size}B"))"

# --- Rotation: keep only N most recent ---
backup_count=$(find "$BACKUP_DIR" -name "jarvis_*.db" -type f | wc -l)
if [[ "$backup_count" -gt "$MAX_BACKUPS" ]]; then
    remove_count=$((backup_count - MAX_BACKUPS))
    echo "[JARVIS] Rotating: removing $remove_count old backup(s)..."
    find "$BACKUP_DIR" -name "jarvis_*.db" -type f | sort | head -n "$remove_count" | while read -r old; do
        rm -f "$old" "${old}-wal" "${old}-shm"
        echo "  Removed: $(basename "$old")"
    done
fi

# --- Summary ---
remaining=$(find "$BACKUP_DIR" -name "jarvis_*.db" -type f | wc -l)
echo "[JARVIS] Backups retained: $remaining / $MAX_BACKUPS"
