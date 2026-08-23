"""
UDP Listener - Bookmap order flow + TradingView Pine CMP overlay
Location: bookmap-bridge/udp_listener.py

Runs as a NORMAL standalone Python process (this venv, not Bookmap's buggy
embedded Python API editor). Listens on 127.0.0.1:9000 for the JSON trade/
depth payloads already broadcast by the EXISTING, stable
C:\\Bookmap\\Python\\bookmap_bridge.py (same one used by wall-breakout-engine -
untouched, still forwards L1 trades + L2 depth independently of this script).

Order flow (Market Pulse / CVD / Wall) is 100% live Bookmap tick data.

CMP for ALL TFs (D1/H4/H1/M30/M15/M5) is overlaid from
../tradingview-mcp-jackson/tv_poll.mjs, which reads DD_CMP_Marker.v6.2.pine's
own dashboard live via CDP (TradingView already has years of chart history,
so no warm-up needed there — Pine already shows every TF instantly). This
overlay ONLY applies while Bookmap itself doesn't have enough bars yet (<3)
for that TF - once Bookmap's own tick data is sufficient, its own live
computation takes over automatically (more precise order-flow timing for
entries once it's warm).

Payload formats sent by bookmap_bridge.py:
  {"type": "instrument", "alias", "pips", "size_multiplier"}
  {"type": "trade",      "alias", "is_bid", "price", "size"}
  {"type": "depth",      "alias", "is_bid", "price", "size"}

NOTE: wall-breakout-engine's own backend (main.py/server.py) is NOT currently
running, so port 9000 is free. If that backend gets started later, it will
compete with this listener for the same UDP port - only run one at a time.
"""

import csv
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market_data_engine import MarketDataEngine
from cvd_engine import CVDEngine
from market_pulse_engine import MarketPulseEngine
from footprint_engine import FootprintEngine
from volume_profile_engine import VolumeProfileEngine
from iceberg_engine import IcebergEngine
from macro_correlation import MacroCorrelation
from cmp_engine import MultiTFAggregator, BookmapDoctrineAnalyst
from cr_master_engine import CRDecisionRecommendationEngine
import mt5_bridge_executor as mt5x
import trade_db

UDP_IP = "127.0.0.1"
UDP_PORT = 9000
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_status.json")
WRITE_INTERVAL_SEC = 0.1  # Dadang: "web harus baca every tick... perubahan sekecil apapun
                          # masuk ke web" - 0.5s kerasa ketinggalan buat data secepat tick
                          # order flow. Data internal (CVD/Pulse/Footprint) udah tick-accurate
                          # dari handle_payload(); ini cuma naikin frekuensi SNAPSHOT-nya.

WIB = timezone(timedelta(hours=7))

# --- MT5 live-bridge (2026-08-09): Dadang wants CVD/Market Pulse/Absorption
# pulled INTO the MT5 EA as an extra live signal - "biar kita tau juga
# potensinya". MQL5 can't talk to Python directly, so this overwrites a tiny
# snapshot CSV in MT5's own Common\Files folder every write cycle (same
# shared folder the EA already uses for its trade-history CSV export) - the
# EA reads it via FileOpen(FILE_READ|FILE_CSV|FILE_COMMON). LIVE ONLY - only
# meaningful while Bookmap+this listener AND MT5 are both running at the
# same time; cannot be used to backtest MT5's historical performance since
# no CVD history existed before today (see CVD_LOG_DIR below, which starts
# fixing that going forward).
MT5_COMMON_FILES_DIR = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
MT5_BRIDGE_FILE = os.path.join(MT5_COMMON_FILES_DIR, "bookmap_live_signal.csv")

# Macro correlation goes in its OWN file rather than as extra columns on
# bookmap_live_signal.csv. The EA reads that CSV by skipping exactly
# `totalFields` header cells then reading positionally (see
# ReadBookmapBridge()), so appending columns shifts every field unless the
# EA is recompiled and reloaded in the same breath - a real corruption risk
# for what is only an informational readout. A separate file degrades
# safely instead: missing or stale simply means the panel shows "-".
MT5_MACRO_FILE = os.path.join(MT5_COMMON_FILES_DIR, "macro_correlation.csv")
# v37: TradingView/Pine RETIRED - Dadang: "trading view nya gak usah ikut
# nyala karena tv sudah tidak kita butuhkan". apply_tv_overlay() (read
# tv_cmp_state.json from tv_poll.mjs via CDP) replaced by apply_mt5_overlay()
# below, reading Common\Files\sultan_status.json - already written every
# ~1s by DD_ChainReaction_MultiTF_EA.mq5's WriteSultanStatus() (v34+), which
# reads MT5's OWN DD_CMP_Indicator (full history always, no cold-start wait,
# immune to this process's own restarts - unlike Bookmap's tick-only CMP).
MT5_STATUS_FILE = os.path.join(MT5_COMMON_FILES_DIR, "sultan_status.json")
MT5_OVERLAY_STALE_SEC = 15.0
MT5_OVERLAY_TFS = ("D1", "H4", "H1", "M30", "M15", "M5")
# v29: split into NEAR (live top-N nearest, refreshed every cycle) + HIST
# (persisted >1hr, kept mapped even after scrolling out of the live nearest
# scan - Dadang: "jangan cuman di area price, tampilkan wall yang jauh dari
# price... yang diatas 1 jam meski jauhnya ribuan pip bisa gak udah
# termaping"). Total per side sent to MT5 = NEAR + HIST. Keep all three in
# sync with DD_ChainReaction_MultiTF_EA_v2.mq5's ReadBookmapBridge()/WALL_SLOTS_PER_SIDE.
#
# v52.24 (2026-08-17): Dadang - "lo juga bisa upgrade apa aja di bookmap
# bridge... tune up bro agar lebih maximal data kita" - right after we found
# the stale-addon bug (v52.22/23) that had been starving this whole pipeline
# of real depth data (49 levels -> 756 levels once the addon got reinstalled).
# NEAR stays 5 (plenty for the immediate-price area - a rich book rarely has
# more than a handful of genuinely significant walls within any one tight
# window). HIST tripled 5->15 - that's the "baca super jauh" side (distant,
# persistent magnet walls like the 4364.0/150-lot one Dadang pointed at),
# and it was starved worst by the old bug since it needs TIME+real data to
# accumulate persistence, which the stale feed could never give it.
WALL_NEAR_SLOTS_PER_SIDE = 5
WALL_HIST_SLOTS_PER_SIDE = 15
WALL_SLOTS_PER_SIDE = WALL_NEAR_SLOTS_PER_SIDE + WALL_HIST_SLOTS_PER_SIDE

