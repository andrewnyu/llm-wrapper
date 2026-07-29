#!/usr/bin/env bash
set -euo pipefail

# Project-local production runner for VM usage.
# Usage:
#   bash start_server.sh start
#   bash start_server.sh stop
#   bash start_server.sh status
#   bash start_server.sh restart
# Optional env vars:
#   HOST=0.0.0.0 PORT=8000 WORKERS=3 TIMEOUT=120

ACTION="${1:-start}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
if [[ ! -d "${VENV_DIR}" ]]; then
  VENV_DIR="${PROJECT_DIR}/.venv"
fi
RUN_DIR="${PROJECT_DIR}/run"
LOG_DIR="${PROJECT_DIR}/logs"
PID_FILE="${RUN_DIR}/gunicorn.pid"
LOG_FILE="${LOG_DIR}/gunicorn.log"
APP_MODULE="${APP_MODULE:-api_key_wrapper.wsgi:application}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-3}"
TIMEOUT="${TIMEOUT:-120}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "No virtualenv found at ./venv or ./.venv"
  echo "Create one first:"
  echo "  python3 -m venv venv"
  echo "  source venv/bin/activate"
  echo "  pip install -U pip"
  echo "  pip install 'django>=5,<6' pyotp qrcode pillow requests google-genai psycopg2-binary gunicorn"
  exit 1
fi

source "${VENV_DIR}/bin/activate"
cd "${PROJECT_DIR}"

load_env_file() {
  local env_file="${PROJECT_DIR}/.env"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "${env_file}"
    set +a
  fi
}

is_running() {
  [[ -f "${PID_FILE}" ]] && pid_is_live_server "$(cat "${PID_FILE}")"
}

pid_is_live_server() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" >/dev/null 2>&1 || return 1

  local cmdline
  cmdline="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
  [[ "${cmdline}" == *"gunicorn"* ]] || return 1
  [[ "${cmdline}" == *"${APP_MODULE}"* ]] || return 1
  [[ "${cmdline}" == *"${PID_FILE}"* ]] || return 1
}

port_listener_pids() {
  local pids=""
  if command -v ss >/dev/null 2>&1; then
    pids="$(ss -ltnp "sport = :${PORT}" 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | sort -u)"
  elif command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | sort -u)"
  fi
  printf "%s\n" "${pids}" | sed '/^$/d'
}

live_server_listener_pids() {
  local pid
  for pid in $(port_listener_pids); do
    if pid_is_live_server "${pid}"; then
      echo "${pid}"
    fi
  done
}

stop_pid() {
  local pid="${1}"
  kill "${pid}" >/dev/null 2>&1 || true

  for _ in {1..10}; do
    if kill -0 "${pid}" >/dev/null 2>&1; then
      sleep 1
    else
      break
    fi
  done

  if kill -0 "${pid}" >/dev/null 2>&1; then
    echo "Process ${pid} still running, sending SIGKILL."
    kill -9 "${pid}" >/dev/null 2>&1 || true
  fi
}

stop_stale_listeners() {
  local pids
  pids="$(live_server_listener_pids)"
  [[ -n "${pids}" ]] || return 0

  echo "Found Gunicorn listener without a valid PID file on ${HOST}:${PORT}: ${pids}"
  local pid
  for pid in ${pids}; do
    echo "Stopping stale Gunicorn listener (PID ${pid})..."
    stop_pid "${pid}"
  done
  rm -f "${PID_FILE}"
}

require_production_env() {
  local debug="${DJANGO_DEBUG:-}"
  local hosts="${DJANGO_ALLOWED_HOSTS:-}"
  local hosts_compact="${hosts//,/}"
  hosts_compact="${hosts_compact//[[:space:]]/}"

  if [[ "${debug}" == "1" ]]; then
    echo "Refusing to start: DJANGO_DEBUG must be 0 in production."
    exit 1
  fi

  if [[ -z "${hosts_compact}" ]]; then
    echo "Refusing to start: DJANGO_ALLOWED_HOSTS must be set."
    exit 1
  fi
}

start_server() {
  if is_running; then
    echo "Server already running (PID $(cat "${PID_FILE}"))."
    exit 0
  fi

  stop_stale_listeners

  if ! python3 -m gunicorn --version >/dev/null 2>&1; then
    echo "gunicorn is not installed in this virtualenv."
    echo "Install it with:"
    echo "  pip install gunicorn"
    exit 1
  fi

  load_env_file
  require_production_env
  mkdir -p "${RUN_DIR}" "${LOG_DIR}"

  echo "Running migrations..."
  python3 manage.py migrate --noinput
  echo "Collecting static files..."
  python3 manage.py collectstatic --noinput

  echo "Starting Gunicorn in background on ${HOST}:${PORT}"
  nohup python3 -m gunicorn "${APP_MODULE}" \
    --bind "${HOST}:${PORT}" \
    --workers "${WORKERS}" \
    --timeout "${TIMEOUT}" \
    --pid "${PID_FILE}" \
    --access-logfile - \
    --error-logfile - \
    >>"${LOG_FILE}" 2>&1 &

  sleep 1
  if is_running; then
    echo "Started (PID $(cat "${PID_FILE}")). Logs: ${LOG_FILE}"
  else
    echo "Failed to start. Check logs: ${LOG_FILE}"
    exit 1
  fi
}

stop_server() {
  if ! is_running; then
    stop_stale_listeners
    if [[ -f "${PID_FILE}" ]]; then
      echo "Removing stale PID file."
    else
      echo "Server is not running."
    fi
    rm -f "${PID_FILE}"
    return 0
  fi

  local pid
  pid="$(cat "${PID_FILE}")"
  echo "Stopping server (PID ${pid})..."
  stop_pid "${pid}"

  rm -f "${PID_FILE}"
  echo "Stopped."
}

status_server() {
  if is_running; then
    echo "Server is running (PID $(cat "${PID_FILE}"))."
    echo "Logs: ${LOG_FILE}"
  elif [[ -n "$(live_server_listener_pids)" ]]; then
    echo "Server has a stale Gunicorn listener without a valid PID file."
    echo "Run: bash start_server.sh restart"
    echo "Logs: ${LOG_FILE}"
  else
    echo "Server is not running."
    rm -f "${PID_FILE}"
  fi
}

case "${ACTION}" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  status)
    status_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  *)
    echo "Unknown command: ${ACTION}"
    echo "Usage: bash start_server.sh {start|stop|status|restart}"
    exit 1
    ;;
esac
