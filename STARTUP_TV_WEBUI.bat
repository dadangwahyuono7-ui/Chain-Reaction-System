@echo off
title Sultan Advisor — Auto Startup (TV + Web UI)
color 0B
chcp 65001 >nul 2>&1

echo.
echo   ╔═══════════════════════════════════════════════╗
echo   ║   SULTAN ADVISOR — AUTO STARTUP              ║
echo   ║   TradingView CDP + Web UI (port 3002)       ║
echo   ╚═══════════════════════════════════════════════╝
echo.

:: ═════════════════════════════════════════════════
:: STEP 0 — SETTLE DELAY (singkat — cukup buat manual & cold boot)
:: ═════════════════════════════════════════════════
echo   [0/2] Settle 5 detik...
timeout /t 5 /nobreak >nul

:: ═════════════════════════════════════════════════
:: STEP 1 — LAUNCH TRADINGVIEW dengan CDP port 9222
:: ═════════════════════════════════════════════════
echo   [1/2] Meluncurkan TradingView dengan CDP port 9222...

:: Cek dulu apakah CDP udah aktif (TV udah jalan dengan flag bener)
node -e "const h=require('http');const r=h.get('http://localhost:9222/json/version',res=>process.exit(res.statusCode===200?0:1));r.on('error',()=>process.exit(1));r.setTimeout(1500,()=>process.exit(1));" >nul 2>&1
if %errorlevel% equ 0 (
    echo         CDP sudah aktif — TradingView skip launch.
    goto webui
)

:: Kill TV yang jalan tanpa CDP flag, lalu relaunch dengan flag
taskkill /F /IM TradingView.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: ─── Cari TradingView.exe ───
set "TV_EXE="

:: 1. MSIX / Windows Store
powershell -NoProfile -Command "(Get-AppxPackage -Name '*TradingView*' -ErrorAction SilentlyContinue).InstallLocation" > "%TEMP%\tv_path.txt" 2>nul
for /f "usebackq tokens=*" %%i in ("%TEMP%\tv_path.txt") do (
    if exist "%%i\TradingView.exe" set "TV_EXE=%%i\TradingView.exe"
)
del "%TEMP%\tv_path.txt" >nul 2>&1

:: 2. WindowsApps folder
if "%TV_EXE%"=="" (
    for /f "tokens=*" %%i in ('dir /s /b "%PROGRAMFILES%\WindowsApps\TradingView*\TradingView.exe" 2^>nul') do set "TV_EXE=%%i"
)

:: 3. Lokasi install biasa
if "%TV_EXE%"=="" if exist "%LOCALAPPDATA%\TradingView\TradingView.exe" set "TV_EXE=%LOCALAPPDATA%\TradingView\TradingView.exe"
if "%TV_EXE%"=="" if exist "%PROGRAMFILES%\TradingView\TradingView.exe"  set "TV_EXE=%PROGRAMFILES%\TradingView\TradingView.exe"

if "%TV_EXE%"=="" (
    echo.
    echo   [ERROR] TradingView.exe tidak ditemukan!
    echo   Web UI tetap dilanjutkan, tapi sync TV tidak akan jalan.
    echo.
    goto webui
)

echo         Ditemukan: %TV_EXE%
:: /MIN = launch minimized (jalan di background/taskbar, CDP tetap baca data)
start "" /MIN "%TV_EXE%" --remote-debugging-port=9222

:: ─── Tunggu CDP siap (max ~45 detik) ───
echo         Menunggu TradingView CDP ready...
set /a _tries=0
:wait_cdp
timeout /t 3 /nobreak >nul
set /a _tries+=1
node -e "const h=require('http');const r=h.get('http://localhost:9222/json/version',res=>process.exit(res.statusCode===200?0:1));r.on('error',()=>process.exit(1));r.setTimeout(2000,()=>process.exit(1));" >nul 2>&1
if %errorlevel% equ 0 goto cdp_ok
if %_tries% geq 15 (
    echo         [WARN] CDP belum ready setelah 45 detik — lanjut buka Web UI aja.
    goto webui
)
goto wait_cdp

:cdp_ok
echo         OK  CDP aktif!

:: ═════════════════════════════════════════════════
:: STEP 2 — LAUNCH WEB UI (port 3002)
:: ═════════════════════════════════════════════════
:webui
echo.
echo   [2/2] Meluncurkan Web UI (sultan-advisor port 3002)...

:: Cek apakah port 3002 udah dipakai (web UI udah jalan)
node -e "const h=require('http');const r=h.get('http://localhost:3002',res=>process.exit(0));r.on('error',()=>process.exit(1));r.setTimeout(1500,()=>process.exit(1));" >nul 2>&1
if %errorlevel% equ 0 (
    echo         Web UI sudah jalan di port 3002 — skip.
    goto done
)

:: Buka window terpisah biar server tetap jalan (PRODUCTION mode via launcher)
start "SULTAN WEB UI" cmd /k "%~dp0_webui_prod.bat"
echo         OK  Web UI (production) starting... buka http://localhost:3002

:: Optional: auto-buka browser ke dashboard setelah server siap
echo         Menunggu server siap lalu buka browser...
set /a _wtries=0
:wait_web
timeout /t 3 /nobreak >nul
set /a _wtries+=1
node -e "const h=require('http');const r=h.get('http://localhost:3002',res=>process.exit(0));r.on('error',()=>process.exit(1));r.setTimeout(2000,()=>process.exit(1));" >nul 2>&1
if %errorlevel% equ 0 (
    start "" "http://localhost:3002"
    goto done
)
if %_wtries% geq 20 goto done
goto wait_web

:done
:: ═════════════════════════════════════════════════
:: STEP 3 — CLOUDFLARE TUNNEL (link permanen team)
:: ═════════════════════════════════════════════════
echo.
echo   [3/3] Menjalankan Cloudflare Tunnel (trade.dadangchatai.com)...
set "CF=C:\Program Files (x86)\cloudflared\cloudflared.exe"
if exist "%CF%" (
    :: cek tunnel udah jalan belum (hindari double)
    tasklist /FI "IMAGENAME eq cloudflared.exe" 2>nul | find /I "cloudflared.exe" >nul
    if errorlevel 1 (
        start "CLOUDFLARE TUNNEL" /MIN "%CF%" tunnel run sultan-advisor
        echo         OK  Tunnel starting (minimized)... team: https://trade.dadangchatai.com
    ) else (
        echo         Tunnel udah jalan — skip.
    )
) else (
    echo         [WARN] cloudflared tidak ketemu — tunnel skip.
)

echo.
echo   ════════════════════════════════════════════════
echo   STARTUP SELESAI
echo   ════════════════════════════════════════════════
echo   TradingView   CDP port 9222
echo   Web UI        http://localhost:3002
echo   Team akses    https://trade.dadangchatai.com
echo   ════════════════════════════════════════════════
echo.
timeout /t 6 /nobreak >nul
exit
