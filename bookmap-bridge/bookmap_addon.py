"""
Chain Reaction - Bookmap Bridge Addon (v8 - Pure Bookmap Edition)
Location: bookmap-bridge/bookmap_addon.py

CMP is computed ENTIRELY from Bookmap's own live tick stream (cmp_engine.py) -
no MT5, no TradingView, no external platform. Bookmap's L1 Python API has NO
historical-bars endpoint (confirmed: github.com/BookmapAPI/python-api), so
candle history builds up live from the moment this addon is loaded. M5-H1
warm up in minutes/hours; H4 needs ~12h; D1 needs ~3 days of live ticks
before a CMP direction exists for that TF. See cmp_engine.py for details.

This file imports its logic from sibling modules in this same folder
(market_data_engine.py, cvd_engine.py, market_pulse_engine.py, cmp_engine.py,
cr_master_engine.py) instead of embedding duplicate copies - single source
of truth, no risk of the two copies drifting out of sync.
"""

import time
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import bookmap as bm
    BOOKMAP_AVAILABLE = True
except ImportError:
    BOOKMAP_AVAILABLE = False
    print("[CR-Bridge] Warning: 'bookmap' package not found. Running in standalone mode.")

from market_data_engine import MarketDataEngine
from cvd_engine import CVDEngine
from market_pulse_engine import MarketPulseEngine
from volume_profile_engine import VolumeProfileEngine
from iceberg_engine import IcebergEngine
from cmp_engine import MultiTFAggregator, BookmapDoctrineAnalyst
from cr_master_engine import CRDecisionRecommendationEngine

STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_status.json")

# =====================================================================
# GLOBAL STATE
# =====================================================================
market_data = MarketDataEngine()
cvd_engine = CVDEngine()
market_pulse = MarketPulseEngine()
volume_profile = VolumeProfileEngine()
iceberg_engine = IcebergEngine()
bar_aggregator = MultiTFAggregator()
doctrine_analyst = BookmapDoctrineAnalyst(bar_aggregator, master_tf="H4")
master_engine = CRDecisionRecommendationEngine(doctrine_analyst, cvd_engine, market_pulse, market_data,
                                                volume_profile=volume_profile, iceberg_engine=iceberg_engine)

alias_to_multiplier = {}
request_id_to_indicator_type = {}
alias_to_indicator_ids = {}
req_id_counter = 100


# =====================================================================
# BOOKMAP API CALLBACK HANDLERS
# =====================================================================
def handle_subscribe_instrument(addon, alias: str, full_name: str, is_crypto: bool, pips: float,
                                size_multiplier: float, instrument_multiplier: float, supported_features: dict):
    global req_id_counter, alias_to_multiplier, request_id_to_indicator_type, alias_to_indicator_ids

    print(f"[CR-Bridge] Subscribed to instrument: {alias} ({full_name})", flush=True)
    alias_to_multiplier[alias] = size_multiplier if size_multiplier > 0 else 1.0
    alias_to_indicator_ids[alias] = {}

    req_id_counter += 1
    request_id_to_indicator_type[req_id_counter] = (alias, "CVD")
    bm.register_indicator(addon, alias, req_id_counter, "CR CVD Delta (5m)", "BOTTOM", color=(0, 200, 255))

    req_id_counter += 1
    request_id_to_indicator_type[req_id_counter] = (alias, "PULSE")
    bm.register_indicator(addon, alias, req_id_counter, "CR Buyer Aggression %", "BOTTOM", color=(255, 200, 0))

    req_id_counter += 1
    request_id_to_indicator_type[req_id_counter] = (alias, "ZONE_HIGH")
    bm.register_indicator(addon, alias, req_id_counter, "CR H4 CMP Resistance (live, pure Bookmap)", "MAIN_CHART", color=(255, 215, 0))

    req_id_counter += 1
    request_id_to_indicator_type[req_id_counter] = (alias, "ZONE_LOW")
    bm.register_indicator(addon, alias, req_id_counter, "CR H4 CMP Support (live, pure Bookmap)", "MAIN_CHART", color=(255, 215, 0))

    req_id_counter += 1
    request_id_to_indicator_type[req_id_counter] = (alias, "BID_WALL")
    bm.register_indicator(addon, alias, req_id_counter, "CR Bid Wall (Liquidity)", "MAIN_CHART", color=(0, 255, 255))

    req_id_counter += 1
    request_id_to_indicator_type[req_id_counter] = (alias, "ASK_WALL")
    bm.register_indicator(addon, alias, req_id_counter, "CR Ask Wall (Liquidity)", "MAIN_CHART", color=(255, 140, 0))

    bm.subscribe_to_trades(addon, alias, 1)
    bm.subscribe_to_depth(addon, alias, 2)


