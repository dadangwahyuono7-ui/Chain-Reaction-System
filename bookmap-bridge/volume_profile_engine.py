"""
Volume Profile Engine - Chain Reaction Bookmap Bridge

Dadang (2026-08-10): "Bookmap bisa kasih kita 3 data utama: Volume, Buy/Sell,
Order book... dari 3 data itu kita bisa hitung apakah market trending naik/
turun/sideways... rekam volume + buy/sell + depth mentah dulu, baru nanti
tentuin rumus sideways paling masuk akal." This engine is deliberately just
the RAW RECORDER for the first data source (volume-at-price) - no trend/
sideways detector built on top yet, per Dadang's explicit instruction to
record first.

Tracks session-cumulative (resets 07:00 WIB, same convention as cvd_engine.py)
volume-at-price so we can derive:
  - POC (Point of Control): the price level with the most TOTAL traded
    volume this session - classic volume-profile concept, distinct from CVD
    (which is buy-sell DELTA, not raw traded volume) and from wall_ladder
    (which is resting ORDER BOOK size, not volume that actually traded).
  - Volume Ratio: session buy volume vs sell volume, as a % - a session-wide
    complement to market_pulse_engine.py's short-window buyer_aggression_pct.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

WIB = timezone(timedelta(hours=7))
SESSION_RESET_HOUR = 7  # 07:00 WIB, same convention as CVDEngine
PRICE_BUCKET = 0.10      # GCZ6 tick size


class VolumeProfileEngine:
    def __init__(self):
        self.buy_vol_at_price: Dict[float, float] = {}
        self.sell_vol_at_price: Dict[float, float] = {}
        self.session_buy_volume: float = 0.0
        self.session_sell_volume: float = 0.0
        self._session_start_ts = self._compute_session_start(time.time())

    @staticmethod
    def _compute_session_start(now_ts: float) -> float:
        now_wib = datetime.fromtimestamp(now_ts, tz=WIB)
        session_start_wib = now_wib.replace(hour=SESSION_RESET_HOUR, minute=0, second=0, microsecond=0)
        if now_wib < session_start_wib:
            session_start_wib -= timedelta(days=1)
        return session_start_wib.timestamp()

    def _maybe_reset_session(self, timestamp: float):
        current_session_start = self._compute_session_start(timestamp)
        if current_session_start > self._session_start_ts:
            self._session_start_ts = current_session_start
            self.buy_vol_at_price.clear()
            self.sell_vol_at_price.clear()
            self.session_buy_volume = 0.0
            self.session_sell_volume = 0.0

    def on_trade(self, price: float, size: float, is_buyer_taker: Optional[bool], timestamp: float = None):
        if is_buyer_taker is None or size <= 0:
            return
        if timestamp is None:
            timestamp = time.time()
        self._maybe_reset_session(timestamp)

        bucket = round(round(price / PRICE_BUCKET) * PRICE_BUCKET, 2)
        if is_buyer_taker:
            self.buy_vol_at_price[bucket] = self.buy_vol_at_price.get(bucket, 0.0) + size
            self.session_buy_volume += size
        else:
            self.sell_vol_at_price[bucket] = self.sell_vol_at_price.get(bucket, 0.0) + size
            self.session_sell_volume += size

    def get_poc(self) -> Optional[Tuple[float, float]]:
        """Point of Control - price bucket with the most TOTAL (buy+sell)
        traded volume this session. None if no trades yet."""
        prices = set(self.buy_vol_at_price) | set(self.sell_vol_at_price)
        if not prices:
            return None
        best_price, best_vol = None, -1.0
        for p in prices:
            vol = self.buy_vol_at_price.get(p, 0.0) + self.sell_vol_at_price.get(p, 0.0)
            if vol > best_vol:
                best_price, best_vol = p, vol
        return (best_price, round(best_vol, 1))

    def get_value_area(self, value_area_pct: float = 0.70) -> Optional[Tuple[float, float]]:
        """VAH/VAL (Value Area High/Low) - the price RANGE containing
        `value_area_pct` (classic default 70%) of the session's total traded
        volume, expanding outward from POC. Classic market-profile algorithm:
        starting at the POC bucket, repeatedly add whichever neighbor (one
        bucket above the current range vs one below) has more volume, until
        the accumulated volume crosses the target. Turns POC from a single
        line into a genuine support/resistance ZONE. Returns (VAL, VAH) or
        None if there's no data yet."""
        poc = self.get_poc()
        if poc is None:
            return None
        poc_price = poc[0]

        prices = sorted(set(self.buy_vol_at_price) | set(self.sell_vol_at_price))
        if not prices:
            return None
        vol_at = {p: self.buy_vol_at_price.get(p, 0.0) + self.sell_vol_at_price.get(p, 0.0) for p in prices}
        total = sum(vol_at.values())
        if total <= 0:
            return None

        idx = prices.index(poc_price)
        lo = hi = idx
        accumulated = vol_at[poc_price]
        target = total * value_area_pct

        while accumulated < target and (lo > 0 or hi < len(prices) - 1):
            vol_below = vol_at[prices[lo - 1]] if lo > 0 else -1.0
            vol_above = vol_at[prices[hi + 1]] if hi < len(prices) - 1 else -1.0
            if vol_above >= vol_below:
                hi += 1
                accumulated += vol_at[prices[hi]]
            else:
                lo -= 1
                accumulated += vol_at[prices[lo]]

        return (round(prices[lo], 2), round(prices[hi], 2))

    def get_snapshot(self) -> Dict[str, Any]:
        total = self.session_buy_volume + self.session_sell_volume
        buy_pct = (self.session_buy_volume / total * 100.0) if total > 0 else 50.0
        poc = self.get_poc()
        va = self.get_value_area()
        return {
            "session_buy_volume": round(self.session_buy_volume, 1),
            "session_sell_volume": round(self.session_sell_volume, 1),
            "session_total_volume": round(total, 1),
            "volume_ratio_buy_pct": round(buy_pct, 1),
            "poc_price": poc[0] if poc else 0.0,
            "poc_volume": poc[1] if poc else 0.0,
            "val": va[0] if va else 0.0,
            "vah": va[1] if va else 0.0,
        }