# --- Historical CVD/Pulse/Absorption/POC logger (2026-08-09, moved into
# Common\Files 2026-08-10/v31): checked the whole project, confirmed ZERO
# historical CVD data existed anywhere before this - cvd_engine.py was
# always real-time-only, in-memory, reset daily. One row every
# CVD_LOG_INTERVAL_SEC (not every 0.1s write cycle - that would be ~864k
# rows/day) into a per-day CSV, so a real dataset starts accumulating from
# today for future backtesting once there's enough of it.
#
# v31: moved from bookmap-bridge/cvd_history/ into MT5's own Common\Files -
# Dadang: "siapin semuanya... buat backtest" - this IS the file the MQL5 EA
# now reads back during Strategy Tester replay (see ReadBookmapHistoryReplay()
# in DD_ChainReaction_MultiTF_EA.mq5) - single source of truth, no separate
# copy/sync step needed. Renamed cvd_history_ -> bookmap_history_ since it's
# no longer just a CVD log (now also carries POC/volume-ratio/top-of-book).
# The OLD cvd_history/*.csv files (pre-v31, ~1hr of data) are LEFT AS-IS,
# not migrated - MQL5's CSV reader assumes one consistent schema per file and
# those old rows predate several of the newer columns (would desync the
# reader). Nothing of value lost - only ~1hr existed, and this file naturally
# keeps accumulating going forward from a clean, consistent schema.
CVD_LOG_DIR = os.path.join(MT5_COMMON_FILES_DIR, "bookmap_history")
# v52.4 (2026-08-17): prefix bumped v3 - added full wall ladder (10 bid + 10
# ask, same near+historical merge as the live bridge file). Dadang, looking
# at the wall lines actually drawn on his chart: "ini harus akurat bro jadi
# meski ada wall di manapun harus terbaca dan harus kerecord juga agar bisa
# kita jadikan histori dan tune up kedepannya" - the wall ladder was ALWAYS
# accurate/complete in the live bridge file (WallLadderTracker's persistent
# _wall_memory already maps far walls up to 24hr, not just the nearest few -
# see cr_master_engine.py), it just was never being written to history, only
# a single best_bid/best_ask snapshot was. This is the fix - same schema-bump
# convention as v1->v2 (fixed-column-per-file reader on the MQL5 side).
#
# v52.14 (2026-08-17): prefix bumped v4 - added per-wall AGE (seconds since
# first seen). Dadang: "sekarang lo browsing sebagai ahli trading CFD dengan
# data bookmap" - professional order-flow practice treats wall PERSISTENCE
# as the tell for real-vs-"bait" liquidity (a wall that just appeared is
# worth less than one that's been sitting - see bookmap.com's own writeup on
# fake liquidity/bait walls). The age was ALREADY computed by
# WallLadderTracker.wall_age_sec()/historical_walls() and flowing through
# _merge_wall_slots() - just never written to either CSV. Now it is.
#
# v52.24 (2026-08-17): prefix bumped v5 - WALL_HIST_SLOTS_PER_SIDE 5->15
# (see above) changes the column count again. Same bump convention.
#
# v52.26 (2026-08-17): prefix bumped v6 - added sweep_side/price/size/
# age_at_sweep/status/since_sec (see write_mt5_bridge_file()'s sweep block) so
# the wall-sweep-reversal signal gets a real dataset to validate against
# before it's ever wired into entry/lot-sizing logic, same "record first"
# discipline Dadang set for POC/CVD (v29 recorded -> v30/31 wired once real
# data existed).
#
# 2026-08-21: prefix bumped v7 - added mega_sweep_active/side/count (see
# WallLadderTracker.mega_sweep in cr_master_engine.py). Same day the Mega
# Sweep staircase alert (3+ same-side sweeps in 5min) got built MT5-first +
# web - Dadang, mid-live-trade, watching it fire: "lo catat aja itu tadi
# mumpung inget" (worried about hitting a usage limit before writing this
# down). Same "record first, wire into entry logic later" discipline as
# every other bookmap_history column.
CVD_LOG_FILE_PREFIX = "bookmap_history_v7_"
CVD_LOG_INTERVAL_SEC = 5.0
_last_cvd_log_ts = 0.0

# Dadang: "lo harus buat mt5 gw entri sesuai signal karena akan kita jadikan
# database bro" - auto-mirror every entry/exit to the MT5 DEMO account
# (magic 2027, isolated from the production engine's 2026) and log every
# trade to trades.db. If MT5 isn't reachable at startup, auto-exec disables
# itself but the rest of the pipeline (CMP/dashboard) keeps running normally.
#
# 2026-08-21: DISABLED per Dadang - "lo ilangin bro kita hanya entri pakai
# ea aja" (only DD_ChainReaction_MultiTF_EA_v2.mq5 should place real
# orders from now on - this system confused him with a SELL that had no
# Wall Sweep behind it, since it was never built to check for one). See
# handle_mt5_auto_execute()'s docstring. Flip back to False to re-enable -
# trades.db logging + everything else stays wired, just dormant.
AUTO_EXECUTE_MT5_TRADES_DISABLED_BY_DADANG = True
trade_db.init_db()
mt5_ready = mt5x.connect()

