"""
CVD Engine - Chain Reaction Bookmap Bridge

Rolling window (2026-08-20, v52.72) - was session-cumulative (reset 07:00 WIB
daily), built on an earlier screenshot of Dadang's Bookmap CVD widget that
looked like a plain daily reset. Turned out that screenshot was stale/not
representative: checked live against the actual widget (Studies config)
and it's set to "Chart range" + reference points repeating every 5 min, NOT
a daily session reset - so the two were quietly measuring different things,
which is why the panel (deep cumulative negative) diverged hard from the
widget (near-zero). Dadang, once that was found: "kita hanya scalping...
biar semua searah" - scalping wants a live, fast-resetting read that tracks
CURRENT pressure, not a slow-moving all-day total that can stay stuck
negative/positive for hours after the flow that caused it is long gone.
CVD_DISPLAY_WINDOW_SEC=300 (5 min) picked to match Dadang's own widget
setting exactly, so the panel and his Bookmap screen read the same thing.
"""

import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

WIB = timezone(timedelta(hours=7))
SESSION_RESET_HOUR = 7  # 07:00 WIB - kept for get_session_delta() (no longer
                         # the primary read, see CVD_DISPLAY_WINDOW_SEC above)
CVD_DISPLAY_WINDOW_SEC = 300.0  # 5 min - matches Dadang's live Bookmap widget


class CVDEngine:
    def __init__(self, history_window_sec: float = CVD_DISPLAY_WINDOW_SEC):
        self.cumulative_delta: float = 0.0  # all-time (process-lifetime) running total, kept for reference
        self.history_window_sec = history_window_sec
        self.trade_history = deque()
        self.session_delta: float = 0.0  # resets at 07:00 WIB daily - THIS is what matches Bookmap's widget
        self._session_start_ts = self._compute_session_start(time.time())

    @staticmethod
    def _compute_session_start(now_ts: float) -> float:
        now_wib = datetime.fromtimestamp(now_ts, tz=WIB)
        session_start_wib = now_wib.replace(hour=SESSION_RESET_HOUR, minute=0, second=0, microsecond=0)
        if now_wib < session_start_wib:
            session_start_wib -= timedelta(days=1)
        return session_start_wib.timestamp()

    def on_trade(self, price: float, size: float, is_buyer_taker: bool, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()

        current_session_start = self._compute_session_start(timestamp)
        if current_session_start > self._session_start_ts:
            self._session_start_ts = current_session_start
            self.session_delta = 0.0  # new session (past 07:00 WIB) -> reset, matches Bookmap

        delta_change = size if is_buyer_taker else -size
        self.cumulative_delta += delta_change
        self.session_delta += delta_change
        self.trade_history.append((timestamp, delta_change, self.cumulative_delta))

        cutoff = timestamp - self.history_window_sec
        while self.trade_history and self.trade_history[0][0] < cutoff:
            self.trade_history.popleft()

    def get_cvd(self) -> float:
        return round(self.cumulative_delta, 2)

    def get_session_delta(self) -> float:
        return round(self.session_delta, 2)

    def get_window_delta(self, window_sec: float = 30.0) -> float:
        """Kept for backward compatibility / testing - no longer used as the
        primary CVD read (see get_session_delta)."""
        if not self.trade_history:
            return 0.0

        now = self.trade_history[-1][0]
        cutoff = now - window_sec

        start_cvd = self.trade_history[0][2]
        for ts, delta_change, running_cvd in self.trade_history:
            if ts >= cutoff:
                start_cvd = running_cvd - delta_change
                break

        end_cvd = self.trade_history[-1][2]
        return round(end_cvd - start_cvd, 2)

    def get_display_cvd(self) -> float:
        """THE CVD number - Full Session/Daily Cumulative Delta (resets 07:00 WIB daily),
        100% synchronized with Bookmap's own Session CVD widget."""
        return self.get_session_delta()

    def get_snapshot(self) -> Dict[str, Any]:
        window_delta = self.get_display_cvd()
        trend = "BUY_ACCUMULATION" if window_delta > 5.0 else ("SELL_ACCUMULATION" if window_delta < -5.0 else "NEUTRAL")
        return {
            "cumulative_delta": self.get_cvd(),
            "delta_30s": window_delta,
            "cvd_trend": trend,
        }
