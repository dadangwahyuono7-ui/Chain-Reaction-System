# Chain Reaction - Bookmap Bridge Addon V2 (Smart S&D Zone Engine).
# Additional addon, loaded alongside bookmap_addon.py / bookmap_bridge.py.
# Writes to live_status_v2.json (separate from V1's live_status.json).

import time
import json
import os
import sys

# Bookmap copies this file into an isolated sandbox folder before running
# it, so sibling imports need a fixed path, not one derived from __file__.
sys.path.insert(0, r"C:\Bookmap\Python")

try:
    import bookmap as bm
    BOOKMAP_AVAILABLE = True
except ImportError:
    BOOKMAP_AVAILABLE = False
    print("[CR-Bridge-V2] Warning: 'bookmap' package not found. Running in standalone mode.")

from market_data_engine_v2 import MarketDataEngine
from cvd_engine_v2 import CVDEngine
from market_pulse_engine_v2 import MarketPulseEngine
from volume_profile_engine_v2 import VolumeProfileEngine
from iceberg_engine_v2 import IcebergEngine
from cmp_engine_v2 import MultiTFAggregator, BookmapDoctrineAnalyst
from cr_master_engine_v2 import CRDecisionRecommendationEngine
from zone_engine import ZoneEngine

STATUS_FILE = os.path.join(r"C:\Bookmap\Python", "live_status_v2.json")

# Same shared file V1's apply_mt5_overlay()/get_xauusd_price() read (already
# safe to read here - EA writes it every ~1s, nobody else writes it). Used
# only to compute the GCZ6-futures-to-XAUUSD-spot offset below, never to
# gate anything - if MT5 isn't running this cycle we just skip the offset.
MT5_STATUS_FILE = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files\sultan_status.json"

# Written every cycle so a NEW, separate EA (DD_ChainReaction_ZoneEngine_v2.mq5
# - never the production EA) can draw these zones directly on Dadang's MT5
# chart. Plain CSV, not JSON - matches the existing bookmap_live_signal.csv
# convention the production EA already reads via FileOpen(FILE_CSV|
# FILE_COMMON), which MQL5 parses natively with FileReadString(); MQL5 has no
# built-in JSON parser. One line per zone (no header - variable row count,
# a header would just be one more line the reader has to know to skip):
# side,lo,hi,wall_count,total_lot,status,retest_count,absorption_hits,score
ZONES_FILE = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files\zones_v2.csv"

market_data = MarketDataEngine()
cvd_engine = CVDEngine()
market_pulse = MarketPulseEngine()
volume_profile = VolumeProfileEngine()
iceberg_engine = IcebergEngine()
bar_aggregator = MultiTFAggregator()
doctrine_analyst = BookmapDoctrineAnalyst(bar_aggregator, master_tf="H4")
master_engine = CRDecisionRecommendationEngine(doctrine_analyst, cvd_engine, market_pulse, market_data,
                                                volume_profile=volume_profile, iceberg_engine=iceberg_engine)
zone_engine = ZoneEngine()

alias_to_multiplier = {}
alias_to_pips = {}
request_id_to_indicator_type = {}
alias_to_indicator_ids = {}
req_id_counter = 100

WALL_LADDER_DEPTH = 20


