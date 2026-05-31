@echo off
title SULTAN WEB UI — Production (port 3002)
color 0B
chcp 65001 >nul 2>&1
cd /d "%~dp0sultan-advisor"

:: ─── Build kalau artifact belum ada (.next\BUILD_ID = tanda build sukses) ───
if not exist ".next\BUILD_ID" (
    echo.
    echo   Build production belum ada — menjalankan npm run build...
    echo   (sekali aja, agak lama. Setelah ini start langsung cepat.)
    echo.
    call npm run build
    if errorlevel 1 (
        echo.
        echo   [ERROR] Build gagal. Cek error di atas.
        pause
        exit /b 1
    )
)

echo.
echo   Starting production server di http://localhost:3002 ...
echo.
call npm run start -- -p 3002
pause
