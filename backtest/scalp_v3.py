"""
SCALP BACKTEST v3 -- Deep Dive: PDB + NOM + Combined System
Data: M30 + H4 CSV. Tidak butuh MT5.

Temuan dari v2:
  - PDB_RR2.0_H4 : n=587, WR=45.5%, +5566 pips (6 tahun) -- WINNER
  - NOM_RR2.0_H4 : n=378, WR=38.9%, +2135 pips
  - LOM_RR2.0    : n=824, WR=35.1%, +841 pips

v3 pipeline:
  1. PDB deep dive:
     - Breakdown BUY vs SELL
     - Breakdown London vs NY session
     - Retest entry variant (tunggu pullback ke level setelah break)
     - RR sweep 1.5 / 2.0 / 2.5 / 3.0
     - SL buffer variations
     - H4 trend strength filter (cmp berapa lama sudah tren)
  2. NOM deep dive:
     - Breakdown BUY vs SELL
     - Time filter: only if Asian range > X pips (ada momentum pre-London)
     - RR sweep
  3. Combined Portfolio: PDB + NOM_H4 sebagai satu sistem
     - Backtest keduanya dijalankan serentak, satu kapital
     - Monthly heatmap combined
     - Max drawdown per bulan
  4. Ranking berbasis composite score: PF * pips_per_year
  5. Final recommendation
"""

import sys, os, bisect
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box as rich_box

from engine.core import TFState
from backtest.backtest import Trade, PIP
from backtest.scalp_backtest import load_m30, simulate_trade
from backtest.scalp_v2 import (
    build_h4_timeline, h4_cmp_at, _daily_pdh_pdl,
    LONDON_START, LONDON_END, NY_START, NY_END,
    ASIAN_START, ASIAN_END, SL_BUFFER, MAX_HOLD_BARS,
    MIN_PDR, _monthly_heatmap, _stats
)

console = Console()
PIP = 0.1

# ============================================================
# CONSTANTS
# ============================================================
PDB_SL_VARIANTS  = [3.0, 5.0, 8.0]   # buffer pips di luar PDH/PDL
PDB_RR_VARIANTS  = [1.5, 2.0, 2.5, 3.0]
NOM_RR_VARIANTS  = [1.5, 2.0, 2.5]
MIN_BAR1_PIPS    = 5.0
RETEST_PIPS      = 8.0   # pullback dalam X pips dari level untuk retest entry
RETEST_MAX_BARS  = 6     # max bars to wait for retest after breakout


# ============================================================
# PDB VARIANTS
# ============================================================

