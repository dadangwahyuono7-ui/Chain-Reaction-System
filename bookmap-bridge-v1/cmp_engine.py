"""
CMP Engine - PURE Bookmap Edition (no MT5, no TradingView, no external platform)
Location: bookmap-bridge/cmp_engine.py

Builds multi-timeframe OHLC bars directly from Bookmap's own live tick stream
(the same trades bookmap_addon.py already receives via handle_trades), then
detects minor-SNR CMP breakout with the EXACT SAME algorithm as
engine/core.py CMPDetector / DD_CMP_Marker.v6.2.pine f_get_data()
(isMinorSup/isMinorRes V/A-shape candle-body breakout).

IMPORTANT — cold start: Bookmap's L1 Python API has NO historical-bars
endpoint (confirmed against github.com/BookmapAPI/python-api — only live
trades/depth/MBO/interval callbacks exist). So candle history builds up live
from the moment this module starts receiving ticks:
  M5  ~ warms up in minutes
  M15 ~ tens of minutes
  M30 ~ about an hour
  H1  ~ a few hours
  H4  ~ about half a day (needs 3 closed H4 bars minimum for a flip)
  D1  ~ a few days
Until a TF has enough closed bars to see one minor-SNR flip, its CMP stays
"WAIT" — this is expected, not a bug. H4 is the master direction, so
get_strike_signal() returns None until H4 has warmed up.
"""

import json
import os
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

TF_SECONDS = {
    "M5": 5 * 60,
    "M15": 15 * 60,
    "M30": 30 * 60,
    "H1": 60 * 60,
    "H4": 4 * 60 * 60,
    "D1": 24 * 60 * 60,
}
TF_ORDER = ["D1", "H4", "H1", "M30", "M15", "M5"]  # master -> smallest
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
    """Rolling closed-bar history + current forming bar for one timeframe, built from ticks."""

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
        # bucket < current.time = out-of-order tick, ignore (shouldn't happen live)

    def rows(self) -> List[Bar]:
        """Closed bars + current forming bar, oldest first (mirrors MT5 copy_rates_from_pos shape:
        rows[-1] = forming bar, rows[-2] = last CLOSED bar, rows[-3] = prior closed bar)."""
        out = list(self.closed)
        if self.current is not None:
            out.append(self.current)
        return out


