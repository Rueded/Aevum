@echo off
title Aevum Data Sync to Cloud
cd /d "%~dp0\backend"
echo =====================================================================
echo           Aevum 数据同步到云端 (本地电脑 -^> 手机云端)
echo =====================================================================
echo.
.venv\Scripts\python.exe sync_to_cloud.py
echo.
echo =====================================================================
pause
