"""
Chain Reaction - CR Decision Engine (Pure Bookmap Edition, self-contained for Bookmap's
embedded Python API editor)
Canonical source: D:\\PROJECT TRADING\\bookmap-bridge\\cr_decision_engine.py
Author: DADANG WAHYUONO - Chain Reaction System

Separate addon from 'bookmap_bridge.py' (that one is the existing UDP bridge to the
Wall Breakout Engine on port 9000 - untouched, still runs independently).

CMP is computed ENTIRELY from Bookmap's own live tick stream - no MT5, no TradingView,
no external platform. Bookmap's L1 Python API has NO historical-bars endpoint
(confirmed: github.com/BookmapAPI/python-api), so candle history builds up live from
the moment this addon is loaded. M5-H1 warm up in minutes/hours; H4 needs ~12h; D1
needs ~3 days of live ticks before a CMP direction exists for that TF. That's expected,
not a bug - watch H4/D1 manually elsewhere in the meantime.

Same minor-SNR breakout doctrine as DD_CMP_Marker.v6.2.pine / engine/core.py
(isMinorSup/isMinorRes V/A-shape candle-body breakout). Entry = breakout (CF) in a
small TF, confirmed by Bookmap's own order flow (Market Pulse + CVD).

This file is a self-contained bundle of (canonical, importable versions live in
D:\\PROJECT TRADING\\bookmap-bridge\\): market_data_engine.py, cvd_engine.py,
market_pulse_engine.py, cmp_engine.py, cr_master_engine.py, plus the Bookmap glue.
Keep this file in sync with those if the doctrine changes.
"""

import time
import json
import os
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

try:
    import bookmap as bm
    BOOKMAP_AVAILABLE = True
except ImportError:
    BOOKMAP_AVAILABLE = False
    print("[CR-Decision] Warning: 'bookmap' package not found. Running in standalone mode.")

# Shared, absolute path so the standalone dashboard (run from the project folder)
# and this addon (run inside Bookmap's own internal script store) agree on the file,
# regardless of where Bookmap actually keeps its copy of this script.
STATUS_FILE = r"D:\PROJECT TRADING\bookmap-bridge\live_status.json"


# =====================================================================
# 1. MARKET DATA ENGINE
# =====================================================================
class MarketDataEngine:
    def __init__(self):
        self.last_price: float = 0.0
        self.bids_depth: Dict[float, float] = {}
        self.asks_depth: Dict[float, float] = {}
        self.wall_threshold_size: float = 50.0

    def on_trade(self, price: float, size: float):
        if price > 0:
            self.last_price = price

    def on_depth(self, is_bid: bool, price: float, size: float):
        target_map = self.bids_depth if is_bid else self.asks_depth
        if size <= 0:
            target_map.pop(price, None)
        else:
            target_map[price] = size

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


