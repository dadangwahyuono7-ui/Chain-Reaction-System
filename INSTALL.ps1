# ============================================================================
#  SULTAN SNIPER ENGINE — INSTALL SCRIPT
#  Commander Dadang Wahyuono | Chain Reaction v4.0 OVERLORD
#
#  Jalankan SEKALI di PC/laptop baru. Script ini akan:
#    1. Cek & install Node.js, Git, cloudflared
#    2. Clone / update repo dari GitHub
#    3. Install dependencies sultan-advisor
#    4. Setup .env.local dari template
#    5. Build Next.js app
#    6. Setup Cloudflare tunnel
#    7. Buat shortcut START TRADING di Desktop
# ============================================================================

$ErrorActionPreference = "Stop"
$REPO_URL  = "https://github.com/dadangwahyuono-eng/Sultan-Sniper-Engine.git"
$INSTALL_DIR = "D:\PROJECT TRADING"
$WEB_DIR   = "$INSTALL_DIR\sultan-advisor"
$WEB_PORT  = 3002

Clear-Host
Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host "   SULTAN SNIPER ENGINE — SETUP INSTALLER                         " -ForegroundColor White
Write-Host "   Chain Reaction v4.0 OVERLORD — Commander Dadang Wahyuono       " -ForegroundColor DarkCyan
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host ""

# ── [1] Cek Node.js ──────────────────────────────────────────────────────────
Write-Host "  [1/7] Cek Node.js..." -ForegroundColor White
$nodeOk = $false
try {
    $nodeVer = node --version 2>$null
    if ($nodeVer -match "v(\d+)") {
        $major = [int]$Matches[1]
        if ($major -ge 18) {
            Write-Host "      OK - Node.js $nodeVer" -ForegroundColor Green
            $nodeOk = $true
        } else {
            Write-Host "      WARN - Node.js $nodeVer terlalu lama, butuh v18+" -ForegroundColor Yellow
        }
    }
} catch {}

if (-not $nodeOk) {
    Write-Host "      Node.js tidak ada — download dan install dulu dari:" -ForegroundColor Red
    Write-Host "      https://nodejs.org/en/download (pilih LTS)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "      Setelah install Node.js, jalankan script ini lagi." -ForegroundColor Yellow
    Start-Process "https://nodejs.org/en/download"
    Read-Host "  Tekan ENTER untuk keluar"
    exit 1
}
Write-Host ""

# ── [2] Cek Git ──────────────────────────────────────────────────────────────
Write-Host "  [2/7] Cek Git..." -ForegroundColor White
$gitOk = $false
try {
    $gitVer = git --version 2>$null
    Write-Host "      OK - $gitVer" -ForegroundColor Green
    $gitOk = $true
} catch {}

if (-not $gitOk) {
    Write-Host "      Git tidak ada — download dari:" -ForegroundColor Red
    Write-Host "      https://git-scm.com/download/win" -ForegroundColor Yellow
    Start-Process "https://git-scm.com/download/win"
    Read-Host "  Tekan ENTER untuk keluar"
    exit 1
}
Write-Host ""

# ── [3] Clone / Update repo ──────────────────────────────────────────────────
Write-Host "  [3/7] Repo..." -ForegroundColor White
if (Test-Path "$INSTALL_DIR\.git") {
    Write-Host "      Repo sudah ada — pull update terbaru..." -ForegroundColor Yellow
    Push-Location $INSTALL_DIR
    git pull origin (git rev-parse --abbrev-ref HEAD 2>$null) 2>&1 | Write-Host
    Pop-Location
    Write-Host "      OK - Repo updated" -ForegroundColor Green
} else {
    Write-Host "      Clone repo ke $INSTALL_DIR ..." -ForegroundColor Yellow
    $parent = Split-Path $INSTALL_DIR -Parent
    $folder = Split-Path $INSTALL_DIR -Leaf
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force $parent | Out-Null }
    git clone $REPO_URL "$INSTALL_DIR" 2>&1 | Write-Host
    Write-Host "      OK - Repo cloned" -ForegroundColor Green
}
Write-Host ""

# ── [4] Setup .env.local + Cloudflare config ─────────────────────────────────
Write-Host "  [4/7] Environment variables & config..." -ForegroundColor White
$envFile    = "$WEB_DIR\.env.local"
$envEx      = "$WEB_DIR\.env.example"
$cfUserDir  = "$env:USERPROFILE\.cloudflared"
$zipDesktop = "$env:USERPROFILE\Desktop\SultanConfig.zip"

