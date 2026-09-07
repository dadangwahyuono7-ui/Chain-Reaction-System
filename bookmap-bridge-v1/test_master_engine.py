"""
Test suite for Chain Reaction Decision Recommendation Engine v8 (Pure Bookmap Edition)
Location: bookmap-bridge/test_master_engine.py
"""

import time

from market_data_engine import MarketDataEngine
from cvd_engine import CVDEngine
from market_pulse_engine import MarketPulseEngine
from cr_master_engine import CRDecisionRecommendationEngine, WallLadderTracker
from cmp_engine import MultiTFAggregator, BookmapDoctrineAnalyst
from absorption_engine import AbsorptionEngine
from footprint_engine import FootprintEngine


class FakeTFState:
    def __init__(self, cmp="WAIT", status="CMP", vr_occurred=False, cf_count=0, cmp_change_time=0.0):
        self.cmp = cmp
        self.status = status
        self.vr_occurred = vr_occurred
        self.cf_count = cf_count
        self.cmp_change_time = cmp_change_time


class FakeAggregator:
    def rows(self, tf):
        return []


class FakeDoctrine:
    """Test double for BookmapDoctrineAnalyst — decision-logic level tests, no real tick data."""

    def __init__(self):
        self.states = {tf: FakeTFState() for tf in ("D1", "H4", "H1", "M30", "M15", "M5")}
        self.aggregator = FakeAggregator()
        self._strike = None
        self._vr_scalp = None
        self._m5_direct = None
        self._watch_reason = ""
        self._position_status = {"action": "HOLD", "reason": "fake hold"}

    def set(self, h4="WAIT", strike=None, vr_scalp=None, m5_direct=None, watch_reason=""):
        self.states["H4"] = FakeTFState(cmp=h4, status="MASTER")
        self._strike = strike
        self._vr_scalp = vr_scalp
        self._m5_direct = m5_direct
        self._watch_reason = watch_reason

    def update(self):
        pass

    def get_strike_signal(self):
        return self._strike

    def get_vr_scalp_signal(self):
        return self._vr_scalp

    def get_m5_direct_signal(self, current_price, zone_tolerance=3.0):
        return self._m5_direct

    def get_position_status(self, direction, entry_tf, entry_time):
        return self._position_status

    def get_watch_reason(self):
        return self._watch_reason


