"""
Market Data Engine - Chain Reaction Bookmap Bridge
Location: C:/Bookmap/Python/market_data_engine.py
"""

from typing import Dict, Optional, Tuple, Any

class MarketDataEngine:
    def __init__(self):
        self.last_price: float = 0.0
        self.bid_price: float = 0.0
        self.bid_size: float = 0.0
        self.ask_price: float = 0.0
        self.ask_size: float = 0.0
        self.bids_depth: Dict[float, float] = {}
        self.asks_depth: Dict[float, float] = {}
        self.wall_threshold_size: float = 10.0   # 2026-08-10: Dadang minta range 10-1000 lot ditampilin di MT5 (garis makin tebal/terang makin gede) - CATATAN: ini threshold yang SAMA dipake WALL_ENTRY signal di sistem trading, jadi nurunin ini juga bikin WALL_ENTRY lebih sensitif/lebih sering fire

    def on_trade(self, price: float, size: float):
        if price > 0:
            self.last_price = price

    def on_depth(self, is_bid: bool, price: float, size: float):
        target_map = self.bids_depth if is_bid else self.asks_depth
        if size <= 0:
            target_map.pop(price, None)
        else:
            target_map[price] = size

    def get_wall_ladder(self, is_bid: bool, top_n: int = 5) -> list:
        """All significant walls on one side, sorted nearest-to-price first.
        Used to advance to the NEXT wall once the current reference wall is
        broken through ('jebol') - see WallLadderTracker in cr_master_engine.py."""
        depth = self.bids_depth if is_bid else self.asks_depth
        walls = [(p, s) for p, s in depth.items() if s >= self.wall_threshold_size]
        if is_bid:
            walls = [w for w in walls if self.last_price == 0 or w[0] <= self.last_price]
            walls.sort(key=lambda x: x[0], reverse=True)  # nearest below price first
        else:
            walls = [w for w in walls if self.last_price == 0 or w[0] >= self.last_price]
            walls.sort(key=lambda x: x[0])  # nearest above price first
        return walls[:top_n]

    def get_nearest_walls(self) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        nearest_bid_wall = None
        nearest_ask_wall = None
        significant_bids = [
            (p, s) for p, s in self.bids_depth.items()
            if s >= self.wall_threshold_size and (self.last_price == 0 or p <= self.last_price)
        ]
        if significant_bids:
            significant_bids.sort(key=lambda x: x[0], reverse=True)
            nearest_bid_wall = significant_bids[0]

        significant_asks = [
            (p, s) for p, s in self.asks_depth.items()
            if s >= self.wall_threshold_size and (self.last_price == 0 or p >= self.last_price)
        ]
        if significant_asks:
            significant_asks.sort(key=lambda x: x[0])
            nearest_ask_wall = significant_asks[0]

        return nearest_bid_wall, nearest_ask_wall

    def get_all_significant_walls(self, is_bid: bool, min_size: float = 10.0) -> list:
        """Returns ALL significant walls in the entire order book (regardless of distance from price)."""
        depth = self.bids_depth if is_bid else self.asks_depth
        walls = [(round(p, 2), s) for p, s in depth.items() if s >= min_size]
        if is_bid:
            walls.sort(key=lambda x: x[0], reverse=True)
        else:
            walls.sort(key=lambda x: x[0])
        return walls

    def get_walls_in_range(self, lo: float, hi: float, is_bid: Optional[bool] = None) -> list:
        """Returns all resting walls currently inside [lo, hi]."""
        results = []
        if is_bid is None or is_bid is True:
            for p, s in self.bids_depth.items():
                if s >= self.wall_threshold_size and lo <= p <= hi:
                    results.append((round(p, 2), s, "BID"))
        if is_bid is None or is_bid is False:
            for p, s in self.asks_depth.items():
                if s >= self.wall_threshold_size and lo <= p <= hi:
                    results.append((round(p, 2), s, "ASK"))
        results.sort(key=lambda x: x[0])
        return results

    def get_snapshot(self) -> Dict[str, Any]:
        bid_wall, ask_wall = self.get_nearest_walls()
        return {
            "last_price": self.last_price,
            "nearest_bid_wall": bid_wall,
            "nearest_ask_wall": ask_wall
        }