class MultiTFAggregator:
    def __init__(self, max_bars: int = 200, auto_seed: bool = True):
        self.tfs: Dict[str, TFBars] = {name: TFBars(secs, max_bars) for name, secs in TF_SECONDS.items()}
        if auto_seed:
            self.seed_from_m1_file()

    def on_trade(self, price: float, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        for tf in self.tfs.values():
            tf.on_trade(price, timestamp)

    def rows(self, tf_name: str) -> List[Bar]:
        return self.tfs[tf_name].rows()

    def seed_from_m1(self, m1_rows: List[List[Any]], lookback_m1: int = 40000):
        """Seed all timeframes directly from historical M1 rows [t, o, h, l, c, v]."""
        if not m1_rows:
            return
        subset = m1_rows[-lookback_m1:] if len(m1_rows) > lookback_m1 else m1_rows
        for tf_name, tf_bars in self.tfs.items():
            secs = tf_bars.tf_seconds
            buckets = {}
            for r in subset:
                t, o, h, l, c, v = r[0], r[1], r[2], r[3], r[4], r[5]
                shift = 3600 if secs == 14400 else (75600 if secs == 86400 else 0)
                bucket = int((t - shift) // secs) * secs + shift
                if bucket not in buckets:
                    buckets[bucket] = [t, o, h, l, c, v]
                else:
                    b = buckets[bucket]
                    if h > b[2]: b[2] = h
                    if l < b[3]: b[3] = l
                    b[4] = c
                    b[5] += v

            sorted_buckets = sorted(buckets.items(), key=lambda x: x[0])
            for b_time, b_data in sorted_buckets[:-1]:
                bar = Bar(b_time, b_data[1])
                bar.high = b_data[2]
                bar.low = b_data[3]
                bar.close = b_data[4]
                tf_bars.closed.append(bar)

            if sorted_buckets:
                last_t, last_data = sorted_buckets[-1]
                tf_bars.current = Bar(last_t, last_data[1])
                tf_bars.current.high = last_data[2]
                tf_bars.current.low = last_data[3]
                tf_bars.current.close = last_data[4]

    def seed_from_m1_file(self, m1_path: str = None) -> bool:
        """Find and load XAUUSD_M1.json to pre-seed all timeframe bars."""
        if m1_path is None:
            candidates = [
                os.path.join(os.path.dirname(__file__), "sultan", "history", "XAUUSD_M1.json"),
                os.path.join(os.path.dirname(__file__), "history", "XAUUSD_M1.json"),
                "C:/bookmap-bridge-v1/sultan/history/XAUUSD_M1.json",
                r"D:\PROJECT TRADING\bookmap-bridge-v1\sultan\history\XAUUSD_M1.json",
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    m1_path = cand
                    break
        if m1_path and os.path.exists(m1_path):
            try:
                with open(m1_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.seed_from_m1(data)
                return True
            except Exception:
                pass
        return False


class CMPDetector:
    """SNR body-only breakout — identical doctrine to engine/core.py CMPDetector."""

    @staticmethod
    def get_snr_flip(bars: List[Bar]):
        if len(bars) < 3:
            return 0.0, 0.0
        curr = bars[-2]
        prev = bars[-3]
        sup = res = 0.0
        # Support (Minor SNR): Previous Bearish, Current Bullish (V-shape)
        if prev.open > prev.close and curr.close > curr.open:
            sup = min(prev.open, prev.close)
        # Resistance (Minor SNR): Previous Bullish, Current Bearish (A-shape)
        if prev.close > prev.open and curr.open > curr.close:
            res = max(prev.close, prev.open)
        return sup, res


class TFState:
    """Ported 1:1 from engine/core.py TFState — same CMP/VR/CF doctrine, list-of-Bar instead of DataFrame."""

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
    """SacredDoctrineAnalyst equivalent, driven by live Bookmap ticks via MultiTFAggregator
    instead of MT5. Same Daily Deploy doctrine: H4 = master, VR = 1 TF down, CF = confirmation."""

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
        """SIMPLIFIED per Dadang's explicit correction: "gw gak pernah bilang
        ikut m15 kenapa jadi m15, fokus aja di h4 m30 m5, kenapa lo buat aturan
        sendiri." Dulu ada 4-tier cascade yang nyelipin M15/H1 (dicontek dari
        SacredDoctrineAnalyst produksi) - itu aturan yang gak pernah diminta.
        Sekarang cuma 3 TF: H4 (atau M30 fallback pas H4 masih warm-up) = arah
        master, M30 = konfirmasi arah kerja, M5 = trigger eksekusi.

        BUG FIX (2026-08-07): dulu WAJIB `m5.vr_occurred` dulu sebelum entry
        bisa fire - artinya kalau M5 dari awal udah searah M30 (gak pernah ada
        VR sama sekali), entry gak akan PERNAH nyala. Dadang: "vr hanya status
        bukan untuk ditunggu... m30 buy close m5 buy entri buy, bukan nunggu vr
        sell dulu... kalo nunggu vr yang gak muncul kita gak akan dapat entri
        dong." VR itu status yang MENUNDA entry kalau MUNCUL (market lagi
        retracement - waktu itu harusnya malah entri ikut arah VR-nya, lihat
        get_vr_scalp_signal), bukan syarat yang harus ditunggu duluan. Selama
        M5 CURRENTLY searah M30/H4, entry valid - titik, gak peduli riwayat
        VR-nya gimana.
        """
        h4, m30, m5 = (self.states[n] for n in ("H4", "M30", "M5"))

        direction = h4.cmp if h4.cmp != "WAIT" else m30.cmp
        if direction == "WAIT":
            return None

        if m30.cmp != direction or m30.cmp == "WAIT":
            return None  # M30 sendiri lagi lawan arah master -> itu VR_SCALP, bukan CF

        if m5.cmp == direction:
            return {"action": direction, "type": "CF", "tf": "M5", "tp_tf": "M30", "sl_tf": "M5",
                    "grade": "A", "reason": f"M30 {direction} solid | M5 {direction} (searah)"}

        return None

    def get_vr_scalp_signal(self) -> Optional[Dict[str, Any]]:
        """VR bukan sesuatu yang HARUS ditunggu - VR dan CF cuma status CMP di
        TF itu sendiri, bukan gerbang. CF = entri SEARAH trend master
        (get_strike_signal di atas). VR = entri SEARAH RETRACEMENT - TF yang
        lagi VR itu sendiri punya CMP baru yang bisa langsung di-scalp (TP
        dekat, bukan trend besar). SIMPLIFIED: cuma H4/M30/M5 - cek M5 (lawan
        M30) dulu baru M30 (lawan H4), gak ada M15/H1 lagi.

        TP target = zona TF yang lagi DILAWAN (bukan jarak tetap). Dadang:
        "breakout CMP M5 adalah pembentukan 1 candle M30 - kalau M5 CMP buy
        kita asumsikan M30 bakal closing ijo... jika sampai area M30 dan M5
        gak bisa bikin M30 flip buy, kita segera TP di situ." Area M30 ITU
        target-nya - kalau M5 gak berhasil nge-flip M30 sebelum harga sampai
        situ, scalp-nya emang berhenti di situ, bukan nunggu lebih jauh.
        SL tetep di TF sendiri (M5/M30) - ketat, karena ini scalp bukan trend."""
        m5, m30 = self.states["M5"], self.states["M30"]

        if m5.status == "VR" and m5.cmp != "WAIT":
            return {"action": m5.cmp, "type": "VR_SCALP", "tf": "M5", "tp_tf": "M30", "sl_tf": "M5",
                    "grade": "SCALP",
                    "reason": "M5 VR ke M30 - retracement, TP di area M30 (kalau M5 gak berhasil flip M30)"}
        if m30.status == "VR" and m30.cmp != "WAIT":
            return {"action": m30.cmp, "type": "VR_SCALP", "tf": "M30", "tp_tf": "H4", "sl_tf": "M30",
                    "grade": "SCALP",
                    "reason": "M30 VR ke H4 - retracement, TP di area H4 (kalau M30 gak berhasil flip H4)"}
        return None

    def get_m5_direct_signal(self, current_price: float, zone_tolerance: float = 3.0) -> Optional[Dict[str, Any]]:
        """PRIORITY 1 doktrin (Dadang, sesi ini): dulu (tanpa data order flow live)
        harus disiplin/kaku nunggu cascade H4>H1>M30>M15>M5 penuh sebagai proxy
        "apa entry ini bagus" - karena gak tau ada wall/momentum atau nggak.
        SEKARANG punya Bookmap real-time (Pulse/CVD/Wall), jadi cukup ikuti M5
        CMP LANGSUNG - gak perlu nunggu cascade TF atas. VR/CF M5 (st.status)
        cuma buat KONTEKS (ditampilin, bukan gate - "kita tau statusnya vr atau
        cf jadi kita paham"). Syarat WAJIB: harga harus DEKAT area CMP/SNR M5
        (support/resistance-nya sendiri) - bukan di tengah pergerakan yang udah
        jauh dari level breakout-nya ("yang penting di area cmp atau snr, bukan
        di tengah-tengah")."""
        m5 = self.states["M5"]
        if m5.cmp == "WAIT":
            return None
        ref_level = m5.res if m5.cmp == "BUY" else m5.sup
        if not ref_level or ref_level <= 0:
            return None
        distance = abs(current_price - ref_level)
        if distance > zone_tolerance:
            return None  # too far from the CMP/SNR zone - "di tengah2", skip
        return {
            "action": m5.cmp, "type": f"M5_DIRECT_{m5.status}", "tf": "M5",
            "grade": "M5",
            "reason": f"M5 {m5.cmp} (status: {m5.status}) di area SNR {ref_level:.2f} (jarak {distance:.2f})",
        }

    def get_position_status(self, direction: str, entry_tf: str, entry_time: float) -> Dict[str, Any]:
        """Post-entry monitor - SEKALI kita entri ikut arah master (M30/H4),
        M5 ALWAYS jadi trigger TAKTIS buat exit/re-entry - BUKAN entry_tf
        (TF asal sinyal masuk, bisa M15/M30/dll). Dadang eksplisit named M5:
        "kita akan berhenti buy jika M5 jadi sell." Dan doktrin fraktal:
        "m5 sell itu pasti m1 sell dulu... m15 buy kalau mau jadi sell pasti
        m5 dulu yang sell" - M5 gerak DULUAN sebelum M15/M30 beneran ikut
        flip, jadi M5 adalah early-warning trigger meskipun entry-nya via
        TF lain. Nunggu entry_tf sendiri flip (M15 misalnya) itu KELAMAAN -
        M5 udah kasih sinyal duluan.

        Doktrin: VR = satu-satunya yang gagalkan CMP, CF = satu-satunya yang
        lanjutkan CMP. SL kena != setup gagal - gagal HANYA kalau CMP master
        (M30) beneran flip. Kalau cuma M5 yang flip sementara master gak
        ikut, itu VR biasa -> EXIT taktis (amankan profit/keluar), BUKAN
        "setup ini salah" - begitu M5 balik searah master, itu CF baru,
        RE-ENTRY lagi. Bisa berkali-kali dalam 1 master direction yang sama.
        """
        watch_tf = "M5"
        st = self.states.get(watch_tf)
        master = self.states.get("M30")
        if st is None:
            return {"action": "HOLD", "reason": f"{watch_tf} tidak tertrack"}

        opp = "SELL" if direction == "BUY" else "BUY"

        if st.cmp == opp and st.cmp_change_time > entry_time:
            master_flipped = (master is not None and master.cmp == opp and
                               master.cmp_change_time > entry_time)
            if master_flipped:
                return {
                    "action": "EXIT", "master_flipped": True,
                    "reason": f"{watch_tf} flip {opp} DAN M30 ikut flip - setup {direction} BENERAN gagal, keluar total",
                }
            return {
                "action": "EXIT", "master_flipped": False,
                "reason": (f"{watch_tf} flip {opp} (VR ke M30, entry awalnya via {entry_tf}) - keluar posisi "
                           f"taktis, M30 masih {direction}, tunggu {watch_tf} balik {direction} buat re-entry"),
            }

        if st.cmp == direction:
            return {"action": "HOLD", "master_flipped": False,
                    "reason": f"{watch_tf} masih/sudah balik {direction} - posisi valid, lanjut"}

        return {"action": "HOLD", "master_flipped": False,
                "reason": f"{watch_tf} belum ada perubahan berarti sejak entry (entry awalnya via {entry_tf})"}

    def get_watch_reason(self) -> str:
        """Live 'what are we waiting for' line for the dashboard when no strike signal yet.
        SIMPLIFIED: cuma H4/M30/M5 - gak nyebut M15 lagi (lihat get_strike_signal)."""
        h4 = self.states["H4"]
        m30 = self.states["M30"]
        if h4.cmp == "WAIT":
            n = len(self.aggregator.rows("H4"))
            if m30.cmp == "WAIT":
                return f"H4 (master) warm-up: {n} candle H4 terkumpul dari live tick, butuh breakout pertama"
            # H4 belum ada, tapi M30 udah live -> ini yang lagi jadi acuan kerja (fallback)
            return f"[Fallback M30] H4 masih warm-up ({n} bars) | M30 {m30.cmp} solid — tunggu M5 VR->CF"
        if m30.cmp == "WAIT":
            n = len(self.aggregator.rows("M30"))
            return f"H4 {h4.cmp} (Pine) | M30 masih warm-up ({n} bars) dari live tick Bookmap"
        if m30.cmp != h4.cmp:
            return f"M30 VR ke H4 ({h4.cmp}) — tunggu CF di M5"
        return f"H4+M30 solid ({h4.cmp}) — tunggu M5 VR->CF"
