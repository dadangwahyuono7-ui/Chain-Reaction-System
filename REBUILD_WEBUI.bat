@echo off
title Rebuild Sultan Advisor Web UI
color 0E
chcp 65001 >nul 2>&1
cd /d "%~dp0sultan-advisor"

echo.
echo   ════════════════════════════════════════════════
echo   REBUILD WEB UI — Production
echo   ════════════════════════════════════════════════
echo   Jalankan ini SETIAP habis ubah code dashboard,
echo   biar production build update.
echo.

call npm run build
if errorlevel 1 (
    echo.
    echo   [ERROR] Build gagal — production lama masih dipakai.
    pause
    exit /b 1
)

echo.
echo   ════════════════════════════════════════════════
echo   BUILD SUKSES
echo   ════════════════════════════════════════════════
echo   Restart Web UI biar pakai build baru:
echo   - Tutup window "SULTAN WEB UI"
echo   - Jalankan lagi _webui_prod.bat (atau reboot)
echo   ════════════════════════════════════════════════
echo.
pause
