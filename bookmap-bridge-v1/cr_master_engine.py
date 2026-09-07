import os
"""
Chain Reaction - Decision Recommendation Engine v8 (Pure Bookmap Edition)
Location: bookmap-bridge/cr_master_engine.py
Author: DADANG WAHYUONO - Chain Reaction System

DOCTRINE:
CMP per TF is computed ENTIRELY from Bookmap's own live tick stream via
cmp_engine.BookmapDoctrineAnalyst — no MT5, no TradingView, no external
platform. Same minor-SNR breakout algorithm as DD_CMP_Marker.v6.2.pine.

Entry flow: once a breakout (CF) fires in a small TF (get_strike_signal()),
if Bookmap's own order flow (Market Pulse + CVD) SUPPORTS that direction ->
ENTRY. Otherwise -> WAIT with a live reason.

Cold start caveat: Bookmap's L1 API has no historical bars, so H4 (master)
can show WAIT for a while after the addon loads (needs live ticks to build
enough H4 candles). This is expected, not a bug — see cmp_engine.py.
"""

import time
from collections import deque
from typing import Any, Dict, Optional

from absorption_engine import AbsorptionEngine

TF_LABEL = {"D1": "D", "H4": "H4", "H1": "H1", "M30": "M30", "M15": "M15", "M5": "M5"}
TF_ORDER = ["D1", "H4", "H1", "M30", "M15", "M5"]

WALL_SPOOF_SHRINK_RATIO = 0.6  # size dropped below 60% of its first-seen size = shrinking
WALL_SPOOF_MIN_SAMPLES = 3     # need a few readings before calling it a shrink trend
WALL_MAGNET_AGE_SEC = 20 * 60  # wall alive 20+ min = persistent/"magnet" (Dadang: "yang jauh
                                # itu yang kuat, dipasang berjam-jam biasanya jadi magnet")
WALL_HISTORY_MIN_AGE_SEC = 60 * 60   # Dadang 2026-08-10: "yang diatas 1 jam meski jauhnya
                                      # ribuan pip bisa gak udah termaping" - once a wall has
                                      # been alive this long, keep remembering/exporting it
                                      # even after it scrolls out of the live top-N nearest
                                      # (crowded out by newer closer walls) - not just a live
                                      # snapshot, an actual persisted memory of old/far zones.
WALL_MEMORY_TTL_SEC = 24 * 60 * 60   # forget an entry if it hasn't been seen live in a full
                                      # day - bounds memory growth without erasing genuinely
                                      # persistent zones mid-session.

# --- Wall SWEEP + reversal detection (2026-08-17, Dadang: "ada ide gila lagi
# bro?") - a big/persistent wall getting traded clean THROUGH ("jebol") is a
# classic stop-hunt/liquidity-grab setup: if price snaps back past the level
# soon after, that's the reversal firing; if it doesn't, the breakout was
# genuine. This builds directly on the existing ask_jebol/bid_jebol detection
# below (already fires on ANY ref-wall break) by additionally logging
# SIGNIFICANT breaks (big + persisted a while - not noise) and tracking what
# happens to price afterward. Display/logging only for now - NOT wired into
# entry/lot-sizing logic yet, same two-phase pattern POC followed (recorded
# first in v29, wired into TryOpen() later in v30/31 once real data existed
# to validate against).
SWEEP_MIN_SIZE_LOT = 30.0          # same decision-tier bar as MT5's InpWallMinSizeLot default -
                                    # NOT the 10-lot visibility floor (market_data_engine.py)
SWEEP_MIN_AGE_SEC = 60.0           # wall must have persisted at least this long before being
                                    # swept to count - filters a wall that appears and vanishes
                                    # immediately either way, not a meaningful liquidity event
SWEEP_REVERSAL_CONFIRM_USD = 2.0   # price must reclaim past the swept level by this much -
                                    # a bare wick back to the exact price doesn't count
SWEEP_WINDOW_SEC = 180.0           # how long to wait for reversal before calling it a genuine
                                    # continuation/breakout instead
SWEEP_LOG_LEN = 20                 # rolling event history depth
MEGA_SWEEP_WINDOW_SEC = 300.0       # same 5-minute window as MT5's MEGA_SWEEP_WINDOW_SEC / web's MEGA_SWEEP_WINDOW_MS
MEGA_SWEEP_MIN_COUNT = 3            # same threshold as MT5's MEGA_SWEEP_MIN_COUNT / web's MEGA_SWEEP_MIN_COUNT


