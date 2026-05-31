# ============================================================================
#  SULTAN SNIPER ENGINE — EXPORT CONFIG
#  Jalankan di PC yang sudah jalan, untuk dipindah ke laptop.
#  Output: SultanConfig.zip di Desktop
# ============================================================================

$INSTALL_DIR = "D:\PROJECT TRADING"
$WEB_DIR     = "$INSTALL_DIR\sultan-advisor"
$CF_DIR      = "$env:USERPROFILE\.cloudflared"
$OUTPUT      = "$env:USERPROFILE\Desktop\SultanConfig.zip"

Clear-Host
Write-Host ""
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host "   SULTAN CONFIG EXPORT — untuk dipindah ke laptop               " -ForegroundColor White
Write-Host "  =================================================================" -ForegroundColor Cyan
Write-Host ""

# Buat temp folder
$tmp = "$env:TEMP\SultanConfigExport"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
New-Item -ItemType Directory $tmp | Out-Null
New-Item -ItemType Directory "$tmp\cloudflared" | Out-Null

$ok = $true

# 1. Copy .env.local
$envFile = "$WEB_DIR\.env.local"
if (Test-Path $envFile) {
    Copy-Item $envFile "$tmp\.env.local"
    Write-Host "  ✅ .env.local (API keys, secrets)" -ForegroundColor Green
} else {
    Write-Host "  ❌ .env.local tidak ditemukan di $envFile" -ForegroundColor Red
    $ok = $false
}

# 2. Copy .cloudflared (tunnel credentials)
if (Test-Path $CF_DIR) {
    Copy-Item "$CF_DIR\*" "$tmp\cloudflared\" -Recurse -ErrorAction SilentlyContinue
    $cfFiles = (Get-ChildItem "$tmp\cloudflared").Count
    Write-Host "  ✅ Cloudflare tunnel config ($cfFiles files)" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  .cloudflared tidak ditemukan — tunnel perlu setup manual di laptop" -ForegroundColor Yellow
}

# 3. Buat zip
if ($ok) {
    if (Test-Path $OUTPUT) { Remove-Item $OUTPUT -Force }
    Compress-Archive -Path "$tmp\*" -DestinationPath $OUTPUT -Force
    Remove-Item $tmp -Recurse -Force

    Write-Host ""
    Write-Host "  =================================================================" -ForegroundColor Green
    Write-Host "   EXPORT SELESAI!                                                " -ForegroundColor Green
    Write-Host "  =================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  File: $OUTPUT" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Cara pindah ke laptop:" -ForegroundColor White
    Write-Host "    1. Copy SultanConfig.zip ke laptop (USB / Google Drive / dll)" -ForegroundColor Cyan
    Write-Host "    2. Taruh di Desktop laptop" -ForegroundColor Cyan
    Write-Host "    3. Jalankan INSTALL.ps1 — config otomatis ke-detect & di-import" -ForegroundColor Cyan
    Write-Host ""
    # Buka Desktop folder
    Start-Process "explorer.exe" $env:USERPROFILE\Desktop
} else {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "  Export gagal — pastikan sistem sudah setup dulu." -ForegroundColor Red
}

Write-Host ""
Read-Host "  Tekan ENTER untuk keluar"