def test_decision_logic_scenarios():
    print("==================================================")
    print("   TESTING DECISION ENGINE (fake doctrine, logic-level)")
    print("==================================================")

    market_data = MarketDataEngine()
    cvd_engine = CVDEngine()
    market_pulse = MarketPulseEngine()
    doctrine = FakeDoctrine()
    engine = CRDecisionRecommendationEngine(doctrine, cvd_engine, market_pulse, market_data)

    market_data.last_price = 4300.00

    # SCENARIO 0: H4 still WAIT (cold start / warm-up)
    print("\n--- SCENARIO 0: H4 WARM-UP (no data yet) ---")
    out0 = engine.evaluate()
    print(f"Status: {out0['status_badge']}")
    assert out0['recommendation'] == "WAIT"
    assert "WARM-UP" in out0['reason_lines'][0]

    # SCENARIO 1: H4 live, no breakout yet -> MONITORING (CMP itself never WAIT once live)
    print("\n--- SCENARIO 1: H4 LIVE, NO BREAKOUT YET ---")
    engine.active_position = None
    doctrine.set(h4="SELL", strike=None, watch_reason="H4+M30 solid (SELL) - tunggu M5 VR->CF")
    out1 = engine.evaluate()
    print(f"Status: {out1['status_badge']}")
    for line in out1['reason_lines']:
        print(f"  {line}")
    assert out1['recommendation'] == "WAIT"
    assert out1['tf_matrix']['H4']['cmp'] == "SELL", "H4 CMP column must NEVER show WAIT once live!"

    # SCENARIO 2: Breakout BUY + Order Flow supports -> ENTRY BUY
    print("\n--- SCENARIO 2: BREAKOUT BUY + ORDER FLOW SUPPORTS ---")
    market_pulse.trades.clear()
    cvd_engine.trade_history.clear(); cvd_engine.session_delta = 0.0
    # Market Pulse = Bookmap's real "Price Change" algorithm (deviation of last
    # price from window average, normalized by max deviation seen) - a rising
    # price ladder puts the last trade at the top of the range -> BUY-biased.
    for i in range(10):
        market_pulse.on_trade(4295.0 + i, 10.0)
        cvd_engine.on_trade(4300.0, 10.0, is_buyer_taker=True)
    doctrine.set(h4="BUY", strike={
        "action": "BUY", "type": "CF", "tf": "M5", "tp_tf": "M30", "sl_tf": "M5",
        "grade": "A", "reason": "M30 BUY solid | M5 VR->CF"
    })
    out2 = engine.evaluate()
    print(f"Status: {out2['status_badge']}")
    for line in out2['reason_lines']:
        print(f"  {line}")
    print(f"Conclusion: {out2['conclusion']}")
    assert out2['recommendation'] == "BUY"

    # SCENARIO 3: Breakout SELL but Order Flow disagrees -> WAIT
    print("\n--- SCENARIO 3: BREAKOUT SELL BUT ORDER FLOW DISAGREES ---")
    engine.active_position = None  # scenario 2 fired a BUY entry - don't leak position state
    doctrine.set(h4="BUY", strike={
        "action": "SELL", "type": "CF", "tf": "M5", "tp_tf": "M30", "sl_tf": "M5",
        "grade": "A", "reason": "M30 SELL solid | M5 VR->CF"
    })
    out3 = engine.evaluate()
    print(f"Status: {out3['status_badge']}")
    for line in out3['reason_lines']:
        print(f"  {line}")
    assert out3['recommendation'] == "WAIT", "Order flow disagreement must block entry!"

    # SCENARIO 4: No CF yet, but a VR scalp is available + order flow supports it
    # -> ENTRY in the RETRACEMENT direction (Dadang: "vr gak harus ditunggu,
    # itu sendiri entri arah retracement, cf itu entri searah trend")
    print("\n--- SCENARIO 4: VR SCALP (no CF, but M30 VR against H4 master) ---")
    engine.active_position = None
    market_pulse.trades.clear()
    cvd_engine.trade_history.clear(); cvd_engine.session_delta = 0.0
    # falling price ladder -> last trade at the bottom of the range -> SELL-biased
    for i in range(10):
        market_pulse.on_trade(4305.0 - i, 10.0)
        cvd_engine.on_trade(4300.0, 10.0, is_buyer_taker=False)
    doctrine.set(h4="BUY", strike=None, vr_scalp={
        "action": "SELL", "type": "VR_SCALP", "tf": "M30", "grade": "SCALP",
        "reason": "M30 VR ke H4 - retracement, TP dekat (bukan trend besar)"
    })
    out4 = engine.evaluate()
    print(f"Status: {out4['status_badge']}")
    for line in out4['reason_lines']:
        print(f"  {line}")
    print(f"Conclusion: {out4['conclusion']}")
    assert out4['recommendation'] == "SELL", "VR scalp must fire an entry when order flow agrees, not just sit and WAIT!"
    assert "SCALP" in out4['reason_lines'][1]

    print("\nDecision-logic scenarios PASSED.")


