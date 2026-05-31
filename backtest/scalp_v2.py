"""
SCALP BACKTEST v2 -- Deep Optimization
XAU/USD M30 + H4 CSV. Tidak butuh MT5.

Pipeline:
  1. Build H4 CMP timeline (state per 4h dari H4 CSV)
  2. Sweep semua variasi LOM (London Open Momentum)
     - RR: 1.5 / 2.0 / 2.5
     - H4 filter: on / off
     - Window: full (07-11) / tight (07-08)
  3. NY Open Momentum (NOM) -- variasi yang sama
  4. PDH/PDL Breakout (PDB) -- trade THROUGH level, bukan approaching
  5. ARB v2 -- Asian Range + H4 filter + 1.5x TP
  6. Combined: LOM_BEST + PDM confluence filter
  7. Rank semua variasi by Profit Factor (min 100 trades)
  8. Monthly heatmap top 3
"""

import sys, os, bisect
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box as rich_box

from engine.core import TFState
from backtest.backtest import Trade, PIP, TF_MINUTES
from backtest.scalp_backtest import load_m30, simulate_trade

console = Console()

# ============================================================
# CONSTANTS
# ============================================================
PIP           = 0.1
SL_BUFFER     = 3.0   # pips extra di luar SL reference
MAX_HOLD_BARS = 24    # max bars open sebelum force close (24 M30 = 12 jam)

# Session hours (broker time, asumsi UTC+2)
ASIAN_START   = 0;  ASIAN_END   = 6
LONDON_START  = 7;  LONDON_END  = 11
LONDON_TIGHT_END = 8   # tight window = 07:00-08:30 saja (bar 07:00 + 07:30)
NY_START      = 13; NY_END      = 17

# PDH/PDL
PDM_APPROACH  = 10.0  # pips dari level untuk trigger entry
PDM_SL        = 20.0  # pips SL
PDB_SL_BUF   = 5.0   # pips SL di luar level untuk PDB
MIN_PDR       = 20.0  # min previous-day range pips untuk PDH/PDL valid

# ARB
ARB_MIN_RANGE = 5.0
ARB_MAX_RANGE = 35.0


# ============================================================
# H4 CMP TIMELINE
# ============================================================

def build_h4_timeline(h4_df: pd.DataFrame) -> tuple:
    """
    Pre-compute H4 TFState setelah setiap bar close.
    Returns (timeline dict, sorted close times list).
    Timeline key = bar_close_time = bar_open_time + 4h.
    Lookup: cari last entry where close_time <= query_time.
    """
    state       = TFState("H4")
    timeline    = {}
    n           = len(h4_df)

    for i in range(n):
        lo      = max(0, i - 99)
        visible = h4_df.iloc[lo:i+1].reset_index(drop=True)
        if len(visible) >= 3:
            state.update(visible, "WAIT", 0.0)
        close_t = h4_df.iloc[i]["time"] + pd.Timedelta(hours=4)
        timeline[close_t] = state.cmp

    sorted_ct = sorted(timeline.keys())
    console.print(
        f"  [green]H4 CMP timeline[/] -- {len(timeline):,} snapshots  "
        f"[grey62]({sorted_ct[0].date()} -> {sorted_ct[-1].date()})[/]"
    )
    return timeline, sorted_ct


def h4_cmp_at(timeline: dict, sorted_ct: list, t: pd.Timestamp) -> str:
    """H4 CMP yang valid saat waktu t (hanya bar yang sudah fully closed)."""
    idx = bisect.bisect_right(sorted_ct, t) - 1
    return timeline[sorted_ct[idx]] if idx >= 0 else "WAIT"


# ============================================================
# DAILY HELPERS
# ============================================================

