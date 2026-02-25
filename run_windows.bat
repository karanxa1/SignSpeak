@echo off
setlocal

echo =====================================
echo       Starting SignSpeak (Windows)       
echo =====================================

:: Kill any existing instances on the ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1

:: Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [X] Python is required but not installed.
    echo.
    echo How to install Python on Windows:
    echo   1. Go to https://www.python.org/downloads/
    echo   2. Download Python 3.12
    echo   3. IMPORTANT: Check "Add Python to PATH" at the bottom of the installer!
    echo   4. Click "Install Now"
    echo.
    pause
    exit /b 1
)

:: Check Node
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [X] Node.js is required but not installed.
    echo.
    echo How to install Node.js on Windows:
    echo   1. Go to https://nodejs.org/
    echo   2. Download the LTS version
    echo   3. Run the installer with default options
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo [OK] %%i
for /f "tokens=*" %%i in ('node --version') do echo [OK] Node %%i
echo.

:: ---- Backend Setup ----
echo [~] Setting up Python Backend...

if not exist ".venv\" (
    echo     Creating virtual environment (one-time setup)...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo     Installing dependencies...
pip install --upgrade pip -q 2>nul
pip install -r backend\requirements.txt -q 2>nul

echo     Starting backend server...
start "SignSpeak Backend" cmd /c "cd backend && python main.py"

:: Wait for backend
echo     Waiting for backend...
timeout /t 5 /nobreak >nul

:: ---- Frontend Setup ----
echo [~] Setting up React Frontend...
cd frontend
if not exist "node_modules\" (
    echo     Installing Node packages (one-time setup)...
    call npm install >nul 2>&1
)
echo     Starting frontend server...
start "SignSpeak Frontend" cmd /c "npm run dev -- --open"
cd ..

echo.
echo =====================================
echo   [OK] SignSpeak is running!
echo   Open: http://localhost:5173
echo   Close the two black windows to stop.
echo =====================================
echo.
pause
