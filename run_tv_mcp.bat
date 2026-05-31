@echo off
echo Starting TradingView Desktop with CDP enabled...
cd /d "d:\tradingview-mcp"
call scripts\launch_tv_debug.bat 9222

echo Starting TradingView MCP Server...
node src/server.js
pause
