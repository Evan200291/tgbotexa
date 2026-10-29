#!/usr/bin/env bash
# Exabyte Digital Store — VPS Safe Update Script
# Usage: ./scripts/update.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=========================================="
echo " Exabyte Digital Store — Updating Service "
echo "=========================================="

# 1. Automated database backup before touching containers
BACKUP_DIR="$ROOT_DIR/data/backups"
mkdir -p "$BACKUP_DIR"

if [ -f "$ROOT_DIR/data/exabyte.sqlite3" ]; then
    TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
    BACKUP_FILE="$BACKUP_DIR/exabyte_db_$TIMESTAMP.sqlite3"
    echo "Creating safety DB backup: $BACKUP_FILE"
    cp "$ROOT_DIR/data/exabyte.sqlite3" "$BACKUP_FILE"
    # Keep only the 30 most recent backups
    find "$BACKUP_DIR" -name "exabyte_db_*.sqlite3" -type f | sort -r | tail -n +31 | xargs -r rm -f
fi

# 2. Fetch latest changes from Git
echo "Pulling latest code from origin/main..."
git fetch origin main
git pull --ff-only origin main

# 3. Build and restart containers gracefully
echo "Rebuilding and restarting Docker containers..."
docker compose build --pull
docker compose up -d --remove-orphans

# 4. Wait for healthy response
echo "Verifying service health..."
sleep 5
docker compose ps

echo "Pruning dangling Docker images..."
docker image prune -f

echo "=========================================="
echo " Update completed successfully!           "
echo "=========================================="
