"""
BACKTEST RUN — Konfigurasi di sini, lalu jalankan:
    python backtest/run.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
from rich.console import Console
from engine.connection import connect_mt5
from backtest.backtest import run_backtest

console = Console()

# ═══════════════════════════════════════════════════════════
#  CONFIG BACKTEST — ubah di sini
# ═══════════════════════════════════════════════════════════

SYMBOL          = "XAUUSD"
START_DATE      = "2025-01-01"   # format YYYY-MM-DD
END_DATE        = "2025-12-31"

INITIAL_BALANCE = 10_000.0       # modal awal (USD)
SL_BUFFER_PIPS  = 5.0            # buffer pips di luar SNR untuk SL/TP
RR_RATIO        = 0.0            # 0 = pakai SNR natural, 2.0 = fixed 1:2 RR
COOLDOWN_BARS   = 12             # jeda setelah close trade (12 M5 = 1 jam)
MAX_TRADES      = 0              # 0 = unlimited

# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    console.print("[bold cyan]CHAIN REACTION v4.0 — BACKTEST MODE[/]")
    console.print("[grey62]Sacred Doctrine Engine — Historical Performance Audit[/]\n")

    if not connect_mt5():
        console.print("[red]ERROR: MT5 connection failed[/]")
        sys.exit(1)

    try:
        results = run_backtest(
            symbol          = SYMBOL,
            start           = START_DATE,
            end             = END_DATE,
            initial_balance = INITIAL_BALANCE,
            sl_buffer_pips  = SL_BUFFER_PIPS,
            rr_ratio        = RR_RATIO,
            cooldown_bars   = COOLDOWN_BARS,
            max_trades      = MAX_TRADES,
        )
    finally:
        mt5.shutdown()
        console.print("\n[grey62]MT5 disconnected.[/]")
