@echo off
title [3] SIGNAL ANNOTATOR
color 0E
cd /d "%~dp0tradingview-mcp-jackson"
echo.
echo  Menunggu engine startup (18 detik)...
timeout /t 18 /nobreak >nul
echo.
node signal_annotator.mjs --watch
pause
