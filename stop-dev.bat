@echo off
echo Stopping Aevum Development Environment...

echo Stopping terminal windows...
taskkill /F /T /FI "WINDOWTITLE eq Aevum_Backend*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Aevum_Frontend*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Aevum_Frontend_V2*" >nul 2>&1

echo Stopped.
