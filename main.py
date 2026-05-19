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
_EQ_HISTORY = []   # equity curve history

_STATIC_INTEL = [
    "🔴 KAMIS 01:00 WIB — Notulen Rapat FOMC (Dampak Tinggi)",
    "🔴 KAMIS 20:45 WIB — Flash PMI Manufaktur (Dampak Tinggi)",
    "📡 INTEL: Kevin Warsh (Ketua The Fed Baru) bersikap Hawkish",
    "🔥 GEOPOLITIK: Ketegangan Selat Hormuz dorong permintaan Emas",
    "📊 SENTIMEN: Pasar memperkirakan 'Tidak ada Pemangkasan Suku Bunga' 2026",
]

_TRANS_CACHE = {}   # {original_text: translated_text}

def _translate_id(text):
    """Terjemahkan teks ke Bahasa Indonesia via Google Translate gratis."""
    if text in _TRANS_CACHE:
        return _TRANS_CACHE[text]
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "id", "dt": "t", "q": text},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=3,
        )
        if r.status_code == 200:
            data  = r.json()
            result = "".join(p[0] for p in data[0] if p[0])
            _TRANS_CACHE[text] = result
            return result
    except Exception:
        pass
    _TRANS_CACHE[text] = text
    return text

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
                        translated = _translate_id(txt)
                        headlines.append(f"📡 {source_name.upper()}: {translated}")
                    if len(headlines) >= 4:
                        break
                if headlines:
                    fetch_live_news._last_source    = source_name
                    fetch_live_news._last_fetch_wib = datetime.now(wib).strftime("%H:%M")
                    return _STATIC_INTEL + headlines
            except Exception:
                if attempt == 0:
                    time.sleep(0.5)

    fetch_live_news._last_source    = "STATIC"
    fetch_live_news._last_fetch_wib = datetime.now(wib).strftime("%H:%M")
    return _STATIC_INTEL

fetch_live_news._last_source    = "STATIC"
fetch_live_news._last_fetch_wib = "──:──"

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
    if 5  <= hour < 12: return "Selamat Pagi, Komandan. Pasar mulai bergerak."
    if 12 <= hour < 17: return "Selamat Siang, Komandan. Likuiditas sedang puncak."
    if 17 <= hour < 22: return "Selamat Malam, Komandan. Operasi Malam aktif."
    return "Dini Hari, Komandan. Volatilitas tinggi — waspada."

def get_price_sparkline(symbol, n=24):
    """Mini chart harga M5 terakhir pakai block chars."""
    _BLOCKS = "▁▂▃▄▅▆▇█"
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, n)
        if rates is None or len(rates) < 4:
            return "─" * n
        closes = [float(r['close']) for r in rates]
        lo, hi = min(closes), max(closes)
        rng = hi - lo or 0.01
        bars = []
        for i, c in enumerate(closes):
            lvl = int((c - lo) / rng * 7)
            # Warnai berdasarkan arah dari bar sebelumnya
            if i == 0:
                bars.append(f"[grey50]{_BLOCKS[lvl]}[/]")
            elif closes[i] > closes[i-1]:
                bars.append(f"[bright_green]{_BLOCKS[lvl]}[/]")
            elif closes[i] < closes[i-1]:
                bars.append(f"[bright_red]{_BLOCKS[lvl]}[/]")
            else:
                bars.append(f"[grey74]{_BLOCKS[lvl]}[/]")
        return "".join(bars)
    except Exception:
        return "─" * n

def get_adr_info(symbol):
    """ADR 14 hari — berapa USD rata-rata range harian, dan sudah terpakai berapa %."""
    try:
        daily = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 15)
        if daily is None or len(daily) < 2:
            return None, None, None
        ranges = [float(r['high']) - float(r['low']) for r in daily[1:15]]
        adr    = sum(ranges) / len(ranges)
        today  = daily[0]
        used   = float(today['high']) - float(today['low'])
        pct    = min(used / adr * 100, 100) if adr > 0 else 0
        return adr, used, pct
    except Exception:
        return None, None, None

def get_session_countdown():
    """Hitung sisa waktu ke sesi berikutnya (London/NY)."""
    now   = datetime.now(pytz.utc)
    hour  = now.hour
    sesi  = [("London", 8), ("New York", 13), ("London", 32)]   # 32 = 8+24 next day
    for nama, buka in sesi:
        if buka > hour:
            sisa_jam  = buka - hour - 1
            sisa_mnt  = 60 - now.minute
            if sisa_mnt == 60: sisa_jam += 1; sisa_mnt = 0
            return f"{nama} buka {sisa_jam:02d}:{sisa_mnt:02d}"
    return "Semua sesi aktif"

def get_open_positions_summary(symbol, magic):
    """Ringkasan posisi terbuka: jumlah, total lot, total P&L."""
    positions = mt5.positions_get(symbol=symbol, magic=magic) or []
    if not positions:
        return []
    tick = mt5.symbol_info_tick(symbol)
    rows = []
    for p in positions:
        is_buy  = p.type == mt5.POSITION_TYPE_BUY
        curr    = tick.bid if is_buy else tick.ask
        pnl_col = "bright_green" if p.profit >= 0 else "bright_red"
        pips    = (curr - p.price_open) * 10 if is_buy else (p.price_open - curr) * 10
        pip_col = "bright_green" if pips >= 0 else "bright_red"
        cmt     = (p.comment or "")[:10]
        rows.append({
            "ticket": p.ticket,
            "dir":    "BUY" if is_buy else "SELL",
            "lot":    p.volume,
            "open":   p.price_open,
            "pnl":    p.profit,
            "pips":   pips,
            "pnl_col": pnl_col,
            "pip_col": pip_col,
            "comment": cmt,
        })
    return rows

_DELTA_CACHE     = {"live_delta":0.0,"live_buy":0.0,"live_sell":0.0,
                    "cum_delta":0.0,"candle_deltas":[],"divergence":False,"method":"──"}
_DELTA_LAST_FETCH = 0.0

def get_delta_info(symbol, n_candles=8):
    """Delta volume: buy pressure vs sell pressure per candle M5.
    Method 1 (TICK): pakai tick flags BUY/SELL dari broker.
    Method 2 (APPROX): fallback — estimasi dari body candle.
    Cache 10 detik agar tidak berat.
    """
    global _DELTA_CACHE, _DELTA_LAST_FETCH
    if time.time() - _DELTA_LAST_FETCH < 2:
        return _DELTA_CACHE
    try:
        # ── ambil M5 candles untuk batas waktu tiap candle
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, n_candles + 2)
        if rates is None or len(rates) < 2:
            return _DELTA_CACHE

        # ── coba ambil tick data (TRADE ticks)
        from_time = datetime.fromtimestamp(int(rates[0]['time'])) - timedelta(minutes=2)
        ticks = mt5.copy_ticks_from(symbol, from_time, 15000, mt5.COPY_TICKS_TRADE)

        candle_deltas = []

        if ticks is not None and len(ticks) > 10:
            # ── METHOD: TICK FLAGS
            method = "TICK"
            for i in range(len(rates) - 1):
                t_open  = int(rates[i]['time'])
                t_close = int(rates[i + 1]['time'])
                c_buy = c_sell = 0.0
                for t in ticks:
                    if not (t_open <= int(t['time']) < t_close):
                        continue
                    vol   = float(t['volume']) or 1.0
                    flags = int(t['flags'])
                    if flags & 32:          # TICK_FLAG_BUY
                        c_buy  += vol
                    elif flags & 64:        # TICK_FLAG_SELL
                        c_sell += vol
                    else:                   # fallback: posisi harga vs midpoint
                        mid = (float(t['bid']) + float(t['ask'])) / 2.0
                        if float(t['ask']) >= mid:
                            c_buy  += vol
                        else:
                            c_sell += vol
                candle_deltas.append(c_buy - c_sell)

            # live candle (candle yang masih berjalan)
            t_live = int(rates[-1]['time'])
            live_buy = live_sell = 0.0
            for t in ticks:
                if int(t['time']) >= t_live:
                    vol   = float(t['volume']) or 1.0
                    flags = int(t['flags'])
                    if flags & 32:
                        live_buy  += vol
                    elif flags & 64:
                        live_sell += vol
            live_delta = live_buy - live_sell
        else:
            # ── METHOD: APPROX (body candle)
            method = "APPROX"
            for r in rates[:-1]:
                rng = float(r['high']) - float(r['low'])
                if rng == 0:
                    candle_deltas.append(0.0)
                    continue
                direction  = 1.0 if float(r['close']) >= float(r['open']) else -1.0
                body_ratio = abs(float(r['close']) - float(r['open'])) / rng
                candle_deltas.append(direction * body_ratio * 100)
            live_delta = candle_deltas[-1] if candle_deltas else 0.0
            live_buy   = max(live_delta, 0)
            live_sell  = max(-live_delta, 0)

        cum_delta = sum(candle_deltas)

        # ── deteksi divergence: harga naik tapi delta turun (atau sebaliknya)
        divergence = False
        if len(rates) >= 4 and len(candle_deltas) >= 3:
            price_dir = float(rates[-2]['close']) - float(rates[-4]['close'])
            delta_dir = sum(candle_deltas[-3:])
            if (price_dir > 0.1 and delta_dir < -0.3) or (price_dir < -0.1 and delta_dir > 0.3):
                divergence = True

        _DELTA_CACHE = {
            "live_delta":    live_delta,
            "live_buy":      live_buy,
            "live_sell":     live_sell,
            "cum_delta":     cum_delta,
            "candle_deltas": candle_deltas[-n_candles:],
            "divergence":    divergence,
            "method":        method,
        }
        _DELTA_LAST_FETCH = time.time()
    except Exception:
        pass
    return _DELTA_CACHE


