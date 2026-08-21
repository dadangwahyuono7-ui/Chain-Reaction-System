# Chain Reaction System - one-time setup after cloning to a new PC.
# Run this ONCE, then use bookmap-bridge\start_trading.ps1 every session.
#
# What this DOES automate: Python venv + dependencies.
# What this DOES NOT (and CANNOT) automate - these are manual, on purpose:
#   1. Installing MT5 itself, logging into your broker account.
#   2. Installing Bookmap itself, connecting to Rithmic.
#   3. Dragging DD_ChainReaction_MultiTF_EA_v2 onto an XAUUSD M5 chart in MT5.
#   4. Loading bookmap_addon.py into Bookmap's Code Editor (Build -> Configure
#      add-ons) on a GCZ6 chart.
#   5. Cloudflare Tunnel credentials (if you want the trade.dadangchatai.com
#      remote-access link) - these are account-specific and can never live in
#      this repo. Copy your .cloudflared\ folder from the old PC to
#      $env:USERPROFILE\.cloudflared\ here, or run "cloudflared tunnel login"
#      fresh and repoint the hostname. Everything ELSE (engine + local
#      dashboard) works fine without this step.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$bridge = "$root\bookmap-bridge"

Write-Host "============================================"
Write-Host "  CHAIN REACTION - SETUP"
Write-Host "============================================"

Write-Host "[1/3] Cek Python..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "!! Python gak ketemu di PATH. Install dulu dari python.org (centang 'Add to PATH' pas install), terus jalanin ulang setup.ps1 ini." -ForegroundColor Red
    exit 1
}
Write-Host "    $($py.Source)"

Write-Host "[2/3] Bikin venv + install dependency..."
$venvPython = "$root\venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    python -m venv "$root\venv"
}
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r "$bridge\requirements.txt"

Write-Host "[3/3] Cek Cloudflare Tunnel (opsional, cuma buat akses dari luar rumah)..."
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
$tunnelConfig = "$env:USERPROFILE\.cloudflared\config.yml"
if (-not $cloudflared) {
    Write-Host "    cloudflared belum ke-install - gak masalah, engine + dashboard lokal tetep jalan."
    Write-Host "    Mau akses dari luar rumah nanti? winget install cloudflare.cloudflared"
} elseif (-not (Test-Path $tunnelConfig)) {
    Write-Host "    cloudflared ADA tapi belum ke-setup di PC ini."
    Write-Host "    Copy folder .cloudflared\ dari PC lama ke $env:USERPROFILE\, atau 'cloudflared tunnel login' + config baru."
} else {
    Write-Host "    OK, tunnel config ketemu."
}

Write-Host ""
Write-Host "============================================"
Write-Host "  SETUP KODE SELESAI. Langkah manual (sekali doang per PC):"
Write-Host "  1. Install + login MT5, drag DD_ChainReaction_MultiTF_EA_v2"
Write-Host "     ke chart XAUUSD M5 (compile dulu di MetaEditor kalau .ex5"
Write-Host "     belum ada / mau versi terbaru)."
Write-Host "  2. Install Bookmap, connect Rithmic, load"
Write-Host "     bookmap-bridge\bookmap_addon.py di chart GCZ6 (Code Editor"
Write-Host "     -> Build -> Configure add-ons)."
Write-Host ""
Write-Host "  Abis itu, tiap mau trading: jalanin"
Write-Host "  bookmap-bridge\start_trading.ps1"
Write-Host "============================================"