# Bookmap's actual API calls this with 8 args (addon, alias, fullname,
# is_crypto, pips, size_multiplier, instrument_multiplier,
# supported_features) - confirmed from bookmap.py's
# _get_default_add_instrument_handler(). The old 4-arg signature crashed
# with "takes 4 positional arguments but 8 were given".
def handle_subscribe_instrument(addon, alias, fullname, is_crypto, pips, size_multiplier,
                                 instrument_multiplier, supported_features):
    alias_to_multiplier[alias] = size_multiplier
    # Bookmap sends trade/depth price as a raw tick count, not a dollar
    # value ("it is relative value, to get actual value multiply it by
    # pips" - Bookmap's own simple_market_maker.py example). Confirmed
    # live: raw price read 47251.99999999999 == 4725.2 * 10 (float rounding
    # signature), i.e. pips == 0.1 for GCZ6 - stored per-alias so
    # handle_trades/handle_depth_info can convert to real price at ingestion.
    alias_to_pips[alias] = pips if pips > 0 else 1.0
    print(f"[CR-Bridge-V2] Subscribed to {alias}", flush=True)

    # add_trades_handler/add_depth_handler above only REGISTER the callback -
    # Bookmap won't actually send trade/depth messages for this alias until
    # the addon explicitly requests them here (ground-truthed against V1's
    # working bookmap_addon.py, which calls these in this same spot). Without
    # this, handle_trades/handle_depth_info never fire even though the addon
    # loads cleanly and on_interval_draw keeps ticking.
    bm.subscribe_to_trades(addon, alias, 1)
    bm.subscribe_to_depth(addon, alias, 2)


# _process_event() calls EVERY registered handler as handler(addon,
# *params) with no exceptions (confirmed by reading _process_event's own
# code directly) - so this needs addon first same as every other handler,
# despite what the type hint alone might suggest.
def handle_unsubscribe_instrument(addon, alias):
    print(f"[CR-Bridge-V2] Unsubscribed from {alias}", flush=True)
    alias_to_multiplier.pop(alias, None)


def handle_trades(addon, alias, price, size, is_otc, is_bid,
                  is_execution_start, is_execution_end, aggressor_order_id, passive_order_id):
    pips = alias_to_pips.get(alias, 1.0)
    native_price = float(price) * pips
    _try_establish_offset(native_price)

    if not offset_ready:
        _buffer_event(("trade", (addon, alias, price, size, is_otc, is_bid,
                                  is_execution_start, is_execution_end,
                                  aggressor_order_id, passive_order_id)))
        return

    _process_trade(addon, alias, price, size, is_otc, is_bid,
                    is_execution_start, is_execution_end, aggressor_order_id, passive_order_id)


def _process_trade(addon, alias, price, size, is_otc, is_bid,
                    is_execution_start, is_execution_end, aggressor_order_id, passive_order_id):
    global gcz6_native_last_price
    multiplier = alias_to_multiplier.get(alias, 1.0)
    pips = alias_to_pips.get(alias, 1.0)
    real_size = float(size) / multiplier
    native_price = float(price) * pips
    gcz6_native_last_price = native_price
    _refresh_mt5_offset(native_price)
    display_price = native_price + mt5_offset
    is_buyer_taker = is_bid
    now = time.time()

    market_data.on_trade(display_price, real_size)
    cvd_engine.on_trade(display_price, real_size, is_buyer_taker, now)
    market_pulse.on_trade(display_price, real_size, is_buyer_taker, now)
    volume_profile.on_trade(display_price, real_size, is_buyer_taker, now)
    iceberg_engine.on_trade(display_price, real_size, now)
    bar_aggregator.on_trade(display_price, now)

    _update_status()


def handle_depth_info(addon, alias, is_bid, price, size):
    pips = alias_to_pips.get(alias, 1.0)
    native_price = float(price) * pips
    _try_establish_offset(native_price)

    if not offset_ready:
        _buffer_event(("depth", (addon, alias, is_bid, price, size)))
        return

    _process_depth(addon, alias, is_bid, price, size)


def _process_depth(addon, alias, is_bid, price, size):
    multiplier = alias_to_multiplier.get(alias, 1.0)
    pips = alias_to_pips.get(alias, 1.0)
    real_size = float(size) / multiplier
    native_price = float(price) * pips
    display_price = native_price + mt5_offset
    market_data.on_depth(is_bid, display_price, real_size)
    iceberg_engine.on_depth(is_bid, display_price, real_size)


