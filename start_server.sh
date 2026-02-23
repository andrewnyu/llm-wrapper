#!/usr/bin/env bash
set -euo pipefail

# Simple project-local runner for VM usage.
# Usage:
#   bash start_server.sh
# Optional env vars:
#   HOST=0.0.0.0 PORT=8000

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
if [[ ! -d "${VENV_DIR}" ]]; then
  VENV_DIR="${PROJECT_DIR}/.venv"
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "No virtualenv found at ./venv or ./.venv"
  echo "Create one first:"
  echo "  python3 -m venv venv"
  echo "  source venv/bin/activate"
  echo "  pip install -U pip"
  echo "  pip install 'django>=5,<6' pyotp qrcode pillow requests google-genai psycopg2-binary"
  exit 1
fi

source "${VENV_DIR}/bin/activate"
cd "${PROJECT_DIR}"

echo "Running migrations..."
python3 manage.py migrate

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "Starting Django dev server on ${HOST}:${PORT}"
echo "Press Ctrl+C to stop."
python3 manage.py runserver "${HOST}:${PORT}"
