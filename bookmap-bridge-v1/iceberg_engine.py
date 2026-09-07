"""
Iceberg / Refill Detection Engine - Chain Reaction Bookmap Bridge

Dadang (2026-08-10): "tambah hal lebih gila." Detects HIDDEN large orders -
a price level where far more volume has TRADED through it recently than its
currently-DISPLAYED resting size would suggest, while the level keeps
reappearing/refilling instead of vanishing once consumed.

This is genuinely different information from WallLadderTracker (wall_ladder
in cr_master_engine.py): a wall is a big size sitting VISIBLY still. An
iceberg deliberately shows a SMALL size on purpose (so it never looks like a
wall) and refills itself every time it gets hit - only the ratio of traded
volume vs displayed size, tracked over time, reveals it.

INFORMATIONAL ONLY for now (not wired into entry sizing) - same "observe
live before gating anything" caution already applied to every other new
Bookmap signal added this session, and explicitly warranted here: this is
the newest, least-proven signal of the bunch.
"""

import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

REFILL_RATIO_THRESHOLD = 3.0    # traded volume at a price >= 3x its current displayed size -> suspicious
MIN_DISPLAYED_SIZE = 2.0        # ignore near-zero noise levels
MIN_TRADED_VOLUME = 15.0        # need a meaningful amount of volume to call it, not 1-2 lots
REFRESH_COUNT_THRESHOLD = 3     # level must have survived at least this many depth updates while non-empty
TRADE_WINDOW_SEC = 120.0        # same window convention as footprint_engine.py
PRICE_TOLERANCE = 0.05          # near-EXACT tick match - NOT a wide zone like the wall-entry footprint check,
                                 # an iceberg is about ONE specific price level, not a zone around it


class IcebergEngine:
    def __init__(self):
        self._refresh_count: Dict[float, int] = {}      # price(rounded) -> how many on_depth updates it's survived
        self._last_seen_size: Dict[float, float] = {}
        self._trades: Deque[Tuple[float, float, float]] = deque()   # (timestamp, price, size)

    def on_depth(self, is_bid: bool, price: float, size: float):
        key = round(price, 2)
        if size <= 0:
            self._refresh_count.pop(key, None)
            self._last_seen_size.pop(key, None)
            return
        prev = self._last_seen_size.get(key)
        self._last_seen_size[key] = size
        if prev is not None:
            self._refresh_count[key] = self._refresh_count.get(key, 0) + 1
        else:
            self._refresh_count.setdefault(key, 0)

    def on_trade(self, price: float, size: float, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        self._trades.append((timestamp, price, size))
        cutoff = timestamp - TRADE_WINDOW_SEC
        while self._trades and self._trades[0][0] < cutoff:
            self._trades.popleft()

    def _traded_volume_at(self, target_price: float) -> float:
        total = 0.0
        for _, price, size in self._trades:
            if abs(price - target_price) <= PRICE_TOLERANCE:
                total += size
        return total

    def detect(self, market_data, is_bid: bool, top_n: int = 30) -> Optional[Dict[str, Any]]:
        """Strongest iceberg candidate (highest traded/displayed ratio) on
        one side of the book, or None if nothing qualifies."""
        depth = market_data.bids_depth if is_bid else market_data.asks_depth
        items = sorted(depth.items(), key=lambda x: x[0], reverse=is_bid)[:top_n]
        best = None
        best_ratio = 0.0
        for price, size in items:
            if size < MIN_DISPLAYED_SIZE:
                continue
            key = round(price, 2)
            if self._refresh_count.get(key, 0) < REFRESH_COUNT_THRESHOLD:
                continue
            traded = self._traded_volume_at(price)
            if traded < MIN_TRADED_VOLUME:
                continue
            ratio = traded / size
            if ratio >= REFILL_RATIO_THRESHOLD and ratio > best_ratio:
                best_ratio = ratio
                best = {
                    "price": round(price, 2),
                    "side": "BID" if is_bid else "ASK",
                    "displayed_size": round(size, 1),
                    "traded_volume": round(traded, 1),
                    "ratio": round(ratio, 2),
                    "refresh_count": self._refresh_count.get(key, 0),
                }
        return best

    def get_snapshot(self, market_data) -> Dict[str, Any]:
        return {
            "bid_iceberg": self.detect(market_data, is_bid=True),
            "ask_iceberg": self.detect(market_data, is_bid=False),
        }