def test_position_exit_and_reentry_cycle():
    """Dadang: "kita entri ikut arah M30... berhenti buy jika M5 jadi sell...
    kalo M5 sell gak bisa flip M30, begitu M5 buy lagi kita balik buy lagi."
    Once in a position, M5 flipping against it (without M30 flipping) must
    fire EXIT - not silently stay "BUY" while the tactical trigger already
    reversed. And once M5 confirms the master direction again, a NEW entry
    must fire (re-entry), same master direction, no need for M30 to do
    anything - CF can fire "berkali-kali selama CMP master belum flip"."""
    print("\n==================================================")
    print("   TESTING POSITION EXIT & RE-ENTRY CYCLE")
    print("==================================================")

    market_data = MarketDataEngine()
    market_data.last_price = 4300.0
    cvd_engine = CVDEngine()
    market_pulse = MarketPulseEngine()
    doctrine = FakeDoctrine()
    engine = CRDecisionRecommendationEngine(doctrine, cvd_engine, market_pulse, market_data)

    # Simulate an already-open BUY position, entered via M5, a while ago.
    engine.active_position = {"dir": "BUY", "tf": "M5", "entry_time": 1000.0}
    doctrine.states["H4"] = FakeTFState(cmp="BUY", status="MASTER")

    # M5 flipped SELL (VR) but M30 (master) did NOT flip -> tactical EXIT,
    # not a "setup gagal" - just a retracement.
    doctrine._position_status = {"action": "EXIT", "master_flipped": False,
                                  "reason": "M5 flip SELL (VR ke M30) - keluar posisi taktis"}
    out_exit = engine.evaluate()
    print(f"After M5 flips against (M30 unchanged): {out_exit['status_badge']}")
    for line in out_exit['reason_lines']:
        print(f"  {line}")
    assert engine.active_position is None, "Position must be cleared on EXIT!"
    assert out_exit['recommendation'] == "WAIT"
    assert "EXIT" in out_exit['status_badge']

    # M5 confirms BUY again (CF) -> a fresh entry signal should fire and
    # re-establish the position, same BUY direction, no M30 change needed.
    # cmp_change_time must be NEWER than when we exited (re-entry cooldown -
    # see get_strike_signal's CF gate in evaluate()) to simulate M5 genuinely
    # re-confirming, not just re-firing on the same stale state.
    doctrine.states["M5"] = FakeTFState(cmp="BUY", cmp_change_time=2000.0)
    market_pulse.trades.clear()
    for i in range(10):
        market_pulse.on_trade(4295.0 + i, 10.0)  # rising ladder -> BUY-biased pulse
    cvd_engine.on_trade(4300.0, 10.0, is_buyer_taker=True)
    doctrine.set(h4="BUY", strike={
        "action": "BUY", "type": "CF", "tf": "M5", "tp_tf": "M30", "sl_tf": "M5",
        "grade": "A", "reason": "M5 balik BUY setelah VR gagal flip M30"
    })
    out_reentry = engine.evaluate()
    print(f"After M5 confirms BUY again: {out_reentry['status_badge']}")
    for line in out_reentry['reason_lines']:
        print(f"  {line}")
    assert out_reentry['recommendation'] == "BUY", "Must re-enter BUY once M5 confirms master direction again!"
    assert engine.active_position is not None and engine.active_position["dir"] == "BUY"

    print("\nPosition exit & re-entry cycle test PASSED.")


def test_m5_direct_zone_filter():
    """Dadang: "intinya kita ikut m5 aja... yang penting di area cmp atau snr,
    bukan di tengah2 karena kita sudah punya data dari bookmap." get_m5_direct_signal()
    must fire when price is near M5's own SNR level, and stay silent when price
    has wandered away from it ("di tengah2")."""
    print("\n==================================================")
    print("   TESTING M5 DIRECT ENTRY (zone-proximity filter)")
    print("==================================================")

    agg = MultiTFAggregator()
    doctrine = BookmapDoctrineAnalyst(agg, master_tf="H4")
    doctrine.states["M5"].cmp = "SELL"
    doctrine.states["M5"].status = "CF"
    doctrine.states["M5"].sup = 4300.0  # SELL -> reference level is support

    near = doctrine.get_m5_direct_signal(current_price=4300.5, zone_tolerance=3.0)
    print(f"price near SNR (4300.5, level 4300.0): {near}")
    assert near is not None, "Must fire when price is close to M5's own SNR level!"
    assert near["action"] == "SELL"
    assert "CF" in near["type"]

    far = doctrine.get_m5_direct_signal(current_price=4315.0, zone_tolerance=3.0)
    print(f"price far from SNR (4315.0, level 4300.0): {far}")
    assert far is None, "Must NOT fire when price wandered away from the SNR zone ('di tengah2')!"

    print("\nM5 direct zone filter test PASSED.")


class FakeMarketDataForWalls:
    """Feeds a scripted sequence of ask-wall ladders into WallLadderTracker,
    one list per update() call, to test shrink-detection and spoof-vs-genuine-break
    without needing real Bookmap depth ticks."""

    def __init__(self, price: float, ask_sequence):
        self.last_price = price
        self._seq = list(ask_sequence)
        self._i = 0

    def get_wall_ladder(self, is_bid: bool, top_n: int = 8):
        if is_bid:
            return []
        ladder = self._seq[min(self._i, len(self._seq) - 1)]
        return ladder


