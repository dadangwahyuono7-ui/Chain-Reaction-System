@echo off
setlocal enabledelayedexpansion
title CHAIN REACTION ADVISOR — Launcher
color 0E
chcp 65001 >nul 2>&1
cls

echo.
echo  ══════════════════════════════════════════════════════════
echo.
echo   ██████╗██╗  ██╗ █████╗ ██╗███╗  ██╗
echo   ██╔════╝██║  ██║██╔══██╗██║████╗ ██║
echo   ██║     ███████║███████║██║██╔██╗██║
echo   ██║     ██╔══██║██╔══██║██║██║╚████║
echo   ╚██████╗██║  ██║██║  ██║██║██║ ╚███║
echo    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚══╝
echo.
echo   CHAIN REACTION ADVISOR  ^|  v4.0 OVERLORD
echo   Commander: Dadang Wahyuono
echo   XAUUSD CFD  ^|  Daily Deploy  ^|  CMP/VR/CF
echo.
echo  ══════════════════════════════════════════════════════════
echo.

set QWEN_PORT=8080
set TV_CDP_PORT=9222
set WEB_PORT=3002
set QWEN_BAT=D:\AI-AGENT\start-qwen3-8b.bat

:: Direktori sultan-advisor adalah folder tempat bat ini berada
set WEB_DIR=%~dp0
:: Buang trailing backslash
if "%WEB_DIR:~-1%"=="\" set "WEB_DIR=%WEB_DIR:~0,-1%"

:: ─────────────────────────────────────────────────────────────────────────────
:: [1/3]  QWEN3-8B AI ENGINE
:: ─────────────────────────────────────────────────────────────────────────────
echo  [1/3] Checking AI Engine  (port :%QWEN_PORT%)...

netstat -ano 2>nul | findstr ":%QWEN_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        OK  Qwen3-8B sudah berjalan di :%QWEN_PORT%
) else (
  if exist "%QWEN_BAT%" (
    start "QWEN3-8B  :8080" cmd /k ""%QWEN_BAT%""
    echo        >>  Qwen3-8B starting... tunggu ~30 detik sampai model loaded
  ) else (
    echo        !!  WARN: %QWEN_BAT% tidak ditemukan — jalankan manual
  )
)
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: [2/3]  TRADINGVIEW + CDP
:: ─────────────────────────────────────────────────────────────────────────────
echo  [2/3] Checking TradingView CDP  (port :%TV_CDP_PORT%)...

netstat -ano 2>nul | findstr ":%TV_CDP_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        OK  TradingView CDP sudah aktif di :%TV_CDP_PORT%
) else (
  echo        >>  Mencari TradingView...

  :: Cari via AppxPackage (Windows Store / MSIX)
  set "TV_EXE="
  powershell -NoProfile -Command ^
    "(Get-AppxPackage -Name '*TradingView*' -ErrorAction SilentlyContinue | Select-Object -First 1).InstallLocation" ^
    > "%TEMP%\tv_path.txt" 2>nul
  for /f "usebackq tokens=*" %%i in ("%TEMP%\tv_path.txt") do (
    if exist "%%i\TradingView.exe" set "TV_EXE=%%i\TradingView.exe"
  )
  del "%TEMP%\tv_path.txt" >nul 2>&1

  :: Fallback — scan WindowsApps
  if "!TV_EXE!"=="" (
    for /f "tokens=*" %%i in ('dir /s /b "%PROGRAMFILES%\WindowsApps\TradingView*\TradingView.exe" 2^>nul') do (
      set "TV_EXE=%%i"
    )
  )

  :: Fallback — lokasi instalasi biasa
  if "!TV_EXE!"=="" if exist "%LOCALAPPDATA%\TradingView\TradingView.exe" (
    set "TV_EXE=%LOCALAPPDATA%\TradingView\TradingView.exe"
  )

  if "!TV_EXE!"=="" (
    echo        !!  WARN: TradingView tidak ditemukan.
    echo             Jalankan manual: TradingView.exe --remote-debugging-port=9222
    echo             Live price tick dan Sync TV tidak akan bekerja tanpa CDP.
  ) else (
    start "" "!TV_EXE!" --remote-debugging-port=%TV_CDP_PORT%
    echo        OK  TradingView launching dengan CDP :%TV_CDP_PORT%
    timeout /t 3 /nobreak >nul
  )
)
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: [3/3]  CHAIN REACTION ADVISOR — WEB APP
:: ─────────────────────────────────────────────────────────────────────────────
echo  [3/3] Checking Web App  (port :%WEB_PORT%)...

netstat -ano 2>nul | findstr ":%WEB_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        OK  Web App sudah berjalan di :%WEB_PORT%
) else (
  if exist "%WEB_DIR%\package.json" (
    start "CHAIN REACTION  WEB  :%WEB_PORT%" cmd /k ^
      "cd /d "%WEB_DIR%" && npm run dev -- --port %WEB_PORT%"
    echo        OK  Web App starting di :%WEB_PORT%
  ) else (
    echo        !!  ERROR: package.json tidak ditemukan di %WEB_DIR%
    pause
    exit /b 1
  )
)
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: READY
:: ─────────────────────────────────────────────────────────────────────────────
echo  ══════════════════════════════════════════════════════════
echo.
echo   CHAIN REACTION ADVISOR — AKTIF
echo.
echo     AI Engine   http://localhost:%QWEN_PORT%
echo     Web App     http://localhost:%WEB_PORT%
echo     TV CDP      localhost:%TV_CDP_PORT%
echo.
echo   NOTE: Tunggu ~30 detik sampai Qwen3-8B fully loaded.
echo         Lalu di Web App klik Sync dari TradingView untuk
echo         update data market terbaru.
echo.
echo   Untuk stop: tutup window QWEN3-8B dan CHAIN REACTION WEB.
echo.
echo  ══════════════════════════════════════════════════════════
echo.

timeout /t 8 /nobreak >nul
start http://localhost:%WEB_PORT%/dashboard

echo  Browser dibuka ke /dashboard
echo  Selamat trading, Commander Dadang!
echo.
pause
endlocal