def _daily_pdh_pdl(df: pd.DataFrame) -> dict:
    """Return dict: {date_normalized -> (pdh, pdl)} dari previous day."""
    df = df.copy()
    df["date"] = df["time"].dt.normalize()
    daily = df.groupby("date").agg(dh=("high","max"), dl=("low","min")).reset_index()
    daily = daily.sort_values("date").reset_index(drop=True)
    out   = {}
    for i in range(1, len(daily)):
        d       = daily.iloc[i]["date"]
        prev    = daily.iloc[i-1]
        out[d]  = (float(prev["dh"]), float(prev["dl"]))
    return out


# ============================================================
# TECHNIQUE: LOM / NOM (configurable session)
# ============================================================

def run_session_momentum(
    df:          pd.DataFrame,
    h4_tl:       dict,
    h4_ct:       list,
    session_start: int,
    session_end:   int,
    tight_end:     int,
    rr_ratio:      float  = 2.0,
    h4_filter:     bool   = False,
    tight_window:  bool   = False,
    min_bar1_pips: float  = 5.0,
    name:          str    = "LOM",
) -> list:
    """
    Momentum trade dari open sebuah session.
    Bar1 = bar M30 pertama di jam session_start.
    Bar2 = bar M30 kedua (session_start+0:30).
    Entry: keduanya bullish -> BUY; keduanya bearish -> SELL.
    """
    trades   = []
    n        = len(df)
    df_dates = df["time"].dt.normalize()
    all_dates = df_dates.unique()

    for date in all_dates:
        day_mask = df_dates == date
        day_bars = df[day_mask]

        # Bar 1
        b1_rows  = day_bars[day_bars["time"].dt.hour == session_start]
        if len(b1_rows) == 0:
            continue
        b1      = b1_rows.iloc[0]
        b1_gi   = df[df["time"] == b1["time"]].index
        if len(b1_gi) == 0:
            continue
        b1_gi   = b1_gi[0]
        if b1_gi + 1 >= n:
            continue

        b2     = df.iloc[b1_gi + 1]
        b2_gi  = b1_gi + 1

        # tight window: bar2 harus masih dalam tight_end jam
        if tight_window and b2["time"].hour >= tight_end:
            continue

        # Filter min range bar1
        if (b1["high"] - b1["low"]) / PIP < min_bar1_pips:
            continue

        b1_bull = b1["close"] > b1["open"]
        b2_bull = b2["close"] > b2["open"]
        b1_bear = b1["close"] < b1["open"]
        b2_bear = b2["close"] < b2["open"]

        if b1_bull and b2_bull:
            sig = "BUY"
        elif b1_bear and b2_bear:
            sig = "SELL"
        else:
            continue

        # H4 CMP filter
        if h4_filter:
            h4c = h4_cmp_at(h4_tl, h4_ct, b2["time"])
            if h4c == "WAIT" or h4c != sig:
                continue

        entry = b2["close"]
        if sig == "BUY":
            sl = min(b1["low"], b2["low"]) - SL_BUFFER * PIP
            tp = entry + (entry - sl) * rr_ratio
        else:
            sl = max(b1["high"], b2["high"]) + SL_BUFFER * PIP
            tp = entry - (sl - entry) * rr_ratio

        if sl <= 0 or (sig == "BUY" and not tp > entry > sl):
            continue
        if sig == "SELL" and not tp < entry < sl:
            continue

        t   = Trade(sig, entry, sl, tp, name, b2["time"])
        res = simulate_trade(df, b2_gi, t)
        if res:
            res["sub_type"] = name
            trades.append(res)

    return trades


# ============================================================
# TECHNIQUE: PDH/PDL Breakout (PDB)
# ============================================================

