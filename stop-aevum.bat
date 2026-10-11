@echo off
title Aevum Stopper
echo Stopping Aevum Development Environment...

taskkill /F /T /FI "WINDOWTITLE eq Aevum_Backend*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Aevum_Frontend*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Aevum_Frontend_V2*" >nul 2>&1

powershell -NoProfile -Command "Get-Process -Name 'uvicorn', 'node' -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*Aevum*' -or $_.CommandLine -like '*1422*' -or $_.CommandLine -like '*8000*' } | Stop-Process -Force" >nul 2>&1

echo Stopped all Aevum services.
ping 127.0.0.1 -n 2 >nul
exit /b 0
