@echo off
setlocal enabledelayedexpansion
title SULTAN ADVISOR — CHAIN REACTION v4.0
color 0E
cls

echo.
echo  ====================================================
echo   ⚡ SULTAN ADVISOR — CHAIN REACTION v4.0 OVERLORD
echo   XAUUSD CFD  ^|  CMP/VR/CF  ^|  Daily Deploy
echo   Commander: Dadang Wahyuono
echo  ====================================================
echo.

:: ── PATH OTOMATIS (relative dari lokasi bat ini) ─────────────────────────────
set ROOT=%~dp0
set WEB_DIR=%ROOT%sultan-advisor
set QWEN_BAT=D:\AI-AGENT\start-qwen3-8b.bat
set QWEN_PORT=8080
set TV_CDP_PORT=9222
set WEB_PORT=3002

:: ─── [1/3] QWEN3-8B — hanya kalau ada (PC rumah) ────────────────────────────
echo  [1/3] AI Engine (Qwen3-8B :8080)...
netstat -ano 2>nul | findstr ":%QWEN_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        [OK] Qwen3 already running — LOCAL mode aktif
) else if exist "%QWEN_BAT%" (
  start "⚡ QWEN3-8B :8080" cmd /k ""%QWEN_BAT%""
  echo        [..] Qwen3 starting — tunggu ~30 detik
) else (
  echo        [--] Qwen3 tidak ada — otomatis pakai CLOUD Claude
)
echo.

:: ─── [2/3] TRADINGVIEW + CDP :9222 ──────────────────────────────────────────
echo  [2/3] TradingView CDP (:9222)...
netstat -ano 2>nul | findstr ":%TV_CDP_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        [OK] TradingView CDP sudah aktif
) else (
  for /f "usebackq tokens=*" %%i in (`powershell -nologo -noprofile -command "(Get-AppxPackage *TradingView* | Select-Object -First 1).InstallLocation" 2^>nul`) do set TV_LOC=%%i
  if defined TV_LOC (
    if exist "!TV_LOC!\TradingView.exe" (
      start "" "!TV_LOC!\TradingView.exe" --remote-debugging-port=%TV_CDP_PORT%
      echo        [OK] TradingView launching dengan CDP...
      timeout /t 4 /nobreak >nul
    ) else (
      echo        [!!] TradingView.exe tidak ketemu di !TV_LOC!
    )
  ) else (
    echo        [--] TradingView tidak diinstall — TV Sync tidak aktif
    echo             Buka TradingView manual kalau mau sync chart
  )
)
echo.

:: ─── [3/3] SULTAN ADVISOR WEB APP ───────────────────────────────────────────
echo  [3/3] Sultan Advisor Web (:3002)...
netstat -ano 2>nul | findstr ":%WEB_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel!==0 (
  echo        [OK] Web App sudah running di :%WEB_PORT%
) else (
  if exist "%WEB_DIR%\package.json" (
    start "🌐 SULTAN ADVISOR :3002" cmd /k "cd /d "%WEB_DIR%" && npm run dev -- --port %WEB_PORT%"
    echo        [..] Web App starting — tunggu ~10 detik
    timeout /t 10 /nobreak >nul
  ) else (
    echo        [!!] ERROR: sultan-advisor tidak ditemukan di %WEB_DIR%
    echo             Pastikan git clone sudah dilakukan!
    pause
    exit /b 1
  )
)
echo.

:: ─── READY ───────────────────────────────────────────────────────────────────
echo  ====================================================
echo.
echo   SULTAN ADVISOR SIAP!
echo.
echo   🌐 Dashboard  →  http://localhost:%WEB_PORT%/dashboard
echo   📡 TV CDP     →  localhost:%TV_CDP_PORT%
echo   🤖 AI Mode    →  %QWEN_PORT% (local) atau cloud auto
echo.
echo  ====================================================
echo.

start http://localhost:%WEB_PORT%/dashboard

echo  Browser dibuka. Selamat trading Commander! ⚡
echo.
pause
endlocal