class WallLadderTracker:
    """Tracks a 'current reference wall' per side instead of always reporting
    the nearest wall. Once price breaks through the current wall ('jebol') -
    or the wall gets pulled from the book - automatically advances to the
    next wall in the ladder. Dadang: "cari area wall terdekat, kalau jebol
    pindah wall berikutnya".

    Also tracks each ref wall's size HISTORY to catch spoofing: a wall that
    shows up, gets smaller and smaller, then disappears BEFORE price ever
    reaches it is a pulled/spoofed wall - different from a wall genuinely
    broken through by price. Also surfaces the most recently-appeared wall
    on each side ("kotak buat wall yang baru muncul") so a fresh spoof
    candidate is visible as soon as it shows up, not just when it's gone.
    """

    def __init__(self, size_history_len: int = 12, event_log_len: int = 30):
        self.ask_ref = None  # (price, size) - resistance above price
        self.bid_ref = None  # (price, size) - support below price
        self.ask_jebol = False
        self.bid_jebol = False
        self.ask_spoofed = False  # ref wall vanished WITHOUT price reaching it
        self.bid_spoofed = False
        self._ask_size_history = deque(maxlen=size_history_len)
        self._bid_size_history = deque(maxlen=size_history_len)
        self.new_ask_wall = None  # freshly appeared wall not seen in the previous update()
        self.new_bid_wall = None
        self._prev_ask_prices = set()
        self._prev_bid_prices = set()
        self._ask_first_seen: Dict[float, float] = {}  # price(rounded) -> unix ts first seen
        self._bid_first_seen: Dict[float, float] = {}
        self._wall_memory: Dict[Any, Dict[str, float]] = {}  # (side, price_rounded) -> {price,size,first_seen,last_seen,max_size}
        self._vault_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "depth_vault.json")
        self._last_vault_save = 0.0
        self._load_vault()
        self.event_log = deque(maxlen=event_log_len)
        self.sweep_events = deque(maxlen=SWEEP_LOG_LEN)

    def _load_vault(self):
        if os.path.exists(self._vault_file):
            try:
                with open(self._vault_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("walls", []):
                    side = item.get("side")
                    p = round(float(item.get("price", 0.0)), 2)
                    if side and p > 0:
                        self._wall_memory[(side, p)] = {
                            "price": p,
                            "size": float(item.get("size", 0.0)),
                            "first_seen": float(item.get("first_seen", time.time())),
                            "last_seen": float(item.get("last_seen", time.time())),
                            "max_size": float(item.get("max_size", item.get("size", 0.0)))
                        }
            except Exception:
                pass

    def _save_vault(self, now: float):
        if self._last_vault_save > 0 and (now - self._last_vault_save) < 3.0:
            return
        self._last_vault_save = now
        try:
            walls_export = []
            for (side, p), e in self._wall_memory.items():
                walls_export.append({
                    "side": side,
                    "price": p,
                    "size": e.get("size", 0.0),
                    "first_seen": e.get("first_seen", now),
                    "last_seen": e.get("last_seen", now),
                    "max_size": e.get("max_size", e.get("size", 0.0))
                })
            tmp = self._vault_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"updated_at": now, "count": len(walls_export), "walls": walls_export}, f, indent=2)
            os.replace(tmp, self._vault_file)
        except Exception:
            pass

    def _log_event(self, side: str, kind: str, price: float, size: float):
        self.event_log.appendleft({
            "time": time.time(), "side": side, "type": kind,
            "price": round(price, 2), "size": round(size, 1),
        })

    def _is_shrinking(self, history: deque) -> bool:
        if len(history) < WALL_SPOOF_MIN_SAMPLES:
            return False
        first, last = history[0], history[-1]
        return first > 0 and last < first * WALL_SPOOF_SHRINK_RATIO

    def wall_age_sec(self, price: float, is_bid: bool) -> float:
        d = self._bid_first_seen if is_bid else self._ask_first_seen
        t = d.get(round(price, 2))
        return (time.time() - t) if t else 0.0

    def _update_memory(self, side: str, walls, now: float):
        mem = self._wall_memory
        for p, s in walls:
            key = (side, round(p, 2))
            e = mem.get(key)
            if e is None:
                mem[key] = {"price": p, "size": s, "first_seen": now, "last_seen": now, "max_size": s}
            else:
                e["price"] = p
                e["size"] = s
                e["last_seen"] = now
                if s > e["max_size"]:
                    e["max_size"] = s
        stale = [k for k, e in mem.items() if k[0] == side and now - e["last_seen"] > WALL_MEMORY_TTL_SEC]
        for k in stale:
            del mem[k]
        self._save_vault(now)

    def historical_walls(self, side: str, min_age_sec: float = 0.0, limit: int = 15):
        """Returns the biggest, most significant resting limit order walls across all prices."""
        now = time.time()
        items = []
        for (s, _p), e in self._wall_memory.items():
            if s != side:
                continue
            sz = e.get("max_size", e.get("size", 0.0))
            if sz >= 10.0:
                items.append((e["price"], e["size"], now - e["first_seen"], sz))
        # Sort by largest order size first (biggest magnet walls across the entire chart)
        items.sort(key=lambda x: x[3], reverse=True)
        return [(x[0], x[1], x[2]) for x in items[:limit]]

    def _maybe_log_sweep(self, side: str, wall_price: float, wall_size: float, now: float):
        """Called right when a ref wall gets jebol (price traded through it).
        Only logs a 'sweep' event if the wall was actually SIGNIFICANT - size
        AND age both above threshold, read from _wall_memory (which still
        holds this price's last-known stats even though it just dropped out
        of the live top-N) - so this stays a stop-hunt/liquidity-grab signal,
        not noise from every small/fresh wall price happens to cross."""
        key = (side, round(wall_price, 2))
        mem = self._wall_memory.get(key)
        age = (mem["last_seen"] - mem["first_seen"]) if mem else 0.0
        size = mem["max_size"] if mem else wall_size
        if size < SWEEP_MIN_SIZE_LOT or age < SWEEP_MIN_AGE_SEC:
            return
        self.sweep_events.append({
            "side": side, "price": wall_price, "size": size,
            "age_at_sweep": round(age), "swept_time": now,
            "status": "PENDING", "resolved_time": None,
        })

    def _resolve_sweeps(self, price: float, now: float):
        """Runs every update() BEFORE this cycle's new jebol checks - walks
        every still-PENDING sweep against the current price. A BID (support)
        sweep reverses if price reclaims back ABOVE the wall + buffer (stop-
        hunt then bounce - bullish). An ASK (resistance) sweep reverses if
        price falls back BELOW the wall - buffer (fakeout breakout then
        reject - bearish). No reclaim within SWEEP_WINDOW_SEC = genuine
        continuation, not a reversal."""
        for ev in self.sweep_events:
            if ev["status"] != "PENDING":
                continue
            reclaimed = (price >= ev["price"] + SWEEP_REVERSAL_CONFIRM_USD) if ev["side"] == "BID" \
                else (price <= ev["price"] - SWEEP_REVERSAL_CONFIRM_USD)
            if reclaimed:
                ev["status"] = "REVERSAL_CONFIRMED"
                ev["resolved_time"] = now
            elif now - ev["swept_time"] > SWEEP_WINDOW_SEC:
                ev["status"] = "CONTINUATION"
                ev["resolved_time"] = now

    @property
    def latest_sweep(self):
        return self.sweep_events[-1] if self.sweep_events else None

    @property
    def mega_sweep(self):
        """2026-08-21 - same staircase escalation already ported to the MT5
        EA (RecomputeMegaSweep()) and the web dashboard (logic.js), added
        here too so it lands in bookmap_history_v7 for future backtesting -
        Dadang: "kita catat aja itu tadi mumpung inget." Counts sweep_events
        (any status - PENDING/REVERSAL_CONFIRMED/CONTINUATION, mirroring
        LogSweepForMega()'s "log on every fresh event" behavior) within the
        last MEGA_SWEEP_WINDOW_SEC on the SAME side; 3+ = a real staircase,
        not a one-off."""
        now = time.time()
        counts = {"BID": 0, "ASK": 0}
        for ev in self.sweep_events:
            if now - ev["swept_time"] <= MEGA_SWEEP_WINDOW_SEC:
                counts[ev["side"]] = counts.get(ev["side"], 0) + 1
        for side in ("BID", "ASK"):
            if counts[side] >= MEGA_SWEEP_MIN_COUNT:
                return {"active": True, "side": side, "count": counts[side]}
        return {"active": False, "side": "", "count": 0}

    def update(self, market_data, top_n: int = 8):
        price = market_data.last_price
        now = time.time()
        self._resolve_sweeps(price, now)
        # top_n dilebarin (Dadang: "ada wall gede tapi jauh, lo terlalu mepet
        # liatnya") - biar wall besar yang agak jauh dari harga tetap kebaca,
        # bukan cuma yang paling deket doang.
        asks = market_data.get_wall_ladder(is_bid=False, top_n=top_n)
        bids = market_data.get_wall_ladder(is_bid=True, top_n=top_n)

        cur_ask_prices = {round(p, 2) for p, _ in asks}
        cur_bid_prices = {round(p, 2) for p, _ in bids}
        new_asks = [w for w in asks if round(w[0], 2) not in self._prev_ask_prices]
        new_bids = [w for w in bids if round(w[0], 2) not in self._prev_bid_prices]
        self.new_ask_wall = new_asks[0] if new_asks else None
        self.new_bid_wall = new_bids[0] if new_bids else None
        if self._prev_ask_prices:  # skip the very first update() - everything looks "new" then
            for w in new_asks:
                self._log_event("ASK", "NEW", w[0], w[1])
        if self._prev_bid_prices:
            for w in new_bids:
                self._log_event("BID", "NEW", w[0], w[1])
        self._prev_ask_prices = cur_ask_prices
        self._prev_bid_prices = cur_bid_prices

        # Umur wall (berapa lama harga level ini terus-terusan muncul di book) -
        # wall yang udah lama bertahan (jam-jaman) itu "magnet" (kuat), beda
        # sama wall yang baru sebentar muncul lalu ilang (rentan spoof).
        for p in cur_ask_prices:
            self._ask_first_seen.setdefault(p, now)
        for p in cur_bid_prices:
            self._bid_first_seen.setdefault(p, now)
        self._ask_first_seen = {p: t for p, t in self._ask_first_seen.items() if p in cur_ask_prices}
        self._bid_first_seen = {p: t for p, t in self._bid_first_seen.items() if p in cur_bid_prices}

        all_asks = market_data.get_all_significant_walls(is_bid=False, min_size=10.0)
        all_bids = market_data.get_all_significant_walls(is_bid=True, min_size=10.0)
        self._update_memory("ASK", all_asks, now)
        self._update_memory("BID", all_bids, now)

        self.ask_jebol = False
        self.ask_spoofed = False
        if self.ask_ref is None:
            self.ask_ref = asks[0] if asks else None
            self._ask_size_history.clear()
        else:
            match = next((w for w in asks if abs(w[0] - self.ask_ref[0]) < 0.01), None)
            broken = price > self.ask_ref[0]
            if match is not None:
                self._ask_size_history.append(match[1])
            if broken or match is None:
                if not broken and match is None:
                    self.ask_spoofed = True  # pulled from book before price ever got there
                    self._log_event("ASK", "SPOOFED", self.ask_ref[0], self.ask_ref[1])
                self.ask_jebol = broken
                if broken:
                    self._log_event("ASK", "JEBOL", self.ask_ref[0], self.ask_ref[1])
                    self._maybe_log_sweep("ASK", self.ask_ref[0], self.ask_ref[1], now)
                self.ask_ref = asks[0] if asks else None
                self._ask_size_history.clear()

        self.bid_jebol = False
        self.bid_spoofed = False
        if self.bid_ref is None:
            self.bid_ref = bids[0] if bids else None
            self._bid_size_history.clear()
        else:
            match = next((w for w in bids if abs(w[0] - self.bid_ref[0]) < 0.01), None)
            broken = price < self.bid_ref[0]
            if match is not None:
                self._bid_size_history.append(match[1])
            if broken or match is None:
                if not broken and match is None:
                    self.bid_spoofed = True
                    self._log_event("BID", "SPOOFED", self.bid_ref[0], self.bid_ref[1])
                self.bid_jebol = broken
                if broken:
                    self._log_event("BID", "JEBOL", self.bid_ref[0], self.bid_ref[1])
                    self._maybe_log_sweep("BID", self.bid_ref[0], self.bid_ref[1], now)
                self.bid_ref = bids[0] if bids else None
                self._bid_size_history.clear()

        return asks, bids

    @property
    def ask_shrinking(self) -> bool:
        return self._is_shrinking(self._ask_size_history)

    @property
    def bid_shrinking(self) -> bool:
        return self._is_shrinking(self._bid_size_history)