def test_wall_spoof_detection():
    """Dadang: "gw sering liat wall baru muncul dan lot berkurang terus akhirnya
    jebol karena spoofing dia" - a wall that shrinks and then vanishes WITHOUT
    price ever reaching it must be flagged ask_spoofed=True (and ask_shrinking=True
    while it's still fading), NOT the same as a genuine ask_jebol (price actually
    broke through it)."""
    print("\n==================================================")
    print("   TESTING WALL SPOOF DETECTION")
    print("==================================================")

    tracker = WallLadderTracker()
    price = 4300.0

    # Step 1: wall appears at 4310 with size 100
    md = FakeMarketDataForWalls(price, [[(4310.0, 100.0)]])
    tracker.update(md)
    assert tracker.ask_ref == (4310.0, 100.0)
    assert not tracker.ask_shrinking

    # Steps 2-4: same wall, size fading 100 -> 70 -> 55 -> 35 (below 60% of 100)
    for size in (70.0, 55.0, 35.0):
        md = FakeMarketDataForWalls(price, [[(4310.0, size)]])
        tracker.update(md)
    print(f"after shrinking sequence: ask_shrinking={tracker.ask_shrinking}")
    assert tracker.ask_shrinking, "Wall shrinking to <60% of its first size must be flagged!"

    # Step 5: wall vanishes from the book entirely - price NEVER reached 4310 (still 4300)
    md = FakeMarketDataForWalls(price, [[]])
    tracker.update(md)
    print(f"after vanish (price never reached it): ask_spoofed={tracker.ask_spoofed}, ask_jebol={tracker.ask_jebol}")
    assert tracker.ask_spoofed, "Wall pulled from book without price reaching it must be SPOOFED, not silent!"
    assert not tracker.ask_jebol, "Must NOT be counted as a genuine breakout when price never touched it!"

    # Contrast: a wall that price genuinely trades through -> ask_jebol=True, NOT spoofed
    tracker2 = WallLadderTracker()
    md = FakeMarketDataForWalls(4300.0, [[(4302.0, 100.0)]])
    tracker2.update(md)
    md = FakeMarketDataForWalls(4303.0, [[]])  # price now ABOVE the wall level = genuine break
    tracker2.update(md)
    print(f"genuine breakout: ask_jebol={tracker2.ask_jebol}, ask_spoofed={tracker2.ask_spoofed}")
    assert tracker2.ask_jebol, "Price genuinely trading through the wall must be ask_jebol=True!"
    assert not tracker2.ask_spoofed, "A genuine breakout must NOT be mislabeled as spoofed!"

    print("\nWall spoof detection test PASSED.")


def test_m30_fallback_when_h4_still_warming_up():
    """H4 masih WAIT (warm-up) tapi M30 udah punya arah -> get_strike_signal() harus
    tetap bisa nyala pakai M30 sebagai fallback direction (Dadang: "M30 kebawah gak
    masalah, gak usah nunggu H4"). Manipulasi state langsung (bukan lewat tick) karena
    yang diuji adalah logic get_strike_signal(), bar aggregation-nya udah dites terpisah."""
    print("\n==================================================")
    print("   TESTING M30 FALLBACK (H4 WAIT, M30 sudah live)")
    print("==================================================")

    agg = MultiTFAggregator()
    doctrine = BookmapDoctrineAnalyst(agg, master_tf="H4")

    # H4 sengaja dibiarkan WAIT (warm-up). M30 solid BUY, M5 baru VR->CF ke BUY.
    doctrine.states["M30"].cmp = "BUY"
    doctrine.states["M30"].cmp_change_time = 50
    doctrine.states["M5"].cmp = "BUY"
    doctrine.states["M5"].vr_occurred = True
    doctrine.states["M5"].vr_change_time = 150
    doctrine.states["M5"].cmp_change_time = 200

    assert doctrine.states["H4"].cmp == "WAIT", "sanity check: H4 harus masih WAIT"

    strike = doctrine.get_strike_signal()
    print(f"strike signal (H4 WAIT, M30 fallback): {strike}")
    assert strike is not None, "Signal harus tetap nyala dari M30 walau H4 masih WAIT!"
    assert strike["action"] == "BUY"
    assert strike["type"] == "CF"

    # Cek juga lewat CRDecisionRecommendationEngine — harus jadi ENTRY BUY kalau order flow align
    market_data = MarketDataEngine()
    market_data.last_price = 4300.0
    cvd_engine = CVDEngine()
    market_pulse = MarketPulseEngine()
    for i in range(10):
        market_pulse.on_trade(4300.0 + i, 10.0)  # rising ladder -> BUY-biased pulse
        cvd_engine.on_trade(4300.0, 10.0, is_buyer_taker=True)
    engine = CRDecisionRecommendationEngine(doctrine, cvd_engine, market_pulse, market_data)
    out = engine.evaluate()
    print(f"Status: {out['status_badge']}")
    for line in out['reason_lines']:
        print(f"  {line}")
    assert out['recommendation'] == "BUY", "Harus ENTRY BUY dari fallback M30, walau H4 masih warm-up!"
    assert "FALLBACK" in out['reason_lines'][0]

    print("\nM30 fallback test PASSED.")