def make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header",  size=4),   # +1 untuk sparkline row
        Layout(name="main",    ratio=1),
        Layout(name="ticker",  size=3)
    )
    layout["main"].split_row(Layout(name="side", ratio=1), Layout(name="body", ratio=3))
    layout["side"].split_column(
        Layout(name="greeting",  size=3),
        Layout(name="account",   ratio=2),
        Layout(name="positions", size=6),
        Layout(name="stats",     ratio=2),
        Layout(name="delta",     size=8),   # NEW: DELTA.FLOW panel
        Layout(name="sentiment", size=5),
    )
    layout["body"].split_column(
        Layout(name="intel",        size=3),
        Layout(name="heatmap_row",  size=12),
        Layout(name="matrix_row",   ratio=2),
        Layout(name="liquidity",    size=6),   # restored
        Layout(name="anim_row",     size=15),
        Layout(name="news_feed",    size=7),
    )
    layout["heatmap_row"].split_row(
        Layout(name="heatmap", ratio=5),
        Layout(name="neural",  ratio=5),
    )
    layout["matrix_row"].split_row(
        Layout(name="matrix",    ratio=5),
        Layout(name="bs_matrix", ratio=6)
    )
    layout["anim_row"].split_row(
        Layout(name="equity",  ratio=5),
        Layout(name="oscillo", ratio=5),
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

_MCHARS = "01アイウエカキクサシスセ▓▒░█◆◈※#@$%ABCDEFabcdef01010110"
_BLOCKS = "▁▂▃▄▅▆▇█"

def _htag(n=6):
    return "0x" + "".join(random.choices("0123456789ABCDEF", k=n))

def _rain(width, frame):
    random.seed(frame * 31337 + width)
    out = ""
    for _ in range(width):
        c = random.choice(_MCHARS)
        r = random.random()
        if r < 0.07:   out += f"[bold bright_green]{c}[/]"
        elif r < 0.35: out += f"[green]{c}[/]"
        else:          out += f"[dim green]{c}[/]"
    random.seed()
    return out

# ── PANEL BUILDERS ────────────────────────────────────────────────────────────

def build_heatmap_panel(frame, analyst, _cs, h4_dir):
    """SIGNAL.HEATMAP — 8 TFs × CMP + ROLE + VR + CF grid."""
    BLINK = frame % 2 == 0
    MG = "bright_green"; CC = "bright_cyan"; RD = "bright_red"; GD = "gold1"
    DG = "grey62"; BC = "bold bright_cyan"; BY = "bold gold1"

    def _T_local(label):
        return f"[{BC}][ {label} ][/{BC}]  [{DG}]{_htag(6)}[/{DG}]"

    cascade_roles = _cs.get("cascade_roles", {})
    cf_ready  = _cs.get("cf_ready", False)
    cf_type   = _cs.get("cf_type", "")
    m15_is_vr = _cs.get("m15_is_vr", False)
    m15_solid = _cs.get("m15_solid", False)
    direction = _cs.get("direction", h4_dir)

    # Pre-compute per-chain CMP values for per-parent VR/CF logic
    _m30_cmp = analyst.states["M30"].cmp
    _m15_cmp = analyst.states["M15"].cmp
    _m5_cmp  = analyst.states["M5"].cmp

    t = Table(
        box=rich_box.SIMPLE_HEAD, expand=True, show_edge=False,
        padding=(0, 1), header_style=f"bold {CC} on grey11",
    )
    t.add_column("TF",   justify="center", width=6)
    t.add_column("CMP",  justify="center", width=10)
    t.add_column("ROLE", justify="center", width=13)
    t.add_column("VR→PARENT", justify="center", width=14)
    t.add_column("CF",   justify="center", width=12)
    t.add_column("⊕",    justify="center", width=3)

    tfs = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]
    aligned_count = 0

    for tf in tfs:
        st = analyst.states[tf]
        is_master = (tf == "H4")
        cmp_val   = st.cmp

        # ── CMP cell — BUY=hijau, SELL=merah, pulse kalau aligned
        aligned_cmp = (cmp_val == h4_dir and h4_dir != "WAIT")
        if cmp_val == "BUY":
            sym = "◉" if (BLINK and aligned_cmp) else "▣"
            cmp_cell = f"[bold white on dark_green] {sym} BUY [/]"
        elif cmp_val == "SELL":
            sym = "◉" if (BLINK and aligned_cmp) else "▣"
            cmp_cell = f"[bold white on dark_red] {sym} SELL[/]"
        else:
            cmp_cell = f"[{DG}]  ─────  [/]"

        # ── ROLE cell — sama dengan HIERARCHY.MATRIX lama
        if tf in ("MN1", "W1", "D1"):
            r_lbl = "MACRO"
            r_col = MG if aligned_cmp else DG
            role_cell = f"[{r_col}]{r_lbl}[/]"
            row_s_role = ""
        elif tf == "H4":
            role_cell = f"[bold white on grey19] ★ MASTER [/]"
            row_s_role = ""
        elif tf == "H1":
            cr = cascade_roles.get("H1", "")
            if cr == "VR" or (cmp_val != direction and cmp_val != "WAIT"):
                # H1 counter H4 = H1 adalah VR
                lbl = "H1_VR ⚡" if BLINK else "H1_VR ·"
                role_cell = f"[bold white on dark_blue] {lbl} [/]"
            elif cmp_val == direction:
                role_cell = f"[bold bright_cyan]H1_CMP[/]"
            else:
                role_cell = f"[{DG}]H1_WAIT[/]"
            row_s_role = ""
        elif tf == "M30":
            h1_cmp = analyst.states["H1"].cmp
            if cmp_val == "WAIT":
                role_cell = f"[{DG}]WAIT[/]"
            elif cmp_val == direction:
                # M30 aligned H4 = CMP setup confirmed
                role_cell = f"[bold bright_cyan]SETUP_CMP[/]"
            else:
                # M30 counter H4 = VR ke H4 (pullback/testing master)
                lbl = "VR→H4 ⚡" if BLINK else "VR→H4 ·"
                role_cell = f"[bold white on dark_blue] {lbl} [/]"
            row_s_role = ""
        elif tf == "M15":
            if m15_is_vr:
                lbl = "VR→M30 ⚡" if BLINK else "VR→M30 ·"
                role_cell = f"[bold white on dark_blue] {lbl} [/]"
            elif m15_solid:
                role_cell = f"[bold white on grey23] SOLID ▣ [/]"
            else:
                role_cell = f"[{DG}]STANDBY[/]"
            row_s_role = ""
        elif tf == "M5":
            m15_cmp = analyst.states["M15"].cmp
            if cf_ready and cf_type == "MINOR_CF":
                lbl = "MINOR_CF ◉" if BLINK else "MINOR_CF ▣"
                role_cell = f"[bold white on dark_green] {lbl} [/]"
            elif cf_ready:
                lbl = f"{cf_type} ◉" if BLINK else f"{cf_type} ▣"
                role_cell = f"[bold white on dark_green] {lbl} [/]"
            elif m15_solid and cmp_val != m15_cmp and cmp_val != "WAIT":
                # M15 SOLID BUY, M5 SELL counter → M5 adalah VR ke M15
                lbl = "VR→M15 ⚡" if BLINK else "VR→M15 ·"
                role_cell = f"[bold white on dark_blue] {lbl} [/]"
            elif m15_is_vr and cmp_val == direction:
                role_cell = f"[{CC}]CF_ZONE[/]"
            elif m15_is_vr and cmp_val != direction:
                role_cell = f"[yellow]VR[/]"
            else:
                role_cell = f"[{DG}]STANDBY[/]"
            row_s_role = ""
        else:
            role_cell = f"[{DG}]──[/]"
            row_s_role = ""

        # ── VR cell — per-parent chain: each TF vs its DIRECT parent
        # H1→H4, M30→H4, M15→M30, M5→M15  (VR=counter parent, CF=returned to parent)
        cr = cascade_roles.get(tf, "")
        if tf == "M15":
            _is_vr = m15_is_vr                                        # M15 vs M30
            _vr_lbl = "VR→M30"
        elif tf == "M5":
            _is_vr = (_m5_cmp != _m15_cmp and _m5_cmp != "WAIT" and _m15_cmp != "WAIT")
            _vr_lbl = "VR→M15"
        elif tf in ("H1", "M30"):
            _is_vr = (cr == "VR")                                      # H1/M30 vs H4
            _vr_lbl = "VR→H4"
        else:
            _is_vr = False
            _vr_lbl = "VR"

        if _is_vr:
            sym = f"⚡{_vr_lbl}⚡" if BLINK else f"· {_vr_lbl} ·"
            vr_cell = f"[bold white on dark_blue] {sym} [/]"
        else:
            vr_cell = f"[{DG}] ───── [/]"

        # ── CF cell — per-parent: which TF FIRED CF back to parent direction
        # M5 CF = cf_ready (any type); M15 CF = CF_LOW; M30/H1 CF = cascade_roles "CF"
        if tf == "M5":
            _is_cf = cf_ready and cf_type in ("MINOR_CF", "CF_HIGH")
            _cf_lbl = cf_type if cf_ready else "CF"
        elif tf == "M15":
            _is_cf = cf_ready and cf_type == "CF_LOW"                  # M15 returned to M30
            _cf_lbl = "CF_LOW"
        elif tf in ("H1", "M30"):
            _is_cf = (cr == "CF")                                       # M30/H1 back to H4
            _cf_lbl = "CF"
        else:
            _is_cf = False
            _cf_lbl = "CF"

        if _is_cf:
            sym = f"◉{_cf_lbl}◉" if BLINK else f"●{_cf_lbl}●"
            cf_cell = f"[bold white on dark_green] {sym} [/]"
        else:
            cf_cell = f"[{DG}] ───── [/]"

        # ── Align indicator ⊕
        if aligned_cmp:
            aligned_count += 1
            alg = f"[{MG}]▼[/]" if h4_dir == "SELL" else f"[{MG}]▲[/]"
        elif cmp_val == "WAIT":
            alg = f"[{DG}]·[/]"
        else:
            alg = f"[{RD}]✗[/]"

        row_style = "on grey15" if is_master else ""
        tf_lbl = f"[{BY}]{tf}★[/]" if is_master else f"[{CC}]{tf}[/]"

        t.add_row(tf_lbl, cmp_cell, role_cell, vr_cell, cf_cell, alg, style=row_style)

    # Summary row
    sync_col = MG if aligned_count >= 6 else GD if aligned_count >= 4 else RD
    t.add_row(
        f"[{DG}]SYNC[/]",
        f"[{DG}]────────[/]",
        f"[{DG}]───────────[/]",
        f"[{DG}]────────────[/]",
        f"[{DG}]──────────[/]",
        f"[{sync_col}]{aligned_count}/8[/]",
    )

    return Panel(t, title=_T_local("SIGNAL.HEATMAP"), border_style="magenta", padding=(0, 0))


