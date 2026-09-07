"""
Footprint Delta Engine - PER-PRICE buy vs sell volume, used specifically to
confirm WALL-based entries (cr_master_engine.py's get_wall_entry_signal()).

Dadang: "jika data market pulse cvd delta mendukung dan footprint delta plus
juga mendukung kita entri" - a THIRD confirmation, distinct from both:
  - Market Pulse (Price Change algorithm - overall price deviation, TIME-based)
  - CVD (session-cumulative aggressor delta, TIME-based)
Footprint Delta here is PRICE-based: buy vs sell volume that actually traded
AT a specific price level (the wall), within a rolling window - answers "is
the aggression happening RIGHT AT this wall favoring the bounce/reject, or
is it actually against it?" This reopens the earlier "5 final modules" lock
as a 6th, specifically scoped to wall-entry confirmation - NOT a return to
the earlier (rejected) per-BAR Footprint Delta market_pulse_engine.py used
to implement; this one is keyed to a specific price, not a time bucket.
"""

import time
from collections import deque
from typing import Any, Dict, Optional


class FootprintEngine:
    def __init__(self, window_sec: float = 120.0, price_tolerance: float = 1.0):
        self.window_sec = window_sec
        self.price_tolerance = price_tolerance
        self.trades = deque()  # (timestamp, price, size, is_buyer_taker)

    def on_trade(self, price: float, size: float, is_buyer_taker: Optional[bool], timestamp: float = None):
        if is_buyer_taker is None:
            return
        if timestamp is None:
            timestamp = time.time()
        self.trades.append((timestamp, price, size, is_buyer_taker))
        cutoff = timestamp - self.window_sec
        while self.trades and self.trades[0][0] < cutoff:
            self.trades.popleft()

    def get_footprint_in_window(self, seconds: float, now: float = None) -> Dict[str, Any]:
        """TIME-scoped variant (all prices, last N seconds) - the ORIGINAL
        per-price version above answers "who's aggressing AT this wall";
        this one answers "who's aggressing RIGHT NOW, at any price" -
        Dadang, 2026-08-25: "footprint itu m1 aja dari bookmap nya bro
        supaya gw tau dari m1 bahwa seller atau buyer mulain masuk" - an
        early-warning read using the same trade log, explicitly informational
        only (not a gate, not a replacement for the per-price version above).
        window_sec=120 default already covers a 60s (M1) lookback with room
        to spare, so no change needed to how long trades are retained."""
        if now is None:
            now = time.time()
        cutoff = now - seconds
        buy_vol = 0.0
        sell_vol = 0.0
        for ts, _price, size, is_buyer_taker in self.trades:
            if ts < cutoff:
                continue
            if is_buyer_taker:
                buy_vol += size
            else:
                sell_vol += size

        total = buy_vol + sell_vol
        if total <= 0:
            return {"status": "NEUTRAL", "buy_volume": 0.0, "sell_volume": 0.0, "buy_pct": 50.0}

        buy_pct = buy_vol / total * 100.0
        if buy_pct >= 60.0:
            status = "BUY_DOMINANT"
        elif buy_pct <= 40.0:
            status = "SELL_DOMINANT"
        else:
            status = "NEUTRAL"
        return {
            "status": status,
            "buy_volume": round(buy_vol, 1),
            "sell_volume": round(sell_vol, 1),
            "buy_pct": round(buy_pct, 1),
        }

    def get_footprint_at_price(self, target_price: float) -> Dict[str, Any]:
        buy_vol = 0.0
        sell_vol = 0.0
        for _, price, size, is_buyer_taker in self.trades:
            if abs(price - target_price) <= self.price_tolerance:
                if is_buyer_taker:
                    buy_vol += size
                else:
                    sell_vol += size

        total = buy_vol + sell_vol
        if total <= 0:
            return {"status": "NEUTRAL", "buy_volume": 0.0, "sell_volume": 0.0, "buy_pct": 50.0}

        buy_pct = buy_vol / total * 100.0
        if buy_pct >= 60.0:
            status = "BUY_DOMINANT"
        elif buy_pct <= 40.0:
            status = "SELL_DOMINANT"
        else:
            status = "NEUTRAL"
        return {
            "status": status,
            "buy_volume": round(buy_vol, 1),
            "sell_volume": round(sell_vol, 1),
            "buy_pct": round(buy_pct, 1),
        }
