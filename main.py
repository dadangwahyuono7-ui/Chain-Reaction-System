import time
import MetaTrader5 as mt5
import json
import os
import random
import math
import requests
import xml.etree.ElementTree as ET
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

_RED_FOLDERS = [
    "🔴 KAMIS 01:00 WIB: FOMC Meeting Minutes (High Impact)",
    "🔴 KAMIS 20:45 WIB: Flash Manufacturing PMI (High Impact)",
    "📡 INTEL: Kevin Warsh (New Fed Chair) stance is Hawkish.",
    "🔥 GEOPOLITICS: Hormuz Strait tensions increase Gold demand.",
    "📊 SENTIMENT: Markets pricing in 'No Rate Cut' for 2026."
]

def fetch_live_news():
    """Fetch ForexLive gold RSS with one retry. Falls back to static red folders."""
    for attempt in range(2):
        try:
            r = requests.get("https://www.forexlive.com/feed/gold", timeout=3)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                headlines = [f"📡 LIVE: {item.find('title').text}"
                             for item in root.findall(".//item")[:3]]
                return _RED_FOLDERS + headlines
        except Exception:
            if attempt == 0:
                time.sleep(1)
    return _RED_FOLDERS

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
        # Overnight sessions (e.g., Sydney 22:00–06:00) wrap past midnight
        if start < end:
            is_active = start <= now.hour < end
        else:
            is_active = now.hour >= start or now.hour < end
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
        Layout(name="sentiment", size=5)
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

