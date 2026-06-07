@echo off
REM Launcher engine — buka run_engine.bat DI DALAM Windows Terminal (render cantik).
REM Dipisah ke run_engine.bat biar gak ada quoting nested yang bikin gagal.
REM Fallback ke cmd biasa kalau wt.exe gak ada.

where wt.exe >nul 2>&1
if %errorlevel%==0 (
  start "" wt.exe --maximized --title "Chain Reaction Engine" -d "D:\PROJECT TRADING" cmd /k run_engine.bat
) else (
  start "" cmd /k run_engine.bat
)
exit /b