def run_pdb_full(
    df:            pd.DataFrame,
    h4_tl:         dict,
    h4_ct:         list,
    pdh_pdl:       dict,
    rr_ratio:      float = 2.0,
    sl_buf:        float = 5.0,
    h4_filter:     bool  = True,
    session_filter: str  = "ALL",   # "ALL" | "LONDON" | "NY" | "ASIAN"
    direction_filter: str = "ALL",  # "ALL" | "BUY" | "SELL"
    retest:        bool  = False,   # tunggu pullback ke level setelah break
    min_pdr:       float = MIN_PDR,
    max_trades_day: int  = 2,       # max PDB trade per hari
) -> list:
    """
    PDH/PDL Breakout -- full configurable.
    Break = M30 bar close melampaui PDH (BUY) atau PDL (SELL).
    Retest mode: setelah break, tunggu bar berikutnya yang pullback ke level.
    """
    trades   = []
    n        = len(df)
    df_dates = df["time"].dt.normalize()
    all_dates = df_dates.unique()

    # Session hour filters
    if session_filter == "LONDON":
        valid_hours = set(range(LONDON_START, LONDON_END + 1))
    elif session_filter == "NY":
        valid_hours = set(range(NY_START, NY_END + 1))
    elif session_filter == "ASIAN":
        valid_hours = set(range(ASIAN_START, ASIAN_END + 1))
    else:
        valid_hours = None  # semua jam valid

    for date in all_dates:
        pdv = pdh_pdl.get(date)
        if pdv is None:
            continue
        pdh, pdl = pdv
        if (pdh - pdl) / PIP < min_pdr:
            continue

        day_mask = df_dates == date
        day_bars = df[day_mask]
        if valid_hours:
            day_bars = day_bars[day_bars["time"].dt.hour.isin(valid_hours)]
        if len(day_bars) == 0:
            continue

        day_trades = 0

        if not retest:
            # -- Immediate entry on break bar close --------------------------------
            for _, bar_row in day_bars.iterrows():
                if day_trades >= max_trades_day:
                    break
                cl = bar_row["close"]
                gi = df[df["time"] == bar_row["time"]].index
                if len(gi) == 0:
                    continue
                gi = gi[0]

                sig = level = None
                if cl > pdh:
                    sig = "BUY"; level = pdh
                elif cl < pdl:
                    sig = "SELL"; level = pdl

                if sig is None:
                    continue
                if direction_filter != "ALL" and sig != direction_filter:
                    continue
                if h4_filter:
                    h4c = h4_cmp_at(h4_tl, h4_ct, bar_row["time"])
                    if h4c == "WAIT" or h4c != sig:
                        continue

                entry = cl
                if sig == "BUY":
                    sl = level - sl_buf * PIP
                    tp = entry + (entry - sl) * rr_ratio
                    if not (tp > entry > sl > 0):
                        continue
                else:
                    sl = level + sl_buf * PIP
                    tp = entry - (sl - entry) * rr_ratio
                    if not (tp < entry < sl):
                        continue

                t   = Trade(sig, entry, sl, tp, "PDB", bar_row["time"])
                res = simulate_trade(df, gi, t)
                if res:
                    res["sub_type"] = "PDB"
                    res["session"]  = _session_tag(bar_row["time"].hour)
                    trades.append(res)
                    day_trades += 1

        else:
            # -- Retest entry: break detected, then wait for pullback ------------
            pending_break: dict | None = None   # {sig, level, break_gi, break_time}

            all_day = df[day_mask].reset_index(drop=True)
            for idx_row, bar_row in all_day.iterrows():
                if day_trades >= max_trades_day:
                    break
                cl  = bar_row["close"]
                hi  = bar_row["high"]
                lo  = bar_row["low"]
                hour = bar_row["time"].hour
                gi   = df[df["time"] == bar_row["time"]].index
                if len(gi) == 0:
                    continue
                gi = gi[0]

                # Check if pending break is too old
                if pending_break and (gi - pending_break["break_gi"]) > RETEST_MAX_BARS:
                    pending_break = None

                # Retest entry check
                if pending_break:
                    sig   = pending_break["sig"]
                    level = pending_break["level"]
                    b_gi  = pending_break["break_gi"]
                    if valid_hours and hour not in valid_hours:
                        pass
                    elif sig == "BUY":
                        # BUY retest: price comes back near PDH from above
                        if lo <= level + RETEST_PIPS * PIP and cl >= level:
                            entry = cl
                            sl    = level - sl_buf * PIP
                            tp    = entry + (entry - sl) * rr_ratio
                            if tp > entry > sl > 0:
                                t   = Trade("BUY", entry, sl, tp, "PDB_RT", bar_row["time"])
                                res = simulate_trade(df, gi, t)
                                if res:
                                    res["sub_type"] = "PDB_RT"
                                    res["session"]  = _session_tag(hour)
                                    trades.append(res)
                                    day_trades += 1
                                pending_break = None
                    else:
                        # SELL retest: price comes back near PDL from below
                        if hi >= level - RETEST_PIPS * PIP and cl <= level:
                            entry = cl
                            sl    = level + sl_buf * PIP
                            tp    = entry - (sl - entry) * rr_ratio
                            if tp < entry < sl:
                                t   = Trade("SELL", entry, sl, tp, "PDB_RT", bar_row["time"])
                                res = simulate_trade(df, gi, t)
                                if res:
                                    res["sub_type"] = "PDB_RT"
                                    res["session"]  = _session_tag(hour)
                                    trades.append(res)
                                    day_trades += 1
                                pending_break = None

                # Detect new break (no pending or after retest done)
                if pending_break is None:
                    sig = level = None
                    if cl > pdh:
                        sig = "BUY"; level = pdh
                    elif cl < pdl:
                        sig = "SELL"; level = pdl

                    if sig and not (direction_filter != "ALL" and sig != direction_filter):
                        if not h4_filter or h4_cmp_at(h4_tl, h4_ct, bar_row["time"]) == sig:
                            pending_break = {
                                "sig": sig, "level": level,
                                "break_gi": gi, "break_time": bar_row["time"]
                            }

    return trades


