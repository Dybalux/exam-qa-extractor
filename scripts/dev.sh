#!/usr/bin/env bash
set -euo pipefail

# Locate repo root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Virtualenv detection: prefer local .venv, fallback to uv or system uvicorn
if [ -x ".venv/bin/uvicorn" ]; then
    UVICORN=".venv/bin/uvicorn"
elif command -v uv >/dev/null 2>&1; then
    UVICORN="uv run uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
    UVICORN="uvicorn"
else
    echo "Error: uvicorn not found. Run 'source .venv/bin/activate' or install dependencies." >&2
    exit 1
fi

# Bun check
if ! command -v bun >/dev/null 2>&1; then
    echo "Error: 'bun' is not installed or not in PATH." >&2
    echo "Install bun from https://bun.sh" >&2
    exit 1
fi

# Ensure frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd frontend && bun install)
fi

echo "=================================================="
echo "  Starting Exam Study System in dev mode"
echo "  Backend:  http://localhost:8000 (Docs: /docs)"
echo "  Frontend: http://localhost:5173"
echo "  Press Ctrl+C to stop both servers"
echo "=================================================="

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "Stopping dev servers..."
    trap - SIGINT SIGTERM EXIT
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    echo "All processes stopped cleanly."
}

trap cleanup SIGINT SIGTERM EXIT

# Start backend
$UVICORN app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
(cd frontend && bun run dev) &
FRONTEND_PID=$!

# Wait for any child process to terminate
wait -n "$BACKEND_PID" "$FRONTEND_PID"
