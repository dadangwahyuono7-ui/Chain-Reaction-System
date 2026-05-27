"""
SCALP BACKTEST — 3 External Techniques for XAU Validation
Data: M30 CSV (2017-2026). Tidak butuh MT5.

============================================================
BROKER TIME NOTE:
  Kebanyakan MT5 broker XAUUSD pakai UTC+2 (winter) atau UTC+3 (summer).
  Default asumsi: UTC+2. Adjust BROKER_UTC_OFFSET di bawah jika perlu.

  Asian session proxy : 00:00–07:00 broker time
  London open window  : 07:00–12:00 broker time
  NY open window      : 13:00–18:00 broker time
============================================================

Technique 1: Asian Range Breakout (ARB)
  Kumpulkan high/low selama Asian session. Entry ketika London open breakout
  dari range. SL = sisi berlawanan range + buffer. TP = 2x range atau fixed RR.
  Filter: range 5–40 pips (terlalu sempit = false breakout, terlalu lebar = risk tinggi).

Technique 2: PDH/PDL Magnet (PDM)
  Teori: harga XAU cenderung touch PDH atau PDL minimal sekali per hari
  (liquidity hunting). Setelah London open, jika harga mendekati PDH dari bawah
  -> BUY entry, TP = PDH. Sebaliknya untuk PDL.
  SL = 20 pips dari entry. Max 1 trade per hari.

Technique 3: London Open Momentum (LOM)
  Baca 2 bar M30 pertama setelah London open (07:00 + 07:30). Jika keduanya
  bullish -> BUY di close bar kedua. Keduanya bearish -> SELL.
  Filter: first bar range > MIN_FIRST_BAR_PIPS. SL = opposite extreme, TP = RR 1:2.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box as rich_box

from backtest.backtest import Trade, PIP, print_report

console = Console()

# ── Config ────────────────────────────────────────────────────────────────────

CSV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DATACSV")

# ─────────────────── TUNING PARAMETERS ──────────────────────
# Broker timezone offset (hours). UTC+2 = default untuk IC Markets / Pepperstone
BROKER_UTC_OFFSET = 2

# Asian session hours (broker time, inclusive)
ASIAN_HOUR_START = 0    # 00:00
ASIAN_HOUR_END   = 6    # last bar open at 06:30 = session ends ~07:00

# London open window (broker time)
LONDON_HOUR_START = 7
LONDON_HOUR_END   = 11  # entry signals hanya dari jam 7 sampai 11

# NY open window (broker time)
NY_HOUR_START = 13
NY_HOUR_END   = 17

# ARB: range filter
ARB_MIN_RANGE_PIPS = 5.0   # range terlalu sempit -> skip
ARB_MAX_RANGE_PIPS = 40.0  # range terlalu lebar -> risk tinggi, skip

# PDM: entry trigger distance from PDH/PDL
PDM_APPROACH_PIPS  = 10.0  # masuk ketika harga dalam X pip dari PDH/PDL
PDM_SL_PIPS        = 20.0  # SL = X pip dari entry
PDM_MIN_HOUR       = LONDON_HOUR_START  # hanya cari signal setelah London open

# LOM: first bar momentum filter
LOM_MIN_FIRST_BAR_PIPS = 5.0   # first bar range minimal X pip

# Trade exit: max bars open (M30 bars = jam)
MAX_HOLD_BARS = 24   # max 12 jam untuk ARB/PDM/LOM
SL_BUFFER     = 3.0  # pips extra di luar SL reference
# ─────────────────────────────────────────────────────────────


# ── Data Loader ───────────────────────────────────────────────────────────────

def load_m30(start: str, end: str) -> pd.DataFrame:
    """Load M30 CSV, filter ke periode."""
    path = os.path.join(CSV_DIR, "XAUUSDM30.csv")
    if not os.path.exists(path):
        console.print(f"[red]ERROR: XAUUSDM30.csv tidak ada di DATACSV/[/]")
        return pd.DataFrame()

    df = pd.read_csv(
        path, header=None, encoding="utf-16", sep=",",
        names=["time", "open", "high", "low", "close", "tick_volume", "spread"]
    )
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M")
    df = df.drop(columns=["spread"])
    df = df.sort_values("time").reset_index(drop=True)

    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    df = df[(df["time"] >= s) & (df["time"] <= e)].reset_index(drop=True)

    console.print(
        f"  [green]M30[/] — {len(df):,} bars  "
        f"[grey62]({df['time'].iloc[0].date()} -> {df['time'].iloc[-1].date()})[/]"
    )
    return df


def simulate_trade(df: pd.DataFrame, start_idx: int, trade: Trade) -> dict | None:
    """
    Simulasikan trade mulai dari bar start_idx+1 (entry sudah di start_idx close).
    Kembalikan result dict atau None jika max hold tercapai tanpa TP/SL.
    """
    for i in range(start_idx + 1, min(start_idx + 1 + MAX_HOLD_BARS, len(df))):
        bar  = df.iloc[i]
        res  = trade.check(bar["high"], bar["low"], bar["time"])
        if res is not None:
            return res

    # Max hold habis -> force close di close bar terakhir
    last_i = min(start_idx + MAX_HOLD_BARS, len(df) - 1)
    last   = df.iloc[last_i]
    return trade._result(last["close"], "EOD", last["time"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hour(ts: pd.Timestamp) -> int:
    return ts.hour

def _date(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.normalize()  # midnight of that day


# ════════════════════════════════════════════════════════════════════════
# TECHNIQUE 1: Asian Range Breakout (ARB)
# ════════════════════════════════════════════════════════════════════════

def run_arb(df: pd.DataFrame, rr_ratio: float = 0.0) -> list:
    """
    Asian Range Breakout.

    Logic:
    1. Kumpulkan bar Asian session (jam 00:00-06:59 broker time)
    2. asian_high = max(high), asian_low = min(low)
    3. Filter: range antara ARB_MIN_RANGE_PIPS dan ARB_MAX_RANGE_PIPS
    4. Di London open window (07:00-11:59):
       - Bar pertama yang close > asian_high -> BUY
       - Bar pertama yang close < asian_low  -> SELL
    5. SL = sisi berlawanan range + SL_BUFFER pips
    6. TP = 2x range (jika rr_ratio=0) atau fixed RR
    7. Max 1 trade per hari, hanya entry pertama yang valid
    """
    trades    = []
    n         = len(df)
    df_dates  = df["time"].dt.normalize()
    all_dates = df_dates.unique()

    for date in all_dates:
        day_mask  = df_dates == date
        day_bars  = df[day_mask].reset_index(drop=True)

        # Asian session bars
        asian = day_bars[day_bars["time"].dt.hour.between(ASIAN_HOUR_START, ASIAN_HOUR_END)]
        if len(asian) < 3:
            continue

        asian_high = asian["high"].max()
        asian_low  = asian["low"].min()
        rng_pips   = (asian_high - asian_low) / PIP

        if rng_pips < ARB_MIN_RANGE_PIPS or rng_pips > ARB_MAX_RANGE_PIPS:
            continue

        # London window bars
        london = day_bars[day_bars["time"].dt.hour.between(LONDON_HOUR_START, LONDON_HOUR_END)]
        if len(london) == 0:
            continue

        # Cari breakout pertama
        for _, bar_row in london.iterrows():
            sig  = None
            idx  = df[df["time"] == bar_row["time"]].index
            if len(idx) == 0:
                continue
            global_idx = idx[0]
            close = bar_row["close"]

            if close > asian_high:
                # BUY breakout
                entry = close
                sl    = asian_low - SL_BUFFER * PIP
                if rr_ratio > 0:
                    tp = entry + (entry - sl) * rr_ratio
                else:
                    tp = entry + rng_pips * 2 * PIP  # 2x range
                sig = "BUY"

            elif close < asian_low:
                # SELL breakout
                entry = close
                sl    = asian_high + SL_BUFFER * PIP
                if rr_ratio > 0:
                    tp = entry - (sl - entry) * rr_ratio
                else:
                    tp = entry - rng_pips * 2 * PIP
                sig = "SELL"

            if sig and sl > 0 and tp > 0:
                if (sig == "BUY"  and tp > entry > sl) or \
                   (sig == "SELL" and tp < entry < sl):
                    t   = Trade(sig, entry, sl, tp, "ARB", bar_row["time"])
                    res = simulate_trade(df, global_idx, t)
                    if res:
                        res["sub_type"] = "ARB"
                        trades.append(res)
                    break  # max 1 trade per hari

    return trades


# ════════════════════════════════════════════════════════════════════════
# TECHNIQUE 2: PDH/PDL Magnet (PDM)
# ════════════════════════════════════════════════════════════════════════

def run_pdm(df: pd.DataFrame) -> list:
    """
    PDH/PDL Magnet.

    Logic:
    1. Hitung PDH (previous day high) dan PDL (previous day low)
    2. Setelah London open (PDM_MIN_HOUR):
       a. Jika harga BELUM touch PDH hari ini, dan close dalam PDM_APPROACH_PIPS di bawah PDH
          -> BUY entry. TP = PDH. SL = entry - PDM_SL_PIPS.
       b. Jika harga BELUM touch PDL hari ini, dan close dalam PDM_APPROACH_PIPS di atas PDL
          -> SELL entry. TP = PDL. SL = entry + PDM_SL_PIPS.
    3. Max 1 trade per hari, prioritas siapa yang approach duluan.
    4. "Touch" = bar high >= PDH (untuk PDH) atau bar low <= PDL (untuk PDL).
    """
    trades   = []
    n        = len(df)

    # Pre-compute daily OHLC
    df["date"]      = df["time"].dt.normalize()
    daily           = df.groupby("date").agg(
        day_high=("high", "max"),
        day_low=("low", "min")
    ).reset_index()
    daily           = daily.sort_values("date").reset_index(drop=True)

    date_to_pdh = {}
    date_to_pdl = {}
    for i in range(1, len(daily)):
        d          = daily.iloc[i]["date"]
        prev       = daily.iloc[i - 1]
        date_to_pdh[d] = float(prev["day_high"])
        date_to_pdl[d] = float(prev["day_low"])

    df_dates = df["date"]
    all_dates = sorted(df_dates.unique())

    for date in all_dates:
        pdh = date_to_pdh.get(date)
        pdl = date_to_pdl.get(date)
        if pdh is None or pdl is None:
            continue

        day_mask = df_dates == date
        day_bars = df[day_mask].reset_index(drop=True)

        touched_pdh = False
        touched_pdl = False
        traded      = False

        for _, bar_row in day_bars.iterrows():
            h  = bar_row["hour"] if "hour" in bar_row else _hour(bar_row["time"])
            hi = bar_row["high"]
            lo = bar_row["low"]
            cl = bar_row["close"]

            # Update touch flags
            if hi >= pdh:
                touched_pdh = True
            if lo <= pdl:
                touched_pdl = True

            if traded or h < PDM_MIN_HOUR:
                continue

            idx = df[df["time"] == bar_row["time"]].index
            if len(idx) == 0:
                continue
            global_idx = idx[0]

            # BUY: approaching PDH from below
            if (not touched_pdh and
                    cl <= pdh and
                    (pdh - cl) / PIP <= PDM_APPROACH_PIPS):
                entry = cl
                sl    = entry - PDM_SL_PIPS * PIP
                tp    = pdh
                if tp > entry > sl:
                    t   = Trade("BUY", entry, sl, tp, "PDM", bar_row["time"])
                    res = simulate_trade(df, global_idx, t)
                    if res:
                        res["sub_type"] = "PDM_H"
                        trades.append(res)
                    traded = True

            # SELL: approaching PDL from above
            elif (not touched_pdl and
                      cl >= pdl and
                      (cl - pdl) / PIP <= PDM_APPROACH_PIPS):
                entry = cl
                sl    = entry + PDM_SL_PIPS * PIP
                tp    = pdl
                if tp < entry < sl:
                    t   = Trade("SELL", entry, sl, tp, "PDM", bar_row["time"])
                    res = simulate_trade(df, global_idx, t)
                    if res:
                        res["sub_type"] = "PDM_L"
                        trades.append(res)
                    traded = True

    return trades


# ════════════════════════════════════════════════════════════════════════
# TECHNIQUE 3: London Open Momentum (LOM)
# ════════════════════════════════════════════════════════════════════════

def run_lom(df: pd.DataFrame, rr_ratio: float = 2.0) -> list:
    """
    London Open Momentum.

    Logic:
    1. Bar 1: bar M30 yang open tepat jam LONDON_HOUR_START (07:00)
    2. Bar 2: bar M30 berikutnya (07:30)
    3. Jika keduanya bullish (close > open): BUY entry di close bar 2
    4. Jika keduanya bearish: SELL entry di close bar 2
    5. Filter: range bar 1 >= LOM_MIN_FIRST_BAR_PIPS (konfirmasi ada momentum)
    6. SL: low bar 1 & 2 (BUY) atau high bar 1 & 2 (SELL)
    7. TP: fixed RR dari SL
    8. Max 1 trade per hari
    """
    trades = []
    n      = len(df)

    df_dates  = df["time"].dt.normalize()
    all_dates = df_dates.unique()

    for date in all_dates:
        day_mask  = df_dates == date
        day_bars  = df[day_mask].copy()

        # Bar 1: jam LONDON_HOUR_START
        bar1_mask = day_bars["time"].dt.hour == LONDON_HOUR_START
        bar1_rows = day_bars[bar1_mask]
        if len(bar1_rows) == 0:
            continue
        bar1 = bar1_rows.iloc[0]

        # Bar 2: bar berikutnya setelah bar 1
        bar1_global_idx = df[df["time"] == bar1["time"]].index
        if len(bar1_global_idx) == 0:
            continue
        b1_idx = bar1_global_idx[0]
        if b1_idx + 1 >= n:
            continue
        bar2       = df.iloc[b1_idx + 1]
        b2_idx     = b1_idx + 1

        # Filter: range bar 1
        bar1_range = (bar1["high"] - bar1["low"]) / PIP
        if bar1_range < LOM_MIN_FIRST_BAR_PIPS:
            continue

        b1_bull = bar1["close"] > bar1["open"]
        b2_bull = bar2["close"] > bar2["open"]
        b1_bear = bar1["close"] < bar1["open"]
        b2_bear = bar2["close"] < bar2["open"]

        sig = None
        if b1_bull and b2_bull:
            sig = "BUY"
        elif b1_bear and b2_bear:
            sig = "SELL"

        if sig is None:
            continue

        entry = bar2["close"]
        if sig == "BUY":
            sl = min(bar1["low"], bar2["low"]) - SL_BUFFER * PIP
            tp = entry + (entry - sl) * rr_ratio
        else:
            sl = max(bar1["high"], bar2["high"]) + SL_BUFFER * PIP
            tp = entry - (sl - entry) * rr_ratio

        if sl <= 0 or tp <= 0:
            continue
        if (sig == "BUY"  and not (tp > entry > sl)) or \
           (sig == "SELL" and not (tp < entry < sl)):
            continue

        t   = Trade(sig, entry, sl, tp, "LOM", bar2["time"])
        res = simulate_trade(df, b2_idx, t)
        if res:
            res["sub_type"] = "LOM"
            trades.append(res)

    return trades


# ── Report: single technique ──────────────────────────────────────────────────

def _technique_report(trades: list, name: str, total_days: int):
    if not trades:
        console.print(f"[yellow]{name}: tidak ada trade.[/]")
        return

    wins       = [t for t in trades if t["pips"] > 0]
    losses     = [t for t in trades if t["pips"] <= 0]
    total_pips = sum(t["pips"] for t in trades)
    win_rate   = len(wins) / len(trades) * 100
    avg_win    = sum(t["pips"] for t in wins)  / len(wins)   if wins   else 0
    avg_loss   = sum(t["pips"] for t in losses)/ len(losses) if losses else 0
    pf         = abs(avg_win / avg_loss) if avg_loss else float("inf")
    freq       = len(trades) / total_days if total_days > 0 else 0

    MG = "bright_green"; RD = "bright_red"; CC = "bright_cyan"
    DG = "grey62"; GD = "gold1"

    wr_col  = MG if win_rate >= 55 else GD if win_rate >= 45 else RD
    pf_col  = MG if pf >= 1.5 else GD if pf >= 1.0 else RD
    pnl_col = MG if total_pips >= 0 else RD

    # Exit breakdown
    by_exit: dict = {}
    for t in trades:
        r = t["reason"]
        by_exit[r] = by_exit.get(r, 0) + 1

    t_row = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0, 2), expand=False)
    t_row.add_column("METRIC", style=DG, width=20)
    t_row.add_column("VALUE",  justify="right", width=12)
    t_row.add_column("METRIC", style=DG, width=20)
    t_row.add_column("VALUE",  justify="right", width=12)

    rows = [
        ("Total Trades",  f"[white]{len(trades)}[/]",
         "Freq/Day",      f"[white]{freq:.2f}[/]"),
        ("Win Rate",      f"[{wr_col}]{win_rate:.1f}%[/]",
         "Profit Factor", f"[{pf_col}]{pf:.2f}[/]"),
        ("Total Pips",    f"[{pnl_col}]{total_pips:+.1f}[/]",
         "Avg Win",       f"[{MG}]{avg_win:+.1f}p[/]"),
        ("Wins / Losses", f"[{MG}]{len(wins)}[/] / [{RD}]{len(losses)}[/]",
         "Avg Loss",      f"[{RD}]{avg_loss:+.1f}p[/]"),
    ]
    exit_str = "  ".join(f"{r}:{c}" for r, c in sorted(by_exit.items()))
    rows.append(("Exits", f"[grey62]{exit_str}[/]", "", ""))

    for r in rows:
        t_row.add_row(*r)

    console.print(Panel(
        t_row,
        title=f"[bold {CC}]{name}[/]",
        border_style="cyan", padding=(0, 1)
    ))


# ── Comparison Summary ────────────────────────────────────────────────────────

def _comparison_table(results: dict):
    """Satu baris per teknik untuk perbandingan langsung."""
    CC = "bright_cyan"; DG = "grey62"; MG = "bright_green"
    RD = "bright_red";  GD = "gold1"

    console.print()
    console.rule("[bold bright_cyan]COMPARISON — 3 TECHNIQUES[/]")

    tbl = Table(box=rich_box.DOUBLE_EDGE, show_header=True,
                header_style="bold bright_cyan", expand=False, padding=(0, 2))
    tbl.add_column("TECHNIQUE", style="bold", width=10)
    tbl.add_column("TRADES",    justify="right", width=8)
    tbl.add_column("WIN%",      justify="right", width=8)
    tbl.add_column("PF",        justify="right", width=6)
    tbl.add_column("TOTAL PIPS",justify="right", width=12)
    tbl.add_column("AVG WIN",   justify="right", width=9)
    tbl.add_column("AVG LOSS",  justify="right", width=9)
    tbl.add_column("VERDICT",   justify="center", width=14)

    for name, trades in results.items():
        if not trades:
            tbl.add_row(name, "0", "—", "—", "—", "—", "—", "[grey62]No trades[/]")
            continue

        wins       = [t for t in trades if t["pips"] > 0]
        losses     = [t for t in trades if t["pips"] <= 0]
        total_pips = sum(t["pips"] for t in trades)
        wr         = len(wins) / len(trades) * 100 if trades else 0
        avg_win    = sum(t["pips"] for t in wins)  / len(wins)   if wins   else 0
        avg_loss   = sum(t["pips"] for t in losses)/ len(losses) if losses else 0
        pf         = abs(avg_win / avg_loss) if avg_loss else float("inf")

        wr_col  = MG if wr >= 55 else GD if wr >= 45 else RD
        pf_col  = MG if pf >= 1.5 else GD if pf >= 1.0 else RD
        pnl_col = MG if total_pips >= 0 else RD

        if pf >= 1.5 and wr >= 50:
            verdict = f"[bold {MG}]STRONG EDGE[/]"
        elif pf >= 1.2 and wr >= 45:
            verdict = f"[bold {GD}]MODERATE[/]"
        elif pf >= 1.0:
            verdict = f"[{GD}]MARGINAL[/]"
        else:
            verdict = f"[bold {RD}]NO EDGE[/]"

        tbl.add_row(
            name,
            str(len(trades)),
            f"[{wr_col}]{wr:.1f}%[/]",
            f"[{pf_col}]{pf:.2f}[/]",
            f"[{pnl_col}]{total_pips:+.1f}[/]",
            f"[{MG}]{avg_win:+.1f}[/]",
            f"[{RD}]{avg_loss:+.1f}[/]",
            verdict,
        )

    console.print(tbl)


# ── Monthly P&L Heatmap ───────────────────────────────────────────────────────

def _monthly_heatmap(all_trades: list, technique_name: str):
    if not all_trades:
        return

    MG = "bright_green"; RD = "bright_red"; DG = "grey62"
    console.print(f"\n[bold bright_cyan]MONTHLY P&L — {technique_name}[/]")

    monthly: dict = {}
    for t in all_trades:
        key = t["open_time"].strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0.0) + t["pips"]

    tbl = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
    years = sorted(set(k[:4] for k in monthly))
    tbl.add_column("YEAR", style=DG, width=6)
    for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]:
        tbl.add_column(m, justify="right", width=7)
    tbl.add_column("TOTAL", justify="right", width=9)

    for yr in years:
        row    = [yr]
        yearly = 0.0
        for mo in range(1, 13):
            key = f"{yr}-{mo:02d}"
            v   = monthly.get(key, None)
            if v is None:
                row.append(f"[{DG}]—[/]")
            else:
                col = MG if v > 0 else RD
                row.append(f"[{col}]{v:+.0f}[/]")
                yearly += v
        col = MG if yearly > 0 else RD
        row.append(f"[bold {col}]{yearly:+.0f}[/]")
        tbl.add_row(*row)

    console.print(tbl)


# ── Main Runner ───────────────────────────────────────────────────────────────

def run_scalp_backtest(
    start:      str   = "2020-01-01",
    end:        str   = "2026-05-20",
    arb_rr:     float = 0.0,   # ARB TP: 0 = 2x range natural, >0 = fixed RR
    lom_rr:     float = 2.0,   # LOM TP: fixed RR (default 1:2)
    show_trades: bool = False,  # tampilkan trade log detail
):
    """
    Jalankan ketiga teknik dan bandingkan hasilnya.
    Data source: backtest/DATACSV/XAUUSDM30.csv
    """
    console.print(Panel(
        "[bold bright_cyan]SCALP BACKTEST — 3 EXTERNAL TECHNIQUES[/]\n"
        "[grey62]XAU/USD M30 | Asian Range Breakout | PDH/PDL Magnet | London Open Momentum[/]",
        border_style="cyan", padding=(0, 2)
    ))
    console.print(f"\n[grey62]Loading M30 data {start} -> {end}...[/]")

    df = load_m30(start, end)
    if len(df) == 0:
        return

    # Precompute hour column untuk speed
    df["hour"] = df["time"].dt.hour

    total_days = len(df["time"].dt.normalize().unique())
    console.print(f"  [grey62]Trading days: {total_days}[/]\n")

    # ── Run all 3 ──────────────────────────────────────────────────────────────
    console.print("[cyan]Running Technique 1: Asian Range Breakout...[/]")
    arb_trades = run_arb(df, rr_ratio=arb_rr)
    console.print(f"  -> {len(arb_trades)} trades\n")

    console.print("[cyan]Running Technique 2: PDH/PDL Magnet...[/]")
    pdm_trades = run_pdm(df)
    console.print(f"  -> {len(pdm_trades)} trades\n")

    console.print("[cyan]Running Technique 3: London Open Momentum...[/]")
    lom_trades = run_lom(df, rr_ratio=lom_rr)
    console.print(f"  -> {len(lom_trades)} trades\n")

    # ── Per-technique reports ──────────────────────────────────────────────────
    _technique_report(arb_trades, "TECHNIQUE 1 — Asian Range Breakout (ARB)", total_days)
    _technique_report(pdm_trades, "TECHNIQUE 2 — PDH/PDL Magnet (PDM)", total_days)
    _technique_report(lom_trades, "TECHNIQUE 3 — London Open Momentum (LOM)", total_days)

    # ── Comparison ─────────────────────────────────────────────────────────────
    _comparison_table({
        "ARB": arb_trades,
        "PDM": pdm_trades,
        "LOM": lom_trades,
    })

    # ── Monthly heatmaps ───────────────────────────────────────────────────────
    _monthly_heatmap(arb_trades, "ARB")
    _monthly_heatmap(pdm_trades, "PDM")
    _monthly_heatmap(lom_trades, "LOM")

    # ── Optional trade log ─────────────────────────────────────────────────────
    if show_trades:
        for name, trades in [("ARB", arb_trades), ("PDM", pdm_trades), ("LOM", lom_trades)]:
            if not trades:
                continue
            CC = "bright_cyan"; DG = "grey62"; MG = "bright_green"; RD = "bright_red"; GD = "gold1"
            console.print(f"\n[{CC}]── {name} TRADE LOG (last 20) ──────────────────────────────[/]")
            tl = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
            tl.add_column("#",     style=DG,       width=4)
            tl.add_column("OPEN",  style=DG,       width=17)
            tl.add_column("DIR",   justify="center",width=5)
            tl.add_column("ENTRY", justify="right", width=8)
            tl.add_column("SL",    justify="right", width=8)
            tl.add_column("TP",    justify="right", width=8)
            tl.add_column("EXIT",  justify="right", width=8)
            tl.add_column("PIPS",  justify="right", width=8)
            tl.add_column("RES",   justify="center",width=5)

            for i, tr in enumerate(trades[-20:], max(1, len(trades) - 19)):
                dc = MG if tr["direction"] == "BUY" else RD
                pc = MG if tr["pips"] > 0 else RD
                rc = (MG if tr["reason"] == "TP" else
                      "yellow" if tr["reason"] == "BE" else
                      GD if tr["reason"] in ("EOD", "H4_END") else RD)
                tl.add_row(
                    str(i),
                    str(tr["open_time"])[:16],
                    f"[{dc}]{tr['direction'][:1]}[/]",
                    f"{tr['entry']:.2f}",
                    f"[{RD}]{tr['sl']:.2f}[/]",
                    f"[{MG}]{tr['tp']:.2f}[/]",
                    f"{tr['exit']:.2f}",
                    f"[{pc}]{tr['pips']:+.1f}[/]",
                    f"[{rc}]{tr['reason']}[/]",
                )
            console.print(tl)

    console.print("\n[grey62]Done.[/]")
    return {"ARB": arb_trades, "PDM": pdm_trades, "LOM": lom_trades}


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ═════════════════════════════ CONFIG ══════════════════════════════
    START       = "2020-01-01"    # M30 ada dari 2017, tapi XAU lebih aktif 2020+
    END         = "2026-05-20"

    ARB_RR      = 0.0    # 0 = 2x Asian range natural | 1.5 = fixed 1:1.5 RR
    LOM_RR      = 2.0    # LOM fixed RR (default 1:2)
    SHOW_TRADES = False  # True = tampilkan trade log detail tiap teknik
    # ═══════════════════════════════════════════════════════════════════

    run_scalp_backtest(
        start        = START,
        end          = END,
        arb_rr       = ARB_RR,
        lom_rr       = LOM_RR,
        show_trades  = SHOW_TRADES,
    )
