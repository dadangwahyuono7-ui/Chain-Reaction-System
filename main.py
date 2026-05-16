import time
import MetaTrader5 as mt5
import json
import os
import random
import math
from datetime import datetime, timedelta
import pytz
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
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

def get_session_times():
    now = datetime.now(pytz.utc)
    sessions = {"LONDON": (8, 16), "NEW YORK": (13, 21), "TOKYO": (0, 8), "SYDNEY": (22, 6)}
    results = []
    for name, (start, end) in sessions.items():
        is_active = start <= now.hour < end
        results.append(f"[{'green' if is_active else 'dim'}]{name}[/]")
    return " | ".join(results)

def make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="ticker", size=3)
    )
    layout["main"].split_row(Layout(name="side", ratio=1), Layout(name="body", ratio=3))
    layout["side"].split_column(Layout(name="account", ratio=1), Layout(name="stats", ratio=1), Layout(name="pulse", size=5))
    layout["body"].split_column(
        Layout(name="intel", size=3),
        Layout(name="matrix", ratio=2),
        Layout(name="feed", ratio=1)
    )
    return layout

def get_real_stats(magic):
    from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(from_date, datetime.now())
    if not deals: return {"win_rate": 0, "strikes": 0, "pnl": 0.0}
    my_deals = [d for d in deals if d.magic == magic]
    if not my_deals: return {"win_rate": 0, "strikes": 0, "pnl": 0.0}
    strikes = len([d for d in my_deals if d.entry == mt5.DEAL_ENTRY_IN])
    pnl = sum([d.profit for d in my_deals])
    closed_deals = [d for d in my_deals if d.entry == mt5.DEAL_ENTRY_OUT]
    wins = len([d for d in closed_deals if d.profit > 0])
    return {"win_rate": (wins / len(closed_deals) * 100) if closed_deals else 0, "strikes": strikes, "pnl": pnl}

