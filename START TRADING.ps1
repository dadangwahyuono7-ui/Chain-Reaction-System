# START TRADING — Chain Reaction v4.0 OVERLORD
# Commander Dadang Wahyuono

$WEB_DIR  = "D:\PROJECT TRADING\sultan-advisor"
$CF_EXE   = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$TV_CDP   = 9222
$WEB_PORT = 3002

function Port-Free { param($p)
  -not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

Clear-Host
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor DarkCyan
Write-Host "   CHAIN REACTION v4.0 OVERLORD — Commander Dadang Wahyuono  " -ForegroundColor Cyan
Write-Host "  ============================================================" -ForegroundColor DarkCyan
Write-Host ""

# ── [1] TradingView ───────────────────────────────────────────────────────────
Write-Host "  [1] TradingView CDP..." -ForegroundColor White

$cdpOk = $false
try {
  $r = Invoke-WebRequest -Uri "http://localhost:$TV_CDP/json/version" -TimeoutSec 2 -ErrorAction Stop
  if ($r.StatusCode -eq 200) { $cdpOk = $true }
} catch {}

if ($cdpOk) {
  Write-Host "      OK - TradingView sudah aktif" -ForegroundColor Green
} else {
  # Cari exe via AppxPackage
  $tvExe = $null
  try {
    $pkg = Get-AppxPackage -Name "*TradingView*" -ErrorAction Stop | Select-Object -First 1
    if ($pkg) {
      $candidate = Join-Path $pkg.InstallLocation "TradingView.exe"
      if (Test-Path $candidate) { $tvExe = $candidate }
    }
  } catch {}

  if ($tvExe) {
    Write-Host "      Launching TradingView dengan CDP flag..." -ForegroundColor Yellow
    # Kill existing TV dulu (kalau ada yang jalan tanpa CDP)
    Get-Process -Name "TradingView" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 1
    # Launch dengan CDP port — pakai Start-Process langsung ke exe
    Start-Process -FilePath $tvExe -ArgumentList "--remote-debugging-port=$TV_CDP"
    Write-Host "      Menunggu TradingView ready (20 detik)..." -ForegroundColor DarkYellow
    $waited = 0
    while ($waited -lt 20) {
      Start-Sleep 2; $waited += 2
      try {
        $r = Invoke-WebRequest -Uri "http://localhost:$TV_CDP/json/version" -TimeoutSec 1 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { Write-Host "      OK - CDP aktif!" -ForegroundColor Green; break }
      } catch {}
    }
    if ($waited -ge 20) {
      Write-Host "      WARN: CDP belum ready — TV sudah dibuka, sync manual nanti" -ForegroundColor DarkYellow
    }
  } else {
    Write-Host "      WARN: TradingView tidak ditemukan — buka manual" -ForegroundColor DarkYellow
  }
}
Write-Host ""

# ── [2] Sultan Advisor Web UI ─────────────────────────────────────────────────
Write-Host "  [2] Web UI port $WEB_PORT..." -ForegroundColor White

if (-not (Port-Free $WEB_PORT)) {
  Write-Host "      OK - Web UI sudah running" -ForegroundColor Green
} else {
  if (-not (Test-Path "$WEB_DIR\package.json")) {
    Write-Host "      ERROR: sultan-advisor tidak ditemukan!" -ForegroundColor Red
  } else {
    $hasBuild = Test-Path "$WEB_DIR\.next\BUILD_ID"
    if ($hasBuild) {
      Write-Host "      Starting production server..." -ForegroundColor Yellow
      Start-Process "cmd.exe" -ArgumentList "/k cd /d `"$WEB_DIR`" && npx next start -p $WEB_PORT" -WindowStyle Minimized
    } else {
      Write-Host "      Build belum ada — jalankan build dulu..." -ForegroundColor Yellow
      Start-Process "cmd.exe" -ArgumentList "/k cd /d `"$WEB_DIR`" && npx next build && npx next start -p $WEB_PORT" -WindowStyle Normal
    }

    Write-Host "      Menunggu server ready..." -ForegroundColor DarkYellow
    $w = 0
    while ($w -lt 60) {
      Start-Sleep 3; $w += 3
      if (-not (Port-Free $WEB_PORT)) { Write-Host "      OK - Server siap!" -ForegroundColor Green; break }
    }
    if ($w -ge 60) { Write-Host "      WARN: Server lambat, coba buka browser manual" -ForegroundColor DarkYellow }
  }
}
Write-Host ""

# ── [3] Cloudflare Tunnel ─────────────────────────────────────────────────────
Write-Host "  [3] Cloudflare Tunnel..." -ForegroundColor White
$cfRunning = Get-Process "cloudflared" -ErrorAction SilentlyContinue
if ($cfRunning) {
  Write-Host "      OK - Tunnel sudah jalan" -ForegroundColor Green
} elseif (Test-Path $CF_EXE) {
  Start-Process $CF_EXE -ArgumentList "tunnel","run" -WindowStyle Hidden
  Start-Sleep 3
  Write-Host "      OK - Tunnel started (trade.dadangchatai.com)" -ForegroundColor Green
} else {
  Write-Host "      SKIP - cloudflared tidak ada" -ForegroundColor DarkGray
}
Write-Host ""

# ── [4] Buka Browser ──────────────────────────────────────────────────────────
Write-Host "  [4] Buka browser dashboard..." -ForegroundColor White
Start-Process "http://localhost:$WEB_PORT/dashboard"
Write-Host ""

Write-Host "  ============================================================" -ForegroundColor DarkCyan
Write-Host "   SIAP! Dashboard: http://localhost:$WEB_PORT/dashboard       " -ForegroundColor Green
Write-Host "   Team akses  : https://trade.dadangchatai.com               " -ForegroundColor Cyan
Write-Host "  ============================================================" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  Tekan ENTER untuk tutup jendela ini..." -ForegroundColor DarkGray
Read-Host
