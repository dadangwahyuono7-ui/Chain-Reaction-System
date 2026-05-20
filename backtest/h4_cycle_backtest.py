"""
H4 CYCLE BACKTEST — "1 Candle H4" Strategy
Doctrine: Daily Deploy — M30 sequence dalam 1 window H4

Rules (per user):
  1. NEW H4 candle opens -> tunggu 30 menit (1 M30 bar close)
  2. Baca CMP M30 terbaru setelah M30 pertama close
  3. Tunggu M5 VR: M5 breakout BERLAWANAN dari CMP M30 (minor SNR body break)
  4. Tunggu M5 CF: M5 breakout SEARAH CMP M30 setelah VR -> ENTRY
  5. SL = M5 VR minor SNR level + buffer
  6. TP = M30 SNR level opposite side + buffer (atau fixed RR)
  7. Force close di akhir candle H4 yang sama (4 jam dari open)
  8. Max 1 trade per H4 candle
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich import box as rich_box

from engine.core import TFState
from backtest.backtest import (load_historical_data, load_csv_data,
                               Trade, PIP, print_report, TF_MINUTES)

console = Console()


# ── M30 Timeline Builder ──────────────────────────────────────────────────────

def build_m30_timeline(m30_df: pd.DataFrame) -> dict:
    """
    Pre-compute M30 TFState at every bar using rolling 100-bar window.
    Returns dict: {bar_open_time -> {cmp, sup, res, cmp_change_time}}.

    Timeline entry at time T stores state AFTER bar T closes, which is
    reflected in TFState when the NEXT bar (T+30) becomes iloc[-1].
    So to read state "after first M30 of H4 closes", look up T0+30.
    """
    state = TFState("M30")
    timeline = {}
    n = len(m30_df)

    for i in range(n):
        lo = max(0, i - 99)
        visible = m30_df.iloc[lo : i + 1].reset_index(drop=True)
        if len(visible) >= 3:
            state.update(visible, "WAIT", 0)
        timeline[m30_df.iloc[i]["time"]] = {
            "cmp":             state.cmp,
            "sup":             state.sup,
            "res":             state.res,
            "cmp_change_time": state.cmp_change_time,
        }

    return timeline


# ── MFE Report ────────────────────────────────────────────────────────────────

def _print_mfe_report(trades: list) -> None:
    """
    MFE (Maximum Favorable Excursion) Analysis.

    Menjawab: setelah CF valid dan entry, harga jalan profit dulu atau
    langsung SL? Dan setelah BE protection aktif, berapa yang jadi BE/TP/SL?
    """
    if not trades:
        return

    sl_trades  = [t for t in trades if t["reason"] == "SL"]
    be_trades  = [t for t in trades if t["reason"] == "BE"]
    tp_trades  = [t for t in trades if t["reason"] == "TP"]
    h4_trades  = [t for t in trades if t["reason"] == "H4_END"]
    be_active  = any(t.get("be_triggered") for t in trades)

    console.rule("[bold yellow]MFE ANALYSIS -- Max Favorable Excursion[/]")
    console.print()

    # ── Per-outcome MFE summary ───────────────────────────────────────────────
    tbl = Table(box=rich_box.SIMPLE_HEAD, show_header=True, header_style="bold cyan")
    tbl.add_column("Outcome",  style="bold")
    tbl.add_column("Trades",   justify="right")
    tbl.add_column("Pips avg", justify="right")
    tbl.add_column("MFE min",  justify="right")
    tbl.add_column("MFE avg",  justify="right")
    tbl.add_column("MFE max",  justify="right")
    tbl.add_column(">0p",      justify="right")
    tbl.add_column(">5p",      justify="right")
    tbl.add_column(">10p",     justify="right")
    tbl.add_column(">20p",     justify="right")

    groups = [
        ("SL",     sl_trades,  "red"),
        ("BE",     be_trades,  "yellow"),
        ("TP",     tp_trades,  "green"),
        ("H4_END", h4_trades,  "grey62"),
        ("ALL",    trades,     "white"),
    ]
    for lbl, group, style in groups:
        if not group:
            continue
        mfe  = [t.get("mfe_pips", 0.0) for t in group]
        pips = [t["pips"] for t in group]
        n    = len(mfe)
        tbl.add_row(
            f"[{style}]{lbl}[/]",
            str(n),
            f"{sum(pips)/n:+.1f}p",
            f"{min(mfe):.1f}p",
            f"{sum(mfe)/n:.1f}p",
            f"{max(mfe):.1f}p",
            f"{sum(1 for m in mfe if m > 0)}/{n}",
            f"{sum(1 for m in mfe if m >= 5)}/{n}",
            f"{sum(1 for m in mfe if m >= 10)}/{n}",
            f"{sum(1 for m in mfe if m >= 20)}/{n}",
        )
    console.print(tbl)

    # ── BE Protection summary (kalau aktif) ──────────────────────────────────
    if be_active and (be_trades or sl_trades):
        total_neg  = len(sl_trades) + len(be_trades)
        lost_pips  = sum(abs(t["pips"]) for t in sl_trades)
        # Estimasi pips diselamatkan: BE trades yang tadinya akan jadi SL
        # Pakai avg SL loss dari true-SL trades sebagai proxy
        avg_sl_loss = (sum(abs(t["pips"]) for t in sl_trades) / len(sl_trades)
                       if sl_trades else 0.0)
        saved_est   = len(be_trades) * avg_sl_loss
        console.print(
            Panel(
                f"[bold]BE Protection aktif -- hasil:[/]\n\n"
                f"  Tidak TP total            : [white]{total_neg}[/] trades\n"
                f"    -> Kena BE (scratch 0p) : [bold yellow]{len(be_trades)}[/]"
                f"  ({len(be_trades)*100/total_neg:.1f}% dari yang tidak TP)\n"
                f"    -> Masih kena SL        : [bold red]{len(sl_trades)}[/]"
                f"  ({len(sl_trades)*100/total_neg:.1f}% dari yang tidak TP)\n\n"
                f"  Pips diselamatkan (est.)  : [bold green]+{saved_est:.0f}p[/]"
                f" ({len(be_trades)} BE x avg SL {avg_sl_loss:.1f}p)\n"
                f"  Pips masih loss di SL     : [bold red]-{lost_pips:.1f}p[/]\n\n"
                f"  [grey62]True SL = trade yang kena SL sebelum sempat\n"
                f"  sentuh BE trigger (+{be_trades[0].get('mfe_pips',5):.0f}p dari entry).[/]"
                if be_trades else
                f"  [grey62]True SL = trade yang kena SL sebelum sempat\n"
                f"  sentuh BE trigger.[/]",
                title="[bold yellow]BE Protection Summary[/]",
                border_style="yellow",
            )
        )

    # ── SL deep-dive (trades yang benar-benar kena SL, bukan BE) ─────────────
    raw_sl = sl_trades  # trades dengan reason="SL" (tidak ada BE trigger)
    if raw_sl:
        mfe = [t.get("mfe_pips", 0.0) for t in raw_sl]
        n   = len(mfe)
        moved_any = sum(1 for m in mfe if m > 0)
        moved_5   = sum(1 for m in mfe if m >= 5)
        moved_10  = sum(1 for m in mfe if m >= 10)
        console.print(
            Panel(
                f"[bold]SL trades yang benar2 loss ({n} trades)[/]\n\n"
                f"  Sempat jalan profit (MFE > 0p) : [bold green]{moved_any}[/] / {n}"
                f" = [bold]{moved_any*100/n:.1f}%[/]\n"
                f"  Sempat jalan >= 5p profit      : {moved_5} / {n}"
                f" = {moved_5*100/n:.1f}%\n"
                f"  Sempat jalan >= 10p profit     : {moved_10} / {n}"
                f" = {moved_10*100/n:.1f}%\n\n"
                f"  MFE min (sebelum SL)           : [bold yellow]{min(mfe):.1f}p[/]\n"
                f"  MFE avg (sebelum SL)           : [bold]{sum(mfe)/n:.1f}p[/]\n\n"
                f"  [grey62]Ini adalah trade yang langsung SL sebelum\n"
                f"  sempat sentuh BE trigger.[/]",
                title="[bold red]True SL -- Tidak Ada BE[/]",
                border_style="red",
            )
        )

    # ── MFE histogram: SL + BE gabungan (semua yang tidak TP) ────────────────
    all_non_tp = sl_trades + be_trades
    if all_non_tp:
        mfe = [t.get("mfe_pips", 0.0) for t in all_non_tp]
        n   = len(mfe)
        buckets = [
            ("<0p  (langsung SL tanpa gerak) ", lambda m: m <= 0),
            ("0-5p  (tidak sentuh BE)        ", lambda m: 0 < m < 5),
            ("5-10p                          ", lambda m: 5 <= m < 10),
            ("10-20p                         ", lambda m: 10 <= m < 20),
            ("20-30p                         ", lambda m: 20 <= m < 30),
            (">30p                           ", lambda m: m >= 30),
        ]
        console.print("[bold cyan]Non-TP trades MFE distribution:[/]")
        for lbl, fn in buckets:
            count = sum(1 for m in mfe if fn(m))
            pct   = count * 100 / n
            bar   = "#" * int(pct / 2)
            console.print(f"  {lbl} {count:4d} ({pct:5.1f}%) {bar}")
        console.print()


# ── H4 Cycle Runner ───────────────────────────────────────────────────────────

def run_h4_cycle_backtest(
    symbol:           str   = "XAUUSD",
    start:            str   = "2025-01-01",
    end:              str   = "2025-12-31",
    initial_balance:  float = 10_000.0,
    sl_buffer_pips:   float = 5.0,
    rr_ratio:         float = 0.0,   # 0 = M30 SNR natural | >0 = fixed RR
    max_trades:       int   = 0,
    child_tf:         str   = "M5",  # TF untuk VR/CF — "M5" atau "M15"
    data_source:      str   = "csv", # "csv" = dari DATACSV folder | "mt5" = live MT5
    be_protect_pips:  float = 0.0,   # 0 = disabled | 5.0 = geser SL ke entry saat +5p
):
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt   = datetime.strptime(end,   "%Y-%m-%d")

    # ── Load data ─────────────────────────────────────────────────────────────
    needed_tfs = ["H4", "M30", child_tf]
    if data_source == "csv":
        console.print(f"\n[bold cyan]Loading CSV data: {symbol}[/]")
        all_data = load_csv_data(symbol, start_dt, end_dt, tfs=needed_tfs)
    else:
        all_data = load_historical_data(symbol, start_dt, end_dt)

    h4_df  = all_data.get("H4",      pd.DataFrame())
    m30_df = all_data.get("M30",     pd.DataFrame())
    m5_df  = all_data.get(child_tf,  pd.DataFrame())

    for name, df in [("H4", h4_df), ("M30", m30_df), (child_tf, m5_df)]:
        if len(df) == 0:
            console.print(f"[red]ERROR: {name} data kosong[/]")
            if name == child_tf and child_tf == "M5" and data_source == "mt5":
                console.print(
                    "[yellow]TIP: M5 belum di-download di MT5.\n"
                    "     MT5 -> Tools -> History Center -> XAUUSD -> M5 -> Download\n"
                    "     Atau ganti DATA_SOURCE = 'csv' di run.py (pakai DATACSV folder).[/]"
                )
            return None

    # ── Pre-build M30 timeline ─────────────────────────────────────────────────
    console.print("\n[cyan]Building M30 CMP timeline...[/]")
    m30_timeline = build_m30_timeline(m30_df)

    child_tf_minutes = TF_MINUTES.get(child_tf, 5)

    # ── Pre-index M30 dan child TF untuk fast O(log N) lookups ────────────────
    m30_df    = m30_df.reset_index(drop=True)
    m30_times = m30_df["time"].values          # searchsorted M30

    m5_df    = m5_df.reset_index(drop=True)
    m5_times = m5_df["time"].values            # searchsorted child TF

    # ── H4 candles in test window ─────────────────────────────────────────────
    h4_test = h4_df[
        (h4_df["time"] >= pd.Timestamp(start_dt)) &
        (h4_df["time"] <= pd.Timestamp(end_dt))
    ].reset_index(drop=True)

    total_h4 = len(h4_test)
    console.print(
        f"[cyan]H4 Cycle Backtest [{child_tf} VR/CF] — [bold]{total_h4}[/] H4 candles "
        f"[grey62]({start} -> {end})[/][/]\n"
    )

    trades        = []
    balance       = initial_balance
    equity_curve  = [initial_balance]
    stat_skip     = 0   # H4 candles skipped (M30 WAIT or no M5 data)
    stat_no_sig   = 0   # H4 candles with no VR or no CF signal
    stat_no_vr    = 0
    stat_no_cf    = 0

    with Progress(
        TextColumn("[cyan]H4 Cycles[/]"),
        BarColumn(bar_width=50),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[grey62]{task.completed}/{task.total}[/]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("h4-cycles", total=total_h4)

        for _, h4_bar in h4_test.iterrows():
            progress.advance(task)

            if max_trades > 0 and len(trades) >= max_trades:
                equity_curve.append(balance)
                continue

            T0   = h4_bar["time"]                       # H4 candle open
            T_end = T0 + pd.Timedelta(hours=4)          # H4 candle close

            # ── Step 1: M30 CMP after first M30 bar of this H4 closes ─────────
            # First M30 bar opened at T0, closed at T0+30.
            # Timeline entry at T0+30 reflects state AFTER that bar's close.
            T_m30_close = T0 + pd.Timedelta(minutes=30)
            m30_state   = m30_timeline.get(T_m30_close)

            # Fallback: market may have no exact T0+30 bar (gap/holiday)
            if m30_state is None:
                for extra in [35, 60, 90]:
                    m30_state = m30_timeline.get(T0 + pd.Timedelta(minutes=extra))
                    if m30_state:
                        break

            if m30_state is None or m30_state["cmp"] == "WAIT":
                stat_skip += 1
                equity_curve.append(balance)
                continue

            direction    = m30_state["cmp"]
            m30_dir_time = m30_state["cmp_change_time"]

            # ── TP ref: HIGH/LOW dari bar M30 pertama H4 (bar yang buka di T0) ─
            # Bar M30 yang buka di T0 = bar yang kasih breakout pertama setelah H4 open.
            # HIGH bar ini = target natural untuk BUY.
            # LOW  bar ini = target natural untuk SELL.
            m30_i = int(np.searchsorted(m30_times, np.datetime64(T0), side="left"))
            if m30_i < len(m30_df) and m30_df.iloc[m30_i]["time"] == T0:
                m30_first_high = float(m30_df.iloc[m30_i]["high"])
                m30_first_low  = float(m30_df.iloc[m30_i]["low"])
            else:
                # Fallback: bar terdekat setelah T0
                if m30_i < len(m30_df):
                    m30_first_high = float(m30_df.iloc[m30_i]["high"])
                    m30_first_low  = float(m30_df.iloc[m30_i]["low"])
                else:
                    m30_first_high = 0.0
                    m30_first_low  = 0.0

            # ── Step 2: M5 bars — context then VR/CF window ───────────────────
            # Find M5 bar index at T0 (use searchsorted for O(log N) lookup)
            # np.searchsorted returns first idx where m5_times >= T0
            m5_start = int(np.searchsorted(m5_times, np.datetime64(T0), side="left"))
            # Context: 100 bars before T0
            ctx_start = max(0, m5_start - 100)
            m5_context = m5_df.iloc[ctx_start:m5_start].reset_index(drop=True)

            if len(m5_context) < 3:
                stat_skip += 1
                equity_curve.append(balance)
                continue

            # Fresh M5 TFState for this H4 cycle, parented to M30 direction
            m5_tracker = TFState("M5")
            m5_tracker.update(m5_context, direction, m30_dir_time)

            vr_found   = False
            vr_sl_ref  = 0.0
            open_trade: Trade | None = None
            cycle_done = False
            vr_triggered = False

            # Loop M5 bars inside the H4 window
            j = m5_start
            while j < len(m5_df):
                t_m5 = m5_df.iloc[j]["time"]
                if t_m5 >= T_end:
                    break

                high  = m5_df.iloc[j]["high"]
                low   = m5_df.iloc[j]["low"]
                close = m5_df.iloc[j]["close"]

                # ── Check open trade exit ──────────────────────────────────────
                if open_trade is not None:
                    result = open_trade.check(high, low, t_m5)
                    if result is not None:
                        trades.append(result)
                        balance += result["pips"] * 1.0
                        equity_curve.append(balance)
                        cycle_done = True
                        break

                # ── Force close at last M5 bar of H4 window ───────────────────
                next_m5_time = (m5_df.iloc[j + 1]["time"]
                                if j + 1 < len(m5_df)
                                else t_m5 + pd.Timedelta(minutes=child_tf_minutes))
                if next_m5_time >= T_end and open_trade is not None:
                    result = open_trade._result(close, "H4_END", t_m5)
                    trades.append(result)
                    balance += result["pips"] * 1.0
                    equity_curve.append(balance)
                    cycle_done = True
                    break

                # ── Update M5 state ────────────────────────────────────────────
                lo      = max(0, j - 99)
                visible = m5_df.iloc[lo : j + 1].reset_index(drop=True)
                status  = m5_tracker.update(visible, direction, m30_dir_time)

                # VR/CF only AFTER first M30 bar closed (T0+30)
                if t_m5 >= T_m30_close and open_trade is None:

                    if not vr_found:
                        if status == "VR":
                            vr_found  = True
                            vr_triggered = True
                            # Record VR SNR level for SL
                            vr_sl_ref = (m5_tracker.sup if direction == "BUY"
                                         else m5_tracker.res)

                    else:
                        if status == "CF":
                            # ── ENTRY searah M30 ───────────────────────────────
                            # M30 breakout BUY → M5 VR (SELL) → M5 CF (BUY) → ENTRY BUY
                            # M30 breakout SELL → M5 VR (BUY) → M5 CF (SELL) → ENTRY SELL
                            entry = close

                            if direction == "BUY":
                                sl = (vr_sl_ref - sl_buffer_pips * PIP
                                      if vr_sl_ref > 0 else entry - 15 * PIP)
                                if rr_ratio > 0:
                                    # Fixed RR
                                    tp = entry + (entry - sl) * rr_ratio
                                elif m30_first_high > entry:
                                    # TP = HIGH bar M30 pertama (puncak momentum BUY)
                                    tp = m30_first_high
                                else:
                                    # M30 high sudah terlewat — fallback 1:1.5 RR
                                    tp = entry + (entry - sl) * 1.5
                            else:  # SELL
                                sl = (vr_sl_ref + sl_buffer_pips * PIP
                                      if vr_sl_ref > 0 else entry + 15 * PIP)
                                if rr_ratio > 0:
                                    tp = entry - (sl - entry) * rr_ratio
                                elif m30_first_low > 0 and m30_first_low < entry:
                                    # TP = LOW bar M30 pertama (dasar momentum SELL)
                                    tp = m30_first_low
                                else:
                                    # M30 low sudah terlewat — fallback 1:1.5 RR
                                    tp = entry - (sl - entry) * 1.5

                            valid = (
                                sl > 0 and tp > 0 and
                                ((direction == "BUY"  and tp > entry > sl) or
                                 (direction == "SELL" and tp < entry < sl))
                            )
                            if valid:
                                label = f"M30{direction[0]}_VR_CF"
                                open_trade = Trade(direction, entry, sl, tp, label,
                                                   t_m5, be_pips=be_protect_pips)

                j += 1

            # End of H4 cycle — force close if still open
            if not cycle_done and open_trade is not None:
                last_j = j - 1 if j > m5_start else m5_start
                last_close = m5_df.iloc[min(last_j, len(m5_df) - 1)]["close"]
                last_time  = m5_df.iloc[min(last_j, len(m5_df) - 1)]["time"]
                result = open_trade._result(last_close, "H4_END", last_time)
                trades.append(result)
                balance += result["pips"] * 1.0

            if not cycle_done and open_trade is None:
                if not vr_triggered:
                    stat_no_vr += 1
                else:
                    stat_no_cf += 1

            equity_curve.append(balance)

    # ── Summary ────────────────────────────────────────────────────────────────
    console.print(
        f"\n[grey62]H4 candles   : [white]{total_h4}[/]\n"
        f"Skipped (no M30 dir / no M5 data) : [yellow]{stat_skip}[/]\n"
        f"No VR found  : [yellow]{stat_no_vr}[/]\n"
        f"VR ok, no CF : [yellow]{stat_no_cf}[/]\n"
        f"Trades fired : [white]{len(trades)}[/][/]"
    )

    print_report(
        trades, equity_curve, initial_balance, balance,
        symbol, start, end,
        engine=f"H4 CYCLE (M30->{child_tf} VR->CF)"
    )
    _print_mfe_report(trades)
    return trades, equity_curve


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from engine.connection import connect_mt5

    # ═══════════════════════════ CONFIG ═══════════════════════════
    SYMBOL          = "XAUUSD"
    START_DATE      = "2025-01-01"
    END_DATE        = "2026-05-20"
    INITIAL_BALANCE = 10_000.0
    SL_BUFFER_PIPS  = 5.0      # buffer pips di luar VR SNR level
    RR_RATIO        = 0.0      # 0 = M30 SNR natural, 2.0 = fixed 1:2 RR

    # DATA_SOURCE: "csv" = tidak butuh MT5 (pakai DATACSV folder)
    #              "mt5" = ambil dari MT5 terminal (harus running)
    DATA_SOURCE     = "csv"
    CHILD_TF        = "M5"     # TF VR/CF: "M5" tersedia di DATACSV
    # ══════════════════════════════════════════════════════════════

    console.print("[bold cyan]H4 CYCLE BACKTEST[/]")
    console.print(f"[grey62]Data: {DATA_SOURCE.upper()} | Rule: New H4 -> M30 CMP -> {CHILD_TF} VR -> {CHILD_TF} CF -> ENTRY[/]")
    console.print("[grey62]Engine: Minor SNR body breakout sesuai Daily Deploy doctrine[/]\n")

    if DATA_SOURCE == "csv":
        run_h4_cycle_backtest(
            symbol          = SYMBOL,
            start           = START_DATE,
            end             = END_DATE,
            initial_balance = INITIAL_BALANCE,
            sl_buffer_pips  = SL_BUFFER_PIPS,
            rr_ratio        = RR_RATIO,
            child_tf        = CHILD_TF,
            data_source     = "csv",
        )
    else:
        if not connect_mt5():
            console.print("[red]ERROR: MT5 connection failed[/]")
        else:
            try:
                run_h4_cycle_backtest(
                    symbol          = SYMBOL,
                    start           = START_DATE,
                    end             = END_DATE,
                    initial_balance = INITIAL_BALANCE,
                    sl_buffer_pips  = SL_BUFFER_PIPS,
                    rr_ratio        = RR_RATIO,
                    child_tf        = CHILD_TF,
                    data_source     = "mt5",
                )
            finally:
                mt5.shutdown()
                console.print("\n[grey62]MT5 disconnected.[/]")
