"""
BACKTEST ENGINE — SACRED DOCTRINE
Replay historical MT5 data through the existing engine (engine/core.py).
Engine core.py TIDAK diubah — hanya data feed-nya yang diganti dari live ke historical.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich import box as rich_box

# Import ONLY TFState & CMPDetector — tidak sentuh engine keseluruhan
from engine.core import TFState, CMPDetector

console = Console()

# ── Constants ─────────────────────────────────────────────────────────────────
TF_ORDER   = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]
MASTER_TF  = "H4"
MASTER_IDX = TF_ORDER.index(MASTER_TF)

MT5_TFS = {
    "MN1": mt5.TIMEFRAME_MN1,
    "W1":  mt5.TIMEFRAME_W1,
    "D1":  mt5.TIMEFRAME_D1,
    "H4":  mt5.TIMEFRAME_H4,
    "H1":  mt5.TIMEFRAME_H1,
    "M30": mt5.TIMEFRAME_M30,
    "M15": mt5.TIMEFRAME_M15,
    "M5":  mt5.TIMEFRAME_M5,
}

# Durasi menit per TF (untuk filter bar yang sudah close)
TF_MINUTES = {
    "MN1": 43200, "W1": 10080, "D1": 1440,
    "H4": 240, "H1": 60, "M30": 30, "M15": 15, "M5": 5,
}

PIP = 0.1   # 1 pip Gold = 0.1 USD


# ── Data Loader ───────────────────────────────────────────────────────────────

def load_historical_data(symbol: str, start: datetime, end: datetime) -> dict:
    """
    Ambil data historical dari MT5 untuk semua TF.
    Buffer berbeda per TF — TF kecil pakai buffer pendek supaya MT5
    tidak timeout, TF besar butuh context lebih panjang untuk initialize_cmp().
    """
    # Buffer per TF (hari) — makin kecil TF makin pendek buffernya
    TF_BUFFER = {
        "MN1": 730, "W1": 730, "D1": 365,
        "H4":  180, "H1":  90,
        "M30":  60, "M15": 30, "M5": 14,
    }

    all_data = {}
    console.print(f"\n[bold cyan]Loading historical data: {symbol}[/]")

    for tf_name, mt5_tf in MT5_TFS.items():
        buf_days    = TF_BUFFER.get(tf_name, 60)
        start_fetch = start - timedelta(days=buf_days)

        rates = mt5.copy_rates_range(symbol, mt5_tf, start_fetch, end)

        # Fallback: jika gagal, coba tanpa buffer (hanya periode backtest)
        if rates is None or len(rates) == 0:
            console.print(f"  [yellow]RETRY[/] {tf_name} — coba tanpa buffer...")
            rates = mt5.copy_rates_range(symbol, mt5_tf, start, end)

        if rates is None or len(rates) == 0:
            console.print(f"  [red]WARN:[/] {tf_name} — no data "
                          f"[grey62](load history di MT5: Tools → History Center)[/]")
            all_data[tf_name] = pd.DataFrame()
            continue

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        all_data[tf_name] = df
        console.print(f"  [green]✓[/] {tf_name:4s} — {len(df):6,} bars  "
                      f"[grey62]({df['time'].iloc[0].strftime('%Y-%m-%d')} → "
                      f"{df['time'].iloc[-1].strftime('%Y-%m-%d')})[/]")

    return all_data


# ── Backtest Analyst ──────────────────────────────────────────────────────────

class BacktestAnalyst:
    """
    Wrapper yang memainkan ulang data historical bar-per-bar melalui TFState
    yang sama persis dengan engine live.  Tidak ada perubahan logic deteksi.
    """

    def __init__(self, symbol: str, all_data: dict):
        self.symbol   = symbol
        self.all_data = all_data
        self.states   = {name: TFState(name) for name in TF_ORDER}
        self.master_cmp  = "WAIT"
        self.master_time = 0.0

    def update_at(self, current_time: pd.Timestamp):
        """
        Update semua TFState dengan data yang SUDAH CLOSE sebelum current_time.
        Bar dianggap closed jika open_time + TF_duration <= current_time + 5min
        (M5 bar yang sedang kita proses baru saja close).
        """
        current_close = current_time + pd.Timedelta(minutes=5)
        context_parent_cmp  = "WAIT"
        context_parent_time = 0.0

        for i, name in enumerate(TF_ORDER):
            df = self.all_data.get(name)
            if df is None or len(df) == 0:
                continue

            # Hanya bar yang sudah fully closed saat ini
            cutoff = current_close - pd.Timedelta(minutes=TF_MINUTES[name])
            visible = df[df["time"] <= cutoff].tail(100).reset_index(drop=True)
            if len(visible) < 3:
                continue

            st = self.states[name]
            if i < MASTER_IDX:
                st.update(visible, context_parent_cmp, context_parent_time)
                context_parent_cmp  = st.cmp
                context_parent_time = st.cmp_change_time

            elif i == MASTER_IDX:
                st.update(visible, context_parent_cmp, context_parent_time)
                self.master_cmp  = st.cmp
                self.master_time = st.cmp_change_time
                st.status = "MASTER"

            else:
                st.update(visible, self.master_cmp, self.master_time)

    def get_signal(self) -> dict | None:
        """
        Deteksi signal entry — logic identik dengan get_strike_signal() di engine,
        termasuk CF_HIGH fix (m5.vr_occurred) yang sudah kita terapkan.
        """
        h4  = self.states["H4"]
        m30 = self.states["M30"]
        m15 = self.states["M15"]
        m5  = self.states["M5"]

        if m30.cmp == "WAIT":
            return None

        direction = m30.cmp

        # Guard: M30 VR ke H4 = block entry
        if h4.cmp != "WAIT" and m30.cmp != h4.cmp:
            return None

        # Evaluasi M15 relative to M30
        m15_is_vr = (
            m15.cmp != direction and
            m15.cmp != "WAIT" and
            m15.cmp_change_time > m30.cmp_change_time
        )
        m15_solid = (m15.cmp == direction and not m15_is_vr)

        # M30 masih alive? (jika M30 flip setelah M15 VR = setup batal)
        if m15_is_vr and m30.cmp_change_time > m15.cmp_change_time:
            return None

        # ① MINOR_CF: M15 solid + M5 VR → M5 CF
        if m15_solid:
            if (m5.vr_occurred and
                m5.cmp == direction and
                m5.cmp_change_time > getattr(m5, "vr_change_time", 0) and
                m5.cmp_change_time > m15.cmp_change_time):
                return {
                    "action":   direction,
                    "type":     "MINOR_CF",
                    "sl_price": m5.sup if direction == "BUY" else m5.res,
                    "tp_price": m15.res if direction == "BUY" else m15.sup,
                }
            return None

        if not m15_is_vr:
            return None

        # ③ CF_LOW: M15 VR → M15 sendiri CF
        if (m15.cmp == direction and m15.vr_occurred and
                m15.cmp_change_time > getattr(m15, "vr_change_time", 0)):
            return {
                "action":   direction,
                "type":     "CF_LOW",
                "sl_price": m15.sup if direction == "BUY" else m15.res,
                "tp_price": m30.res if direction == "BUY" else m30.sup,
            }

        # ② CF_HIGH: M15 VR, M5 CF (m5.vr_occurred enforced — Iron Law fix)
        if (m15.cmp != direction and
                m5.vr_occurred and
                m5.cmp == direction and
                m5.cmp_change_time > m15.cmp_change_time and
                m5.cmp_change_time > getattr(m5, "vr_change_time", 0)):
            return {
                "action":   direction,
                "type":     "CF_HIGH",
                "sl_price": m15.sup if direction == "BUY" else m15.res,
                "tp_price": m30.res if direction == "BUY" else m30.sup,
            }

        return None


# ── Position Tracker ──────────────────────────────────────────────────────────

class Trade:
    def __init__(self, direction, entry, sl, tp, sig_type, open_time):
        self.direction = direction
        self.entry     = entry
        self.sl        = sl
        self.tp        = tp
        self.sig_type  = sig_type
        self.open_time = open_time

    def check(self, high, low, current_time):
        """Return (pips, reason, close_time) jika trade close, else None."""
        if self.direction == "BUY":
            if low  <= self.sl: return self._result(self.sl,  "SL", current_time)
            if high >= self.tp: return self._result(self.tp,  "TP", current_time)
        else:
            if high >= self.sl: return self._result(self.sl,  "SL", current_time)
            if low  <= self.tp: return self._result(self.tp,  "TP", current_time)
        return None

    def _result(self, exit_price, reason, close_time):
        pips = ((exit_price - self.entry) if self.direction == "BUY"
                else (self.entry - exit_price)) / PIP
        return {
            "direction":  self.direction,
            "type":       self.sig_type,
            "entry":      self.entry,
            "exit":       exit_price,
            "sl":         self.sl,
            "tp":         self.tp,
            "pips":       pips,
            "reason":     reason,
            "open_time":  self.open_time,
            "close_time": close_time,
        }


# ── Main Runner ───────────────────────────────────────────────────────────────

def run_backtest(
    symbol:          str   = "XAUUSD",
    start:           str   = "2025-01-01",
    end:             str   = "2025-12-31",
    initial_balance: float = 10_000.0,
    sl_buffer_pips:  float = 5.0,   # buffer di luar SNR
    rr_ratio:        float = 0.0,   # 0 = pakai SNR natural, >0 pakai fixed RR
    cooldown_bars:   int   = 12,    # M5 bars cooldown setelah entry (12 = 1 jam)
    max_trades:      int   = 0,     # 0 = unlimited
):
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt   = datetime.strptime(end,   "%Y-%m-%d")

    # Load data
    all_data = load_historical_data(symbol, start_dt, end_dt)

    # M5 sebagai jam replay
    m5_df = all_data.get("M5", pd.DataFrame())
    if len(m5_df) == 0:
        console.print("[red]ERROR: M5 data kosong[/]")
        return None

    # Filter ke periode backtest saja
    m5_bars = m5_df[
        (m5_df["time"] >= pd.Timestamp(start_dt)) &
        (m5_df["time"] <= pd.Timestamp(end_dt))
    ].reset_index(drop=True)

    total_bars = len(m5_bars)
    console.print(f"\n[cyan]Replaying [bold]{total_bars:,}[/] M5 bars "
                  f"[grey62]({start} → {end})[/][/]")

    analyst  = BacktestAnalyst(symbol, all_data)
    trades   = []
    open_trade: Trade | None = None
    balance  = initial_balance
    equity_curve = [initial_balance]
    cooldown = 0
    last_sig_type = None

    with Progress(
        TextColumn("[cyan]Progress[/]"),
        BarColumn(bar_width=50),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("replay", total=total_bars)

        for _, bar in m5_bars.iterrows():
            t     = bar["time"]
            high  = bar["high"]
            low   = bar["low"]
            close = bar["close"]

            # ── 1. Cek exit open trade
            if open_trade is not None:
                result = open_trade.check(high, low, t)
                if result is not None:
                    trades.append(result)
                    pnl_pip = result["pips"]
                    # Konversi pips ke USD (Gold: ~$1 per pip per 0.01 lot)
                    balance += pnl_pip * 1.0
                    open_trade = None
                    cooldown = cooldown_bars

            equity_curve.append(balance)

            # ── 2. Cooldown
            if cooldown > 0:
                cooldown -= 1
                progress.advance(task)
                continue

            if open_trade is not None:
                progress.advance(task)
                continue

            if max_trades > 0 and len(trades) >= max_trades:
                progress.advance(task)
                continue

            # ── 3. Update engine & cek signal
            analyst.update_at(t)
            sig = analyst.get_signal()

            if sig and sig["type"] != last_sig_type:
                direction = sig["action"]
                sig_type  = sig["type"]
                sl_ref    = sig["sl_price"]
                tp_ref    = sig["tp_price"]

                # Hitung SL dan TP
                if direction == "BUY":
                    entry = close
                    sl    = (sl_ref - sl_buffer_pips * PIP) if sl_ref and sl_ref > 0 else close - 15 * PIP
                    if rr_ratio > 0:
                        tp = entry + (entry - sl) * rr_ratio
                    else:
                        tp = (tp_ref + sl_buffer_pips * PIP) if tp_ref and tp_ref > 0 else close + 30 * PIP
                else:
                    entry = close
                    sl    = (sl_ref + sl_buffer_pips * PIP) if sl_ref and sl_ref > 0 else close + 15 * PIP
                    if rr_ratio > 0:
                        tp = entry - (sl - entry) * rr_ratio
                    else:
                        tp = (tp_ref - sl_buffer_pips * PIP) if tp_ref and tp_ref > 0 else close - 30 * PIP

                # Validasi
                if sl > 0 and tp > 0 and sl != entry and tp != entry:
                    if (direction == "BUY"  and tp > entry > sl) or \
                       (direction == "SELL" and tp < entry < sl):
                        open_trade    = Trade(direction, entry, sl, tp, sig_type, t)
                        last_sig_type = sig_type

            progress.advance(task)

    # Force close posisi yang masih open di akhir
    if open_trade is not None:
        last = m5_bars.iloc[-1]
        result = open_trade._result(last["close"], "EOD", last["time"])
        trades.append(result)
        balance += result["pips"] * 1.0

    print_report(trades, equity_curve, initial_balance, balance, symbol, start, end)
    return trades, equity_curve


# ── Report Printer ────────────────────────────────────────────────────────────

def print_report(trades, equity_curve, initial_balance, final_balance,
                 symbol, start, end):
    MG = "bright_green"; RD = "bright_red"; CC = "bright_cyan"; DG = "grey62"
    GD = "gold1"

    console.print()
    console.print(Panel(
        f"[bold {CC}]BACKTEST RESULT — SACRED DOCTRINE ENGINE[/]\n"
        f"[{DG}]Symbol:[/] [white]{symbol}[/]   "
        f"[{DG}]Period:[/] [white]{start} → {end}[/]",
        border_style="cyan", padding=(0, 2)
    ))

    if not trades:
        console.print(f"[yellow]Tidak ada trade yang generated.[/]")
        return

    wins   = [t for t in trades if t["pips"] > 0]
    losses = [t for t in trades if t["pips"] <= 0]
    total_pips = sum(t["pips"] for t in trades)
    win_rate   = len(wins) / len(trades) * 100
    avg_win    = sum(t["pips"] for t in wins)  / len(wins)   if wins   else 0
    avg_loss   = sum(t["pips"] for t in losses)/ len(losses) if losses else 0
    pf         = abs(avg_win / avg_loss) if avg_loss else 0

    # Max Drawdown
    peak = equity_curve[0]
    max_dd_pct = 0.0
    for eq in equity_curve:
        if eq > peak: peak = eq
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        if dd > max_dd_pct: max_dd_pct = dd

    # Consecutive wins/losses
    max_consec_w = max_consec_l = cur_w = cur_l = 0
    for t in trades:
        if t["pips"] > 0:
            cur_w += 1; cur_l = 0
            max_consec_w = max(max_consec_w, cur_w)
        else:
            cur_l += 1; cur_w = 0
            max_consec_l = max(max_consec_l, cur_l)

    pnl_col = MG if total_pips >= 0 else RD
    wr_col  = MG if win_rate >= 55 else GD if win_rate >= 45 else RD
    dd_col  = MG if max_dd_pct < 5 else GD if max_dd_pct < 10 else RD

    # ── Summary table
    summ = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0, 3),
                 expand=False)
    summ.add_column("METRIC",       style=DG,  width=22)
    summ.add_column("VALUE",        justify="right", width=14)
    summ.add_column("METRIC",       style=DG,  width=22)
    summ.add_column("VALUE",        justify="right", width=14)

    rows = [
        ("Total Trades",    f"[white]{len(trades)}[/]",
         "Avg Win (pips)",  f"[{MG}]{avg_win:+.1f}[/]"),
        ("Win Rate",        f"[{wr_col}]{win_rate:.1f}%[/]",
         "Avg Loss (pips)", f"[{RD}]{avg_loss:+.1f}[/]"),
        ("Total Pips",      f"[{pnl_col}]{total_pips:+.1f}[/]",
         "Profit Factor",   f"[{MG if pf>=1.5 else GD if pf>=1 else RD}]{pf:.2f}[/]"),
        ("Initial Balance", f"[white]{initial_balance:,.0f}[/]",
         "Max Drawdown",    f"[{dd_col}]{max_dd_pct:.2f}%[/]"),
        ("Final Balance",   f"[{pnl_col}]{final_balance:,.2f}[/]",
         "Net P&L",         f"[{pnl_col}]{final_balance-initial_balance:+,.2f}[/]"),
        ("Max Consec Win",  f"[{MG}]{max_consec_w}[/]",
         "Max Consec Loss", f"[{RD}]{max_consec_l}[/]"),
    ]
    for r in rows:
        summ.add_row(*r)
    console.print(summ)

    # ── By signal type
    by_type: dict = {}
    for t in trades:
        tp = t["type"]
        if tp not in by_type:
            by_type[tp] = {"n": 0, "w": 0, "pips": 0.0}
        by_type[tp]["n"] += 1
        by_type[tp]["pips"] += t["pips"]
        if t["pips"] > 0:
            by_type[tp]["w"] += 1

    console.print(f"\n[{CC}]── BY SIGNAL TYPE ──────────────────────────[/]")
    tt = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0, 2))
    tt.add_column("TYPE",   style=DG, width=12)
    tt.add_column("TRADES", justify="right", width=8)
    tt.add_column("WIN%",   justify="right", width=8)
    tt.add_column("PIPS",   justify="right", width=10)
    tt.add_column("AVG",    justify="right", width=8)

    for sig_type, d in by_type.items():
        wr  = d["w"] / d["n"] * 100 if d["n"] else 0
        avg = d["pips"] / d["n"] if d["n"] else 0
        pc  = MG if d["pips"] >= 0 else RD
        wc  = MG if wr >= 50 else RD
        tt.add_row(
            f"[{CC}]{sig_type}[/]",
            str(d["n"]),
            f"[{wc}]{wr:.0f}%[/]",
            f"[{pc}]{d['pips']:+.1f}[/]",
            f"[{pc}]{avg:+.1f}[/]",
        )
    console.print(tt)

    # ── Trade list (last 30)
    console.print(f"\n[{CC}]── TRADE LOG (last 30) ─────────────────────[/]")
    tl = Table(box=rich_box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
    tl.add_column("#",      style=DG,  width=4)
    tl.add_column("OPEN",   style=DG,  width=17)
    tl.add_column("DIR",    justify="center", width=5)
    tl.add_column("TYPE",   width=10)
    tl.add_column("ENTRY",  justify="right", width=8)
    tl.add_column("SL",     justify="right", width=8)
    tl.add_column("TP",     justify="right", width=8)
    tl.add_column("EXIT",   justify="right", width=8)
    tl.add_column("PIPS",   justify="right", width=8)
    tl.add_column("RES",    justify="center", width=5)

    for i, tr in enumerate(trades[-30:], max(1, len(trades) - 29)):
        dc = MG if tr["direction"] == "BUY" else RD
        pc = MG if tr["pips"] > 0 else RD
        rc = MG if tr["reason"] == "TP" else (GD if tr["reason"] == "EOD" else RD)
        tl.add_row(
            str(i),
            str(tr["open_time"])[:16],
            f"[{dc}]{tr['direction'][:1]}[/]",
            tr["type"],
            f"{tr['entry']:.2f}",
            f"[{RD}]{tr['sl']:.2f}[/]",
            f"[{MG}]{tr['tp']:.2f}[/]",
            f"{tr['exit']:.2f}",
            f"[{pc}]{tr['pips']:+.1f}[/]",
            f"[{rc}]{tr['reason']}[/]",
        )
    console.print(tl)

    # ── Equity curve ASCII
    if len(equity_curve) > 2:
        console.print(f"\n[{CC}]── EQUITY CURVE ────────────────────────────[/]")
        W, H = 64, 8
        mn, mx = min(equity_curve), max(equity_curve)
        rng = mx - mn if mx != mn else 1.0
        step = max(1, len(equity_curve) // W)
        sampled = [equity_curve[i] for i in range(0, len(equity_curve), step)][:W]

        for row in range(H - 1, -1, -1):
            lo = mn + rng * row / H
            hi = mn + rng * (row + 1) / H
            line = ""
            for v in sampled:
                if v >= hi:       line += f"[{MG}]█[/]"
                elif v >= lo:     line += f"[green]▄[/]"
                elif row == H//2: line += f"[{DG}]─[/]"
                else:             line += " "
            if   row == H-1: yl = f" [{DG}]{mx:,.0f}[/]"
            elif row == H//2:yl = f" [{DG}]{(mn+rng*0.5):,.0f}[/]"
            elif row == 0:   yl = f" [{DG}]{mn:,.0f}[/]"
            else:            yl = ""
            console.print(f"  {line}{yl}")
        console.print(f"  [{DG}]{'─'*W}[/]")
        console.print(f"  [{DG}]Start: {equity_curve[0]:,.2f}  →  "
                      f"End: {equity_curve[-1]:,.2f}  "
                      f"({'[bright_green]+' if final_balance>=initial_balance else '[bright_red]'}"
                      f"{final_balance-initial_balance:+,.2f}[/])[/]")


# ── Entry point (bisa run langsung: python backtest.py) ───────────────────────

if __name__ == "__main__":
    from engine.connection import connect_mt5

    # ═══════════════════════════ CONFIG ═══════════════════════════
    SYMBOL          = "XAUUSD"
    START_DATE      = "2025-01-01"
    END_DATE        = "2025-12-31"
    INITIAL_BALANCE = 10_000.0
    SL_BUFFER_PIPS  = 5.0      # buffer pips di luar SNR
    RR_RATIO        = 0.0      # 0=SNR natural, 2.0=fixed 1:2 RR
    COOLDOWN_BARS   = 12       # cooldown M5 bars setelah trade (12=1 jam)
    # ══════════════════════════════════════════════════════════════

    console.print("[bold cyan]CHAIN REACTION v4.0 — BACKTEST MODE[/]")
    console.print("[grey62]Sacred Doctrine Engine — Historical Performance Audit[/]\n")

    if not connect_mt5():
        console.print("[red]ERROR: MT5 connection failed[/]")
    else:
        try:
            run_backtest(
                symbol          = SYMBOL,
                start           = START_DATE,
                end             = END_DATE,
                initial_balance = INITIAL_BALANCE,
                sl_buffer_pips  = SL_BUFFER_PIPS,
                rr_ratio        = RR_RATIO,
                cooldown_bars   = COOLDOWN_BARS,
            )
        finally:
            mt5.shutdown()
            console.print("\n[grey62]MT5 disconnected.[/]")
