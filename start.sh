#!/bin/bash

echo "========================================================"
echo "  Starting Orbius - Multi-Agent BRD Studio"
echo "========================================================"
echo ""

# Start Backend
echo "Starting Backend (FastAPI)..."
cd backend
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate
echo "Installing backend requirements..."
pip install -r requirements.txt
echo "Starting FastAPI Backend on http://127.0.0.1:8000 ..."
PYTHONPATH=. python -m uvicorn app.main:app --host 0.0.0.0 --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start Frontend
echo ""
echo "Starting Frontend (Vite)..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
echo "Starting Vite Frontend Dev Server on http://localhost:5173 ..."
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "========================================================"
echo "[!] Backend: http://127.0.0.1:8000"
echo "[!] Frontend: http://localhost:5173"
echo ""
echo "Both services are starting in the background."
echo "Press Ctrl+C to stop both services."
echo "========================================================"

# Trap Ctrl+C to stop both processes cleanly
trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' SIGINT SIGTERM

# Automatically open browser on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    (sleep 2 && open http://localhost:5173) &
fi

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