def test_real_tick_pipeline_warms_up_h4():
    """End-to-end: real MultiTFAggregator + BookmapDoctrineAnalyst, fed pure synthetic
    Bookmap ticks (no MT5/TradingView) — proves H4 goes WARM-UP -> live CMP from ticks alone."""
    print("\n==================================================")
    print("   TESTING REAL TICK PIPELINE (pure Bookmap, no MT5/TradingView)")
    print("==================================================")

    market_data = MarketDataEngine()
    cvd_engine = CVDEngine()
    market_pulse = MarketPulseEngine()
    agg = MultiTFAggregator()
    doctrine = BookmapDoctrineAnalyst(agg, master_tf="H4")
    engine = CRDecisionRecommendationEngine(doctrine, cvd_engine, market_pulse, market_data)
    market_data.last_price = 4300.0

    out_before = engine.evaluate()
    print(f"Before ticks: {out_before['status_badge']} -> {out_before['reason_lines'][0]}")
    assert out_before['recommendation'] == "WAIT"
    assert "WARM-UP" in out_before['reason_lines'][0]

    # Feed synthetic H4 ticks forming a minor-SNR SELL breakout (same pattern validated
    # directly against CMPDetector/TFState — see cmp_engine.py). H4 bucket = 14400s.
    t0 = 1_700_000_000
    agg.on_trade(4300.0, t0)
    agg.on_trade(4295.0, t0 + 10)          # H4 Bar1 bearish 4300->4295
    engine.evaluate()
    agg.on_trade(4295.0, t0 + 14400)
    agg.on_trade(4300.0, t0 + 14410)       # H4 Bar2 bullish 4295->4300 (V vs Bar1 -> sup=4295)
    engine.evaluate()
    agg.on_trade(4299.0, t0 + 28800)       # H4 Bar3 opens
    engine.evaluate()
    agg.on_trade(4290.0, t0 + 28810)       # H4 Bar3 closes bearish, well below sup
    engine.evaluate()
    agg.on_trade(4289.0, t0 + 43200)       # H4 Bar4 starts -> triggers flip check
    out_after = engine.evaluate()

    print(f"After ticks: {out_after['status_badge']}")
    for line in out_after['reason_lines']:
        print(f"  {line}")
    assert out_after['tf_matrix']['H4']['cmp'] == "SELL", "H4 should be live SELL from pure ticks alone!"

    print("\nReal tick pipeline PASSED — pure Bookmap ticks drive live CMP, no external platform needed.")