def build_neural_flow_panel(frame, analyst, _cs, h4_dir):
    """NEURAL.FLOW — chain node visualization."""
    BLINK = frame % 2 == 0
    MG = "bright_green"; CC = "bright_cyan"; RD = "bright_red"; GD = "gold1"
    DG = "grey62"; BC = "bold bright_cyan"

    def _T_local(label):
        return f"[{BC}][ {label} ][/{BC}]  [{DG}]{_htag(6)}[/{DG}]"

    def node(label, active, bg, fire=False):
        if fire:
            sym = "⚡" if BLINK else "◉"
            return f"[bold white on {bg}] {sym} {label} {sym} [/]"
        if active:
            sym = "◉" if BLINK else "●"
            return f"[bold white on {bg}] {sym} {label} [/]"
        return f"[{DG}][ ○ {label} ][/]"

    def pipe(active, color=None):
        c = color or MG
        return f"[{c}] ══► [/]" if active else f"[{DG}] ──► [/]"

    def tag(ok, yes_txt, no_txt):
        return f"[{MG}]{yes_txt}[/]" if ok else f"[{DG}]{no_txt}[/]"

    cf_ready  = _cs.get("cf_ready", False)
    cf_type   = _cs.get("cf_type", "")
    m15_is_vr = _cs.get("m15_is_vr", False)
    m15_solid = _cs.get("m15_solid", False)
    direction = _cs.get("direction", h4_dir)

    # ── Node states sesuai daily deploy chain: H4 → M30 → M15 → M5
    macro_ok = all(analyst.states[t].cmp == h4_dir for t in ["MN1","W1","D1"]) and h4_dir != "WAIT"
    h4_ok    = analyst.states["H4"].cmp == h4_dir and h4_dir != "WAIT"
    m30_cmp  = analyst.states["M30"].cmp
    m15_cmp  = analyst.states["M15"].cmp
    m5_cmp   = analyst.states["M5"].cmp

    # Step 1: M30 CMP locked (aligned H4)
    m30_locked = m30_cmp == h4_dir and h4_dir != "WAIT"
    # Step 2: M15 VR aktif (counter H4 = VR) atau SOLID
    m15_active = m15_is_vr or m15_solid
    m15_vr_dir = m15_cmp != h4_dir and m15_cmp != "WAIT"   # M15 counter H4
    # Step 3: M5 CF fired
    m5_cf = cf_ready

    # M5 state label
    m5_state = ""
    if cf_ready:
        m5_state = f"[blink bold {MG}] ⚡ CF::FIRE ⚡ [/]" if BLINK else f"[bold {MG}] ◉ CF READY [/]"
    elif m15_is_vr and m5_cmp == h4_dir:
        m5_state = f"[{CC}] CF_ZONE [/]"
    elif m15_solid and m5_cmp != m15_cmp and m5_cmp != "WAIT":
        m5_state = f"[yellow] VR→M15 [/]"
    elif m15_active:
        m5_state = f"[{DG}]standby...[/]"
    else:
        m5_state = f"[{DG}]standby...[/]"

    # M15 state label
    if m15_is_vr:
        m15_lbl = "VR ⚡" if BLINK else "VR ·"
        m15_bg  = "dark_blue"
    elif m15_solid:
        m15_lbl = "SOLID ▣"
        m15_bg  = "grey23"
    else:
        m15_lbl = "M15"
        m15_bg  = "grey19"

    # M30 state label
    if m30_locked:
        m30_lbl = "M30 CMP"
        m30_bg  = "dark_green"
    elif m30_cmp != "WAIT":
        m30_lbl = "VR→H4 ⚡" if BLINK else "VR→H4"
        m30_bg  = "dark_blue"
    else:
        m30_lbl = "M30"
        m30_bg  = "grey19"

    # Chain strength: 4 steps
    strength = sum([macro_ok, h4_ok, m30_locked, m15_active, m5_cf])
    str_col  = MG if strength >= 4 else GD if strength >= 2 else RD
    str_bar  = _bar(strength * 2, 10, fill_color=str_col, empty_color="grey19", fill_char="▰", empty_char="▱")
    aligned_n = sum(1 for tf in ["MN1","W1","D1","H4","H1","M30","M15","M5"]
                    if analyst.states[tf].cmp == h4_dir and h4_dir != "WAIT")

    # ── Layout: MACRO → H4 → M30 → M15 → M5 (chain utama daily deploy)
    lines = [
        Text.from_markup(f"  [{DG}]{'─'*48}[/]"),

        # Baris 1: MACRO → H4 MASTER
        Text.from_markup(
            f"  {node('MACRO', macro_ok, 'dark_green')}"
            f"{pipe(macro_ok, GD)}"
            f"{node('H4 ★ MASTER', h4_ok, 'dark_goldenrod')}"
            f"  [{BY}]DIR::{h4_dir}[/] "
            f"[{'bright_green' if h4_dir=='BUY' else 'bright_red'}]{'▲' if h4_dir=='BUY' else '▼'}[/]"
        ),

        Text.from_markup(f"  [{DG}]{'─'*48}[/]"),
        Text(""),

        # Baris 2: H4 → M30 CMP (step 1)
        Text.from_markup(
            f"  [{DG}]        ↓  Step 1[/]\n"
            f"  {node(m30_lbl, m30_locked or (m30_cmp!='WAIT'), m30_bg)}"
            f"  "
            f"{'[bold bright_cyan]CMP locked ✅[/]' if m30_locked else '[yellow]VR ke H4 (pullback)[/]' if m30_cmp!='WAIT' else f'[{DG}]waiting M30...[/]'}"
        ),

        Text(""),

        # Baris 3: M30 → M15 VR (step 2)
        Text.from_markup(
            f"  [{DG}]        ↓  Step 2[/]\n"
            f"  {pipe(m15_active, CC)}"
            f"{node(m15_lbl, m15_active, m15_bg)}"
            f"  "
            f"{'[bold bright_cyan]VR aktif ✅[/]' if m15_is_vr else '[white]SOLID (counter M30)[/]' if m15_solid else f'[{DG}]waiting M15 VR...[/]'}"
        ),

        Text(""),

        # Baris 4: M15 → M5 CF (step 3)
        Text.from_markup(
            f"  [{DG}]        ↓  Step 3[/]\n"
            f"  {pipe(m5_cf, MG)}"
            f"{node('M5', m5_cf, 'dark_green', fire=m5_cf)}"
            f"  {m5_state}"
        ),

        Text(""),
        Text.from_markup(f"  [{DG}]{'─'*48}[/]"),
        Text.from_markup(
            f"  [{DG}]CHAIN[/] {str_bar} [{str_col}]{strength}/5[/]"
            f"   [{DG}]ALIGN[/] [{MG}]{aligned_n}/8 TF[/]"
        ),
    ]

    border = (MG if BLINK else "green") if m5_cf else (CC if m15_active else DG)
    return Panel(RichGroup(*lines), title=_T_local("NEURAL.FLOW"), border_style=border, padding=(0, 1))


