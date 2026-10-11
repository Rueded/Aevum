@chcp 65001 >nul
@echo off
setlocal enabledelayedexpansion
title Aevum Mobile Android Companion Launcher

echo =====================================================================
echo           Aevum Companion AI - 手机 Android 模式启动器
echo =====================================================================
echo.

cd /d "%~dp0"

set "LAN_IP="
for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -like '192.168.*' | Select-Object -ExpandProperty IPAddress -First 1)"`) do set "LAN_IP=%%a"

if "!LAN_IP!"=="" (
    for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -like '10.*' | Select-Object -ExpandProperty IPAddress -First 1)"`) do set "LAN_IP=%%a"
)

if "!LAN_IP!"=="" (
    set "LAN_IP=192.168.42.151"
)

echo [检测] 当前局域网 IP: !LAN_IP!
echo.
echo 正在检查后台服务状态...

curl -s http://127.0.0.1:8000/health >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [1/2] 正在启动后端服务: 端口 8000...
    start "Aevum_Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --host 0.0.0.0"
    ping 127.0.0.1 -n 4 >nul
) else (
    echo [1/2] 后端服务已在运行中: 端口 8000
)

curl -s http://127.0.0.1:1422 >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [2/2] 正在启动前端服务: 端口 1422...
    start "Aevum_Frontend_V2" cmd /k "cd /d %~dp0apps\desktop-v2 && npm run dev -- --host 0.0.0.0 --port 1422"
    ping 127.0.0.1 -n 4 >nul
) else (
    echo [2/2] 前端服务已在运行中: 端口 1422
)

echo.
echo =====================================================================
echo    🎉 Aevum 手机端就绪！
echo.
echo    📱 手机浏览器请直接访问:
echo       http://!LAN_IP!:1422?view=mobile
echo.
echo    使用说明:
echo    1. 确保你的手机和电脑连接在同一个 Wi-Fi 或手机热点下。
echo    2. 在手机浏览器地址栏输入上方链接。
echo    3. 手机端专为移动端打造，纯打字聊天，无 Live2D 模型开销，流畅极速！
echo    4. 点击右上角或在手机浏览器菜单选择【添加到主屏幕】即可当原生 App 使用。
echo =====================================================================
echo.
pause
