"""
Absorption Engine - Chain Reaction Layer 2.3 (final module, per Dadang's
5-module architecture: Chain Reaction, Market Pulse, CVD, Absorption, Wall).

Dadang: "harga turun, CVD SELL, tapi harga gak turun... artinya ada yang
menyerap, seller jual, buyer makan semua - itu sering jadi tanda reversal.
Kalau engine bisa baca absorption ini nambah kualitas entry."

Absorption = strong one-directional CVD delta over a SHORT rolling window
WHILE price barely moves in that direction. Big passive size is soaking up
the aggression without letting price follow through - a warning that the
current move is running out of steam, not a hard veto (Dadang's own
example: "BUY WARNING, buyer mulai ter-absorb, kurangi lot" - the entry
still fires, just smaller).

Reuses CVDEngine.get_window_delta() (kept in cvd_engine.py for exactly this -
the main CVD reading is session-cumulative since 07:00 WIB, too broad for
absorption, which needs a short window).

Thresholds (delta_threshold, price_move_threshold) are heuristic defaults -
they need tuning against real GCZ6 volume once live data comes in.
"""

import time
from collections import deque
from typing import Any, Dict


class AbsorptionEngine:
    def __init__(self, window_sec: float = 30.0, delta_threshold: float = 50.0,
                 price_move_threshold: float = 0.5):
        self.window_sec = window_sec
        self.delta_threshold = delta_threshold
        self.price_move_threshold = price_move_threshold
        self._price_history = deque()  # (timestamp, price)

    def on_price(self, price: float, timestamp: float = None):
        if not price:
            return
        if timestamp is None:
            timestamp = time.time()
        self._price_history.append((timestamp, price))
        cutoff = timestamp - self.window_sec
        while self._price_history and self._price_history[0][0] < cutoff:
            self._price_history.popleft()

    def get_absorption(self, cvd_window_delta: float) -> Dict[str, Any]:
        """cvd_window_delta: pass CVDEngine.get_window_delta(self.window_sec)."""
        if len(self._price_history) < 2:
            return {"status": "NONE", "reason": "belum cukup data buat baca absorption"}

        oldest_price = self._price_history[0][1]
        newest_price = self._price_history[-1][1]
        price_move = newest_price - oldest_price
        price_barely_moved = abs(price_move) < self.price_move_threshold

        if cvd_window_delta <= -self.delta_threshold and price_barely_moved:
            return {
                "status": "SELLER_ABSORBED",
                "reason": f"CVD window {cvd_window_delta:+.0f} (seller agresif) tapi harga cuma "
                          f"{price_move:+.2f} - ada yang nyerap seller, potensi reversal ke BUY",
            }
        if cvd_window_delta >= self.delta_threshold and price_barely_moved:
            return {
                "status": "BUYER_ABSORBED",
                "reason": f"CVD window {cvd_window_delta:+.0f} (buyer agresif) tapi harga cuma "
                          f"{price_move:+.2f} - ada yang nyerap buyer, potensi reversal ke SELL",
            }
        return {"status": "NONE", "reason": "gak ada tanda absorption"}
