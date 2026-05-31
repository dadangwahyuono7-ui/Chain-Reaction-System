@echo off
title SHARE WEB UI — Cloudflare Tunnel (akses team)
color 0D
chcp 65001 >nul 2>&1

set "CF=C:\Program Files (x86)\cloudflared\cloudflared.exe"

echo.
echo   ════════════════════════════════════════════════
echo   SHARE WEB UI — Cloudflare Tunnel
echo   ════════════════════════════════════════════════
echo   Bikin link publik HTTPS buat team akses web UI lo.
echo.
echo   Cara pakai:
echo     1. Pastikan START TRADING udah jalan (web UI port 3002)
echo     2. Tunggu link muncul di bawah:
echo          https://xxxx-xxxx.trycloudflare.com
echo     3. COPY link itu, share ke team (WA/Telegram)
echo     4. Team buka link, login pakai akun mereka
echo.
echo   ⚠  Window ini HARUS tetap kebuka selama team akses.
echo      Tutup window = tunnel mati = link gak bisa dibuka.
echo   ════════════════════════════════════════════════
echo.

:: Cek cloudflared ada
if not exist "%CF%" (
    echo   [ERROR] cloudflared tidak ketemu di:
    echo   %CF%
    echo   Install ulang: winget install Cloudflare.cloudflared
    pause
    exit /b 1
)

:: Cek web UI jalan dulu di port 3002
node -e "const h=require('http');const r=h.get('http://localhost:3002',res=>process.exit(0));r.on('error',()=>process.exit(1));r.setTimeout(2000,()=>process.exit(1));" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [WARN] Web UI di port 3002 BELUM jalan!
    echo   Jalankan "START TRADING" dulu, baru jalankan share ini.
    echo.
    pause
    exit /b 1
)

echo   Web UI OK di port 3002. Membuka tunnel...
echo   (link muncul beberapa detik lagi, cari baris trycloudflare.com)
echo.
"%CF%" tunnel --url http://localhost:3002
echo.
echo   Tunnel ditutup.
pause
