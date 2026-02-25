@echo off
setlocal
cd /d "%~dp0"

echo =====================================
echo       Starting SignSpeak (Windows)       
echo =====================================

:: Check requirements
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [X] Error: Python is required but not installed.
    echo Please download it from https://www.python.org/downloads/
    echo CRITICAL: Ensure you check the box "Add Python to PATH" during installation.
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [X] Error: Node.js (npm) is required but not installed.
    echo Please download it from https://nodejs.org/
    pause
    exit /b 1
)

:: Setup and run backend in a new window
echo [~] Setting up Python Backend...
cd backend
if not exist ".venv\" (
    echo Creating virtual environment...
    python -m venv .venv
)
echo Installing dependencies (this may take a moment on first run)...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
echo Starting AI Backend...
start "SignSpeak Backend Server" cmd /c "python main.py"
cd ..

:: Setup and run frontend in a new window
echo [~] Setting up React Frontend...
cd frontend
echo Installing Node dependencies...
call npm install >nul 2>&1
echo Starting Web Server...
start "SignSpeak Frontend" cmd /c "npm run dev -- --open"
cd ..

echo.
echo [!] SignSpeak is starting! Two new black windows have opened for the backend and frontend.
echo [!] Your browser should open automatically to http://localhost:5173
echo.
echo [X] TO QUIT: Just close the two new black windows when you are done.
echo =====================================
pause
