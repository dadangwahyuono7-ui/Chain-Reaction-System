@echo off
title Sultan Sniper — Stop
chcp 65001 >nul 2>&1
color 0C

echo.
echo   ╔══════════════════════════════════════╗
echo   ║   SULTAN SNIPER — STOP ALL          ║
echo   ╚══════════════════════════════════════╝
echo.

:: Stop Python engine (main.py)
echo   Stopping Python engine...
taskkill /F /FI "WINDOWTITLE eq *SULTAN ENGINE*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq *Sultan Sniper Engine*" >nul 2>&1

:: Stop Node.js processes (scenario_builder + signal_annotator)
echo   Stopping Node.js scripts...
taskkill /F /FI "WINDOWTITLE eq *SCENARIO BUILDER*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq *SIGNAL ANNOTATOR*" >nul 2>&1

:: Fallback: kill by image name jika title tidak match
:: (hati-hati: ini kill SEMUA python dan node — uncomment jika perlu)
:: taskkill /F /IM python.exe >nul 2>&1
:: taskkill /F /IM node.exe >nul 2>&1

echo.
echo   Semua komponen dihentikan.
echo.
pause