def handle_unsubscribe_instrument(addon, alias: str):
    print(f"[CR-Bridge] Unsubscribed from {alias}", flush=True)
    alias_to_multiplier.pop(alias, None)
    alias_to_indicator_ids.pop(alias, None)


def handle_register_indicator_response(addon, request_id: int, indicator_id: int):
    if request_id in request_id_to_indicator_type:
        alias, ind_type = request_id_to_indicator_type[request_id]
        if alias in alias_to_indicator_ids:
            alias_to_indicator_ids[alias][ind_type] = indicator_id
            print(f"[CR-Bridge] Indicator '{ind_type}' assigned ID {indicator_id} for {alias}", flush=True)


def handle_trades(addon, alias: str, price: float, size: int, is_otc: bool, is_bid: bool,
                  is_execution_start: bool, is_execution_end: bool, aggressor_order_id: str, passive_order_id: str):
    multiplier = alias_to_multiplier.get(alias, 1.0)
    real_size = float(size) / multiplier
    is_buyer_taker = is_bid  # Bookmap docs: is_bid==True means trade WAS a buy (confirmed via API docs)
    now = time.time()

    market_data.on_trade(price, real_size)
    cvd_engine.on_trade(price, real_size, is_buyer_taker, now)
    market_pulse.on_trade(price, real_size, is_buyer_taker, now)
    volume_profile.on_trade(price, real_size, is_buyer_taker, now)
    iceberg_engine.on_trade(price, real_size, now)
    bar_aggregator.on_trade(price, now)  # feeds the pure-Bookmap CMP engine

    _update_chart_indicators(addon, alias)


def handle_depth_info(addon, alias: str, is_bid: bool, price: float, size: int):
    multiplier = alias_to_multiplier.get(alias, 1.0)
    real_size = float(size) / multiplier
    market_data.on_depth(is_bid, price, real_size)
    iceberg_engine.on_depth(is_bid, price, real_size)


def on_interval_draw(addon, alias: str):
    _update_chart_indicators(addon, alias)


last_disk_write_time = 0.0


def _update_chart_indicators(addon, alias: str):
    global last_disk_write_time
    now = time.time()

    # Throttle to once every 200ms (max 5x/sec) to avoid disk I/O / CPU freezing
    if now - last_disk_write_time >= 0.2:
        last_disk_write_time = now
        master_eval = master_engine.evaluate()  # runs doctrine_analyst.update() internally
        try:
            with open(STATUS_FILE, "w") as f:
                json.dump(master_eval, f, indent=2)
        except Exception:
            pass

    if alias not in alias_to_indicator_ids:
        return

    ind_map = alias_to_indicator_ids[alias]
    cvd_snap = cvd_engine.get_snapshot()
    pulse_snap = market_pulse.get_pulse()

    if "CVD" in ind_map:
        bm.add_point(addon, alias, ind_map["CVD"], cvd_snap["delta_30s"])
    if "PULSE" in ind_map:
        bm.add_point(addon, alias, ind_map["PULSE"], pulse_snap["buyer_aggression_pct"])

    # Plot live H4 CMP barrier (sup/res), built purely from Bookmap ticks
    h4_state = doctrine_analyst.states.get("H4")
    if h4_state:
        if "ZONE_HIGH" in ind_map and h4_state.res > 0:
            bm.add_point(addon, alias, ind_map["ZONE_HIGH"], h4_state.res)
        if "ZONE_LOW" in ind_map and h4_state.sup > 0:
            bm.add_point(addon, alias, ind_map["ZONE_LOW"], h4_state.sup)

    bid_wall, ask_wall = market_data.get_nearest_walls()
    if bid_wall and "BID_WALL" in ind_map:
        bm.add_point(addon, alias, ind_map["BID_WALL"], bid_wall[0])
    if ask_wall and "ASK_WALL" in ind_map:
        bm.add_point(addon, alias, ind_map["ASK_WALL"], ask_wall[0])


if __name__ == "__main__":
    if BOOKMAP_AVAILABLE:
        addon = bm.create_addon()
        bm.add_trades_handler(addon, handle_trades)
        bm.add_depth_handler(addon, handle_depth_info)
        bm.add_on_interval_handler(addon, on_interval_draw)
        bm.add_indicator_response_handler(addon, handle_register_indicator_response)
        bm.start_addon(addon, handle_subscribe_instrument, handle_unsubscribe_instrument)
        bm.wait_until_addon_is_turned_off(addon)
    else:
        print("Bookmap module unavailable. Run test_master_engine.py for simulation.")
