"""
Smart Supply & Demand Zone Engine (V2 - Bookmap microstructure layer).

Dadang, 2026-08-25: "kita ada yang kelewat bro dalam engine kita selama
ini kita lupa nentuin zona SND bro... data dari bookmap MT5 SNR chain
kita tapi zone SND dari bookmap." The existing Chain Reaction doctrine
(CMP/VR/CF, minor SNR) stays exactly as-is and untouched - this is a
SEPARATE location/context layer, sourced from Bookmap order-flow, that
never gates or replaces a Chain Signal.

WALL != ZONE (Dadang's own framing): a wall is one raw resting-liquidity
price point - individual walls keep being tracked exactly as before,
nothing about wall detection itself changes. A ZONE is 2+ walls
clustered within CLUSTER_USD of each other, confirmed over time by
absorption + persistence + reaction - a location worth respecting, not
just a liquidity number.

Audited before writing this (per Dadang's explicit "JANGAN LANGSUNG
CODING... audit repository dulu"): the live pipeline (udp_listener.py's
CRDecisionRecommendationEngine, cr_master_engine.py) ALREADY runs
WallLadderTracker (persistent wall memory with first_seen/last_seen/
max_size + TTL pruning) and AbsorptionEngine (CVD-window-vs-price-move
absorption detection) every cycle - this module does NOT reimplement
those, it consumes their already-computed live output
(result["wall_ladder"], result["absorption"]) each cycle and adds the
one thing that's genuinely missing: turning wall CLUSTERS into
persistent ZONE objects with their own lifecycle and score.

Scoring (0-100) is explicitly NOT locked - Dadang: "jangan mengunci
formula terlalu cepat... usulkan formula terbaik berdasarkan data yang
benar-benar tersedia." The weights below are a first pass built only
from data that's actually flowing (wall density/size, zone age,
absorption hits while price is inside the zone, retest survival) -
recalibrate once real GCZ6 session data shows whether these ranges read
sensibly, same "record first, tune later" discipline as
absorption_engine.py's own threshold comment.

V2 ONLY - lives in bookmap-bridge-v2/, isolated from the live
bookmap-bridge/ pipeline. Nothing in the V1 folder imports this.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

CLUSTER_USD = 3.0                  # same radius as the EA's InpWallZoneClusterUsd (ClusterAndDrawWallZones()) - keeps Python and MT5 agreeing on what counts as a cluster
MIN_WALLS_FOR_ZONE = 2             # WALL != ZONE - need at least 2 clustered walls to become a zone candidate
MAX_ZONE_WIDTH_USD = 8.0           # 2026-08-26: Dadang, live screenshot - "ada demand di atas suplay" (zones had grown so wide over the session they overlapped the OPPOSITE side entirely). _match_or_create()'s widen-never-shrink policy has no natural ceiling on its own - capped here so a zone keeps absorbing genuinely nearby new walls but stops merging once it would grow unreasonably wide; a cluster that would blow the cap becomes its own separate zone instead
ZONE_TTL_SEC = 24 * 3600           # a zone not seen live for a full day is dropped
BROKEN_INVALIDATE_SEC = 3600       # a zone that's been BROKEN for an hour straight (never reclaimed) is dropped
BREAK_BUFFER_USD = CLUSTER_USD * 0.5   # price must clear the zone by more than "just barely" before counting as broken - filters noise at the exact edge


class SupplyDemandZone:
    """One persistent zone. Identity = zone_id, assigned once at creation
    and stable across updates even as the exact price range drifts a
    little (the walls inside it can shift tick to tick without the zone
    itself being treated as "new")."""

    __slots__ = (
        "zone_id", "side", "lo", "hi", "wall_count", "total_lot",
        "created_at", "last_seen", "status", "retest_count",
        "absorption_hits", "score",
    )

    def __init__(self, zone_id: int, side: str, lo: float, hi: float,
                 wall_count: int, total_lot: float, now: float):
        self.zone_id = zone_id
        self.side = side              # "SUPPLY" (ask-side) or "DEMAND" (bid-side)
        self.lo = lo
        self.hi = hi
        self.wall_count = wall_count
        self.total_lot = total_lot
        self.created_at = now
        self.last_seen = now
        self.status = "FRESH"         # FRESH -> ACTIVE -> TESTED -> WEAKENED -> BROKEN -> INVALID
        self.retest_count = 0
        self.absorption_hits = 0
        self.score = 0.0

    def contains(self, price: float) -> bool:
        return self.lo <= price <= self.hi

    def overlaps(self, lo: float, hi: float) -> bool:
        return not (hi < self.lo or lo > self.hi)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "side": self.side,
            "lo": round(self.lo, 2),
            "hi": round(self.hi, 2),
            "wall_count": self.wall_count,
            "total_lot": round(self.total_lot, 1),
            "status": self.status,
            "retest_count": self.retest_count,
            "absorption_hits": self.absorption_hits,
            "score": round(self.score),
            "age_sec": round(now_() - self.created_at),
        }


def now_() -> float:
    return time.time()


class ZoneEngine:
    """Owns the persistent zone list for one side-pair (bid=DEMAND,
    ask=SUPPLY). Call update() once per udp_listener.py cycle with the
    CURRENT wall ladders (already computed by WallLadderTracker) + price
    + the CURRENT absorption status (already computed by AbsorptionEngine)
    + CVD window delta (already available via cvd_engine.get_window_delta()).
    This engine does not fetch any of that itself - keeps it a pure
    consumer, easy to test/replay independent of the live Bookmap feed."""

    def __init__(self):
        self._zones: Dict[int, SupplyDemandZone] = {}
        self._next_id = 1
        self._prev_price: Optional[float] = None

    def _cluster(self, walls: List[Tuple[float, float]]) -> List[Tuple[float, float, int, float]]:
        """walls = [(price, size), ...] for ONE side. Returns
        [(lo, hi, wall_count, total_lot), ...] for clusters of >=
        MIN_WALLS_FOR_ZONE - same total-span-bounded greedy algorithm as
        the EA's ClusterAndDrawWallZones() (v52.31, fixed in v52.33 to
        bound the TOTAL span from the first wall rather than chaining
        consecutive small hops into an unbounded staircase) - ported here
        so Python and MT5 would classify the same walls into the same
        clusters if run side by side."""
        pts = sorted((p, s) for p, s in walls if p > 0 and s > 0)
        clusters = []
        i, n = 0, len(pts)
        while i < n:
            j = i
            while j + 1 < n and (pts[j + 1][0] - pts[i][0]) <= CLUSTER_USD:
                j += 1
            if j - i + 1 >= MIN_WALLS_FOR_ZONE:
                lo, hi = pts[i][0], pts[j][0]
                total_lot = sum(s for _, s in pts[i:j + 1])
                clusters.append((lo, hi, j - i + 1, total_lot))
            i = j + 1
        return clusters

    def _match_or_create(self, side: str, lo: float, hi: float, count: int,
                          total_lot: float, now: float) -> SupplyDemandZone:
        """A cluster read this cycle is the SAME zone as an existing one if
        their ranges overlap - keeps zone_id (and its accumulated score/
        history) stable instead of a fresh zone every cycle just because
        the exact wall prices inside it wobbled a little. Widens (never
        shrinks) to cover both readings - a zone visibly "shrinking" every
        cycle from noise would be confusing to watch."""
        for z in self._zones.values():
            if z.side != side or z.status == "INVALID" or not z.overlaps(lo, hi):
                continue
            merged_lo, merged_hi = min(z.lo, lo), max(z.hi, hi)
            if merged_hi - merged_lo > MAX_ZONE_WIDTH_USD:
                continue   # would blow the width cap - let this cluster become its own zone below instead of ballooning an existing one

            z.lo = merged_lo
            z.hi = merged_hi
            z.wall_count = count
            z.total_lot = total_lot
            z.last_seen = now
            if z.status == "FRESH":
                z.status = "ACTIVE"
            elif z.status == "BROKEN":
                # walls reformed in the same spot after a break - treat as
                # a genuinely new attempt rather than resurrecting the old
                # (now-invalidated) reputation.
                z.status = "ACTIVE"
                z.retest_count = 0
                z.absorption_hits = 0
            return z
        z = SupplyDemandZone(self._next_id, side, lo, hi, count, total_lot, now)
        self._next_id += 1
        self._zones[z.zone_id] = z
        return z

    def update(self, bid_walls: List[Tuple[float, float]], ask_walls: List[Tuple[float, float]],
               price: float, absorption_status: str) -> List[Dict[str, Any]]:
        now = now_()

        for lo, hi, count, total_lot in self._cluster(bid_walls):
            self._match_or_create("DEMAND", lo, hi, count, total_lot, now)
        for lo, hi, count, total_lot in self._cluster(ask_walls):
            self._match_or_create("SUPPLY", lo, hi, count, total_lot, now)

        prev_price = self._prev_price
        self._prev_price = price

        for z in list(self._zones.values()):
            if z.status == "INVALID":
                continue

            inside_now = z.contains(price)
            inside_before = prev_price is not None and z.contains(prev_price)

            # RETEST: price entered the zone this cycle having been outside
            # it the previous cycle.
            if inside_now and not inside_before and z.status in ("ACTIVE", "TESTED", "WEAKENED"):
                z.retest_count += 1
                z.status = "TESTED"

            # ABSORPTION confirmation - only counts while price is actually
            # inside THIS zone, and only in the direction that favors it
            # (sellers being absorbed supports a DEMAND zone holding;
            # buyers being absorbed supports a SUPPLY zone holding).
            if inside_now:
                favors = (z.side == "DEMAND" and absorption_status == "SELLER_ABSORBED") or \
                         (z.side == "SUPPLY" and absorption_status == "BUYER_ABSORBED")
                if favors:
                    z.absorption_hits += 1

            # BROKEN - price cleared the far side of the zone by more than a
            # noise buffer. NOTE: this is a LIVE TICK read, not a confirmed
            # candle CLOSE - the doctrine's real close-confirmation belongs
            # to the EA's MTF layer (price-history-based, per timeframe).
            # This tick-based read is intentionally provisional/faster, not
            # a replacement for that stricter confirmation.
            if z.side == "DEMAND" and price < z.lo - BREAK_BUFFER_USD:
                z.status = "BROKEN"
            elif z.side == "SUPPLY" and price > z.hi + BREAK_BUFFER_USD:
                z.status = "BROKEN"
            elif z.status == "TESTED" and not inside_now:
                # survived a retest without breaking - back to holding, but
                # note it's not "fresh" anymore either.
                z.status = "WEAKENED" if z.retest_count >= 2 else "ACTIVE"

            z.score = self._score(z, now)

            stale = (now - z.last_seen) > ZONE_TTL_SEC
            broken_too_long = z.status == "BROKEN" and (now - z.last_seen) > BROKEN_INVALIDATE_SEC
            if stale or broken_too_long:
                z.status = "INVALID"

        self._zones = {zid: z for zid, z in self._zones.items() if z.status != "INVALID"}
        return [z.to_dict() for z in sorted(self._zones.values(), key=lambda z: z.score, reverse=True)]

    def _score(self, z: SupplyDemandZone, now: float) -> float:
        """0-100. Components weighted by what's ACTUALLY measurable from
        data confirmed live in the audit (see module docstring) - not
        locked, expect to retune once real session data comes in:
          - wall density/size   (0-30): more walls + more resting lot = a physically bigger obstacle
          - persistence         (0-25): how long this zone has held without breaking (age-based)
          - absorption evidence (0-25): real order-flow confirmation while price tested it, not just resting size
          - retest survival     (0-20): each retest that didn't break the zone adds confidence; broken zones score 0 here
        """
        wall_score = min(30.0, z.wall_count * 6.0 + min(z.total_lot, 100.0) * 0.1)
        age_hours = (now - z.created_at) / 3600.0
        persistence_score = min(25.0, age_hours * 5.0)
        absorption_score = min(25.0, z.absorption_hits * 8.0)
        retest_score = 0.0 if z.status == "BROKEN" else min(20.0, z.retest_count * 10.0)
        return wall_score + persistence_score + absorption_score + retest_score
