@echo off
setlocal enabledelayedexpansion
title CHAIN REACTION v4.0 OVERLORD — MASTER CONTROL
color 0E
cls

:: ══════════════════════════════════════════════════════════
::   CHAIN REACTION v4.0 OVERLORD
::   XAUUSD · Daily Deploy · CMP/VR/CF
::   Commander: Dadang Wahyuono
:: ══════════════════════════════════════════════════════════
echo.
echo  ██████╗██╗  ██╗ █████╗ ██╗███╗  ██╗
echo  ██╔════╝██║  ██║██╔══██╗██║████╗ ██║
echo  ██║     ███████║███████║██║██╔██╗██║
echo  ██║     ██╔══██║██╔══██║██║██║╚████║
echo  ╚██████╗██║  ██║██║  ██║██║██║ ╚███║
echo   ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚══╝
echo.
echo  ██████╗ ███████╗ █████╗  ██████╗████████╗██╗ ██████╗ ███╗  ██╗
echo  ██╔══██╗██╔════╝██╔══██╗██╔════╝╚══██╔══╝██║██╔═══██╗████╗ ██║
echo  ██████╔╝█████╗  ███████║██║        ██║   ██║██║   ██║██╔██╗██║
echo  ██╔══██╗██╔══╝  ██╔══██║██║        ██║   ██║██║   ██║██║╚████║
echo  ██║  ██║███████╗██║  ██║╚██████╗   ██║   ██║╚██████╔╝██║ ╚███║
echo  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚══╝
echo.
echo  ════════════════════════════════════════════════════════
echo   XAUUSD CFD  ^|  Daily Deploy System  ^|  v4.0 OVERLORD
echo   Commander: Dadang Wahyuono
echo  ════════════════════════════════════════════════════════
echo.

set QWEN_PORT=8080
set TV_CDP_PORT=9222
set WEB_PORT=3002
set QWEN_BAT=D:\AI-AGENT\start-qwen3-8b.bat
set TV_MCP_DIR=D:\PROJECT TRADING\NEW ENGINE\MCP TRADING VIEW\tradingview-mcp-jackson
set WEB_DIR=D:\PROJECT TRADING\sultan-advisor

:: ─── [1/4] QWEN3-8B AI ENGINE ────────────────────────────────────────────────
echo  [1/4] Checking AI Engine (Qwen3-8B : %QWEN_PORT%)...
netstat -ano 2>nul | findstr ":%QWEN_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        [OK] AI Engine already running at :%QWEN_PORT%
) else (
  echo        [..] Starting Qwen3-8B...
  if exist "%QWEN_BAT%" (
    start "⚡ QWEN3-8B  ENGINE  :8080" cmd /k ""%QWEN_BAT%""
    echo        [OK] Qwen3-8B starting — wait ~30s to fully load
  ) else (
    echo        [!!] WARN: %QWEN_BAT% tidak ditemukan
  )
)
echo.

:: ─── [2/4] TRADINGVIEW + CDP ─────────────────────────────────────────────────
echo  [2/4] Checking TradingView CDP (: %TV_CDP_PORT%)...
netstat -ano 2>nul | findstr ":%TV_CDP_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        [OK] TradingView CDP already active at :%TV_CDP_PORT%
) else (
  echo        [..] Launching TradingView with CDP...
  for /f "usebackq tokens=*" %%i in (`powershell -nologo -noprofile -command "(Get-AppxPackage *TradingView* | Select-Object -First 1).InstallLocation"`) do set TV_LOC=%%i
  if defined TV_LOC (
    if exist "!TV_LOC!\TradingView.exe" (
      start "" "!TV_LOC!\TradingView.exe" --remote-debugging-port=%TV_CDP_PORT%
      echo        [OK] TradingView launching with CDP :%TV_CDP_PORT%
      timeout /t 4 /nobreak >nul
    ) else (
      echo        [!!] WARN: TradingView.exe tidak ditemukan di !TV_LOC!
    )
  ) else (
    echo        [!!] WARN: TradingView AppxPackage tidak ditemukan
    echo             Jalankan TradingView manual dengan: --remote-debugging-port=%TV_CDP_PORT%
  )
)
echo.

:: ─── [3/4] LIVE DASHBOARD (auto_watcher) ─────────────────────────────────────
echo  [3/4] Starting Live CMD Dashboard...
if exist "%TV_MCP_DIR%\auto_watcher.mjs" (
  start "📊 CHAIN REACTION  LIVE DASHBOARD  ^| XAUUSD ^| CMP/VR/CF" cmd /k ^
    "mode con: cols=160 lines=45 && cd /d "%TV_MCP_DIR%" && echo. && echo  Starting Chain Reaction Live Dashboard... && echo. && node auto_watcher.mjs"
  echo        [OK] Live Dashboard launched
) else (
  echo        [!!] WARN: auto_watcher.mjs tidak ditemukan di %TV_MCP_DIR%
)
echo.

:: ─── [4/4] CHAIN REACTION WEB APP ────────────────────────────────────────────
echo  [4/4] Checking Web App (:%WEB_PORT%)...
netstat -ano 2>nul | findstr ":%WEB_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        [OK] Web App already running at :%WEB_PORT%
) else (
  echo        [..] Starting Chain Reaction Web App...
  if exist "%WEB_DIR%\package.json" (
    start "🌐 CHAIN REACTION  WEB APP  :%WEB_PORT%" cmd /k ^
      "cd /d "%WEB_DIR%" && npm run dev -- --port %WEB_PORT%"
    echo        [OK] Web App starting at :%WEB_PORT%
  ) else (
    echo        [!!] WARN: %WEB_DIR%\package.json tidak ditemukan
  )
)
echo.

:: ─── READY ───────────────────────────────────────────────────────────────────
echo  ════════════════════════════════════════════════════════
echo.
echo   CHAIN REACTION ADVISOR — AKTIF
echo.
echo   ⚡ AI Engine   http://localhost:%QWEN_PORT%
echo   🌐 Web App     http://localhost:%WEB_PORT%
echo   📡 TV CDP      localhost:%TV_CDP_PORT%
echo   📊 Watcher     CMD Window (auto_watcher.mjs)
echo.
echo   Untuk Python engine + MT5: jalankan START_ENGINE.bat
echo.
echo   NOTE: Tunggu ~30 detik sampai Qwen3-8B fully loaded
echo         Lalu di Web App klik ⚡ Sync dari TradingView
echo.
echo  ════════════════════════════════════════════════════════
echo.

timeout /t 8 /nobreak >nul
start http://localhost:%WEB_PORT%/dashboard

echo  Browser dibuka ke /dashboard. Selamat trading, Commander Dadang!
echo.
pause
endlocal
