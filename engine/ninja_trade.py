"""
engine/ninja_trade.py — NINJA TRADE "Curi-Curi" H4 Cycle Analyst
Sepenuhnya independent dari SacredDoctrineAnalyst / DailyDeployAnalyst.
Zero interference dengan engine yang sudah ada.

State machine per H4 candle:
  IDLE      -> tunggu H4 baru
  WAIT_M30  -> H4 open, tunggu M30 bar pertama close (+30 menit)
  WAIT_VR   -> M30 CMP terkunci, hunting VR di M5
  WAIT_CF   -> VR ditemukan, tunggu CF searah M30
  ARMED     -> CF valid, sinyal entry siap (blink di dashboard)
  IN_TRADE  -> posisi open, pantau BE + floating P&L

"Curi-curi" rule:
  BE protection aktif: saat floating profit >= be_pips,
  SL otomatis geser ke entry (risk = 0).
"""

import time
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

from engine.core import TFState

PIP = 0.1   # XAUUSD: 1 pip = $0.10


class NinjaTradeAnalyst:
    """
    Ninja Trade analyst — H4 cycle "curi-curi" strategy.

    Usage (main loop):
        ninja = NinjaTradeAnalyst("XAUUSD", be_pips=5.0)
        ...
        state = ninja.update()          # call every loop tick
        signal = ninja.get_signal()     # returns dict if ARMED, else None
        ninja.mark_trade_open(ticket, entry, sl, tp, direction)  # after order sent
    """

    def __init__(self, symbol: str = "XAUUSD",
                 be_pips: float = 5.0,
                 sl_buffer_pips: float = 5.0):
        self.symbol        = symbol
        self.be_pips       = be_pips
        self.sl_buffer     = sl_buffer_pips

        # ── State machine ──────────────────────────────────────────────────────
        self.state      = "IDLE"
        self.status_msg = "Waiting for new H4 candle..."

        # ── H4 window ──────────────────────────────────────────────────────────
        self.h4_open_time:  pd.Timestamp | None = None
        self.h4_end_time:   pd.Timestamp | None = None
        self.m30_gate_time: pd.Timestamp | None = None   # h4_open + 30min

        # ── M30 data ───────────────────────────────────────────────────────────
        self.m30_direction:  str   = "WAIT"
        self.m30_dir_time:   int   = 0
        self.m30_first_high: float = 0.0    # TP ref untuk BUY
        self.m30_first_low:  float = 0.0    # TP ref untuk SELL

        # ── M5 tracker (fresh each H4 cycle) ──────────────────────────────────
        self._m5_tracker: TFState | None = None
        self._vr_sl_ref:  float = 0.0      # SL reference dari bar VR

        # ── Signal (aktif saat ARMED) ──────────────────────────────────────────
        self.signal: dict | None = None    # {direction,entry,sl,tp,be_pips,sl_pips,tp_pips}

        # ── Live trade tracking ────────────────────────────────────────────────
        self.trade_ticket:   int   | None = None
        self.trade_entry:    float = 0.0
        self.trade_sl:       float = 0.0
        self.trade_tp:       float = 0.0
        self.trade_dir:      str   = ""
        self.trade_be_done:  bool  = False
        self.trade_pips:     float = 0.0

        # ── Session stats ──────────────────────────────────────────────────────
        self.stats = {
            "trades":  0,
            "wins":    0,
            "be":      0,
            "losses":  0,
            "pips":    0.0,
        }

        # ── Cache ──────────────────────────────────────────────────────────────
        self._cache_m30_df:    pd.DataFrame | None = None
        self._cache_m5_df:     pd.DataFrame | None = None
        self._last_fetch_ts:   float = 0.0
        self._FETCH_INTERVAL:  float = 3.0   # re-fetch interval (detik)

        # ── H4 detection rate-limiter ──────────────────────────────────────────
        # Adaptive: lambat (30s) saat masih jauh, cepat (5s) saat mau ganti candle
        self._last_h4_check_ts: float = 0.0

    # ── Data fetching ──────────────────────────────────────────────────────────

    def _fetch(self, timeframe, count: int = 150) -> pd.DataFrame | None:
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def _refresh_data(self):
        """Rate-limited data refresh (max 1x per _FETCH_INTERVAL detik)."""
        now = time.time()
        if now - self._last_fetch_ts < self._FETCH_INTERVAL:
            return
        self._last_fetch_ts = now
        self._cache_m30_df  = self._fetch(mt5.TIMEFRAME_M30, 150)
        self._cache_m5_df   = self._fetch(mt5.TIMEFRAME_M5,  150)

    def _secs_to_next_h4(self) -> float:
        """Hitung detik sampai H4 candle berikutnya berdasarkan h4_open_time."""
        if self.h4_open_time is None:
            return 0.0
        next_h4 = self.h4_open_time + pd.Timedelta(hours=4)
        delta   = (next_h4 - pd.Timestamp.now()).total_seconds()
        return max(0.0, delta)

    def _get_h4_open(self) -> pd.Timestamp | None:
        """
        Deteksi H4 candle terbaru dari MT5 — pakai server time broker,
        bukan hitung manual (aman untuk semua broker / timezone offset).

        Rate-limit adaptive:
          - > 2 menit sebelum batas H4 → cek tiap 30 detik (hemat API)
          - < 2 menit sebelum batas H4 → cek tiap 5 detik  (presisi tinggi)
          - Pertama kali (h4_open_time=None) → langsung fetch tanpa tunggu
        """
        now      = time.time()
        secs_left = self._secs_to_next_h4()

        # Tentukan interval polling berdasarkan kedekatan ke batas H4
        if self.h4_open_time is None:
            interval = 0.0                # pertama kali: langsung fetch
        elif secs_left < 120:
            interval = 5.0               # < 2 menit: polling cepat
        else:
            interval = 30.0              # jauh dari batas: hemat

        if now - self._last_h4_check_ts < interval:
            return self.h4_open_time     # kembalikan cache, skip MT5 call

        self._last_h4_check_ts = now
        df = self._fetch(mt5.TIMEFRAME_H4, 3)
        return df.iloc[-1]["time"] if df is not None and len(df) > 0 else None

    # ── State transitions ──────────────────────────────────────────────────────

    def _reset_cycle(self, h4_open: pd.Timestamp):
        """Reset state untuk H4 cycle baru."""
        self.h4_open_time   = h4_open
        self.h4_end_time    = h4_open + pd.Timedelta(hours=4)
        self.m30_gate_time  = h4_open + pd.Timedelta(minutes=30)
        self.m30_direction  = "WAIT"
        self.m30_dir_time   = 0
        self.m30_first_high = 0.0
        self.m30_first_low  = 0.0
        self._m5_tracker    = None
        self._vr_sl_ref     = 0.0
        self.signal         = None
        self.state          = "WAIT_M30"
        self.status_msg     = f"H4 open {h4_open.strftime('%H:%M')} -> wait M30 +30m"

    def _read_m30_direction(self) -> tuple[str, int]:
        df = self._cache_m30_df
        if df is None or len(df) < 3:
            return "WAIT", 0
        state = TFState("M30")
        n = len(df)
        for i in range(max(0, n - 100), n):
            visible = df.iloc[max(0, i - 99): i + 1].reset_index(drop=True)
            if len(visible) >= 3:
                state.update(visible, "WAIT", 0)
        return state.cmp, state.cmp_change_time

    def _update_m5(self) -> str:
        df = self._cache_m5_df
        if df is None or len(df) < 3:
            return "WAIT"
        if self._m5_tracker is None:
            self._m5_tracker = TFState("M5")
            if self.h4_open_time is not None:
                ctx = df[df["time"] < self.h4_open_time].tail(100).reset_index(drop=True)
                if len(ctx) >= 3:
                    self._m5_tracker.update(ctx, self.m30_direction, self.m30_dir_time)
        n = len(df)
        visible = df.iloc[max(0, n - 100):].reset_index(drop=True)
        return self._m5_tracker.update(visible, self.m30_direction, self.m30_dir_time)

    def _build_signal(self):
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return
        d     = self.m30_direction
        entry = tick.ask if d == "BUY" else tick.bid
        if d == "BUY":
            sl = (self._vr_sl_ref - self.sl_buffer * PIP
                  if self._vr_sl_ref > 0 else entry - 15 * PIP)
            tp = (self.m30_first_high
                  if self.m30_first_high > entry
                  else entry + (entry - sl) * 1.5)
        else:
            sl = (self._vr_sl_ref + self.sl_buffer * PIP
                  if self._vr_sl_ref > 0 else entry + 15 * PIP)
            tp = (self.m30_first_low
                  if 0 < self.m30_first_low < entry
                  else entry - (sl - entry) * 1.5)

        valid = (sl > 0 and tp > 0 and
                 ((d == "BUY"  and tp > entry > sl) or
                  (d == "SELL" and tp < entry < sl)))
        if not valid:
            self.status_msg = "CF fired — signal invalid (SL/TP mismatch)"
            return

        sl_p = abs(entry - sl) / PIP
        tp_p = abs(tp - entry) / PIP
        self.signal = {
            "direction": d, "entry": entry, "sl": sl, "tp": tp,
            "be_pips": self.be_pips,
            "sl_pips": round(sl_p, 1), "tp_pips": round(tp_p, 1),
        }
        self.state      = "ARMED"
        self.status_msg = (f"CF FIRE! {d} ~{entry:.2f} | "
                           f"SL {sl:.2f}({sl_p:.0f}p) TP {tp:.2f}({tp_p:.0f}p)")

    # ── Main update ────────────────────────────────────────────────────────────

    def update(self) -> dict:
        """
        Main update method — panggil setiap loop tick dari main.py.
        Returns state dict untuk dashboard. Thread-safe (no shared state).
        """
        self._refresh_data()

        # Kalau IN_TRADE, hanya pantau posisi
        if self.state == "IN_TRADE":
            self._monitor_trade()
            return self.get_state()

        # ── Deteksi H4 baru ───────────────────────────────────────────────────
        latest_h4 = self._get_h4_open()
        if latest_h4 is not None and latest_h4 != self.h4_open_time:
            self._reset_cycle(latest_h4)
            # Simpan HIGH/LOW bar M30 pertama (yang buka di waktu H4 open)
            if self._cache_m30_df is not None:
                row = self._cache_m30_df[self._cache_m30_df["time"] == latest_h4]
                if len(row) > 0:
                    self.m30_first_high = float(row.iloc[0]["high"])
                    self.m30_first_low  = float(row.iloc[0]["low"])

        # ── H4 window expired ─────────────────────────────────────────────────
        if (self.h4_end_time is not None and
                pd.Timestamp.now() >= self.h4_end_time and
                self.state not in ("IN_TRADE", "IDLE")):
            self.state       = "IDLE"
            self.signal      = None
            self._m5_tracker = None
            self.status_msg  = "H4 window closed -- IDLE"

        # ── State machine ─────────────────────────────────────────────────────
        if self.state == "WAIT_M30":
            if (self.m30_gate_time is not None and
                    pd.Timestamp.now() >= self.m30_gate_time):
                direction, dir_time = self._read_m30_direction()
                if direction != "WAIT":
                    self.m30_direction = direction
                    self.m30_dir_time  = dir_time
                    self.state         = "WAIT_VR"
                    self.status_msg    = f"M30={direction} -- hunting VR on M5..."
                else:
                    self.status_msg = "M30=WAIT, no breakout yet"

        elif self.state == "WAIT_VR":
            s = self._update_m5()
            if s == "VR":
                self._vr_sl_ref = (self._m5_tracker.sup if self.m30_direction == "BUY"
                                   else self._m5_tracker.res)
                self.state      = "WAIT_CF"
                self.status_msg = f"VR found! ref={self._vr_sl_ref:.2f} -- wait CF..."

        elif self.state == "WAIT_CF":
            s = self._update_m5()
            if s == "CF":
                self._build_signal()
            elif s == "VR":
                # VR baru di cycle yang sama
                self._vr_sl_ref = (self._m5_tracker.sup if self.m30_direction == "BUY"
                                   else self._m5_tracker.res)
                self.status_msg = f"New VR ref={self._vr_sl_ref:.2f} -- wait CF..."

        return self.get_state()

    # ── Live trade management ──────────────────────────────────────────────────

    def _monitor_trade(self):
        """Pantau posisi: update floating pips, apply BE kalau sudah waktunya."""
        if self.trade_ticket is None:
            self.state = "IDLE"
            return

        positions = mt5.positions_get(ticket=self.trade_ticket)
        if not positions:
            self._on_close()
            return

        pos  = positions[0]
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return

        is_buy = (pos.type == mt5.POSITION_TYPE_BUY)
        curr   = tick.bid if is_buy else tick.ask
        pips   = ((curr - self.trade_entry) / PIP if is_buy
                  else (self.trade_entry - curr) / PIP)
        self.trade_pips = pips

        # BE protection: saat floating >= be_pips, geser SL ke entry
        if not self.trade_be_done and self.be_pips > 0 and pips >= self.be_pips:
            req = {
                "action":   mt5.TRADE_ACTION_SLTP,
                "symbol":   self.symbol,
                "position": pos.ticket,
                "sl":       pos.price_open,   # BE = entry price
                "tp":       pos.tp,
            }
            result = mt5.order_send(req)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.trade_be_done = True
                self.trade_sl      = self.trade_entry
                self.status_msg    = (f"[BE ACTIVE] SL -> {self.trade_entry:.2f} "
                                      f"(float +{pips:.1f}p)")

    def _on_close(self):
        """Record hasil dan reset setelah posisi ditutup."""
        profit = 0.0
        if self.h4_open_time:
            deals = mt5.history_deals_get(
                self.h4_open_time.to_pydatetime(), datetime.now())
            if deals:
                for d in reversed(deals):
                    if (d.entry == mt5.DEAL_ENTRY_OUT and
                            d.position_id == self.trade_ticket):
                        profit = d.profit
                        break

        self.stats["trades"] += 1
        self.stats["pips"]   += profit
        if profit > 0.5:
            self.stats["wins"]   += 1
        elif self.trade_be_done and abs(profit) < 0.5:
            self.stats["be"]     += 1
        else:
            self.stats["losses"] += 1

        icon = "WIN" if profit > 0.5 else ("BE" if abs(profit) < 0.5 else "SL")
        self.status_msg    = f"Closed [{icon}] {profit:+.2f}$ -- waiting next H4"
        self.trade_ticket  = None
        self.trade_be_done = False
        self.trade_pips    = 0.0
        self.state         = "IDLE"
        self.signal        = None

    def mark_trade_open(self, ticket: int, entry: float,
                        sl: float, tp: float, direction: str):
        """Panggil setelah order berhasil tereksekusi di MT5."""
        self.trade_ticket  = ticket
        self.trade_entry   = entry
        self.trade_sl      = sl
        self.trade_tp      = tp
        self.trade_dir     = direction
        self.trade_be_done = False
        self.trade_pips    = 0.0
        self.state         = "IN_TRADE"
        self.signal        = None
        self.status_msg    = f"IN TRADE #{ticket} @ {entry:.2f} [{direction}]"

    # ── Dashboard interface ────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """Return state dict untuk dashboard rendering."""
        return {
            "state":         self.state,
            "status_msg":    self.status_msg,
            "h4_open":       self.h4_open_time,
            "h4_end":        self.h4_end_time,
            "m30_gate":      self.m30_gate_time,
            "m30_dir":       self.m30_direction,
            "m30_high":      self.m30_first_high,
            "m30_low":       self.m30_first_low,
            "vr_sl_ref":     self._vr_sl_ref,
            "signal":        self.signal,
            "be_pips":       self.be_pips,
            "in_trade":      self.state == "IN_TRADE",
            "trade_entry":   self.trade_entry,
            "trade_sl":      self.trade_sl,
            "trade_tp":      self.trade_tp,
            "trade_dir":     self.trade_dir,
            "trade_be_done": self.trade_be_done,
            "trade_pips":    self.trade_pips,
            "stats":         {**self.stats},
        }

    def get_signal(self) -> dict | None:
        """
        Returns signal dict jika ARMED, else None.
        Compatible dengan executor.execute_strike() interface.
        """
        if self.state != "ARMED" or self.signal is None:
            return None
        return {
            "action":   self.signal["direction"],
            "type":     "NINJA_CF",
            "sl_price": self.signal["sl"],
            "tp_price": self.signal["tp"],
        }
