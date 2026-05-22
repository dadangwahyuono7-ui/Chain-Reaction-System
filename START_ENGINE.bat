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

:: ─────────────────────────────────────────────────
:: STEP 1: Cek / Launch TradingView dengan CDP
:: ─────────────────────────────────────────────────
echo   [1/4] TradingView CDP port 9222...
curl -s --max-time 2 http://localhost:9222/json/version >nul 2>&1
if %errorlevel% equ 0 (
    echo         OK  TradingView sudah aktif di port 9222
) else (
    echo         ... Meluncurkan TradingView dengan CDP...
    call "%~dp0tradingview-mcp-jackson\scripts\launch_tv_debug.bat" 9222
    if %errorlevel% neq 0 (
        echo         GAGAL launch TradingView. Buka manual dulu.
        pause
        exit /b 1
    )
)

:: ─────────────────────────────────────────────────
:: STEP 2: Launch semua dengan Windows Terminal tabs
:: ─────────────────────────────────────────────────
echo.
echo   [2/4] Membuka Windows Terminal dengan 3 tab...
echo.

:: Cek apakah Windows Terminal tersedia
where wt.exe >nul 2>&1
if %errorlevel% equ 0 (
    :: ── Windows Terminal: semua dalam 1 window dengan tabs ──
    start "" wt.exe ^
        --title "Sultan Sniper Engine" ^
        new-tab ^
            --title "SULTAN ENGINE" ^
            --colorScheme "One Half Dark" ^
            cmd /k "title [PYTHON] SULTAN SNIPER ENGINE && cd /d %~dp0 && echo. && echo  Memulai Sultan Sniper Engine... && echo. && venv\Scripts\python.exe main.py" ^
        ; new-tab ^
            --title "SCENARIO BUILDER" ^
            --colorScheme "Tango Dark" ^
            cmd /k "title [NODE] SCENARIO BUILDER && cd /d %~dp0tradingview-mcp-jackson && echo. && echo  Menunggu engine startup (12 detik)... && timeout /t 12 /nobreak >nul && echo. && node scenario_builder.mjs --watch" ^
        ; new-tab ^
            --title "SIGNAL ANNOTATOR" ^
            --colorScheme "Campbell" ^
            cmd /k "title [NODE] SIGNAL ANNOTATOR && cd /d %~dp0tradingview-mcp-jackson && echo. && echo  Menunggu engine startup (15 detik)... && timeout /t 15 /nobreak >nul && echo. && node signal_annotator.mjs --watch"

    echo   OK  Windows Terminal dibuka dengan 3 tab:
    echo       Tab 1 — SULTAN ENGINE     (Python main.py)
    echo       Tab 2 — SCENARIO BUILDER  (refresh 30s)
    echo       Tab 3 — SIGNAL ANNOTATOR  (poll 10s)
) else (
    :: ── Fallback: CMD window terpisah ──
    echo   Windows Terminal tidak ditemukan, buka CMD terpisah...

    start "SULTAN ENGINE" cmd /k "title [PYTHON] SULTAN SNIPER ENGINE && cd /d %~dp0 && color 0A && echo. && venv\Scripts\python.exe main.py"

    timeout /t 12 /nobreak >nul

    start "SCENARIO BUILDER" cmd /k "title [NODE] SCENARIO BUILDER && cd /d %~dp0tradingview-mcp-jackson && color 0B && node scenario_builder.mjs --watch"

    timeout /t 2 /nobreak >nul

    start "SIGNAL ANNOTATOR" cmd /k "title [NODE] SIGNAL ANNOTATOR && cd /d %~dp0tradingview-mcp-jackson && color 0E && node signal_annotator.mjs --watch"

    echo   OK  3 CMD window dibuka
)

:: ─────────────────────────────────────────────────
:: Done
:: ─────────────────────────────────────────────────
echo.
echo   ════════════════════════════════════════════════
echo   SEMUA KOMPONEN AKTIF
echo   ════════════════════════════════════════════════
echo.
echo   SULTAN ENGINE     main.py + MT5
echo   SCENARIO BUILDER  auto-gambar skenario 30s
echo   SIGNAL ANNOTATOR  auto-annotate signal 10s
echo.
echo   Untuk stop semua: jalankan STOP_ENGINE.bat
echo   ════════════════════════════════════════════════
echo.
timeout /t 5 /nobreak >nul
exit
