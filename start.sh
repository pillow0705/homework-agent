#!/usr/bin/env bash
# Start the Homework Agent server.
# Usage: ./start.sh [PORT]
# Default port: 5500

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-5500}"

# Verify ANTHROPIC_API_KEY
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    echo "[homework-agent] ERROR: ANTHROPIC_API_KEY is not set."
    echo "  Export it before starting: export ANTHROPIC_API_KEY=sk-..."
    exit 1
fi

echo "[homework-agent] Starting on port $PORT ..."
HOMEWORK_PORT="$PORT" python3 "$SCRIPT_DIR/server.py"