def run_pdb(
    df:         pd.DataFrame,
    h4_tl:      dict,
    h4_ct:      list,
    pdh_pdl:    dict,
    rr_ratio:   float = 2.0,
    h4_filter:  bool  = False,
    min_pdr:    float = MIN_PDR,
) -> list:
    """
    PDH/PDL Breakout: trade THROUGH level (momentum continuation).
    Ketika close bar M30 melewati PDH -> BUY.
    Ketika close bar M30 melewati PDL -> SELL.
    SL = level - buffer (BUY) atau level + buffer (SELL).
    TP = fixed RR dari SL.
    Max 1 trade per hari. Hanya setelah London open.
    """
    trades   = []
    n        = len(df)
    df_dates = df["time"].dt.normalize()
    all_dates = df_dates.unique()

    for date in all_dates:
        pdh_pdl_val = pdh_pdl.get(date)
        if pdh_pdl_val is None:
            continue
        pdh, pdl = pdh_pdl_val
        if (pdh - pdl) / PIP < min_pdr:
            continue

        day_mask = df_dates == date
        day_bars = df[day_mask]
        london   = day_bars[day_bars["time"].dt.hour.between(LONDON_START, LONDON_END)]
        if len(london) == 0:
            continue

        traded = False
        for _, bar_row in london.iterrows():
            if traded:
                break
            cl  = bar_row["close"]
            gi  = df[df["time"] == bar_row["time"]].index
            if len(gi) == 0:
                continue
            gi  = gi[0]

            sig   = None
            level = 0.0
            if cl > pdh:
                sig = "BUY"; level = pdh
            elif cl < pdl:
                sig = "SELL"; level = pdl

            if sig is None:
                continue

            if h4_filter:
                h4c = h4_cmp_at(h4_tl, h4_ct, bar_row["time"])
                if h4c == "WAIT" or h4c != sig:
                    continue

            entry = cl
            if sig == "BUY":
                sl = level - PDB_SL_BUF * PIP
                tp = entry + (entry - sl) * rr_ratio
                if not (tp > entry > sl):
                    continue
            else:
                sl = level + PDB_SL_BUF * PIP
                tp = entry - (sl - entry) * rr_ratio
                if not (tp < entry < sl):
                    continue

            t   = Trade(sig, entry, sl, tp, "PDB", bar_row["time"])
            res = simulate_trade(df, gi, t)
            if res:
                res["sub_type"] = "PDB"
                trades.append(res)
            traded = True

    return trades


# ============================================================
# TECHNIQUE: ARB v2 (Asian Range Breakout + H4 filter)
# ============================================================

def run_arb_v2(
    df:         pd.DataFrame,
    h4_tl:      dict,
    h4_ct:      list,
    rr_ratio:   float = 0.0,   # 0 = 1.5x range natural
    h4_filter:  bool  = False,
    min_range:  float = ARB_MIN_RANGE,
    max_range:  float = ARB_MAX_RANGE,
) -> list:
    trades   = []
    n        = len(df)
    df_dates = df["time"].dt.normalize()
    all_dates = df_dates.unique()

    for date in all_dates:
        day_mask = df_dates == date
        day_bars = df[day_mask]

        asian  = day_bars[day_bars["time"].dt.hour.between(ASIAN_START, ASIAN_END)]
        if len(asian) < 3:
            continue
        ah = asian["high"].max()
        al = asian["low"].min()
        rng_pips = (ah - al) / PIP
        if rng_pips < min_range or rng_pips > max_range:
            continue

        london = day_bars[day_bars["time"].dt.hour.between(LONDON_START, LONDON_END)]
        if len(london) == 0:
            continue

        for _, bar_row in london.iterrows():
            cl = bar_row["close"]
            gi = df[df["time"] == bar_row["time"]].index
            if len(gi) == 0:
                continue
            gi = gi[0]

            sig = None
            if cl > ah:
                sig = "BUY"
            elif cl < al:
                sig = "SELL"

            if sig is None:
                continue

            if h4_filter:
                h4c = h4_cmp_at(h4_tl, h4_ct, bar_row["time"])
                if h4c == "WAIT" or h4c != sig:
                    continue

            entry = cl
            if sig == "BUY":
                sl = al - SL_BUFFER * PIP
                tp = entry + (rng_pips * 1.5 * PIP) if rr_ratio == 0 else entry + (entry - sl) * rr_ratio
                if not (tp > entry > sl):
                    continue
            else:
                sl = ah + SL_BUFFER * PIP
                tp = entry - (rng_pips * 1.5 * PIP) if rr_ratio == 0 else entry - (sl - entry) * rr_ratio
                if not (tp < entry < sl):
                    continue

            t   = Trade(sig, entry, sl, tp, "ARB2", bar_row["time"])
            res = simulate_trade(df, gi, t)
            if res:
                res["sub_type"] = "ARB2"
                trades.append(res)
            break  # 1 trade per hari

    return trades


