import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

class CMPDetector:
    """SNR Body-only detection using ONLY the specified candle transition."""
    @staticmethod
    def get_snr_flip(df):
        """
        Returns Minor SNR if a flip/breakout occurred between the last two closed candles.
        CMP = Current Market Price Breakout Minor SNR (Body Break)
        """
        if len(df) < 3:
            return 0.0, 0.0
            
        # Using rates[-2] (just closed) and rates[-3] (previous closed)
        curr = df.iloc[-2]
        prev = df.iloc[-3]
        sup = res = 0.0
        
        # Support (Minor SNR): Previous Bearish, Current Bullish (V-shape)
        if prev['open'] > prev['close'] and curr['close'] > curr['open']:
            sup = min(prev['open'], prev['close'])
            
        # Resistance (Minor SNR): Previous Bullish, Current Bearish (A-shape)
        if prev['close'] > prev['open'] and curr['open'] > curr['close']:
            res = max(prev['close'], prev['open'])
            
        return sup, res

class TFState:
    """Manages CMP, VR (Valid Reversal), and CF (Confirmation) states for a single timeframe."""
    def __init__(self, name):
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

    def initialize_cmp(self, df):
        """Scan backward to find the most recent breakout (startup only)."""
        pip_threshold = 0.1 # Gold 1-pip
        for i in range(len(df)-2, 2, -1):
            temp_sup, temp_res = 0.0, 0.0
            # Scan backward to find closest SNR flip
            for j in range(i, 2, -1):
                curr, prev = df.iloc[j], df.iloc[j-1]
                if temp_sup == 0 and prev['open'] > prev['close'] and curr['close'] > curr['open']:
                    temp_sup = min(prev['open'], prev['close'])
                if temp_res == 0 and prev['close'] > prev['open'] and curr['open'] > curr['close']:
                    temp_res = max(prev['close'], prev['open'])
                if temp_sup > 0 and temp_res > 0:
                    break
            
            c_close = df['close'].iloc[i]
            if temp_res > 0 and c_close > temp_res + pip_threshold:
                self.cmp = "BUY"
                self.sup, self.res = temp_sup, temp_res
                self.cmp_change_time = df['time'].iloc[i].timestamp() if hasattr(df['time'].iloc[i], 'timestamp') else float(df['time'].iloc[i])
                break
            if temp_sup > 0 and c_close < temp_sup - pip_threshold:
                self.cmp = "SELL"
                self.sup, self.res = temp_sup, temp_res
                self.cmp_change_time = df['time'].iloc[i].timestamp() if hasattr(df['time'].iloc[i], 'timestamp') else float(df['time'].iloc[i])
                break

    def update(self, df, parent_cmp="WAIT", parent_change_time=0):
        if len(df) < 3:
            return "WAIT"

        # 1. Initialize CMP on first run
        if not self.initialized:
            self.initialize_cmp(df)
            self.initialized = True

        # 2. Track Parent CMP change (Reset VR sequence if Master flips)
        if parent_cmp != self.last_parent_cmp:
            self.parent_cmp_change_time = parent_change_time
            self.vr_occurred = False
            self.last_parent_cmp = parent_cmp

        # 3. Update SNR ONLY on the most recent flip
        new_sup, new_res = CMPDetector.get_snr_flip(df)
        if new_sup > 0: self.sup = new_sup
        if new_res > 0: self.res = new_res

        # 4. CMP Logic (Body Breakout)
        last_close = df['close'].iloc[-2]
        pip_threshold = 0.1
        
        if self.res > 0 and last_close > self.res + pip_threshold:
            if self.cmp != "BUY":
                self.cmp = "BUY"
                self.cmp_change_time = df['time'].iloc[-2].timestamp() if hasattr(df['time'].iloc[-2], 'timestamp') else float(df['time'].iloc[-2])
        elif self.sup > 0 and last_close < self.sup - pip_threshold:
            if self.cmp != "SELL":
                self.cmp = "SELL"
                self.cmp_change_time = df['time'].iloc[-2].timestamp() if hasattr(df['time'].iloc[-2], 'timestamp') else float(df['time'].iloc[-2])

        # 5. State Determination (Strict Time Law: Master -> VR -> CF)
        # VR = Child breaks Minor SNR against Parent Direction AFTER Parent CMP
        # CF = Child breaks Minor SNR aligned with Parent Direction AFTER VR occurred
        
        status = "CMP"
        if parent_cmp != "WAIT":
            # CASE 1: Valid Reversal (VR)
            if self.cmp != parent_cmp and self.cmp != "WAIT":
                # VR must occur AFTER Parent established its direction (Time Law)
                if self.cmp_change_time > self.parent_cmp_change_time:
                    if not self.vr_occurred:
                        self.vr_occurred = True
                        self.vr_change_time = self.cmp_change_time # Record VR time
                    status = "VR"
            
            # CASE 2: Confirmation (CF)
            elif self.cmp == parent_cmp:
                # CF is valid ONLY if:
                # 1. VR happened before
                # 2. This current CMP breakout (CF) happened AFTER the VR (Strict Chronological Law)
                if self.vr_occurred and self.cmp_change_time > getattr(self, 'vr_change_time', 0):
                    status = "CF"
                else:
                    # If it's the same direction as parent but no VR yet, it's just CMP
                    status = "CMP"
                    self.vr_occurred = False # Reset if it just follows parent without reversal
        
        self.status = status
        return status

