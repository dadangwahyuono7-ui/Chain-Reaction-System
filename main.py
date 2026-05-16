import time
import MetaTrader5 as mt5
import json
import os
import random
import math
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.syntax import Syntax
from engine.connection import connect_mt5
from engine.core import SacredDoctrineAnalyst
from engine.executor import ChainReactionExecutor

console = Console()

class ChainFeed:
    def __init__(self):
        self.logs = []
    def add(self, msg):
        now = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{now}] {msg}")
        if len(self.logs) > 6: self.logs.pop(0)
    def render(self):
        return "\n".join(self.logs)

feed = ChainFeed()

def load_settings():
    path = "chain_settings.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"auto_trade": False, "lot_size": 0.01, "max_layers": 3, "barrier_limit": 3.5}

def make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="ticker", size=3)
    )
    layout["main"].split_row(
        Layout(name="side", ratio=1),
        Layout(name="body", ratio=3)
    )
    layout["side"].split_column(
        Layout(name="account", ratio=1),
        Layout(name="pulse", ratio=1)
    )
    layout["body"].split_column(
        Layout(name="matrix", ratio=2),
        Layout(name="feed", ratio=1)
    )
    return layout

def get_ticker_text(frame):
    news = [
        "INSTITUTIONAL LIQUIDITY DETECTED NEAR H4 SNR",
        "CHAIN REACTION CORE: STABLE",
        "BARRIER GUARD: ACTIVE & PROTECTING",
        "SACRED DOCTRINE: TIME LAW ENFORCED",
        "GOLD VOLATILITY: MONITORING",
        "SULTAN SNIPER RETIRED - LONG LIVE CHAIN REACTION",
        "NEURAL SCAN: NO MALFORMED PATTERNS FOUND"
    ]
    # Simple scrolling effect
    combined = "  •  ".join(news)
    shift = frame % len(combined)
    display = combined[shift:] + "  •  " + combined[:shift]
    return display[:100]

def update_layout(layout, analyst, executor, symbol, settings, frame):
    # 1. Header with Pulse & Ticker
    tick = mt5.symbol_info_tick(symbol)
    bid = f"{tick.bid:.2f}" if tick else "OFFLINE"
    ask = f"{tick.ask:.2f}" if tick else "OFFLINE"
    
    pulse_char = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"][frame % 10]
    
    header_text = Text.assemble(
        (f" {pulse_char} CHAIN REACTION KINETIC ", "bold gold1"),
        (f" | MASTER: {settings.get('master_tf', 'H4')} ", "bold cyan"),
        (f" | BID: ", "white"), (bid, "bold green"),
        (f" ASK: ", "white"), (ask, "bold red"),
        (f" | {datetime.now().strftime('%H:%M:%S')}", "dim white")
    )
    layout["header"].update(Panel(Align.center(header_text), style="dodger_blue1"))

    # 2. Account Panel
    acc = mt5.account_info()
    acc_table = Table(box=None, expand=True)
    acc_table.add_column("Key", style="cyan")
    acc_table.add_column("Value", style="bold magenta", justify="right")
    if acc:
        acc_table.add_row("ACCOUNT", str(acc.login))
        acc_table.add_row("BALANCE", f"{acc.balance:,.2f}")
        acc_table.add_row("PROFIT", f"{acc.profit:+.2f}")
    layout["account"].update(Panel(acc_table, title="[bold white]CORE SYNC[/bold white]", border_style="cyan"))

    # 3. Pulse / Neural Scanner (Visual Movement)
    sin_val = math.sin(frame * 0.5) * 10 + 10
    pulse_bar = "█" * int(sin_val)
    pulse_text = Text.assemble(
        ("\n NEURAL HEARTBEAT\n", "bold white"),
        (f" {pulse_bar}\n", "bold gold1"),
        ("\n STATUS: ACTIVE SCAN", "blink green")
    )
    layout["pulse"].update(Panel(Align.center(pulse_text), title="[bold white]ENGINE PULSE[/bold white]", border_style="gold1"))

    # 4. Reaction Matrix with "Scanning" Highlight
    matrix_table = Table(expand=True, border_style="grey37")
    matrix_table.add_column("TF", justify="center", style="bold white")
    matrix_table.add_column("CMP", justify="center")
    matrix_table.add_column("STATUS", justify="center")
    matrix_table.add_column("SNR LEVEL", justify="center", style="dim")

    tfs = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]
    scanning_idx = (frame // 2) % len(tfs)
    
    for i, tf in enumerate(tfs):
        st = analyst.states[tf]
        is_scanning = (i == scanning_idx)
        cmp_color = "green" if st.cmp == "BUY" else "red" if st.cmp == "SELL" else "white"
        stat_color = "yellow" if st.status == "CF" else "deep_sky_blue1" if st.status == "VR" else "white"
        if st.status == "MASTER": stat_color = "gold1"
        
        row_style = "on grey15" if is_scanning else ""
        
        matrix_table.add_row(
            f"{'▶' if is_scanning else ' '} {tf}",
            f"[{cmp_color}]{st.cmp}[/]",
            f"[{stat_color}]{st.status}[/]",
            f"S:{st.sup:.2f} R:{st.res:.2f}",
            style=row_style
        )
    layout["matrix"].update(Panel(matrix_table, title="[bold white]HIERARCHY MATRIX[/bold white]", border_style="magenta"))

    # 5. Feed
    layout["feed"].update(Panel(feed.render(), title="[bold white]TACTICAL FEED[/bold white]", border_style="green"))

    # 6. Ticker (Scrolling News)
    ticker_text = get_ticker_text(frame)
    layout["ticker"].update(Panel(Align.center(Text(ticker_text, style="bold italic yellow")), style="grey23"))

def main():
    symbol = "XAUUSD"
    if not connect_mt5(): return

    settings = load_settings()
    analyst = SacredDoctrineAnalyst(symbol, master_tf=settings.get("master_tf", "H4"))
    executor = ChainReactionExecutor(symbol, magic_number=settings.get("magic_number", 2026))
    
    layout = make_layout()
    frame = 0
    
    last_strike_time = 0
    cooldown = 300

    with Live(layout, refresh_per_second=8, screen=True) as live:
        while True:
            try:
                analyst.update()
                settings = load_settings()
                executor.monitor_positions(analyst)
                
                # Signal Processing
                signal = analyst.get_strike_signal()
                if signal and settings.get("auto_trade"):
                    if time.time() - last_strike_time > cooldown:
                        # (Execution logic same as before)
                        success, msg = executor.execute_strike(signal['action'], analyst)
                        if success:
                            last_strike_time = time.time()
                            feed.add(f"🚀 STRIKE: {signal['reason']}")
                        else:
                            feed.add(f"❌ VETO: {msg}")
                
                update_layout(layout, analyst, executor, symbol, settings, frame)
                frame += 1
                time.sleep(0.125)
            except KeyboardInterrupt: break
            except Exception as e:
                feed.add(f"ERROR: {str(e)}")
                time.sleep(2)

if __name__ == "__main__":
    main()