def _session_tag(hour: int) -> str:
    if LONDON_START <= hour <= LONDON_END:
        return "LONDON"
    if NY_START <= hour <= NY_END:
        return "NY"
    if ASIAN_START <= hour <= ASIAN_END:
        return "ASIAN"
    return "OTHER"


# ============================================================
# NOM DEEP DIVE
# ============================================================

def run_nom_deep(
    df:           pd.DataFrame,
    h4_tl:        dict,
    h4_ct:        list,
    rr_ratio:     float = 2.0,
    h4_filter:    bool  = True,
    min_bar1:     float = MIN_BAR1_PIPS,
    asian_min_range: float = 0.0,  # tambahan filter: asian range min sebelum NY open
    direction_filter: str = "ALL",
) -> list:
    """
    NY Open Momentum dengan breakdown tambahan.
    """
    trades   = []
    n        = len(df)
    df_dates = df["time"].dt.normalize()
    all_dates = df_dates.unique()

    for date in all_dates:
        day_mask = df_dates == date
        day_bars = df[day_mask]

        # Optional: asian range filter
        if asian_min_range > 0:
            asian = day_bars[day_bars["time"].dt.hour.between(ASIAN_START, ASIAN_END)]
            if len(asian) < 3:
                continue
            a_rng = (asian["high"].max() - asian["low"].min()) / PIP
            if a_rng < asian_min_range:
                continue

        # Bar 1 at NY_START
        b1_rows = day_bars[day_bars["time"].dt.hour == NY_START]
        if len(b1_rows) == 0:
            continue
        b1    = b1_rows.iloc[0]
        b1_gi = df[df["time"] == b1["time"]].index
        if len(b1_gi) == 0:
            continue
        b1_gi = b1_gi[0]
        if b1_gi + 1 >= n:
            continue

        b2    = df.iloc[b1_gi + 1]
        b2_gi = b1_gi + 1

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

        if direction_filter != "ALL" and sig != direction_filter:
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

        if sl <= 0:
            continue
        if sig == "BUY" and not (tp > entry > sl):
            continue
        if sig == "SELL" and not (tp < entry < sl):
            continue

        t   = Trade(sig, entry, sl, tp, "NOM", b2["time"])
        res = simulate_trade(df, b2_gi, t)
        if res:
            res["sub_type"] = "NOM"
            trades.append(res)

    return trades


# ============================================================
# COMBINED PORTFOLIO SIMULATOR
# ============================================================