class SacredDoctrineAnalyst:
    """Orchestrates the Multi-TF sequence (MN1 down to M5) to find Chain Reaction opportunities."""
    def __init__(self, symbol, master_tf="H4"):
        self.symbol = symbol
        self.master_tf = master_tf
        self.timeframes = {
            "MN1": mt5.TIMEFRAME_MN1,
            "W1": mt5.TIMEFRAME_W1,
            "D1": mt5.TIMEFRAME_D1,
            "H4": mt5.TIMEFRAME_H4,
            "H1": mt5.TIMEFRAME_H1,
            "M30": mt5.TIMEFRAME_M30,
            "M15": mt5.TIMEFRAME_M15,
            "M5": mt5.TIMEFRAME_M5
        }
        self.tf_order = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]
        self.states = {name: TFState(name) for name in self.timeframes}
        
    def update(self):
        """Update all TF states with dynamic Master anchoring."""
        # 1. First, update the Master TF and its context (Higher TFs)
        master_idx = self.tf_order.index(self.master_tf)
        
        # Context parent for the Master (The TF directly above it)
        context_parent_cmp = "WAIT"
        context_parent_time = 0
        
        for i, name in enumerate(self.tf_order):
            mt5_tf = self.timeframes[name]
            rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, 100)
            if rates is None or len(rates) == 0: continue
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')

            if i < master_idx:
                # Context TFs (Higher than Master) - Update independently or parented top-down
                self.states[name].update(df, context_parent_cmp, context_parent_time)
                context_parent_cmp = self.states[name].cmp
                context_parent_time = self.states[name].cmp_change_time
            
            elif i == master_idx:
                # The Master TF - Its CMP becomes the anchor for all lower TFs
                self.states[name].update(df, context_parent_cmp, context_parent_time)
                self.master_cmp = self.states[name].cmp
                self.master_time = self.states[name].cmp_change_time
                self.states[name].status = "MASTER" # Visual indicator
            
            else:
                # Child TFs (Lower than Master) - ALL anchored to the Master's CMP
                self.states[name].update(df, self.master_cmp, self.master_time)
            
        return self.states

    def get_strike_signal(self):
        """
        CHAIN REACTION GHOST STRIKE (Recursive Nested Logic):
        Ensures we don't miss strong trends by looking for micro-VR/CF.
        """
        master = self.states[self.master_tf]
        if master.cmp == "WAIT": return None
        
        # TF Setup Scale
        m30 = self.states["M30"]
        m15 = self.states["M15"]
        m5 = self.states["M5"]
        
        # --- GHOST STRIKE: Standard (M5 CF to M15 VR) ---
        if m30.cmp == master.cmp and not m30.vr_occurred:
            if m15.status == "VR" and m5.status == "CF" and m5.cmp == master.cmp:
                return {
                    "action": m5.cmp,
                    "reason": f"Ghost Strike: M15 VR + M5 CF",
                    "tf": "M5",
                    "type": "GHOST_STRIKE"
                }

        # --- CHEAT CODE: Counter-Master Scalp ---
        if m30.status == "VR":
            if m5.cmp == m30.cmp and m5.status == "CF":
                return {
                    "action": m5.cmp,
                    "reason": f"Cheat Code: M30 VR + M5 CF",
                    "tf": "M5",
                    "type": "CHEAT_SCALP"
                }

        # --- PRE-VR MOMENTUM: Pro-Master ---
        if m5.cmp == master.cmp:
            if not m30.vr_occurred:
                return {
                    "action": m5.cmp,
                    "reason": f"Pre-VR Momentum: {self.master_tf} {master.cmp} + M30 Fresh",
                    "tf": "M5",
                    "type": "PRE_VR"
                }
            
            if m5.status == "CF":
                return {
                    "action": m5.cmp,
                    "reason": f"Confirmation Strike: M5 CF to Master {self.master_tf}",
                    "tf": "M5",
                    "type": "CF_STRIKE"
                }
            
    def get_strategic_forecast(self):
        """Generates a plain-language narrative based on the Sacred Doctrine."""
        master = self.states[self.master_tf]
        m30 = self.states["M30"]
        m15 = self.states["M15"]
        m5 = self.states["M5"]
        
        direction = master.cmp
        if direction == "WAIT":
            return "MASTER UNCERTAIN: Scanning for direction in higher timeframes."
            
        # Analysis Logic
        if m5.cmp != direction:
            # Market is in VR (M5 is opposite to Master)
            msg = f"MARKET STATUS: [bold yellow]VALID RETRACEMENT (VR)[/]. Master {self.master_tf} is {direction}, but M5 is {m5.cmp}. "
            if m15.cmp == direction:
                msg += "M15 masih solid. Tunggu M5 pecah SELL (CF) untuk eksekusi Sniper."
            else:
                msg += "M15 sudah VR! Retracement merembet ke atas. Play it safe."
            return msg
            
        elif m5.status == "CF":
            return f"MARKET STATUS: [bold green]CONFIRMATION (CF)[/]. M5 sudah searah Master {direction} setelah VR. Sinyal valid untuk STRIKE!"
            
        elif m5.cmp == direction:
            if not m15.vr_occurred and not m30.vr_occurred:
                return f"MARKET STATUS: [bold cyan]MOMENTUM KENCENG[/]. Semua TF searah {direction}. Cari celah Ghost Strike di M5."
            else:
                return f"MARKET STATUS: [bold blue]RECOVERY[/]. Market mulai kembali ke jalur {direction} setelah retracement."
                
    def get_total_sentiment(self):
        """Calculates the total alignment across all timeframes."""
        buy_score = 0
        sell_score = 0
        weights = {"MN1": 10, "W1": 8, "D1": 6, "H4": 5, "H1": 3, "M30": 2, "M15": 1, "M5": 1}
        
        for name, weight in weights.items():
            st = self.states[name]
            if st.cmp == "BUY": buy_score += weight
            elif st.cmp == "SELL": sell_score += weight
            
        total = sum(weights.values())
        buy_pct = (buy_score / total) * 100
        sell_pct = (sell_score / total) * 100
        
        return buy_pct, sell_pct


