#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/TraceX"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend/tracenetx-ui"
BACKEND_PORT=8002
FRONTEND_PORT=3003

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "[*] Shutting down TraceX..."
    [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "[1/2] Starting TraceX FastAPI backend on port ${BACKEND_PORT}..."
cd "$BACKEND_DIR"
python3 -m uvicorn main:app --reload --port ${BACKEND_PORT} > /tmp/tracex-backend.log 2>&1 &
BACKEND_PID=$!

echo "    Waiting for backend /docs to respond..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:${BACKEND_PORT}/docs" >/dev/null 2>&1; then
        echo "    Backend is ready (attempt ${i})."
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "[X] Backend process died. Check /tmp/tracex-backend.log"
        exit 1
    fi
    if [ "$i" -eq 60 ]; then
        echo "[X] Backend /docs never responded after 60s. Check /tmp/tracex-backend.log"
        exit 1
    fi
    sleep 1
done

echo "[2/2] Starting React frontend on port ${FRONTEND_PORT}..."
cd "$FRONTEND_DIR"
PORT=${FRONTEND_PORT} BROWSER=none npm start > /tmp/tracex-frontend.log 2>&1 &
FRONTEND_PID=$!

echo "    Waiting for frontend to respond..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
        echo "    Frontend is ready (attempt ${i})."
        break
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "[X] Frontend process died. Check /tmp/tracex-frontend.log"
        exit 1
    fi
    if [ "$i" -eq 60 ]; then
        echo "[!] Frontend didn't respond after 60s, opening anyway..."
        break
    fi
    sleep 1
done

echo "    Opening browser tabs..."
xdg-open "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 &
xdg-open "http://localhost:${BACKEND_PORT}/docs" >/dev/null 2>&1 &

echo ""
echo "============================================"
echo " TraceX (PS 26146) is up"
echo "   Backend /docs : http://localhost:${BACKEND_PORT}/docs"
echo "   Frontend      : http://localhost:${FRONTEND_PORT}"
echo " Logs: /tmp/tracex-backend.log, /tmp/tracex-frontend.log"
echo " Press Ctrl+C to stop backend + frontend"
echo "============================================"
echo ""

wait "$BACKEND_PID" "$FRONTEND_PID"
