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
from engine.core import SacredDoctrineAnalyst, BSTradingAnalyst
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

def get_market_volatility():
    try:
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 5)
        if rates is None or len(rates) == 0:
            return "[dim]SCANNING...[/dim]"
        tot = 0.0
        for r in rates:
            # Safe access for numpy structured array
            h = float(r['high'] if rates.dtype and 'high' in rates.dtype.names else r[2])
            l = float(r['low'] if rates.dtype and 'low' in rates.dtype.names else r[3])
            tot += (h - l)
        avg_range = tot / len(rates)
        if avg_range < 0.6:
            return f"[green]LOW[/green] ({avg_range:.2f} USD)"
        elif avg_range < 1.8:
            return f"[yellow]MODERATE[/yellow] ({avg_range:.2f} USD)"
        else:
            return f"[blink bold red]🚨 HIGH[/blink bold red] ({avg_range:.2f} USD)"
    except Exception:
        return "[dim]STANDBY[/dim]"

def get_commander_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12: return "Good Morning, Commander. Markets are waking up."
    if 12 <= hour < 17: return "Good Afternoon, Commander. Liquidity is peaking."
    if 17 <= hour < 22: return "Good Evening, Commander. Night Ops in progress."
    return "Late Night, Commander. High Volatility expected."

def make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="ticker", size=3)
    )
    layout["main"].split_row(Layout(name="side", ratio=1), Layout(name="body", ratio=3))
    layout["side"].split_column(
        Layout(name="greeting", size=3),
        Layout(name="account", ratio=2),
        Layout(name="stats", ratio=2),
        Layout(name="sentiment", size=5),
        Layout(name="sniper_hud", size=9)
    )
    layout["body"].split_column(
        Layout(name="intel", size=3),
        Layout(name="matrix_row", ratio=2),
        Layout(name="liquidity", size=6),
        Layout(name="news_feed", ratio=1)
    )
    layout["matrix_row"].split_row(
        Layout(name="matrix", ratio=1),
        Layout(name="bs_matrix", ratio=1)
    )
    layout["news_feed"].split_row(
        Layout(name="news", ratio=1),
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

def update_layout(layout, analyst, bs_analyst, executor, symbol, settings, frame):
    pulse_colors = ["white", "bright_cyan", "gold1", "bright_cyan"]
    title_style = f"bold {pulse_colors[frame % 4]}"
    
    # 0. Strategic Intel (Marquee)
    intel_msg = analyst.get_strategic_forecast().replace("[bold yellow]", "").replace("[bold green]", "").replace("[bold cyan]", "").replace("[bold blue]", "").replace("[/]", "")
    display_len = 80; combined = "  •  " + intel_msg + "  •  "; shift = (frame // 2) % len(combined); scrolling_text = combined[shift:] + combined[:shift]
    layout["intel"].update(Panel(Align.center(Text(scrolling_text[:display_len], style="bold gold1")), title=f"[{title_style}]STRATEGIC INTEL[/{title_style}]", border_style="gold1"))

    # Theme
    master = analyst.states[settings.get("master_tf", "H4")]
    theme_color = "green" if master.cmp == "BUY" else "red" if master.cmp == "SELL" else "gold1"
    sync_icon = "📡" if frame % 4 < 2 else "🛰️"
    tick = mt5.symbol_info_tick(symbol)
    bid = f"{tick.bid:.2f}" if tick else "OFFLINE"; ask = f"{tick.ask:.2f}" if tick else "OFFLINE"
    pulse_char = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"][frame % 10]
    
    layout["header"].update(Panel(Align.center(Text.assemble((f" {pulse_char} CHAIN REACTION ", f"bold {theme_color}"), (f" [bold white][OVERLORD CLEARANCE][/bold white] ", "blink"), (f" | BY: COMMANDER DADANG ", "bold yellow"), (f" | {symbol}: ", "white"), (bid, "bold green"), (f"/", "white"), (ask, "bold red"), (f" | {datetime.now().strftime('%H:%M:%S')}", "dim white"))), style=f"bold {theme_color}"))
    layout["greeting"].update(Panel(Align.center(Text(get_commander_greeting(), style="bold cyan")), border_style="dim cyan"))

    # Core Sync & Stats
    acc = mt5.account_info(); acc_table = Table(box=None, expand=True)
    acc_table.add_column("Key", style="cyan"); acc_table.add_column("Val", style="bold magenta", justify="right")
    if acc: acc_table.add_row("ACC", f"{acc.login}"); acc_table.add_row("BAL", f"{acc.balance:,.0f}"); acc_table.add_row("EQTY", f"{acc.equity:,.0f}")
    acc_table.add_row("", ""); acc_table.add_row("[cyan]UPLINK[/]", f"[bold cyan]{'█' * int(math.sin(frame * 0.8) * 4 + 5)}[/]")
    layout["account"].update(Panel(acc_table, title=f"[{title_style}]{sync_icon} CORE SYNC[/{title_style}]", border_style="cyan" if frame % 4 != 0 else "bright_cyan"))

    stats = get_real_stats(settings.get("magic_number", 2026)); stats_table = Table(box=None, expand=True)
    stats_table.add_column("Stat", style="yellow"); stats_table.add_column("Val", style="bold white", justify="right")
    stats_table.add_row("WIN RATE", f"{stats['win_rate']:.0f}%"); stats_table.add_row("STRIKES", str(stats['strikes'])); stats_table.add_row("PnL TODAY", f"[green]+{stats['pnl']:,.2f}[/]" if stats['pnl'] >= 0 else f"[red]{stats['pnl']:,.2f}[/]")
    stats_table.add_row("", ""); stats_table.add_row("[yellow]PROC[/]", f"[bold yellow]{'█' * int(math.cos(frame * 0.6) * 4 + 5)}[/]")
    layout["stats"].update(Panel(stats_table, title=f"[{title_style}]📊 LIVE STATS[/{title_style}]", border_style="yellow" if frame % 4 != 2 else "bright_yellow"))

    # Sentiment Radar
    buy_pct, sell_pct = analyst.get_total_sentiment()
    sentiment_bar = f"[green]{'█' * int(buy_pct/10)}[/][red]{'█' * int(sell_pct/10)}[/]"
    layout["sentiment"].update(Panel(Align.center(Text(f"BUY {buy_pct:.0f}% | SELL {sell_pct:.0f}%\n{sentiment_bar}\nOVERLORD SENTIMENT", style="bold white")), title="[dim]RADAR[/]", border_style="bright_magenta"))

    # Unified Sniper HUD with ASCII Art and Waveform
    wave = ""
    for i in range(12):
        h = int(math.sin((frame + i) * 0.5) * 2 + 2)
        wave += " " if h < 1 else "▂" if h == 1 else "▃" if h == 2 else "▅" if h == 3 else "▆"
    
    # Blinking target center
    dot = "[blink red]●[/blink red]" if frame % 2 == 0 else " "
    
    hud_art = (
        f"     _.-'''''-._     [bold cyan]UPLINK: ONLINE[/bold cyan]\n"
        f"   .'   _ | _   '.   [bold green]TARGET: {symbol}[/bold green]\n"
        f"  /   /   {dot}   \\   \\  [bold yellow]SOP: ACTIVE[/bold yellow]\n"
        f" |   |----+----|   | ----------------\n"
        f"  \\   \\   {dot}   /   /  [bold magenta]WAVE:[/bold magenta] {wave}\n"
        f"   '.   '-...-'   .' [dim white]{sync_icon} SCANNING SYSTEMS...[/dim white]"
    )
    layout["sniper_hud"].update(Panel(Align.center(Text.from_markup(hud_art)), title=f"[{title_style}]🎯 COMMANDER HUD[/{title_style}]", border_style="green"))

    # Hierarchy Matrix
    matrix_table = Table(expand=True, border_style="grey37")
    matrix_table.add_column("TF", justify="center", style="bold white"); matrix_table.add_column("CMP", justify="center"); matrix_table.add_column("STATUS", justify="center"); matrix_table.add_column("SNR", justify="center", style="dim")
    tfs = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]; scanning_idx = (frame // 1) % len(tfs)
    for i, tf in enumerate(tfs):
        st = analyst.states[tf]; is_scanning = (i == scanning_idx); blink = "[blink]" if is_scanning and frame % 2 == 0 else ""
        c = "green" if st.cmp == "BUY" else "red" if st.cmp == "SELL" else "white"; s_c = "yellow" if st.status == "CF" else "deep_sky_blue1" if st.status == "VR" else "white"
        if st.status == "MASTER": s_c = "gold1"
        row_style = "bold on grey19" if is_scanning else ""; matrix_table.add_row(f"{'📡' if is_scanning else '  '} {tf}", f"[{c}]{st.cmp}[/]", f"{blink}[{s_c}]{st.status}[/]{blink if blink else ''}", f"{st.sup:.1f}/{st.res:.1f}", style=row_style)
    
    # Telemetry spacer & status row to fill the empty space (hacker-vibe!)
    matrix_table.add_row("", "", "", "")
    aligned_tfs = sum(1 for tf in tfs if analyst.states[tf].cmp == analyst.states["H4"].cmp)
    wib_str = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%H:%M:%S")
    matrix_table.add_row(
        "[bold cyan]📡 TELEMETRY[/]",
        f"[green]ALIGN: {aligned_tfs}/8[/]",
        f"[yellow]WIB: {wib_str}[/]",
        f"[green]LATENCY: {random.randint(11, 24)}ms[/]"
    )
    layout["matrix"].update(Panel(matrix_table, title=f"[{title_style}]HIERARCHY MATRIX[/{title_style}]", border_style="magenta"))

    # BS Trading SOP Engine Panel
    bs_table = Table(box=None, expand=True)
    bs_table.add_column("Property", style="cyan")
    bs_table.add_column("Value", justify="right")
    
    dir_style = "bold green" if bs_analyst.locked_direction == "BUY" else "bold red" if bs_analyst.locked_direction == "SELL" else "white"
    bs_table.add_row("1. DIRECTION LOCK", f"[{dir_style}]{bs_analyst.locked_direction} LOCK {'🟢' if bs_analyst.locked_direction == 'BUY' else '🔴'}[/]")
    
    mz_style = "blink bold green" if bs_analyst.standby_state == "READY" else "bold yellow"
    mz_icon = "🟢" if bs_analyst.standby_state == "READY" else "🟡"
    bs_table.add_row("2. STANDBY STATE", f"[{mz_style}]{bs_analyst.standby_state} {mz_icon}[/]")
    
    active_mz_str = "None"
    if bs_analyst.active_mz:
        mz = bs_analyst.active_mz
        active_mz_str = f"[bold magenta]{mz['tf']} {mz['type']}[/] ({mz['low']:.1f}-{mz['high']:.1f})"
    bs_table.add_row("   ACTIVE MZ", active_mz_str)
    
    trigger_str = "[dim]NO TRIGGER 📡[/]"
    if bs_analyst.pmb_trigger:
        trig = bs_analyst.pmb_trigger
        trigger_str = f"[blink bold red]🔥 {trig['type']} Sweep ({trig['risk']})[/]"
    bs_table.add_row("3. PMB TRIGGER", trigger_str)
    
    if bs_analyst.pmb_trigger:
        trig = bs_analyst.pmb_trigger
        bs_table.add_row("   ENTRY DETAILS", f"[green]SL: {trig['sl']:.1f}[/] | [yellow]TP: {trig['tp']:.1f}[/]")
        
    safety_str = f"[bold green]🛡️ SECURE[/]" if not bs_analyst.safety_veto else f"[bold red]🚨 VETO: {bs_analyst.safety_msg}[/]"
    bs_table.add_row("4. SAFETY FILTER", safety_str)
    
    trend_labels = []
    for tf in ["D1", "H4", "H1", "M30", "M15", "M5", "M1"]:
        tr = bs_analyst.tf_trends[tf]
        col = "green" if tr == "BUY" else "red" if tr == "SELL" else "white"
        trend_labels.append(f"[{col}]{tf}:{tr[:3]}[/]")
    bs_table.add_row("5. TF TRENDS", " ".join(trend_labels))
    
    # Interactive MZ boundary visual slider & hacker telemetry to fill the empty space!
    bs_table.add_row("", "")
    if bs_analyst.active_mz:
        mz = bs_analyst.active_mz
        low = float(mz['low'])
        high = float(mz['high'])
        current = float(bs_analyst.current_price)
        pct = (current - low) / (high - low) if high > low else 0.5
        pct = max(0.0, min(1.0, pct))
        width = 24
        filled = int(pct * width)
        slider = "─" * filled + "[blink bold green]●[/blink bold green]" + "─" * (width - filled)
        
        bs_table.add_row("[bold cyan]🎯 MZ BOUNDARY[/]", f"[dim]{low:.1f}[/] {slider} [dim]{high:.1f}[/]")
        dist_to_low = current - low
        dist_to_high = high - current
        bs_table.add_row("   ZONE METRICS", f"[green]DL: {dist_to_low:.2f}[/] | [yellow]DH: {dist_to_high:.2f}[/]")
    else:
        scanners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        scanner = scanners[frame % len(scanners)]
        scan_wave = "".join(random.choice(["░", "▒", "▓", "█", " "]) for _ in range(12))
        bs_table.add_row("[bold dim yellow]🛰️ MZ RADAR[/]", f"[dim yellow]{scanner} SCANNING FOR SB/SS ZONE[/]")
        bs_table.add_row("   SYSTEM FREQ", f"[cyan]FREQ: 433.9MHz[/] | [magenta]{scan_wave}[/]")
        
    # Dynamic pulse identity banner for Commander Dadang (Centered, Large and Bold with Wide Letter Spacing)
    blink_dot = "[blink green]●[/blink green]" if frame % 2 == 0 else "[green] [/green]"
    pulse_colors = ["bold bright_cyan", "bold yellow", "bold bright_green", "bold bright_magenta"]
    col_name = pulse_colors[(frame // 2) % len(pulse_colors)]
    
    # Render a beautiful, large and wide centered commander badge
    commander_banner = Align.center(
        Text.from_markup(f"[bold red]⚔️[/bold red]  [{col_name}]D A D A N G   W A H Y U O N O[/{col_name}]  {blink_dot}", style="bold")
    )
    
    # Wrap both the table, a spacing blank row, and the centered banner in a Group for clean vertical spacing
    from rich.console import Group
    bs_panel_content = Group(
        bs_table,
        Text(""), # Pushes the banner down by exactly 1 line to prevent crowding!
        commander_banner
    )
        
    layout["bs_matrix"].update(Panel(bs_panel_content, title=f"[{title_style}]BS TRADING SOP ENGINE[/{title_style}]", border_style="green" if not bs_analyst.safety_veto else "red"))

    # Liquidity Map
    h4 = analyst.states["H4"]; d1 = analyst.states["D1"]; cp = tick.bid if tick else 0
    def get_map(st):
        if st.sup == 0 or st.res == 0: return "[dim]SCANNING...[/]"
        range_size = st.res - st.sup; 
        if range_size <= 0: return "[dim]SCANNING...[/]"
        pos = int(((cp - st.sup) / range_size) * 20); pos = max(0, min(20, pos)); bar = list("--------------------")
        if 0 <= pos < 20: bar[pos] = "⚡"
        return f"[blue]SUP: {st.sup:.1f}[/] |{''.join(bar)}| [red]RES: {st.res:.1f}[/]"
    liq_table = Table(box=None, expand=True); liq_table.add_row(f"[bold cyan]H4 LIQ:[/bold cyan] {get_map(h4)}"); liq_table.add_row(f"[bold gold1]D1 LIQ:[/bold gold1] {get_map(d1)}")
    layout["liquidity"].update(Panel(liq_table, title=f"[{title_style}]INSTITUTIONAL LIQUIDITY MAP[/{title_style}]", border_style="cyan"))

    # 10. GLOBAL INTEL & NEWS (Live RSS + Forex Factory Red Radar)
    import requests
    import xml.etree.ElementTree as ET

    def fetch_live_news_id():
        # High Impact Red Folders in WIB (UTC+7) for May 2026
        red_folders = [
            "🔴 KAMIS 01:00 WIB: FOMC Meeting Minutes (High Impact)",
            "🔴 KAMIS 20:45 WIB: Flash Manufacturing PMI (High Impact)",
            "📡 INTEL: Kevin Warsh (New Fed Chair) stance is Hawkish.",
            "🔥 GEOPOLITICS: Hormuz Strait tensions increase Gold demand.",
            "📊 SENTIMENT: Markets pricing in 'No Rate Cut' for 2026."
        ]
        try:
            r = requests.get("https://www.forexlive.com/feed/gold", timeout=3)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                live_headlines = [f"📡 LIVE: {item.find('title').text}" for item in root.findall(".//item")[:3]]
                return red_folders + live_headlines
        except: pass
        return red_folders

    if not hasattr(update_layout, "_cached_news") or frame % 300 == 0:
        update_layout._cached_news = fetch_live_news_id()
    
    news_items = update_layout._cached_news
    news_idx = (frame // 30) % len(news_items)
    news_text = Text(news_items[news_idx], style="bold bright_white")
    layout["news"].update(Panel(Align.center(news_text), title=f"[{title_style}]🌍 GLOBAL INTEL & RED RADAR[/{title_style}]", border_style="bright_blue"))

    layout["feed"].update(Panel(feed.render(), title=f"[{title_style}]TACTICAL FEED[/{title_style}]", border_style="green"))
    vol = get_market_volatility()
    ticker_text = Text.from_markup(
        f"🌐 [bold cyan]SESSIONS:[/bold cyan] {get_session_times()}   •   "
        f"📊 [bold cyan]XAUUSD VOLATILITY:[/bold cyan] {vol}   •   "
        f"📡 [bold green]CORE STATUS: ACTIVE[/bold green]   •   "
        f"⚔️ [bold gold1]COMMANDER PROTOCOL: SECURED[/bold gold1]",
        style="bold"
    )
    layout["ticker"].update(Panel(Align.center(ticker_text), border_style="grey37"))

def boot_sequence():
    console.clear()
    tasks = ["INITIALIZING OVERLORD KERNEL...", "AUTHENTICATING COMMANDER CLEARANCE...", "SYNCING GLOBAL LIQUIDITY MAP...", "CALIBRATING SENTIMENT RADAR...", "LINKING SACRED DOCTRINE v4.0...", "ARMING CHAIN REACTION SNIPER...", "DECRYPTING INSTITUTIONAL DATA...", "STABILIZING NEURAL WAVEFORM...", "UPLINKING TO MARKAS BESAR...", "OVERLORD SYSTEM ONLINE!"]
    with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"), BarColumn(bar_width=40, complete_style="gold1"), console=console, transient=True) as progress:
        for i, task_name in enumerate(tasks):
            t = progress.add_task(f"[ {i+1}/10 ] {task_name}", total=100)
            while not progress.finished:
                progress.update(t, advance=random.uniform(5, 15)); time.sleep(0.08); 
                if progress.tasks[i].finished: break
    logo = """[bold gold1]
     _______ _    _          _____ _   _   _____  ______          _____ _______ _____ ____  _   _ 
    |  _____| |  | |   /\   |_   _| \ | | |  __ \|  ____|   /\   / ____|__   __|_   _/ __ \| \ | |
    | |     | |__| |  /  \    | | |  \| | | |__) | |__     /  \ | |       | |    | || |  | |  \| |
    | |     |  __  | / /\ \   | | | . ` | |  _  /|  __|   / /\ \| |       | |    | || |  | | . ` |
    | |_____| |  | |/ ____ \ _| |_| |\  | | | \ \| |____ / ____ \ |____   | |   _| || |__| | |\  |
    |_______|_|  |_/_/    \_\_____|_| \_| |_|  \_\______/_/    \_\_____|  |_|  |_____\____/|_| \_|
    [/bold gold1]
    [bold cyan]                       PROPERTY OF COMMANDER DADANG | v4.0 OVERLORD[/bold cyan]
    """
    console.clear(); console.print("\n" * 3); console.print(Align.center(logo)); time.sleep(5.0); console.print(Align.center("[bold blink green]UPLINK ESTABLISHED. ACCESS GRANTED.[/bold blink green]")); time.sleep(1.5)

def main():
    symbol = "XAUUSD"
    if not connect_mt5(): return
    boot_sequence()
    settings = load_settings(); analyst = SacredDoctrineAnalyst(symbol, master_tf=settings.get("master_tf", "H4"))
    bs_analyst = BSTradingAnalyst(symbol)
    executor = ChainReactionExecutor(symbol, magic_number=settings.get("magic_number", 2026))
    layout = make_layout(); frame = 0; last_strike_time_chain = 0; last_strike_time_bs = 0
    feed.add(f"🔗 OVERLORD ONLINE: Standing by for Market Ignition")
    feed.add(f"⚖️ DOCTRINE ARMED: Time Law v4.0 Enforced")
    feed.add(f"🛰️ RADAR ACTIVE: Scanning for {symbol} Liquidity")
    with Live(layout, refresh_per_second=8, screen=True) as live:
        while True:
            try:
                analyst.update(); bs_analyst.update(analyst); settings = load_settings()
                events = executor.monitor_positions(analyst)
                for e in events: feed.add(e)
                
                # 1. Sultan Sniper Chain Reaction - Independent Execution
                signal = analyst.get_strike_signal()
                if signal and settings.get("auto_trade"):
                    if time.time() - last_strike_time_chain > 300:
                        positions = mt5.positions_get(symbol=symbol, magic=settings.get("magic_number", 2026))
                        chain_pos = [p for p in positions if p.comment.startswith("Chain_")] if positions else []
                        if len(chain_pos) < settings.get("max_layers", 3):
                            success, msg = executor.execute_strike(signal['action'], analyst, lot=settings.get("lot_size", 0.01), comment=f"Chain_{signal['tf']}")
                            feed.add(msg)
                            if success: last_strike_time_chain = time.time()
                
                # 2. BS Trading SOP - Independent Execution
                if settings.get("enable_bs_trading"):
                    bs_signal = bs_analyst.get_bs_signal()
                    if bs_signal:
                        if time.time() - last_strike_time_bs > 300:
                            positions = mt5.positions_get(symbol=symbol, magic=settings.get("magic_number", 2026))
                            bs_pos = [p for p in positions if p.comment.startswith("BS_")] if positions else []
                            if len(bs_pos) < settings.get("max_layers", 3):
                                lot_multiplier = 0.5 if bs_signal['level'] == 1 else 1.0
                                success, msg = executor.execute_strike(
                                    direction=bs_signal['action'],
                                    analyst=analyst,
                                    lot=settings.get("lot_size", 0.01) * lot_multiplier,
                                    comment=f"BS_L{bs_signal['level']}",
                                    tp_price=bs_signal['tp'],
                                    sl_price=bs_signal['sl']
                                )
                                feed.add(msg)
                                if success: last_strike_time_bs = time.time()
                                
                update_layout(layout, analyst, bs_analyst, executor, symbol, settings, frame)
                frame += 1; time.sleep(0.1)
            except KeyboardInterrupt: break
            except Exception as e: feed.add(f"ERR: {str(e)}"); time.sleep(2)

if __name__ == "__main__":
    main()
