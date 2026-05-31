@echo off
setlocal enabledelayedexpansion
title Chain Reaction v4.0 OVERLORD - Commander Dadang
color 0B
chcp 65001 >nul 2>&1
cls

echo.
echo  ============================================================
echo   CHAIN REACTION v4.0 OVERLORD
echo   Commander Dadang Wahyuono  -  XAUUSD Daily Deploy
echo  ============================================================
echo.

set "TV_EXE=C:\Program Files\WindowsApps\TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj\TradingView.exe"
set "WEB_DIR=D:\PROJECT TRADING\sultan-advisor"
set "CF_EXE=C:\Program Files (x86)\cloudflared\cloudflared.exe"
set "WEB_PORT=3002"
set "TV_CDP=9222"

:: == [1] TradingView ===========================================================
echo  [1/3] TradingView dengan CDP port %TV_CDP%...
netstat -ano 2>nul | findstr ":%TV_CDP% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo        OK - TradingView CDP sudah aktif
    goto tv_done
)
if not exist "%TV_EXE%" (
    echo        WARN: TradingView.exe tidak ditemukan di path default
    echo        Coba buka TradingView manual
    goto tv_done
)
echo        Launching TradingView...
start "" "%TV_EXE%" --remote-debugging-port=%TV_CDP%
echo        Menunggu 8 detik...
timeout /t 8 /nobreak >nul
echo        OK - TradingView diluncurkan
:tv_done
echo.

:: == [2] Web UI ================================================================
echo  [2/3] Sultan Advisor Web UI port %WEB_PORT%...
netstat -ano 2>nul | findstr ":%WEB_PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo        OK - Web UI sudah running
    goto web_done
)
if not exist "%WEB_DIR%\package.json" (
    echo        ERROR: Folder sultan-advisor tidak ditemukan!
    echo        Path: %WEB_DIR%
    goto web_done
)
if exist "%WEB_DIR%\.next\BUILD_ID" (
    echo        Starting production server...
    start "SULTAN WEB UI" /MIN /D "%WEB_DIR%" cmd /k npx next start -p %WEB_PORT%
) else (
    echo        Build belum ada, menjalankan build dulu... (2-3 menit)
    start "SULTAN BUILD+START" /D "%WEB_DIR%" cmd /k npx next build ^&^& npx next start -p %WEB_PORT%
)
echo        Menunggu server siap (30 detik maks)...
set /a tries=0
:wait_web
timeout /t 3 /nobreak >nul
set /a tries+=1
netstat -ano 2>nul | findstr ":%WEB_PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo        OK - Web UI siap!
    goto web_done
)
if !tries! lss 10 goto wait_web
echo        Server lambat - browser akan dibuka, refresh kalau belum siap
:web_done
echo.

:: == [3] Cloudflare Tunnel =====================================================
echo  [3/3] Cloudflare Tunnel...
tasklist /FI "IMAGENAME eq cloudflared.exe" 2>nul | find /I "cloudflared.exe" >nul
if not errorlevel 1 (
    echo        OK - Tunnel sudah jalan
    goto cf_done
)
if not exist "%CF_EXE%" (
    echo        SKIP - cloudflared tidak ada
    goto cf_done
)
start "CLOUDFLARE" /MIN "%CF_EXE%" tunnel run
timeout /t 3 /nobreak >nul
echo        OK - Tunnel starting (trade.dadangchatai.com)
:cf_done
echo.

:: == Buka Browser ==============================================================
echo  Membuka dashboard di browser...
start "" "http://localhost:%WEB_PORT%/dashboard"
echo.
echo  ============================================================
echo   SELESAI!
echo   Dashboard : http://localhost:%WEB_PORT%/dashboard
echo   Team      : https://trade.dadangchatai.com
echo  ============================================================
echo.
echo  Jendela ini bisa ditutup. Selamat trading Commander!
echo.
pause
