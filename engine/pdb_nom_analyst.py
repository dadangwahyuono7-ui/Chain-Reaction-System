"""
engine/pdb_nom_analyst.py — PDB + NOM Live Analysts

PDH/PDL Breakout (PDB):   Backtest 2020-2026: +21,019 pips, PF 2.33, WR 36%
NY Open Momentum  (NOM):  Backtest 2020-2026: +2,434  pips, PF 2.22, WR 34.7%
Combined Sharpe = 1.24, max DD = 20.9%

Usage (main loop):
    pdb = PDBAnalyst("XAUUSD")
    nom = NOMAnalyst("XAUUSD")
    ...
    pdb.update(analyst)   # call every tick
    nom.update(analyst)
    pdb_sig = pdb.get_signal()   # None or dict with action/sl/tp/comment
    nom_sig = nom.get_signal()
    pdb.mark_trade_open()        # call after executor.execute_strike() success
    nom.mark_trade_open()
"""

import MetaTrader5 as mt5
import pytz
from datetime import datetime, date


PIP        = 0.1   # XAUUSD: 1 pip = $0.10
PDB_SL_BUF = 5.0   # pips buffer below PDH (BUY) or above PDL (SELL)
PDB_RR     = 3.0   # validated RR — backtest peak at 3.0
NOM_SL_BUF = 3.0   # pips buffer outside the 2-bar high/low for SL
NOM_RR     = 2.5   # validated RR
MIN_PDR    = 20.0  # min prev-day range pips — skip thin / holiday days


class PDBAnalyst:
    """
    PDH/PDL Breakout: entry when M30 bar closes through prev-day high/low,
    confirmed by H4 CMP direction.

    Fire in ANY session (Asian PF=2.64 is the best window in backtest).
    Calls to execute_strike() must pass bypass_session=True and bypass_snr=True
    because entry IS the PDH/PDL level.
    Max 2 trades per calendar day (UTC).
    """

    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self._pdh: float = 0.0
        self._pdl: float = 0.0
        self._pdh_date: date = None   # cache date — refresh once per day only
        self._signal: dict = None
        self._trades_today: int = 0
        self._last_date: date = None
        self._last_bar_time: datetime = None

    # ── public API ────────────────────────────────────────────────────────────

    def update(self, analyst) -> None:
        """Call every loop tick. Signal stored internally, retrieve via get_signal()."""
        self._signal = None

        # Reset daily trade counter at UTC midnight
        today_utc = datetime.now(pytz.utc).date()
        if self._last_date != today_utc:
            self._trades_today = 0
            self._last_date = today_utc

        if self._trades_today >= 2:
            return

        # Refresh PDH/PDL (cached — one MT5 call per day)
        self._refresh_pdh_pdl()
        if self._pdh <= 0 or self._pdl <= 0:
            return
        if (self._pdh - self._pdl) / PIP < MIN_PDR:
            return  # thin day, unreliable levels

        # Get last completed M30 bar
        bars = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M30, 1, 1)
        if bars is None or len(bars) == 0:
            return

        bar = bars[0]
        bar_dt = datetime.fromtimestamp(bar["time"], tz=pytz.utc)
        if bar_dt == self._last_bar_time:
            return  # already evaluated this bar

        close = bar["close"]
        h4_cmp = analyst.states["H4"].cmp

        sig = None
        level = 0.0
        if close > self._pdh and h4_cmp == "BUY":
            sig = "BUY"
            level = self._pdh
        elif close < self._pdl and h4_cmp == "SELL":
            sig = "SELL"
            level = self._pdl

        self._last_bar_time = bar_dt

        if sig is None:
            return

        if sig == "BUY":
            sl = level - PDB_SL_BUF * PIP
            tp = close + (close - sl) * PDB_RR
        else:
            sl = level + PDB_SL_BUF * PIP
            tp = close - (sl - close) * PDB_RR

        self._signal = {
            "action":  sig,
            "sl":      round(sl, 2),
            "tp":      round(tp, 2),
            "level":   round(level, 2),
            "comment": f"PDB_{sig}_{level:.2f}",
        }

    def get_signal(self):
        return self._signal

    def mark_trade_open(self) -> None:
        self._trades_today += 1

    def status_text(self) -> str:
        if self._pdh <= 0:
            return "PDB: Waiting for D1 data"
        if self._trades_today >= 2:
            return f"PDB: Max trades reached today (2/2)"
        if self._signal:
            s = self._signal
            return f"PDB: {s['action']} fired @ level {s['level']:.2f} | sl={s['sl']:.2f} tp={s['tp']:.2f}"
        return (f"PDB: Watching PDH={self._pdh:.2f} PDL={self._pdl:.2f} "
                f"| Trades={self._trades_today}/2")

    # ── private ───────────────────────────────────────────────────────────────

    def _refresh_pdh_pdl(self) -> None:
        today = datetime.now(pytz.utc).date()
        if self._pdh_date == today and self._pdh > 0:
            return  # already cached for today
        bars = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_D1, 1, 1)
        if bars is None or len(bars) == 0:
            return
        self._pdh = bars[0]["high"]
        self._pdl = bars[0]["low"]
        self._pdh_date = today