def simulate_portfolio(
    trade_lists: list[list],   # list of trade result lists
    initial_balance: float = 10_000.0,
    risk_pct: float = 1.0,    # % balance per trade
) -> dict:
    """
    Gabungkan semua trade dari berbagai teknik, sort by open_time,
    simulasikan sebagai satu portfolio.
    Hitung equity curve, monthly, max drawdown, Sharpe proxy.
    """
    all_trades = []
    for tl in trade_lists:
        all_trades.extend(tl)
    all_trades.sort(key=lambda t: t["open_time"])

    balance      = initial_balance
    equity_curve = [initial_balance]
    monthly: dict = {}
    peak = initial_balance
    max_dd_pct = 0.0

    for t in all_trades:
        balance += t["pips"] * 1.0  # 1 pip = $1 per 0.01 lot
        equity_curve.append(balance)
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak * 100 if peak > 0 else 0
        if dd > max_dd_pct:
            max_dd_pct = dd

        key = t["open_time"].strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0.0) + t["pips"]

    green_m = sum(1 for v in monthly.values() if v > 0)
    total_m = len(monthly)
    years   = (all_trades[-1]["open_time"] - all_trades[0]["open_time"]).days / 365.25 \
              if all_trades else 1

    wins  = [t for t in all_trades if t["pips"] > 0]
    loss  = [t for t in all_trades if t["pips"] <= 0]
    total = sum(t["pips"] for t in all_trades)
    wr    = len(wins) / len(all_trades) * 100 if all_trades else 0
    avg_w = sum(t["pips"] for t in wins)  / len(wins)   if wins  else 0
    avg_l = sum(t["pips"] for t in loss)  / len(loss)   if loss  else 0
    pf    = abs(avg_w / avg_l) if avg_l else 0

    # Monthly returns array for Sharpe proxy
    m_vals = list(monthly.values())
    m_avg  = sum(m_vals) / len(m_vals) if m_vals else 0
    m_std  = (sum((v - m_avg) ** 2 for v in m_vals) / len(m_vals)) ** 0.5 if m_vals else 1
    sharpe = (m_avg / m_std * (12 ** 0.5)) if m_std > 0 else 0  # annualized proxy

    return {
        "n":           len(all_trades),
        "wr":          wr,
        "pf":          pf,
        "total_pips":  total,
        "per_year":    total / years if years > 0 else 0,
        "per_month":   m_avg,
        "avg_w":       avg_w,
        "avg_l":       avg_l,
        "green_m":     green_m,
        "total_m":     total_m,
        "green_pct":   green_m / total_m * 100 if total_m else 0,
        "max_dd_pct":  max_dd_pct,
        "sharpe":      sharpe,
        "equity":      equity_curve,
        "monthly":     monthly,
        "all_trades":  all_trades,
    }


# ============================================================
# REPORTS
# ============================================================

def _print_portfolio_report(port: dict, name: str):
    MG = "bright_green"; RD = "bright_red"; GD = "gold1"; DG = "grey62"; CC = "bright_cyan"

    gm_col  = MG if port["green_pct"] >= 65 else GD if port["green_pct"] >= 55 else RD
    pf_col  = MG if port["pf"] >= 1.5 else GD if port["pf"] >= 1.2 else RD
    wr_col  = MG if port["wr"] >= 42 else GD if port["wr"] >= 35 else RD
    dd_col  = MG if port["max_dd_pct"] < 10 else GD if port["max_dd_pct"] < 20 else RD
    sh_col  = MG if port["sharpe"] >= 0.8 else GD if port["sharpe"] >= 0.5 else RD

    rows = [
        ("Trades",       f"[white]{port['n']}[/]",
         "Green Months", f"[{gm_col}]{port['green_pct']:.0f}% ({port['green_m']}/{port['total_m']})[/]"),
        ("Win Rate",     f"[{wr_col}]{port['wr']:.1f}%[/]",
         "Profit Factor",f"[{pf_col}]{port['pf']:.2f}[/]"),
        ("Total Pips",   f"[{MG if port['total_pips']>0 else RD}]{port['total_pips']:+.0f}[/]",
         "Per Year",     f"[{MG if port['per_year']>0 else RD}]{port['per_year']:+.0f}p[/]"),
        ("Per Month avg",f"[{MG if port['per_month']>0 else RD}]{port['per_month']:+.1f}p[/]",
         "Sharpe proxy", f"[{sh_col}]{port['sharpe']:.2f}[/]"),
        ("Avg Win",      f"[{MG}]{port['avg_w']:+.1f}p[/]",
         "Avg Loss",     f"[{RD}]{port['avg_l']:+.1f}p[/]"),
        ("Max Drawdown", f"[{dd_col}]{port['max_dd_pct']:.1f}%[/]",
         "",             ""),
    ]

    t_row = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0,2), expand=False)
    t_row.add_column("METRIC", style=DG, width=16)
    t_row.add_column("VALUE",  justify="right", width=22)
    t_row.add_column("METRIC", style=DG, width=16)
    t_row.add_column("VALUE",  justify="right", width=22)
    for r in rows:
        t_row.add_row(*r)

    console.print(Panel(t_row, title=f"[bold {CC}]{name}[/]",
                        border_style="bright_yellow", padding=(0,1)))


