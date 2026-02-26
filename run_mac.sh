#!/bin/bash

echo "====================================="
echo "      Starting SignSpeak (Mac)       "
echo "====================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill any existing instances
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1

# Find Python 3.10-3.12
PYTHON=""
for v in python3.12 python3.11 python3.10 python3; do
    if command -v $v &> /dev/null; then
        VER=$($v -c 'import sys; print(sys.version_info.minor)' 2>/dev/null)
        MAJ=$($v -c 'import sys; print(sys.version_info.major)' 2>/dev/null)
        if [ -n "$VER" ] && [ "$MAJ" -eq 3 ] && [ "$VER" -ge 10 ] && [ "$VER" -le 12 ]; then
            PYTHON=$v
            break
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    echo "❌ Python 3.10, 3.11, or 3.12 is required."
    echo ""
    echo "How to install Python on Mac:"
    echo "  Option 1: Download from https://www.python.org/downloads/"
    echo "  Option 2: brew install python@3.12"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ Node.js is required but not installed."
    echo ""
    echo "How to install Node.js:"
    echo "  Download from https://nodejs.org/ (LTS version)"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "✓ Python: $($PYTHON --version)"
echo "✓ Node:   $(node --version)"
echo ""

# ---- Backend Setup ----
echo "⚙️  Setting up Python backend..."
VENV_DIR="$SCRIPT_DIR/.venv"

# Check if existing venv was built with a different Python version — if so, recreate it
if [ -d "$VENV_DIR" ]; then
    VENV_PYTHON="$VENV_DIR/bin/python"
    if [ -f "$VENV_PYTHON" ]; then
        VENV_VER=$("$VENV_PYTHON" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null)
        WANT_VER=$($PYTHON -c 'import sys; print(sys.version_info.minor)' 2>/dev/null)
        if [ "$VENV_VER" != "$WANT_VER" ]; then
            echo "   Recreating virtual environment (Python version changed: 3.$VENV_VER → 3.$WANT_VER)..."
            rm -rf "$VENV_DIR"
        fi
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "   Creating virtual environment (one-time setup)..."
    $PYTHON -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment."
        read -p "Press Enter to exit..."
        exit 1
    fi
fi
source "$VENV_DIR/bin/activate"

echo "   Installing Python packages (first run may take several minutes)..."
pip install --upgrade pip --quiet --quiet 2>/dev/null || true
pip install -r "$SCRIPT_DIR/backend/requirements.txt" --quiet --quiet
if [ $? -ne 0 ]; then
    echo "❌ pip install failed. Check your internet connection and try again."
    read -p "Press Enter to exit..."
    exit 1
fi
echo "   ✓ Python packages ready."
echo ""

# ---- Start backend ----
echo "   Starting backend server..."
cd "$SCRIPT_DIR/backend"
python main.py &
BACKEND_PID=$!
cd "$SCRIPT_DIR"

# ---- Poll until backend is actually answering ----
echo "⏳ Waiting for backend to be ready..."
READY=0
for i in $(seq 1 60); do
    if curl -s --max-time 1 http://localhost:8000/docs > /dev/null 2>&1; then
        READY=1
        echo "   ✓ Backend is up!"
        break
    fi
    echo "   [$i/60] Still starting..."
    sleep 2
done

if [ $READY -eq 0 ]; then
    echo ""
    echo "❌ Backend did not start after 120 seconds."
    echo "   Check the terminal output above for error messages."
    kill $BACKEND_PID 2>/dev/null
    read -p "Press Enter to exit..."
    exit 1
fi
echo ""

# ---- Frontend Setup ----
echo "⚙️  Setting up React frontend..."
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "   Installing Node packages (one-time setup, takes ~30 seconds)..."
    npm install --silent 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "❌ npm install failed. Check your internet connection."
        kill $BACKEND_PID 2>/dev/null
        read -p "Press Enter to exit..."
        exit 1
    fi
fi
echo "   ✓ Node packages ready."
echo ""

echo "   Starting frontend server..."
npm run dev &
FRONTEND_PID=$!

# ---- Poll until Vite is up, then open browser ----
echo "⏳ Waiting for frontend to be ready..."
for i in $(seq 1 20); do
    if curl -s --max-time 1 http://localhost:5173 > /dev/null 2>&1; then
        echo "   ✓ Frontend is up!"
        break
    fi
    sleep 1
done

cd "$SCRIPT_DIR"

# ---- Open browser ----
echo ""
echo "====================================="
echo "  ✅ SignSpeak is running!"
echo "  🌐 Opening http://localhost:5173"
echo "  🛑 Press Ctrl+C to stop"
echo "====================================="
echo ""
open "http://localhost:5173"

# Clean up both processes on exit
cleanup() {
    echo ""
    echo "Stopping SignSpeak..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    echo "Done. Goodbye!"
    exit 0
}
trap cleanup SIGINT SIGTERM

wait