def build_equity_curve_panel(frame, acc):
    """EQUITY.CURVE — animated ASCII chart of equity history."""
    global _EQ_HISTORY
    MG = "bright_green"; RD = "bright_red"; DG = "grey62"; BC = "bold bright_cyan"

    def _T_local(label):
        return f"[{BC}][ {label} ][/{BC}]  [{DG}]{_htag(6)}[/{DG}]"

    # Append current equity
    if acc is not None:
        _EQ_HISTORY.append(float(acc.equity))
        if len(_EQ_HISTORY) > 200:
            _EQ_HISTORY.pop(0)

    if len(_EQ_HISTORY) < 2:
        placeholder = Text.from_markup(f"  [{DG}]COLLECTING DATA...[/]")
        return Panel(placeholder, title=_T_local("EQUITY.CURVE"), border_style=MG, padding=(0, 0))

    hist = _EQ_HISTORY[-51:]
    base = _EQ_HISTORY[0]
    mn   = min(hist)
    mx_h = max(hist)
    rng  = mx_h - mn if mx_h != mn else 1.0
    ROWS = 6

    chart = []
    for row in range(ROWS - 1, -1, -1):
        lo  = mn + rng * row / ROWS
        hi  = mn + rng * (row + 1) / ROWS
        line = ""
        for i, val in enumerate(hist):
            is_last = (i == len(hist) - 1)
            if val >= hi:
                ch = f"[bold {MG}]█[/]" if is_last else f"[{MG}]█[/]"
            elif val >= lo:
                frac = (val - lo) / (rng / ROWS)
                blk  = _BLOCKS[min(int(frac * 8), 7)]
                ch   = f"[bold {MG}]{blk}[/]" if is_last else f"[green]{blk}[/]"
            else:
                ch = f"[grey19]░[/]"
            line += ch
        if row == ROWS - 1: y_lbl = f" [{DG}]{mx_h:>7.2f}[/]"
        elif row == ROWS // 2: y_lbl = f" [{DG}]{(mn + rng * 0.5):>7.2f}[/]"
        elif row == 0: y_lbl = f" [{DG}]{mn:>7.2f}[/]"
        else: y_lbl = ""
        chart.append(Text.from_markup(line + y_lbl))

    chart.append(Text.from_markup(
        f"[{DG}]{'─' * len(hist)}[/]"
        f"  [{DG}]← {len(hist)} frames[/]"
    ))

    live_eq = float(acc.equity) if acc else (hist[-1] if hist else base)
    pnl     = live_eq - base
    pnl_col = MG if pnl >= 0 else RD
    eq_col  = MG if live_eq >= base else RD
    peak_dd = mx_h - live_eq

    stats_t = Table(box=None, expand=True, show_header=False, padding=(0, 2))
    stats_t.add_column("", justify="left", ratio=1)
    stats_t.add_column("", justify="left", ratio=1)
    stats_t.add_column("", justify="left", ratio=1)
    stats_t.add_column("", justify="left", ratio=1)
    stats_t.add_row(
        Text.from_markup(f"[{DG}]EQ[/]  [{eq_col}]{live_eq:.2f}[/]"),
        Text.from_markup(f"[{DG}]PnL[/] [{pnl_col}]{'+' if pnl >= 0 else ''}{pnl:.2f}[/]"),
        Text.from_markup(f"[{DG}]PEAK[/] [{MG}]{mx_h:.2f}[/]"),
        Text.from_markup(f"[{DG}]DD[/]  [{RD}]{peak_dd:.2f}[/]"),
    )

    pnl_fill = min(int(abs(pnl) / max(abs(pnl) + 1, 30) * 44), 44)
    pnl_bar  = _bar(pnl_fill, 44, fill_color=pnl_col, empty_color="grey19", fill_char="▓", empty_char="░")

    content = RichGroup(*chart, Text(""), stats_t, Text.from_markup(f"  {pnl_bar}"))
    border  = (MG if frame % 2 == 0 else "green") if pnl >= 0 else RD
    return Panel(content, title=_T_local("EQUITY.CURVE"), border_style=border, padding=(0, 0))


def build_oscilloscope_panel(frame, pos_rows):
    """PnL.OSCILLOSCOPE — animated waveform + live positions table."""
    MG = "bright_green"; RD = "bright_red"; DG = "grey62"; BC = "bold bright_cyan"

    def _T_local(label):
        return f"[{BC}][ {label} ][/{BC}]  [{DG}]{_htag(6)}[/{DG}]"

    WIDTH = 48
    ROWS  = 6
    total = sum(p["pnl"] for p in pos_rows) if pos_rows else 0.0
    tot_col = MG if total >= 0 else RD

    # Waveform — composite sine
    wave = []
    for x in range(WIDTH):
        t   = x / WIDTH * 6 * math.pi + frame * 0.28
        val = (math.sin(t) * 0.45
               + math.sin(t * 1.9 + 0.8) * 0.30
               + math.cos(t * 0.6 + 1.2) * 0.25)
        lvl = int((val + 1) / 2 * (ROWS * 8 - 1))
        wave.append(max(0, min(ROWS * 8 - 1, lvl)))

    osc_lines = []
    mid_row = ROWS // 2
    for row in range(ROWS - 1, -1, -1):
        line = ""
        for lvl in wave:
            row_lvl = lvl // 8
            sub_lvl = lvl % 8
            if row_lvl > row:
                line += f"[{tot_col}]█[/]"
            elif row_lvl == row:
                line += f"[green]{_BLOCKS[sub_lvl]}[/]"
            else:
                line += f"[grey35]─[/]" if row == mid_row else f"[grey19] [/]"
        suffix = f"  [{DG}]── 0 ──[/]" if row == mid_row else ""
        osc_lines.append(Text.from_markup(f" {line}{suffix}"))

    # Position table
    pos_t = Table(box=None, expand=True, show_header=False, padding=(0, 1), show_edge=False)
    pos_t.add_column("", width=5,  justify="center")
    pos_t.add_column("", width=5,  justify="center")
    pos_t.add_column("", width=7,  justify="right")
    pos_t.add_column("", width=8,  justify="right")
    pos_t.add_column("", ratio=1)

    max_pnl = max((abs(p["pnl"]) for p in pos_rows), default=1.0) or 1.0
    if pos_rows:
        for p in pos_rows[:4]:
            d_col  = MG if p["dir"] == "BUY" else RD
            pnl_c  = MG if p["pnl"] >= 0 else RD
            fill   = int(abs(p["pnl"]) / max_pnl * 10)
            mini_b = _bar(fill, 10, fill_color=pnl_c, empty_color="grey19", fill_char="▪", empty_char="·")
            pos_t.add_row(
                f"[bold white on {'dark_green' if p['dir']=='BUY' else 'dark_red'}] {p['dir'][:1]} [/]",
                f"[white]{p['lot']}L[/]",
                f"[{p['pip_col']}]{p['pips']:+.1f}p[/]",
                f"[{pnl_c}]{p['pnl']:+.2f}$[/]",
                mini_b,
            )
    else:
        pos_t.add_row(f"[{DG}]──[/]", f"[{DG}]NO POSITIONS[/]", "", "", "")

    sep = Text.from_markup(f" [{DG}]{'─'*42}[/]")
    n_pos = max(len(pos_rows), 1)
    tot_fill = int(abs(total) / (max_pnl * n_pos) * 44) if max_pnl else 0
    tot_bar  = _bar(min(tot_fill, 44), 44, fill_color=tot_col, empty_color="grey19", fill_char="█", empty_char="░")
    total_txt = Text.from_markup(
        f"  [{DG}]TOTAL P&L[/]  [{tot_col}]{'+' if total >= 0 else ''}{total:.2f}$[/]"
        f"  [{tot_col}]{'▲' if total >= 0 else '▼'}[/]"
    )

    border  = (MG if frame % 2 == 0 else "green") if total >= 0 else RD
    content = RichGroup(*osc_lines, Text(""), pos_t, sep, total_txt, Text.from_markup(f"  {tot_bar}"))
    return Panel(content, title=_T_local("PnL.OSCILLOSCOPE"), border_style=border, padding=(0, 0))


