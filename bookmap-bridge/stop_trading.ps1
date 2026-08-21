# Chain Reaction - stop the background processes started by start_trading.ps1
# (udp_listener.py, sultan_dashboard_server.py, cloudflared).
# Does NOT touch MT5 or Bookmap - those you close yourself.
#
# 2026-08-20: target list was stale - tv_poll.mjs (TradingView, retired
# 2026-08-11) and dashboard_web.py (removed from start_trading.ps1 same day
# as this fix) were still listed while sultan_dashboard_server.py (the one
# actually started now) was missing entirely.

$targets = @("udp_listener.py", "sultan_dashboard_server.py")
$killed = 0

foreach ($proc in Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe" }) {
    foreach ($t in $targets) {
        if ($proc.CommandLine -like "*$t*") {
            Write-Host "Stopping PID $($proc.ProcessId): $t"
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            $killed++
        }
    }
}
foreach ($proc in Get-Process -Name cloudflared -ErrorAction SilentlyContinue) {
    Write-Host "Stopping PID $($proc.Id): cloudflared"
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    $killed++
}

if ($killed -eq 0) {
    Write-Host "Gak ada proses Chain Reaction yang lagi jalan."
} else {
    Write-Host "$killed proses distop."
}
Start-Sleep -Seconds 3
