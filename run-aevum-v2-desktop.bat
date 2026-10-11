@echo off
title Aevum Desktop V2 Native App Launcher

echo =====================================================================
echo           Aevum Companion AI - Desktop V2 (Native App)
echo =====================================================================
echo.

cd /d "%~dp0"

echo [1/2] Starting Aevum Core Backend (FastAPI / Port 8000)...
start "Aevum_Backend" cmd /k "cd backend && uv run uvicorn app.main:app --port 8000 --host 127.0.0.1"

echo Waiting for Backend to initialize...
ping 127.0.0.1 -n 4 >nul

echo [2/2] Starting Desktop V2 Native Window (Tauri)...
start "Aevum_Frontend_V2" cmd /k "cd apps\desktop-v2 && pnpm tauri dev"

echo.
echo =====================================================================
echo    Aevum Desktop V2 (Tauri native app) is launching!
echo.
echo    - Backend API: http://127.0.0.1:8000
echo    - Backend Docs: http://127.0.0.1:8000/docs
echo.
echo    Keep the Aevum_Backend and Aevum_Frontend_V2 windows open.
echo    To stop all services, run stop-aevum.bat or close their windows.
echo =====================================================================
echo.
pause
