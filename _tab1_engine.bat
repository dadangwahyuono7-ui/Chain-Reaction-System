@echo off
title [1] SULTAN ENGINE — Chain Reaction v4.0
color 0A
chcp 65001 >nul 2>&1
mode con: cols=220 lines=50
cd /d "%~dp0"
echo.
echo  Starting Sultan Sniper Engine...
echo.
venv\Scripts\python.exe main.py
pause
