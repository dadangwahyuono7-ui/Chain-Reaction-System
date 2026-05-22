@echo off
title Sultan Sniper — System Launcher
color 0A
chcp 65001 >nul 2>&1

echo.
echo   ╔═══════════════════════════════════════════════╗
echo   ║   SULTAN SNIPER ENGINE — SYSTEM LAUNCH       ║
echo   ║   Chain Reaction v4.0 OVERLORD               ║
echo   ╚═══════════════════════════════════════════════╝
echo.

:: ═════════════════════════════════════════════════
:: STEP 1 — LAUNCH TRADINGVIEW dengan CDP
:: ═════════════════════════════════════════════════
echo   [1/4] Meluncurkan TradingView dengan CDP port 9222...

:: Kill TradingView yang lagi jalan (supaya CDP pasti aktif)
taskkill /F /IM TradingView.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Cari lokasi TradingView.exe
set "TV_EXE="

:: 1. MSIX / Windows Store (paling umum di Windows 11)
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "(Get-AppxPackage -Name '*TradingView*' -ErrorAction SilentlyContinue).InstallLocation" 2^>nul') do (
    if exist "%%i\TradingView.exe" set "TV_EXE=%%i\TradingView.exe"
)

:: 2. WindowsApps folder
if "%TV_EXE%"=="" (
    for /f "tokens=*" %%i in ('dir /s /b "%PROGRAMFILES%\WindowsApps\TradingView*\TradingView.exe" 2^>nul') do set "TV_EXE=%%i"
)

:: 3. Lokasi install biasa
if "%TV_EXE%"=="" if exist "%LOCALAPPDATA%\TradingView\TradingView.exe" set "TV_EXE=%LOCALAPPDATA%\TradingView\TradingView.exe"
if "%TV_EXE%"=="" if exist "%PROGRAMFILES%\TradingView\TradingView.exe"  set "TV_EXE=%PROGRAMFILES%\TradingView\TradingView.exe"

:: Gagal kalau tidak ketemu
if "%TV_EXE%"=="" (
    echo.
    echo   [ERROR] TradingView.exe tidak ditemukan!
    echo   Pastikan TradingView Desktop sudah diinstall.
    echo.
    pause
    exit /b 1
)

echo         Ditemukan: %TV_EXE%
echo         Meluncurkan...
start "" "%TV_EXE%" --remote-debugging-port=9222

:: ─── Tunggu CDP siap (cek pakai Node.js, lebih reliable dari curl) ───
echo         Menunggu TradingView CDP ready...

:wait_cdp
timeout /t 3 /nobreak >nul
node -e "const h=require('http');const r=h.get('http://localhost:9222/json/version',res=>{if(res.statusCode===200)process.exit(0);else process.exit(1)});r.on('error',()=>process.exit(1));r.setTimeout(2000,()=>process.exit(1));" >nul 2>&1
if %errorlevel% neq 0 goto wait_cdp

echo         OK  CDP aktif!

:: ─── Tunggu chart load ───
echo         Menunggu chart load (20 detik)...
timeout /t 20 /nobreak >nul
echo         OK  TradingView siap.

:: ═════════════════════════════════════════════════
:: STEP 2 — LAUNCH SEMUA KOMPONEN
:: ═════════════════════════════════════════════════
echo.
echo   [2/4] Membuka komponen engine...
echo.

where wt.exe >nul 2>&1
if %errorlevel% equ 0 (

    :: ── Windows Terminal: semua dalam 1 window, 3 tabs ──────────────
    start "" wt.exe ^
        new-tab ^
            --title "SULTAN ENGINE" ^
            --colorScheme "One Half Dark" ^
            cmd /k "title [1] SULTAN ENGINE && cd /d %~dp0 && echo. && echo  Starting Sultan Sniper Engine... && echo. && venv\Scripts\python.exe main.py" ^
        ; new-tab ^
            --title "SCENARIO BUILDER" ^
            --colorScheme "Tango Dark" ^
            cmd /k "title [2] SCENARIO BUILDER && cd /d %~dp0tradingview-mcp-jackson && echo. && echo  Menunggu engine startup... && timeout /t 15 /nobreak >nul && echo. && node scenario_builder.mjs --watch" ^
        ; new-tab ^
            --title "SIGNAL ANNOTATOR" ^
            --colorScheme "Campbell" ^
            cmd /k "title [3] SIGNAL ANNOTATOR && cd /d %~dp0tradingview-mcp-jackson && echo. && echo  Menunggu engine startup... && timeout /t 18 /nobreak >nul && echo. && node signal_annotator.mjs --watch"

    echo   OK  Windows Terminal dibuka (3 tabs)

) else (

    :: ── Fallback: CMD window terpisah ───────────────────────────────
    echo   Windows Terminal tidak ada, buka 3 CMD window terpisah...

    start "SULTAN ENGINE"    cmd /k "title [1] SULTAN ENGINE    && cd /d %~dp0 && color 0A && venv\Scripts\python.exe main.py"
    timeout /t 15 /nobreak >nul
    start "SCENARIO BUILDER" cmd /k "title [2] SCENARIO BUILDER && cd /d %~dp0tradingview-mcp-jackson && color 0B && node scenario_builder.mjs --watch"
    timeout /t 2  /nobreak >nul
    start "SIGNAL ANNOTATOR" cmd /k "title [3] SIGNAL ANNOTATOR && cd /d %~dp0tradingview-mcp-jackson && color 0E && node signal_annotator.mjs --watch"

    echo   OK  3 CMD window dibuka

)

:: ═════════════════════════════════════════════════
:: DONE
:: ═════════════════════════════════════════════════
echo.
echo   ════════════════════════════════════════════════
echo   SISTEM AKTIF
echo   ════════════════════════════════════════════════
echo.
echo   TradingView       CDP port 9222
echo   Tab 1             main.py + MT5 (Sultan Engine)
echo   Tab 2             scenario_builder --watch (30s)
echo   Tab 3             signal_annotator --watch (10s)
echo.
echo   Stop semua: STOP_ENGINE.bat
echo   ════════════════════════════════════════════════
echo.
timeout /t 5 /nobreak >nul
exit