# =====================================================================
# 2. CVD ENGINE
# =====================================================================
class CVDEngine:
    def __init__(self, history_window_sec: float = 60.0):
        self.cumulative_delta: float = 0.0
        self.history_window_sec = history_window_sec
        self.trade_history = deque()

    def on_trade(self, price: float, size: float, is_buyer_taker: bool, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        delta_change = size if is_buyer_taker else -size
        self.cumulative_delta += delta_change
        self.trade_history.append((timestamp, delta_change, self.cumulative_delta))
        cutoff = timestamp - self.history_window_sec
        while self.trade_history and self.trade_history[0][0] < cutoff:
            self.trade_history.popleft()

    def get_window_delta(self, window_sec: float = 30.0) -> float:
        if not self.trade_history:
            return 0.0
        now = self.trade_history[-1][0]
        cutoff = now - window_sec
        start_cvd = self.trade_history[0][2]
        for ts, delta_change, running_cvd in self.trade_history:
            if ts >= cutoff:
                start_cvd = running_cvd - delta_change
                break
        end_cvd = self.trade_history[-1][2]
        return round(end_cvd - start_cvd, 2)

    def get_snapshot(self) -> Dict[str, Any]:
        recent_delta_30s = self.get_window_delta(30.0)
        trend = "BUY_ACCUMULATION" if recent_delta_30s > 5.0 else ("SELL_ACCUMULATION" if recent_delta_30s < -5.0 else "NEUTRAL")
        return {"cumulative_delta": round(self.cumulative_delta, 2), "delta_30s": recent_delta_30s, "cvd_trend": trend}


# =====================================================================
# 3. MARKET PULSE ENGINE
# =====================================================================
class MarketPulseEngine:
    def __init__(self, window_sec: float = 10.0):
        self.window_sec = window_sec
        self.recent_trades = deque()

    def on_trade(self, price: float, size: float, is_buyer_taker: bool, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        self.recent_trades.append((timestamp, size, is_buyer_taker))
        self._clean_old_trades(timestamp)

    def _clean_old_trades(self, current_time: float):
        cutoff = current_time - self.window_sec
        while self.recent_trades and self.recent_trades[0][0] < cutoff:
            self.recent_trades.popleft()

    def get_pulse(self, current_time: float = None) -> Dict[str, Any]:
        if current_time is None:
            current_time = time.time()
        self._clean_old_trades(current_time)
        if not self.recent_trades:
            return {"buyer_aggression_pct": 50.0, "seller_aggression_pct": 50.0}
        total_volume = sum(t[1] for t in self.recent_trades)
        buyer_volume = sum(t[1] for t in self.recent_trades if t[2])
        buyer_pct = round((buyer_volume / total_volume * 100.0), 1) if total_volume > 0 else 50.0
        return {"buyer_aggression_pct": buyer_pct, "seller_aggression_pct": round(100.0 - buyer_pct, 1)}


# =====================================================================
# 4. CMP ENGINE - pure Python, builds OHLC bars from Bookmap's own tick stream
#    (no historical-bars API exists in Bookmap L1 - confirmed against
#    github.com/BookmapAPI/python-api). Same minor-SNR doctrine as
#    engine/core.py CMPDetector / DD_CMP_Marker.v6.2.pine f_get_data().
# =====================================================================
TF_SECONDS = {"M5": 5 * 60, "M15": 15 * 60, "M30": 30 * 60, "H1": 60 * 60, "H4": 4 * 60 * 60, "D1": 24 * 60 * 60}
TF_ORDER = ["D1", "H4", "H1", "M30", "M15", "M5"]
PIP_THRESHOLD = 0.1


class Bar:
    __slots__ = ("time", "open", "high", "low", "close")

    def __init__(self, t: int, o: float):
        self.time = t
        self.open = o
        self.high = o
        self.low = o
        self.close = o

    def update(self, price: float):
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price


class TFBars:
    def __init__(self, tf_seconds: int, max_bars: int = 200):
        self.tf_seconds = tf_seconds
        self.closed: Deque[Bar] = deque(maxlen=max_bars)
        self.current: Optional[Bar] = None

    def on_trade(self, price: float, timestamp: float):
        bucket = int(timestamp // self.tf_seconds) * self.tf_seconds
        if self.current is None:
            self.current = Bar(bucket, price)
        elif bucket == self.current.time:
            self.current.update(price)
        elif bucket > self.current.time:
            self.closed.append(self.current)
            self.current = Bar(bucket, price)

    def rows(self) -> List[Bar]:
        out = list(self.closed)
        if self.current is not None:
            out.append(self.current)
        return out


class MultiTFAggregator:
    def __init__(self, max_bars: int = 200):
        self.tfs: Dict[str, TFBars] = {name: TFBars(secs, max_bars) for name, secs in TF_SECONDS.items()}

    def on_trade(self, price: float, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        for tf in self.tfs.values():
            tf.on_trade(price, timestamp)

    def rows(self, tf_name: str) -> List[Bar]:
        return self.tfs[tf_name].rows()


class CMPDetector:
    @staticmethod
    def get_snr_flip(bars: List[Bar]):
        if len(bars) < 3:
            return 0.0, 0.0
        curr = bars[-2]
        prev = bars[-3]
        sup = res = 0.0
        if prev.open > prev.close and curr.close > curr.open:
            sup = min(prev.open, prev.close)
        if prev.close > prev.open and curr.open > curr.close:
            res = max(prev.close, prev.open)
        return sup, res


class TFState:
    def __init__(self, name: str):
        self.name = name
        self.cmp = "WAIT"
        self.status = "CMP"
        self.vr_occurred = False
        self.vr_change_time = 0
        self.last_parent_cmp = "WAIT"
        self.sup = 0.0
        self.res = 0.0
        self.initialized = False
        self.cmp_change_time = 0
        self.parent_cmp_change_time = 0
        self.cf_fire_time = 0
        self.cf_fail_time = 0
        self.cf_failed = False
        self.cf_count = 0

    def initialize_cmp(self, bars: List[Bar]):
        for i in range(len(bars) - 2, 2, -1):
            temp_sup, temp_res = 0.0, 0.0
            for j in range(i, 2, -1):
                curr, prev = bars[j], bars[j - 1]
                if temp_sup == 0 and prev.open > prev.close and curr.close > curr.open:
                    temp_sup = min(prev.open, prev.close)
                if temp_res == 0 and prev.close > prev.open and curr.open > curr.close:
                    temp_res = max(prev.close, prev.open)
                if temp_sup > 0 and temp_res > 0:
                    break
            c_close = bars[i].close
            if temp_res > 0 and c_close > temp_res + PIP_THRESHOLD:
                self.cmp = "BUY"
                self.sup, self.res = temp_sup, temp_res
                self.cmp_change_time = bars[i].time
                break
            if temp_sup > 0 and c_close < temp_sup - PIP_THRESHOLD:
                self.cmp = "SELL"
                self.sup, self.res = temp_sup, temp_res
                self.cmp_change_time = bars[i].time
                break

    def update(self, bars: List[Bar], parent_cmp: str = "WAIT", parent_change_time: int = 0) -> str:
        if len(bars) < 3:
            return "WAIT"
        if not self.initialized:
            self.initialize_cmp(bars)
            self.initialized = True

        if parent_cmp != self.last_parent_cmp:
            self.parent_cmp_change_time = parent_change_time
            self.vr_occurred = False
            self.last_parent_cmp = parent_cmp
            self.cf_fire_time = 0
            self.cf_fail_time = 0
            self.cf_failed = False
            self.cf_count = 0
        elif parent_change_time > self.parent_cmp_change_time:
            if self.vr_occurred and self.vr_change_time < parent_change_time:
                self.vr_occurred = False
                self.cf_fire_time = 0
                self.cf_fail_time = 0
                self.cf_failed = False
                self.cf_count = 0
            self.parent_cmp_change_time = parent_change_time

        new_sup, new_res = CMPDetector.get_snr_flip(bars)
        if new_sup > 0:
            self.sup = new_sup
        if new_res > 0:
            self.res = new_res

        last_close = bars[-2].close
        if self.res > 0 and last_close > self.res + PIP_THRESHOLD:
            if self.cmp != "BUY":
                self.cmp = "BUY"
                self.cmp_change_time = bars[-2].time
        elif self.sup > 0 and last_close < self.sup - PIP_THRESHOLD:
            if self.cmp != "SELL":
                self.cmp = "SELL"
                self.cmp_change_time = bars[-2].time

        status = "CMP"
        if parent_cmp != "WAIT":
            if self.cmp != parent_cmp and self.cmp != "WAIT":
                if self.cmp_change_time > self.parent_cmp_change_time:
                    if not self.vr_occurred:
                        self.vr_occurred = True
                        self.vr_change_time = self.cmp_change_time
                    if (self.cf_fire_time > 0 and not self.cf_failed and
                            self.cmp_change_time > self.cf_fire_time):
                        self.cf_failed = True
                        self.cf_fail_time = self.cmp_change_time
                    status = "VR"
            elif self.cmp == parent_cmp:
                vr_in_current_cycle = self.vr_change_time > self.parent_cmp_change_time
                is_fresh_cf = self.cmp_change_time > self.cf_fail_time
                if (self.vr_occurred and vr_in_current_cycle and
                        self.cmp_change_time > self.vr_change_time and is_fresh_cf):
                    status = "CF"
                    if self.cmp_change_time > self.cf_fire_time:
                        self.cf_fire_time = self.cmp_change_time
                        self.cf_failed = False
                        self.cf_count += 1
                else:
                    status = "CMP"
                    self.vr_occurred = False

        self.status = status
        return status


class BookmapDoctrineAnalyst:
    def __init__(self, aggregator: MultiTFAggregator, master_tf: str = "H4"):
        self.aggregator = aggregator
        self.master_tf = master_tf
        self.tf_order = TF_ORDER
        self.states: Dict[str, TFState] = {name: TFState(name) for name in self.tf_order}

    def update(self) -> Dict[str, TFState]:
        master_idx = self.tf_order.index(self.master_tf)
        context_parent_cmp, context_parent_time = "WAIT", 0
        chain_parent_cmp, chain_parent_time = "WAIT", 0

        for i, name in enumerate(self.tf_order):
            bars = self.aggregator.rows(name)
            if len(bars) < 3:
                continue
            if i < master_idx:
                self.states[name].update(bars, context_parent_cmp, context_parent_time)
                context_parent_cmp = self.states[name].cmp
                context_parent_time = self.states[name].cmp_change_time
            elif i == master_idx:
                self.states[name].update(bars, context_parent_cmp, context_parent_time)
                self.states[name].status = "MASTER"
                chain_parent_cmp = self.states[name].cmp
                chain_parent_time = self.states[name].cmp_change_time
            else:
                self.states[name].update(bars, chain_parent_cmp, chain_parent_time)
                chain_parent_cmp = self.states[name].cmp
                chain_parent_time = self.states[name].cmp_change_time
        return self.states

    def get_strike_signal(self) -> Optional[Dict[str, Any]]:
        h4, h1, m30, m15, m5 = (self.states[n] for n in ("H4", "H1", "M30", "M15", "M5"))
        direction = h4.cmp
        if direction == "WAIT":
            return None

        h1_is_vr = (h1.cmp != direction and h1.cmp != "WAIT" and h1.cmp_change_time > h4.cmp_change_time)

        if m30.cmp == direction and m30.cmp != "WAIT":
            m15_is_vr = (m15.cmp != direction and m15.cmp != "WAIT" and m15.cmp_change_time > m30.cmp_change_time)
            m15_solid = (m15.cmp == direction and m15.cmp != "WAIT" and not m15_is_vr)
            m30_stable = not (m15_is_vr and m30.cmp_change_time > m15.cmp_change_time)

            if m15_solid:
                if (m5.vr_occurred and m5.cmp == direction and
                        m5.cmp_change_time > m5.vr_change_time and
                        m5.cmp_change_time > m15.cmp_change_time and
                        m5.cmp_change_time > m5.cf_fail_time):
                    return {"action": direction, "type": "MINOR_CF", "tf": "M5", "tp_tf": "M15", "sl_tf": "M5",
                            "grade": "C", "reason": "Minor CF: M30+M15 solid | M5 VR->CF"}
            elif m15_is_vr and m30_stable:
                if (m15.vr_occurred and m15.cmp == direction and
                        m15.cmp_change_time > m15.vr_change_time and
                        m15.cmp_change_time > m15.cf_fail_time):
                    return {"action": direction, "type": "CF_LOW", "tf": "M15", "tp_tf": "M30", "sl_tf": "M15",
                            "grade": "A", "reason": "CF Low: M30 solid | M15 VR->CF"}
                if (m5.vr_occurred and m5.cmp == direction and
                        m5.cmp_change_time > m15.cmp_change_time and
                        m5.cmp_change_time > m5.vr_change_time and
                        m5.cmp_change_time > m5.cf_fail_time):
                    return {"action": direction, "type": "CF_HIGH", "tf": "M5", "tp_tf": "M30", "sl_tf": "M15",
                            "grade": "B", "reason": "CF High: M30 solid | M15 VR | M5 CF"}

        if (h1_is_vr and m30.cmp == direction and m30.cmp != "WAIT" and
                m30.cmp_change_time > h1.cmp_change_time and
                m30.cmp_change_time > m30.cf_fail_time):
            return {"action": direction, "type": "H4_CF_HIGH", "tf": "M30", "tp_tf": "H4", "sl_tf": "H1",
                    "grade": "A", "reason": f"H4 {direction} | H1 VR | M30 CF HIGH"}
        return None

    def get_watch_reason(self) -> str:
        h4 = self.states["H4"]
        if h4.cmp == "WAIT":
            n = len(self.aggregator.rows("H4"))
            return f"H4 (master) warm-up: {n} candle H4 terkumpul dari live tick, butuh breakout pertama"
        m30 = self.states["M30"]
        if m30.cmp != h4.cmp:
            return f"M30 VR ke H4 ({h4.cmp}) - tunggu CF di M15/M5"
        m15 = self.states["M15"]
        if m15.cmp != m30.cmp:
            return f"H4+M30 solid ({h4.cmp}) | M15 VR - tunggu CF di M5 (CF HIGH) atau M15 balik (CF LOW)"
        return f"H4+M30+M15 solid ({h4.cmp}) - tunggu M5 VR->CF (MINOR CF)"


# =====================================================================
# 5. DECISION RECOMMENDATION ENGINE
# =====================================================================
TF_LABEL = {"D1": "D", "H4": "H4", "H1": "H1", "M30": "M30", "M15": "M15", "M5": "M5"}


class CRDecisionRecommendationEngine:
    def __init__(self, doctrine: BookmapDoctrineAnalyst, cvd_engine: CVDEngine,
                 market_pulse: MarketPulseEngine, market_data: MarketDataEngine):
        self.doctrine = doctrine
        self.cvd_engine = cvd_engine
        self.market_pulse = market_pulse
        self.market_data = market_data

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
                action = "* MASTER"
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
        cvd_30s = self.cvd_engine.get_window_delta(30.0)
        buyer_agg_pct = self.market_pulse.get_pulse()["buyer_aggression_pct"]
        bid_wall, ask_wall = self.market_data.get_nearest_walls()

        h4_dir = self.doctrine.states["H4"].cmp
        strike = self.doctrine.get_strike_signal()
        tf_matrix = self._build_tf_matrix()

        pulse_side = "BUY" if buyer_agg_pct >= 50.0 else "SELL"
        cvd_side = "BUY" if cvd_30s >= 0.0 else "SELL"

        if h4_dir == "WAIT":
            recommendation = "WAIT"
            status_badge = "WAIT"
            n = len(self.doctrine.aggregator.rows("H4"))
            reason_lines = [
                "H4 (master) masih WARM-UP",
                f"  - {n} candle H4 terkumpul dari live tick Bookmap - butuh breakout pertama buat nentuin arah",
                "  - Bookmap gak punya history candle lama, jadi ini dibangun dari nol sejak addon di-load",
            ]
            conclusion = "CMP murni dari tick Bookmap, belum ada arah H4. SABAR sampai warm-up kelar."
        elif not strike:
            recommendation = "WAIT"
            status_badge = "WAIT"
            reason_lines = [
                f"H4 CMP: {h4_dir}",
                "Belum ada breakout (CF) di TF kecil - MONITORING",
                f"Market Pulse: {buyer_agg_pct:.1f}% ({pulse_side})",
                f"CVD Delta: {cvd_30s:+.1f} ({cvd_side})",
                f"Watch: {self.doctrine.get_watch_reason()}",
            ]
            conclusion = "Belum ada breakout confirm di sub-chain. SABAR."
        else:
            action = strike["action"]
            flow_agrees = (pulse_side == cvd_side == action)
            reason_lines = [
                f"H4 CMP: {h4_dir}",
                f"Breakout: {strike['type']} @ {strike['tf']} -> {strike['reason']}",
                f"Market Pulse: {buyer_agg_pct:.1f}% ({pulse_side})",
                f"CVD Delta: {cvd_30s:+.1f} ({cvd_side})",
            ]
            if flow_agrees:
                recommendation = action
                status_badge = "BUY" if action == "BUY" else "SELL"
                reason_lines.append("Order Flow MENDUKUNG arah breakout")
                conclusion = (f"Breakout {strike['type']} di {strike['tf']} DIDUKUNG order flow "
                              f"({pulse_side}/{cvd_side}). ENTRI {action}. Grade: {strike.get('grade', '-')}")
            else:
                recommendation = "WAIT"
                status_badge = "WAIT"
                reason_lines.append(f"Order Flow BELUM align ke {action} (Pulse={pulse_side}, CVD={cvd_side})")
                conclusion = f"Breakout {strike['type']} ada tapi order flow belum dukung {action}. TUNGGU."

        wall_summary = "No Nearby Wall"
        target_advice = "Normal TP"
        sizing_advice = "Full Position Size"
        if recommendation == "BUY" and ask_wall:
            dist_ticks = abs(ask_wall[0] - current_price) / 0.1
            if dist_ticks <= 10:
                wall_summary = f"Ask Wall Near @ {ask_wall[0]:.2f} ({ask_wall[1]:.0f} contracts, {dist_ticks:.0f} ticks away)"
                target_advice = "Target Dekat (Conservative TP @ Ask Wall)"
                sizing_advice = "Normal Position Size"
            else:
                wall_summary = f"Ask Wall Far @ {ask_wall[0]:.2f} ({ask_wall[1]:.0f} contracts)"
        elif recommendation == "SELL" and bid_wall:
            dist_ticks = abs(current_price - bid_wall[0]) / 0.1
            if dist_ticks <= 10:
                wall_summary = f"Bid Wall Near @ {bid_wall[0]:.2f} ({bid_wall[1]:.0f} contracts, {dist_ticks:.0f} ticks away)"
                target_advice = "Target Dekat (Conservative TP @ Bid Wall)"
                sizing_advice = "Reduce Position Size (Kurangi Lot)"
            else:
                wall_summary = f"Bid Wall Far @ {bid_wall[0]:.2f} ({bid_wall[1]:.0f} contracts)"

        return {
            "recommendation": recommendation, "status_badge": status_badge, "reason_lines": reason_lines,
            "conclusion": conclusion, "wall_summary": wall_summary, "target_advice": target_advice,
            "sizing_advice": sizing_advice, "current_price": current_price,
            "buyer_aggression_pct": buyer_agg_pct, "cvd_30s": cvd_30s, "tf_matrix": tf_matrix,
        }


# =====================================================================
# 6. GLOBAL STATE + BOOKMAP CALLBACKS
# =====================================================================
market_data = MarketDataEngine()
cvd_engine = CVDEngine()
market_pulse = MarketPulseEngine()
bar_aggregator = MultiTFAggregator()
doctrine_analyst = BookmapDoctrineAnalyst(bar_aggregator, master_tf="H4")
master_engine = CRDecisionRecommendationEngine(doctrine_analyst, cvd_engine, market_pulse, market_data)

alias_to_multiplier = {}
request_id_to_indicator_type = {}
alias_to_indicator_ids = {}
req_id_counter = 100


def handle_subscribe_instrument(addon, alias, full_name, is_crypto, pips, size_multiplier,
                                 instrument_multiplier, supported_features):
    global req_id_counter
    print(f"[CR-Decision] Subscribed to instrument: {alias} ({full_name})", flush=True)
    alias_to_multiplier[alias] = size_multiplier if size_multiplier > 0 else 1.0
    alias_to_indicator_ids[alias] = {}

    for ind_type, label, panel, color in [
        ("CVD", "CR CVD Delta (30s)", "BOTTOM", (0, 200, 255)),
        ("PULSE", "CR Buyer Aggression %", "BOTTOM", (255, 200, 0)),
        ("ZONE_HIGH", "CR H4 CMP Resistance (live, pure Bookmap)", "MAIN_CHART", (255, 215, 0)),
        ("ZONE_LOW", "CR H4 CMP Support (live, pure Bookmap)", "MAIN_CHART", (255, 215, 0)),
        ("BID_WALL", "CR Bid Wall (Liquidity)", "MAIN_CHART", (0, 255, 255)),
        ("ASK_WALL", "CR Ask Wall (Liquidity)", "MAIN_CHART", (255, 140, 0)),
    ]:
        req_id_counter += 1
        request_id_to_indicator_type[req_id_counter] = (alias, ind_type)
        bm.register_indicator(addon, alias, req_id_counter, label, panel, color=color)

    bm.subscribe_to_trades(addon, alias, 1)
    bm.subscribe_to_depth(addon, alias, 2)


def handle_unsubscribe_instrument(addon, alias):
    print(f"[CR-Decision] Unsubscribed from {alias}", flush=True)
    alias_to_multiplier.pop(alias, None)
    alias_to_indicator_ids.pop(alias, None)


def handle_register_indicator_response(addon, request_id, indicator_id):
    if request_id in request_id_to_indicator_type:
        alias, ind_type = request_id_to_indicator_type[request_id]
        if alias in alias_to_indicator_ids:
            alias_to_indicator_ids[alias][ind_type] = indicator_id
            print(f"[CR-Decision] Indicator '{ind_type}' assigned ID {indicator_id} for {alias}", flush=True)


def handle_trades(addon, alias, price, size, is_otc, is_bid, is_execution_start, is_execution_end,
                   aggressor_order_id, passive_order_id):
    multiplier = alias_to_multiplier.get(alias, 1.0)
    real_size = float(size) / multiplier
    is_buyer_taker = is_bid  # Bookmap docs: is_bid==True means trade WAS a buy
    now = time.time()

    market_data.on_trade(price, real_size)
    cvd_engine.on_trade(price, real_size, is_buyer_taker, now)
    market_pulse.on_trade(price, real_size, is_buyer_taker, now)
    bar_aggregator.on_trade(price, now)

    _update_chart_indicators(addon, alias)


def handle_depth_info(addon, alias, is_bid, price, size):
    multiplier = alias_to_multiplier.get(alias, 1.0)
    market_data.on_depth(is_bid, price, float(size) / multiplier)


def on_interval_draw(addon, alias):
    _update_chart_indicators(addon, alias)


last_disk_write_time = 0.0


def _update_chart_indicators(addon, alias):
    global last_disk_write_time
    now = time.time()

    if now - last_disk_write_time >= 0.2:
        last_disk_write_time = now
        master_eval = master_engine.evaluate()
        try:
            with open(STATUS_FILE, "w") as f:
                json.dump(master_eval, f, indent=2)
        except Exception as e:
            print(f"[CR-Decision] write error: {e}", flush=True)

    if alias not in alias_to_indicator_ids:
        return
    ind_map = alias_to_indicator_ids[alias]
    cvd_snap = cvd_engine.get_snapshot()
    pulse_snap = market_pulse.get_pulse()

    if "CVD" in ind_map:
        bm.add_point(addon, alias, ind_map["CVD"], cvd_snap["delta_30s"])
    if "PULSE" in ind_map:
        bm.add_point(addon, alias, ind_map["PULSE"], pulse_snap["buyer_aggression_pct"])

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
        print("Bookmap module unavailable.")