market_data = MarketDataEngine()
cvd_engine = CVDEngine()
market_pulse = MarketPulseEngine()
footprint_engine = FootprintEngine()
volume_profile = VolumeProfileEngine()
iceberg_engine = IcebergEngine()
macro = MacroCorrelation()   # 6E (Euro FX) as a dollar-strength proxy - informational only
bar_aggregator = MultiTFAggregator()
doctrine_analyst = BookmapDoctrineAnalyst(bar_aggregator, master_tf="H4")
master_engine = CRDecisionRecommendationEngine(doctrine_analyst, cvd_engine, market_pulse, market_data,
                                                footprint_engine, volume_profile=volume_profile,
                                                iceberg_engine=iceberg_engine)

# Reconcile with any position already open on the broker (e.g. survived a
# restart) BEFORE the main loop starts - otherwise a fresh active_position=
# None lets a still-true CF/M30 condition fire a DUPLICATE entry. Caught
# live: two identical BUY entries 166s apart, exactly one restart cycle
# in between, both still open and losing money in parallel.
if mt5_ready:
    _existing_position = mt5x.get_open_position_dict()
    if _existing_position:
        master_engine.active_position = _existing_position
        print(f"[UDP-Listener] Reconciled EXISTING position on startup: "
              f"#{_existing_position['mt5_ticket']} {_existing_position['dir']} "
              f"{_existing_position['lot']}L @ {_existing_position['entry_price']:.2f}", flush=True)


def reconcile_broker_position():
    """Runs BEFORE evaluate() every cycle. If we're tracking an active_position
    with an mt5_ticket but the broker says it's no longer open (SL/TP hit on
    its own, not via our close_position() call), our internal state would
    otherwise go stale forever - dashboard would keep showing "BUY (HOLD)"
    with no real position behind it, and trades.db would keep that row stuck
    at status='OPEN'. Caught live: a BMR_CF entry got SL'd in 6 seconds,
    trades.db still said OPEN until this reconciliation was added."""
    if not mt5_ready:
        return
    pos = master_engine.active_position
    if not pos:
        return
    ticket = pos.get("mt5_ticket")
    if not ticket or mt5x.is_position_open(ticket):
        return
    closed = mt5x.check_orphaned_close(ticket)
    if closed:
        trade_db.log_exit(ticket, closed["price"], "SL/TP hit on broker (reconciled)", closed["pnl"])
        print(f"[UDP-Listener] Reconciled orphaned close: #{ticket} PnL {closed['pnl']:+.2f}", flush=True)
    master_engine.active_position = None


def handle_mt5_auto_execute(prev_position, result):
    """Fires exactly once per entry/exit TRANSITION (not every poll) by
    diffing master_engine.active_position across this evaluate() call.

    2026-08-21: DISABLED - Dadang saw a BMR_M5_DIRECT_CF SELL open with no
    Wall Sweep confirmation and didn't recognize it: "kenapa dia ngeselin
    bro kan blm ada sweep untuk sell" -> "lo ilangin bro kita hanya entri
    pakai ea aja bro nanti gw bingung mana entrian dari bookmap dan ea nya."
    This system (magic 2027, BMR_ prefix) has always been independent of
    DD_ChainReaction_MultiTF_EA_v2.mq5's Sweep Reversal Veto (different
    codebase entirely, see project_bookmap_bridge memory) - it was never
    supposed to require a sweep, so it isn't a bug, but Dadang wants only
    ONE system placing real orders from here on. Everything ELSE in this
    file (CVD/wall/sweep/absorption feeding the EA panel + Sultan dashboard)
    is untouched - this function just stops executing on the broker."""
    if AUTO_EXECUTE_MT5_TRADES_DISABLED_BY_DADANG:
        return
    if not mt5_ready:
        return
    new_position = master_engine.active_position

    if prev_position is None and new_position is not None:
        sig = result.get("active_signal") or {}
        direction = new_position["dir"]
        # NO TP (2026-08-07) - Dadang: "JANGAN TP KECUALI ADA SIGNAL SELL...
        # gw trading gak pernah TP 10 pip." Exit is 100% doctrine-driven
        # (get_position_status() -> close_position()), never a broker-side
        # price target. sl_price_hint: WALL_ENTRY gives a real technical
        # level (wall invalidation); CF/VR_SCALP have none, so mt5x falls
        # back to the wide %-of-balance catastrophic backstop for those.
        sl_price_hint = sig.get("sl_price", 0.0)
        lot_multiplier = result.get("lot_multiplier", 1.0)
        order = mt5x.execute_entry(direction, sig.get("type", "?"), sl_price_hint, lot_multiplier)
        if order:
            trade_db.log_entry(direction, sig.get("type"), sig.get("tf"), sig.get("grade"),
                                sig.get("reason"), order["price"], order["sl"], order["tp"],
                                order["lot"], order["ticket"])
            # tag onto the SAME dict cr_master_engine.py is tracking, so it's
            # still there next cycle (both for the eventual exit AND so the
            # dashboard can show entry/SL/TP while the position is held)
            master_engine.active_position.update({
                "mt5_ticket": order["ticket"], "entry_price": order["price"],
                "sl": order["sl"], "tp": order["tp"], "lot": order["lot"],
            })

    elif prev_position is not None and new_position is None:
        ticket = prev_position.get("mt5_ticket")
        if not ticket:
            return
        reason = result.get("conclusion", "exit")
        closed = mt5x.close_position(ticket, reason)
        if closed is None:
            closed = mt5x.check_orphaned_close(ticket)  # SL/TP might've already hit on its own
        if closed:
            trade_db.log_exit(ticket, closed["price"], reason, closed["pnl"])