# ============================================================
# TECHNIQUE: LOM + PDH/PDL Proximity Filter (LOM_PDF)
# Jangan trade jika TP terhalang PDH/PDL dalam jarak X pips
# ============================================================

def run_lom_pdf(
    df:          pd.DataFrame,
    h4_tl:       dict,
    h4_ct:       list,
    pdh_pdl:     dict,
    rr_ratio:    float = 2.0,
    h4_filter:   bool  = True,
    tight_window: bool  = True,
    min_bar1:    float = 5.0,
    block_pips:  float = 15.0,  # skip jika PDH/PDL menghalangi TP dalam X pips
) -> list:
    """LOM terbaik + filter: skip jika PDH/PDL memblokir TP."""
    trades   = []
    n        = len(df)
    df_dates = df["time"].dt.normalize()
    all_dates = df_dates.unique()

    for date in all_dates:
        day_mask = df_dates == date
        day_bars = df[day_mask]

        b1_rows  = day_bars[day_bars["time"].dt.hour == LONDON_START]
        if len(b1_rows) == 0:
            continue
        b1      = b1_rows.iloc[0]
        b1_gi   = df[df["time"] == b1["time"]].index
        if len(b1_gi) == 0:
            continue
        b1_gi   = b1_gi[0]
        if b1_gi + 1 >= n:
            continue

        b2    = df.iloc[b1_gi + 1]
        b2_gi = b1_gi + 1

        if tight_window and b2["time"].hour >= LONDON_TIGHT_END:
            continue
        if (b1["high"] - b1["low"]) / PIP < min_bar1:
            continue

        b1_bull = b1["close"] > b1["open"]
        b2_bull = b2["close"] > b2["open"]
        b1_bear = b1["close"] < b1["open"]
        b2_bear = b2["close"] < b2["open"]

        if b1_bull and b2_bull:
            sig = "BUY"
        elif b1_bear and b2_bear:
            sig = "SELL"
        else:
            continue

        if h4_filter:
            h4c = h4_cmp_at(h4_tl, h4_ct, b2["time"])
            if h4c == "WAIT" or h4c != sig:
                continue

        entry = b2["close"]
        if sig == "BUY":
            sl = min(b1["low"], b2["low"]) - SL_BUFFER * PIP
            tp = entry + (entry - sl) * rr_ratio
        else:
            sl = max(b1["high"], b2["high"]) + SL_BUFFER * PIP
            tp = entry - (sl - entry) * rr_ratio

        # PDH/PDL proximity block
        pdv = pdh_pdl.get(date)
        if pdv:
            pdh, pdl = pdv
            if sig == "BUY" and pdh > entry:
                # PDH antara entry dan TP
                if (pdh - entry) / PIP < block_pips:
                    continue  # PDH menghalangi terlalu dekat
            if sig == "SELL" and pdl < entry:
                if (entry - pdl) / PIP < block_pips:
                    continue

        if sl <= 0:
            continue
        if sig == "BUY"  and not (tp > entry > sl):
            continue
        if sig == "SELL" and not (tp < entry < sl):
            continue

        t   = Trade(sig, entry, sl, tp, "LOM_PDF", b2["time"])
        res = simulate_trade(df, b2_gi, t)
        if res:
            res["sub_type"] = "LOM_PDF"
            trades.append(res)

    return trades


