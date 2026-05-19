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
        Daily Deploy Doctrine — Pasangan TF yang benar (per seminar):

          SETUP H4  → VR di H1  → CF LOW = H1   / CF HIGH = M30  (H4_CF_HIGH)
          SETUP H1  → VR di M30 → CF LOW = M30  / CF HIGH = M15
          SETUP M30 → VR di M15 → CF LOW = M15  / CF HIGH = M5

        Urutan wajib (Time Law):
          H4 CMP → H1 VR dulu → baru boleh entry
          VR hanya SEKALI per setup. CF boleh berkali-kali selama CMP H4 valid.

        Empat tipe signal (prioritas aman → berisiko):
          ① MINOR_CF   : H1 CF + M30 solid + M15 solid + M5 VR→CF    SL=M5  TP=M15
          ② CF_LOW     : H1 CF + M30 solid + M15 VR→CF               SL=M15 TP=M30
          ③ CF_HIGH    : H1 CF + M30 solid + M15 VR  + M5 CF         SL=M15 TP=M30
          ④ H4_CF_HIGH : H1 VR (masih)  + M30 BO direction            SL=H1  TP=H4
        """
        h4  = self.states["H4"]
        h1  = self.states["H1"]
        m30 = self.states["M30"]
        m15 = self.states["M15"]
        m5  = self.states["M5"]

        """
        VR dan CF hanya STATUS CMP tiap TF — tidak ada blocking.
        Signal fires naturally ketika kondisi terpenuhi.
        CMP aktif = TF satu level di atas TF yang sedang VR.

        Prioritas signal (aman → berisiko):
          ① MINOR_CF   : M30+M15 solid + M5 VR→CF      SL=M5  TP=M15  (paling aman)
          ② CF_LOW     : M30 solid + M15 VR→CF          SL=M15 TP=M30
          ③ CF_HIGH    : M30 solid + M15 VR + M5 CF     SL=M15 TP=M30
          ④ H4_CF_HIGH : H1 VR + M30 CF                 SL=H1  TP=H4   (paling berisiko)

        Sub-chain (①②③) hanya aktif ketika M30 aligned dengan H4 direction.
        H4_CF_HIGH (④) hanya aktif ketika sub-chain belum ready.
        Tidak ada return None yang memblok — semua fall-through ke H4_CF_HIGH.
        """
        # H4 adalah direction master
        direction = h4.cmp
        if direction == "WAIT":
            return None

        h1_is_vr = (
            h1.cmp != direction and h1.cmp != "WAIT" and
            h1.cmp_change_time > h4.cmp_change_time
        )

        # ── Sub-chain: aktif ketika M30 aligned dengan direction ─────────────────
        # Tidak ada explicit block — jika M30 counter, sub-chain tidak aktif secara alami
        if m30.cmp == direction and m30.cmp != "WAIT":
            m15_is_vr = (
                m15.cmp != direction and m15.cmp != "WAIT" and
                m15.cmp_change_time > m30.cmp_change_time
            )
            m15_solid = (m15.cmp == direction and m15.cmp != "WAIT" and not m15_is_vr)
            # Time Law: M30 flip SETELAH M15 VR → M15 berhasil break M30, reset
            m30_stable = not (m15_is_vr and m30.cmp_change_time > m15.cmp_change_time)

            # ① MINOR_CF: M30+M15 solid → M5 VR→CF
            if m15_solid:
                if (m5.vr_occurred and
                    m5.cmp == direction and
                    m5.cmp_change_time > getattr(m5, "vr_change_time", 0) and
                    m5.cmp_change_time > m15.cmp_change_time):
                    return {
                        "action": direction,
                        "type":   "MINOR_CF",
                        "tf":     "M5",
                        "tp_tf":  "M15",
                        "sl_tf":  "M5",
                        "reason": f"Minor CF: M30+M15 solid | M5 VR→CF"
                    }
                # M5 belum ready — fall through ke H4_CF_HIGH

            elif m15_is_vr and m30_stable:
                # ② CF_LOW: M15 VR→CF
                if (m15.vr_occurred and
                    m15.cmp == direction and
                    m15.cmp_change_time > getattr(m15, "vr_change_time", 0)):
                    return {
                        "action": direction,
                        "type":   "CF_LOW",
                        "tf":     "M15",
                        "tp_tf":  "M30",
                        "sl_tf":  "M15",
                        "reason": f"CF Low: M30 solid | M15 VR→CF"
                    }
                # ③ CF_HIGH: M15 masih VR, M5 sudah CF
                if (m5.vr_occurred and
                    m5.cmp == direction and
                    m5.cmp_change_time > m15.cmp_change_time and
                    m5.cmp_change_time > getattr(m5, "vr_change_time", 0)):
                    return {
                        "action": direction,
                        "type":   "CF_HIGH",
                        "tf":     "M5",
                        "tp_tf":  "M30",
                        "sl_tf":  "M15",
                        "reason": f"CF High: M30 solid | M15 VR | M5 CF"
                    }
                # CF belum ready — fall through ke H4_CF_HIGH

        # ④ H4_CF_HIGH — prioritas terendah, hanya ketika sub-chain belum ready
        # H1 VR = H1 sedang nguji H4. M30 BO ke direction = konfirmasi H4 CF HIGH
        if (h1_is_vr and
            m30.cmp == direction and m30.cmp != "WAIT" and
            m30.cmp_change_time > h1.cmp_change_time):
            return {
                "action": direction,
                "type":   "H4_CF_HIGH",
                "tf":     "M30",
                "tp_tf":  "H4",
                "sl_tf":  "H1",
                "reason": f"H4 {direction} | H1 VR | M30 CF HIGH ⚡"
            }

        return None
            
    def get_chain_status(self):
        """Returns structured chain state for dashboard panels."""
        h4  = self.states["H4"]
        h1  = self.states["H1"]
        m30 = self.states["M30"]
        m15 = self.states["M15"]
        m5  = self.states["M5"]

        # H4 = direction master (doctrine: semua signal ikut H4)
        direction = h4.cmp
        opp = "SELL" if direction == "BUY" else "BUY"
        step1_ok = direction != "WAIT"

        # ── H1 state relative to H4 ───────────────────────────────────────────────
        # H1 VR = H1 sudah BO berlawanan dengan H4 (prerequisite utama entry)
        h1_is_vr = (
            step1_ok and
            h1.cmp != direction and h1.cmp != "WAIT" and
            h1.cmp_change_time > h4.cmp_change_time
        )
        h1_is_cf = (
            step1_ok and
            h1.vr_occurred and h1.cmp == direction and
            h1.cmp_change_time > getattr(h1, "vr_change_time", 0)
        )

        # ── H4_CF_HIGH: H1 VR + M30 CF ───────────────────────────────────────────
        h4_cf_high_ready = (
            h1_is_vr and
            m30.cmp == direction and m30.cmp != "WAIT" and
            m30.cmp_change_time > h1.cmp_change_time
        )

        # ── M30 state relative to H4 ─────────────────────────────────────────────
        m30_vr_to_h4_flag = (
            step1_ok and m30.cmp != direction and m30.cmp != "WAIT"
        )

        # Macro role
        h1_vr_to_h4 = h1_is_vr
        if m30_vr_to_h4_flag and not h1_is_vr:
            macro_role = "VR_H4"        # M30 counter H4 (no H1 VR) — block
        elif h4_cf_high_ready:
            macro_role = "CF_HIGH_H4"   # H1 VR + M30 CF = power signal
        elif h1_is_vr:
            macro_role = "CF_H4"        # H1 VR, M30 belum CF
        else:
            macro_role = "SOLID_H4"     # Semua aligned, CONTI territory

        # ── M15 state (available when M30 aligned) ───────────────────────────────
        m30_aligned = (step1_ok and m30.cmp == direction)
        m15_is_vr = (
            m30_aligned and
            m15.cmp != direction and m15.cmp != "WAIT" and
            m15.cmp_change_time > m30.cmp_change_time
        )
        m15_solid = (
            m30_aligned and
            m15.cmp == direction and m15.cmp != "WAIT" and
            not m15_is_vr
        )
        m30_broken = (m15_is_vr and m30.cmp_change_time > m15.cmp_change_time)
        m30_stable = not m30_broken

        # ── CF detection ──────────────────────────────────────────────────────────
        cf_ready = False
        cf_type  = ""

        if h4_cf_high_ready:
            cf_ready = True
            cf_type  = "H4_CF_HIGH"

        elif m30_aligned:
            if m15_solid:
                if (m5.vr_occurred and m5.cmp == direction and
                    m5.cmp_change_time > getattr(m5, "vr_change_time", 0) and
                    m5.cmp_change_time > m15.cmp_change_time):
                    cf_ready = True
                    cf_type  = "MINOR_CF"
            elif m15_is_vr and m30_stable:
                if (m15.vr_occurred and m15.cmp == direction and
                    m15.cmp_change_time > getattr(m15, "vr_change_time", 0)):
                    cf_ready = True
                    cf_type  = "CF_LOW"
                elif (m5.vr_occurred and m5.cmp == direction and
                      m5.cmp_change_time > m15.cmp_change_time and
                      m5.cmp_change_time > getattr(m5, "vr_change_time", 0)):
                    cf_ready = True
                    cf_type  = "CF_HIGH"

        # ── Cascade roles (semua TF vs H4 direction) ─────────────────────────────
        h4_dir = h4.cmp
        cascade_tfs   = []
        cascade_roles = {}
        for tf_name, st in [("H1", h1), ("M30", m30), ("M15", m15), ("M5", m5)]:
            if h4_dir == "WAIT" or st.cmp == "WAIT":
                cascade_roles[tf_name] = "WAIT"
            elif st.cmp != h4_dir:
                cascade_tfs.append(tf_name)
                cascade_roles[tf_name] = "VR"
            else:
                cascade_roles[tf_name] = "CF" if st.vr_occurred else "CMP"

        cascade_depth = len(cascade_tfs)

        h1_is_cf = (
            step1_ok and
            h1.vr_occurred and h1.cmp == direction and
            h1.cmp_change_time > getattr(h1, "vr_change_time", 0)
        )

        return {
            "direction":     direction,
            "opposite":      opp,
            "step1_ok":      step1_ok,
            # H1 phase info (informational, bukan gate)
            "h1_is_vr":      h1_is_vr,   # H1 sedang VR ke H4 (retracement)
            "h1_is_cf":      h1_is_cf,   # H1 sudah CF balik ke direction
            # M30/M15 sub-chain
            "m30_aligned":   m30_aligned,
            "m15_is_vr":     m15_is_vr,
            "m15_solid":     m15_solid,
            "m30_stable":    m30_stable,
            "m30_broken":    m30_broken,
            # CF
            "cf_ready":      cf_ready,
            "cf_type":       cf_type,
            # Backward-compat keys
            "macro_role":    macro_role,
            "m30_vr_to_h4":  m30_vr_to_h4_flag,
            "h1_vr_to_h4":   h1_vr_to_h4,
            "cascade_depth": cascade_depth,
            "cascade_tfs":   cascade_tfs,
            "cascade_roles": cascade_roles,
        }

    def get_strategic_forecast(self):
        """Plain-language narrative aligned with Daily Deploy doctrine (H4→H1→M30→M15→M5)."""
        cs = self.get_chain_status()
        direction = cs["direction"]
        opp       = cs["opposite"]
        d_col     = "green" if direction == "BUY" else "red" if direction == "SELL" else "white"

        if not cs["step1_ok"]:
            return "H4 SCANNING: Menunggu breakout H4 untuk menentukan direction utama."

        # ── H4_CF_HIGH: H1 VR + M30 CF ───────────────────────────────────────────
        if cs["cf_ready"] and cs["cf_type"] == "H4_CF_HIGH":
            return (f"[blink bold magenta]⚡ H4_CF_HIGH SIAP[/]: "
                    f"H4 {direction} | H1 VR ({opp}) | M30 CF ({direction}). "
                    f"HIGH RISK — 3 TF! SL=H1 SNR | TP=H4 SNR")

        if cs["h1_is_vr"]:
            return (f"[bold {d_col}]H4 {direction}[/] | [bold red]H1 VR ({opp})[/] — "
                    f"H4 sedang ditest H1. Menunggu M30 BO {direction} (H4_CF_HIGH) "
                    f"atau M30 VR lalu cari CF di M15/M5.")

        # ── H1 belum VR: CONTI territory ─────────────────────────────────────────
        # H4 direction kuat, semua TF masih aligned → cari CF di sub-chain
        if not cs["h1_is_vr"] and not cs["h1_is_cf"]:
            # Sub-chain masih bisa entry (CONTI)
            if cs["cf_ready"] and cs["cf_type"] == "MINOR_CF":
                return (f"[blink bold green]✅ MINOR CF SIAP[/] [grey62](CONTI)[/]: "
                        f"H4+M30+M15 solid | M5 VR→CF. SL=M5 | TP=M15")
            if cs["cf_ready"] and cs["cf_type"] == "CF_LOW":
                return (f"[blink bold green]🔥 CF LOW SIAP[/] [grey62](CONTI)[/]: "
                        f"H4+M30 solid | M15 VR→CF. SL=M15 | TP=M30")
            if cs["cf_ready"] and cs["cf_type"] == "CF_HIGH":
                return (f"[blink bold yellow]⚡ CF HIGH SIAP[/] [grey62](CONTI)[/]: "
                        f"H4+M30 solid | M15 VR | M5 CF. SL=M15 | TP=M30")
            if cs["m30_vr_to_h4"]:
                return (f"[bold {d_col}]H4 {direction}[/] [grey62](CONTI — H1 aligned)[/] | "
                        f"[bold red]M30 VR[/] ke H4 — Tunggu CF di M15/M5.")
            if cs["m15_solid"]:
                return (f"[bold {d_col}]H4+M30+M15 SOLID[/] [grey62](CONTI)[/] — "
                        f"Tunggu M5 VR→CF ({opp} → {direction}).")
            if cs["m15_is_vr"]:
                return (f"[bold {d_col}]H4+M30 solid[/] [grey62](CONTI)[/] | "
                        f"[bold blue]M15 VR {opp}[/] — Tunggu M5 CF {direction} (CF HIGH) "
                        f"atau M15 balik {direction} (CF LOW).")
            return (f"[bold {d_col}]H4 {direction}[/] [grey62](CONTI — H1 masih aligned)[/] — "
                    f"Menunggu VR di sub-chain (M30/M15/M5) untuk CF entry.")

        # ── H1 sudah CF: sub-chain aktif ─────────────────────────────────────────
        if cs["m30_broken"]:
            return (f"[bold red]⚠ SETUP BATAL[/]: M15 VR berhasil break M30 CMP [{d_col}]{direction}[/]. "
                    f"Tunggu M30 rebuild.")

        if cs["m30_vr_to_h4"]:
            return (f"[bold {d_col}]H4+H1 CF[/] | [bold red]M30 VR ke H4[/] — "
                    f"M30 counter {direction}. Tunggu CF di M15/M5.")

        if cs["cf_ready"] and cs["cf_type"] == "MINOR_CF":
            return (f"[blink bold green]✅ MINOR CF SIAP[/]: "
                    f"H4+H1+M30+M15 solid | M5 VR→CF. SAFEST ENTRY! SL=M5 | TP=M15")

        if cs["cf_ready"] and cs["cf_type"] == "CF_LOW":
            return (f"[blink bold green]🔥 CF LOW RISK SIAP[/]: "
                    f"H4+H1+M30 solid | M15 VR→CF. EXECUTE! SL=M15 | TP=M30")

        if cs["cf_ready"] and cs["cf_type"] == "CF_HIGH":
            return (f"[blink bold yellow]⚡ CF HIGH RISK SIAP[/]: "
                    f"H4+H1+M30 solid | M15 VR | M5 CF. CAUTION! SL=M15 | TP=M30")

        if cs["m15_solid"]:
            return (f"[bold green]H4+H1+M30+M15 SOLID[/] | "
                    f"Tunggu M5 flip {opp} (VR ke M15) → balik {direction} (MINOR CF).")

        if cs["m15_is_vr"]:
            return (f"[bold cyan]H4+H1+M30 solid[/] | [bold blue]M15 VR {opp}[/] — "
                    f"Tunggu M5 CF {direction} (CF HIGH) atau M15 balik {direction} (CF LOW).")

        return (f"[bold {d_col}]H4+H1 CF | M30={direction}[/] — "
                f"Tunggu M15 solid+M5 VR (MINOR CF) atau M15 VR {opp} (CF LOW/HIGH).")
                
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

    def get_market_regime(self):
        """
        Deteksi trending vs sideways.

        Sistem CMP→VR→CF HANYA bekerja di market trending.
        Di sideways: H4 tidak punya CMP kuat → cascade tidak selesai →
        VR terus muncul tanpa CF yang valid → terus rugi kecil-kecil.

        Cara deteksi:
        1. H4 CMP = WAIT → belum ada breakout master → sideways pasti
        2. Sentiment seimbang (gap < 20%) → tidak ada dominasi arah → sideways
        3. H4 range (res-sup) terlalu kecil → harga terkompresi → konsolidasi
        4. Cascade depth terlalu tinggi (≥3) → counter-move sudah merembet jauh → choppy
        """
        h4  = self.states["H4"]
        buy_pct, sell_pct = self.get_total_sentiment()
        sentiment_gap = abs(buy_pct - sell_pct)

        # 1. H4 master belum breakout
        if h4.cmp == "WAIT":
            return "SIDEWAYS", "H4 belum breakout Minor SNR — master tanpa arah"

        # 2. Sentiment terlalu seimbang (semua TF bolak-balik, tidak ada dominasi)
        if sentiment_gap < 15:
            return "SIDEWAYS", f"Sentiment seimbang ({buy_pct:.0f}%/{sell_pct:.0f}%) — tidak ada trend"

        # 3. H4 range terlalu sempit (harga terkompresi di dalam range kecil)
        h4_range = h4.res - h4.sup if h4.res > h4.sup > 0 else 0
        if 0 < h4_range < 2.5:  # < 2.5 USD = sangat sempit untuk XAUUSD
            return "SIDEWAYS", f"H4 range {h4_range:.1f} USD — market compressed, hindari entry"

        # 4. Trending kuat — cascade dari bawah bisa naik sampai H4
        if sentiment_gap > 45:
            dominant = "BUY" if buy_pct > sell_pct else "SELL"
            return "TRENDING", f"Strong {dominant} ({sentiment_gap:.0f}% gap) — CF cascade valid"

        # 5. Ranging — ada trend tapi tidak kuat, CF bisa gagal di tengah
        dominant = "BUY" if buy_pct > sell_pct else "SELL"
        return "RANGING", f"Moderate {dominant} ({sentiment_gap:.0f}% gap) — hati-hati sideways lokal"


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
        self.last_locked_direction = "WAIT"  # tracks direction changes for counter reset

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

        # Reset VP/VR counters whenever the locked direction flips — prevents veto
        # bleeding into a new trend that hasn't triggered any reversal yet.
        if self.locked_direction != self.last_locked_direction:
            self.vp_counts = {name: 0 for name in self.timeframes}
            self.last_locked_direction = self.locked_direction
            
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


class DailyDeployAnalyst:  # kept for import compatibility — logic now inside get_strike_signal()
    """
    Daily Deploy System — "Cheat Code of Direction"
    (Seminar Daily Deploy PDF by Bonker)

    Three cascading setup layers run in parallel:
      D1_DEPLOY : direction=D1  → VR=H4  → CF_Low=H4  / CF_High=H1
      H4_DEPLOY : direction=H4  → VR=H1  → CF_Low=H1  / CF_High=M30
      H1_DEPLOY : direction=H1  → VR=M30 → CF_Low=M30 / CF_High=M15

    Signal types per layer:
      CONTI    — trade every direction-aligned BO at VR TF *before* VR occurs
      CF_LOW   — 2-TF system: VR TF itself flips back → entry (lower risk)
      CF_HIGH  — 3-TF system: one TF below VR gives direction BO → entry (higher risk)

    Rules enforced:
      • VR only counted ONCE per setup (resets on direction flip)
      • VR must occur AFTER the direction TF breakout (Time Law)
      • CF must occur AFTER VR time
      • CF_HIGH only fires when CF_LOW has not yet fired (hierarchy)
    """

    LAYERS = [
        {"name": "D1_DEPLOY", "dir_tf": "D1",  "vr_tf": "H4",  "cf_low_tf": "H4",  "cf_high_tf": "H1"},
        {"name": "H4_DEPLOY", "dir_tf": "H4",  "vr_tf": "H1",  "cf_low_tf": "H1",  "cf_high_tf": "M30"},
        {"name": "H1_DEPLOY", "dir_tf": "H1",  "vr_tf": "M30", "cf_low_tf": "M30", "cf_high_tf": "M15"},
    ]

    def __init__(self, symbol):
        self.symbol = symbol
        self.current_price = 0.0
        self.active_signals = []
        self.layer_states = {
            l["name"]: {"direction": "WAIT", "vr_occurred": False, "vr_time": 0}
            for l in self.LAYERS
        }

    def update(self, analyst):
        """
        Evaluate all three cascade layers using live TFState data from
        the SacredDoctrineAnalyst. Must be called AFTER analyst.update().
        """
        tick = mt5.symbol_info_tick(self.symbol)
        if tick:
            self.current_price = tick.bid

        self.active_signals = []

        for layer in self.LAYERS:
            name    = layer["name"]
            state   = self.layer_states[name]
            dir_st  = analyst.states[layer["dir_tf"]]
            vr_st   = analyst.states[layer["vr_tf"]]
            cfl_st  = analyst.states[layer["cf_low_tf"]]
            cfh_st  = analyst.states.get(layer["cf_high_tf"])
            direction = dir_st.cmp

            # Reset layer on direction flip or WAIT
            if direction == "WAIT" or direction != state["direction"]:
                state["direction"] = direction
                state["vr_occurred"] = False
                state["vr_time"] = 0
                if direction == "WAIT":
                    continue

            # ── VR Detection ──────────────────────────────────────────────
            # VR = vr_tf broke COUNTER to direction, AFTER direction_tf breakout
            vr_counter = vr_st.cmp != direction and vr_st.cmp != "WAIT"
            vr_after   = vr_st.cmp_change_time > dir_st.cmp_change_time

            if vr_counter and vr_after and not state["vr_occurred"]:
                state["vr_occurred"] = True
                state["vr_time"]     = vr_st.cmp_change_time

            if not state["vr_occurred"]:
                # ── CONTI (Pre-VR) ────────────────────────────────────────
                # Trade every BO at vr_tf that aligns with direction,
                # while waiting for the VR to occur.
                if vr_st.cmp == direction and vr_st.cmp_change_time > dir_st.cmp_change_time:
                    self.active_signals.append({
                        "layer":    name,
                        "action":   direction,
                        "type":     "CONTI",
                        "risk":     "MEDIUM",
                        "dir_tf":   layer["dir_tf"],
                        "entry_tf": layer["vr_tf"],
                        "reason":   f"CONTI {layer['dir_tf']}→{layer['vr_tf']} (pre-VR, direction {direction})"
                    })
            else:
                # ── CF Low Risk ───────────────────────────────────────────
                # cf_low_tf (same TF as vr_tf) returns to direction AFTER vr_time
                cf_low_ok = (
                    cfl_st.cmp == direction and
                    cfl_st.cmp_change_time > state["vr_time"]
                )
                if cf_low_ok:
                    self.active_signals.append({
                        "layer":    name,
                        "action":   direction,
                        "type":     "CF_LOW",
                        "risk":     "LOW",
                        "dir_tf":   layer["dir_tf"],
                        "entry_tf": layer["cf_low_tf"],
                        "reason":   f"CF Low {layer['dir_tf']}→{layer['vr_tf']}→{layer['cf_low_tf']}"
                    })

                # ── CF High Risk ──────────────────────────────────────────
                # One TF below VR aligns with direction AFTER vr_time.
                # Only fires when CF_LOW has NOT yet fired (hierarchy).
                elif cfh_st and not cf_low_ok:
                    cf_high_ok = (
                        cfh_st.cmp == direction and
                        cfh_st.cmp_change_time > state["vr_time"]
                    )
                    if cf_high_ok:
                        self.active_signals.append({
                            "layer":    name,
                            "action":   direction,
                            "type":     "CF_HIGH",
                            "risk":     "HIGH",
                            "dir_tf":   layer["dir_tf"],
                            "entry_tf": layer["cf_high_tf"],
                            "reason":   f"CF High {layer['dir_tf']}→{layer['vr_tf']}→{layer['cf_high_tf']}"
                        })

    def get_best_signal(self):
        """
        Return highest-priority active signal.
        Priority: CF_LOW > CF_HIGH > CONTI, then D1_DEPLOY > H4_DEPLOY > H1_DEPLOY.
        """
        if not self.active_signals:
            return None
        type_pri  = {"CF_LOW": 0, "CF_HIGH": 1, "CONTI": 2}
        layer_pri = {"D1_DEPLOY": 0, "H4_DEPLOY": 1, "H1_DEPLOY": 2}
        return sorted(
            self.active_signals,
            key=lambda s: (type_pri.get(s["type"], 99), layer_pri.get(s["layer"], 99))
        )[0]

    def get_layer_summary(self):
        """Returns list of per-layer status strings for UI rendering."""
        lines = []
        for layer in self.LAYERS:
            name  = layer["name"]
            state = self.layer_states[name]
            label = name.replace("_DEPLOY", "")
            direction = state["direction"]
            phase = "VR✓ waiting CF" if state["vr_occurred"] else "pre-VR (CONTI)"
            col   = "green" if direction == "BUY" else "red" if direction == "SELL" else "dim white"
            lines.append(f"[bold {col}]{label}[/] [{col}]{direction}[/] | [dim]{phase}[/]")
        return lines

