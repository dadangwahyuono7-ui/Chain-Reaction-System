@echo off
title SOP AKAR v3.0 - Auto Watcher

echo =======================================
echo  SOP AKAR v3.0 - Auto Watcher
echo  by Dadang Wahyuono
echo =======================================
echo.

echo [1/2] Menutup TradingView yang ada...
taskkill /F /IM TradingView.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/2] Membuka TradingView dengan CDP port 9222...
start "" "C:\Program Files\WindowsApps\TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj\TradingView.exe" --remote-debugging-port=9222

echo Tunggu TradingView siap (20 detik)...
timeout /t 20 /nobreak >nul

echo.
echo [3/3] Starting Auto Watcher...
cd "%~dp0tradingview-mcp-jackson"
node auto_watcher.mjs

pause