# ── Auto-import dari SultanConfig.zip kalau ada di Desktop ───────────────────
if (Test-Path $zipDesktop) {
    Write-Host "      SultanConfig.zip ditemukan di Desktop — import otomatis..." -ForegroundColor Yellow
    $tmpExtract = "$env:TEMP\SultanConfigImport"
    if (Test-Path $tmpExtract) { Remove-Item $tmpExtract -Recurse -Force }
    Expand-Archive -Path $zipDesktop -DestinationPath $tmpExtract -Force

    # Import .env.local
    if (Test-Path "$tmpExtract\.env.local") {
        Copy-Item "$tmpExtract\.env.local" $envFile -Force
        Write-Host "      OK - .env.local di-import dari zip" -ForegroundColor Green
    }

    # Import .cloudflared credentials
    $cfSrc = "$tmpExtract\cloudflared"
    if ((Test-Path $cfSrc) -and (Get-ChildItem $cfSrc).Count -gt 0) {
        if (-not (Test-Path $cfUserDir)) { New-Item -ItemType Directory $cfUserDir | Out-Null }
        Copy-Item "$cfSrc\*" $cfUserDir -Recurse -Force
        Write-Host "      OK - Cloudflare tunnel config di-import dari zip" -ForegroundColor Green
    }

    Remove-Item $tmpExtract -Recurse -Force
    Write-Host "      Semua config dari PC lama berhasil di-import!" -ForegroundColor Green

} elseif (Test-Path $envFile) {
    Write-Host "      OK - .env.local sudah ada" -ForegroundColor Green

} elseif (Test-Path $envEx) {
    # Tidak ada zip, tidak ada .env.local — minta isi manual
    Copy-Item $envEx $envFile
    Write-Host ""
    Write-Host "  =================================================================" -ForegroundColor Yellow
    Write-Host "   PERLU DIISI MANUAL: sultan-advisor\.env.local               " -ForegroundColor Yellow
    Write-Host "  =================================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  TIP: Jalankan EXPORT_CONFIG.ps1 di PC lama dulu untuk export" -ForegroundColor Cyan
    Write-Host "       semua config otomatis — tidak perlu isi manual!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Atau isi manual sekarang:" -ForegroundColor White
    Write-Host "    BLUEPACK_API_KEY   = API key dari https://ai.bluepack.my.id" -ForegroundColor White
    Write-Host "    BETTER_AUTH_SECRET = string random panjang" -ForegroundColor White
    Write-Host "    TELEGRAM_BOT_TOKEN = dari @BotFather (opsional)" -ForegroundColor White
    Write-Host "    TELEGRAM_CHAT_ID   = chat ID kamu (opsional)" -ForegroundColor White
    Write-Host ""
    Start-Process "notepad.exe" $envFile
    Read-Host "  Tekan ENTER setelah selesai isi .env.local"
} else {
    Write-Host "      ERROR: .env.example tidak ditemukan!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ── [5] Install dependencies & Build ─────────────────────────────────────────
Write-Host "  [5/7] Install & Build sultan-advisor..." -ForegroundColor White
Push-Location $WEB_DIR

Write-Host "      npm install --include=dev (bisa 2-5 menit)..." -ForegroundColor Yellow
npm install --include=dev 2>&1 | Select-Object -Last 5 | Write-Host

Write-Host "      npx next build (bisa 2-3 menit)..." -ForegroundColor Yellow
npx next build 2>&1 | Select-Object -Last 8 | Write-Host

if (Test-Path ".next\BUILD_ID") {
    Write-Host "      OK - Build sukses!" -ForegroundColor Green
} else {
    Write-Host "      ERROR - Build gagal. Cek log di atas." -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host ""

# ── [6] Cloudflare Tunnel ─────────────────────────────────────────────────────
Write-Host "  [6/7] Cloudflare Tunnel (trade.dadangchatai.com)..." -ForegroundColor White
$CF_EXE  = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$CF_DIR  = "C:\Program Files (x86)\cloudflared"
$CF_URL  = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi"

if (Test-Path $CF_EXE) {
    Write-Host "      OK - cloudflared sudah ada" -ForegroundColor Green
} else {
    Write-Host "      cloudflared tidak ada — download installer..." -ForegroundColor Yellow
    $msiPath = "$env:TEMP\cloudflared.msi"
    try {
        Invoke-WebRequest -Uri $CF_URL -OutFile $msiPath -UseBasicParsing
        Write-Host "      Install cloudflared..." -ForegroundColor Yellow
        Start-Process msiexec -ArgumentList "/i `"$msiPath`" /quiet" -Wait
        if (Test-Path $CF_EXE) {
            Write-Host "      OK - cloudflared installed" -ForegroundColor Green
        } else {
            Write-Host "      WARN - cloudflared install mungkin butuh restart" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "      WARN - Gagal auto-download cloudflared. Manual: https://developers.cloudflare.com/cloudflared/install-and-setup/installation" -ForegroundColor Yellow
    }
}

# Cek apakah tunnel sudah ada (bisa dari zip import atau setup sebelumnya)
$cfCredsFile = Get-ChildItem "$env:USERPROFILE\.cloudflared\*.json" -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $cfCredsFile) {
    Write-Host ""
    Write-Host "  =================================================================" -ForegroundColor Yellow
    Write-Host "   SETUP CLOUDFLARE TUNNEL (sekali saja)                          " -ForegroundColor Yellow
    Write-Host "  =================================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Pilih salah satu cara:" -ForegroundColor White
    Write-Host ""
    Write-Host "  CARA 1 — Copy credentials dari PC lama (LEBIH MUDAH):" -ForegroundColor Cyan
    Write-Host "    Di PC lama, copy seluruh folder ini ke laptop:" -ForegroundColor White
    Write-Host "    $env:USERPROFILE\.cloudflared\" -ForegroundColor Yellow
    Write-Host "    (isinya: cert.pem, config.yml, dan file *.json tunnel credentials)" -ForegroundColor White
    Write-Host ""
    Write-Host "  CARA 2 — Setup tunnel baru di laptop:" -ForegroundColor Cyan
    Write-Host "    1. Buka Command Prompt sebagai Admin" -ForegroundColor White
    Write-Host "    2. Jalankan: cloudflared tunnel login" -ForegroundColor Yellow
    Write-Host "    3. Browser akan terbuka → login Cloudflare → authorize" -ForegroundColor White
    Write-Host "    4. Jalankan: cloudflared tunnel create sultan-laptop" -ForegroundColor Yellow
    Write-Host "    5. Buat route: cloudflared tunnel route dns sultan-laptop trade.dadangchatai.com" -ForegroundColor Yellow
    Write-Host "       (jika domain sudah dipakai PC lama, buat subdomain berbeda)" -ForegroundColor White
    Write-Host ""
    Read-Host "  Tekan ENTER setelah setup tunnel selesai (atau skip untuk sekarang)"
} else {
    Write-Host "      OK - Cloudflare credentials sudah ada" -ForegroundColor Green
}
Write-Host ""

# ── [7] Desktop Shortcut ──────────────────────────────────────────────────────
Write-Host "  [7/7] Shortcut Desktop..." -ForegroundColor White
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\START TRADING.lnk"
$ps1Path = "$INSTALL_DIR\START TRADING.ps1"

if (Test-Path $shortcutPath) {
    Write-Host "      OK - Shortcut sudah ada" -ForegroundColor Green
} elseif (Test-Path $ps1Path) {
    $wshell = New-Object -ComObject WScript.Shell
    $lnk = $wshell.CreateShortcut($shortcutPath)
    $lnk.TargetPath = "powershell.exe"
    $lnk.Arguments  = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1Path`""
    $lnk.WorkingDirectory = $INSTALL_DIR
    $lnk.IconLocation = "powershell.exe,0"
    $lnk.Description = "Start Chain Reaction Trading System"
    $lnk.Save()
    Write-Host "      OK - Shortcut dibuat di Desktop" -ForegroundColor Green
} else {
    Write-Host "      WARN - START TRADING.ps1 tidak ditemukan, shortcut tidak dibuat" -ForegroundColor Yellow
}
Write-Host ""

# ── SELESAI ───────────────────────────────────────────────────────────────────
Write-Host "  =================================================================" -ForegroundColor Green
Write-Host "   SETUP SELESAI!                                                  " -ForegroundColor Green
Write-Host "  =================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Cara start trading:" -ForegroundColor White
Write-Host "    1. Double-click 'START TRADING' di Desktop" -ForegroundColor Cyan
Write-Host "    2. TradingView + Web UI + Cloudflare tunnel akan start otomatis" -ForegroundColor Cyan
Write-Host "    3. Buka: http://localhost:$WEB_PORT/dashboard" -ForegroundColor Cyan
Write-Host "    4. Atau akses dari manapun: https://trade.dadangchatai.com" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Update ke versi terbaru:" -ForegroundColor White
Write-Host "    Jalankan script ini lagi — dia otomatis git pull + rebuild" -ForegroundColor Cyan
Write-Host ""
Write-Host "  =================================================================" -ForegroundColor DarkCyan
Write-Host ""
Read-Host "  Tekan ENTER untuk keluar"