def update_layout(layout, analyst, executor, symbol, settings, frame):
    BLINK = frame % 2 == 0

    # ── PALETTE ────────────────────────────────────────────────────────────────
    MG  = "bright_green"          # matrix green
    CC  = "bright_cyan"           # cyber cyan
    RD  = "bright_red"            # alert red
    GD  = "gold1"                 # gold/master
    DG  = "grey62"                # visible label on any background
    BG  = "bold bright_green"
    BC  = "bold bright_cyan"
    BR  = "bold bright_red"
    BY  = "bold gold1"

    def _T(label, addr=None):
        """Hacker-style panel title."""
        a = addr or _htag(6)
        return f"[{BC}][ {label} ][/{BC}]  [{DG}]{a}[/{DG}]"

    # ── LIVE TICK ──────────────────────────────────────────────────────────────
    # ── LIVE TICK ──────────────────────────────────────────────────────────────
    tick   = mt5.symbol_info_tick(symbol)
    bid    = f"{tick.bid:.2f}" if tick else "──────"
    ask    = f"{tick.ask:.2f}" if tick else "──────"
    master = analyst.states[settings.get("master_tf", "H4")]
    h4_dir_theme = master.cmp
    theme  = MG if h4_dir_theme == "BUY" else RD if h4_dir_theme == "SELL" else GD
    spin   = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][frame % 10]
    pid    = _htag(4)
    uptime = f"{frame // 10:05d}s"

    # ── HEADER ─────────────────────────────────────────────────────────────────
    enc_s    = f"[{MG}]ENC:OK[/]" if BLINK else f"[green]ENC:OK[/]"
    fw_s     = f"[{CC}]FW:ACT[/]"
    sparkline = get_price_sparkline(symbol)
    countdown = get_session_countdown()
    header_top = Text.assemble(
        (f" {spin} ", f"bold {theme}"),
        ("CHAIN_REACTION::", f"bold {theme}"),
        ("OVERLORD_v4.0  ", BC),
        (" ── ", DG),
        ("CMDR::DADANG  ", BY),
        (" ── ", DG),
        (f"{symbol}  ", "white"),
        (bid, BG),
        (" / ", DG),
        (ask, BR),
        ("  ──  ", DG),
        (datetime.now().strftime("%H:%M:%S"), BC),
        (" WIB  ", "grey74"),
        (f"[{pid}]  {enc_s}  {fw_s}  [grey62]UP:{uptime}[/grey62]", ""),
    )
    header_bot = Text.from_markup(
        f"  [grey62]M5:[/grey62] {sparkline}"
        f"  [grey62]║[/grey62]  "
        f"[grey62]Sesi:[/grey62] [{CC}]{countdown}[/{CC}]"
    )
    layout["header"].update(Panel(
        RichGroup(Align.center(header_top), header_bot),
        style=f"bold {theme}", padding=(0, 0)
    ))

    # ── GREETING  (matrix rain) ────────────────────────────────────────────────
    greeting_rain = _rain(34, frame)
    greeting_msg  = get_commander_greeting()
    greeting_body = Text.from_markup(
        f"{greeting_rain}\n"
        f"  [{CC}]// {greeting_msg}[/{CC}]"
    )
    layout["greeting"].update(Panel(greeting_body, border_style="green", padding=(0, 0)))

    # ── STRATEGIC INTEL MARQUEE ─────────────────────────────────────────────────
    intel_raw = analyst.get_strategic_forecast()
    for tag in ["[bold yellow]","[bold green]","[bold cyan]","[bold blue]","[bold magenta]","[/]"]:
        intel_raw = intel_raw.replace(tag, "")
    _scroll_src = f"  ◈  {intel_raw}  ◈  "
    _shift  = (frame // 2) % len(_scroll_src)
    _scrolled = (_scroll_src[_shift:] + _scroll_src[:_shift])[:130]
    layout["intel"].update(
        Panel(Align.center(Text(_scrolled, style=f"bold {GD}")),
              title=_T("STRATEGIC_INTEL"), border_style=GD, padding=(0, 0))
    )

    # ── ACCOUNT  (VAULT ACCESS) ────────────────────────────────────────────────
    acc = mt5.account_info()
    acc_t = Table(box=None, expand=True, padding=(0, 1))
    acc_t.add_column("", style=DG, width=7)
    acc_t.add_column("", style=BG, justify="right")
    if acc:
        dd_pct = ((acc.balance - acc.equity) / acc.balance * 100) if acc.balance > 0 else 0
        eq_pct = (acc.equity  / acc.balance  * 100)               if acc.balance > 0 else 100
        eq_col = MG if eq_pct >= 99 else "yellow" if eq_pct >= 97 else RD
        dd_col = MG if dd_pct < 0.5  else "yellow" if dd_pct < 2  else RD
        eq_bar = _bar(int(eq_pct / 100 * 12), 12, fill_color=eq_col, empty_color="grey19")
        acc_t.add_row("ID",     f"[{CC}]{acc.login}[/]")
        acc_t.add_row("BAL",    f"[white]{acc.balance:,.0f}[/]")
        acc_t.add_row("EQ",     f"[{eq_col}]{acc.equity:,.0f}[/]")
        acc_t.add_row("DD",     f"[{dd_col}]{dd_pct:.2f}%[/]")
        acc_t.add_row("",       eq_bar)
    uplink_v  = int(math.sin(frame * 0.8) * 4 + 5)
    uplink_bar = _bar(uplink_v, 10, fill_color=CC, empty_color="grey19")
    acc_t.add_row("NET", uplink_bar)
    layout["account"].update(
        Panel(acc_t, title=_T("VAULT.ACCESS", pid), border_style=CC, padding=(0, 0))
    )

    # ── OPEN POSITIONS ─────────────────────────────────────────────────────────
    pos_rows = get_open_positions_summary(symbol, settings.get("magic_number", 2026))
    pos_t    = Table(box=None, expand=True, padding=(0, 1), show_header=False)
    pos_t.add_column("", style="white",  width=5)
    pos_t.add_column("", width=5)
    pos_t.add_column("", justify="right", width=6)
    pos_t.add_column("", justify="right", width=8)
    if pos_rows:
        total_pnl = sum(p["pnl"] for p in pos_rows)
        tp_col    = MG if total_pnl >= 0 else RD
        for p in pos_rows[:4]:   # max 4 baris agar muat
            d_col = MG if p["dir"] == "BUY" else RD
            pos_t.add_row(
                f"[{d_col}]{p['dir'][:1]}[/]",
                f"[white]{p['lot']}L[/]",
                f"[{p['pip_col']}]{p['pips']:+.1f}p[/]",
                f"[{p['pnl_col']}]{p['pnl']:+.2f}[/]",
            )
        pos_t.add_row("", "", "", f"[{tp_col}]={total_pnl:+.2f}[/]")
        pos_border = MG if total_pnl >= 0 else RD
    else:
        pos_t.add_row("[grey62]──[/]", "[grey62]TIDAK ADA POSISI[/]", "", "")
        pos_border = "grey35"
    layout["positions"].update(
        Panel(pos_t, title=_T("POSISI.AKTIF"), border_style=pos_border, padding=(0, 0))
    )

    # ── LIVE STATS  (SYS METRICS) ──────────────────────────────────────────────
    stats   = get_real_stats(settings.get("magic_number", 2026))
    pnl_col = MG if stats['pnl'] >= 0 else RD
    wr_col  = MG if stats['win_rate'] >= 60 else "yellow" if stats['win_rate'] >= 40 else RD
    st_t    = Table(box=None, expand=True, padding=(0, 1))
    st_t.add_column("", style=DG, width=7)
    st_t.add_column("", style=BG, justify="right")
    st_t.add_row("WIN%",   f"[{wr_col}]{stats['win_rate']:.0f}%[/]")
    st_t.add_row("TRADES", f"[{CC}]{stats['strikes']}[/]")
    st_t.add_row("PnL",    f"[{pnl_col}]{'+' if stats['pnl']>=0 else ''}{stats['pnl']:,.2f}[/]")
    proc_v   = int(math.cos(frame * 0.6) * 4 + 5)
    proc_bar = _bar(proc_v, 10, fill_color=GD, empty_color="grey19")
    st_t.add_row("", "")
    st_t.add_row("CPU",    proc_bar)
    layout["stats"].update(
        Panel(st_t, title=_T("SYS.METRICS"), border_style=GD, padding=(0, 0))
    )

    # ── DELTA.FLOW  (footprint volume) ────────────────────────────────────────
    dlt      = get_delta_info(symbol)
    live_d   = dlt["live_delta"]
    cum_d    = dlt["cum_delta"]
    deltas   = dlt["candle_deltas"]
    method   = dlt["method"]
    div_warn = dlt["divergence"]

    # animasi per-frame: last_update countdown + pulsing bar tip
    secs_ago = int(time.time() - _DELTA_LAST_FETCH)
    upd_col  = MG if secs_ago < 3 else "yellow" if secs_ago < 6 else RD
    upd_txt  = f"[{upd_col}]{secs_ago}s ago[/]"

    dlt_t = Table(box=None, expand=True, show_header=False, padding=(0, 1))
    dlt_t.add_column("", style=DG, width=7)
    dlt_t.add_column("", ratio=1)

    if deltas:
        max_abs  = max(abs(d) for d in deltas + [live_d]) or 1.0
        live_col = MG if live_d >= 0 else RD

        # Live bar — tip karakter berputar tiap frame (animasi)
        live_f    = int(abs(live_d) / max_abs * 12)
        tip_chars = "▏▎▍▌▋▊▉█" if live_d >= 0 else "▉▊▋▌▍▎▏█"
        tip       = tip_chars[frame % len(tip_chars)]
        live_bar  = _bar(live_f, 12, fill_color=live_col, empty_color="grey19", fill_char="█", empty_char="░")
        live_bar += f"[{live_col}]{tip}[/]"
        live_arr  = f"[bold {MG}]▲ BUY[/]"  if live_d >= 0 else f"[bold {RD}]▼ SELL[/]"
        dlt_t.add_row("LIVE Δ", Text.from_markup(
            f"{live_bar}  [{live_col}]{live_d:+.2f}[/]  {live_arr}"
        ))

        # Cumulative delta — nilai berkedip kalau baru update
        cum_col = MG if cum_d >= 0 else RD
        cum_pulse = f"[blink {cum_col}]{cum_d:+.2f}[/]" if secs_ago < 2 else f"[{cum_col}]{cum_d:+.2f}[/]"
        dlt_t.add_row("CUM Δ", Text.from_markup(
            f"[{cum_col}]{'▲' if cum_d>=0 else '▼'}[/] {cum_pulse}  [{DG}]{method}[/]  {upd_txt}"
        ))

        # Histogram 8 candle — scroll satu posisi tiap 4 frame (animasi scroll)
        scroll_offset = (frame // 4) % max(len(deltas), 1)
        hist_deltas   = (deltas + deltas)[scroll_offset: scroll_offset + 8]
        hist = ""
        for d in hist_deltas:
            if   d >  max_abs * 0.6: hist += f"[bold {MG}]█[/]"
            elif d >  max_abs * 0.2: hist += f"[{MG}]▄[/]"
            elif d >  0:             hist += f"[green]▂[/]"
            elif d < -max_abs * 0.6: hist += f"[bold {RD}]█[/]"
            elif d < -max_abs * 0.2: hist += f"[{RD}]▄[/]"
            elif d <  0:             hist += f"[red]▂[/]"
            else:                    hist += f"[{DG}]─[/]"
        # scan cursor
        scan_pos = frame % 8
        hist_chars = list(hist.split("]["))
        dlt_t.add_row("M5 HIST", Text.from_markup(hist + f"  [{DG}]◄[/]"))

        # Buy vs Sell tug-of-war bar — full width, animated fill
        total_vol  = dlt["live_buy"] + dlt["live_sell"] + 0.001
        buy_ratio  = dlt["live_buy"]  / total_vol
        sell_ratio = dlt["live_sell"] / total_vol
        tow_width  = 20
        buy_fill   = int(buy_ratio  * tow_width)
        sell_fill  = int(sell_ratio * tow_width)
        # animasi: bar tumbuh sedikit-sedikit tiap frame
        anim_buy  = min(buy_fill,  (frame % (tow_width + 1)))  if buy_fill  > 0 else 0
        anim_sell = min(sell_fill, (frame % (tow_width + 1)))  if sell_fill > 0 else 0
        b_tow = _bar(buy_fill,  tow_width, fill_color=MG, empty_color="grey19", fill_char="▮", empty_char="·")
        s_tow = _bar(sell_fill, tow_width, fill_color=RD, empty_color="grey19", fill_char="▮", empty_char="·")
        dlt_t.add_row("", Text.from_markup(
            f"[{MG}]B[/] {b_tow}  [{RD}]S[/] {s_tow}"
        ))

        # Divergence warning
        if div_warn:
            dlt_t.add_row("",
                Text.from_markup(
                    f"[blink bold yellow]⚠ DIVERGENCE: harga ≠ delta[/]" if BLINK
                    else f"[bold yellow]⚠ DIVERGENCE: harga ≠ delta[/]"
                )
            )
    else:
        spin_d = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][frame % 10]
        dlt_t.add_row("STATUS", Text.from_markup(f"[{MG}]{spin_d}[/] [{DG}]Mengambil tick data...[/]"))

    # Border blink berdasarkan arah delta — selalu bergerak
    dlt_border = (MG if BLINK else "green") if live_d > 0 else \
                 (RD if BLINK else "dark_red") if live_d < 0 else DG
    layout["delta"].update(
        Panel(dlt_t, title=_T("DELTA.FLOW"), border_style=dlt_border, padding=(0, 0))
    )

    # ── SENTIMENT  (SIGNAL SCAN) ───────────────────────────────────────────────
    buy_pct, sell_pct = analyst.get_total_sentiment()
    regime, _         = analyst.get_market_regime()
    bw = 11
    b_bar = _bar(int(buy_pct/100*bw),  bw, fill_color=MG,  empty_color="grey19")
    s_bar = _bar(int(sell_pct/100*bw), bw, fill_color=RD,   empty_color="grey19")
    dom     = "BUY"  if buy_pct > sell_pct else "SELL"
    dom_col = MG if dom == "BUY" else RD
    reg_c   = MG if regime == "TRENDING" else "yellow" if regime == "RANGING" else RD
    reg_sym = "▲" if regime == "TRENDING" else "≈" if regime == "RANGING" else "⚠"
    pulse   = f"[blink {dom_col}]◆[/]" if BLINK else f"[{dom_col}]◇[/]"
    sent_t  = Text.from_markup(
        f" [{DG}]BUY [/]  {b_bar} [{MG if dom=='BUY' else 'dim'}]{buy_pct:.0f}%[/]\n"
        f" [{DG}]SELL[/]  {s_bar} [{RD if dom=='SELL' else 'dim'}]{sell_pct:.0f}%[/]\n"
        f" [{reg_c}]{reg_sym} {regime[:5]}[/]  {pulse} [{dom_col}]{dom}[/]"
    )
    layout["sentiment"].update(
        Panel(sent_t, title=_T("SIGNAL.SCAN"), border_style="magenta", padding=(0, 0))
    )

    # ── CHAIN STATUS (shared) ──────────────────────────────────────────────────
    _cs      = analyst.get_chain_status()
    _dir     = _cs["direction"]
    _opp     = _cs["opposite"]
    _d_col   = MG if _dir == "BUY" else RD if _dir == "SELL" else "white"
    cf_fired = _cs["cf_ready"]
    cf_type  = _cs.get("cf_type", "")
    _depth   = _cs.get("cascade_depth", 0)
    _roles   = _cs.get("cascade_roles", {})
    _h4_dir  = analyst.states["H4"].cmp
    _h4_col  = MG if _h4_dir == "BUY" else RD if _h4_dir == "SELL" else "white"
    _d_arr   = "▲" if _h4_dir == "BUY" else "▼" if _h4_dir == "SELL" else "·"
    _c_arr   = "▼" if _h4_dir == "BUY" else "▲"

    def _tf_chip(tf_name):
        role = _roles.get(tf_name, "WAIT")
        if role == "WAIT": return f"[dim]{tf_name}?[/]"
        if role == "VR":   return f"[{CC}]{tf_name}{_c_arr}[VR][/]"
        if role == "CF":   return f"[{_h4_col}]{tf_name}{_d_arr}[CF][/]"
        return f"[{_h4_col}]{tf_name}{_d_arr}[/]"

    cascade_chips = " → ".join(_tf_chip(tf) for tf in ["H1","M30","M15","M5"])

    def _sicon(ok):
        return (f"[{MG}]▣[/]" if BLINK else f"[green]▣[/]") if ok else f"[{DG}]□[/]"

    s1_ok = _cs["step1_ok"]
    s2_ok = _cs["m15_is_vr"] or _cs["m15_solid"]
    s3_ok = cf_fired

    s1_lbl = f"[{_d_col}]{_dir}[/]"  if s1_ok else f"[{DG}]──[/]"
    s1_sub = "M30 CMP locked"          if s1_ok else "Tunggu breakout M30"
    if _cs["m15_is_vr"]:
        s2_lbl = f"[{CC}]VR ACTIVE[/]";  s2_sub = "M15 menguji M30"
    elif _cs["m15_solid"]:
        s2_lbl = f"[{MG}]SOLID[/]";      s2_sub = "M15 aligned"
    else:
        s2_lbl = f"[{DG}]──[/]";         s2_sub = ""
    if cf_fired:
        if cf_type == "MINOR_CF":
            s3_lbl = f"[blink {MG}]MINOR_CF[/]" if BLINK else f"[{MG}]MINOR_CF[/]"
            s3_sub = "SL=M5  TP=M15"
        elif cf_type == "CF_LOW":
            s3_lbl = f"[blink {MG}]CF_LOW[/]"   if BLINK else f"[{MG}]CF_LOW[/]"
            s3_sub = "SL=M15 TP=M30"
        else:
            s3_lbl = f"[blink yellow]CF_HIGH[/]" if BLINK else "[yellow]CF_HIGH[/]"
            s3_sub = "SL=M15 TP=M30"
    else:
        s3_lbl = f"[{DG}]──[/]"; s3_sub = "Tunggu M5/M15 CF"

    macro_m = _cs.get("macro_role", "SOLID_H4")
    macro_lbl = (f"[{RD}]M30⟵H4  !! BLOCK[/]"       if macro_m == "VR_H4" else
                 f"[magenta]M30⟵H4  CF_HIGH ⚡[/]"    if macro_m == "CF_HIGH_H4" else
                 f"[{CC}]H1⟶M30⟵H4  BUILDING[/]"    if macro_m == "CF_H4" else
                 f"[{MG}]M30⟵H4  SOLID[/]")

    _dep_col    = MG if _depth == 0 else "yellow" if _depth <= 2 else RD
    _steps_done = int(s1_ok) + int(s2_ok) + int(s3_ok)
    _rw         = 12
    _r_fill     = int(_steps_done / 3 * _rw)
    _r_col      = MG if _steps_done == 3 else "yellow" if _steps_done >= 1 else "dim"
    _ready_bar  = _bar(_r_fill, _rw, fill_color=_r_col, empty_color="grey19", fill_char="█", empty_char="░")

    if not s1_ok:
        next_txt = ">> SCAN M30 SNR..."; next_bc = DG
    elif _cs.get("m30_broken"):
        next_txt = "!! SETUP BATAL — CARI M30 BARU"; next_bc = RD
    elif cf_fired and cf_type == "MINOR_CF":
        next_txt = ">> SAFEST_ENTRY::FIRE()"; next_bc = MG
    elif cf_fired and cf_type == "CF_LOW":
        next_txt = ">> CF_LOW::FIRE()";         next_bc = MG
    elif cf_fired and cf_type == "CF_HIGH":
        next_txt = ">> CF_HIGH::FIRE()";         next_bc = "yellow"
    elif _cs["m15_solid"]:
        next_txt = f">> WAIT M5.flip({_opp}) → M5.cf({_dir})"; next_bc = CC
    elif _cs["m15_is_vr"]:
        next_txt = f">> WAIT M5.cf({_dir}) || M15.cf({_dir})"; next_bc = CC
    else:
        next_txt = f">> WAIT M15.solid({_dir}) || M15.vr({_opp})"; next_bc = CC

    # ── HIERARCHY MATRIX  (hacker style) ──────────────────────────────────────
    regime_str, _ = analyst.get_market_regime()
    reg_c = MG if regime_str=="TRENDING" else "yellow" if regime_str=="RANGING" else RD

    mx = Table(
        box=rich_box.SIMPLE_HEAD, expand=True, show_edge=False, padding=(0, 1),
        header_style=f"bold {CC} on grey11",
    )
    mx.add_column("TF",   justify="center", width=8)
    mx.add_column("CMP",  justify="center", width=7)
    mx.add_column("ROLE", justify="center", width=14)
    mx.add_column("SUP",  justify="right",  style="white",   width=8)
    mx.add_column("RES",  justify="right",  style="white",   width=8)

    tfs = ["MN1","W1","D1","H4","H1","M30","M15","M5"]
    scan_idx = frame % len(tfs)
    for i, tf in enumerate(tfs):
        st       = analyst.states[tf]
        scanning = (i == scan_idx)
        cmp_col  = MG if st.cmp == "BUY" else RD if st.cmp == "SELL" else "dim"

        if tf in ("MN1","W1","D1"):
            r_lbl = "MACRO";      r_col = _h4_col if st.cmp == _h4_dir else "dim"
        elif tf == "H4":
            r_lbl = "MASTER";     r_col = GD
        elif tf == "H1":
            r_lbl = "H1_VR" if (st.cmp!="WAIT" and st.cmp!=_h4_dir) else "H1_CMP"
            r_col = CC if "VR" in r_lbl else "white"
        elif tf == "M30":
            if st.cmp == "WAIT":
                r_lbl = "WAIT";     r_col = "dim"
            elif st.cmp == _h4_dir:
                r_lbl = "SETUP_CMP"; r_col = BC
            else:
                r_lbl = "VR→H4";    r_col = CC   # M30 counter H4 = VR ke H1
        elif tf == "M15":
            if _cs["m15_is_vr"]:    r_lbl = "VR ⚡";    r_col = CC
            elif _cs["m15_solid"]:  r_lbl = "SOLID ▣";  r_col = MG
            else:                   r_lbl = "STANDBY";   r_col = "dim"
        elif tf == "M5":
            if cf_fired and cf_type == "MINOR_CF":              r_lbl = "MINOR_CF ▣"; r_col = MG
            elif cf_fired:                                      r_lbl = f"{cf_type} ▣"; r_col = MG
            elif _cs["m15_solid"] and st.cmp!=_dir and st.cmp!="WAIT": r_lbl="VR→M15"; r_col="yellow"
            elif _cs["m15_is_vr"] and st.cmp!=_dir:            r_lbl = "VR";        r_col = "yellow"
            elif _cs["m15_is_vr"] and st.cmp==_dir:            r_lbl = "CF_ZONE";   r_col = CC
            else:                                               r_lbl = "STANDBY";   r_col = "dim"
        else:
            r_lbl = st.cmp; r_col = "white"

        if scanning:                        row_s = "bold on grey19"
        elif "MASTER" in r_lbl:            row_s = "on grey15"
        elif "CF" in r_lbl and tf == "M5": row_s = "on dark_green"
        elif "VR" in r_lbl:                row_s = "on dark_blue"
        elif "SOLID" in r_lbl:             row_s = "on grey23"
        else:                              row_s = ""

        scan_pfx = f"[blink {MG}]►[/]" if scanning and BLINK else ("►" if scanning else " ")
        tf_lbl   = f"{scan_pfx} {tf}"
        if scanning:
            tf_lbl += f"  [{DG}]{_htag(4)}[/]"

        # Jika ada background, paksa semua teks terang agar kontras
        if row_s:
            role_display = f"[bold white]{r_lbl}[/]"
            sup_c        = "bold white"
            res_c        = "bold white"
        else:
            role_display = f"[{r_col}]{r_lbl}[/]"
            sup_c        = "bright_green"
            res_c        = "bright_red"
        mx.add_row(
            tf_lbl,
            f"[{cmp_col}]{st.cmp}[/]",
            role_display,
            f"[{sup_c}]{st.sup:.1f}[/]",
            f"[{res_c}]{st.res:.1f}[/]",
            style=row_s,
        )

    aligned_n  = sum(1 for tf in tfs if analyst.states[tf].cmp == _h4_dir and _h4_dir != "WAIT")
    wib_now    = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%H:%M:%S")
    depth_bar  = _bar(min(_depth,5), 5, fill_color=_dep_col, empty_color="grey19")
    lat        = random.randint(8, 22)

    mx.add_row(f"[{DG}]──────[/]","─────","──────────","────────","────────")
    mx.add_row(f"[{CC}]SYNC[/]",  f"[{MG}]{aligned_n}/8[/]",  f"[{DG}]{wib_now}[/]", "", f"[{DG}]{lat}ms[/]")
    mx.add_row(f"[{CC}]DEPTH[/]", depth_bar, f"[{_dep_col}]D{_depth}[/]  [{reg_c}]{regime_str[:5]}[/]",
               "", f"[{_r_col}]{_steps_done}/3[/]")

    chain_border = (MG if BLINK else "green") if cf_fired else \
                   (RD if _cs.get("m30_broken") else CC)

    layout["matrix"].update(
        Panel(mx, title=_T("HIERARCHY.MATRIX"), border_style="magenta", padding=(0, 0))
    )

    # ── CHAIN REACTION STORYLINE  (TARGET ACQUISITION) ────────────────────────
    dir_arrow  = "▲" if _dir == "BUY" else "▼" if _dir == "SELL" else "·"
    dir_pct    = f"[{_r_col}]{_steps_done}/3[/]  {_ready_bar}"
    dir_banner = Text.from_markup(
        f"  [{_d_col}]{dir_arrow} {_dir}[/]"
        f"  [{DG}]|[/]  "
        f"[{_dep_col}]CASCADE_DEPTH::{_depth}[/]"
        f"  [{DG}]|[/]  "
        f"{dir_pct}"
    )

    cascade_text = Text.from_markup(
        f"  [{_h4_col}]H4{_d_arr}[/] → {cascade_chips}"
    )

    sep = Text("  " + "═" * 52, style=DG)

    steps_t = Table(box=None, expand=True, show_header=False, padding=(0, 1), show_edge=False)
    steps_t.add_column("", width=3,  justify="center")
    steps_t.add_column("", width=10, style="white")
    steps_t.add_column("", width=12, justify="right")
    steps_t.add_column("", ratio=1,  style="grey74")

    s1_rs = "bold on dark_green"     if s1_ok else ""
    s2_rs = "bold on dark_blue"      if _cs["m15_is_vr"] else "bold on dark_cyan" if _cs["m15_solid"] else ""
    s3_rs = ("bold on dark_green" if cf_type in ("MINOR_CF","CF_LOW") else "bold on dark_red") if cf_fired else ""

    steps_t.add_row(_sicon(s1_ok), "M30_CMP",   s1_lbl, s1_sub, style=s1_rs)
    steps_t.add_row(_sicon(s2_ok), "M15_STATE", s2_lbl, s2_sub, style=s2_rs)
    steps_t.add_row(_sicon(s3_ok), "CF_ENTRY",  s3_lbl, s3_sub, style=s3_rs)

    ctx_t = Table(box=None, expand=True, show_header=False, padding=(0, 1))
    ctx_t.add_column("", width=9, style="white")
    ctx_t.add_column("", ratio=1)
    ctx_t.add_row("MACRO",  macro_lbl)
    ctx_t.add_row("REGIME", f"[{reg_c}]{regime_str}[/]")

    # NEXT ACTION — styled as terminal command prompt
    next_blink = BLINK and "──" not in next_txt
    next_display = f"[blink {next_bc}]{next_txt}[/]" if next_blink else f"[{next_bc}]{next_txt}[/]"
    next_panel = Panel(
        Text.from_markup(f"  [grey62]>>>[/grey62]  {next_display}"),
        border_style=next_bc if next_bc not in ("dim","") else "green",
        height=3, padding=(0, 0),
    )

    pulse_c  = [BC, BY, BG, "bold magenta"][(frame // 3) % 4]
    blink_d  = f"[blink {MG}]◆[/]" if BLINK else f"[{MG}]◇[/]"
    cmdr_txt = Text.from_markup(
        f"[bold red]//[/bold red]  [{pulse_c}]C M D R :: D A D A N G  W A H Y U O N O[/{pulse_c}]  {blink_d}"
    )

    story_group = RichGroup(
        dir_banner, Text(""), cascade_text, sep,
        steps_t, sep, ctx_t, Text(""),
        next_panel, Text(""),
        Align.center(cmdr_txt),
    )
    layout["bs_matrix"].update(
        Panel(story_group,
              title=_T("TARGET.ACQUISITION"), border_style=chain_border, padding=(0, 1))
    )

    # ── LIQUIDITY  (ZONE RADAR) ────────────────────────────────────────────────
    h4s = analyst.states["H4"]
    d1s = analyst.states["D1"]
    cp  = tick.bid if tick else 0

    def _liq_row(st, label, col):
        if st.sup == 0 or st.res == 0:
            return f"[{col}]{label}[/]  [{DG}]SCANNING...[/]", ""
        rng = st.res - st.sup
        if rng <= 0:
            return f"[{col}]{label}[/]  [{DG}]─[/]", ""
        pct    = max(0.0, min(1.0, (cp - st.sup) / rng))
        pos    = int(pct * 26)
        bar    = list("─" * 26)
        marker = f"[blink {GD}]◆[/]" if BLINK else f"[{GD}]◆[/]"
        if 0 <= pos < 26: bar[pos] = marker
        bar_s  = "".join(bar)
        zone   = f"[{MG}]SUP_ZONE[/]" if pct < 0.3 else f"[{RD}]RES_ZONE[/]" if pct > 0.7 else "[yellow]MID_ZONE[/]"
        pct_r  = (1 - pct) * 100
        l1 = f"[{col}]{label}[/]  [bright_green]{st.sup:.1f}[/]|{bar_s}|[bright_red]{st.res:.1f}[/]"
        l2 = f"  [grey74]↑RES {st.res-cp:.1f}$ ({pct_r:.0f}%)[/]  [grey74]↓SUP {cp-st.sup:.1f}$[/]  {zone}"
        return l1, l2

    liq_t = Table(box=None, expand=True, show_header=False, padding=(0, 0))
    liq_t.add_column("", ratio=1)
    h4l1, h4l2 = _liq_row(h4s, "H4", BC)
    d1l1, d1l2 = _liq_row(d1s, "D1", BY)
    liq_t.add_row(h4l1); liq_t.add_row(h4l2)
    liq_t.add_row(d1l1); liq_t.add_row(d1l2)

    # ADR Meter
    adr_val, adr_used, adr_pct = get_adr_info(symbol)
    if adr_val is not None:
        adr_bw  = 20
        adr_f   = int((adr_pct or 0) / 100 * adr_bw)
        adr_col = MG if (adr_pct or 0) < 50 else "yellow" if (adr_pct or 0) < 80 else RD
        adr_bar = _bar(adr_f, adr_bw, fill_color=adr_col, empty_color="grey19")
        adr_txt = (
            f"  [grey62]ADR 14D:[/grey62] [white]{adr_val:.1f}$[/white]"
            f"  [grey62]Hari ini:[/grey62] [white]{adr_used:.1f}$[/white]"
            f"  {adr_bar} [{adr_col}]{adr_pct:.0f}%[/]"
        )
        liq_t.add_row(Text.from_markup(adr_txt))

    layout["liquidity"].update(
        Panel(liq_t, title=_T("ZONE.RADAR"), border_style=CC, padding=(0, 1))
    )

    # ── NEWS  (INTERCEPT FEED) ─────────────────────────────────────────────────
    news_ttl = settings.get("news_refresh_seconds", 300)
    now_ts   = time.time()
    if not hasattr(update_layout, "_cached_news") or \
       (now_ts - getattr(update_layout, "_news_last_fetch", 0)) >= news_ttl:
        update_layout._cached_news     = fetch_live_news()
        update_layout._news_last_fetch = now_ts
    news_items = update_layout._cached_news
    news_idx   = (frame // 30) % max(1, len(news_items))
    _src       = fetch_live_news._last_source
    _fwib      = fetch_live_news._last_fetch_wib
    _live_ind  = f"[{MG}]◉ {_src}[/]" if _src != "STATIC" else f"[{DG}]◌ STATIC[/]"
    layout["news"].update(
        Panel(
            Align.center(Text(news_items[news_idx], style=f"bold white")),
            title=f"[{BC}][ INTERCEPT.FEED ][/{BC}]  {_live_ind}  [{DG}]{_fwib}[/]",
            border_style="blue", padding=(0, 1),
        )
    )

    # ── TACTICAL FEED  (SYS LOG) ───────────────────────────────────────────────
    layout["feed"].update(
        Panel(Text.from_markup(feed.render()),
              title=_T("SYS.LOG"), border_style=MG, padding=(0, 1))
    )

    # ── NEW ANIMATED PANELS ────────────────────────────────────────────────────
    layout["heatmap"].update(build_heatmap_panel(frame, analyst, _cs, _h4_dir))
    layout["neural"].update(build_neural_flow_panel(frame, analyst, _cs, _h4_dir))
    layout["equity"].update(build_equity_curve_panel(frame, acc))
    layout["oscillo"].update(build_oscilloscope_panel(frame, pos_rows))

    # ── TICKER ──────────────────────────────────────────────────────────────────
    pkt   = f"{random.randint(100000,999999)}"
    ticker_text = Text.from_markup(
        f"[{DG}]PKT:{pkt}[/]  "
        f"[{CC}]SESSIONS:[/{CC}]  {get_session_times()}"
        f"  [{DG}]║[/]  "
        f"[{CC}]VOLATILITY:[/{CC}]  {get_market_volatility()}"
        f"  [{DG}]║[/]  "
        f"[{MG}]CORE::ACTIVE[/]"
        f"  [{DG}]║[/]  "
        f"[{BY}]FIREWALL::SECURED[/]"
        f"  [{DG}]PKT_OK[/]"
    )
    layout["ticker"].update(
        Panel(Align.center(ticker_text), border_style="grey35", padding=(0, 0))
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
