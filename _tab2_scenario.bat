@echo off
title [2] SCENARIO BUILDER
color 0B
cd /d "%~dp0tradingview-mcp-jackson"
echo.
echo  Menunggu engine startup (15 detik)...
timeout /t 15 /nobreak >nul
echo.
node scenario_builder.mjs --watch
pause
