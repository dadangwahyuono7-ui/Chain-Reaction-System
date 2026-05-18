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
from rich.console import Group as RichGroup
from rich import box as rich_box
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

_STATIC_INTEL = [
    "🔴 KAMIS 01:00 WIB — FOMC Meeting Minutes (High Impact)",
    "🔴 KAMIS 20:45 WIB — Flash Manufacturing PMI (High Impact)",
    "📡 INTEL: Kevin Warsh (New Fed Chair) stance is Hawkish",
    "🔥 GEOPOLITICS: Hormuz Strait tensions increase Gold demand",
    "📊 SENTIMENT: Markets pricing in 'No Rate Cut' for 2026",
]

_NEWS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

_RSS_SOURCES = [
    ("ForexLive",   "https://www.forexlive.com/feed/"),
    ("Investing",   "https://www.investing.com/rss/news_14.rss"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines"),
]

fetch_live_news._last_source = "STATIC"
fetch_live_news._last_fetch_wib = "──:──"

def fetch_live_news():
    """Try multiple RSS sources with proper headers. Falls back to static intel."""
    gold_kw = {"gold","xauusd","commodit","metal","fed","fomc","rate","dollar","usd"}
    wib = pytz.timezone("Asia/Jakarta")

    for source_name, url in _RSS_SOURCES:
        for attempt in range(2):
            try:
                r = requests.get(url, headers=_NEWS_HEADERS, timeout=4)
                if r.status_code != 200:
                    break
                root  = ET.fromstring(r.content)
                items = root.findall(".//item")
                headlines = []
                for item in items:
                    t = item.find("title")
                    if t is None or not t.text:
                        continue
                    txt = t.text.strip()
                    if any(k in txt.lower() for k in gold_kw):
                        headlines.append(f"📡 {source_name.upper()}: {txt}")
                    if len(headlines) >= 4:
                        break
                if headlines:
                    fetch_live_news._last_source   = source_name
                    fetch_live_news._last_fetch_wib = datetime.now(wib).strftime("%H:%M")
                    return _STATIC_INTEL + headlines
            except Exception:
                if attempt == 0:
                    time.sleep(0.5)

    fetch_live_news._last_source    = "STATIC"
    fetch_live_news._last_fetch_wib = datetime.now(wib).strftime("%H:%M")
    return _STATIC_INTEL

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
        Layout(name="matrix", ratio=5),
        Layout(name="bs_matrix", ratio=6)
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

def _bar(filled, total, fill_char="█", empty_char="░", fill_color="green", empty_color="grey27"):
    f = int(filled)
    e = total - f
    return f"[{fill_color}]{fill_char * f}[/][{empty_color}]{empty_char * e}[/]"

def update_layout(layout, analyst, executor, symbol, settings, frame):
    BLINK = frame % 2 == 0
    title_colors = ["bold bright_cyan", "bold gold1", "bold bright_cyan", "bold white"]
    TS = title_colors[frame % 4]

    # ── LIVE TICK ──────────────────────────────────────────────────────────────
    tick   = mt5.symbol_info_tick(symbol)
    bid    = f"{tick.bid:.2f}" if tick else "──────"
    ask    = f"{tick.ask:.2f}" if tick else "──────"
    master = analyst.states[settings.get("master_tf", "H4")]
    theme  = "green" if master.cmp == "BUY" else "red" if master.cmp == "SELL" else "gold1"
    spin   = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][frame % 10]

    # ── HEADER ─────────────────────────────────────────────────────────────────
    header_text = Text.assemble(
        (f" {spin} ", f"bold {theme}"),
        ("CHAIN REACTION ", f"bold {theme}"),
        ("[ OVERLORD v4.0 ] ", "bold white"),
        ("  BY: COMMANDER DADANG    ", "bold yellow"),
        (f"{symbol}  ", "dim white"),
        (bid, "bold bright_green"),
        (" / ", "dim"),
        (ask, "bold bright_red"),
        (f"    {datetime.now().strftime('%H:%M:%S')} WIB", "dim cyan"),
    )
    layout["header"].update(Panel(Align.center(header_text), style=f"bold {theme}", padding=(0, 1)))
    layout["greeting"].update(
        Panel(Align.center(Text(get_commander_greeting(), style="italic cyan")),
              border_style="dim cyan", padding=(0, 0))
    )

    # ── STRATEGIC INTEL MARQUEE ─────────────────────────────────────────────────
    intel_raw = analyst.get_strategic_forecast()
    for tag in ["[bold yellow]","[bold green]","[bold cyan]","[bold blue]","[bold magenta]","[/]"]:
        intel_raw = intel_raw.replace(tag, "")
    _scroll_src = "    ◆    " + intel_raw
    _shift = (frame // 2) % len(_scroll_src)
    _scrolled = (_scroll_src[_shift:] + _scroll_src[:_shift])[:120]
    layout["intel"].update(
        Panel(Align.center(Text(_scrolled, style="bold gold1")),
              title=f"[{TS}]◈  STRATEGIC INTEL[/{TS}]", border_style="gold1", padding=(0, 0))
    )

    # ── ACCOUNT PANEL ──────────────────────────────────────────────────────────
    acc = mt5.account_info()
    acc_t = Table(box=None, expand=True, padding=(0, 1))
    acc_t.add_column("", style="dim cyan", width=6)
    acc_t.add_column("", style="bold white", justify="right")
    if acc:
        dd_pct  = ((acc.balance - acc.equity) / acc.balance * 100) if acc.balance > 0 else 0
        eq_pct  = (acc.equity  / acc.balance  * 100)               if acc.balance > 0 else 100
        eq_col  = "bright_green" if eq_pct >= 99 else "yellow" if eq_pct >= 97 else "red"
        dd_col  = "bright_green" if dd_pct < 0.5 else "yellow" if dd_pct < 2 else "red"
        eq_bar  = _bar(int(eq_pct / 100 * 12), 12, fill_color=eq_col, empty_color="grey27")
        acc_t.add_row("LOGIN",   f"[bright_white]{acc.login}[/]")
        acc_t.add_row("BAL",     f"[white]{acc.balance:,.0f}[/]")
        acc_t.add_row("EQUITY",  f"[{eq_col}]{acc.equity:,.0f}[/]")
        acc_t.add_row("DD",      f"[{dd_col}]{dd_pct:.2f}%[/]")
        acc_t.add_row("",        eq_bar)
    sync_icon = "📡" if BLINK else "🛰️"
    uplink_bar = _bar(int(math.sin(frame * 0.8) * 4 + 5), 10, fill_color="bright_cyan", empty_color="grey27")
    acc_t.add_row("UPLINK",  uplink_bar)
    layout["account"].update(
        Panel(acc_t, title=f"[{TS}]{sync_icon} CORE SYNC[/{TS}]",
              border_style="cyan", padding=(0, 0))
    )

    # ── LIVE STATS ──────────────────────────────────────────────────────────────
    stats   = get_real_stats(settings.get("magic_number", 2026))
    pnl_col = "bright_green" if stats['pnl'] >= 0 else "red"
    wr_col  = "bright_green" if stats['win_rate'] >= 60 else "yellow" if stats['win_rate'] >= 40 else "red"
    st_t    = Table(box=None, expand=True, padding=(0, 1))
    st_t.add_column("", style="dim yellow", width=9)
    st_t.add_column("", style="bold white", justify="right")
    st_t.add_row("WIN RATE",  f"[{wr_col}]{stats['win_rate']:.0f}%[/]")
    st_t.add_row("STRIKES",   str(stats['strikes']))
    st_t.add_row("PnL TODAY", f"[{pnl_col}]{'+' if stats['pnl']>=0 else ''}{stats['pnl']:,.2f}[/]")
    proc_bar = _bar(int(math.cos(frame * 0.6) * 4 + 5), 10, fill_color="gold1", empty_color="grey27")
    st_t.add_row("", "")
    st_t.add_row("PROC",  proc_bar)
    layout["stats"].update(
        Panel(st_t, title=f"[{TS}]📊 LIVE STATS[/{TS}]",
              border_style="yellow", padding=(0, 0))
    )

    # ── SENTIMENT RADAR ─────────────────────────────────────────────────────────
    buy_pct, sell_pct = analyst.get_total_sentiment()
    regime, _         = analyst.get_market_regime()
    bw = 12
    b_bar = _bar(int(buy_pct/100*bw),  bw, fill_color="bright_green", empty_color="grey27")
    s_bar = _bar(int(sell_pct/100*bw), bw, fill_color="bright_red",   empty_color="grey27")
    dom        = "BUY"  if buy_pct > sell_pct else "SELL"
    dom_col    = "bright_green" if dom == "BUY" else "bright_red"
    reg_col    = "bright_green" if regime == "TRENDING" else "yellow" if regime == "RANGING" else "red"
    reg_icon   = "▲" if regime == "TRENDING" else "≈" if regime == "RANGING" else "⚠"
    pulse_dot  = "[blink bold bright_green]◆[/]" if dom == "BUY" and BLINK else \
                 "[blink bold bright_red]◆[/]"   if dom == "SELL" and BLINK else \
                 "[dim]◆[/]"
    sent_t = Text.from_markup(
        f" [dim]BUY [/dim]  {b_bar} [{dom_col if dom=='BUY' else 'dim'}]{buy_pct:.0f}%[/]\n"
        f" [dim]SELL[/dim]  {s_bar} [{dom_col if dom=='SELL' else 'dim'}]{sell_pct:.0f}%[/]\n"
        f" [{reg_col}]{reg_icon} {regime}[/]   {pulse_dot} [{dom_col}]{dom}[/]"
    )
    layout["sentiment"].update(
        Panel(sent_t, title=f"[{TS}]⚡ RADAR[/{TS}]", border_style="magenta", padding=(0, 0))
    )

    # ── CHAIN STATUS DATA (shared) ──────────────────────────────────────────────
    _cs     = analyst.get_chain_status()
    _dir    = _cs["direction"]
    _opp    = _cs["opposite"]
    _d_col  = "bright_green" if _dir == "BUY" else "bright_red" if _dir == "SELL" else "white"
    cf_fired = _cs["cf_ready"]
    cf_type  = _cs.get("cf_type", "")
    _depth   = _cs.get("cascade_depth", 0)
    _roles   = _cs.get("cascade_roles", {})
    _h4_dir  = analyst.states["H4"].cmp
    _h4_col  = "bright_green" if _h4_dir == "BUY" else "bright_red" if _h4_dir == "SELL" else "white"
    _d_arr   = "▲" if _h4_dir == "BUY" else "▼" if _h4_dir == "SELL" else "·"
    _c_arr   = "▼" if _h4_dir == "BUY" else "▲"

    def _tf_chip(tf_name):
        role = _roles.get(tf_name, "WAIT")
        if role == "WAIT":   return f"[dim]{tf_name}?[/]"
        if role == "VR":     return f"[bright_cyan]{tf_name}{_c_arr}[VR][/]"
        if role == "CF":     return f"[{_h4_col}]{tf_name}{_d_arr}[CF][/]"
        return f"[{_h4_col}]{tf_name}{_d_arr}[/]"

    cascade_chips = " → ".join(_tf_chip(tf) for tf in ["H1","M30","M15","M5"])

    # Step icons
    def _sicon(ok):
        return ("[bright_green]✔[/]" if BLINK else "[green]✔[/]") if ok else "[dim]○[/]"

    s1_ok  = _cs["step1_ok"]
    s2_ok  = _cs["m15_is_vr"] or _cs["m15_solid"]
    s3_ok  = cf_fired

    # Step labels
    s1_lbl = f"[{_d_col}]{_dir}[/]" if s1_ok else "[dim]WAIT[/]"
    s1_sub = "M30 CMP locked" if s1_ok else "Tunggu breakout M30"

    if _cs["m15_is_vr"]:
        s2_lbl = "[bright_cyan]VR ACTIVE[/]"
        s2_sub = f"M15 menguji M30 ⚠"
    elif _cs["m15_solid"]:
        s2_lbl = "[bright_green]SOLID ✔[/]"
        s2_sub = "M15 aligned, M30 aman"
    else:
        s2_lbl = "[dim]STANDBY[/]"
        s2_sub = ""

    if cf_fired:
        if cf_type == "MINOR_CF":
            s3_lbl = "[blink bright_green]MINOR CF[/]" if BLINK else "[bright_green]MINOR CF[/]"
            s3_sub = "SL=M5 SNR  TP=M15 SNR"
        elif cf_type == "CF_LOW":
            s3_lbl = "[blink bright_green]CF  LOW[/]" if BLINK else "[bright_green]CF  LOW[/]"
            s3_sub = "SL=M15 SNR  TP=M30 SNR"
        else:
            s3_lbl = "[blink yellow]CF HIGH[/]" if BLINK else "[yellow]CF HIGH[/]"
            s3_sub = "SL=M15 SNR  TP=M30 SNR"
    else:
        s3_lbl = "[dim]WAIT[/]"
        s3_sub = "M5/M15 balik ke arah M30"

    macro_m = _cs.get("macro_role", "SOLID_H4")
    if macro_m == "VR_H4":
        macro_lbl = "[bright_red]M30 VR ← H4  BLOCK[/]"
    elif macro_m == "CF_HIGH_H4":
        macro_lbl = "[magenta]M30 CF HIGH RISK ← H4[/]"
    elif macro_m == "CF_H4":
        macro_lbl = "[cyan]H1 VR → M30 CF ← H4[/]"
    else:
        macro_lbl = "[white]M30 SOLID ← H4[/]"

    _dep_col   = "bright_green" if _depth==0 else "yellow" if _depth<=2 else "bright_red"
    _steps_done = int(s1_ok) + int(s2_ok) + int(s3_ok)
    _rw = 14
    _r_fill = int(_steps_done / 3 * _rw)
    _r_col  = "bright_green" if _steps_done == 3 else "yellow" if _steps_done >= 1 else "dim"
    _ready_bar = _bar(_r_fill, _rw, fill_color=_r_col, empty_color="grey27", fill_char="▰", empty_char="▱")

    if not s1_ok:
        next_txt = "Scan M30 SNR breakout..."
        next_col = "dim"
    elif _cs.get("m30_broken"):
        next_txt = "Setup BATAL — cari M30 baru"
        next_col = "bold bright_red"
    elif cf_fired and cf_type == "MINOR_CF":
        next_txt = "🎯 SAFEST ENTRY — FIRE!"
        next_col = "blink bold bright_green"
    elif cf_fired and cf_type == "CF_LOW":
        next_txt = "🎯 CF LOW — FIRE!"
        next_col = "blink bold bright_green"
    elif cf_fired and cf_type == "CF_HIGH":
        next_txt = "⚡ CF HIGH — FIRE!"
        next_col = "blink bold yellow"
    elif _cs["m15_solid"]:
        next_txt = f"Tunggu M5 flip {_opp} → {_dir} (MINOR CF)"
        next_col = "cyan"
    elif _cs["m15_is_vr"]:
        next_txt = f"Tunggu M5 CF {_dir} atau M15 balik {_dir}"
        next_col = "cyan"
    else:
        next_txt = f"Tunggu M15 solid {_dir} atau VR {_opp} ke M30"
        next_col = "cyan"

    # ── HIERARCHY MATRIX TABLE ──────────────────────────────────────────────────
    matrix_table = Table(
        box=rich_box.SIMPLE_HEAD, expand=True,
        header_style="bold white on grey19", show_edge=False,
        padding=(0, 1),
    )
    matrix_table.add_column("TF",   justify="center", style="bold white",   width=6)
    matrix_table.add_column("CMP",  justify="center",                       width=7)
    matrix_table.add_column("ROLE", justify="center",                       width=14)
    matrix_table.add_column("SUP",  justify="right",  style="dim green",    width=9)
    matrix_table.add_column("RES",  justify="right",  style="dim red",      width=9)

    tfs = ["MN1","W1","D1","H4","H1","M30","M15","M5"]
    scan_idx = frame % len(tfs)
    for i, tf in enumerate(tfs):
        st      = analyst.states[tf]
        scanning = (i == scan_idx)
        cmp_col  = "bright_green" if st.cmp=="BUY" else "bright_red" if st.cmp=="SELL" else "dim"
        role     = _roles.get(tf, "") if tf not in ("MN1","W1","D1","H4") else ""

        if tf in ("MN1","W1","D1"):
            r_lbl = "MACRO"; r_col = _h4_col if st.cmp==_h4_dir else "dim"
        elif tf == "H4":
            r_lbl = "MASTER"; r_col = "gold1"
        elif tf == "H1":
            r_lbl = "H1 VR" if (st.cmp!="WAIT" and st.cmp!=_h4_dir) else "H1 CMP"
            r_col = "bright_cyan" if "VR" in r_lbl else "white"
        elif tf == "M30":
            r_lbl = "SETUP CMP" if st.cmp!="WAIT" else "M30 WAIT"
            r_col = "bold cyan" if st.cmp!="WAIT" else "dim"
        elif tf == "M15":
            if _cs["m15_is_vr"]: r_lbl = "VR  ⚡"; r_col = "bright_cyan"
            elif _cs["m15_solid"]: r_lbl = "SOLID  ✔"; r_col = "bright_green"
            else: r_lbl = "STANDBY"; r_col = "dim"
        elif tf == "M5":
            if cf_fired and cf_type=="MINOR_CF": r_lbl="MINOR CF  ✔"; r_col="bright_green"
            elif cf_fired: r_lbl=f"{cf_type}  ✔"; r_col="bright_green"
            elif _cs["m15_solid"] and st.cmp!=_dir and st.cmp!="WAIT": r_lbl="VR→M15"; r_col="yellow"
            elif _cs["m15_is_vr"] and st.cmp!=_dir: r_lbl="VR"; r_col="yellow"
            elif _cs["m15_is_vr"] and st.cmp==_dir: r_lbl="CF ZONE"; r_col="cyan"
            else: r_lbl="STANDBY"; r_col="dim"
        else:
            r_lbl = st.cmp; r_col = "white"

        if scanning:           row_s = "on grey15"
        elif "MASTER" in r_lbl:row_s = "on grey11"
        elif "CF" in r_lbl and tf=="M5": row_s = "on dark_green"
        elif "VR" in r_lbl:    row_s = "on navy_blue"
        elif "SOLID" in r_lbl: row_s = "on dark_slate_gray3"
        else:                  row_s = ""

        prefix = "▶" if scanning else " "
        matrix_table.add_row(
            f"{prefix} {tf}",
            f"[{cmp_col}]{st.cmp}[/]",
            f"[{r_col}]{r_lbl}[/]",
            f"{st.sup:.1f}",
            f"{st.res:.1f}",
            style=row_s,
        )

    # Matrix footer rows
    aligned_n  = sum(1 for tf in tfs if analyst.states[tf].cmp == _h4_dir and _h4_dir!="WAIT")
    wib_now    = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%H:%M:%S")
    depth_bar  = _bar(min(_depth,5), 5, fill_color=_dep_col, empty_color="grey27", fill_char="█", empty_char="░")
    regime_str, _ = analyst.get_market_regime()
    reg_c = "bright_green" if regime_str=="TRENDING" else "yellow" if regime_str=="RANGING" else "bright_red"

    matrix_table.add_row("─────","─────","──────────","─────────","─────────")
    matrix_table.add_row(
        "[dim cyan]SYNC[/]",
        f"[bright_green]{aligned_n}/8[/]",
        f"[dim]{wib_now}[/]",
        "", f"[dim]{random.randint(11,24)}ms[/]"
    )
    matrix_table.add_row(
        "[dim cyan]DEPTH[/]",
        depth_bar,
        f"[{_dep_col}]D{_depth}[/]  [{reg_c}]{regime_str[:5]}[/]",
        "",
        f"[{_r_col}]{_steps_done}/3[/]"
    )
    chain_border = ("bright_green" if BLINK else "green") if cf_fired else \
                   ("bright_red" if _cs.get("m30_broken") else "cyan")
    layout["matrix"].update(
        Panel(matrix_table, title=f"[{TS}]▣  HIERARCHY MATRIX[/{TS}]",
              border_style="magenta", padding=(0, 0))
    )

    # ── CHAIN REACTION STORYLINE PANEL (bs_matrix) ─────────────────────────────
    # Direction banner
    dir_arrow = "▲" if _dir=="BUY" else "▼" if _dir=="SELL" else "·"
    dir_banner = Text.from_markup(
        f"  [{_d_col}]{dir_arrow} {_dir}[/]"
        f"  [dim]◆[/]  "
        f"[{_dep_col}]CASCADE DEPTH {_depth}[/]"
        f"  [dim]◆[/]  "
        f"[{_r_col}]SIGNAL {_steps_done}/3[/]"
        f"  {_ready_bar}"
    )

    # Cascade chain row
    cascade_text = Text.from_markup(
        f"  [{_h4_col}]H4{_d_arr}[/]  →  {cascade_chips}"
    )

    # Steps table
    steps_t = Table(
        box=rich_box.SIMPLE, expand=True, show_header=False,
        padding=(0, 2), show_edge=False,
    )
    steps_t.add_column("", width=3,  justify="center")
    steps_t.add_column("", width=7,  style="dim")
    steps_t.add_column("", width=14, justify="right")
    steps_t.add_column("", ratio=1,  style="dim italic")

    s1_rs = "on dark_green" if s1_ok else ""
    s2_rs = "on navy_blue" if _cs["m15_is_vr"] else "on dark_green" if _cs["m15_solid"] else ""
    s3_rs = ("on dark_green" if cf_type in ("MINOR_CF","CF_LOW") else "on dark_orange3") if cf_fired else ""

    steps_t.add_row(_sicon(s1_ok), "M30 CMP", s1_lbl, s1_sub, style=s1_rs)
    steps_t.add_row(_sicon(s2_ok), "M15",     s2_lbl, s2_sub, style=s2_rs)
    steps_t.add_row(_sicon(s3_ok), "CF ENTRY", s3_lbl, s3_sub, style=s3_rs)

    # Context table (macro + regime)
    ctx_t = Table(box=None, expand=True, show_header=False, padding=(0, 2))
    ctx_t.add_column("", width=8, style="dim")
    ctx_t.add_column("", ratio=1)
    ctx_t.add_row("M30/H4", macro_lbl)
    ctx_t.add_row("REGIME", f"[{reg_c}]{regime_str}[/]")

    # Next action banner
    next_panel = Panel(
        Align.center(Text.from_markup(f"[{next_col}]{next_txt}[/{next_col}]")),
        border_style=next_col.replace("blink ","").replace("bold ",""),
        height=3, padding=(0, 1),
    )

    # Commander identity
    pulse_c = ["bold bright_cyan","bold gold1","bold bright_green","bold magenta"][(frame//3)%4]
    blink_d = "[blink bright_green]◆[/]" if BLINK else "[bright_green]◆[/]"
    cmdr_banner = Align.center(
        Text.from_markup(
            f"[bold red]⚔[/]  [{pulse_c}]D A D A N G   W A H Y U O N O[/{pulse_c}]  {blink_d}",
        )
    )

    story_group = RichGroup(
        dir_banner,
        Text(""),
        cascade_text,
        Text("  " + "─" * 50, style="dim"),
        steps_t,
        Text("  " + "─" * 50, style="dim"),
        ctx_t,
        Text(""),
        next_panel,
        Text(""),
        cmdr_banner,
    )
    layout["bs_matrix"].update(
        Panel(story_group,
              title=f"[{TS}]⚡  CHAIN REACTION STORYLINE[/{TS}]",
              border_style=chain_border, padding=(0, 1))
    )

    # ── LIQUIDITY MAP ───────────────────────────────────────────────────────────
    h4s = analyst.states["H4"]
    d1s = analyst.states["D1"]
    cp  = tick.bid if tick else 0

    def _liq_row(st, label, col):
        if st.sup == 0 or st.res == 0:
            return f"[{col}]{label}[/]  [dim]SCANNING...[/]", ""
        rng  = st.res - st.sup
        if rng <= 0:
            return f"[{col}]{label}[/]  [dim]─[/]", ""
        pct  = max(0.0, min(1.0, (cp - st.sup) / rng))
        pos  = int(pct * 24)
        bar  = ["─"] * 24
        bar[pos] = "[blink bold yellow]◆[/]"
        bar_s = "".join(bar)
        zone = "[bright_green]SUP ZONE[/]" if pct < 0.3 else \
               "[bright_red]RES ZONE[/]"   if pct > 0.7 else "[yellow]MID ZONE[/]"
        pct_res = (1 - pct) * 100
        l1 = f"[{col}]{label}[/]  [dim green]{st.sup:.1f}[/]  |{bar_s}|  [dim red]{st.res:.1f}[/]"
        l2 = f"       [dim]↑RES {st.res-cp:.1f}$ ({pct_res:.0f}%)[/]  [dim]↓SUP {cp-st.sup:.1f}$[/]  {zone}"
        return l1, l2

    liq_t = Table(box=None, expand=True, show_header=False, padding=(0, 0))
    liq_t.add_column("", ratio=1)
    h4l1, h4l2 = _liq_row(h4s, "H4", "bold cyan")
    d1l1, d1l2 = _liq_row(d1s, "D1", "bold gold1")
    liq_t.add_row(h4l1); liq_t.add_row(h4l2)
    liq_t.add_row(d1l1); liq_t.add_row(d1l2)
    layout["liquidity"].update(
        Panel(liq_t, title=f"[{TS}]⚡  INSTITUTIONAL LIQUIDITY MAP[/{TS}]",
              border_style="cyan", padding=(0, 1))
    )

    # ── NEWS + FEED ─────────────────────────────────────────────────────────────
    news_ttl = settings.get("news_refresh_seconds", 300)
    now_ts   = time.time()
    if not hasattr(update_layout, "_cached_news") or \
       (now_ts - getattr(update_layout, "_news_last_fetch", 0)) >= news_ttl:
        update_layout._cached_news     = fetch_live_news()
        update_layout._news_last_fetch = now_ts
    news_items = update_layout._cached_news
    news_idx    = (frame // 30) % max(1, len(news_items))
    _src        = fetch_live_news._last_source
    _fetch_wib  = fetch_live_news._last_fetch_wib
    _live_tag   = f"[bright_green]◉ LIVE: {_src}[/]" if _src != "STATIC" else "[dim]◌ STATIC[/]"
    _news_title = f"[{TS}]🌍  GLOBAL INTEL[/{TS}]  {_live_tag}  [dim]{_fetch_wib}[/]"
    layout["news"].update(
        Panel(Align.center(Text(news_items[news_idx], style="bold bright_white")),
              title=_news_title, border_style="blue", padding=(0, 1))
    )
    layout["feed"].update(
        Panel(Text.from_markup(feed.render()),
              title=f"[{TS}]📡  TACTICAL FEED[/{TS}]", border_style="green", padding=(0, 1))
    )

    # ── TICKER ──────────────────────────────────────────────────────────────────
    ticker_text = Text.from_markup(
        f"🌐 [bold cyan]SESSIONS:[/bold cyan]  {get_session_times()}"
        f"    ◆    "
        f"📊 [bold cyan]VOLATILITY:[/bold cyan]  {get_market_volatility()}"
        f"    ◆    "
        f"📡 [bold bright_green]CORE: ACTIVE[/bold bright_green]"
        f"    ◆    "
        f"⚔️  [bold gold1]COMMANDER PROTOCOL: SECURED[/bold gold1]"
    )
    layout["ticker"].update(
        Panel(Align.center(ticker_text), border_style="grey23", padding=(0, 0))
    )


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
