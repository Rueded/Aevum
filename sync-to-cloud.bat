@echo off
chcp 65001 >nul
title Aevum Data Sync to Cloud
cd /d "%~dp0backend"
echo =====================================================================
echo           Aevum Cloud Data Sync (PC to Cloud)
echo =====================================================================
echo.
call .venv\Scripts\python.exe sync_to_cloud.py
echo.
echo =====================================================================
pause
