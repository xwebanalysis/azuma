#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping containers..."
docker compose -f "$ROOT_DIR/docker-compose.yml" down --volumes --remove-orphans 2>/dev/null || true

echo "Removing local artifacts..."
rm -rf "$ROOT_DIR/backend/.venv"
rm -f "$ROOT_DIR/backend/azuma.db"
rm -rf "$ROOT_DIR/frontend/node_modules"
rm -rf "$ROOT_DIR/frontend/dist"

echo "Clean."