def test_absorption_detection():
    """Dadang: "harga turun, CVD SELL, tapi harga gak turun - artinya ada yang
    nyerap... itu sering jadi tanda reversal." Absorption = strong one-sided
    CVD window delta while price barely moves. Also verifies the WARNING
    (not hard block) integration: a fresh entry still fires, just with
    lot_multiplier halved - Dadang's own example: "BUY WARNING, kurangi lot"."""
    print("\n==================================================")
    print("   TESTING ABSORPTION DETECTION")
    print("==================================================")

    # --- Unit-level: AbsorptionEngine directly ---
    ae = AbsorptionEngine(window_sec=30.0, delta_threshold=50.0, price_move_threshold=0.5)
    t0 = 1_800_000_000.0
    ae.on_price(4300.0, t0)
    ae.on_price(4300.2, t0 + 10)
    ae.on_price(4300.1, t0 + 20)   # price barely moved across the window
    result = ae.get_absorption(cvd_window_delta=-120.0)  # heavy SELL aggression
    print(f"heavy sell + flat price: {result}")
    assert result["status"] == "SELLER_ABSORBED", "strong sell delta + flat price must flag seller absorption!"

    ae2 = AbsorptionEngine(window_sec=30.0, delta_threshold=50.0, price_move_threshold=0.5)
    ae2.on_price(4300.0, t0)
    ae2.on_price(4295.0, t0 + 20)  # price DID move a lot -> genuine move, not absorption
    result2 = ae2.get_absorption(cvd_window_delta=-120.0)
    print(f"heavy sell + price actually moved: {result2}")
    assert result2["status"] == "NONE", "price genuinely following the delta must NOT be flagged as absorption!"

    # --- Integration: fresh entry still fires, lot_multiplier drops when absorption warns ---
    market_data = MarketDataEngine()
    market_data.last_price = 4300.0
    cvd_engine = CVDEngine()
    market_pulse = MarketPulseEngine()
    agg = MultiTFAggregator()
    doctrine = BookmapDoctrineAnalyst(agg, master_tf="H4")
    doctrine.states["M30"].cmp = "BUY"
    doctrine.states["M30"].cmp_change_time = 50
    engine = CRDecisionRecommendationEngine(doctrine, cvd_engine, market_pulse, market_data)

    # M5 not in VR/CF yet -> no active_signal, evaluate() just WAITs, but it still
    # seeds absorption_engine's (flat, 4300.0) price history on every call, same
    # as it would during live warm-up before any signal fires.
    engine.evaluate()
    engine.evaluate()

    # NOW fire the CF signal (M5 VR->CF, BUY) and feed order flow that agrees.
    doctrine.states["M5"].cmp = "BUY"
    doctrine.states["M5"].vr_occurred = True
    doctrine.states["M5"].vr_change_time = 150
    doctrine.states["M5"].cmp_change_time = 200
    for i in range(10):
        market_pulse.on_trade(4295.0 + i, 10.0)  # rising ladder -> BUY pulse
    now = time.time()
    # ... but the CVD *window* shows heavy recent buyer aggression while price
    # (still 4300.0, unchanged from the seeding calls above) stays flat -> absorption.
    for i in range(10):
        cvd_engine.on_trade(4300.0, 15.0, is_buyer_taker=True, timestamp=now - 5 + i * 0.3)

    out = engine.evaluate()  # this is the fresh-entry call - active_position was still None going in

    print(f"Status: {out['status_badge']}")
    for line in out['reason_lines']:
        print(f"  {line}")
    assert out['recommendation'] == "BUY", "entry must still fire despite absorption warning (warning, not a block)!"
    assert out['lot_multiplier'] == 0.5, "lot must be halved when absorption warns against the fired direction!"
    assert out['absorption']['status'] == "BUYER_ABSORBED"
    assert any("ABSORPTION" in line for line in out['reason_lines'])

    print("\nAbsorption detection test PASSED.")


