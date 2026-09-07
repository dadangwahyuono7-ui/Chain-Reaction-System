# Chain Reaction - start all background processes HIDDEN (no visible cmd windows).
# Only the Sultan Sniper Engine dashboard window stays visible.
# Logs go to *.log files next to each script since you can't see the console anymore.
#
# 2026-08-20: dashboard_web.py (the other "Chain Reaction" window, port 8765)
# REMOVED from here - Dadang: "gw pakai yang ini yang selain ini buang aja"
# (pointing at Sultan Sniper Engine). Was never wired to the public tunnel
# anyway (config.yml points at 8766/sultan_dashboard_server.py), so nothing
# else depended on it. File itself untouched in case it's ever wanted back -
# just not auto-launched anymore.
#
# 2026-08-11: TradingView + tv_poll.mjs REMOVED from here - Dadang: "trading
# view nya gak usah ikut nyala karena tv sudah tidak kita butuhkan" - MT5's
# own DD_CMP_Indicator (via the new Sultan export, see udp_listener.py's
# apply_mt5_overlay()) replaced Pine as the cold-start CMP source, so
# TradingView is no longer part of this pipeline at all. If you still want to
# glance at a TradingView chart manually, open it yourself - it's just not
# auto-launched or read by anything anymore.

$ErrorActionPreference = "Stop"
# 2026-08-20: $root used to be hardcoded "D:\PROJECT TRADING" - broke this
# entire script (venv path, bridge path, everything downstream) the instant
# Dadang cloned/copied the project to anywhere else (a different drive, a
# different folder name, a different PC). Resolved relative to the script's
# OWN location instead - this file lives in bookmap-bridge/, so root is one
# level up. Works no matter where the repo actually sits.
$bridge = $PSScriptRoot
$root = Split-Path -Parent $bridge
$venvPython = "$root\venv\Scripts\python.exe"
$venvPythonW = "$root\venv\Scripts\pythonw.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "!! Venv belum ada di $root\venv - jalanin setup.ps1 dulu (sekali doang, abis clone)." -ForegroundColor Yellow
    Start-Sleep -Seconds 8
    exit 1
}

Write-Host "============================================"
Write-Host "  CHAIN REACTION - START TRADING SESSION"
Write-Host "============================================"