# Checked _get_parameters_from_msg() directly (the actual param-parsing
# code, more reliable than the type hints - one of those was ALSO wrong/
# incomplete for INSTRUMENT_INFO above): ON_INTERVAL still sends 1 extra
# param (alias), despite add_on_interval_handler's hint suggesting none.
def on_interval_draw(addon, alias):
    _update_status()


last_disk_write_time = 0.0

# GCZ6 (COMEX futures) never trades at the exact same number as XAUUSD (MT5
# spot CFD) - there's a real, slowly-drifting futures/spot basis, not a bug.
# Dadang: "gw trading di MT5 bukan di Bookmap... bookmap akan gw minimise,
# gw focus ke MT5 dan web kita aja" - so EVERY price this addon produces
# (order book, wall ladder, zones, CVD reference, TF matrix, current_price -
# all of it) needs to already be in MT5 terms, not just the couple of
# fields a display happens to show today. Applying the offset once here, at
# ingestion, means every engine downstream (market_data, cvd_engine,
# volume_profile, iceberg_engine, bar_aggregator, zone_engine) stores and
# outputs MT5-scale prices natively - no per-field patching at the output
# boundary, no risk of missing a field when a new one gets added later.
gcz6_native_last_price = 0.0
mt5_offset = 0.0
_last_offset_refresh = 0.0
OFFSET_REFRESH_SEC = 1.0   # once established, the futures/spot basis drifts slowly - no need to hit the MT5 file every tick

# Bookmap dumps the FULL resting order book the instant the addon subscribes
# (confirmed in Rithmic's own log: a burst of DboBookRebuild callbacks) -
# almost always before mt5_offset has ever been computed from a real MT5
# read. Any price touched only during that first burst (typically the
# biggest, most persistent walls - exactly what the zone engine cares about
# most) would otherwise freeze at the wrong scale forever, since resting
# orders that never change don't get re-sent. Rather than surgically
# remapping six different engines' own price-keyed internals after the fact
# (easy to miss one), every trade/depth event is buffered here UNTOUCHED
# until a real offset is confirmed, then replayed in order - nothing is
# ever handed to an engine at the wrong scale in the first place.
offset_ready = False
_pending_events = []
MAX_PENDING_EVENTS = 5000   # ~a few seconds of ticks - if MT5/EA genuinely never comes up, stop buffering rather than leak memory forever
BOOTSTRAP_POLL_SEC = 0.1    # check fast during bootstrap - OFFSET_REFRESH_SEC's slower 1s cadence only applies once offset_ready


def _read_mt5_xauusd_price():
    """Same read-only file V1 already relies on (EA writes it every ~1s).
    Returns 0.0 on any failure (MT5/EA not running, file mid-write) - caller
    treats that as "not ready yet / keep the last known offset", same
    contract as V1's own get_xauusd_price()."""
    try:
        with open(MT5_STATUS_FILE, encoding="utf-8-sig") as f:
            data = json.load(f)
        price = float(data.get("price", 0.0))
        return price if price > 0 else 0.0
    except Exception:
        return 0.0


def _buffer_event(event):
    _pending_events.append(event)
    if len(_pending_events) > MAX_PENDING_EVENTS:
        # MT5/EA hasn't come up in a genuinely long time - give up waiting
        # and flush at offset 0.0 (raw GCZ6 scale) rather than grow forever.
        # Later ticks keep trying _try_establish_offset() normally; if MT5
        # comes up after this point, only the flushed backlog stays
        # unconverted, not anything going forward.
        print(f"[CR-Bridge-V2] MT5 offset never became available after {MAX_PENDING_EVENTS} ticks - "
              f"flushing buffered events unconverted.", flush=True)
        _replay_pending()
        global offset_ready
        offset_ready = True