def update_layout(layout, analyst, executor, symbol, settings, frame):
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
    
    header_text = Text.assemble(
        (f" {pulse_char} CHAIN REACTION ", f"bold {theme_color}"),
        (" [ ", "blink white"),
        ("OVERLORD CLEARANCE", "blink bold white"),
        (" ] ", "blink white"),
        (" | BY: COMMANDER DADANG ", "bold yellow"),
        (f" | {symbol}: ", "white"),
        (bid, "bold green"),
        ("/", "white"),
        (ask, "bold red"),
        (f" | {datetime.now().strftime('%H:%M:%S')}", "dim white"),
    )
    layout["header"].update(Panel(Align.center(header_text), style=f"bold {theme_color}"))
    layout["greeting"].update(Panel(Align.center(Text(get_commander_greeting(), style="bold cyan")), border_style="dim cyan"))

    # Core Sync & Stats
    acc = mt5.account_info()
    acc_table = Table(box=None, expand=True)
    acc_table.add_column("Key", style="cyan")
    acc_table.add_column("Val", style="bold magenta", justify="right")
    if acc:
        dd_pct = ((acc.balance - acc.equity) / acc.balance * 100) if acc.balance > 0 else 0
        eq_pct = (acc.equity / acc.balance * 100) if acc.balance > 0 else 100
        eq_bar_w = 10
        eq_filled = int(eq_pct / 100 * eq_bar_w)
        eq_col = "green" if eq_pct >= 99 else "yellow" if eq_pct >= 97 else "red"
        eq_bar = f"[{eq_col}]{'█' * eq_filled}[/][dim]{'░' * (eq_bar_w - eq_filled)}[/]"
        acc_table.add_row("ACC", f"{acc.login}")
        acc_table.add_row("BAL", f"[white]{acc.balance:,.0f}[/]")
        acc_table.add_row("EQTY", f"[{eq_col}]{acc.equity:,.0f}[/]")
        acc_table.add_row("DD%", f"[{'red' if dd_pct > 1 else 'green'}]{dd_pct:.2f}%[/]")
        acc_table.add_row("", eq_bar)
    acc_table.add_row("[cyan]UPLINK[/]", f"[bold cyan]{'█' * int(math.sin(frame * 0.8) * 4 + 5)}[/]")
    layout["account"].update(Panel(acc_table, title=f"[{title_style}]{sync_icon} CORE SYNC[/{title_style}]", border_style="cyan" if frame % 4 != 0 else "bright_cyan"))

    stats = get_real_stats(settings.get("magic_number", 2026)); stats_table = Table(box=None, expand=True)
    stats_table.add_column("Stat", style="yellow"); stats_table.add_column("Val", style="bold white", justify="right")
    stats_table.add_row("WIN RATE", f"{stats['win_rate']:.0f}%"); stats_table.add_row("STRIKES", str(stats['strikes'])); stats_table.add_row("PnL TODAY", f"[green]+{stats['pnl']:,.2f}[/]" if stats['pnl'] >= 0 else f"[red]{stats['pnl']:,.2f}[/]")
    stats_table.add_row("", ""); stats_table.add_row("[yellow]PROC[/]", f"[bold yellow]{'█' * int(math.cos(frame * 0.6) * 4 + 5)}[/]")
    layout["stats"].update(Panel(stats_table, title=f"[{title_style}]📊 LIVE STATS[/{title_style}]", border_style="yellow" if frame % 4 != 2 else "bright_yellow"))

    # Sentiment Radar — proper block bars
    buy_pct, sell_pct = analyst.get_total_sentiment()
    bw = 14
    b_filled = int(buy_pct / 100 * bw)
    s_filled = int(sell_pct / 100 * bw)
    b_bar = f"[green]{'█' * b_filled}[/][dim]{'░' * (bw - b_filled)}[/]"
    s_bar = f"[red]{'█' * s_filled}[/][dim]{'░' * (bw - s_filled)}[/]"
    dominant = "BUY" if buy_pct > sell_pct else "SELL"
    dom_col = "green" if dominant == "BUY" else "red"
    _regime_s, _ = analyst.get_market_regime()
    reg_col_s = "green" if _regime_s == "TRENDING" else "yellow" if _regime_s == "RANGING" else "red"
    reg_icon_s = "📈" if _regime_s == "TRENDING" else "〰" if _regime_s == "RANGING" else "⚠"
    pulse_dot = "[blink bold green]◆[/]" if dominant == "BUY" else "[blink bold red]◆[/]"
    sent_text = Text.from_markup(
        f" BUY  {b_bar} [green]{buy_pct:.0f}%[/]\n"
        f" SELL {s_bar} [red]{sell_pct:.0f}%[/]\n"
        f" [{reg_col_s}]{reg_icon_s} {_regime_s}[/]  {pulse_dot} [{dom_col}]{dominant}[/]"
    )
    layout["sentiment"].update(Panel(sent_text, title=f"[{title_style}]⚡ RADAR[/{title_style}]", border_style="bright_magenta"))

    # CHAIN STORYLINE STATUS PANEL — live CMP→VR→CF progress
    _cs = analyst.get_chain_status()
    _dir    = _cs["direction"]
    _opp    = _cs["opposite"]
    _d_col  = "green" if _dir == "BUY" else "red" if _dir == "SELL" else "white"

    def _step_icon(ok, blink_ok=False):
        if ok:
            return "[blink bold green]🔥[/]" if blink_ok else "[green]✅[/]"
        return "[dim]⬜[/]"

    # Step 1 — M30 CMP
    s1_icon = _step_icon(_cs["step1_ok"])
    s1_lbl  = f"[{_d_col}]{_dir}[/]" if _cs["step1_ok"] else "[dim]WAIT[/]"
    s1_note = "M30 arah terkunci" if _cs["step1_ok"] else "Tunggu breakout M30"

    # Step 2 — M15 state (VR ke M30 atau SOLID)
    if _cs["m15_is_vr"]:
        s2_icon = _step_icon(True)
        s2_lbl  = f"[deep_sky_blue1]VR {_opp}[/]"
        s2_note = "M15 menguji M30 CMP ⚠"
    elif _cs["m15_solid"]:
        s2_icon = "[green]🔒[/]"
        s2_lbl  = f"[green]SOLID {_dir}[/]"
        s2_note = "M15 aligned — M30 aman"
    else:
        s2_icon = "[dim]⬜[/]"
        s2_lbl  = f"[dim]WAIT[/]"
        s2_note = ""

    # Step 3 — CF type + label
    cf_fired = _cs["cf_ready"]
    s3_icon  = _step_icon(cf_fired, blink_ok=True)
    cf_type  = _cs.get("cf_type", "")
    if cf_fired:
        if cf_type == "MINOR_CF":
            cf_lbl  = "[blink bold green]MINOR CF ✅[/]"
            cf_note = "M5 VR→CF | SL=M5 | TP=M15"
        elif cf_type == "CF_LOW":
            cf_lbl  = "[blink bold green]CF LOW 🔥[/]"
            cf_note = "M15 CF | SL=M15 | TP=M30"
        else:
            cf_lbl  = "[blink bold yellow]CF HIGH ⚡[/]"
            cf_note = "M5 CF | SL=M15 | TP=M30"
    else:
        cf_lbl  = "[dim]TUNGGU CF[/]"
        cf_note = "M5 atau M15 balik ke arah M30"

    # M30 Stability (hanya relevan saat M15 VR)
    if _cs["m30_broken"]:
        stab_txt = "[blink bold red]⚠ INVALID — VR break M30![/]"
    elif _cs["m15_is_vr"]:
        stab_txt = "[green]🔒 LOCKED — M30 stable[/]"
    elif _cs["m15_solid"]:
        stab_txt = "[green]✅ KUAT — M15 solid, M30 tidak diuji[/]"
    else:
        stab_txt = "[dim]—[/]"

    # Next action
    if not _cs["step1_ok"]:
        next_txt = "[dim]Scan M30 SNR breakout...[/]"
    elif _cs["m30_broken"]:
        next_txt = "[bold red]Setup batal! Cari M30 setup baru.[/]"
    elif cf_fired and cf_type == "MINOR_CF":
        next_txt = f"[blink bold green]🎯 SAFEST FIRE! M5 CF | SL=M5 SNR | TP=M15 SNR[/]"
    elif cf_fired and cf_type == "CF_LOW":
        next_txt = f"[blink bold green]🎯 FIRE! CF Low Risk | SL=M15 SNR | TP=M30 SNR[/]"
    elif cf_fired and cf_type == "CF_HIGH":
        next_txt = f"[blink bold yellow]⚡ FIRE! CF High Risk | SL=M15 SNR | TP=M30 SNR[/]"
    elif _cs["m15_solid"]:
        next_txt = f"[cyan]Tunggu M5 flip [{_d_col}]{_opp}[/] (VR ke M15) → balik [{_d_col}]{_dir}[/] (MINOR CF)[/]"
    elif _cs["m15_is_vr"]:
        next_txt = f"[cyan]Tunggu M5 CF [{_d_col}]{_dir}[/] (High) atau M15 balik [{_d_col}]{_dir}[/] (Low)[/]"
    else:
        next_txt = f"[cyan]Tunggu M15 solid [{_d_col}]{_dir}[/] + M5 VR, atau M15 VR [{_d_col}]{_opp}[/] ke M30[/]"

    # Macro role label for M30 vs H4
    macro = _cs.get("macro_role", "SOLID_H4")
    if macro == "VR_H4":
        macro_lbl = "[blink bold red]🚫 M30 VR ke H4 — BLOCK[/]"
    elif macro == "CF_HIGH_H4":
        macro_lbl = f"[bold magenta]⚡ M30 CF High Risk ke H4 (via H1 VR) — POWER[/]"
    elif macro == "CF_H4":
        macro_lbl = f"[bold cyan]📈 H1 VR → M30 CF ke H4 — BUILDING[/]"
    else:
        macro_lbl = f"[white]M30 SOLID ke H4 — NORMAL[/]"

    # ── Market Regime ─────────────────────────────────────────────────────────
    _regime, _regime_msg = analyst.get_market_regime()
    if _regime == "TRENDING":
        regime_lbl = f"[bold green]📈 TRENDING[/] — {_regime_msg}"
    elif _regime == "RANGING":
        regime_lbl = f"[bold yellow]〰 RANGING[/] — {_regime_msg}"
    else:
        regime_lbl = f"[blink bold red]⚠ SIDEWAYS[/] — {_regime_msg}"

    # ── CASCADE CHAIN visual: H4 → H1 → M30 → M15 → M5 ─────────────────────
    # VR/CF = CMP di TF masing-masing, hanya konteks parent yang memberi label
    _h4_dir  = analyst.states["H4"].cmp
    _h4_col  = "green" if _h4_dir == "BUY" else "red" if _h4_dir == "SELL" else "white"
    _d_arr   = "▲" if _h4_dir == "BUY" else "▼" if _h4_dir == "SELL" else "?"
    _c_arr   = "▼" if _h4_dir == "BUY" else "▲"
    _roles   = _cs.get("cascade_roles", {})
    _depth   = _cs.get("cascade_depth", 0)

    def _tf_chip(tf_name):
        role = _roles.get(tf_name, "WAIT")
        st   = analyst.states[tf_name]
        if role == "WAIT":
            return f"[dim]{tf_name}?[/]"
        if role == "VR":
            col  = "deep_sky_blue1"
            arr  = _c_arr
            tag  = "VR"
        elif role == "CF":
            col  = _h4_col
            arr  = _d_arr
            tag  = "CF"
        else:  # CMP
            col  = _h4_col
            arr  = _d_arr
            tag  = ""
        label = f"{tf_name}{arr}" + (f"[{tag}]" if tag else "")
        return f"[{col}]{label}[/]"

    cascade_line = (
        f"  [{_h4_col}]H4{_d_arr}[/] ──▶ "
        + " ──▶ ".join(_tf_chip(tf) for tf in ["H1", "M30", "M15", "M5"])
    )

    # Cascade depth warning
    if _depth == 0:
        depth_txt = "[green]DEPTH 0 — semua aligned, momentum kuat[/]"
    elif _depth == 1:
        depth_txt = f"[cyan]DEPTH 1 — {_cs['cascade_tfs']} VR, minor retracement[/]"
    elif _depth == 2:
        depth_txt = f"[yellow]DEPTH 2 — {_cs['cascade_tfs']} VR, tunggu CF[/]"
    elif _depth >= 3:
        depth_txt = f"[blink bold red]DEPTH {_depth} — CASCADE DALAM, JANGAN ENTRY[/]"
    else:
        depth_txt = "[dim]—[/]"

    # Signal readiness progress bar
    _steps_done = sum([_cs['step1_ok'], _cs['m15_is_vr'] or _cs['m15_solid'], _cs['cf_ready']])
    _ready_pct  = int(_steps_done / 3 * 100)
    _rw = 16
    _r_filled = int(_steps_done / 3 * _rw)
    _r_col = "blink bold green" if _steps_done == 3 else "yellow" if _steps_done >= 1 else "dim"
    _ready_bar = f"[{_r_col}]{'▰' * _r_filled}[/][dim]{'▱' * (_rw - _r_filled)}[/]"
    _ready_lbl = f"[{_r_col}]{_steps_done}/3  {_ready_pct}%[/]"

    storyline = Text.from_markup(
        f"  [bold white]CASCADE CHAIN  (VR=CF=CMP di TF masing-masing)[/bold white]\n"
        f"{cascade_line}\n"
        f"  [dim]REGIME:[/dim] {regime_lbl}\n"
        f"  [dim]DEPTH :[/dim] {depth_txt}\n"
        f"\n"
        f"  [dim]SIGNAL READY:[/dim] {_ready_bar} {_ready_lbl}\n"
        f"  {s1_icon} [dim]M30 CMP:[/dim] {s1_lbl}  [dim italic]{s1_note}[/dim italic]\n"
        f"  {s2_icon} [dim]M15    :[/dim] {s2_lbl}  [dim italic]{s2_note}[/dim italic]\n"
        f"  {s3_icon} [dim]CF     :[/dim] {cf_lbl}  [dim italic]{cf_note}[/dim italic]\n"
        f"  [dim]M30/H4 :[/dim] {macro_lbl}\n"
        f"  [dim]▶ NEXT :[/dim] {next_txt}"
    )
    chain_border = "blink bold green" if cf_fired else ("red" if _cs["m30_broken"] else "cyan")

    # Hierarchy Matrix — chain-aware STATUS column
    cs = analyst.get_chain_status()
    m30_state = analyst.states["M30"]
    m15_state = analyst.states["M15"]
    m5_state  = analyst.states["M5"]

    def chain_role(tf, st):
        """Return chain role label + color for each TF in context of current setup."""
        if tf in ("MN1", "W1", "D1"):
            lbl = "MACRO"
            col = "gold1" if st.cmp == cs["direction"] else "dim"
        elif tf == "H4":
            lbl = "MASTER"
            col = "gold1"
        elif tf == "H1":
            if st.cmp != "WAIT" and st.cmp != analyst.states["H4"].cmp:
                lbl = "H1 VR"; col = "deep_sky_blue1"
            else:
                lbl = "H1 CMP"; col = "white"
        elif tf == "M30":
            lbl = "SETUP CMP" if st.cmp != "WAIT" else "M30 WAIT"
            col = "bold cyan" if st.cmp != "WAIT" else "dim"
        elif tf == "M15":
            if cs["m15_is_vr"]:
                lbl = "VR ACTIVE ⚡"; col = "deep_sky_blue1"
            elif cs["m15_solid"]:
                lbl = "SOLID 🔒"; col = "green"
            else:
                lbl = "STANDBY"; col = "dim"
        elif tf == "M5":
            if cs["cf_ready"] and cs["cf_type"] == "MINOR_CF":
                lbl = "MINOR CF ✅"; col = "blink bold green"
            elif cs["cf_ready"] and cs["cf_type"] in ("CF_HIGH", "CF_LOW"):
                lbl = f"{cs['cf_type']} 🔥"; col = "blink bold green"
            elif cs["m15_solid"] and st.cmp != cs["direction"] and st.cmp != "WAIT":
                lbl = "VR→M15"; col = "yellow"
            elif cs["m15_is_vr"] and st.cmp != cs["direction"]:
                lbl = "VR"; col = "yellow"
            elif cs["m15_is_vr"] and st.cmp == cs["direction"]:
                lbl = "CF ZONE"; col = "green"
            else:
                lbl = "STANDBY"; col = "dim"
        else:
            lbl = st.status; col = "white"
        return lbl, col

    matrix_table = Table(expand=True, border_style="grey37")
    matrix_table.add_column("TF",    justify="center", style="bold white")
    matrix_table.add_column("CMP",   justify="center")
    matrix_table.add_column("ROLE",  justify="center")
    matrix_table.add_column("SNR",   justify="center", style="dim")
    tfs = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]
    scanning_idx = frame % len(tfs)
    for i, tf in enumerate(tfs):
        st = analyst.states[tf]
        is_scanning = (i == scanning_idx)
        blink = "[blink]" if is_scanning and frame % 2 == 0 else ""
        c = "green" if st.cmp == "BUY" else "red" if st.cmp == "SELL" else "white"
        lbl, r_col = chain_role(tf, st)
        # Row background based on chain role priority
        if is_scanning:
            row_style = "bold on grey19"
        elif "CF READY" in lbl or "MINOR CF" in lbl:
            row_style = "on dark_green"
        elif "VR ACTIVE" in lbl or "VR→M15" in lbl:
            row_style = "on navy_blue"
        elif "SOLID" in lbl:
            row_style = "on dark_slate_gray2" if frame % 2 == 0 else ""
        elif "MASTER" in lbl:
            row_style = "on grey15"
        else:
            row_style = ""
        matrix_table.add_row(
            f"{'📡' if is_scanning else '  '} {tf}",
            f"[{c}]{st.cmp}[/]",
            f"{blink}[{r_col}]{lbl}[/]{blink if blink else ''}",
            f"{st.sup:.1f}/{st.res:.1f}",
            style=row_style,
        )

    matrix_table.add_row("", "", "", "")
    aligned_tfs = sum(1 for tf in tfs if analyst.states[tf].cmp == analyst.states["H4"].cmp)
    wib_str = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%H:%M:%S")
    matrix_table.add_row(
        "[bold cyan]📡 TELEMETRY[/]",
        f"[green]ALIGN: {aligned_tfs}/8[/]",
        f"[yellow]WIB: {wib_str}[/]",
        f"[green]LATENCY: {random.randint(11, 24)}ms[/]",
    )
    # Signal summary rows — fill empty space with live status
    _cs_m = analyst.get_chain_status()
    _steps_m = sum([_cs_m['step1_ok'], _cs_m['m15_is_vr'] or _cs_m['m15_solid'], _cs_m['cf_ready']])
    _rw_m = 8
    _rf_m = int(_steps_m / 3 * _rw_m)
    _rc_m = "green" if _steps_m == 3 else "yellow" if _steps_m >= 1 else "dim"
    _rbar_m = f"[{_rc_m}]{'▰' * _rf_m}{'▱' * (_rw_m - _rf_m)}[/]"
    _depth_m = _cs_m.get('cascade_depth', 0)
    _dc_m = "green" if _depth_m == 0 else "yellow" if _depth_m <= 2 else "red"
    _dbar_m = f"[{_dc_m}]{'█' * min(_depth_m, 4)}{'░' * (4 - min(_depth_m, 4))}[/]"
    _regime_m, _ = analyst.get_market_regime()
    _rc2_m = "green" if _regime_m == "TRENDING" else "yellow" if _regime_m == "RANGING" else "red"
    cf_type_m = _cs_m.get('cf_type', '')
    cf_lbl_m = f"[blink green]{cf_type_m}[/]" if _cs_m['cf_ready'] else "[dim]WAIT[/]"
    matrix_table.add_row(
        "[bold cyan]⚡ SIGNAL[/]",
        _rbar_m,
        f"[{_rc_m}]{_steps_m}/3 READY[/]",
        cf_lbl_m,
    )
    matrix_table.add_row(
        "[dim]CASCADE[/]",
        _dbar_m,
        f"[{_dc_m}]DEPTH {_depth_m}[/]",
        f"[{_rc2_m}]{_regime_m}[/]",
    )
    layout["matrix"].update(Panel(matrix_table, title=f"[{title_style}]HIERARCHY MATRIX[/{title_style}]", border_style="magenta"))

    # ── CHAIN STORYLINE → bs_matrix (kanan, lebar, full height) ─────────────
    # Commander Dadang identity banner — di bawah storyline
    blink_dot = "[blink green]●[/blink green]" if frame % 2 == 0 else "[green] [/green]"
    pulse_colors = ["bold bright_cyan", "bold yellow", "bold bright_green", "bold bright_magenta"]
    col_name = pulse_colors[(frame // 2) % len(pulse_colors)]
    commander_banner = Align.center(
        Text.from_markup(
            f"[bold red]⚔️[/bold red]  [{col_name}]D A D A N G   W A H Y U O N O[/{col_name}]  {blink_dot}",
            style="bold"
        )
    )
    chain_panel_content = RichGroup(storyline, Text(""), commander_banner)
    layout["bs_matrix"].update(Panel(
        chain_panel_content,
        title=f"[{title_style}]🎯 CHAIN REACTION STORYLINE[/{title_style}]",
        border_style=chain_border,
    ))

    # Liquidity Map
    h4 = analyst.states["H4"]; d1 = analyst.states["D1"]; cp = tick.bid if tick else 0
    def get_map_v2(st, tf_label, col):
        if st.sup == 0 or st.res == 0:
            return f"[{col}]{tf_label}[/] [dim]SCANNING...[/]", ""
        range_size = st.res - st.sup
        if range_size <= 0:
            return f"[{col}]{tf_label}[/] [dim]SCANNING...[/]", ""
        pct = max(0.0, min(1.0, (cp - st.sup) / range_size))
        pos = int(pct * 22)
        bar = list("─" * 22)
        if 0 <= pos < 22: bar[pos] = "[blink bold yellow]⚡[/blink bold yellow]"
        # Color the zone: bottom 30% green (near sup), top 30% red (near res)
        bar_str = ''.join(bar)
        dist_res = st.res - cp
        dist_sup = cp - st.sup
        pct_to_res = (1 - pct) * 100
        zone = "[green]SUP ZONE[/]" if pct < 0.3 else "[red]RES ZONE[/]" if pct > 0.7 else "[yellow]MID ZONE[/]"
        line1 = f"[{col}]{tf_label}[/] [dim green]{st.sup:.1f}[/dim green] |{bar_str}| [dim red]{st.res:.1f}[/dim red]"
        line2 = f"       [dim]↑RES {dist_res:.1f}$ ({pct_to_res:.0f}%)[/] | [dim]↓SUP {dist_sup:.1f}$[/] | {zone}"
        return line1, line2
    liq_table = Table(box=None, expand=True)
    h4_l1, h4_l2 = get_map_v2(h4, "H4", "bold cyan")
    d1_l1, d1_l2 = get_map_v2(d1, "D1", "bold gold1")
    liq_table.add_row(h4_l1)
    liq_table.add_row(h4_l2)
    liq_table.add_row(d1_l1)
    liq_table.add_row(d1_l2)
    layout["liquidity"].update(Panel(liq_table, title=f"[{title_style}]⚡ INSTITUTIONAL LIQUIDITY MAP[/{title_style}]", border_style="cyan"))

    # 10. GLOBAL INTEL & NEWS (Live RSS + Forex Factory Red Radar)
    news_ttl = settings.get("news_refresh_seconds", 300)
    now_ts = time.time()
    if not hasattr(update_layout, "_cached_news") or \
       (now_ts - getattr(update_layout, "_news_last_fetch", 0)) >= news_ttl:
        update_layout._cached_news = fetch_live_news()
        update_layout._news_last_fetch = now_ts
    
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
    settings   = load_settings()
    analyst  = SacredDoctrineAnalyst(symbol, master_tf=settings.get("master_tf", "H4"))
    executor = ChainReactionExecutor(symbol, magic_number=settings.get("magic_number", 2026))
    layout = make_layout()
    frame = 0
    last_strike_time_chain = 0
    feed.add(f"🔗 OVERLORD ONLINE: Standing by for Market Ignition")
    feed.add(f"⚖️ DOCTRINE ARMED: Time Law v4.0 Enforced")
    feed.add(f"🛰️ RADAR ACTIVE: Scanning for {symbol} Liquidity")
    with Live(layout, refresh_per_second=8, screen=True) as live:
        while True:
            try:
                settings = load_settings()
                executor.update_settings(settings)  # sync all magic numbers from config

                analyst.update()

                events = executor.monitor_positions(analyst)
                for e in events:
                    feed.add(e)

                magic = settings.get("magic_number", 2026)
                max_layers = settings.get("max_layers", 3)
                lot_size = settings.get("lot_size", 0.01)

                # Single positions fetch shared by both engines — prevents double-open on same tick
                all_positions = mt5.positions_get(symbol=symbol, magic=magic) or []
                total_open = len(all_positions)

                # 1. Chain Reaction Sniper — Independent Execution
                signal = analyst.get_strike_signal()
                if signal and settings.get("auto_trade"):
                    if time.time() - last_strike_time_chain > 300:
                        chain_pos = [p for p in all_positions if p.comment.startswith("Chain_")]
                        if len(chain_pos) < max_layers and total_open < max_layers:
                            success, msg = executor.execute_strike(
                                signal['action'], analyst,
                                comment=f"Chain_{signal['type']}_{signal['tf']}",
                                tp_tf=signal.get('tp_tf'),
                                sl_tf=signal.get('sl_tf'),
                                settings=settings
                            )
                            feed.add(msg)
                            if success:
                                last_strike_time_chain = time.time()
                                # Refresh positions count so BS engine sees the new order
                                all_positions = mt5.positions_get(symbol=symbol, magic=magic) or []
                                total_open = len(all_positions)

                update_layout(layout, analyst, executor, symbol, settings, frame)
                frame += 1
                time.sleep(0.1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                feed.add(f"ERR: {str(e)}")
                time.sleep(2)

if __name__ == "__main__":
    main()