class NOMAnalyst:
    """
    NY Open Momentum: fire when first 2 M30 bars of NY session (13:00 & 13:30 UTC)
    are both in the same direction, confirmed by H4 CMP.

    SELL bias (backtest: SELL PF=2.47 vs BUY PF=2.05).
    Signal window: 14:00-14:29 UTC. Max 1 trade per calendar day.
    """

    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self._signal: dict = None
        self._traded_today: bool = False
        self._last_date: date = None

    # ── public API ────────────────────────────────────────────────────────────

    def update(self, analyst) -> None:
        """Call every loop tick. Signal valid only in the 14:00-14:29 UTC window."""
        self._signal = None

        now_utc = datetime.now(pytz.utc)
        today_utc = now_utc.date()

        if self._last_date != today_utc:
            self._traded_today = False
            self._last_date = today_utc

        if self._traded_today:
            return

        # Signal window: 14:00-14:29 UTC (after both NY open bars have closed)
        if not (now_utc.hour == 14 and now_utc.minute < 30):
            return

        # Last 2 completed M30 bars (oldest first in the returned array)
        bars = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M30, 1, 2)
        if bars is None or len(bars) < 2:
            return

        b1, b2 = bars[0], bars[1]
        b1_dt = datetime.fromtimestamp(b1["time"], tz=pytz.utc)
        b2_dt = datetime.fromtimestamp(b2["time"], tz=pytz.utc)

        # Verify these are the 13:00 and 13:30 UTC bars
        if b1_dt.hour != 13 or b1_dt.minute != 0:
            return
        if b2_dt.hour != 13 or b2_dt.minute != 30:
            return

        b1_bull = b1["close"] > b1["open"]
        b2_bull = b2["close"] > b2["open"]
        b1_bear = b1["close"] < b1["open"]
        b2_bear = b2["close"] < b2["open"]

        h4_cmp = analyst.states["H4"].cmp

        if b1_bear and b2_bear and h4_cmp == "SELL":
            sig = "SELL"
            sl = round(max(b1["high"], b2["high"]) + NOM_SL_BUF * PIP, 2)
            ref_entry = b2["close"]
            tp = round(ref_entry - (sl - ref_entry) * NOM_RR, 2)
        elif b1_bull and b2_bull and h4_cmp == "BUY":
            sig = "BUY"
            sl = round(min(b1["low"], b2["low"]) - NOM_SL_BUF * PIP, 2)
            ref_entry = b2["close"]
            tp = round(ref_entry + (ref_entry - sl) * NOM_RR, 2)
        else:
            return

        self._signal = {
            "action":  sig,
            "sl":      sl,
            "tp":      tp,
            "b1_open": b1_dt.strftime("%H:%M"),
            "comment": f"NOM_{sig}_NY",
        }

    def get_signal(self):
        return self._signal

    def mark_trade_open(self) -> None:
        self._traded_today = True

    def status_text(self) -> str:
        now = datetime.now(pytz.utc)
        if self._traded_today:
            return "NOM: Done for today"
        if self._signal:
            s = self._signal
            return f"NOM: {s['action']} armed | sl={s['sl']:.2f} tp={s['tp']:.2f}"
        if now.hour == 14 and now.minute < 30:
            return "NOM: Window open — no setup"
        return f"NOM: Waiting NY open (14:00 UTC) | UTC {now.hour:02d}:{now.minute:02d}"
