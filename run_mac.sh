#!/bin/bash

echo "====================================="
echo "      Starting SignSpeak (Mac)       "
echo "====================================="

# Check requirements
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not installed."
    echo "Please download it from https://www.python.org/downloads/"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ Error: Node.js (npm) is required but not installed."
    echo "Please download it from https://nodejs.org/"
    exit 1
fi

# Setup and run backend
echo "⚙️ Setting up Python Backend..."
cd backend
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate
echo "Installing Python dependencies (this may take a moment on first run)..."
pip install -r requirements.txt -q
echo "Starting AI Backend Server..."
python3 main.py &
BACKEND_PID=$!
cd ..

# Setup and run frontend
echo "⚙️ Setting up React Frontend..."
cd frontend
echo "Installing Node dependencies..."
npm install > /dev/null 2>&1
echo "Starting Web Server..."
npm run dev -- --open &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ SignSpeak is running successfully!"
echo "🌐 Your browser should open automatically to http://localhost:5173"
echo ""
echo "🛑 TO QUIT: Press Ctrl+C in this terminal to stop both servers."
echo "====================================="

# Clean up processes on exit
trap "echo -e '\nStopping SignSpeak servers...'; kill $BACKEND_PID 2>/dev/null; kill $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

wait
