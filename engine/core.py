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

        # 5. State Determination (Sequence: CMP -> VR -> CF)
        # VR = Child breaks Minor SNR against Parent Direction
        # CF = Child breaks Minor SNR aligned with Parent Direction (Must have VR first)
        
        status = "CMP"
        if parent_cmp != "WAIT":
            # CASE 1: Valid Reversal (VR)
            if self.cmp != parent_cmp and self.cmp != "WAIT":
                if self.cmp_change_time > self.parent_cmp_change_time:
                    self.vr_occurred = True
                    status = "VR"
            
            # CASE 2: Confirmation (CF)
            elif self.cmp == parent_cmp:
                # CF is valid ONLY if VR happened before
                status = "CF" if self.vr_occurred else "CMP"
        
        self.status = status
        return status

class SacredDoctrineAnalyst:
    """Orchestrates the Multi-TF sequence (MN1 down to M5) to find Sultan Strike opportunities."""
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
            "M5": mt5.TIMEFRAME_M5
        }
        self.states = {name: TFState(name) for name in self.timeframes}
        
    def update(self):
        """Update all TF states from top-down."""
        parent_cmp = "WAIT"
        parent_time = 0
        
        # Process from Highest to Lowest
        for name in ["MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"]:
            mt5_tf = self.timeframes[name]
            rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, 100)
            if rates is None or len(rates) == 0:
                continue
                
            df = pd.DataFrame(rates)
            # Add time conversion for timestamp handling
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Update state using parent's CMP
            self.states[name].update(df, parent_cmp, parent_time)
            
            # Current becomes parent for next TF
            parent_cmp = self.states[name].cmp
            parent_time = self.states[name].cmp_change_time
            
        return self.states

    def get_strike_signal(self):
        """
        Detects 'Sultan Strike' signal.
        Criteria:
        1. Setup TF (e.g., M15) must be in CF status.
        2. Master TF (e.g., H4) must be CMP aligned.
        3. Trigger TF (M5) must be in CF status.
        """
        # Logic: If M5 is CF and M15 is CF and H4 is aligned -> STRIKE
        m5 = self.states["M5"]
        m15 = self.states["M15"]
        h4 = self.states["H4"]
        
        if m5.status == "CF" and m15.status == "CF" and m5.cmp == h4.cmp:
            return {
                "action": m5.cmp,
                "reason": f"Sultan Strike: M5 CF + M15 CF Aligned with H4 {h4.cmp}",
                "tf": "M5"
            }
        
        # High Risk: Only M5 CF
        if m5.status == "CF":
             return {
                "action": m5.cmp,
                "reason": f"High Risk Strike: M5 CF Detected Aligned with M15 {m15.cmp}",
                "tf": "M5",
                "risk": "HIGH"
            }
            
        return None