def _try_establish_offset(reference_native_price):
    """One-time bootstrap: as soon as a valid MT5 price is readable, lock in
    the first offset, flip offset_ready, and replay everything buffered so
    far through the normal (now offset-aware) processing path."""
    global mt5_offset, offset_ready, _last_offset_refresh
    if offset_ready or reference_native_price <= 0:
        return
    now = time.time()
    if now - _last_offset_refresh < BOOTSTRAP_POLL_SEC:
        return
    _last_offset_refresh = now
    mt5_price = _read_mt5_xauusd_price()
    if mt5_price <= 0:
        return
    mt5_offset = mt5_price - reference_native_price
    offset_ready = True
    print(f"[CR-Bridge-V2] MT5 offset established: {mt5_offset:+.2f} "
          f"(GCZ6 {reference_native_price:.2f} -> MT5 {mt5_price:.2f}) - "
          f"replaying {len(_pending_events)} buffered events", flush=True)
    _replay_pending()


def _replay_pending():
    global _pending_events
    events, _pending_events = _pending_events, []
    for kind, args in events:
        if kind == "trade":
            _process_trade(*args)
        else:
            _process_depth(*args)


def _refresh_mt5_offset(reference_native_price):
    """Keeps mt5_offset current after bootstrap, at most once per
    OFFSET_REFRESH_SEC. On failure (MT5 momentarily unreadable) deliberately
    keeps the last good offset rather than snapping back to 0 - a
    stale-by-a-few-seconds offset is far less confusing than prices suddenly
    jumping back to raw GCZ6 scale."""
    global mt5_offset, _last_offset_refresh
    now = time.time()
    if now - _last_offset_refresh < OFFSET_REFRESH_SEC:
        return
    _last_offset_refresh = now
    if reference_native_price <= 0:
        return
    mt5_price = _read_mt5_xauusd_price()
    if mt5_price > 0:
        mt5_offset = mt5_price - reference_native_price


def _update_status():
    global last_disk_write_time
    now = time.time()

    if now - last_disk_write_time < 0.2:
        return
    last_disk_write_time = now

    master_eval = master_engine.evaluate()

    bid_walls = market_data.get_wall_ladder(True, WALL_LADDER_DEPTH)
    ask_walls = market_data.get_wall_ladder(False, WALL_LADDER_DEPTH)
    absorption_status = (master_eval.get("absorption") or {}).get("status", "NONE")
    display_price = market_data.last_price  # already MT5-scale - offset applied at ingestion

    zones = []
    if display_price > 0:
        zones = zone_engine.update(bid_walls, ask_walls, display_price, absorption_status)

    master_eval["sd_zones"] = zones
    # Diagnostic only - lets us sanity-check the conversion without affecting
    # anything a dashboard would read (current_price above is already correct).
    master_eval["current_price_gcz6_raw"] = round(gcz6_native_last_price, 2)
    master_eval["mt5_offset"] = round(mt5_offset, 2)

    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(master_eval, f, indent=2)
    except Exception:
        pass

    _write_zones_csv(zones)


def _write_zones_csv(zones):
    """Atomic-ish overwrite (tmp + move) so the EA never reads a half-written
    file - same pattern the production EA's own sultan_status.json write
    uses (FileMove after FileDelete)."""
    try:
        tmp_path = ZONES_FILE + ".tmp"
        with open(tmp_path, "w") as f:
            for z in zones:
                f.write(f"{z['side']},{z['lo']},{z['hi']},{z['wall_count']},"
                        f"{z['total_lot']},{z['status']},{z['retest_count']},"
                        f"{z['absorption_hits']},{z['score']}\n")
        os.replace(tmp_path, ZONES_FILE)
    except Exception:
        pass


if __name__ == "__main__":
    if BOOKMAP_AVAILABLE:
        addon = bm.create_addon()
        bm.add_trades_handler(addon, handle_trades)
        bm.add_depth_handler(addon, handle_depth_info)
        bm.add_on_interval_handler(addon, on_interval_draw)
        bm.start_addon(addon, handle_subscribe_instrument, handle_unsubscribe_instrument)
        bm.wait_until_addon_is_turned_off(addon)
    else:
        print("Bookmap module unavailable.")
