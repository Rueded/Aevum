@echo off
title Aevum Desktop V2 Launcher

echo =====================================================================
echo                 Aevum Companion AI - Desktop V2
echo =====================================================================
echo.

cd /d "%~dp0"

echo [1/3] Starting Aevum Core Backend (FastAPI / Port 8000)...
start "Aevum_Backend" cmd /k "cd backend && uv run uvicorn app.main:app --port 8000 --host 0.0.0.0"

echo Waiting for Backend to initialize...
ping 127.0.0.1 -n 4 >nul

echo [2/3] Starting Desktop V2 Frontend (Vite / Port 1422)...
start "Aevum_Frontend_V2" cmd /k "cd apps\desktop-v2 && pnpm.cmd dev"

echo Waiting for Frontend to initialize...
ping 127.0.0.1 -n 4 >nul

echo [3/3] Opening Browser at http://localhost:1422 ...
start http://localhost:1422

for /f "tokens=*" %%i in ('uv run python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()" 2^>nul') do set LAN_IP=%%i
if "%LAN_IP%"=="" set LAN_IP=192.168.42.151

echo.
echo =====================================================================
echo    Aevum Desktop V2 started successfully!
echo.
echo    - 电脑桌面/浏览器: http://localhost:1422
echo    - 手机 Android 聊天: http://%LAN_IP%:1422
echo    - 后端 API 地址:    http://127.0.0.1:8000
echo    - 后端 API 文档:    http://127.0.0.1:8000/docs
echo.
echo    手机连接方式:
echo    1. 确保手机与电脑连接在同一个 Wi-Fi 局域网。
echo    2. 手机浏览器直接打开: http://%LAN_IP%:1422
echo       （会自动进入纯对话手机模式，无模型纯打字，响应飞快！）
echo    3. 可在手机 Chrome 菜单中选择【添加到主屏幕】，即成为独立 App！
echo =====================================================================
echo.
pause
