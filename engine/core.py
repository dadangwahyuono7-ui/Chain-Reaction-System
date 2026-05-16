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
            
        return None