def apply_mt5_overlay():
    """Replaces the old apply_tv_overlay() (TradingView/Pine, removed v37 -
    Dadang: "tv sudah tidak kita butuhkan"). Injects MT5-sourced CMP
    DIRECTION while Bookmap's own bars are still <3 for that TF, reading
    Common\\Files\\sultan_status.json - already written every ~1s by
    DD_ChainReaction_MultiTF_EA.mq5's WriteSultanStatus() (v34+), which reads
    MT5's OWN DD_CMP_Indicator (full history always, no cold-start wait).

    Known regression vs the old Pine overlay: DD_CMP_Indicator.mq5 doesn't
    track VR/CF state (only raw CMP flips), so overlaid TFs only get a
    direction - VR/CF columns stay at their TFState default ("-") instead of
    Pine's fuller vr/cf/action text. M1 passthrough also drops (MT5 export
    doesn't include M1). Accepted tradeoff per Dadang's explicit direction."""
    overlaid = set()
    try:
        with open(MT5_STATUS_FILE, "r", encoding="ascii") as f:
            mt5_status = json.load(f)
    except Exception:
        return overlaid

    if time.time() - mt5_status.get("timestamp", 0) > MT5_OVERLAY_STALE_SEC:
        return overlaid

    regime = mt5_status.get("regime", {})
    key_map = {"D1": "d1", "H4": "h4", "H1": "h1", "M30": "m30", "M15": "m15", "M5": "m5"}
    for tf in MT5_OVERLAY_TFS:
        if len(bar_aggregator.rows(tf)) >= 3:
            continue  # Bookmap's own real data is enough now, don't override
        cmp_val = (regime.get(key_map[tf]) or "").upper()
        if cmp_val in ("BUY", "SELL"):
            st = doctrine_analyst.states[tf]
            # Same cmp_change_time discipline as the old Pine overlay had -
            # only stamp a NEW time when cmp actually transitions, not every
            # poll, or get_position_status()'s EXIT check would never fire.
            if st.cmp != cmp_val:
                st.cmp_change_time = time.time()
            st.cmp = cmp_val
            st.initialized = True
            st.status = "CMP"
            st.vr_occurred = False
            overlaid.add(tf)
    return overlaid


def _write_atomic(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    # os.replace() can transiently fail on Windows ("Access is denied") if
    # dashboard_web.py's http.server has the destination file open for a GET
    # at that exact instant. Harmless (next write recovers) but happens more
    # often now that WRITE_INTERVAL_SEC dropped to 0.1s - retry instead of
    # dropping that cycle's snapshot.
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.02)


def _merge_wall_slots(near_list, hist_list, near_n, hist_n):
    """near_n nearest-live walls + hist_n most-persistent historical walls
    (>1hr, may be far from price), deduped by rounded price so a wall
    already covered by the near list doesn't waste a historical slot
    repeating itself. Pads with [0,0,0] (MT5 side skips zero-price)."""
    slots = []
    seen = set()
    for w in (near_list or [])[:near_n]:
        key = round(w[0], 2)
        if key in seen:
            continue
        seen.add(key)
        slots.append(w)
    for w in (hist_list or []):
        if len(slots) >= near_n + hist_n:
            break
        key = round(w[0], 2)
        if key in seen:
            continue
        seen.add(key)
        slots.append(w)
    while len(slots) < near_n + hist_n:
        slots.append([0.0, 0.0, 0])
    return slots[:near_n + hist_n]


