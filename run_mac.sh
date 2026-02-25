#!/bin/bash

echo "====================================="
echo "      Starting SignSpeak (Mac)       "
echo "====================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill any existing instances
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null

# Find Python 3.10-3.12
PYTHON=""
for v in python3.12 python3.11 python3.10 python3; do
    if command -v $v &> /dev/null; then
        VER=$($v -c 'import sys; print(sys.version_info.minor)' 2>/dev/null)
        if [ -n "$VER" ] && [ "$VER" -ge 10 ] && [ "$VER" -le 12 ]; then
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
echo "⚙️  Setting up Python Backend..."
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "   Creating virtual environment (one-time setup)..."
    $PYTHON -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "   Installing dependencies..."
pip install --upgrade pip -q 2>/dev/null
pip install -r "$SCRIPT_DIR/backend/requirements.txt" -q 2>&1 | grep -v "already satisfied"

echo "   Starting backend server..."
cd "$SCRIPT_DIR/backend"
python main.py &
BACKEND_PID=$!

# Wait for backend to be ready
echo -n "   Waiting for backend"
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
        echo " ✓"
        break
    fi
    echo -n "."
    sleep 1
done

# ---- Frontend Setup ----
echo "⚙️  Setting up React Frontend..."
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "   Installing Node packages (one-time setup)..."
    npm install --silent 2>/dev/null
fi
echo "   Starting frontend server..."
npm run dev -- --open &
FRONTEND_PID=$!

sleep 2
echo ""
echo "====================================="
echo "  ✅ SignSpeak is running!"
echo "  🌐 Open: http://localhost:5173"
echo "  🛑 Press Ctrl+C to stop"
echo "====================================="
echo ""

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
