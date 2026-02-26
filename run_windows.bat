@echo off
setlocal enabledelayedexpansion

echo =====================================
echo       Starting SignSpeak (Windows)
echo =====================================
echo.

:: ---- Kill anything already on our ports ----
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: ---- Check Python ----
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python is not installed or not in PATH.
    echo.
    echo     1. Go to https://www.python.org/downloads/
    echo     2. Download Python 3.12
    echo     3. IMPORTANT: Check "Add Python to PATH" at the bottom of the installer!
    echo     4. Click "Install Now", then restart this script.
    echo.
    pause
    exit /b 1
)

:: ---- Check Node / npm ----
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Node.js is not installed.
    echo.
    echo     1. Go to https://nodejs.org/
    echo     2. Download the LTS version and install with default options.
    echo     3. Restart your computer, then run this script again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [OK] %%i
for /f "tokens=*" %%i in ('node --version 2^>^&1')   do echo [OK] Node %%i
echo.

:: ---- Virtual environment ----
echo [~] Setting up Python environment...
if not exist ".venv\" (
    echo     Creating virtual environment (one-time, takes ~10 seconds)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [X] Failed to create virtual environment.
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat

:: ---- Install Python dependencies ----
echo     Installing Python packages (first run may take several minutes)...
python -m pip install --upgrade pip --quiet
pip install -r backend\requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo [X] pip install failed. Check your internet connection and try again.
    pause
    exit /b 1
)
echo     [OK] Python packages ready.
echo.

:: ---- Start backend ----
echo [~] Starting backend server...
start "SignSpeak Backend" cmd /k "cd /d "%~dp0backend" && "%~dp0.venv\Scripts\python.exe" main.py"

:: ---- Poll until backend is actually answering ----
echo [~] Waiting for backend to be ready...
set READY=0
for /l %%i in (1,1,60) do (
    if !READY! == 0 (
        curl -s --max-time 1 http://localhost:8000/docs >nul 2>&1
        if !errorlevel! == 0 (
            set READY=1
            echo     [OK] Backend is up^^!
        ) else (
            echo     [%%i/60] Still starting...
            timeout /t 2 /nobreak >nul
        )
    )
)

if !READY! == 0 (
    echo.
    echo [X] Backend did not start after 120 seconds.
    echo     Check the "SignSpeak Backend" window for error messages.
    pause
    exit /b 1
)
echo.

:: ---- Frontend dependencies ----
echo [~] Setting up React frontend...
cd frontend
if not exist "node_modules\" (
    echo     Installing Node packages (one-time, takes ~30 seconds)...
    call npm install
    if %errorlevel% neq 0 (
        echo [X] npm install failed. Check your internet connection.
        cd ..
        pause
        exit /b 1
    )
)
echo     [OK] Node packages ready.
echo.

:: ---- Start frontend ----
echo [~] Starting frontend...
start "SignSpeak Frontend" cmd /k "npm run dev"

:: ---- Wait for Vite to be ready, then open browser ----
echo [~] Waiting for frontend to be ready...
set FREADY=0
for /l %%i in (1,1,20) do (
    if !FREADY! == 0 (
        curl -s --max-time 1 http://localhost:5173 >nul 2>&1
        if !errorlevel! == 0 (
            set FREADY=1
            echo     [OK] Frontend is up^^!
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)
cd ..

:: ---- Open browser ----
echo.
echo =====================================
echo   [OK] SignSpeak is running!
echo   Opening http://localhost:5173 ...
echo =====================================
echo.
echo   To stop: close the two black terminal windows.
echo.
start "" http://localhost:5173
pause
