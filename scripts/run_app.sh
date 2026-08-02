#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${PORT:-8501}"

cd "$PROJECT_DIR"

if command -v pkill >/dev/null 2>&1; then
  pkill -f "streamlit run app.py" 2>/dev/null || true
else
  echo "pkill not available; skipping cleanup of previous Streamlit processes." >&2
fi

source .venv/bin/activate
exec streamlit run app.py --server.address=0.0.0.0 --server.port="$PORT"