class BSTradingAnalyst:
    """
    SOP ENGINE - BS TRADING (EBOOK BS TRADING.pdf)
    Implements:
      Fase 1: Directional Mapping (MN1, W1, D1) -> Lock Direction
      Fase 2: Monitoring Zone (MZ) on H4, H1, M30
      Fase 3: Deteksi Trigger (PMB - Pecah Masuk Balik) on M15, M5, M1
      Fase 4: Multi Timeframe & Storyline Validation (Adjacent vs Skip steps)
      Fase 5: VP/VR Safety Logic (Rule 1, 2, and 3 validation)
    """
    def __init__(self, symbol):
        self.symbol = symbol
        self.timeframes = {
            "MN1": mt5.TIMEFRAME_MN1,
            "W1": mt5.TIMEFRAME_W1,
            "D1": mt5.TIMEFRAME_D1,
            "H4": mt5.TIMEFRAME_H4,
            "H1": mt5.TIMEFRAME_H1,
            "M30": mt5.TIMEFRAME_M30,
            "M15": mt5.TIMEFRAME_M15,
            "M5": mt5.TIMEFRAME_M5,
            "M1": mt5.TIMEFRAME_M1
        }
        self.tf_order = ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5", "M1"]
        self.locked_direction = "WAIT"
        self.current_price = 0.0
        
        # State storage
        self.sb_levels = {name: [] for name in self.timeframes}
        self.ss_levels = {name: [] for name in self.timeframes}
        self.tf_trends = {name: "WAIT" for name in self.timeframes} # Latest SB/SS trend
        
        # Monitoring Zones
        self.active_mz = None # dict with 'tf', 'type', 'low', 'high', 'level_ref'
        self.standby_state = "STANDBY" # STANDBY or READY (Inside MZ)
        
        # Trigger
        self.pmb_trigger = None # dict with 'tf', 'type', 'risk', 'tp_price', 'sl_price'
        
        # Safety / VP/VR counters
        self.vp_counts = {name: 0 for name in self.timeframes} # counter-direction hits
        self.safety_veto = False
        self.safety_msg = "OK"

    @staticmethod
    def detect_structural_sb_ss(df):
        """
        Structural SB/SS detection algorithm.
        Identifies Swing Highs & Swing Lows, and checks if subsequent
        candles break the opposing nearest level, certifying them as SB or SS.
        """
        if len(df) < 10:
            return [], []
            
        highs = [] # list of (idx, val, time)
        lows = []  # list of (idx, val, time)
        for i in range(2, len(df) - 2):
            if df['high'].iloc[i] == max(df['high'].iloc[i-2:i+3]):
                highs.append((i, df['high'].iloc[i], df['time'].iloc[i]))
            if df['low'].iloc[i] == min(df['low'].iloc[i-2:i+3]):
                lows.append((i, df['low'].iloc[i], df['time'].iloc[i]))
                
        sb_list = []
        ss_list = []
        
        # SB (Strong Buyer) Detection
        for l_idx, l_low, l_time in lows:
            prior_resistances = [h_val for h_idx, h_val, h_time in highs if h_idx < l_idx]
            if not prior_resistances:
                continue
            nearest_res = prior_resistances[-1]
            
            is_sb = False
            break_idx = -1
            for k in range(l_idx + 1, len(df)):
                if df['close'].iloc[k] < l_low:
                    break # invalidated
                if df['close'].iloc[k] > nearest_res:
                    is_sb = True
                    break_idx = k
                    break
            if is_sb:
                body_min = min(df['open'].iloc[l_idx], df['close'].iloc[l_idx])
                sb_list.append({
                    'price': l_low,
                    'time': l_time,
                    'zone_low': l_low,
                    'zone_high': body_min,
                    'resistance_broken': nearest_res
                })
                
        # SS (Strong Seller) Detection
        for h_idx, h_high, h_time in highs:
            prior_supports = [l_val for l_idx, l_val, l_time in lows if l_idx < h_idx]
            if not prior_supports:
                continue
            nearest_sup = prior_supports[-1]
            
            is_ss = False
            break_idx = -1
            for k in range(h_idx + 1, len(df)):
                if df['close'].iloc[k] > h_high:
                    break # invalidated
                if df['close'].iloc[k] < nearest_sup:
                    is_ss = True
                    break_idx = k
                    break
            if is_ss:
                body_max = max(df['open'].iloc[h_idx], df['close'].iloc[h_idx])
                ss_list.append({
                    'price': h_high,
                    'time': h_time,
                    'zone_low': body_max,
                    'zone_high': h_high,
                    'support_broken': nearest_sup
                })
                
        return sb_list, ss_list

    def update(self, analyst=None):
        """Update SOP Engine cycle, optionally synchronizing trend breakouts with the Chain Reaction analyst."""
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return
        self.current_price = tick.bid
        
        dfs = {}
        
        # 1. Fetch rates and determine trends/levels
        if analyst is not None:
            # Synchronize 100% of breakouts and SNR levels with Chain Reaction
            for name in self.tf_order:
                if name == "M1":
                    # M1 is not in Chain, so we scan it independently
                    mt5_tf = self.timeframes[name]
                    rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, 100)
                    if rates is not None and len(rates) > 0:
                        df = pd.DataFrame(rates)
                        df['time'] = pd.to_datetime(df['time'], unit='s')
                        dfs["M1"] = df
                        
                        # Simple local minor SNR breakouts for M1
                        last_close = df['close'].iloc[-2]
                        m1_sup = df['low'].iloc[-20:-2].min()
                        m1_res = df['high'].iloc[-20:-2].max()
                        self.tf_trends["M1"] = "BUY" if last_close > m1_res else ("SELL" if last_close < m1_sup else "WAIT")
                        self.sb_levels["M1"] = [{'price': m1_sup, 'zone_low': m1_sup - 0.5, 'zone_high': m1_sup}] if m1_sup > 0 else []
                        self.ss_levels["M1"] = [{'price': m1_res, 'zone_low': m1_res, 'zone_high': m1_res + 0.5}] if m1_res > 0 else []
                elif name in analyst.states:
                    st = analyst.states[name]
                    self.tf_trends[name] = st.cmp
                    
                    # Align S/R levels perfectly with Chain Reaction's minor SNR breakout lines
                    self.sb_levels[name] = [{
                        'price': st.sup,
                        'zone_low': st.sup - 1.5,
                        'zone_high': st.sup,
                        'time': datetime.now()
                    }] if st.sup > 0 else []
                    
                    self.ss_levels[name] = [{
                        'price': st.res,
                        'zone_low': st.res,
                        'zone_high': st.res + 1.5,
                        'time': datetime.now()
                    }] if st.res > 0 else []
                    
                    # Fetch M15/M5 rates for Fase 3 PMB sweeps
                    if name in ["M15", "M5"]:
                        mt5_tf = self.timeframes[name]
                        rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, 100)
                        if rates is not None and len(rates) > 0:
                            df = pd.DataFrame(rates)
                            df['time'] = pd.to_datetime(df['time'], unit='s')
                            dfs[name] = df
        else:
            # Standalone fallback: Detect levels structural pivots independently
            for name in self.tf_order:
                mt5_tf = self.timeframes[name]
                rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, 100)
                if rates is None or len(rates) == 0:
                    continue
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                dfs[name] = df
                
                sb, ss = self.detect_structural_sb_ss(df)
                self.sb_levels[name] = sb
                self.ss_levels[name] = ss
                
                if sb or ss:
                    newest_sb = sb[-1] if sb else None
                    newest_ss = ss[-1] if ss else None
                    if newest_sb and newest_ss:
                        self.tf_trends[name] = "BUY" if newest_sb['time'] > newest_ss['time'] else "SELL"
                    elif newest_sb:
                        self.tf_trends[name] = "BUY"
                    else:
                        self.tf_trends[name] = "SELL"
                else:
                    self.tf_trends[name] = "WAIT"

        # --- FASE 1: DIRECTIONAL MAPPING (MN1, W1, D1) ---
        # Lock direction based on Daily trend first, fallback to W1/MN1
        h_tfs = ["D1", "W1", "MN1"]
        for tf in h_tfs:
            if self.tf_trends[tf] != "WAIT":
                self.locked_direction = self.tf_trends[tf]
                break
        if self.locked_direction == "WAIT":
            self.locked_direction = "BUY" # Default fallback
            
        # --- FASE 5: VP/VR SAFETY LOGIC ---
        # Rule 3: No skip timeframe.
        # If a TF is counter-trend, its parent must also be counter-trend (unless it's the anchor itself).
        self.safety_veto = False
        self.safety_msg = "SAFETY: SYSTEM SECURE"
        
        # Track adjacent pairs for skip check: D1 -> H4 -> H1 -> M30 -> M15 -> M5 -> M1
        pairs = [("D1", "H4"), ("H4", "H1"), ("H1", "M30"), ("M30", "M15"), ("M15", "M5"), ("M5", "M1")]
        for parent, child in pairs:
            # If child has reversed counter to locked direction, but parent has NOT reversed
            if self.tf_trends[child] != "WAIT" and self.tf_trends[child] != self.locked_direction:
                if self.tf_trends[parent] == self.locked_direction:
                    self.safety_veto = True
                    self.safety_msg = f"VETO: Reversal skipped {parent} -> {child}"
                    break
                    
        # Rule 1 & 2: VP/VR Count check
        # Increment VP count if child flips against parent trend
        for parent, child in pairs:
            if self.tf_trends[child] != "WAIT" and self.tf_trends[child] != self.tf_trends[parent]:
                # This is a counter-parent flip.
                if self.vp_counts[child] == 0:
                    self.vp_counts[child] = 1 # Rule 1: first VP/VR is valid
                elif self.vp_counts[child] > 1:
                    # Rule 1 veto: VP/VR only once!
                    self.safety_veto = True
                    self.safety_msg = f"VETO: VP/VR occurred multiple times on {child}"
            elif self.tf_trends[child] == self.tf_trends[parent] and self.tf_trends[child] != "WAIT":
                # Rule 2: Continuation (flips back to parent trend direction)
                if self.vp_counts[child] == 1:
                    self.vp_counts[child] = 2 # Mark as continuation

        # --- FASE 2: MONITORING ZONES (H4, H1, M30) ---
        # Find active SB and SS levels closest to CMP
        self.active_mz = None
        self.standby_state = "STANDBY"
        
        m_tfs = ["H4", "H1", "M30"]
        for tf in m_tfs:
            sb_zones = self.sb_levels[tf]
            ss_zones = self.ss_levels[tf]
            
            # Find nearest SB below current price
            sb_below = [z for z in sb_zones if z['zone_high'] < self.current_price]
            # Find nearest SS above current price
            ss_above = [z for z in ss_zones if z['zone_low'] > self.current_price]
            
            # Check if current price is inside an SB zone (MZ BUY)
            sb_inside = [z for z in sb_zones if z['zone_low'] <= self.current_price <= z['zone_high']]
            # Check if current price is inside an SS zone (MZ SELL)
            ss_inside = [z for z in ss_zones if z['zone_low'] <= self.current_price <= z['zone_high']]
            
            if sb_inside and self.locked_direction == "BUY":
                self.active_mz = {
                    'tf': tf,
                    'type': 'BUY',
                    'low': sb_inside[-1]['zone_low'],
                    'high': sb_inside[-1]['zone_high'],
                    'level_ref': sb_inside[-1]['price']
                }
                self.standby_state = "READY"
                break
            elif ss_inside and self.locked_direction == "SELL":
                self.active_mz = {
                    'tf': tf,
                    'type': 'SELL',
                    'low': ss_inside[-1]['zone_low'],
                    'high': ss_inside[-1]['zone_high'],
                    'level_ref': ss_inside[-1]['price']
                }
                self.standby_state = "READY"
                break
                
        # --- FASE 3 & 4: DETEKSI TRIGGER & MTF RISK (M15, M5, M1) ---
        self.pmb_trigger = None
        if self.standby_state == "READY" and self.active_mz and not self.safety_veto:
            t_tfs = ["M15", "M5", "M1"]
            for tf in t_tfs:
                if tf not in dfs:
                    continue
                df = dfs[tf]
                
                # Check for PMB sweeps
                is_pmb, pmb_type, invalidation_price = self.detect_pmb_sweep(df)
                if is_pmb and pmb_type == self.active_mz['type']:
                    # Validate Multi Timeframe Jumps (Fase 4)
                    mz_tf = self.active_mz['tf']
                    mz_idx = self.tf_order.index(mz_tf)
                    pmb_idx = self.tf_order.index(tf)
                    
                    diff = pmb_idx - mz_idx
                    
                    if diff == 1:
                        # Adjacent Step
                        risk = "LOW/MEDIUM RISK (Level 2)"
                        # TP wajib at reference strong level (Opposite)
                        opposite_type = "SELL" if pmb_type == "BUY" else "BUY"
                        tp_zones = self.ss_levels[mz_tf] if opposite_type == "SELL" else self.sb_levels[mz_tf]
                        tp_price = tp_zones[-1]['price'] if tp_zones else (self.current_price + 3.0 if pmb_type == "BUY" else self.current_price - 3.0)
                        
                        self.pmb_trigger = {
                            'tf': tf,
                            'type': pmb_type,
                            'risk': risk,
                            'level': 2,
                            'tp': tp_price,
                            'sl': invalidation_price
                        }
                        break
                    elif diff == 2:
                        # Skipped Step
                        risk = "HIGH RISK (Level 1)"
                        # TP at nearest S/R
                        opposite_type = "SELL" if pmb_type == "BUY" else "BUY"
                        tp_zones = self.ss_levels[tf] if opposite_type == "SELL" else self.sb_levels[tf]
                        tp_price = tp_zones[-1]['price'] if tp_zones else (self.current_price + 1.5 if pmb_type == "BUY" else self.current_price - 1.5)
                        
                        self.pmb_trigger = {
                            'tf': tf,
                            'type': pmb_type,
                            'risk': risk,
                            'level': 1,
                            'tp': tp_price,
                            'sl': invalidation_price
                        }
                        break
                    else:
                        # Over-skipped or same TF ➡️ Veto
                        continue

    def detect_pmb_sweep(self, df):
        """
        Pecah Masuk Balik Sweep Detector:
        Pecah: price breaks minor S/R swing high/low of last 10 candles.
        Masuk Balik: returns back into the boundary.
        Momentum: body size >= 1.5x average size of last 10 candles, and >= 0.5 USD.
        """
        if len(df) < 15:
            return False, None, 0.0
            
        # We check the last closed candle (df.iloc[-2]) and current candle (df.iloc[-1])
        curr = df.iloc[-2]
        
        # Calculate average body size of previous 10 candles before curr
        prev_10 = df.iloc[-12:-2]
        avg_body = prev_10.apply(lambda r: abs(r['close'] - r['open']), axis=1).mean()
        
        # Calculate curr body
        curr_body = abs(curr['close'] - curr['open'])
        
        # Momentum check: 1.5x average body and >= 5 pips (0.5 USD)
        is_momentum = curr_body >= (1.5 * avg_body) and curr_body >= 0.5
        
        if not is_momentum:
            return False, None, 0.0
            
        # Support/Resistance sweeps of last 10 candles excluding curr
        swept_candles = df.iloc[-12:-2]
        minor_support = swept_candles['low'].min()
        minor_resistance = swept_candles['high'].max()
        
        # PMB BUY Sweep: low was below minor_support but closed above minor_support
        if curr['low'] < minor_support and curr['close'] > minor_support and curr['close'] > curr['open']:
            invalidation_price = curr['low']
            return True, "BUY", invalidation_price
            
        # PMB SELL Sweep: high was above minor_resistance but closed below minor_resistance
        if curr['high'] > minor_resistance and curr['close'] < minor_resistance and curr['close'] < curr['open']:
            invalidation_price = curr['high']
            return True, "SELL", invalidation_price
            
        return False, None, 0.0

    def get_bs_signal(self):
        """Returns the active signal from the BS Trading SOP Engine."""
        if self.pmb_trigger:
            return {
                'action': self.pmb_trigger['type'],
                'reason': f"BS PMB Sweep: {self.pmb_trigger['tf']} on {self.active_mz['tf']} MZ ({self.pmb_trigger['risk']})",
                'tf': self.pmb_trigger['tf'],
                'risk': self.pmb_trigger['risk'],
                'level': self.pmb_trigger['level'],
                'tp': self.pmb_trigger['tp'],
                'sl': self.pmb_trigger['sl']
            }
        return None