class CRDecisionRecommendationEngine:
    WALL_ZONE_TOLERANCE = 3.0  # USD - "sampai area wall", same convention as get_m5_direct_signal
    WALL_SL_BUFFER = 1.0       # USD past the wall - invalidation point, not a % backstop

    def __init__(self, doctrine, cvd_engine, market_pulse, market_data, footprint_engine=None, volume_profile=None,
                 iceberg_engine=None):
        self.doctrine = doctrine
        self.cvd_engine = cvd_engine
        self.market_pulse = market_pulse
        self.market_data = market_data
        self.footprint_engine = footprint_engine
        self.volume_profile = volume_profile
        self.iceberg_engine = iceberg_engine
        self.wall_ladder = WallLadderTracker()
        self.absorption_engine = AbsorptionEngine()
        self.active_position = None  # {"dir","tf","entry_time"} once a signal fires; monitored
                                      # for tactical exit/re-entry (Dadang's M30-anchored cycle)
        self._last_exit_m5_time = None  # re-entry cooldown - None = never exited yet, don't gate

    def get_wall_entry_signal(self, current_price: float) -> Optional[Dict[str, Any]]:
        """Dadang: dulu breakout-CMP dipake sebagai proxy karena BELUM punya
        Bookmap (minor-SNR = pengganti data liquidity asli). SEKARANG Bookmap
        nunjukin SNR ASLI (wall) - entry gak perlu nunggu CMP breakout kalau
        harga udah di area wall kuat dan Footprint (buy/sell volume PERSIS di
        harga wall itu) dukung arah bounce/reject-nya. Pulse+CVD dicek umum
        di evaluate() buat semua tipe sinyal - jadi total 3 konfirmasi searah
        Dadang: "market pulse cvd delta mendukung DAN footprint delta plus
        juga mendukung baru kita entri."

        SL teknis di seberang wall (invalidation point) - BUKAN backstop %
        (wall itu level liquidity ASLI, jauh lebih robust daripada minor-SNR
        M5 yang kena hunt 6 detik) dan BUKAN CMP zone manapun."""
        if self.footprint_engine is None:
            return None
        bid_wall = self.wall_ladder.bid_ref
        ask_wall = self.wall_ladder.ask_ref

        if bid_wall and abs(current_price - bid_wall[0]) <= self.WALL_ZONE_TOLERANCE:
            fp = self.footprint_engine.get_footprint_at_price(bid_wall[0])
            if fp["status"] == "BUY_DOMINANT":
                return {
                    "action": "BUY", "type": "WALL_ENTRY", "tf": "WALL",
                    "sl_price": round(bid_wall[0] - self.WALL_SL_BUFFER, 2),
                    "grade": "WALL",
                    "reason": (f"Harga di area wall support {bid_wall[0]:.2f} ({bid_wall[1]:.0f}ct) | "
                               f"Footprint BUY {fp['buy_pct']:.0f}% - bounce, SL di bawah wall"),
                }
        if ask_wall and abs(current_price - ask_wall[0]) <= self.WALL_ZONE_TOLERANCE:
            fp = self.footprint_engine.get_footprint_at_price(ask_wall[0])
            if fp["status"] == "SELL_DOMINANT":
                return {
                    "action": "SELL", "type": "WALL_ENTRY", "tf": "WALL",
                    "sl_price": round(ask_wall[0] + self.WALL_SL_BUFFER, 2),
                    "grade": "WALL",
                    "reason": (f"Harga di area wall resistance {ask_wall[0]:.2f} ({ask_wall[1]:.0f}ct) | "
                               f"Footprint SELL {100 - fp['buy_pct']:.0f}% - reject, SL di atas wall"),
                }
        return None

    def _build_tf_matrix(self) -> Dict[str, Any]:
        matrix: Dict[str, Any] = {}
        for tf in TF_ORDER:
            key = TF_LABEL[tf]
            st = self.doctrine.states.get(tf)
            if not st:
                matrix[key] = {"cmp": "WAIT", "vr": "-", "cf": "-", "action": "NO DATA", "time": "-"}
                continue
            vr_txt = "VR" if st.vr_occurred else "-"
            cf_txt = f"CF #{st.cf_count}" if st.cf_count > 0 else "-"
            if st.status == "MASTER":
                action = "★ MASTER"
            elif st.status == "VR":
                action = "VR - retest"
            elif st.status == "CF":
                action = f"CF #{st.cf_count} confirm"
            elif st.cmp == "WAIT":
                n = len(self.doctrine.aggregator.rows(tf))
                action = f"WARMUP ({n} bars)"
            else:
                action = "MONITOR"
            matrix[key] = {"cmp": st.cmp, "vr": vr_txt, "cf": cf_txt, "action": action, "time": "LIVE"}
        matrix["M1"] = {"cmp": "-", "vr": "-", "cf": "-", "action": "not tracked", "time": "-"}
        return matrix

    def evaluate(self) -> Dict[str, Any]:
        self.doctrine.update()

        current_price = self.market_data.last_price
        # v52.72 (2026-08-20): rolling CVD_DISPLAY_WINDOW_SEC (5 min) window,
        # matches Dadang's live Bookmap widget + scalping use case - see
        # cvd_engine.py module docstring. Was session-cumulative (reset 07:00
        # WIB daily) - that was found to silently diverge from what Dadang's
        # actual widget shows (widget's own config turned out to be "Chart
        # range" + 5-min repeat, not a daily session reset like assumed).
        cvd_30s = self.cvd_engine.get_display_cvd()
        buyer_agg_pct = self.market_pulse.get_pulse()["buyer_aggression_pct"]
        # Absorption (Layer 2.3, final module per Dadang's 5-module architecture):
        # short-window CVD delta vs price move, separate from the session-cumulative
        # CVD used above - see absorption_engine.py.
        self.absorption_engine.on_price(current_price)
        cvd_window_delta = self.cvd_engine.get_window_delta(self.absorption_engine.window_sec)
        absorption = self.absorption_engine.get_absorption(cvd_window_delta)
        # v52.21 (2026-08-17): Dadang, pointing at a 200-lot wall sitting well
        # below the live price cluster on his own Bookmap screenshot: "harus
        # baca super jauh agar tau wall dimana... bukan hanya di sekitaran
        # harga yang live." top_n=8 (the old default) is how many nearest
        # significant walls even get LOOKED AT before anything downstream
        # (near-slot export, _wall_memory persistence tracking, eventual
        # "historical" slot eligibility) has a chance to notice them - a big
        # wall sitting past the 8th-nearest position on a crowded book simply
        # never entered the pipeline. Widened to 20 so a wall like this one
        # gets tracked (and, once it's held InpWallMinAgeSec/InpWallMinSizeLot,
        # actually usable by HasLiquiditySupport()'s v52.20 wide scan on the
        # MT5 side) instead of silently falling outside the window.
        #
        # v52.22: Dadang - "kenapa lebarnya hanya 20 tidak 100 atau 1000
        # sekalian bro" - fair question, 20 was an arbitrary conservative
        # pick with no real justification. Raised to 1000 (effectively
        # unbounded - a real order book will never actually have 1000
        # distinct price levels holding >=10 lot at once, so this never
        # becomes the limiting factor). This number ONLY controls how many
        # candidate walls Python even LOOKS AT before ranking them - it does
        # NOT change how many reach MT5 (that's WALL_NEAR_SLOTS_PER_SIDE +
        # WALL_HIST_SLOTS_PER_SIDE = 5+5 in udp_listener.py, unchanged), so
        # widening this costs nothing and only gives every real wall a
        # chance to be seen and ranked.
        asks_ladder, bids_ladder = self.wall_ladder.update(self.market_data, top_n=1000)
        ask_wall = self.wall_ladder.ask_ref
        bid_wall = self.wall_ladder.bid_ref
        # v52.25: Dadang - "kalo memang ada wal di sana... kenapa nunggu load
        # bro" + "kalo bisa lo garis aja wall itu dimana lebih baik garis" -
        # the "historical" slots feeding MT5's chart-line drawing
        # (UpdateWallLines() -> DrawWallLine(), already loops all 20 slots,
        # no MQL5 change needed) were gated behind WALL_HISTORY_MIN_AGE_SEC
        # (1 hour) before a wall was even ELIGIBLE to be sent - so a
        # genuinely-there-right-now wall like his 4364.0/150-lot example
        # wouldn't get a line until it had survived an hour first. min_age_sec=0
        # removes that eligibility gate entirely - ANY currently-tracked wall
        # can now flow to MT5 and get drawn immediately. historical_walls()
        # still SORTS most-persistent-first internally, so when there are more
        # candidates than the 15 export slots, genuinely older/more-proven
        # ones still win the ranking - this only stops brand-new ones from
        # being excluded outright. Trading DECISIONS are unaffected - MT5's
        # own InpWallMinAgeSec independently re-checks each wall's age before
        # HasLiquiditySupport() trusts it, completely separate from whether
        # it's drawn as a line.
        hist_asks = self.wall_ladder.historical_walls("ASK", min_age_sec=0)
        hist_bids = self.wall_ladder.historical_walls("BID", min_age_sec=0)
        # v52.28: Dadang, looking at the actual MT5 chart - "kenapa garis wall
        # ini ask bisa di bawah price ya bro" - real bug, not a rendering
        # glitch: _wall_memory (which historical_walls() reads from) is only
        # pruned by 24h TTL, never re-validated against where price is NOW.
        # Once price genuinely trades THROUGH a resting ask (consuming it,
        # i.e. a sweep - see WallLadderTracker.update()'s jebol detection
        # above), that price's memory entry keeps its last-known price/size
        # forever until TTL, and kept getting reported as a live "ask wall"
        # even though it's now BEHIND price, not ahead of it - structurally
        # impossible for a real resting sell order (confirmed live: 9/10
        # historical asks were below current_price when Dadang flagged this).
        # Side-sanity filter: an ask wall only makes sense above price, a bid
        # wall only below - drop anything crossed before it ever reaches
        # export (near-list is unaffected, it's read fresh from the live book
        # each cycle so it's naturally always correctly sided).
        hist_asks = [w for w in hist_asks if w[0] > current_price]
        hist_bids = [w for w in hist_bids if w[0] < current_price]

        if self.volume_profile is not None:
            vol_snap = self.volume_profile.get_snapshot()
        else:
            vol_snap = {"session_buy_volume": 0.0, "session_sell_volume": 0.0, "session_total_volume": 0.0,
                        "volume_ratio_buy_pct": 50.0, "poc_price": 0.0, "poc_volume": 0.0, "val": 0.0, "vah": 0.0}

        iceberg_snap = self.iceberg_engine.get_snapshot(self.market_data) if self.iceberg_engine is not None \
            else {"bid_iceberg": None, "ask_iceberg": None}

        h4_dir = self.doctrine.states["H4"].cmp
        m30_dir = self.doctrine.states["M30"].cmp
        # H4 (master) belum warm-up -> fallback ke M30 sebagai arah kerja yang ditampilkan,
        # sinkron sama get_strike_signal() yang juga fallback ke M30 (lihat cmp_engine.py)
        using_fallback = (h4_dir == "WAIT" and m30_dir != "WAIT")
        effective_dir = m30_dir if using_fallback else h4_dir

        # PRIORITAS 0: harga di area WALL (liquidity ASLI dari Bookmap) + Footprint
        # dukung arah bounce/reject-nya. Dadang: "breakout gw buat karena gw gak
        # punya bookmap dulu... sekarang udah jelas snr-nya di bookmap" - gak
        # perlu nunggu CMP breakout SAMA SEKALI buat sinyal ini, makanya dicek
        # duluan dan bisa fire walau H4/M30 masih WAIT (lihat effective_dir check
        # di bawah).
        wall_entry = self.get_wall_entry_signal(current_price)

        # PRIORITAS 1: ikuti M5 langsung + order flow, ASAL harga masih di area
        # CMP/SNR M5 (bukan di tengah pergerakan). Sekarang punya data order flow
        # live dari Bookmap jadi gak perlu lagi disiplin kaku nunggu cascade
        # H4>H1>M30>M15 penuh (itu doktrin buat kondisi TANPA data order flow).
        # VR/CF-nya M5 cuma status/konteks (ditampilin, bukan gate).
        # Fallback ke cascade CF (get_strike_signal) / VR scalp kalau M5 lagi
        # gak di area SNR-nya (harga di tengah2, belum ada zona jelas).
        m5_direct = None if wall_entry else self.doctrine.get_m5_direct_signal(current_price)
        strike = None if (wall_entry or m5_direct) else self.doctrine.get_strike_signal()
        vr_scalp = None if (wall_entry or m5_direct or strike) else self.doctrine.get_vr_scalp_signal()
        active_signal = wall_entry or m5_direct or strike or vr_scalp

        # RE-ENTRY COOLDOWN (2026-08-07) - Dadang: "mau entri harus ada wall
        # yang nahan dulu bukan langsung entri lagi... mana ada mau buy entri
        # pas candle ijo, nunggu merah dulu lah minimal." Root cause of the
        # 9-entries-in-10-seconds whipsaw: after an EXIT, M5's cmp/cmp_change_
        # time often hasn't moved AT ALL yet, so the very next 0.1s cycle sees
        # the SAME stale CF condition and fires again immediately. Block CF
        # (M5-sourced) signals until M5 stamps a genuinely NEW cmp_change_time
        # - CMPDetector's own V/A-shape logic requires an opposite-then-same
        # breakout to do that, which structurally forces at least one real
        # retracement ("candle merah") to happen first before a fresh
        # confirmation counts.
        if (active_signal and active_signal.get("type") == "CF" and
                self._last_exit_m5_time is not None and
                self.doctrine.states["M5"].cmp_change_time <= self._last_exit_m5_time):
            active_signal = None

        is_scalp = active_signal is not None and active_signal["type"] in ("VR_SCALP", "M5_DIRECT_VR")
        is_wall_entry = active_signal is not None and active_signal["type"] == "WALL_ENTRY"

        # BUG BESAR DITEMUKAN & DIFIX (2026-08-07): dulu ada TP price target
        # (wall-based) DAN absorption-driven exit di posisi monitoring - hasil
        # nyata: 9 entry dalam <10 detik, semua whipsaw exit ~0.6-0.7 detik
        # setelah entry, rugi kecil berkali-kali. Dadang: "JANGAN TP KECUALI
        # ADA SIGNAL SELL... meski ada absorption di buy nya lanjut... gw
        # trading gak pernah TP 10 pip." Dicabut TOTAL: gak ada TP price
        # target apapun (wall atau lainnya) yang dikirim ke MT5 - exit
        # SATU-SATUNYA dari get_position_status() (M30 flip / M5 gagal),
        # absorption cuma dipake buat WARNING+kecilin lot pas fresh entry
        # (di bawah), BUKAN buat maksa exit posisi yang lagi jalan.

        tf_matrix = self._build_tf_matrix()

        pulse_side = "BUY" if buyer_agg_pct >= 50.0 else "SELL"
        cvd_side = "BUY" if cvd_30s >= 0.0 else "SELL"
        lot_multiplier = 1.0  # overridden to 0.5 below when absorption warns against a fresh entry

        if self.active_position is not None:
            # POSITION MONITORING - kita UDAH entri, entry_tf (M5) sekarang jadi
            # trigger TAKTIS exit/re-entry, bukan sinyal baru berdiri sendiri.
            # Dadang: "kita entri ikut arah M30... berhenti buy jika M5 jadi
            # sell... kalo M5 sell gak bisa flip M30, begitu M5 buy lagi kita
            # balik buy lagi." SL kena != setup gagal - gagal HANYA kalau M30 flip.
            pos = self.active_position
            pos_status = self.doctrine.get_position_status(pos["dir"], pos["tf"], pos["entry_time"])
            # Absorption exit REMOVED (2026-08-07) - was causing whipsaw churn,
            # see note above. Exit ONLY via doctrine (M30 flip / M5 gagal).

            dir_label = f"M30 CMP: {effective_dir} [FALLBACK, H4 masih warm-up]" if using_fallback else f"H4 CMP: {effective_dir}"
            if pos_status["action"] == "EXIT":
                # Cooldown - JANGAN re-entry pakai state M5 yang SAMA yang barusan
                # dipakai buat exit ini. Dadang: "mau entri harus ada wall yang
                # nahan dulu bukan langsung entri lagi... mana ada mau buy entri
                # pas candle ijo, nunggu merah dulu lah minimal." M5's own
                # CMPDetector V/A-shape requires a genuine opposite-then-same
                # breakout to stamp a NEW cmp_change_time - jadi syarat ini
                # otomatis mensyaratkan minimal 1 candle "merah" (retracement)
                # dulu sebelum M5 confirm "ijo" lagi, bukan re-fire di state basi.
                self._last_exit_m5_time = self.doctrine.states["M5"].cmp_change_time
                self.active_position = None
                recommendation = "WAIT"
                status_badge = "🟠 EXIT"
                reason_lines = [
                    f"🚪 EXIT posisi {pos['dir']} (entry via {pos['tf']})",
                    f"  - {pos_status['reason']}",
                    f"✔ {dir_label}",
                    f"⚡ Market Pulse: {buyer_agg_pct:.1f}% ({pulse_side})",
                    f"📈 CVD Delta: {cvd_30s:+.1f} ({cvd_side})",
                ]
                conclusion = pos_status["reason"]
            else:
                recommendation = pos["dir"]
                status_badge = "🟢 BUY (HOLD)" if pos["dir"] == "BUY" else "🔴 SELL (HOLD)"
                reason_lines = [
                    f"📌 HOLD posisi {pos['dir']} (entry via {pos['tf']})",
                    f"  - {pos_status['reason']}",
                    f"✔ {dir_label}",
                    f"⚡ Market Pulse: {buyer_agg_pct:.1f}% ({pulse_side})",
                    f"📈 CVD Delta: {cvd_30s:+.1f} ({cvd_side})",
                ]
                conclusion = f"Posisi {pos['dir']} masih valid. {pos_status['reason']}"

        elif effective_dir == "WAIT" and not is_wall_entry:
            # WALL_ENTRY sengaja BYPASS gate ini - dia gak butuh H4/M30 warm-up
            # sama sekali (liquidity wall + footprint, bukan CMP cascade).
            recommendation = "WAIT"
            status_badge = "🟡 WAIT"
            n = len(self.doctrine.aggregator.rows("H4"))
            reason_lines = [
                "⚠ H4 (master) & M30 masih WARM-UP",
                f"  - {n} candle H4 terkumpul dari live tick Bookmap - butuh breakout pertama buat nentuin arah",
                "  - Bookmap gak punya history candle lama, jadi ini dibangun dari nol sejak addon di-load",
            ]
            conclusion = "CMP murni dari tick Bookmap, belum ada arah sama sekali. SABAR sampai warm-up kelar."

        elif not active_signal:
            recommendation = "WAIT"
            status_badge = "🟡 WAIT"
            dir_label = f"M30 CMP: {effective_dir} [FALLBACK, H4 masih warm-up]" if using_fallback else f"H4 CMP: {effective_dir}"
            reason_lines = [
                f"✔ {dir_label}",
                "⏳ Belum ada CF (trend) atau VR (retracement) di TF kecil - MONITORING",
                f"⚡ Market Pulse: {buyer_agg_pct:.1f}% ({pulse_side})",
                f"📈 CVD Delta: {cvd_30s:+.1f} ({cvd_side})",
                f"👁 {self.doctrine.get_watch_reason()}",
            ]
            conclusion = "Belum ada status CMP (VR/CF) di sub-chain buat entri. SABAR."

        else:
            action = active_signal["action"]
            flow_agrees = (pulse_side == cvd_side == action)
            if effective_dir == "WAIT":
                dir_label = "H4/M30 masih WAIT [WALL_ENTRY gak butuh master trend]"
            elif using_fallback:
                dir_label = f"M30 CMP: {effective_dir} [FALLBACK, H4 masih warm-up]"
            else:
                dir_label = f"H4 CMP: {effective_dir}"
            entry_kind = ("WALL ENTRY (liquidity Bookmap, gak nunggu breakout)" if is_wall_entry else
                          "SCALP (retracement, lawan master)" if is_scalp else
                          "CONTINUATION (searah trend master)")
            reason_lines = [
                f"✔ {dir_label}",
                f"✔ {active_signal['type']} @ {active_signal['tf']} -> {active_signal['reason']} [{entry_kind}]",
                f"⚡ Market Pulse: {buyer_agg_pct:.1f}% ({pulse_side})",
                f"📈 CVD Delta: {cvd_30s:+.1f} ({cvd_side})",
            ]

            if flow_agrees:
                recommendation = action
                status_badge = "🟢 BUY" if action == "BUY" else "🔴 SELL"
                reason_lines.append(f"✔ Order Flow MENDUKUNG arah {'VR (scalp)' if is_scalp else 'breakout'}")
                conclusion = (f"{active_signal['type']} di {active_signal['tf']} DIDUKUNG order flow "
                              f"({pulse_side}/{cvd_side}). ENTRI {action} [{entry_kind}]. "
                              f"Grade: {active_signal.get('grade', '-')}")

                # Absorption WARNING (bukan hard block) - Dadang: "Pulse BUY, CVD
                # BUY, tapi buyer mulai ter-absorb -> BUY WARNING, kurangi lot."
                # Entry tetap fire, cuma lot dikecilin.
                if ((action == "BUY" and absorption["status"] == "BUYER_ABSORBED") or
                        (action == "SELL" and absorption["status"] == "SELLER_ABSORBED")):
                    lot_multiplier = 0.5
                    status_badge += " ⚠ ABSORB"
                    reason_lines.append(f"⚠ ABSORPTION WARNING: {absorption['reason']} - lot dikecilin")
                    conclusion += f" | ⚠ ABSORPTION: {absorption['reason']}"

                # Mulai tracking posisi - siklus berikutnya cek exit/hold via
                # get_position_status(), bukan nyari sinyal baru dari nol lagi.
                self.active_position = {"dir": action, "tf": active_signal["tf"], "entry_time": time.time()}
            else:
                recommendation = "WAIT"
                status_badge = "🟡 WAIT"
                reason_lines.append(f"⚠ Order Flow BELUM align ke {action} (Pulse={pulse_side}, CVD={cvd_side})")
                conclusion = (f"{active_signal['type']} ada di {active_signal['tf']} tapi order flow belum dukung "
                              f"{action}. TUNGGU absorpsi/konfirmasi dulu.")

        # POST-RECOMMENDATION WALL LADDER (wall NEVER flips BUY<->SELL, only
        # advances to the next wall once the current reference gets jebol)
        wall_summary = "No Nearby Wall"
        target_advice = "Normal TP"
        sizing_advice = "Full Position Size"

        if recommendation == "BUY" and ask_wall:
            if self.wall_ladder.ask_spoofed:
                jebol_tag = " [SPOOFED -> wall ke-pull, pindah wall berikutnya]"
            elif self.wall_ladder.ask_jebol:
                jebol_tag = " [JEBOL -> pindah wall berikutnya]"
            elif self.wall_ladder.ask_shrinking:
                jebol_tag = " [MENGECIL - waspada spoof]"
            else:
                jebol_tag = ""
            dist_ticks = abs(ask_wall[0] - current_price) / 0.1
            if dist_ticks <= 10:
                wall_summary = f"Ask Wall Near @ {ask_wall[0]:.2f} ({ask_wall[1]:.0f} contracts, {dist_ticks:.0f} ticks away){jebol_tag}"
                target_advice = "Target Dekat (Conservative TP @ Ask Wall)"
                sizing_advice = "Normal Position Size"
            else:
                wall_summary = f"Ask Wall Far @ {ask_wall[0]:.2f} ({ask_wall[1]:.0f} contracts){jebol_tag}"
                target_advice = "Normal TP (Potensi Besar)"
                sizing_advice = "Full Position Size"
        elif recommendation == "SELL" and bid_wall:
            if self.wall_ladder.bid_spoofed:
                jebol_tag = " [SPOOFED -> wall ke-pull, pindah wall berikutnya]"
            elif self.wall_ladder.bid_jebol:
                jebol_tag = " [JEBOL -> pindah wall berikutnya]"
            elif self.wall_ladder.bid_shrinking:
                jebol_tag = " [MENGECIL - waspada spoof]"
            else:
                jebol_tag = ""
            dist_ticks = abs(current_price - bid_wall[0]) / 0.1
            if dist_ticks <= 10:
                wall_summary = f"Bid Wall Near @ {bid_wall[0]:.2f} ({bid_wall[1]:.0f} contracts, {dist_ticks:.0f} ticks away){jebol_tag}"
                target_advice = "Target Dekat (Conservative TP @ Bid Wall)"
                sizing_advice = "Reduce Position Size (Kurangi Lot)"
            else:
                wall_summary = f"Bid Wall Far @ {bid_wall[0]:.2f} ({bid_wall[1]:.0f} contracts){jebol_tag}"
                target_advice = "Normal TP (Potensi Besar)"
                sizing_advice = "Full Position Size"

        # Real L2 order book (ALL depth levels, not just significant ≥50-lot
        # walls like wall_ladder above) - for a genuine DOM ladder display.
        # Nearest-to-price first on both sides, capped at 15 levels.
        raw_asks = sorted(self.market_data.asks_depth.items())[:15]
        raw_bids = sorted(self.market_data.bids_depth.items(), reverse=True)[:15]
        best_ask = raw_asks[0][0] if raw_asks else 0.0
        best_bid = raw_bids[0][0] if raw_bids else 0.0
        spread = round(best_ask - best_bid, 2) if best_ask and best_bid else 0.0

        # Last 30 real M5 OHLC bars (candle-formation doctrine's own bars,
        # not a synthetic tick-line) for a genuine price-action chart.
        m5_bars = [
            {"time": b.time, "open": b.open, "high": b.high, "low": b.low, "close": b.close}
            for b in self.doctrine.aggregator.rows("M5")[-30:]
        ]

        return {
            "recommendation": recommendation,
            "status_badge": status_badge,
            "reason_lines": reason_lines,
            "order_book": {
                "asks": [[p, s] for p, s in raw_asks],
                "bids": [[p, s] for p, s in raw_bids],
            },
            "spread": spread,
            "m5_bars": m5_bars,
            "wall_ladder": {
                "asks": [[p, s, round(self.wall_ladder.wall_age_sec(p, False))] for p, s in asks_ladder],
                "bids": [[p, s, round(self.wall_ladder.wall_age_sec(p, True))] for p, s in bids_ladder],
                "historical_asks": [[p, s, round(age)] for p, s, age in hist_asks],
                "historical_bids": [[p, s, round(age)] for p, s, age in hist_bids],
                "magnet_age_sec": WALL_MAGNET_AGE_SEC,
                "ask_jebol": self.wall_ladder.ask_jebol,
                "bid_jebol": self.wall_ladder.bid_jebol,
                "ask_spoofed": self.wall_ladder.ask_spoofed,
                "bid_spoofed": self.wall_ladder.bid_spoofed,
                "ask_shrinking": self.wall_ladder.ask_shrinking,
                "bid_shrinking": self.wall_ladder.bid_shrinking,
                "new_ask_wall": list(self.wall_ladder.new_ask_wall) if self.wall_ladder.new_ask_wall else None,
                "new_bid_wall": list(self.wall_ladder.new_bid_wall) if self.wall_ladder.new_bid_wall else None,
                "event_log": list(self.wall_ladder.event_log),
            },
            "wall_sweep": {
                "latest": self.wall_ladder.latest_sweep,
                "history": list(self.wall_ladder.sweep_events),
                "mega": self.wall_ladder.mega_sweep,
            },
            "conclusion": conclusion,
            "wall_summary": wall_summary,
            "target_advice": target_advice,
            "sizing_advice": sizing_advice,
            "current_price": current_price,
            "buyer_aggression_pct": buyer_agg_pct,
            "cvd_30s": cvd_30s,
            "tf_matrix": tf_matrix,
            # Raw signal dict (type/tf/grade/tp_tf/sl_tf/reason) that drove this
            # cycle's decision, if any - lets a consumer (udp_listener's MT5
            # auto-executor) resolve TP/SL and log without re-parsing reason_lines.
            "active_signal": active_signal,
            "position": dict(self.active_position) if self.active_position else None,
            "absorption": absorption,
            "footprint": self._nearest_wall_footprint(current_price, ask_wall, bid_wall),
            "lot_multiplier": lot_multiplier,
            "volume_profile": vol_snap,
            "iceberg": iceberg_snap,
        }

    def _nearest_wall_footprint(self, current_price, ask_wall, bid_wall) -> Optional[Dict[str, Any]]:
        """Footprint reading at whichever ref wall (ask/bid) is closer to
        price right now - display-only (get_wall_entry_signal above does its
        own precise per-side check), lets the dashboard show something
        meaningful even when not exactly at the zone-tolerance threshold."""
        if self.footprint_engine is None:
            return None
        candidates = []
        if ask_wall:
            candidates.append(("ASK", ask_wall, abs(current_price - ask_wall[0])))
        if bid_wall:
            candidates.append(("BID", bid_wall, abs(current_price - bid_wall[0])))
        if not candidates:
            return None
        side, wall, dist = min(candidates, key=lambda c: c[2])
        fp = self.footprint_engine.get_footprint_at_price(wall[0])
        fp["side"] = side
        fp["wall_price"] = wall[0]
        fp["distance"] = round(dist, 2)
        return fp
