$uri = "http://127.0.0.1:9222/json"
try {
    $tabs = Invoke-RestMethod -Uri $uri
} catch {
    Write-Host "[ERROR] Could not connect to TradingView debug port 9222! Please make sure launch_tv_debug.bat was run." -ForegroundColor Red
    exit
}

$chartTab = $tabs | Where-Object { $_.url -like "*tradingview.com/chart*" } | Select-Object -First 1

if ($chartTab -eq $null) {
    Write-Host "[ERROR] No active TradingView chart tab found! Please open a chart in TradingView." -ForegroundColor Red
    exit
}

$wsUrl = $chartTab.webSocketDebuggerUrl
Write-Host "Establishing secure AI uplink to WebSocket..."

# Connect using native .NET ClientWebSocket
$ws = New-Object System.Net.WebSockets.ClientWebSocket
$cts = New-Object System.Threading.CancellationTokenSource
$wsUri = New-Object System.Uri($wsUrl)

try {
    $ws.ConnectAsync($wsUri, $cts.Token).Wait()
} catch {
    Write-Host "[ERROR] Failed to establish WebSocket connection!" -ForegroundColor Red
    exit
}

# Read JavaScript code cleanly from external JS file
$jsFile = "d:\PROJECT TRADING\engine\draw_tv_poc.js"
if (-not (Test-Path $jsFile)) {
    Write-Host "[ERROR] JS Payload file not found!" -ForegroundColor Red
    exit
}
$jsCode = Get-Content -Path $jsFile -Raw

# Format Chrome DevTools Protocol Runtime.evaluate payload
$payload = @{
    id = 1
    method = "Runtime.evaluate"
    params = @{
        expression = $jsCode
    }
} | ConvertTo-Json -Compress

$bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
$buffer = New-Object System.ArraySegment[System.Byte] -ArgumentList (,$bytes)

# Send to TradingView Desktop tab
$ws.SendAsync($buffer, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token).Wait()

Write-Host "[SUCCESS] Dynamic Cyber-Badge successfully injected into TradingView!"
$ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "Done", $cts.Token).Wait()
