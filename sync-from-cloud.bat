@echo off
chcp 65001 >nul
title Aevum Data Download from Cloud
cd /d "%~dp0backend"
echo =====================================================================
echo           Aevum Cloud Data Download (Cloud to PC)
echo =====================================================================
echo.
call .venv\Scripts\python.exe sync_from_cloud.py
echo.
echo =====================================================================
pause
