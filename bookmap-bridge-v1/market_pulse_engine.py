"""
Market Pulse Engine -> replicates Bookmap's OWN "Market Pulse" add-on, which
uses the "Price Change" algorithm (confirmed via Bookmap's own tooltip,
screenshot from Dadang, 2026-08-07):

    "The Price Change algorithm can be used with any instrument. It
    calculates the deviation of the last trade price from the average trade
    price in a given interval. The percentage value shows how close the
    current deviation is to the max deviation that was detected on the
    interval."

Pure price statistics - NO buy/sell aggressor classification at all. This
explains why every earlier version (volume-based aggressor, price-change
window variants) never matched Bookmap's own reading: the real widget never
looks at is_bid/aggressor side, only at how far the last price has strayed
from its own recent average, normalized against the biggest such stray seen
in the window (Training period, default 5min).

is_buyer_taker/size are accepted for call-signature compatibility with
udp_listener.py's on_trade(price, size, is_buyer_taker, timestamp) but are
unused - Price Change doesn't need them.
"""

import time
from collections import deque
from typing import Any, Dict, Optional


class MarketPulseEngine:
    def __init__(self, training_period_sec: float = 300.0):
        self.training_period_sec = training_period_sec
        self.trades = deque()  # (timestamp, price)
        self._last_deviation = 0.0
        self._max_abs_deviation = 0.0

    def on_trade(self, price: float, size: float = None,
                 is_buyer_taker: Optional[bool] = None, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        self.trades.append((timestamp, price))
        cutoff = timestamp - self.training_period_sec
        while self.trades and self.trades[0][0] < cutoff:
            self.trades.popleft()

        avg_price = sum(p for _, p in self.trades) / len(self.trades)
        last_price = self.trades[-1][1]
        self._last_deviation = last_price - avg_price
        self._max_abs_deviation = max(abs(p - avg_price) for _, p in self.trades)

    def get_pulse(self, current_time: float = None) -> Dict[str, Any]:
        if not self.trades or self._max_abs_deviation <= 0:
            return {"price_change_pct": 0.0, "buyer_aggression_pct": 50.0, "seller_aggression_pct": 50.0}

        pct = self._last_deviation / self._max_abs_deviation * 100.0
        pct = max(-100.0, min(100.0, pct))
        # map -100..+100 (Bookmap's own scale) -> 0..100 so cr_master_engine's
        # existing >50/<50 buy/sell-agreement check keeps working unchanged.
        buy_pct = round((pct + 100.0) / 2.0, 1)
        return {
            "price_change_pct": round(pct, 1),
            "buyer_aggression_pct": buy_pct,
            "seller_aggression_pct": round(100.0 - buy_pct, 1),
        }
