@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Chain Reaction Engine - DEMO Auto + Telegram
cd /d "D:\PROJECT TRADING"
venv\Scripts\python.exe main.py
echo.
echo  Engine berhenti. Tekan tombol apa saja untuk tutup window ini.
pause >nul