def test_wall_entry_signal():
    """Dadang: "breakout gw buat karena gw gak punya bookmap dulu... sekarang
    udah jelas snr-nya di bookmap - entri gak perlu nunggu breakout kalau
    harga di area wall kuat dan footprint dukung arah bounce/reject-nya,"
    dan SL-nya teknis di seberang wall (bukan backstop %) - "sl di bawah
    area wall itu juga ok"."""
    print("\n==================================================")
    print("   TESTING WALL ENTRY SIGNAL (Footprint-confirmed)")
    print("==================================================")

    # --- Unit-level: FootprintEngine directly ---
    fp = FootprintEngine(window_sec=120.0, price_tolerance=1.0)
    for i in range(10):
        fp.on_trade(4300.0, 10.0, is_buyer_taker=True)  # heavy buying AT this price
    result = fp.get_footprint_at_price(4300.0)
    print(f"heavy buy at 4300.0: {result}")
    assert result["status"] == "BUY_DOMINANT"

    fp2 = FootprintEngine(window_sec=120.0, price_tolerance=1.0)
    for i in range(10):
        fp2.on_trade(4300.0, 10.0, is_buyer_taker=False)
    result2 = fp2.get_footprint_at_price(4300.0)
    print(f"heavy sell at 4300.0: {result2}")
    assert result2["status"] == "SELL_DOMINANT"

    result3 = fp.get_footprint_at_price(4350.0)  # far from any recorded trade
    print(f"far from trades: {result3}")
    assert result3["status"] == "NEUTRAL"

    # --- Integration: get_wall_entry_signal() fires BUY at a support wall
    # with buy-dominant footprint, gives a technical (not %-backstop) SL ---
    market_data = MarketDataEngine()
    market_data.last_price = 4300.5
    cvd_engine = CVDEngine()
    market_pulse = MarketPulseEngine()
    footprint_engine = FootprintEngine()
    agg = MultiTFAggregator()
    doctrine = BookmapDoctrineAnalyst(agg, master_tf="H4")
    engine = CRDecisionRecommendationEngine(doctrine, cvd_engine, market_pulse, market_data, footprint_engine)

    market_data.on_depth(True, 4300.0, 60.0)    # support wall right below price
    market_data.on_depth(False, 4310.0, 55.0)   # resistance wall (opposite side)
    engine.wall_ladder.update(market_data)      # seed ref walls from real depth data (like live usage)
    for i in range(10):
        footprint_engine.on_trade(4300.0, 10.0, is_buyer_taker=True)  # buyers defending the wall

    signal = engine.get_wall_entry_signal(current_price=4300.5)
    print(f"wall entry signal: {signal}")
    assert signal is not None, "Must fire when price is at a wall with buy-dominant footprint!"
    assert signal["action"] == "BUY"
    assert signal["type"] == "WALL_ENTRY"
    assert signal["sl_price"] < 4300.0, "SL must be technical (below the wall), not a % backstop!"
    assert "tp_price" not in signal, "No TP - Dadang: 'JANGAN TP KECUALI ADA SIGNAL SELL', exit is doctrine-only!"

    far_signal = engine.get_wall_entry_signal(current_price=4320.0)  # too far from any wall
    print(f"far from any wall: {far_signal}")
    assert far_signal is None

    # --- Full evaluate(): fires even while H4/M30 are still WAIT (no CMP cascade needed) ---
    assert doctrine.states["H4"].cmp == "WAIT" and doctrine.states["M30"].cmp == "WAIT", \
        "sanity check: doctrine harus masih cold start"
    for i in range(10):
        market_pulse.on_trade(4295.0 + i, 10.0)  # rising ladder -> BUY-biased pulse
        cvd_engine.on_trade(4300.0, 10.0, is_buyer_taker=True)
    out = engine.evaluate()
    print(f"Status (H4/M30 still WAIT): {out['status_badge']}")
    for line in out['reason_lines']:
        print(f"  {line}")
    assert out['recommendation'] == "BUY", "WALL_ENTRY must fire BUY even with H4/M30 still WAIT!"
    assert out['active_signal']['type'] == "WALL_ENTRY"

    print("\nWall entry signal test PASSED.")