# ============================================================
# STATS
# ============================================================

def _stats(trades: list) -> dict:
    if not trades:
        return {"n": 0, "wr": 0, "pf": 0, "pips": 0, "avg_w": 0, "avg_l": 0, "freq": 0}
    wins   = [t for t in trades if t["pips"] > 0]
    losses = [t for t in trades if t["pips"] <= 0]
    pips   = sum(t["pips"] for t in trades)
    wr     = len(wins) / len(trades) * 100
    avg_w  = sum(t["pips"] for t in wins)  / len(wins)   if wins   else 0
    avg_l  = sum(t["pips"] for t in losses)/ len(losses) if losses else 0
    pf     = abs(avg_w / avg_l) if avg_l else float("inf")
    return {"n": len(trades), "wr": wr, "pf": pf, "pips": pips,
            "avg_w": avg_w, "avg_l": avg_l}


# ============================================================
# REPORTS
# ============================================================

def _print_ranking(results: dict, total_days: int, min_trades: int = 50):
    MG = "bright_green"; RD = "bright_red"; GD = "gold1"; DG = "grey62"; CC = "bright_cyan"

    console.print()
    console.rule("[bold bright_cyan]RANKING -- ALL VARIANTS[/]")

    scored = []
    for name, trades in results.items():
        s = _stats(trades)
        if s["n"] < min_trades:
            continue
        s["name"] = name
        s["freq"] = s["n"] / total_days
        scored.append(s)

    # Sort by PF, then by total pips
    scored.sort(key=lambda x: (x["pf"], x["pips"]), reverse=True)

    tbl = Table(box=rich_box.DOUBLE_EDGE, header_style="bold bright_cyan",
                expand=False, padding=(0, 1))
    tbl.add_column("RANK",      width=5,  justify="right")
    tbl.add_column("TECHNIQUE", width=20, style="bold")
    tbl.add_column("TRADES",    width=7,  justify="right")
    tbl.add_column("FREQ/D",    width=7,  justify="right")
    tbl.add_column("WIN%",      width=7,  justify="right")
    tbl.add_column("PF",        width=6,  justify="right")
    tbl.add_column("TOTAL P",   width=10, justify="right")
    tbl.add_column("AVG WIN",   width=8,  justify="right")
    tbl.add_column("AVG LOSS",  width=9,  justify="right")
    tbl.add_column("VERDICT",   width=14, justify="center")

    for rank, s in enumerate(scored, 1):
        wr_col  = MG if s["wr"] >= 50 else GD if s["wr"] >= 40 else RD
        pf_col  = MG if s["pf"] >= 1.8 else GD if s["pf"] >= 1.3 else RD
        pnl_col = MG if s["pips"] >= 0 else RD

        if s["pf"] >= 1.8 and s["wr"] >= 38:
            verdict = f"[bold {MG}]STRONG EDGE[/]"
        elif s["pf"] >= 1.5 and s["wr"] >= 35:
            verdict = f"[bold {GD}]GOOD EDGE[/]"
        elif s["pf"] >= 1.2:
            verdict = f"[{GD}]MODERATE[/]"
        else:
            verdict = f"[{RD}]WEAK[/]"

        tbl.add_row(
            f"[{GD}]{rank}[/]",
            f"[{CC}]{s['name']}[/]",
            str(s["n"]),
            f"{s['freq']:.2f}",
            f"[{wr_col}]{s['wr']:.1f}%[/]",
            f"[{pf_col}]{s['pf']:.2f}[/]",
            f"[{pnl_col}]{s['pips']:+.0f}p[/]",
            f"[{MG}]{s['avg_w']:+.1f}[/]",
            f"[{RD}]{s['avg_l']:+.1f}[/]",
            verdict,
        )

    console.print(tbl)
    return scored


