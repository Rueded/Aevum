@echo off
echo Starting Aevum Development Environment...

cd /d "%~dp0"

echo [1/2] Starting Backend...
start "Aevum_Backend" cmd /k "cd backend && uv run uvicorn app.main:app --reload"

echo Waiting for backend to become reachable on port 8000...
:waitloop
powershell -Command "if((Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -WarningAction SilentlyContinue).TcpTestSucceeded) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    timeout /t 2 >nul
    goto waitloop
)

echo Backend is up!

echo [2/2] Starting Frontend...
start "Aevum_Frontend" cmd /k "cd apps\desktop && pnpm tauri dev"

echo Development environment started successfully.
echo Use stop-dev.bat to stop everything.