def _print_monthly_portfolio(monthly: dict, name: str):
    MG = "bright_green"; RD = "bright_red"; DG = "grey62"
    console.print(f"\n[bold bright_cyan]MONTHLY P&L -- {name}[/]")

    years = sorted(set(k[:4] for k in monthly))
    tbl   = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
    tbl.add_column("YR", style=DG, width=5)
    for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]:
        tbl.add_column(m, justify="right", width=6)
    tbl.add_column("TOT", justify="right", width=8)

    grand_total = 0.0
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
        grand_total += tot

    console.print(tbl)
    col = MG if grand_total > 0 else RD
    console.print(f"  [grey62]Grand Total: [{col}]{grand_total:+.0f}p[/][/]")


def _print_direction_breakdown(trades: list, name: str):
    MG = "bright_green"; RD = "bright_red"; DG = "grey62"; CC = "bright_cyan"
    console.print(f"\n[bold {CC}]{name} -- DIRECTION & SESSION BREAKDOWN[/]")

    # By direction
    for tag, fn in [("BUY", lambda t: t["direction"]=="BUY"),
                    ("SELL",lambda t: t["direction"]=="SELL")]:
        subset = [t for t in trades if fn(t)]
        if not subset:
            continue
        s = _stats(subset)
        col = MG if s["pips"] > 0 else RD
        console.print(
            f"  [{tag=='BUY' and MG or RD}]{tag:5s}[/]  "
            f"n={s['n']:4d}  WR={s['wr']:5.1f}%  PF={s['pf']:.2f}  "
            f"[{col}]{s['pips']:+.0f}p[/]"
        )

    # By session (if available)
    sessions = set(t.get("session", "N/A") for t in trades)
    if sessions - {"N/A"}:
        console.print()
        for sess in sorted(sessions):
            subset = [t for t in trades if t.get("session") == sess]
            s = _stats(subset)
            col = MG if s["pips"] > 0 else RD
            console.print(
                f"  {sess:7s}  n={s['n']:4d}  WR={s['wr']:5.1f}%  PF={s['pf']:.2f}  "
                f"[{col}]{s['pips']:+.0f}p[/]"
            )


