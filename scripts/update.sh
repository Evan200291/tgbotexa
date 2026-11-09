#!/usr/bin/env bash
# Exabyte Digital Store — VPS Safe Update Script
# Usage: ./scripts/update.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=========================================="
echo " Exabyte Digital Store — Updating Service "
echo "=========================================="

# 1. Automated database backup before updating
BACKUP_DIR="$ROOT_DIR/data/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

if [ -f "$ROOT_DIR/data/exabyte.sqlite3" ]; then
    BACKUP_FILE="$BACKUP_DIR/exabyte_db_$TIMESTAMP.sqlite3"
    echo "Creating safety DB backup (Bot 1): $BACKUP_FILE"
    cp "$ROOT_DIR/data/exabyte.sqlite3" "$BACKUP_FILE"
    find "$BACKUP_DIR" -name "exabyte_db_*.sqlite3" -type f | sort -r | tail -n +31 | xargs -r rm -f
fi

if [ -f "$ROOT_DIR/data_bot2/exabyte.sqlite3" ]; then
    BACKUP_DIR2="$ROOT_DIR/data_bot2/backups"
    mkdir -p "$BACKUP_DIR2"
    BACKUP_FILE2="$BACKUP_DIR2/exabyte_db_$TIMESTAMP.sqlite3"
    echo "Creating safety DB backup (Bot 2): $BACKUP_FILE2"
    cp "$ROOT_DIR/data_bot2/exabyte.sqlite3" "$BACKUP_FILE2"
    find "$BACKUP_DIR2" -name "exabyte_db_*.sqlite3" -type f | sort -r | tail -n +31 | xargs -r rm -f
fi

# 2. Fetch latest changes from Git
echo "Pulling latest code from origin/main..."
git fetch origin main
git pull --ff-only origin main

# 3. Restart services (PM2 or Docker)
if command -v pm2 >/dev/null 2>&1 && pm2 list | grep -q "exabyte-bot1\|outlineplus-bot2"; then
    echo "Updating Python dependencies and restarting PM2 processes..."
    ./.venv/bin/pip install -q -r requirements.txt
    pm2 restart ecosystem.config.cjs --update-env
    pm2 save
    pm2 status
else
    echo "Rebuilding and restarting Docker containers..."
    docker compose build --pull
    docker compose up -d --remove-orphans
    echo "Verifying service health..."
    sleep 5
    docker compose ps
    echo "Pruning dangling Docker images..."
    docker image prune -f
fi

echo "=========================================="
echo " Update completed successfully!           "
echo "=========================================="