def _monthly_heatmap(trades: list, name: str):
    if not trades:
        return
    MG = "bright_green"; RD = "bright_red"; DG = "grey62"

    console.print(f"\n[bold bright_cyan]MONTHLY P&L -- {name}[/]")

    monthly: dict = {}
    for t in trades:
        key = t["open_time"].strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0.0) + t["pips"]

    years = sorted(set(k[:4] for k in monthly))
    tbl   = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
    tbl.add_column("YR",   style=DG, width=5)
    for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]:
        tbl.add_column(m, justify="right", width=6)
    tbl.add_column("TOT", justify="right", width=8)

    for yr in years:
        row = [yr]; tot = 0.0
        for mo in range(1, 13):
            key = f"{yr}-{mo:02d}"
            v   = monthly.get(key)
            if v is None:
                row.append(f"[{DG}]--[/]")
            else:
                col = MG if v > 0 else RD
                row.append(f"[{col}]{v:+.0f}[/]")
                tot += v
        col = MG if tot > 0 else RD
        row.append(f"[bold {col}]{tot:+.0f}[/]")
        tbl.add_row(*row)

    console.print(tbl)


def _green_months_pct(trades: list) -> float:
    """Persen bulan yang profitable -- proxy konsistensi."""
    if not trades:
        return 0.0
    monthly: dict = {}
    for t in trades:
        key = t["open_time"].strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0.0) + t["pips"]
    if not monthly:
        return 0.0
    green = sum(1 for v in monthly.values() if v > 0)
    return green / len(monthly) * 100


def _print_deep_report(name: str, trades: list, total_days: int):
    if not trades:
        return
    s    = _stats(trades)
    gm   = _green_months_pct(trades)
    wins = [t for t in trades if t["pips"] > 0]
    loss = [t for t in trades if t["pips"] <= 0]

    MG = "bright_green"; RD = "bright_red"; GD = "gold1"; DG = "grey62"; CC = "bright_cyan"

    # Exit breakdown
    exit_br = {}
    for t in trades:
        exit_br[t["reason"]] = exit_br.get(t["reason"], 0) + 1

    exit_str = "  ".join(f"{k}:{v}" for k, v in sorted(exit_br.items()))
    freq = s["n"] / total_days

    rows = [
        ("Trades",         f"[white]{s['n']}[/]",
         "Freq/Day",       f"[white]{freq:.2f}[/]"),
        ("Win Rate",       f"[{'bright_green' if s['wr']>=45 else 'gold1' if s['wr']>=35 else 'bright_red'}]{s['wr']:.1f}%[/]",
         "Profit Factor",  f"[{'bright_green' if s['pf']>=1.8 else 'gold1' if s['pf']>=1.2 else 'bright_red'}]{s['pf']:.2f}[/]"),
        ("Total Pips",     f"[{'bright_green' if s['pips']>=0 else 'bright_red'}]{s['pips']:+.1f}[/]",
         "Green Months",   f"[{'bright_green' if gm>=60 else 'gold1' if gm>=50 else 'bright_red'}]{gm:.0f}%[/]"),
        ("Avg Win",        f"[{MG}]{s['avg_w']:+.1f}p[/]",
         "Avg Loss",       f"[{RD}]{s['avg_l']:+.1f}p[/]"),
        ("Wins / Losses",  f"[{MG}]{len(wins)}[/] / [{RD}]{len(loss)}[/]",
         "Exits",          f"[grey62]{exit_str}[/]"),
    ]

    t_row = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0,2), expand=False)
    t_row.add_column("METRIC", style=DG, width=16)
    t_row.add_column("VALUE",  justify="right", width=14)
    t_row.add_column("METRIC", style=DG, width=16)
    t_row.add_column("VALUE",  justify="right", width=18)
    for r in rows:
        t_row.add_row(*r)

    console.print(Panel(t_row, title=f"[bold {CC}]{name}[/]",
                        border_style="cyan", padding=(0,1)))