def _equity_ascii(equity: list, width: int = 60, height: int = 8):
    MG = "bright_green"; DG = "grey62"
    console.print(f"\n[bold bright_cyan]EQUITY CURVE -- COMBINED PORTFOLIO[/]")
    mn, mx = min(equity), max(equity)
    rng = mx - mn if mx != mn else 1.0
    step = max(1, len(equity) // width)
    sampled = [equity[i] for i in range(0, len(equity), step)][:width]

    for row in range(height - 1, -1, -1):
        lo = mn + rng * row / height
        hi = mn + rng * (row + 1) / height
        line = ""
        for v in sampled:
            if   v >= hi: line += f"[{MG}]#[/]"
            elif v >= lo: line += f"[green]#[/]"
            elif row == height//2: line += f"[{DG}]-[/]"
            else: line += " "
        if row == height - 1: yl = f" [{DG}]{mx:,.0f}[/]"
        elif row == height//2: yl = f" [{DG}]{(mn+rng*0.5):,.0f}[/]"
        elif row == 0: yl = f" [{DG}]{mn:,.0f}[/]"
        else: yl = ""
        console.print(f"  {line}{yl}")
    console.print(f"  [{DG}]{'-'*width}[/]")
    pnl_col = MG if equity[-1] >= equity[0] else "bright_red"
    console.print(
        f"  [{DG}]Start: {equity[0]:,.0f}  ->  End: {equity[-1]:,.0f}  "
        f"([{pnl_col}]{equity[-1]-equity[0]:+,.0f}[/])[/]"
    )


# ============================================================
# MAIN
# ============================================================

def run_v3(
    start:      str   = "2020-01-01",
    end:        str   = "2026-05-20",
):
    console.print(Panel(
        "[bold bright_cyan]SCALP BACKTEST v3 -- Deep Dive: PDB + NOM + Combined[/]\n"
        "[grey62]XAU/USD | PDH/PDL Breakout | NY Open Momentum | Combined Portfolio[/]",
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
    h4_df = h4_df[h4_df["time"] <= pd.Timestamp(end)].reset_index(drop=True)

    h4_tl, h4_ct = build_h4_timeline(h4_df)
    df["hour"]    = df["time"].dt.hour
    total_days    = len(df["time"].dt.normalize().unique())
    pdh_pdl       = _daily_pdh_pdl(df)

    console.print(f"  [grey62]Period: {start} -> {end} | Days: {total_days}[/]\n")

    results = {}

    # ============================================================
    # 1. PDB PARAMETER SWEEP
    # ============================================================
    console.print("[cyan]-- PDB Parameter Sweep --[/]")
    for rr in PDB_RR_VARIANTS:
        for sl_b in PDB_SL_VARIANTS:
            for h4f in [True, False]:
                tag = f"PDB_RR{rr}_SL{int(sl_b)}{'_H4' if h4f else ''}"
                r   = run_pdb_full(df, h4_tl, h4_ct, pdh_pdl,
                                   rr_ratio=rr, sl_buf=sl_b, h4_filter=h4f)
                results[tag] = r
                s = _stats(r)
                console.print(
                    f"  {tag:30s}  n={s['n']:4d}  WR={s['wr']:5.1f}%  "
                    f"PF={s['pf']:.2f}  pips={s['pips']:+.0f}"
                )

    # PDB session breakdown (best config: RR2.0, SL5, H4)
    console.print("\n[cyan]-- PDB Session Breakdown --[/]")
    for sess in ["LONDON", "NY", "ASIAN", "ALL"]:
        tag = f"PDB_RR2.0_SL5_H4_{sess}"
        r   = run_pdb_full(df, h4_tl, h4_ct, pdh_pdl,
                           rr_ratio=2.0, sl_buf=5.0, h4_filter=True,
                           session_filter=sess)
        results[tag] = r
        s = _stats(r)
        console.print(
            f"  {tag:35s}  n={s['n']:4d}  WR={s['wr']:5.1f}%  "
            f"PF={s['pf']:.2f}  pips={s['pips']:+.0f}"
        )

    # PDB direction breakdown
    console.print("\n[cyan]-- PDB Direction Breakdown --[/]")
    for dirn in ["BUY", "SELL"]:
        tag = f"PDB_RR2.0_H4_{dirn}"
        r   = run_pdb_full(df, h4_tl, h4_ct, pdh_pdl,
                           rr_ratio=2.0, sl_buf=5.0, h4_filter=True,
                           direction_filter=dirn)
        results[tag] = r
        s = _stats(r)
        console.print(
            f"  {tag:30s}  n={s['n']:4d}  WR={s['wr']:5.1f}%  "
            f"PF={s['pf']:.2f}  pips={s['pips']:+.0f}"
        )

    # PDB retest variant
    console.print("\n[cyan]-- PDB Retest Entry --[/]")
    for rr in [2.0, 2.5]:
        tag = f"PDB_RT_RR{rr}_H4"
        r   = run_pdb_full(df, h4_tl, h4_ct, pdh_pdl,
                           rr_ratio=rr, sl_buf=5.0, h4_filter=True, retest=True)
        results[tag] = r
        s = _stats(r)
        console.print(
            f"  {tag:30s}  n={s['n']:4d}  WR={s['wr']:5.1f}%  "
            f"PF={s['pf']:.2f}  pips={s['pips']:+.0f}"
        )

    # ============================================================
    # 2. NOM DEEP DIVE
    # ============================================================
    console.print("\n[cyan]-- NOM (NY Open) Sweep --[/]")
    for rr in NOM_RR_VARIANTS:
        for h4f in [True, False]:
            for ar in [0.0, 10.0, 15.0]:
                tag = f"NOM_RR{rr}{'_H4' if h4f else ''}{'_AR'+str(int(ar)) if ar>0 else ''}"
                r   = run_nom_deep(df, h4_tl, h4_ct, rr_ratio=rr,
                                   h4_filter=h4f, asian_min_range=ar)
                results[tag] = r
                s = _stats(r)
                console.print(
                    f"  {tag:35s}  n={s['n']:4d}  WR={s['wr']:5.1f}%  "
                    f"PF={s['pf']:.2f}  pips={s['pips']:+.0f}"
                )

    # ============================================================
    # 3. RANKING -- Composite Score: PF * pips_per_year
    # ============================================================
    console.print()
    console.rule("[bold bright_cyan]RANKING -- COMPOSITE SCORE (PF x Pips/Year)[/]")

    period_years = total_days / 252.0  # trading days

    scored = []
    for name, trades in results.items():
        s = _stats(trades)
        if s["n"] < 80 or s["pips"] <= 0:
            continue
        ppy  = s["pips"] / period_years
        comp = s["pf"] * ppy
        gm   = _green_months(trades)
        scored.append({**s, "name": name, "ppy": ppy, "composite": comp,
                       "green_pct": gm})

    scored.sort(key=lambda x: x["composite"], reverse=True)

    MG = "bright_green"; RD = "bright_red"; GD = "gold1"; DG = "grey62"; CC = "bright_cyan"

    tbl = Table(box=rich_box.DOUBLE_EDGE, header_style="bold bright_cyan",
                expand=False, padding=(0, 1))
    tbl.add_column("#",        width=4,  justify="right")
    tbl.add_column("TECHNIQUE",width=25, style="bold")
    tbl.add_column("N",        width=6,  justify="right")
    tbl.add_column("WIN%",     width=7,  justify="right")
    tbl.add_column("PF",       width=6,  justify="right")
    tbl.add_column("TOTAL P",  width=9,  justify="right")
    tbl.add_column("P/YR",     width=8,  justify="right")
    tbl.add_column("GRN%",     width=6,  justify="right")
    tbl.add_column("SCORE",    width=10, justify="right")

    for rank, s in enumerate(scored[:20], 1):
        wr_col = MG if s["wr"] >= 45 else GD if s["wr"] >= 35 else RD
        pf_col = MG if s["pf"] >= 1.5 else GD if s["pf"] >= 1.2 else RD
        gm_col = MG if s["green_pct"] >= 60 else GD if s["green_pct"] >= 50 else RD
        tbl.add_row(
            f"[{GD}]{rank}[/]",
            f"[{CC}]{s['name']}[/]",
            str(s["n"]),
            f"[{wr_col}]{s['wr']:.1f}%[/]",
            f"[{pf_col}]{s['pf']:.2f}[/]",
            f"[{MG}]{s['pips']:+.0f}[/]",
            f"[{MG}]{s['ppy']:+.0f}[/]",
            f"[{gm_col}]{s['green_pct']:.0f}%[/]",
            f"[bold {MG}]{s['composite']:,.0f}[/]",
        )
    console.print(tbl)

    # ============================================================
    # 4. DEEP REPORT: PDB best + NOM best
    # ============================================================
    if scored:
        best_pdb_name = next(
            (s["name"] for s in scored if "PDB" in s["name"] and "RT" not in s["name"]), None
        )
        best_nom_name = next(
            (s["name"] for s in scored if "NOM" in s["name"]), None
        )

        best_pdb = results.get(best_pdb_name, []) if best_pdb_name else []
        best_nom = results.get(best_nom_name, []) if best_nom_name else []

        console.print()
        console.rule("[bold bright_cyan]DEEP DIVE -- BEST PDB[/]")
        if best_pdb:
            s = _stats(best_pdb)
            gm = _green_months(best_pdb)
            console.print(
                f"  [bold bright_cyan]{best_pdb_name}[/]  "
                f"n={s['n']}  WR={s['wr']:.1f}%  PF={s['pf']:.2f}  "
                f"pips={s['pips']:+.0f}  green={gm:.0f}%"
            )
            _print_direction_breakdown(best_pdb, best_pdb_name)
            _monthly_heatmap(best_pdb, best_pdb_name)

        console.print()
        console.rule("[bold bright_cyan]DEEP DIVE -- BEST NOM[/]")
        if best_nom:
            s = _stats(best_nom)
            gm = _green_months(best_nom)
            console.print(
                f"  [bold bright_cyan]{best_nom_name}[/]  "
                f"n={s['n']}  WR={s['wr']:.1f}%  PF={s['pf']:.2f}  "
                f"pips={s['pips']:+.0f}  green={gm:.0f}%"
            )
            _print_direction_breakdown(best_nom, best_nom_name)
            _monthly_heatmap(best_nom, best_nom_name)

        # ============================================================
        # 5. COMBINED PORTFOLIO SIMULATION
        # ============================================================
        console.print()
        console.rule("[bold bright_yellow]COMBINED PORTFOLIO -- PDB + NOM[/]")

        port = simulate_portfolio(
            [best_pdb, best_nom],
            initial_balance=10_000.0,
            risk_pct=1.0
        )
        _print_portfolio_report(port, f"COMBINED: {best_pdb_name} + {best_nom_name}")
        _print_monthly_portfolio(port["monthly"], "COMBINED")
        _equity_ascii(port["equity"])

        # ============================================================
        # 6. FINAL RECOMMENDATION
        # ============================================================
        console.print()
        port_ppy = port["per_year"]
        port_gm  = port["green_pct"]

        console.print(Panel(
            f"[bold bright_green]FINAL RECOMMENDATION[/]\n\n"
            f"  Sistem terbaik: [bold bright_cyan]{best_pdb_name} + {best_nom_name}[/]\n\n"
            f"  PDB ({best_pdb_name}):\n"
            f"    - Trade: Breakout PDH/PDL dengan konfirmasi H4 CMP\n"
            f"    - Entry : M30 close melampaui PDH/PDL\n"
            f"    - SL    : PDH/PDL - 5 pip (BUY) / + 5 pip (SELL)\n"
            f"    - TP    : 2x RR dari SL\n"
            f"    - Filter: H4 CMP harus searah (bukan WAIT)\n\n"
            f"  NOM ({best_nom_name}):\n"
            f"    - Trade: NY Open (13:00 broker) momentum 2 bar M30\n"
            f"    - Entry : Close bar M30 ke-2 jika keduanya searah\n"
            f"    - SL    : Low/High 2 bar pertama + 3 pip\n"
            f"    - TP    : 2x RR dari SL\n"
            f"    - Filter: H4 CMP harus searah\n\n"
            f"  Combined Portfolio (6 tahun):\n"
            f"    - Total Trades   : {port['n']}\n"
            f"    - Pips/Tahun     : {port_ppy:+.0f}\n"
            f"    - Pips/Bulan avg : {port['per_month']:+.1f}\n"
            f"    - Green Months   : {port_gm:.0f}%\n"
            f"    - Max Drawdown   : {port['max_dd_pct']:.1f}%\n"
            f"    - Sharpe proxy   : {port['sharpe']:.2f}\n\n"
            f"  [grey62]CARA PAKAI:\n"
            f"  Gunakan sebagai konfirmasi entry di atas sistem CMP/VR/CF lo.\n"
            f"  Ketika CMP/VR/CF kasih signal + PDH/PDL break searah = entry strong.\n"
            f"  Ketika NY open momentum searah H4 + CMP = entry tambahan.[/]",
            title="[bold bright_yellow]HASIL AKHIR[/]",
            border_style="bright_yellow", padding=(0, 2)
        ))

    console.print("\n[grey62]Done.[/]")
    return results


def _green_months(trades: list) -> float:
    if not trades:
        return 0.0
    monthly: dict = {}
    for t in trades:
        key = t["open_time"].strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0.0) + t["pips"]
    green = sum(1 for v in monthly.values() if v > 0)
    return green / len(monthly) * 100 if monthly else 0.0


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    START = "2020-01-01"
    END   = "2026-05-20"
    run_v3(start=START, end=END)