def update_layout(layout, analyst, executor, symbol, settings, frame):
    # 0. Scrolling Strategic Intel
    intel_msg = analyst.get_strategic_forecast().replace("[bold yellow]", "").replace("[bold green]", "").replace("[bold cyan]", "").replace("[bold blue]", "").replace("[/]", "")
    display_len = 80
    combined = "  •  " + intel_msg + "  •  "
    shift = (frame // 2) % len(combined)
    scrolling_text = combined[shift:] + combined[:shift]
    layout["intel"].update(Panel(Align.center(Text(scrolling_text[:display_len], style="bold gold1")), title="[bold white]STRATEGIC INTEL[/bold white]", border_style="gold1"))

    # Theme
    master = analyst.states[settings.get("master_tf", "H4")]
    theme_color = "green" if master.cmp == "BUY" else "red" if master.cmp == "SELL" else "gold1"
    
    tick = mt5.symbol_info_tick(symbol)
    bid = f"{tick.bid:.2f}" if tick else "OFFLINE"
    ask = f"{tick.ask:.2f}" if tick else "OFFLINE"
    pulse_char = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"][frame % 10]
    
    layout["header"].update(Panel(Align.center(Text.assemble((f" {pulse_char} CHAIN REACTION WAR-LORD ", f"bold {theme_color}"), (f" | BY: COMMANDER DADANG ", "bold yellow"), (f" | {symbol}: ", "white"), (bid, "bold green"), (f"/", "white"), (ask, "bold red"), (f" | {datetime.now().strftime('%H:%M:%S')}", "dim white"))), style=f"bold {theme_color}"))

    acc = mt5.account_info()
    acc_table = Table(box=None, expand=True)
    acc_table.add_column("Key", style="cyan"); acc_table.add_column("Val", style="bold magenta", justify="right")
    if acc: acc_table.add_row("ACC", str(acc.login)); acc_table.add_row("BAL", f"{acc.balance:,.0f}"); acc_table.add_row("EQTY", f"{acc.equity:,.0f}")
    layout["account"].update(Panel(acc_table, title="[bold white]CORE[/bold white]", border_style="cyan"))

    stats = get_real_stats(settings.get("magic_number", 2026))
    stats_table = Table(box=None, expand=True)
    stats_table.add_column("Stat", style="yellow"); stats_table.add_column("Val", style="bold white", justify="right")
    stats_table.add_row("WIN RATE", f"{stats['win_rate']:.0f}%"); stats_table.add_row("STRIKES", str(stats['strikes'])); stats_table.add_row("PnL TODAY", f"[green]+{stats['pnl']:,.2f}[/]" if stats['pnl'] >= 0 else f"[red]{stats['pnl']:,.2f}[/]")
    layout["stats"].update(Panel(stats_table, title="[bold white]REAL STATS[/bold white]", border_style="yellow"))

    sin_val = math.sin(frame * 0.5) * 8 + 8
    layout["pulse"].update(Panel(Align.center(Text(f"\n{'█' * int(sin_val)}\nPULSE ACTIVE", style=f"bold {theme_color}")), border_style=theme_color))

    matrix_table = Table(expand=True, border_style="grey37")
    matrix_table.add_column("TF", justify="center", style="bold white"); matrix_table.add_column("CMP", justify="center"); matrix_table.add_column("STATUS", justify="center"); matrix_table.add_column("SNR", justify="center", style="dim")
    tfs = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]
    scanning_idx = (frame // 2) % len(tfs)
    for i, tf in enumerate(tfs):
        st = analyst.states[tf]; is_scanning = (i == scanning_idx)
        c = "green" if st.cmp == "BUY" else "red" if st.cmp == "SELL" else "white"
        s_c = "yellow" if st.status == "CF" else "deep_sky_blue1" if st.status == "VR" else "white"
        if st.status == "MASTER": s_c = "gold1"
        matrix_table.add_row(f"{'▶' if is_scanning else ' '} {tf}", f"[{c}]{st.cmp}[/]", f"[{s_c}]{st.status}[/]", f"{st.sup:.1f}/{st.res:.1f}", style="on grey15" if is_scanning else "")
    layout["matrix"].update(Panel(matrix_table, title="[bold white]HIERARCHY MATRIX[/bold white]", border_style="magenta"))

    layout["feed"].update(Panel(feed.render(), title="[bold white]TACTICAL FEED[/bold white]", border_style="green"))
    layout["ticker"].update(Panel(Align.center(Text(f" SESSIONS: {get_session_times()}  •  CHAIN REACTION CORE: STABLE  •  SACRED DOCTRINE: TIME LAW ENFORCED ", style="bold yellow")), style="grey23"))

def boot_sequence():
    console.clear()
    tasks = [
        "INITIALIZING KERNEL...", "LOADING SACRED DOCTRINE...", "AUTHENTICATING COMMANDER DADANG...",
        "SYNCING HIERARCHY MATRIX...", "ARMED TIME LAW v2.5...", "CALIBRATING BARRIER GUARD...",
        "LINKING GHOST STRIKE RADAR...", "FETCHING REAL-TIME ACCOUNT STATS...", "NEURAL PULSE SYNCHRONIZATION...",
        "CHAIN REACTION SYSTEM READY!"
    ]
    with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"), BarColumn(bar_width=40, complete_style="gold1"), console=console, transient=True) as progress:
        for i, task_name in enumerate(tasks):
            t = progress.add_task(f"[ {i+1}/10 ] {task_name}", total=100)
            while not progress.finished:
                progress.update(t, advance=random.uniform(5, 15))
                time.sleep(0.1)
                if progress.tasks[i].finished: break

    logo = """[bold gold1]
     _______ _    _          _____ _   _   _____  ______          _____ _______ _____ ____  _   _ 
    |  _____| |  | |   /\   |_   _| \ | | |  __ \|  ____|   /\   / ____|__   __|_   _/ __ \| \ | |
    | |     | |__| |  /  \    | | |  \| | | |__) | |__     /  \ | |       | |    | || |  | |  \| |
    | |     |  __  | / /\ \   | | | . ` | |  _  /|  __|   / /\ \| |       | |    | || |  | | . ` |
    | |_____| |  | |/ ____ \ _| |_| |\  | | | \ \| |____ / ____ \ |____   | |   _| || |__| | |\  |
    |_______|_|  |_/_/    \_\_____|_| \_| |_|  \_\______/_/    \_\_____|  |_|  |_____\____/|_| \_|
    [/bold gold1]
    [bold cyan]                       PROPERTY OF COMMANDER DADANG | v3.0 WAR-LORD[/bold cyan]
    """
    console.clear(); console.print("\n" * 3); console.print(Align.center(logo))
    time.sleep(5.0)
    console.print(Align.center("[bold blink green]UPLINK ESTABLISHED. ACCESS GRANTED.[/bold blink green]"))
    time.sleep(1.5)

def main():
    symbol = "XAUUSD"
    if not connect_mt5(): return
    boot_sequence()
    settings = load_settings(); analyst = SacredDoctrineAnalyst(symbol, master_tf=settings.get("master_tf", "H4"))
    executor = ChainReactionExecutor(symbol, magic_number=settings.get("magic_number", 2026))
    layout = make_layout(); frame = 0; last_strike_time = 0
    feed.add(f"🔗 CORE ONLINE: Standing by for Market Ignition")
    feed.add(f"⚖️ DOCTRINE ARMED: Time Law Enforced")
    feed.add(f"🛰️ RADAR ACTIVE: Scanning for {symbol} Reaction")
    with Live(layout, refresh_per_second=8, screen=True) as live:
        while True:
            try:
                analyst.update(); settings = load_settings()
                events = executor.monitor_positions(analyst)
                for e in events: feed.add(e)
                signal = analyst.get_strike_signal()
                if signal and settings.get("auto_trade"):
                    if time.time() - last_strike_time > 300:
                        positions = mt5.positions_get(symbol=symbol, magic=settings.get("magic_number", 2026))
                        if len(positions) < settings.get("max_layers", 3):
                            success, msg = executor.execute_strike(signal['action'], analyst, lot=settings.get("lot_size", 0.01), comment=f"Chain_{signal['tf']}")
                            feed.add(msg)
                            if success: last_strike_time = time.time()
                update_layout(layout, analyst, executor, symbol, settings, frame)
                frame += 1; time.sleep(0.1)
            except KeyboardInterrupt: break
            except Exception as e: feed.add(f"ERR: {str(e)}"); time.sleep(2)

if __name__ == "__main__":
    main()