def write_mt5_bridge_file(result: dict, price: float):
    """Overwrite a tiny snapshot CSV in MT5's Common\\Files folder so the
    MQL5 EA can read Bookmap's live CVD/Pulse/Absorption/Wall/Volume-Profile
    via FileOpen(FILE_READ|FILE_CSV|FILE_COMMON). Live-only - see module
    docstring note above MT5_BRIDGE_FILE. Never raises - a failed write here
    (e.g. MT5 not installed on this machine, folder missing) must not take
    down the rest of the pipeline.

    2026-08-10 (v24): added bid/ask wall (price,size) - Dadang: "bisa gak
    berapa banyak lot di bookmap langsung tergaris di MT5 tapi harus lo
    cover sesuai harga bookmap nya" - `price` here IS Bookmap's own
    instrument price (GCZ6 futures, not XAUUSD spot), sent alongside the
    wall prices so the MT5 side can compute price_offset = XAUUSD_price -
    this_price and convert every wall level before drawing it - the futures/
    spot basis isn't constant, so this offset must be recomputed every write
    cycle, never hardcoded. Missing wall slots are sent as 0,0 (MT5 side
    skips zero-price walls).

    2026-08-10 (v29): added poc_price/poc_volume/vol_ratio_buy_pct/session
    buy+sell volume (VolumeProfileEngine) - Dadang: "kasih tambahan cvd atau
    footprint atau apalah yang mengindikasikan kekuatan buyer atau seller...
    garis poc juga". Also each side's wall slots are now a MERGE of near
    (live nearest) + historical (persisted >1hr, may be far from price) -
    Dadang: "jangan cuman di area price, tampilkan wall yang jauh dari
    price... yang diatas 1 jam meski jauhnya ribuan pip bisa gak udah
    termaping" - see _merge_wall_slots() and WallLadderTracker.historical_walls().

    2026-08-10 (v33): added val/vah (Value Area High/Low - turns POC from a
    single line into a 70%-of-volume ZONE) and bid/ask iceberg fields
    (IcebergEngine - hidden refilling orders, price/displayed size/ratio per
    side, 0s if none detected) - Dadang: "tambah keduanya bro"."""
    try:
        os.makedirs(MT5_COMMON_FILES_DIR, exist_ok=True)
        absorption_status = (result.get("absorption") or {}).get("status", "NONE")
        wall_ladder = result.get("wall_ladder") or {}
        vol_snap = result.get("volume_profile") or {}
        iceberg_snap = result.get("iceberg") or {}
        bid_ice = iceberg_snap.get("bid_iceberg") or {}
        ask_ice = iceberg_snap.get("ask_iceberg") or {}
        bid_slots = _merge_wall_slots(wall_ladder.get("bids"), wall_ladder.get("historical_bids"),
                                       WALL_NEAR_SLOTS_PER_SIDE, WALL_HIST_SLOTS_PER_SIDE)
        ask_slots = _merge_wall_slots(wall_ladder.get("asks"), wall_ladder.get("historical_asks"),
                                       WALL_NEAR_SLOTS_PER_SIDE, WALL_HIST_SLOTS_PER_SIDE)

        header = ["timestamp", "price", "cvd_session", "pulse_pct", "absorption",
                   "poc_price", "poc_volume", "vol_ratio_buy_pct", "buy_vol_session", "sell_vol_session",
                   "val", "vah",
                   "bid_ice_px", "bid_ice_sz", "bid_ice_ratio",
                   "ask_ice_px", "ask_ice_sz", "ask_ice_ratio"]
        row = [
            f"{time.time():.2f}",
            f"{price:.2f}",
            f"{result.get('cvd_30s', 0.0):.2f}",
            f"{result.get('buyer_aggression_pct', 0.0):.2f}",
            absorption_status,
            f"{vol_snap.get('poc_price', 0.0):.2f}",
            f"{vol_snap.get('poc_volume', 0.0):.1f}",
            f"{vol_snap.get('volume_ratio_buy_pct', 50.0):.1f}",
            f"{vol_snap.get('session_buy_volume', 0.0):.1f}",
            f"{vol_snap.get('session_sell_volume', 0.0):.1f}",
            f"{vol_snap.get('val', 0.0):.2f}",
            f"{vol_snap.get('vah', 0.0):.2f}",
            f"{bid_ice.get('price', 0.0):.2f}", f"{bid_ice.get('displayed_size', 0.0):.1f}", f"{bid_ice.get('ratio', 0.0):.2f}",
            f"{ask_ice.get('price', 0.0):.2f}", f"{ask_ice.get('displayed_size', 0.0):.1f}", f"{ask_ice.get('ratio', 0.0):.2f}",
        ]
        # v52.14: age (seconds since first seen) was ALREADY computed as
        # element [2] of every wall tuple (WallLadderTracker.wall_age_sec()/
        # historical_walls()) and flowing all the way through
        # _merge_wall_slots() - just never written out here. Dadang: "browsing
        # sebagai ahli" turned up that professional order-flow practice treats
        # a wall's PERSISTENCE as the tell for real-vs-spoofed ("bait")
        # liquidity - a wall that just appeared is worth less than one that's
        # been sitting for a while. MT5 side (HasLiquiditySupport(), v52.14)
        # now requires a minimum age before trusting a wall as real support.
        for i, w_ in enumerate(bid_slots, start=1):
            header += [f"bid{i}_px", f"bid{i}_sz", f"bid{i}_age"]
            row += [f"{w_[0]:.2f}", f"{w_[1]:.1f}", f"{(w_[2] if len(w_) > 2 else 0):.0f}"]
        for i, w_ in enumerate(ask_slots, start=1):
            header += [f"ask{i}_px", f"ask{i}_sz", f"ask{i}_age"]
            row += [f"{w_[0]:.2f}", f"{w_[1]:.1f}", f"{(w_[2] if len(w_) > 2 else 0):.0f}"]

        # v52.26: wall-SWEEP + reversal (Dadang: "ide gila lagi bro?") - a big/
        # persistent wall traded clean through, then either reclaimed (stop-hunt
        # reversal) or not (genuine continuation) - see cr_master_engine.py's
        # WallLadderTracker._maybe_log_sweep()/_resolve_sweeps(). Appended at the
        # END of the row (not inserted among the wall slots above) so every
        # existing field keeps its exact column position - ReadBookmapBridge()
        # only needs its totalFields count bumped, not its whole read order.
        sweep = (result.get("wall_sweep") or {}).get("latest")
        now_ts = time.time()
        if sweep:
            sweep_side   = sweep.get("side", "")
            sweep_price  = sweep.get("price", 0.0)
            sweep_size   = sweep.get("size", 0.0)
            sweep_age    = sweep.get("age_at_sweep", 0)
            sweep_status = sweep.get("status", "NONE")
            sweep_since  = now_ts - sweep.get("swept_time", now_ts)
        else:
            sweep_side, sweep_price, sweep_size, sweep_age, sweep_status, sweep_since = "", 0.0, 0.0, 0, "NONE", 0.0
        header += ["sweep_side", "sweep_price", "sweep_size", "sweep_age_sec", "sweep_status", "sweep_since_sec"]
        row += [sweep_side, f"{sweep_price:.2f}", f"{sweep_size:.1f}", f"{sweep_age:.0f}", sweep_status, f"{sweep_since:.0f}"]

        # 2026-08-22 - near-price footprint (buy vs sell volume actually
        # TRADED at the current price, within footprint_engine's rolling
        # window - see footprint_engine.py). Dadang, discussing why
        # Momentum(M5) needed a Bookmap-side companion (built as CVD-based
        # "Momentum M5 Bookmap" the same night): "valentini gw rasa dia
        # pakai footprint bro." Reuses the SAME shared footprint_engine
        # instance already fed live trades for wall-entry confirmation
        # (cr_master_engine.py) - get_footprint_at_price() is a pure query,
        # calling it again here doesn't affect that existing use. The MT5
        # EA does its own event-anchored snapshot/diff on these two raw
        # numbers (same pattern as g_bmMomBaseCvd) rather than Python trying
        # to track "since the M5 breakout" itself - keeps this one-way
        # export simple, consistent with every other bridge field.
        fp_now = footprint_engine.get_footprint_at_price(price)
        header += ["footprint_buy_vol", "footprint_sell_vol"]
        row += [f"{fp_now.get('buy_volume', 0.0):.1f}", f"{fp_now.get('sell_volume', 0.0):.1f}"]

        # 2026-08-23 - HVN/LVN (High/Low Volume Node) nearest to current
        # price, from the Pavlovic/Fabio bootcamp material Dadang studied:
        # HVN = price tends to stall/bounce (thick, already-defended area),
        # LVN = price tends to slip through fast (thin/skipped area). Same
        # append-at-end convention as sweep/footprint above - column position
        # of every earlier field stays untouched.
        hvn_lvn = volume_profile.get_hvn_lvn(price)
        header += ["hvn_price", "hvn_volume", "lvn_price", "lvn_volume"]
        row += [f"{hvn_lvn['hvn_price']:.2f}", f"{hvn_lvn['hvn_volume']:.1f}",
                f"{hvn_lvn['lvn_price']:.2f}", f"{hvn_lvn['lvn_volume']:.1f}"]

        tmp = MT5_BRIDGE_FILE + ".tmp"
        with open(tmp, "w", encoding="ascii", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerow(row)
        os.replace(tmp, MT5_BRIDGE_FILE)
    except Exception as e:
        print(f"[UDP-Listener] MT5 bridge write failed (non-fatal): {e}", flush=True)


def write_mt5_macro_file(macro_state: dict):
    """Standalone 2-row CSV for the EA's MACRO panel row. Deliberately kept
    out of bookmap_live_signal.csv - see the MT5_MACRO_FILE note above."""
    try:
        header = ["timestamp", "active", "alias", "price", "change",
                  "direction", "usd", "cvd", "flow_confirms", "verdict"]
        row = [
            f"{time.time():.2f}",
            "1" if macro_state.get("active") else "0",
            str(macro_state.get("alias", ""))[:24],
            f"{macro_state.get('price', 0.0):.5f}",
            f"{macro_state.get('change', 0.0):.5f}",
            str(macro_state.get("direction", "")),
            str(macro_state.get("usd", "")),
            f"{macro_state.get('cvd', 0.0):.1f}",
            "1" if macro_state.get("flow_confirms") else "0",
            str(macro_state.get("verdict", "")),
        ]
        tmp = MT5_MACRO_FILE + ".tmp"
        with open(tmp, "w", encoding="ascii", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerow(row)
        os.replace(tmp, MT5_MACRO_FILE)
    except Exception as e:
        print(f"[UDP-Listener] MT5 macro write failed (non-fatal): {e}", flush=True)


def log_cvd_history(result: dict, price: float, h4_cmp: str):
    """Append one throttled row (every CVD_LOG_INTERVAL_SEC) to a per-day CSV
    in cvd_history/ - starts building the historical dataset that never
    existed before 2026-08-09. Never raises, same reasoning as
    write_mt5_bridge_file().

    2026-08-10 (v29): Dadang: "rekam volume + buy/sell + depth mentah dulu.
    Setelah datanya banyak, baru kita tentukan rumus sideways yang paling
    masuk akal" - deliberately just RECORDING the 3 raw data sources he
    named (volume-at-price -> poc/ratio, buy/sell -> session volumes,
    order book -> top-of-book depth) here, no trend/sideways formula built
    on top yet."""
    global _last_cvd_log_ts
    now = time.time()
    if now - _last_cvd_log_ts < CVD_LOG_INTERVAL_SEC:
        return
    _last_cvd_log_ts = now
    try:
        os.makedirs(CVD_LOG_DIR, exist_ok=True)
        day_str = datetime.fromtimestamp(now, tz=WIB).strftime("%Y-%m-%d")
        path = os.path.join(CVD_LOG_DIR, f"{CVD_LOG_FILE_PREFIX}{day_str}.csv")
        is_new = not os.path.exists(path)
        absorption_status = (result.get("absorption") or {}).get("status", "NONE")
        vol_snap = result.get("volume_profile") or {}
        iceberg_snap = result.get("iceberg") or {}
        bid_ice = iceberg_snap.get("bid_iceberg") or {}
        ask_ice = iceberg_snap.get("ask_iceberg") or {}
        best_bid = max(market_data.bids_depth) if market_data.bids_depth else 0.0
        best_bid_sz = market_data.bids_depth.get(best_bid, 0.0) if best_bid else 0.0
        best_ask = min(market_data.asks_depth) if market_data.asks_depth else 0.0
        best_ask_sz = market_data.asks_depth.get(best_ask, 0.0) if best_ask else 0.0
        # v52.4: full wall ladder, same near+historical merge as the live
        # bridge file - see write_mt5_bridge_file() above for why (Dadang:
        # "wall dimanapun harus terbaca DAN harus kerecord juga").
        wall_ladder = result.get("wall_ladder") or {}
        bid_slots = _merge_wall_slots(wall_ladder.get("bids"), wall_ladder.get("historical_bids"),
                                       WALL_NEAR_SLOTS_PER_SIDE, WALL_HIST_SLOTS_PER_SIDE)
        ask_slots = _merge_wall_slots(wall_ladder.get("asks"), wall_ladder.get("historical_asks"),
                                       WALL_NEAR_SLOTS_PER_SIDE, WALL_HIST_SLOTS_PER_SIDE)
        with open(path, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if is_new:
                header = ["timestamp_utc", "time_wib", "price", "cvd_session", "pulse_pct", "absorption", "h4_cmp",
                          "poc_price", "poc_volume", "vol_ratio_buy_pct", "buy_vol_session", "sell_vol_session",
                          "val", "vah",
                          "best_bid_px", "best_bid_sz", "best_ask_px", "best_ask_sz",
                          "bid_ice_px", "bid_ice_sz", "bid_ice_ratio",
                          "ask_ice_px", "ask_ice_sz", "ask_ice_ratio"]
                for i in range(1, len(bid_slots) + 1):
                    header += [f"bid{i}_px", f"bid{i}_sz", f"bid{i}_age"]
                for i in range(1, len(ask_slots) + 1):
                    header += [f"ask{i}_px", f"ask{i}_sz", f"ask{i}_age"]
                header += ["sweep_side", "sweep_price", "sweep_size", "sweep_age_at_sweep_sec",
                           "sweep_status", "sweep_since_sec"]
                header += ["mega_sweep_active", "mega_sweep_side", "mega_sweep_count"]
                w.writerow(header)
            row = [
                f"{now:.2f}",
                datetime.fromtimestamp(now, tz=WIB).strftime("%H:%M:%S"),
                f"{price:.2f}",
                f"{result.get('cvd_30s', 0.0):.2f}",
                f"{result.get('buyer_aggression_pct', 0.0):.2f}",
                absorption_status,
                h4_cmp,
                f"{vol_snap.get('poc_price', 0.0):.2f}",
                f"{vol_snap.get('poc_volume', 0.0):.1f}",
                f"{vol_snap.get('volume_ratio_buy_pct', 50.0):.1f}",
                f"{vol_snap.get('session_buy_volume', 0.0):.1f}",
                f"{vol_snap.get('session_sell_volume', 0.0):.1f}",
                f"{vol_snap.get('val', 0.0):.2f}",
                f"{vol_snap.get('vah', 0.0):.2f}",
                f"{best_bid:.2f}", f"{best_bid_sz:.1f}", f"{best_ask:.2f}", f"{best_ask_sz:.1f}",
                f"{bid_ice.get('price', 0.0):.2f}", f"{bid_ice.get('displayed_size', 0.0):.1f}", f"{bid_ice.get('ratio', 0.0):.2f}",
                f"{ask_ice.get('price', 0.0):.2f}", f"{ask_ice.get('displayed_size', 0.0):.1f}", f"{ask_ice.get('ratio', 0.0):.2f}",
            ]
            for w_ in bid_slots:
                row += [f"{w_[0]:.2f}", f"{w_[1]:.1f}", f"{(w_[2] if len(w_) > 2 else 0):.0f}"]
            for w_ in ask_slots:
                row += [f"{w_[0]:.2f}", f"{w_[1]:.1f}", f"{(w_[2] if len(w_) > 2 else 0):.0f}"]
            sweep = (result.get("wall_sweep") or {}).get("latest")
            if sweep:
                row += [sweep.get("side", ""), f"{sweep.get('price', 0.0):.2f}", f"{sweep.get('size', 0.0):.1f}",
                        f"{sweep.get('age_at_sweep', 0):.0f}", sweep.get("status", "NONE"),
                        f"{(now - sweep.get('swept_time', now)):.0f}"]
            else:
                row += ["", "0.00", "0.0", "0", "NONE", "0"]
            mega = result.get("wall_sweep", {}).get("mega") or {}
            row += [int(bool(mega.get("active"))), mega.get("side", ""), mega.get("count", 0)]
            w.writerow(row)
    except Exception as e:
        print(f"[UDP-Listener] CVD history log failed (non-fatal): {e}", flush=True)


def handle_payload(payload: dict):
    ptype = payload.get("type")

    # 2026-08-13: bookmap_bridge.py has ALWAYS tagged every payload with the
    # instrument "alias", but nothing here ever read it - every trade/depth
    # message went straight into the gold engines regardless of which tab it
    # came from. That was harmless while only GCZ6 was subscribed, but the
    # moment a second instrument is attached (6E, at ~1.159 vs gold's ~4450)
    # its prices would silently poison the volume profile, POC, wall map and
    # CVD - no error, just wrong numbers. Routing by alias closes that hole
    # BEFORE the second instrument is attached, not after.
    alias = payload.get("alias", "")
    if macro.matches(alias):
        if ptype == "trade":
            macro.on_trade(alias, payload["price"], payload["size"],
                           payload["is_bid"], time.time())
        # depth from the macro instrument is intentionally dropped - the wall
        # engine's thresholds are calibrated for gold's thin book, not 6E's.
        return

    if ptype == "trade":
        price = payload["price"]
        size = payload["size"]
        is_bid = payload["is_bid"]
        # Bookmap docs: is_bid == True means the trade WAS a buy (aggressor bought).
        # NOT "traded at the bid price" - that assumption was backwards and inverted
        # our CVD/Pulse sign vs Bookmap's own widgets. Confirmed against
        # github.com/BookmapAPI/python-api trades handler docs.
        is_buyer_taker = is_bid
        now = time.time()
        market_data.on_trade(price, size)
        cvd_engine.on_trade(price, size, is_buyer_taker, now)
        market_pulse.on_trade(price, size, is_buyer_taker, now)
        footprint_engine.on_trade(price, size, is_buyer_taker, now)
        volume_profile.on_trade(price, size, is_buyer_taker, now)
        iceberg_engine.on_trade(price, size, now)
        bar_aggregator.on_trade(price, now)
    elif ptype == "depth":
        market_data.on_depth(payload["is_bid"], payload["price"], payload["size"])
        iceberg_engine.on_depth(payload["is_bid"], payload["price"], payload["size"])
    elif ptype == "instrument":
        print(f"[UDP-Listener] Instrument: {payload.get('alias')}", flush=True)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(WRITE_INTERVAL_SEC)
    print(f"[UDP-Listener] Listening on {UDP_IP}:{UDP_PORT} (from bookmap_bridge.py)", flush=True)
    print(f"[UDP-Listener] Writing -> {STATUS_FILE}", flush=True)

    last_write = 0.0
    trade_count = 0
    try:
        while True:
            try:
                data, _addr = sock.recvfrom(65536)
                payload = json.loads(data.decode("utf-8"))
                handle_payload(payload)
                if payload.get("type") == "trade":
                    trade_count += 1
            except socket.timeout:
                pass
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[UDP-Listener] bad payload: {e}", flush=True)

            now = time.time()
            if now - last_write >= WRITE_INTERVAL_SEC:
                last_write = now
                try:
                    reconcile_broker_position()
                    # v37: TradingView/Pine retired (Dadang: "tv sudah tidak
                    # kita butuhkan") - apply_mt5_overlay() reads MT5's own
                    # DD_CMP_Indicator (via sultan_status.json, EA v34+)
                    # instead. Only gives CMP direction, not VR/CF/action
                    # text (DD_CMP_Indicator.mq5 doesn't track that state) -
                    # overlaid TFs' vr/cf columns stay at TFState's own
                    # default ("-") instead of Pine's fuller text. Accepted
                    # tradeoff, see apply_mt5_overlay()'s docstring.
                    overlaid = apply_mt5_overlay()
                    prev_position = dict(master_engine.active_position) if master_engine.active_position else None
                    result = master_engine.evaluate()
                    handle_mt5_auto_execute(prev_position, result)
                    result["updated_at"] = now
                    result["mt5_overlay_active"] = sorted(overlaid)

                    # Macro correlation (6E as a dollar proxy) - informational
                    # only, per Dadang: "hanya tambahan informasi aja bro".
                    # Phrased against whatever direction the engine is currently
                    # working so the verdict reads as SEARAH / LAWAN.
                    try:
                        gold_dir = (result.get("recommendation") or "").upper()
                        if gold_dir not in ("BUY", "SELL"):
                            gold_dir = ""
                        result["macro"] = macro.get_state(gold_dir)
                        write_mt5_macro_file(result["macro"])
                    except Exception as e:
                        result["macro"] = {"active": False, "reason": f"error: {e}"}

                    # M1 isn't part of the CMPDetector/TFState cascade (it's the TF that
                    # FORMS M5, not a doctrine step on its own) - Dadang: "m1 sebenernya
                    # ada karena m1 pembentuk m5". Informational only, straight
                    # passthrough - now from MT5's own DD_CMP_Indicator (v37, was Pine).
                    try:
                        with open(MT5_STATUS_FILE, "r", encoding="ascii") as f:
                            mt5_status_for_m1 = json.load(f)
                        m1_dir = (mt5_status_for_m1.get("regime", {}).get("m1") or "").upper()
                    except Exception:
                        m1_dir = ""
                    if m1_dir in ("BUY", "SELL"):
                        result["tf_matrix"]["M1"] = {
                            "cmp": m1_dir, "vr": "-", "cf": "-", "action": "MONITOR", "time": "LIVE",
                        }
                        # Doktrin pembentukan candle fraktal (Dadang): "m5 sell itu pasti
                        # m1 sell dulu... alurannya gitu pembentukan marketnya" - M1 bentuk
                        # M5, M5 bentuk M15, dst (bottom-up, bukan top-down). M1 dipakai
                        # sebagai LEADING indicator eksplisit di alasan live, bukan cuma
                        # baris tabel informational doang.
                        master_dir = doctrine_analyst.states["H4"].cmp
                        if master_dir != "WAIT":
                            if m1_dir == master_dir:
                                result["reason_lines"].append(
                                    f"👣 M1 {m1_dir} (searah H4) - leading indicator, cascade bottom-up udah mulai")
                            else:
                                result["reason_lines"].append(
                                    f"👣 M1 {m1_dir} (lawan H4 {master_dir}) - cascade bottom-up belum mulai, "
                                    f"M5/M15 belum bisa CF genuine")
                    result["db_stats"] = trade_db.get_stats()
                    result["recent_trades"] = trade_db.get_recent_trades(10)
                    # order_book, spread, m5_bars: built in cr_master_engine.py's
                    # evaluate() from REAL market_data/aggregator state (no
                    # padding, no synthetic fallback candles). A previous
                    # version of this block fabricated fake order book levels
                    # and sine-wave-generated "candles" when real data was
                    # thin - Dadang: "semua data harus dari bookmap bukan
                    # dummy atau palsu." Removed entirely (2026-08-07).
                    result["mt5_bridge"] = mt5_ready

                    # v37: dashboard.html's header showed the RAW GCZ6 futures
                    # price (Bookmap's own instrument) unconverted - Dadang:
                    # "harga yang di web harus ke konvert ke mt5 juga bro".
                    # Sultan's dashboard already converts (MQL5-side offset);
                    # this brings the same conversion to the old dashboard,
                    # as an ADDITIONAL field - current_price stays the raw
                    # GCZ6 value (write_mt5_bridge_file/log_cvd_history below
                    # still need that untouched for their own offset math).
                    if mt5_ready:
                        xauusd_price = mt5x.get_xauusd_price()
                        if xauusd_price > 0:
                            result["current_price_xauusd"] = round(xauusd_price, 2)

                    # v52.18 (2026-08-17): Dadang - "lo taruh juga di WEB gw dan
                    # webpy gw bro" - same TRENDING+direction / SIDEWAYS regime
                    # already added to the MT5 panel and Sultan web (v52.16/17),
                    # now on this dashboard too. Same H4/M30/M5-must-all-agree
                    # definition (IsRegimeTrending() on the MQL5 side) - reuses
                    # doctrine_analyst.states, which already carries all 6 TFs
                    # (either Bookmap's own tracking or the MT5 overlay above).
                    h4_dir  = doctrine_analyst.states["H4"].cmp
                    m30_dir = doctrine_analyst.states["M30"].cmp
                    m5_dir  = doctrine_analyst.states["M5"].cmp
                    is_trending = h4_dir in ("BUY", "SELL") and h4_dir == m30_dir == m5_dir
                    result["regime"] = {
                        "trending": is_trending,
                        "direction": h4_dir if is_trending else "",
                        "label": f"TRENDING {h4_dir}" if is_trending else "SIDEWAYS",
                    }

                    write_mt5_bridge_file(result, market_data.last_price)
                    log_cvd_history(result, market_data.last_price, doctrine_analyst.states["H4"].cmp)

                    _write_atomic(STATUS_FILE, result)

                    max_bid = max(market_data.bids_depth.values()) if market_data.bids_depth else 0
                    max_ask = max(market_data.asks_depth.values()) if market_data.asks_depth else 0
                    print(f"[UDP-Listener] trades={trade_count} price={market_data.last_price} "
                          f"H4={doctrine_analyst.states['H4'].cmp} rec={result['recommendation']} "
                          f"depth_levels(bid={len(market_data.bids_depth)},ask={len(market_data.asks_depth)}) "
                          f"max_size(bid={max_bid:.0f},ask={max_ask:.0f}) "
                          f"mt5_overlay={sorted(overlaid) or 'none'} "
                          f"mt5={'on' if mt5_ready else 'OFF'} db={result['db_stats']}", flush=True)
                except Exception as e:
                    print(f"[UDP-Listener] evaluate error: {e}", flush=True)
    except KeyboardInterrupt:
        print("[UDP-Listener] Stopped.", flush=True)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
