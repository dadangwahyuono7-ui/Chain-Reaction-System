"""
Macro correlation tracker - reads a SECOND Bookmap instrument (default 6E,
Euro FX futures) purely as a dollar-strength proxy, to answer one question
before a gold entry: "is the macro backdrop with me or against me?"

Dadang, 2026-08-13, after spotting multi-instrument Market Pulse widgets on
YouTube: "bisa dikorelasikan ke dashboard web view py gw dan panel gw...
hanya tambahan informasi aja bro" - explicitly informational. This never
gates, blocks or sizes a trade; the H4->M30->M5 doctrine still decides
direction and the entry. This only surfaces a conflict warning.

WHY 6E AND NOT DXY:
  DXY (DX) is an ICE product - a separate Rithmic data subscription from
  the CME Group package that already covers his COMEX gold. 6E is CME, and
  was confirmed live on his feed (Bookmap showed "Data: Live"). EUR is
  ~57% of the DXY basket, so 6E inverted tracks the dollar closely enough
  for a directional read.

DIRECTION MAPPING:
  6E up   = EUR strong = USD weak   -> tailwind for gold  (SEARAH on BUY)
  6E down = EUR weak   = USD strong -> headwind for gold  (LAWAN on BUY)

DELIBERATELY MINIMAL: no volume profile, no wall detection, no iceberg
tracking for this instrument. Those engines are calibrated for gold's
book (wall_threshold_size=10 lots); 6E's book runs 130-190 per level, so
reusing them would produce garbage. All that's needed here is direction +
whether flow confirms it, which is CVD plus a short price-change window.
"""

import time
from collections import deque
from typing import Any, Dict, Optional

# Bookmap sends every payload tagged with an "alias" (the instrument name as
# shown on its tab, e.g. "6EZ6.CME@RITHMIC"). Matching is done on a substring
# so the contract month can roll (6EZ6 -> 6EH7) without a code change.
DEFAULT_MACRO_MATCH = "6E"

# Window over which price direction and flow are judged. Short enough to
# reflect the current session's push, long enough not to flip on noise.
WINDOW_SEC = 300.0

# Below this move (in the instrument's own price units) the read is NEUTRAL
# rather than UP/DOWN. 6E ticks in 0.00005; 0.0004 is ~8 ticks, which
# filters chop without needing a real volatility model.
FLAT_THRESHOLD = 0.0004


class MacroCorrelation:
    def __init__(self, match: str = DEFAULT_MACRO_MATCH, window_sec: float = WINDOW_SEC):
        self.match = match.upper()
        self.window_sec = window_sec
        self.alias: Optional[str] = None      # the full alias actually seen on the wire
        self.prices = deque()                 # (timestamp, price)
        self.cvd_window = deque()             # (timestamp, signed_size)
        self.last_price = 0.0
        self.last_trade_ts = 0.0

    def matches(self, alias: str) -> bool:
        return bool(alias) and self.match in alias.upper()

    def on_trade(self, alias: str, price: float, size: float, is_buyer_taker: bool,
                 timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        self.alias = alias
        self.last_price = price
        self.last_trade_ts = timestamp

        self.prices.append((timestamp, price))
        self.cvd_window.append((timestamp, size if is_buyer_taker else -size))
        cutoff = timestamp - self.window_sec
        while self.prices and self.prices[0][0] < cutoff:
            self.prices.popleft()
        while self.cvd_window and self.cvd_window[0][0] < cutoff:
            self.cvd_window.popleft()

    def is_live(self, max_age_sec: float = 120.0) -> bool:
        return self.last_trade_ts > 0 and (time.time() - self.last_trade_ts) <= max_age_sec

    def get_state(self, gold_direction: str = "") -> Dict[str, Any]:
        """gold_direction: "BUY"/"SELL"/"" - the direction the gold engine is
        currently working. Used only to phrase the SEARAH/LAWAN verdict."""
        if not self.is_live():
            return {
                "active": False,
                "alias": self.alias or "",
                "reason": "belum ada data (attach addon Bookmap ke tab 6E)",
            }

        first_price = self.prices[0][1] if self.prices else self.last_price
        change = self.last_price - first_price
        cvd = sum(d for _, d in self.cvd_window)

        if change > FLAT_THRESHOLD:
            direction, usd = "UP", "WEAK"
        elif change < -FLAT_THRESHOLD:
            direction, usd = "DOWN", "STRONG"
        else:
            direction, usd = "FLAT", "NEUTRAL"

        # Gold is inversely tied to the dollar, so a rising EUR (weak USD)
        # supports gold longs. Confluence is only claimed when the flow (CVD)
        # agrees with the price move - price up on negative delta is exactly
        # the kind of unbacked move that fails.
        flow_confirms = (change > 0 and cvd > 0) or (change < 0 and cvd < 0)

        if direction == "FLAT":
            verdict = "NEUTRAL"
        elif not gold_direction or gold_direction not in ("BUY", "SELL"):
            verdict = "GOLD BULLISH" if direction == "UP" else "GOLD BEARISH"
        elif (gold_direction == "BUY" and direction == "UP") or \
             (gold_direction == "SELL" and direction == "DOWN"):
            verdict = "SEARAH"
        else:
            verdict = "LAWAN"

        return {
            "active": True,
            "alias": self.alias or "",
            "price": round(self.last_price, 5),
            "change": round(change, 5),
            "direction": direction,        # UP / DOWN / FLAT  (of 6E itself)
            "usd": usd,                    # WEAK / STRONG / NEUTRAL
            "cvd": round(cvd, 1),
            "flow_confirms": flow_confirms,
            "verdict": verdict,            # SEARAH / LAWAN / NEUTRAL
            "age_sec": round(time.time() - self.last_trade_ts, 1),
        }
