@echo off
title [1] SULTAN ENGINE
color 0A
cd /d "%~dp0"
echo.
echo  Starting Sultan Sniper Engine...
echo.
venv\Scripts\python.exe main.py
pause