# 2026-08-14: bersih-bersih dulu sebelum nyalain apapun.
#
# Kalau salah satu proses ini udah jalan (script dijalanin 2x, atau ada sisa
# dari sesi sebelumnya), instance baru GAGAL bind port:
#     OSError: [WinError 10048] Only one usage of each socket address...
# Thread server-nya mati diam-diam, window-nya tetep nongol tapi kosong, dan
# cloudflared kehilangan origin ("connection refused") - persis kejadian yang
# bikin dashboard mati sendiri. Menjadikan script ini idempoten (aman
# dijalanin berkali-kali) menghilangkan seluruh kelas masalah itu.
Write-Host "[0] Bersihin sisa proses lama..."
Get-CimInstance Win32_Process -Filter "name='python.exe' or name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'udp_listener|dashboard_web|sultan_dashboard_server|chart_engine_server|tunnel_gate|news_engine' } |
    ForEach-Object {
        Write-Host "    stop PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Get-Process -Name cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "    stop cloudflared PID $($_.Id)"
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3   # kasih waktu Windows lepasin port-nya
Write-Host ""

Write-Host "[1/3] UDP Listener - core engine (hidden, background)..."
Start-Process "$venvPython" -ArgumentList "udp_listener.py" -WorkingDirectory "$bridge" -WindowStyle Hidden -RedirectStandardOutput "$bridge\udp_listener.log" -RedirectStandardError "$bridge\udp_listener_err.log"
Start-Sleep -Seconds 3

Write-Host "[2/4] Sultan Sniper Engine Dashboard (window bakal nongol, maximized)..."
Start-Process "$venvPythonW" -ArgumentList "sultan_dashboard_server.py" -WorkingDirectory "$bridge" -RedirectStandardOutput "$bridge\sultan_dashboard.log" -RedirectStandardError "$bridge\sultan_dashboard_err.log"
Start-Sleep -Seconds 3

# 2026-08-25: this was never in here - it was added straight from a live
# session with `python news_engine.py` and nothing else ever restarted it.
# After a reboot it just silently never came back (found frozen at ~32h
# stale when Dadang asked why the News tab's AI wasn't analyzing anymore).
Write-Host "[2.5/5] Sultan Chart Engine MT5 Candles (port 8800, hidden)..."
Start-Process "$venvPython" -ArgumentList "chart_engine_server.py" -WorkingDirectory "$bridge" -WindowStyle Hidden -RedirectStandardOutput "$bridge\chart_engine.log" -RedirectStandardError "$bridge\chart_engine_err.log"
Start-Sleep -Seconds 2

Write-Host "[3/4] News & Catalyst engine (hidden, background)..."
Start-Process "$venvPython" -ArgumentList "news_engine.py" -WorkingDirectory "$bridge" -WindowStyle Hidden -RedirectStandardOutput "$bridge\news_engine.log" -RedirectStandardError "$bridge\news_engine_err.log"
Start-Sleep -Seconds 2

# 2026-08-14: akses dari luar rumah. Dadang: "web ini akan aktif ketika gw
# aktifin aja bukan on 24 jam, jadi masukin ke start gw supaya bareng jalan
# background." Jadi BUKAN Windows service - hidup/mati ngikut sesi trading.
#
# Tanpa password (keputusan Dadang: akun demo). tunnel_gate.py masih ada di
# folder ini kalau suatu saat mau dipasang lagi - arahin config.yml ke 8767
# terus jalanin gate-nya sebelum baris cloudflared di bawah.
Write-Host "[4/4] Cloudflare Tunnel -> https://trade.dadangchatai.com/dashboard ..."
# 2026-08-20: was a single hardcoded path - only ever worked if cloudflared
# happened to be installed at that exact spot. Check PATH first (works for
# any install method: winget, choco, manual), then the two common manual-
# install locations as a fallback.
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) {
    foreach ($candidate in @(
        "C:\Program Files (x86)\cloudflared\cloudflared.exe",
        "C:\Program Files\cloudflared\cloudflared.exe"
    )) {
        if (Test-Path $candidate) { $cloudflared = $candidate; break }
    }
}
$tunnelConfig = "$env:USERPROFILE\.cloudflared\config.yml"
if (-not $cloudflared) {
    Write-Host "    (cloudflared.exe gak ketemu - install dulu: winget install cloudflare.cloudflared)"
    Write-Host "    Akses dari luar rumah dilewati, tapi engine + dashboard lokal tetep jalan normal."
} elseif (-not (Test-Path $tunnelConfig)) {
    Write-Host "    (cloudflared ADA tapi belum ke-setup di PC ini - $tunnelConfig gak ketemu)"
    Write-Host "    Copy folder .cloudflared\ dari PC lama ke sini, atau jalanin 'cloudflared tunnel login' + config baru."
    Write-Host "    Akses dari luar rumah dilewati, tapi engine + dashboard lokal tetep jalan normal."
} else {
    Start-Process "$cloudflared" -ArgumentList "tunnel run" -WindowStyle Hidden -RedirectStandardOutput "$bridge\cloudflared.log" -RedirectStandardError "$bridge\cloudflared_err.log"
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Semua jalan di BACKGROUND - gak ada jendela"
Write-Host "  cmd nongol. Yang keliatan cuma 1 dashboard"
Write-Host "  window: 'Sultan Sniper Engine' (maximized)."
Write-Host ""
Write-Host "  Akses dari HP/luar rumah (tanpa login):"
Write-Host "    https://trade.dadangchatai.com/dashboard"
Write-Host ""
Write-Host "  Log kalau mau cek error:"
Write-Host "    $bridge\udp_listener.log"
Write-Host "    $bridge\sultan_dashboard.log"
Write-Host "    $bridge\news_engine.log"
Write-Host "    $bridge\cloudflared.log"
Write-Host ""
Write-Host "  MASIH MANUAL (gak bisa diotomatisin dari sini):"
Write-Host "  1. Buka MT5, login, drag DD_ChainReaction_MultiTF_EA_v2"
Write-Host "     ke chart XAUUSD M5"
Write-Host "  2. Buka Bookmap, connect Rithmic, load bookmap_addon.py"
Write-Host "     di chart GCZ6 (Code Editor -> Build -> Configure add-ons)"
Write-Host ""
Write-Host "  Mau matiin semua? Jalanin STOP_TRADING.bat"
Write-Host "============================================"
Start-Sleep -Seconds 6