# ============================================================
# MAIN
# ============================================================

def run_all(
    start:       str   = "2020-01-01",
    end:         str   = "2026-05-20",
    min_trades:  int   = 80,
    show_top_n:  int   = 5,
):
    console.print(Panel(
        "[bold bright_cyan]SCALP BACKTEST v2 -- Deep Optimization[/]\n"
        "[grey62]XAU/USD M30 + H4 | LOM variants | NOM | PDB | ARB v2 | LOM+PDF[/]",
        border_style="cyan", padding=(0, 2)
    ))

    # ── Load data ─────────────────────────────────────────────────────────────
    console.print("\n[cyan]Loading data...[/]")
    df = load_m30(start, end)
    if len(df) == 0:
        return

    h4_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DATACSV", "XAUUSDH4.csv")
    h4_df   = pd.read_csv(
        h4_path, header=None, encoding="utf-16", sep=",",
        names=["time","open","high","low","close","tick_volume","spread"]
    )
    h4_df["time"] = pd.to_datetime(h4_df["time"], format="%Y.%m.%d %H:%M")
    h4_df = h4_df.drop(columns=["spread"]).sort_values("time").reset_index(drop=True)
    # Ambil buffer 1 tahun sebelum start untuk warm-up H4 CMP
    h4_df = h4_df[h4_df["time"] <= pd.Timestamp(end)].reset_index(drop=True)
    console.print(f"  [green]H4[/] -- {len(h4_df):,} bars")

    h4_tl, h4_ct = build_h4_timeline(h4_df)

    df["hour"]   = df["time"].dt.hour
    total_days   = len(df["time"].dt.normalize().unique())
    pdh_pdl      = _daily_pdh_pdl(df)

    console.print(f"  [grey62]Period: {start} -> {end} | Days: {total_days}[/]\n")

    results = {}

    # ── LOM variants ──────────────────────────────────────────────────────────
    console.print("[cyan]Running LOM variants...[/]")

    rr_list = [1.5, 2.0, 2.5]
    for rr in rr_list:
        for h4f in [False, True]:
            for tw in [False, True]:
                tag = f"LOM_RR{rr}{'_H4' if h4f else ''}{'_TW' if tw else ''}"
                r   = run_session_momentum(
                    df, h4_tl, h4_ct,
                    LONDON_START, LONDON_END, LONDON_TIGHT_END,
                    rr_ratio=rr, h4_filter=h4f, tight_window=tw,
                    name=tag
                )
                results[tag] = r
                s = _stats(r)
                console.print(f"  {tag:28s} n={s['n']:4d}  WR={s['wr']:5.1f}%  PF={s['pf']:.2f}  pips={s['pips']:+.0f}")

    # ── NOM variants (NY Open) ─────────────────────────────────────────────────
    console.print("\n[cyan]Running NOM (NY Open) variants...[/]")

    for rr in rr_list:
        for h4f in [False, True]:
            tag = f"NOM_RR{rr}{'_H4' if h4f else ''}"
            r   = run_session_momentum(
                df, h4_tl, h4_ct,
                NY_START, NY_END, NY_START + 1,
                rr_ratio=rr, h4_filter=h4f, tight_window=False,
                name=tag
            )
            results[tag] = r
            s = _stats(r)
            console.print(f"  {tag:28s} n={s['n']:4d}  WR={s['wr']:5.1f}%  PF={s['pf']:.2f}  pips={s['pips']:+.0f}")

    # ── PDB variants ──────────────────────────────────────────────────────────
    console.print("\n[cyan]Running PDB (PDH/PDL Breakout) variants...[/]")

    for rr in rr_list:
        for h4f in [False, True]:
            tag = f"PDB_RR{rr}{'_H4' if h4f else ''}"
            r   = run_pdb(df, h4_tl, h4_ct, pdh_pdl, rr_ratio=rr, h4_filter=h4f)
            results[tag] = r
            s = _stats(r)
            console.print(f"  {tag:28s} n={s['n']:4d}  WR={s['wr']:5.1f}%  PF={s['pf']:.2f}  pips={s['pips']:+.0f}")

    # ── ARB v2 ────────────────────────────────────────────────────────────────
    console.print("\n[cyan]Running ARB v2 variants...[/]")

    for h4f in [False, True]:
        for rng in [(5,30), (8,25), (5,20)]:
            tag = f"ARB2{'_H4' if h4f else ''}_R{rng[0]}-{rng[1]}"
            r   = run_arb_v2(df, h4_tl, h4_ct, h4_filter=h4f,
                             min_range=rng[0], max_range=rng[1])
            results[tag] = r
            s = _stats(r)
            console.print(f"  {tag:28s} n={s['n']:4d}  WR={s['wr']:5.1f}%  PF={s['pf']:.2f}  pips={s['pips']:+.0f}")

    # ── LOM + PDF (PDH/PDL proximity filter) ──────────────────────────────────
    console.print("\n[cyan]Running LOM + PDF (PDH/PDL proximity block) variants...[/]")

    for rr in rr_list:
        for block in [10.0, 15.0, 20.0]:
            tag = f"LOM_PDF_RR{rr}_B{int(block)}"
            r   = run_lom_pdf(
                df, h4_tl, h4_ct, pdh_pdl,
                rr_ratio=rr, h4_filter=True, tight_window=True,
                block_pips=block
            )
            results[tag] = r
            s = _stats(r)
            console.print(f"  {tag:28s} n={s['n']:4d}  WR={s['wr']:5.1f}%  PF={s['pf']:.2f}  pips={s['pips']:+.0f}")

    # ── Ranking ───────────────────────────────────────────────────────────────
    scored = _print_ranking(results, total_days, min_trades=min_trades)

    # ── Deep report + monthly heatmap top N ───────────────────────────────────
    console.print()
    console.rule(f"[bold bright_cyan]DEEP REPORT -- TOP {show_top_n}[/]")

    for s in scored[:show_top_n]:
        name   = s["name"]
        trades = results[name]
        _print_deep_report(name, trades, total_days)
        _monthly_heatmap(trades, name)

    # ── Final recommendation ───────────────────────────────────────────────────
    if scored:
        best = scored[0]
        gm   = _green_months_pct(results[best["name"]])
        console.print()
        console.print(Panel(
            f"[bold bright_green]BEST TECHNIQUE: {best['name']}[/]\n\n"
            f"  Trades       : {best['n']}\n"
            f"  Win Rate     : {best['wr']:.1f}%\n"
            f"  Profit Factor: {best['pf']:.2f}\n"
            f"  Total Pips   : {best['pips']:+.0f}\n"
            f"  Green Months : {gm:.0f}%\n"
            f"  Freq/Day     : {best['freq']:.2f}\n\n"
            f"[grey62]Recommendation: Gunakan {best['name']} sebagai layer tambahan\n"
            f"di atas sistem CMP/VR/CF lo. Entry konfirmasi dua arah\n"
            f"(session momentum + CMP direction) = probability tertinggi.[/]",
            title="[bold bright_yellow]KESIMPULAN[/]",
            border_style="bright_yellow", padding=(0, 2)
        ))

    console.print("\n[grey62]Done.[/]")
    return results, scored


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ═══════════ CONFIG ═══════════
    START      = "2020-01-01"
    END        = "2026-05-20"
    MIN_TRADES = 80    # minimum trades untuk masuk ranking
    SHOW_TOP   = 5     # deep report untuk top N
    # ══════════════════════════════
    run_all(start=START, end=END, min_trades=MIN_TRADES, show_top_n=SHOW_TOP)
