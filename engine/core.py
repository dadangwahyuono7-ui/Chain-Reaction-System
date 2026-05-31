import time
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
        self.last_parent_cmp_change_time = 0
        # ── CF fire/fail tracking ─────────────────────────────────────────────
        self.cf_fire_time = 0      # Timestamp saat CF terakhir fire (breakout valid)
        self.cf_fail_time = 0      # Timestamp saat CF terakhir gagal (TF flip balik)
        self.cf_failed    = False  # True = CF terakhir gagal, tunggu CF baru
        # ── CF count: berapa kali CF sudah fire pada VR setup ini ─────────────
        # Doktrin: VR hanya sekali, CF berkali-kali selama CMP master belum flip
        # cf_count naik setiap CF baru fire setelah pullback (cf_fail → cf_fire)
        # Reset ke 0 hanya ketika parent CMP berubah (siklus baru)
        self.cf_count = 0

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
            # Arah parent berubah → reset total termasuk CF tracking
            # Ini adalah "CMP flip" — VR berhasil jebol barrier, siklus baru mulai
            self.parent_cmp_change_time = parent_change_time
            self.vr_occurred  = False
            self.last_parent_cmp = parent_cmp
            # Reset CF tracking — siklus baru, slate bersih
            self.cf_fire_time = 0
            self.cf_fail_time = 0
            self.cf_failed    = False
            self.cf_count     = 0   # VR baru = hitungan CF kembali ke 0
        elif parent_change_time > self.parent_cmp_change_time:
            # Arah parent SAMA tapi CMP baru terbentuk di level SNR berbeda
            # (mis. H4 masih BUY tapi baru break level baru yang lebih tinggi)
            # → VR dari siklus lama tidak relevan lagi → reset
            if self.vr_occurred and self.vr_change_time < parent_change_time:
                self.vr_occurred  = False   # ← FIX: stale VR dari siklus lama
                # Reset CF tracking juga — VR lama sudah tidak relevan
                self.cf_fire_time = 0
                self.cf_fail_time = 0
                self.cf_failed    = False
                self.cf_count     = 0
            self.parent_cmp_change_time = parent_change_time

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
                        self.vr_occurred    = True
                        self.vr_change_time = self.cmp_change_time  # Record VR time

                    # ── CF FAIL DETECTION ─────────────────────────────────────
                    # Kalau sebelumnya ada CF yang fire, dan sekarang CMP flip balik
                    # berlawanan → CF yang tadi GAGAL
                    if (self.cf_fire_time > 0 and
                            not self.cf_failed and
                            self.cmp_change_time > self.cf_fire_time):
                        self.cf_failed    = True
                        self.cf_fail_time = self.cmp_change_time

                    status = "VR"

            # CASE 2: Confirmation (CF)
            elif self.cmp == parent_cmp:
                # CF is valid ONLY if:
                # 1. VR sudah terjadi sebelumnya
                # 2. VR terjadi SETELAH parent CMP saat ini — bukan dari siklus parent lama
                # 3. CF breakout ini terjadi SETELAH VR (Strict Chronological Law)
                # 4. CF breakout ini terjadi SETELAH cf_fail_time terakhir (fresh CF)
                vr_in_current_cycle = self.vr_change_time > self.parent_cmp_change_time
                is_fresh_cf         = self.cmp_change_time > self.cf_fail_time  # True jika belum pernah fail
                if (self.vr_occurred and
                        vr_in_current_cycle and
                        self.cmp_change_time > self.vr_change_time and
                        is_fresh_cf):
                    status = "CF"
                    # ── Record CF fire time ───────────────────────────────────
                    if self.cmp_change_time > self.cf_fire_time:
                        self.cf_fire_time = self.cmp_change_time
                        self.cf_failed    = False   # Fresh CF → reset fail flag
                        self.cf_count    += 1       # VR hanya sekali, CF berkali-kali
                else:
                    # Sama arah dengan parent tapi tanpa VR yang valid → CMP biasa
                    status = "CMP"
                    self.vr_occurred = False  # Reset jika langsung ikut parent tanpa reversal
        
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
                # The Master TF — update dengan context parent (TF di atasnya)
                self.states[name].update(df, context_parent_cmp, context_parent_time)
                self.master_cmp = self.states[name].cmp
                self.master_time = self.states[name].cmp_change_time
                self.states[name].status = "MASTER"
                # Chain ke bawah dimulai dari master sebagai direct parent
                chain_parent_cmp  = self.master_cmp
                chain_parent_time = self.master_time

            else:
                # ── DOCTRINE: VR = 1 TF di bawah CMP-nya ─────────────────────
                # Setiap child TF pakai DIRECT parent-nya (bukan H4/master langsung)
                # Chain: H4 (master) → H1 → M30 → M15 → M5
                # H1  VR check: H1.cmp_change_time  > H4.cmp_change_time  ✅
                # M30 VR check: M30.cmp_change_time > H1.cmp_change_time  ✅
                # M15 VR check: M15.cmp_change_time > M30.cmp_change_time ✅
                # M5  VR check: M5.cmp_change_time  > M15.cmp_change_time ✅
                self.states[name].update(df, chain_parent_cmp, chain_parent_time)
                # Update chain untuk TF berikutnya (direct parent ke bawah)
                chain_parent_cmp  = self.states[name].cmp
                chain_parent_time = self.states[name].cmp_change_time

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
                    m5.cmp_change_time > m15.cmp_change_time and
                    m5.cmp_change_time > getattr(m5, "cf_fail_time", 0)):   # ← fresh CF guard
                    return {
                        "action": direction,
                        "type":   "MINOR_CF",
                        "tf":     "M5",
                        "tp_tf":  "M15",
                        "sl_tf":  "M5",
                        "grade":  self.get_signal_grade("MINOR_CF"),
                        "reason": f"Minor CF: M30+M15 solid | M5 VR→CF"
                    }
                # M5 belum ready — fall through ke H4_CF_HIGH

            elif m15_is_vr and m30_stable:
                # ② CF_LOW: M15 VR→CF
                if (m15.vr_occurred and
                    m15.cmp == direction and
                    m15.cmp_change_time > getattr(m15, "vr_change_time", 0) and
                    m15.cmp_change_time > getattr(m15, "cf_fail_time", 0)):  # ← fresh CF guard
                    return {
                        "action": direction,
                        "type":   "CF_LOW",
                        "tf":     "M15",
                        "tp_tf":  "M30",
                        "sl_tf":  "M15",
                        "grade":  self.get_signal_grade("CF_LOW"),
                        "reason": f"CF Low: M30 solid | M15 VR→CF"
                    }
                # ③ CF_HIGH: M15 masih VR, M5 sudah CF
                if (m5.vr_occurred and
                    m5.cmp == direction and
                    m5.cmp_change_time > m15.cmp_change_time and
                    m5.cmp_change_time > getattr(m5, "vr_change_time", 0) and
                    m5.cmp_change_time > getattr(m5, "cf_fail_time", 0)):   # ← fresh CF guard
                    return {
                        "action": direction,
                        "type":   "CF_HIGH",
                        "tf":     "M5",
                        "tp_tf":  "M30",
                        "sl_tf":  "M15",
                        "grade":  self.get_signal_grade("CF_HIGH"),
                        "reason": f"CF High: M30 solid | M15 VR | M5 CF"
                    }
                # CF belum ready — fall through ke H4_CF_HIGH

        # ④ H4_CF_HIGH — prioritas terendah, hanya ketika sub-chain belum ready
        # H1 VR = H1 sedang nguji H4. M30 BO ke direction = konfirmasi H4 CF HIGH
        if (h1_is_vr and
            m30.cmp == direction and m30.cmp != "WAIT" and
            m30.cmp_change_time > h1.cmp_change_time and
            m30.cmp_change_time > getattr(m30, "cf_fail_time", 0)):  # ← fresh CF guard
            return {
                "action": direction,
                "type":   "H4_CF_HIGH",
                "tf":     "M30",
                "tp_tf":  "H4",
                "sl_tf":  "H1",
                "grade":  self.get_signal_grade("H4_CF_HIGH"),
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

        if h4_cf_high_ready and m30.cmp_change_time > getattr(m30, "cf_fail_time", 0):
            cf_ready = True
            cf_type  = "H4_CF_HIGH"

        elif m30_aligned:
            if m15_solid:
                if (m5.vr_occurred and m5.cmp == direction and
                    m5.cmp_change_time > getattr(m5, "vr_change_time", 0) and
                    m5.cmp_change_time > m15.cmp_change_time and
                    m5.cmp_change_time > getattr(m5, "cf_fail_time", 0)):   # fresh CF guard
                    cf_ready = True
                    cf_type  = "MINOR_CF"
            elif m15_is_vr and m30_stable:
                if (m15.vr_occurred and m15.cmp == direction and
                    m15.cmp_change_time > getattr(m15, "vr_change_time", 0) and
                    m15.cmp_change_time > getattr(m15, "cf_fail_time", 0)):  # fresh CF guard
                    cf_ready = True
                    cf_type  = "CF_LOW"
                elif (m5.vr_occurred and m5.cmp == direction and
                      m5.cmp_change_time > m15.cmp_change_time and
                      m5.cmp_change_time > getattr(m5, "vr_change_time", 0) and
                      m5.cmp_change_time > getattr(m5, "cf_fail_time", 0)):  # fresh CF guard
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
                # VR state — tapi cek apakah ini setelah CF yang gagal
                if (getattr(st, "cf_failed", False) and
                        getattr(st, "cf_fire_time", 0) > 0):
                    cascade_tfs.append(tf_name)
                    cascade_roles[tf_name] = "CF_FAIL"  # CF gagal, balik VR lagi
                else:
                    cascade_tfs.append(tf_name)
                    cascade_roles[tf_name] = "VR"
            else:
                # Aligned dengan H4 — CF atau CMP biasa
                if st.vr_occurred and getattr(st, "cf_fire_time", 0) > 0:
                    cascade_roles[tf_name] = "CF"
                elif st.vr_occurred:
                    cascade_roles[tf_name] = "CF"      # vr_occurred tapi belum fire
                else:
                    cascade_roles[tf_name] = "CMP"

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

    def get_signal_grade(self, signal_type: str) -> str:
        """
        Grade setup A+/A/B/C per doktrin — VR dari TF mana + momentum:

          A+ : CF_LOW dengan H1 sudah balik CF searah H4 + market TRENDING
               → Full cascade sempurna, level SL jauh, momentum paling kuat
          A  : CF_LOW dengan H1 masih VR  ATAU  H4_CF_HIGH (H1 VR + M30 CF)
               → VR dari H1 (TF besar), momentum kuat
          B  : CF_HIGH (VR dari M15, M5 masuk duluan)  ATAU  CF_LOW di CONTI territory
               → Entry lebih awal, SL lebih dekat, risk lebih besar
          C  : MINOR_CF (VR dari M5, TP kecil di M15)
               → Paling cepat, paling kecil, cocok scalp saja

        Market regime modifier:
          TRENDING → naik setengah notch (B jadi B+, A jadi A+)
          SIDEWAYS → turun notch (A jadi B, B jadi C)
        """
        h4  = self.states["H4"]
        h1  = self.states["H1"]
        direction = h4.cmp

        h1_is_vr = (
            h1.cmp != direction and h1.cmp != "WAIT" and
            h1.cmp_change_time > h4.cmp_change_time
        )
        h1_is_cf = (
            h1.vr_occurred and h1.cmp == direction and
            h1.cmp_change_time > getattr(h1, "vr_change_time", 0)
        )

        regime, _ = self.get_market_regime()
        trending  = (regime == "TRENDING")
        sideways  = (regime == "SIDEWAYS")

        if signal_type == "H4_CF_HIGH":
            # H1 VR + M30 CF: power signal, VR dari H1
            return "A+" if trending else "A"

        if signal_type == "CF_LOW":
            if h1_is_cf:
                return "A+"                           # Full cascade confirmed
            elif h1_is_vr:
                return "B" if sideways else "A"       # H1 sedang VR, momentum besar
            else:
                return "C" if sideways else "B"       # CONTI territory, tanpa H1 VR

        if signal_type == "CF_HIGH":
            if h1_is_cf or h1_is_vr:
                return "A" if trending else "B"
            else:
                return "C" if sideways else "B"

        if signal_type == "MINOR_CF":
            return "B" if (h1_is_cf and trending) else "C"

        return "C"

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
                
    def get_active_cmp_scan(self) -> list:
        """
        Cara paling sederhana baca market — langsung dari doktrin:

            "TF yang sedang VR → TF atasnya adalah CMP yang AKTIF.
             Tunggu CF di TF itu → ENTRY."

        Tidak perlu set master TF dulu.
        Cukup scan semua TF, cari yang VR terhadap parent langsungnya.
        TF atas parent tersebut = setup yang sedang berjalan.

        ── SETUP STRENGTH (dari status master di TF-nya sendiri) ────────────
        STRONG  : master TF statusnya CF ke parent-nya
          → VR sebelumnya GAGAL mengubah parent direction → direction CONFIRMED
          → Price akan jalan JAUH, bisa tembus ke parent barrier (extended TP)
          Contoh: H4 CF ke D1 → setup di H1 adalah BUY KUAT karena D1 confirmed

        NORMAL  : master TF langsung aligned tanpa VR (PRIMARY atau CONTI)
          → Direction valid tapi belum ada konfirmasi dari siklus VR→CF
          → TP ke master barrier saja

        LIMITED : master TF statusnya VR ke parent-nya (counter-trend)
          → Master hanya retracement, dibatasi parent barrier
          → Jangan ikut kecuali berani ambil risiko (danger_level > 0)
          Contoh: H4 VR ke D1 → H4 SELL tapi D1 BUY, setup terbatas

        ── Extended TP ───────────────────────────────────────────────────────
        Kalau setup_strength = STRONG (master CF ke parent):
          - TP normal  = master barrier
          - TP extended = parent barrier (karena parent direction confirmed juga)

        Dari sini juga langsung ketahuan:
          - Berapa TF yang VR sekarang = seberapa dalam retracement berlangsung
          - Danger level = berapa layer yang sedang counter terhadap setup utama
          - VR TF tertinggi = setup paling powerful (jarak TP paling jauh)

        Returns list sorted by TF level DESC (H4 > H1 > M30 > M15 > M5):
        [
          {
            "vr_tf":         str  — TF yang sedang VR
            "cmp_tf":        str  — TF atasnya = CMP aktif saat ini
            "direction":     str  — arah CMP (BUY/SELL)
            "vr_dir":        str  — arah VR (berlawanan direction)
            "signal":        str  — WAITING_CF / CF_LOW / CF_HIGH / VR_DEAD
            "entry_tf":      str  — TF entry jika signal sudah siap, else None
            "tp_tf":         str  — TP normal = cmp_tf barrier
            "extended_tp":   str  — TP extended = cmp parent barrier (jika STRONG)
            "sl_tf":         str  — SL = vr_tf barrier
            "setup_strength":str  — STRONG / NORMAL / LIMITED
            "cmp_role":      str  — CF / ALIGNED / PRIMARY / VR (status master di TF atasnya)
            "danger_level":  int  — berapa TF atas yang berlawanan dengan direction
            "vr_dead":       bool — True jika VR sudah diinvalidasi
          }
        ]
        """
        # Pair: TF → parent langsung
        HIERARCHY = ["D1", "H4", "H1", "M30", "M15", "M5"]
        PAIRS = [
            ("H4",  "D1"),   # H4 VR ke D1
            ("H1",  "H4"),   # H1 VR ke H4
            ("M30", "H1"),   # M30 VR ke H1
            ("M15", "M30"),  # M15 VR ke M30
            ("M5",  "M15"),  # M5 VR ke M15
        ]

        # Pair untuk CF entry: VR TF → (cf_low_entry, cf_high_entry)
        CF_ENTRY = {
            "H4":  ("H4",  "H1"),
            "H1":  ("H1",  "M30"),
            "M30": ("M30", "M15"),
            "M15": ("M15", "M5"),
            "M5":  ("M5",  None),
        }

        results = []

        for vr_name, cmp_name in PAIRS:
            vr_st  = self.states[vr_name]
            cmp_st = self.states[cmp_name]

            # Keduanya harus punya CMP (bukan WAIT)
            if vr_st.cmp == "WAIT" or cmp_st.cmp == "WAIT":
                continue

            # VR = TF ini berlawanan dengan parent langsungnya
            if vr_st.cmp == cmp_st.cmp:
                continue   # Bukan VR, sedang aligned

            # Waktu: VR harus terjadi SETELAH CMP parent terbentuk
            if vr_st.cmp_change_time <= cmp_st.cmp_change_time:
                continue

            direction = cmp_st.cmp
            vr_dir    = vr_st.cmp
            opp       = vr_dir   # arah VR = berlawanan direction

            # ── Danger level ─────────────────────────────────────────────
            cmp_idx = HIERARCHY.index(cmp_name)
            danger  = sum(
                1 for anc in HIERARCHY[:cmp_idx]
                if self.states[anc].cmp not in ("WAIT", direction)
            )

            # ── VR invalidation ──────────────────────────────────────────
            # VR TF sudah menyelesaikan CF untuk TF atasnya (parent direction)
            # = VR TF pernah CF (cf_fire_time > cmp_st.cmp_change_time) DAN kembali ke opp
            vr_dead = (
                getattr(vr_st, "cf_fire_time", 0) > cmp_st.cmp_change_time and
                vr_st.cmp == opp    # masih di opp (sudah VR→CF→VR lagi = dikonsumsi parent)
            )

            # ── CF entry TF mapping ──────────────────────────────────────
            cf_low_tf, cf_high_tf = CF_ENTRY[vr_name]
            cf_low_st  = self.states[cf_low_tf]
            cf_high_st = self.states[cf_high_tf] if cf_high_tf else None

            # ── VR invalidation (check sub-chain TF, bukan VR TF sendiri) ──
            # Sub-chain = TF satu level di bawah VR TF (= cf_high_tf)
            # Invalidated jika sub-chain sudah menyelesaikan CF UNTUK parent direction
            # = sub_st.cf_fire_time > vr_st.cmp_change_time AND sub_st.cmp == direction
            #
            # Contoh: M30 VR BUY ke H1 SELL
            #   sub_chain = M15
            #   M15.cf_fire_time > M30.cmp_change_time → M15 sempat CF setelah M30 BUY
            #   M15.cmp == SELL (= H1 direction) → M15 confirm H1 → M30 VR MATI
            vr_dead = False
            if cf_high_tf:
                sub_st = self.states[cf_high_tf]
                vr_dead = (
                    getattr(sub_st, "cf_fire_time", 0) > vr_st.cmp_change_time and
                    sub_st.cmp == direction    # sub-chain sudah kembali ke parent direction
                )

            # ── CF_LOW: VR TF sendiri balik ke direction ──────────────────
            cf_low_ok = (
                not vr_dead and
                cf_low_st.cmp == direction and
                cf_low_st.cmp_change_time > cmp_st.cmp_change_time and
                cf_low_st.cmp_change_time > getattr(cf_low_st, "cf_fail_time", 0)
            )

            # ── CF_HIGH: VR TF masih VR, TF 1 level bawah sudah CF searah ─
            cf_high_ok = False
            if not cf_low_ok and cf_high_st and not vr_dead:
                cf_high_ok = (
                    vr_st.cmp == opp and                         # VR TF masih VR
                    cf_high_st.cmp == direction and
                    cf_high_st.cmp_change_time > vr_st.cmp_change_time and
                    cf_high_st.cmp_change_time > getattr(cf_high_st, "cf_fail_time", 0)
                )

            # ── Determine signal ──────────────────────────────────────────
            if vr_dead:
                signal   = "VR_DEAD"
                entry_tf = None
            elif cf_low_ok:
                signal   = "CF_LOW"
                entry_tf = cf_low_tf
            elif cf_high_ok:
                signal   = "CF_HIGH"
                entry_tf = cf_high_tf
            else:
                signal   = "WAITING_CF"
                entry_tf = None

            # ── Setup strength: status master (cmp_tf) di TF atasnya ───────
            # Ini yang menentukan seberapa jauh price akan jalan
            cmp_parent_name = HIERARCHY[cmp_idx - 1] if cmp_idx > 0 else None
            cmp_parent_st   = self.states.get(cmp_parent_name) if cmp_parent_name else None
            cmp_parent_cmp  = cmp_parent_st.cmp if cmp_parent_st else "WAIT"

            if cmp_parent_cmp == "WAIT" or cmp_idx == 0:
                # Paling atas hierarki — tidak ada parent context
                cmp_role      = "PRIMARY"
                setup_strength = "NORMAL"
                extended_tp   = None

            elif cmp_st.cmp != cmp_parent_cmp:
                # Master TF berlawanan parent = master sendiri adalah VR
                # Setup ini counter-trend → TERBATAS, hati-hati
                cmp_role      = "VR"
                setup_strength = "LIMITED"
                extended_tp   = None

            else:
                # Master TF searah parent — apakah CF (pernah VR lalu balik)?
                vr_t    = getattr(cmp_st, "vr_change_time", 0)
                par_t   = cmp_parent_st.cmp_change_time if cmp_parent_st else 0
                was_cf  = cmp_st.vr_occurred and vr_t > par_t

                if was_cf:
                    # ✓ STRONG: master adalah CF ke parent
                    # VR gagal mengubah parent direction → direction CONFIRMED
                    # Price akan jalan jauh — mungkin sampai parent barrier
                    cmp_role      = "CF"
                    setup_strength = "STRONG"
                    extended_tp   = cmp_parent_name   # Bisa tembus ke parent barrier
                else:
                    # CONTI territory — master langsung ikut parent tanpa siklus VR
                    cmp_role      = "ALIGNED"
                    setup_strength = "NORMAL"
                    extended_tp   = None

            # ── Grade & Reason ────────────────────────────────────────────
            # Grade derivasi dari kekuatan setup + tipe signal
            # Logika: CF setelah failed VR = terkuat (VR satu-satunya cara flip CMP)
            #         VR gagal flip → direction CONFIRMED → market harus lanjut
            grade_map = {
                ("STRONG",  "CF_LOW"):     "A+",
                ("STRONG",  "CF_HIGH"):    "A",
                ("STRONG",  "WAITING_CF"): "A_WATCH",   # Setup kuat, tunggu entry
                ("NORMAL",  "CF_LOW"):     "B+",
                ("NORMAL",  "CF_HIGH"):    "B",
                ("NORMAL",  "WAITING_CF"): "B_WATCH",
                ("LIMITED", "CF_LOW"):     "C+",
                ("LIMITED", "CF_HIGH"):    "C",
                ("LIMITED", "WAITING_CF"): "C_WATCH",
            }
            grade = grade_map.get((setup_strength, signal), "INVALID" if vr_dead else "WAIT")

            # Reason menjelaskan MENGAPA setup ini kuat/lemah
            if vr_dead:
                reason = (
                    f"[VR MATI] {vr_name} sudah CF untuk {cmp_name} — "
                    f"VR ke {cmp_name} sudah habis enerjinya"
                )
            elif setup_strength == "STRONG":
                reason = (
                    f"{cmp_name} {direction} [STRONG] — "
                    f"VR ke {cmp_parent_name} GAGAL flip CMP {cmp_parent_name} "
                    f"→ {cmp_name} CF kembali → direction CONFIRMED "
                    f"→ market HARUS lanjut {direction} | "
                    f"TP normal={cmp_name} barrier | TP extended={extended_tp} barrier"
                )
            elif setup_strength == "LIMITED":
                reason = (
                    f"{cmp_name} {direction} [LIMITED/BAHAYA] — "
                    f"{cmp_name} hanya VR ke {cmp_parent_name}, "
                    f"dibatasi {cmp_parent_name} barrier | "
                    f"Hanya valid selama {cmp_name} CMP belum flip"
                )
            else:
                reason = (
                    f"{cmp_name} {direction} [NORMAL] — "
                    f"Direction valid, tunggu siklus VR→CF selesai"
                )

            results.append({
                "vr_tf":          vr_name,
                "cmp_tf":         cmp_name,
                "direction":      direction,
                "vr_dir":         vr_dir,
                "signal":         signal,
                "entry_tf":       entry_tf,
                "tp_tf":          cmp_name,        # TP normal = CMP master barrier
                "extended_tp":    extended_tp,     # TP extended jika STRONG (master CF ke parent)
                "sl_tf":          vr_name,         # SL = VR TF barrier
                "setup_strength": setup_strength,  # STRONG / NORMAL / LIMITED
                "cmp_role":       cmp_role,        # CF / ALIGNED / PRIMARY / VR
                "grade":          grade,           # A+/A/B+/B/C+/C/INVALID
                "danger_level":   danger,
                "vr_dead":        vr_dead,
                "reason":         reason,
                # VR hanya sekali, CF berkali-kali — tracking berapa kali CF sudah fire
                # pada VR setup ini (untuk dashboard: "CF #2", "CF #3", dst.)
                # Doktrin: setiap TP → pullback → CF baru = entri baru yang valid
                "cf_count":       getattr(vr_st, "cf_count", 0),
            })

        return results

    def get_tf_context(self) -> dict:
        """
        Tampilkan konteks/peran setiap TF dalam hierarki relative ke TF langsung di atasnya.

        Doktrin Universal: setiap TF bisa jadi master untuk setup di TF bawahnya,
        terlepas TF itu sendiri adalah VR atau CF ke TF atasnya.

        Peran (role) TF terhadap parent langsungnya:
          PRIMARY : TF paling atas atau parent belum ada CMP (belum ada referensi)
          ALIGNED : TF searah parent → CMP biasa (bisa jadi CONTI atau CF)
          VR      : TF berlawanan parent → retracement/test (BERBAHAYA tapi valid)
          CF      : TF sudah VR lalu balik searah parent → konfirmasi (aman)

        Penting untuk trading:
          - TF dengan role VR = hati-hati! Jalannya terbatas (sampai parent barrier saja)
          - TF dengan role ALIGNED/CF = lebih aman, jalan lebih jauh
          - TF apapun bisa jadi master untuk setup di bawahnya

        Danger level per TF = berapa TF atas yang berlawanan dengan CMP TF ini.

        Returns dict[tf_name] → {cmp, role, parent, parent_cmp, danger_level,
                                  deploy_ok, tp_reference}
        """
        hierarchy = ["D1", "H4", "H1", "M30", "M15", "M5"]
        result    = {}

        for i, tf_name in enumerate(hierarchy):
            st          = self.states[tf_name]
            parent_name = hierarchy[i - 1] if i > 0 else None
            parent_st   = self.states[parent_name] if parent_name else None

            cmp        = st.cmp
            parent_cmp = parent_st.cmp if parent_st else "WAIT"

            # ── Role terhadap parent langsung ─────────────────────────────
            if cmp == "WAIT":
                role = "WAIT"
            elif parent_name is None or parent_cmp == "WAIT":
                role = "PRIMARY"       # Tidak ada parent CMP, TF ini adalah acuan
            elif cmp != parent_cmp:
                # TF berlawanan parent → VR = retracement, bahaya tapi valid
                role = "VR"
            else:
                # TF searah parent — apakah ada VR dulu (CF) atau langsung CONTI?
                vr_t = getattr(st, "vr_change_time", 0)
                parent_t = parent_st.cmp_change_time if parent_st else 0
                if st.vr_occurred and vr_t > parent_t:
                    role = "CF"        # Sudah VR dulu lalu balik = konfirmasi kuat
                else:
                    role = "ALIGNED"   # Langsung ikut parent = CONTI territory

            # ── Danger level = berapa TF atas yang berlawanan ─────────────
            danger = sum(
                1 for anc in hierarchy[:i]
                if self.states[anc].cmp not in ("WAIT", cmp)
            )

            # ── TP reference = TF parent langsung ────────────────────────
            # Setup di TF ini → TP ke parent barrier
            # Kalau role VR → jarak ke parent LEBIH PENDEK → TP lebih dekat
            tp_reference = parent_name if parent_name else tf_name

            # ── Deploy viable = TF ini punya CMP dan bisa jadi master ────
            deploy_ok = cmp != "WAIT"

            result[tf_name] = {
                "cmp":          cmp,
                "role":         role,          # PRIMARY / VR / CF / ALIGNED / WAIT
                "parent":       parent_name,
                "parent_cmp":   parent_cmp,
                "danger_level": danger,
                "deploy_ok":    deploy_ok,
                "tp_reference": tp_reference,
                "is_counter":   (role == "VR"),  # True = TF ini berlawanan parent (hati-hati)
                "vr_occurred":  st.vr_occurred,
                "cf_fire_time": getattr(st, "cf_fire_time", 0),
            }

        return result

    def get_post_entry_status(self, signal_type: str, direction: str, entry_time: float) -> dict:
        """
        Monitor kondisi setelah entry CF — apakah upper TF sudah konfirmasi?

        Doktrin:
        - CF BERHASIL = upper TF (setup TF) juga breakout SEARAH setelah CF entry
        - CF GAGAL    = entry TF langsung flip berlawanan (cf_fail_time > entry_time)
        - TP SEGERA   = upper TF flip berlawanan ATAU entry TF gagal

        Map TF per signal:
          MINOR_CF   → entry M5,  monitor M15
          CF_LOW     → entry M15, monitor M30
          CF_HIGH    → entry M5,  monitor M15  (M15 harus CF juga)
          H4_CF_HIGH → entry M30, monitor H1

        Contoh penggunaan:
          status = analyst.get_post_entry_status("CF_HIGH", "SELL", entry_ts)
          if status["action"] == "TAKE_PROFIT": executor.close_position(...)
          elif status["action"] == "HOLD": ...  # hold ke TP full

        Returns dict:
          action           : "HOLD" | "TAKE_PROFIT" | "WAIT"
          reason           : str — penjelasan singkat
          confirmed        : bool — upper TF sudah breakout searah
          failed           : bool — CF entry gagal
          entry_tf_status  : str  — status TF entry saat ini
          monitor_tf_status: str  — status TF monitor saat ini
        """
        # Peta signal → (entry_tf, monitor_tf)
        tf_map = {
            "MINOR_CF":   ("M5",  "M15"),
            "CF_LOW":     ("M15", "M30"),
            "CF_HIGH":    ("M5",  "M15"),
            "H4_CF_HIGH": ("M30", "H1"),
        }

        if signal_type not in tf_map:
            return {
                "action":            "WAIT",
                "reason":            f"Unknown signal type: {signal_type}",
                "confirmed":         False,
                "failed":            False,
                "entry_tf_status":   "?",
                "monitor_tf_status": "?",
            }

        entry_tf_name, monitor_tf_name = tf_map[signal_type]
        entry_st   = self.states[entry_tf_name]
        monitor_st = self.states[monitor_tf_name]
        opp        = "SELL" if direction == "BUY" else "BUY"

        # ── 1. CF GAGAL: entry TF flip berlawanan setelah entry ──────────────
        entry_tf_failed = (
            getattr(entry_st, "cf_failed", False) and
            getattr(entry_st, "cf_fail_time", 0) > entry_time
        )

        # ── 2. UPPER TF CONFIRMED: monitor TF breakout searah setelah entry ──
        upper_confirmed = (
            monitor_st.cmp == direction and
            monitor_st.cmp_change_time > entry_time
        )

        # ── 3. UPPER TF COUNTER: monitor TF flip berlawanan setelah entry ────
        upper_failed = (
            monitor_st.cmp == opp and
            monitor_st.cmp_change_time > entry_time
        )

        # ── 4. CMP MASTER MASIH VALID? ────────────────────────────────────────
        # Doktrin: VR adalah satu-satunya cara CMP flip.
        # Selama CMP master belum flip → setup tetap valid.
        # CMP flip = ada VR baru yang BERHASIL (bukan sekedar VR lalu gagal).
        # Ini dideteksi dari: monitor_st.cmp == opp AND waktu flip setelah entry.
        # (upper_failed di atas sudah handle ini — jika upper TF flip = TP segera)

        if entry_tf_failed:
            return {
                "action":            "TAKE_PROFIT",
                "reason":            (f"{entry_tf_name} flip {opp} setelah CF "
                                      f"— CF GAGAL, close posisi segera"),
                "confirmed":         False,
                "failed":            True,
                "entry_tf_status":   f"CF_FAIL ({entry_tf_name}→{opp})",
                "monitor_tf_status": monitor_st.status,
            }

        if upper_confirmed:
            return {
                "action":            "HOLD",
                "reason":            (f"{monitor_tf_name} breakout {direction} searah CF "
                                      f"— SETUP VALID, hold ke TP {monitor_tf_name} barrier"),
                "confirmed":         True,
                "failed":            False,
                "entry_tf_status":   entry_st.status,
                "monitor_tf_status": f"CF ({monitor_tf_name}→{direction})",
            }

        if upper_failed:
            return {
                "action":            "TAKE_PROFIT",
                "reason":            (f"{monitor_tf_name} flip {opp} setelah entry "
                                      f"— {monitor_tf_name} akan retrace untuk VR, TP segera"),
                "confirmed":         False,
                "failed":            True,
                "entry_tf_status":   entry_st.status,
                "monitor_tf_status": f"COUNTER ({monitor_tf_name}→{opp})",
            }

        # Masih menunggu — belum ada sinyal dari upper TF
        return {
            "action":            "WAIT",
            "reason":            (f"Menunggu {monitor_tf_name} breakout {direction} "
                                  f"(konfirmasi CF) — hold sementara"),
            "confirmed":         False,
            "failed":            False,
            "entry_tf_status":   entry_st.status,
            "monitor_tf_status": monitor_st.status,
        }

    # TP Rules baku per doktrin: CF dari TF ini → target SNR di TF atasnya
    TP_MAP = {
        "M5":  "M15",
        "M15": "M30",
        "M30": "H1",
        "H1":  "H4",
        "H4":  "D1",
    }

    def get_scalp_while_waiting(self) -> list:
        """
        Doktrin: VR adalah CMP di TF-nya sendiri.

        Setiap TF yang sedang VR ke parent-nya bisa dijadikan CMP baru untuk scalp
        di arah berlawanan main setup — sambil menunggu setup utama selesai.

        Contoh:
          H4 BUY + H1 VR (SELL) → scalp SELL valid
          Syarat: M30 BELUM VR BUY (M30 masih SELL = CONTI H1 SELL)
          Entry:  M15 SELL → M5 VR BUY → M5 CF SELL
          TP:     SNR M15 (CF M5) atau SNR M30 (CF M15)
          STOP:   M30 VR BUY terjadi → H1 mau CF BUY → stop scalp SELL

        TP Rules baku:
          CF M5  → SNR M15  |  CF M15 → SNR M30  |  CF M30 → SNR H1
          CF H1  → SNR H4   |  CF H4  → SNR Daily

        Returns list sorted by scalp_master_tf level (H1 > M30 > M15):
        [
          {
            "scalp_master_tf" : str   — TF yang VR = CMP scalp
            "parent_tf"       : str   — TF di atas (main setup direction)
            "scalp_dir"       : str   — arah scalp (= arah VR)
            "parent_dir"      : str   — arah main setup (nanti mau ke sini)
            "status"          : str   — "SCALP_VALID" | "STOP_SCALP"
            "guard_tf"        : str   — TF penjaga (1 level bawah scalp master)
            "guard_condition" : str   — kondisi yang harus terpenuhi (BELUM VR)
            "signal"          : str   — "CF_LOW" | "CF_HIGH" | "WAITING_CF" | None
            "entry_tf"        : str   — TF entry jika signal siap, else None
            "tp_tf"           : str   — TP target per TP_MAP
            "sl_tf"           : str   — SL reference TF
            "danger_level"    : int   — berapa TF atas yang counter scalp_dir
            "reason"          : str   — narasi singkat
          }
        ]
        """
        HIERARCHY = ["D1", "H4", "H1", "M30", "M15", "M5"]

        # Pasangan: (scalp_master, parent) — TF yang bisa jadi CMP scalp
        VR_PAIRS = [
            ("H1",  "H4"),
            ("M30", "H1"),
            ("M15", "M30"),
        ]

        results = []

        for scalp_master_tf, parent_tf in VR_PAIRS:
            scalp_st  = self.states[scalp_master_tf]
            parent_st = self.states[parent_tf]

            if scalp_st.cmp == "WAIT" or parent_st.cmp == "WAIT":
                continue

            # Harus VR: scalp_master berlawanan parent
            if scalp_st.cmp == parent_st.cmp:
                continue

            # Time Law: VR harus terjadi SETELAH parent CMP terbentuk
            if scalp_st.cmp_change_time <= parent_st.cmp_change_time:
                continue

            scalp_dir  = scalp_st.cmp   # arah scalp (= arah VR TF)
            parent_dir = parent_st.cmp  # arah main setup yang sedang ditunggu

            scalp_idx = HIERARCHY.index(scalp_master_tf)

            # Guard TF (1 level bawah scalp master)
            # Kunci: guard BELUM VR ke parent_dir = scalp masih valid
            # Jika guard SUDAH VR ke parent_dir → scalp master mau CF parent_dir → STOP
            if scalp_idx + 1 >= len(HIERARCHY):
                continue
            guard_tf = HIERARCHY[scalp_idx + 1]
            guard_st = self.states[guard_tf]

            guard_vr_to_parent = (
                guard_st.cmp == parent_dir and
                guard_st.cmp != "WAIT" and
                guard_st.cmp_change_time > scalp_st.cmp_change_time
            )

            if guard_vr_to_parent:
                results.append({
                    "scalp_master_tf": scalp_master_tf,
                    "parent_tf":       parent_tf,
                    "scalp_dir":       scalp_dir,
                    "parent_dir":      parent_dir,
                    "status":          "STOP_SCALP",
                    "guard_tf":        guard_tf,
                    "guard_condition": f"{guard_tf} sudah VR {parent_dir}",
                    "signal":          None,
                    "entry_tf":        None,
                    "tp_tf":           None,
                    "sl_tf":           None,
                    "danger_level":    0,
                    "reason": (
                        f"[STOP SCALP] {guard_tf} sudah VR {parent_dir} ke {scalp_master_tf} "
                        f"→ {scalp_master_tf} mau CF {parent_dir} "
                        f"→ Jangan scalp {scalp_dir} lagi | Tunggu CF {parent_dir} di {scalp_master_tf}"
                    ),
                })
                continue

            # Sub TF (2 level bawah scalp master) — untuk CF_HIGH
            sub_tf = HIERARCHY[scalp_idx + 2] if scalp_idx + 2 < len(HIERARCHY) else None
            sub_st = self.states[sub_tf] if sub_tf else None

            # ── CF_LOW: guard_tf sudah VR (parent_dir) lalu balik ke scalp_dir ──
            cf_low_ok = (
                guard_st.cmp == scalp_dir and
                guard_st.vr_occurred and
                guard_st.cmp_change_time > getattr(guard_st, "vr_change_time", 0) and
                guard_st.cmp_change_time > scalp_st.cmp_change_time and
                guard_st.cmp_change_time > getattr(guard_st, "cf_fail_time", 0)
            )

            # ── CF_HIGH: guard_tf masih VR (parent_dir), sub_tf CF scalp_dir ──
            cf_high_ok = False
            if sub_st and not cf_low_ok:
                guard_is_vr = (
                    guard_st.cmp == parent_dir and
                    guard_st.cmp_change_time > scalp_st.cmp_change_time
                )
                if guard_is_vr:
                    cf_high_ok = (
                        sub_st.cmp == scalp_dir and
                        sub_st.cmp_change_time > guard_st.cmp_change_time and
                        sub_st.cmp_change_time > getattr(sub_st, "cf_fail_time", 0)
                    )

            if cf_low_ok:
                signal   = "CF_LOW"
                entry_tf = guard_tf
                tp_tf    = self.TP_MAP.get(guard_tf)
                sl_tf    = sub_tf if sub_tf else guard_tf
            elif cf_high_ok:
                signal   = "CF_HIGH"
                entry_tf = sub_tf
                tp_tf    = self.TP_MAP.get(sub_tf)
                sl_tf    = sub_tf
            else:
                signal   = "WAITING_CF"
                entry_tf = None
                tp_tf    = self.TP_MAP.get(guard_tf)   # TP target jika signal terjadi
                sl_tf    = None

            # Danger: berapa TF di atas scalp_master yang counter scalp_dir
            danger = sum(
                1 for anc in HIERARCHY[:scalp_idx]
                if self.states[anc].cmp not in ("WAIT", scalp_dir)
            )

            entry_hint = (
                f"Entry {scalp_dir} di {entry_tf} | TP: {tp_tf} SNR | SL: {sl_tf} SNR"
                if signal != "WAITING_CF" else
                f"Tunggu CF {scalp_dir} di {guard_tf}"
                + (f" atau {sub_tf}" if sub_tf else "")
            )

            results.append({
                "scalp_master_tf": scalp_master_tf,
                "parent_tf":       parent_tf,
                "scalp_dir":       scalp_dir,
                "parent_dir":      parent_dir,
                "status":          "SCALP_VALID",
                "guard_tf":        guard_tf,
                "guard_condition": f"{guard_tf} BELUM VR {parent_dir}",
                "signal":          signal,
                "entry_tf":        entry_tf,
                "tp_tf":           tp_tf,
                "sl_tf":           sl_tf,
                "danger_level":    danger,
                "reason": (
                    f"{parent_tf} {parent_dir} | {scalp_master_tf} VR ({scalp_dir}) = CMP scalp | "
                    f"{entry_hint}"
                ),
            })

        return results

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


class FundamentalSNR:
    """
    Level-level fundamental penting: PDH/PDL, PWH/PWL, Daily Open, Round Numbers.
    Digunakan sebagai:
      1. BLOCK entry jika terlalu dekat (< snr_block_usd)
      2. WARNING di dashboard jika dalam range (< snr_warn_usd)

    Refresh otomatis tiap 5 menit — hemat MT5 API call.
    """
    ROUND_STEP = 50.0   # XAUUSD: round number setiap 50 USD (3300, 3350, dll)

    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol      = symbol
        self.pdh:   float = 0.0   # Previous Day High
        self.pdl:   float = 0.0   # Previous Day Low
        self.pwh:   float = 0.0   # Previous Week High
        self.pwl:   float = 0.0   # Previous Week Low
        self.daily_open: float = 0.0
        self._last_update:    float = 0.0
        self._UPDATE_INTERVAL: float = 300.0   # refresh tiap 5 menit

    def update(self):
        """Fetch PDH/PDL/PWH/PWL dari MT5. Rate-limited 5 menit."""
        now = time.time()
        if now - self._last_update < self._UPDATE_INTERVAL:
            return
        self._last_update = now

        # D1: ambil kemarin (index -2) dan hari ini (index -1)
        d1 = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_D1, 0, 3)
        if d1 is not None and len(d1) >= 2:
            self.daily_open = float(d1[-1]["open"])
            self.pdh        = float(d1[-2]["high"])
            self.pdl        = float(d1[-2]["low"])

        # W1: ambil minggu lalu (index -2)
        w1 = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_W1, 0, 3)
        if w1 is not None and len(w1) >= 2:
            self.pwh = float(w1[-2]["high"])
            self.pwl = float(w1[-2]["low"])

    def nearest_round(self, price: float) -> float:
        """Round number XAUUSD terdekat (setiap 50 USD)."""
        return round(price / self.ROUND_STEP) * self.ROUND_STEP

    def check_proximity(self, price: float, threshold_usd: float = 5.0) -> list:
        """
        Cek kedekatan price ke semua level fundamental.
        Returns list of dict sorted by jarak terdekat.
        """
        rn = self.nearest_round(price)
        levels = [
            ("PDH",        self.pdh),
            ("PDL",        self.pdl),
            ("PWH",        self.pwh),
            ("PWL",        self.pwl),
            ("DAILY.OPEN", self.daily_open),
            (f"RN.{rn:.0f}", rn),
        ]
        results = []
        for name, lv in levels:
            if lv <= 0:
                continue
            dist = abs(price - lv)
            results.append({
                "name":    name,
                "price":   lv,
                "dist":    round(dist, 2),
                "is_near": dist <= threshold_usd,
                "above":   price > lv,   # True = price di atas level
            })
        return sorted(results, key=lambda x: x["dist"])

    def get_nearest_warning(self, price: float,
                            block_usd: float = 2.0,
                            warn_usd:  float = 5.0) -> tuple:
        """
        Returns (blocked, warned, message) untuk executor guard.
          blocked = True → jangan entry (terlalu dekat)
          warned  = True → entry boleh tapi tampilkan warning
        """
        hits = self.check_proximity(price, warn_usd)
        if not hits:
            return False, False, "Fundamental SNR: OK"

        nearest = hits[0]
        dist    = nearest["dist"]
        pos     = "atas" if nearest["above"] else "bawah"
        msg     = (f"SNR {nearest['name']} {nearest['price']:.2f} "
                   f"({dist:.2f}$ di {pos})")

        if dist <= block_usd:
            return True, True, f"BLOCK: {msg}"
        return False, True, f"WARN: {msg}"

    def get_levels_display(self, price: float) -> dict:
        """Untuk dashboard — semua level + proximity dalam range 10 USD."""
        return {
            "pdh":        self.pdh,
            "pdl":        self.pdl,
            "pwh":        self.pwh,
            "pwl":        self.pwl,
            "daily_open": self.daily_open,
            "round":      self.nearest_round(price),
            "proximity":  self.check_proximity(price, 10.0),
        }


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
    (Seminar Daily Deploy PDF)

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

    # Hierarki TF — urutan dari terbesar ke terkecil
    TF_HIERARCHY = ["D1", "H4", "H1", "M30", "M15", "M5"]

    LAYERS = [
        # name          dir_tf  vr_tf  cf_low_tf  cf_high_tf  danger_label
        {"name": "D1_DEPLOY",  "dir_tf": "D1",  "vr_tf": "H4",  "cf_low_tf": "H4",  "cf_high_tf": "H1"},
        {"name": "H4_DEPLOY",  "dir_tf": "H4",  "vr_tf": "H1",  "cf_low_tf": "H1",  "cf_high_tf": "M30"},
        {"name": "H1_DEPLOY",  "dir_tf": "H1",  "vr_tf": "M30", "cf_low_tf": "M30", "cf_high_tf": "M15"},
        # M30 sebagai master — DANGEROUS karena M30 biasanya VR ke H1
        # Syarat tambahan: cek VR invalidation (M15 sudah bermain untuk H1 direction)
        {"name": "M30_DEPLOY", "dir_tf": "M30", "vr_tf": "M15", "cf_low_tf": "M15", "cf_high_tf": "M5"},
    ]

    @staticmethod
    def _danger_level(dir_tf: str, direction: str, states: dict) -> int:
        """
        Hitung danger level = berapa TF di atas dir_tf yang berlawanan dengan direction.

        0 = semua TF atas searah (setup paling aman)
        1 = 1 TF atas berlawanan (dir_tf adalah VR ke 1 level)
        2+ = 2+ TF atas berlawanan (sangat counter-trend, hati-hati)

        Contoh:
          M30 BUY, H1 SELL, H4 BUY → danger = 1 (hanya H1 berlawanan)
          M30 BUY, H1 SELL, H4 SELL → danger = 2 (H1 + H4 berlawanan)
        """
        hierarchy = DailyDeployAnalyst.TF_HIERARCHY
        if dir_tf not in hierarchy:
            return 0
        idx = hierarchy.index(dir_tf)
        count = 0
        for anc in hierarchy[:idx]:
            anc_cmp = states[anc].cmp if anc in states else "WAIT"
            if anc_cmp not in ("WAIT", direction):
                count += 1
        return count

    @staticmethod
    def _vr_invalidated(vr_st, dir_st_cmp_change_time: float, direction: str) -> bool:
        """
        Deteksi apakah VR sudah MATI — sub-chain sudah bermain UNTUK arah parent,
        bukan untuk VR master kita.

        Kondisi invalidasi:
          VR TF (mis. M15 dalam M30_DEPLOY) sebelumnya fire CF (cf_fire_time tercatat)
          SETELAH direction TF terbentuk, DAN sekarang kembali ke arah berlawanan direction.

        Artinya: VR TF sudah menyelesaikan siklus VR→CF untuk TF ATAS kita (parent direction),
        bukan untuk kita. M30 VR sudah habis enerjinya.

        Contoh M30_DEPLOY BUY:
          M30 BUY → M15 VR SELL (test M30) → M15 BUY (CF to M30) → M15 SELL lagi (CF for H1!)
          M15.cf_fire_time > M30.cmp_change_time + M15.cmp == SELL = M30 BUY adalah MATI
        """
        opp = "SELL" if direction == "BUY" else "BUY"
        return (
            getattr(vr_st, "cf_fire_time", 0) > dir_st_cmp_change_time and
            vr_st.cmp == opp   # VR TF sudah kembali ke arah berlawanan direction setelah CF
        )

    def __init__(self, symbol):
        self.symbol = symbol
        self.current_price = 0.0
        self.active_signals = []
        self.layer_states = {
            l["name"]: {
                "direction":   "WAIT",
                "vr_occurred": False,
                "vr_time":     0,
            }
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
            cfh_st  = analyst.states.get(layer.get("cf_high_tf"))
            direction = dir_st.cmp

            # Reset layer on direction flip or WAIT
            if direction == "WAIT" or direction != state["direction"]:
                state["direction"]   = direction
                state["vr_occurred"] = False
                state["vr_time"]     = 0
                if direction == "WAIT":
                    continue

            # ── Danger level & VR invalidation ───────────────────────────────
            danger   = self._danger_level(layer["dir_tf"], direction, analyst.states)
            vr_dead  = self._vr_invalidated(vr_st, dir_st.cmp_change_time, direction)

            # ── VR Detection ──────────────────────────────────────────────────
            # VR = vr_tf broke COUNTER to direction, AFTER direction_tf breakout
            vr_counter = vr_st.cmp != direction and vr_st.cmp != "WAIT"
            vr_after   = vr_st.cmp_change_time > dir_st.cmp_change_time

            if vr_counter and vr_after and not state["vr_occurred"]:
                state["vr_occurred"] = True
                state["vr_time"]     = vr_st.cmp_change_time

            if not state["vr_occurred"]:
                # ── CONTI (Pre-VR) ────────────────────────────────────────────
                # Trade every BO at vr_tf that aligns with direction,
                # while waiting for the VR to occur.
                # Jika vr_dead = True: abaikan CONTI juga (sub-chain sudah mati)
                if (not vr_dead and
                        vr_st.cmp == direction and
                        vr_st.cmp_change_time > dir_st.cmp_change_time):
                    self.active_signals.append({
                        "layer":        name,
                        "action":       direction,
                        "type":         "CONTI",
                        "risk":         "MEDIUM",
                        "danger_level": danger,
                        "vr_dead":      False,
                        "cf_count":     0,   # Pre-VR, belum ada CF
                        "dir_tf":       layer["dir_tf"],
                        "entry_tf":     layer["vr_tf"],
                        "reason":       (
                            f"CONTI {layer['dir_tf']}→{layer['vr_tf']}"
                            f" (pre-VR, {direction}"
                            f"{' | COUNTER x'+str(danger) if danger > 0 else ''})"
                        ),
                    })
            else:
                # VR sudah terjadi — cek CF_LOW dan CF_HIGH
                # Jika VR sudah mati (sub-chain bermain untuk H1/H4 direction), skip
                if vr_dead:
                    # Tetap tambahkan sebagai sinyal tapi dengan flag vr_dead=True
                    # agar dashboard bisa menampilkan "VR MATI — jangan entry"
                    self.active_signals.append({
                        "layer":        name,
                        "action":       direction,
                        "type":         "VR_DEAD",
                        "risk":         "INVALID",
                        "danger_level": danger,
                        "vr_dead":      True,
                        "cf_count":     getattr(vr_st, "cf_count", 0),  # berapa kali CF sempat fire sebelum VR mati
                        "dir_tf":       layer["dir_tf"],
                        "entry_tf":     layer["vr_tf"],
                        "reason":       (
                            f"[VR MATI] {layer['dir_tf']} {direction} | "
                            f"{layer['vr_tf']} sudah CF ke arah atas — "
                            f"setup {name} tidak valid lagi"
                        ),
                    })
                    continue

                # ── CF Low Risk ───────────────────────────────────────────────
                # cf_low_tf (same TF as vr_tf) returns to direction AFTER vr_time
                # Fresh CF guard: cf_fail_time < cmp_change_time
                cf_low_ok = (
                    cfl_st.cmp == direction and
                    cfl_st.cmp_change_time > state["vr_time"] and
                    cfl_st.cmp_change_time > getattr(cfl_st, "cf_fail_time", 0)
                )
                if cf_low_ok:
                    self.active_signals.append({
                        "layer":        name,
                        "action":       direction,
                        "type":         "CF_LOW",
                        "risk":         "LOW" if danger == 0 else "HIGH",
                        "danger_level": danger,
                        "vr_dead":      False,
                        # berapa kali CF sudah fire pada VR setup ini
                        # CF #1 = pertama kali, CF #2 = re-entry setelah pullback, dst.
                        "cf_count":     getattr(cfl_st, "cf_count", 0),
                        "dir_tf":       layer["dir_tf"],
                        "entry_tf":     layer["cf_low_tf"],
                        "reason":       (
                            f"CF Low {layer['dir_tf']}→{layer['vr_tf']}→{layer['cf_low_tf']}"
                            + (f" | COUNTER-TREND x{danger} ⚠" if danger > 0 else "")
                        ),
                    })

                # ── CF High Risk ──────────────────────────────────────────────
                # One TF below VR aligns with direction AFTER vr_time.
                # Only fires when CF_LOW has NOT yet fired (hierarchy).
                elif cfh_st and not cf_low_ok:
                    cf_high_ok = (
                        cfh_st.cmp == direction and
                        cfh_st.cmp_change_time > state["vr_time"] and
                        cfh_st.cmp_change_time > getattr(cfh_st, "cf_fail_time", 0)
                    )
                    if cf_high_ok:
                        self.active_signals.append({
                            "layer":        name,
                            "action":       direction,
                            "type":         "CF_HIGH",
                            "risk":         "HIGH",
                            "danger_level": danger,
                            "vr_dead":      False,
                            # CF HIGH: entry TF = cf_high_tf (1 level di bawah VR TF)
                            # cf_count dari cfh_st — berapa kali sub-TF ini fire CF
                            "cf_count":     getattr(cfh_st, "cf_count", 0),
                            "dir_tf":       layer["dir_tf"],
                            "entry_tf":     layer.get("cf_high_tf", layer["vr_tf"]),
                            "reason":       (
                                f"CF High {layer['dir_tf']}→{layer['vr_tf']}→{layer.get('cf_high_tf','?')}"
                                + (f" | COUNTER-TREND x{danger} ⚠" if danger > 0 else "")
                            ),
                        })

    def get_best_signal(self):
        """
        Return highest-priority active signal.

        Prioritas:
          1. Exclude VR_DEAD / INVALID — tidak boleh entry
          2. Prefer danger_level rendah (aligned > counter-trend)
          3. Prefer signal type: CF_LOW > CF_HIGH > CONTI
          4. Prefer layer atas: D1_DEPLOY > H4_DEPLOY > H1_DEPLOY > M30_DEPLOY
        """
        valid = [s for s in self.active_signals if s.get("risk") != "INVALID" and not s.get("vr_dead")]
        if not valid:
            return None
        type_pri  = {"CF_LOW": 0, "CF_HIGH": 1, "CONTI": 2}
        layer_pri = {"D1_DEPLOY": 0, "H4_DEPLOY": 1, "H1_DEPLOY": 2, "M30_DEPLOY": 3}
        return sorted(
            valid,
            key=lambda s: (
                s.get("danger_level", 0),
                type_pri.get(s["type"], 99),
                layer_pri.get(s["layer"], 99),
            )
        )[0]

    def get_layer_summary(self):
        """Returns list of per-layer status strings for UI rendering."""
        lines = []
        for layer in self.LAYERS:
            name  = layer["name"]
            state = self.layer_states[name]
            label = name.replace("_DEPLOY", "")
            direction = state["direction"]
            col   = "green" if direction == "BUY" else "red" if direction == "SELL" else "dim white"

            if state["vr_occurred"]:
                phase = "VR ok → waiting CF"
            else:
                phase = "pre-VR (CONTI)"

            # Cari signal aktif untuk layer ini
            layer_sigs = [s for s in self.active_signals if s.get("layer") == name]
            best = None
            for s in layer_sigs:
                if s["type"] in ("CF_LOW", "CF_HIGH"):
                    best = s; break
            if best is None:
                for s in layer_sigs:
                    if s["type"] == "CONTI":
                        best = s; break

            signal_str = ""
            if best:
                if best.get("vr_dead"):
                    signal_str = " [bold red][VR MATI][/]"
                else:
                    dl = best.get("danger_level", 0)
                    risk_col  = "red" if dl > 1 else "yellow" if dl == 1 else "green"
                    counter   = f" [bold {risk_col}]x{dl} COUNTER[/]" if dl > 0 else ""
                    # Tampilkan nomor CF entry — CF #1 = pertama, CF #2 = re-entry dst.
                    cf_n      = best.get("cf_count", 0)
                    cf_label  = f" [dim white]#{cf_n}[/]" if cf_n > 0 else ""
                    signal_str = f" [{risk_col}]{best['type']}[/]{cf_label}{counter}"

            lines.append(
                f"[bold {col}]{label}[/] [{col}]{direction}[/] | [dim]{phase}[/]{signal_str}"
            )
        return lines