def test_no_tp_absorption_does_not_exit_and_reentry_cooldown():
    """Dadang caught a REAL whipsaw bug live: 9 entries in <10 seconds, every
    one immediately closed by the (now-removed) absorption-driven TP, tiny
    losses each time. "JANGAN TP KECUALI ADA SIGNAL SELL... meski ada
    absorption di buy nya lanjut... mana ada mau buy entri pas candle ijo,
    nunggu merah dulu lah minimal... gw trading gak pernah TP 10 pip."
    Verifies the fix: (1) no signal carries a tp_price anymore, (2) an open
    position does NOT get force-exited by Absorption alone, (3) re-entry is
    blocked on the SAME stale M5 state right after an exit (the churn), but
    fires once M5 genuinely stamps a fresh cmp_change_time."""
    print("\n==================================================")
    print("   TESTING NO-TP + NO ABSORPTION-EXIT + RE-ENTRY COOLDOWN")
    print("==================================================")

    # --- (1) CF signal never carries a tp_price ---
    market_data = MarketDataEngine()
    market_data.last_price = 4300.0
    cvd_engine = CVDEngine()
    market_pulse = MarketPulseEngine()
    footprint_engine = FootprintEngine()
    agg = MultiTFAggregator()
    doctrine = BookmapDoctrineAnalyst(agg, master_tf="H4")
    doctrine.states["M30"].cmp = "BUY"
    doctrine.states["M30"].cmp_change_time = 50
    doctrine.states["M5"].cmp = "BUY"
    doctrine.states["M5"].cmp_change_time = 200
    engine = CRDecisionRecommendationEngine(doctrine, cvd_engine, market_pulse, market_data, footprint_engine)
    market_data.on_depth(False, 4320.0, 60.0)
    engine.wall_ladder.update(market_data)
    for i in range(10):
        market_pulse.on_trade(4295.0 + i, 10.0)
        cvd_engine.on_trade(4300.0, 10.0, is_buyer_taker=True)

    out = engine.evaluate()
    print(f"active_signal: {out['active_signal']}")
    assert out['recommendation'] == "BUY"
    assert "tp_price" not in out['active_signal'], "CF must NEVER carry a tp_price - exit is doctrine-only!"

    # --- (2) Absorption alone must NOT force-exit an open, doctrine-valid position ---
    doctrine2 = BookmapDoctrineAnalyst(MultiTFAggregator(), master_tf="H4")
    doctrine2.states["H4"].cmp = "BUY"
    doctrine2.states["M30"].cmp = "BUY"
    doctrine2.states["M5"].cmp = "BUY"  # M5 still confirming BUY - doctrine says HOLD
    doctrine2.states["M5"].cmp_change_time = time.time() - 30
    cvd_engine2 = CVDEngine()
    market_pulse2 = MarketPulseEngine()
    footprint_engine2 = FootprintEngine()
    engine2 = CRDecisionRecommendationEngine(doctrine2, cvd_engine2, market_pulse2, MarketDataEngine(), footprint_engine2)
    engine2.market_data.last_price = 4300.0
    engine2.active_position = {"dir": "BUY", "tf": "M5", "entry_time": time.time() - 60}

    engine2.absorption_engine.on_price(4300.0)
    engine2.absorption_engine.on_price(4300.0)  # flat price -> classic absorption setup
    now = time.time()
    for i in range(10):
        cvd_engine2.on_trade(4300.0, 15.0, is_buyer_taker=True, timestamp=now - 5 + i * 0.3)  # heavy buy delta

    out2 = engine2.evaluate()
    print(f"Status with active BUY position + buyer-absorbed: {out2['status_badge']}")
    assert out2['absorption']['status'] == "BUYER_ABSORBED", "sanity check: absorption must actually be detected"
    assert "EXIT" not in out2['status_badge'], "Absorption alone must NOT force an exit - only a real SELL/doctrine signal!"
    assert engine2.active_position is not None, "Position must still be held!"

    # --- (3) Re-entry cooldown: blocked immediately after exit (stale M5), fires once M5 is genuinely fresh ---
    doctrine3 = FakeDoctrine()
    doctrine3.states["H4"] = FakeTFState(cmp="BUY", status="MASTER")
    engine3 = CRDecisionRecommendationEngine(doctrine3, CVDEngine(), MarketPulseEngine(), MarketDataEngine())
    engine3.active_position = {"dir": "BUY", "tf": "M5", "entry_time": 1000.0}
    doctrine3._position_status = {"action": "EXIT", "master_flipped": False, "reason": "M5 flip SELL - taktis"}
    out_exit = engine3.evaluate()
    assert engine3.active_position is None

    # Same stale M5 cmp_change_time as when we exited -> churn, must be blocked
    doctrine3.states["M5"] = FakeTFState(cmp="BUY", cmp_change_time=0.0)
    doctrine3.set(h4="BUY", strike={"action": "BUY", "type": "CF", "tf": "M5",
                                     "grade": "A", "reason": "re-fire on stale state"})
    out_stale = engine3.evaluate()
    print(f"Re-fire attempt on STALE M5 state: {out_stale['status_badge']}")
    assert out_stale['recommendation'] != "BUY", "Must NOT re-enter on the same stale M5 state right after exit - that's the churn bug!"

    # M5 genuinely stamps a NEW cmp_change_time (a real fresh candle event) -> allowed
    doctrine3.states["M5"] = FakeTFState(cmp="BUY", cmp_change_time=5000.0)
    market_pulse3 = engine3.market_pulse
    for i in range(10):
        market_pulse3.on_trade(4295.0 + i, 10.0)
    engine3.cvd_engine.on_trade(4300.0, 10.0, is_buyer_taker=True)
    out_fresh = engine3.evaluate()
    print(f"Re-fire attempt on FRESH M5 state: {out_fresh['status_badge']}")
    assert out_fresh['recommendation'] == "BUY", "Must re-enter once M5 has a genuinely fresh cmp_change_time!"

    print("\nNo-TP + no absorption-exit + re-entry cooldown test PASSED.")


if __name__ == "__main__":
    test_decision_logic_scenarios()
    test_position_exit_and_reentry_cycle()
    test_m5_direct_zone_filter()
    test_wall_spoof_detection()
    test_m30_fallback_when_h4_still_warming_up()
    test_real_tick_pipeline_warms_up_h4()
    test_absorption_detection()
    test_wall_entry_signal()
    test_no_tp_absorption_does_not_exit_and_reentry_cooldown()
    print("\n==================================================")
    print("   ALL TEST SUITES PASSED!")
    print("==================================================")
