"""
Standalone Thread-Safe DD v6.2 Overlay Dashboard Application
Location: bookmap-bridge/cr_dashboard_app.py
Author: DADANG WAHYUONO - Chain Reaction System

Reads live_status.json every 200ms and updates UI in real-time.
Runs in its own Python process to prevent any Bookmap freeze or GUI thread locks.
"""

import tkinter as tk
import json
import os
import time

STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_status.json")

# ── Palette ──────────────────────────────────────────────────────────────
BG_ROOT = "#0b0e14"
BG_PANEL = "#12161f"
BG_PANEL_ALT = "#161b26"
BORDER = "#2a3141"
GOLD = "#E8B94A"
GOLD_DIM = "#8a7133"
CYAN = "#5FD3E8"
GREEN = "#22C55E"
RED = "#EF4444"
TEXT = "#E5E7EB"
TEXT_DIM = "#8B92A0"
YELLOW = "#F5C542"

FONT_HEAD = ("Segoe UI Semibold", 10)
FONT_UI = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI Semibold", 9)
FONT_MONO = ("Cascadia Mono", 9)
FONT_MONO_SM = ("Cascadia Mono", 8)


class CRDashboardApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Chain Reaction — Decision Recommendation Engine")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.root.configure(bg=BG_ROOT)
        self.root.geometry("580x560+20+60")
        self.root.minsize(520, 480)

        self._last_data_wall_time = None
        self._heartbeat_on = True
        self._live_line = ""

        self._build_header()
        self._build_badge()
        self._build_table()
        self._build_wall_panel()
        self._build_reason_panel()
        self._build_live_bar()

        self.root.after(200, self._poll_status)
        self.root.after(1000, self._tick_heartbeat)

    # ── Layout builders ──────────────────────────────────────────────────
    def _card(self, parent, **pack_kw):
        f = tk.Frame(parent, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        f.pack(**pack_kw)
        return f

    def _build_header(self):
        header = tk.Frame(self.root, bg=BG_ROOT)
        header.pack(fill="x", padx=10, pady=(10, 6))

        left = tk.Frame(header, bg=BG_ROOT)
        left.pack(side="left")
        tk.Label(left, text="CHAIN REACTION", font=("Segoe UI Semibold", 12), fg=GOLD, bg=BG_ROOT).pack(anchor="w")
        tk.Label(left, text="Decision Recommendation Engine · Dadang Wahyuono",
                 font=("Segoe UI", 8), fg=TEXT_DIM, bg=BG_ROOT).pack(anchor="w")

        right = tk.Frame(header, bg=BG_ROOT)
        right.pack(side="right")
        self.lbl_symbol = tk.Label(right, text="—", font=("Segoe UI Semibold", 9), fg=TEXT_DIM, bg=BG_ROOT)
        self.lbl_symbol.pack(anchor="e")
        self.lbl_price_hdr = tk.Label(right, text="0.00", font=("Segoe UI Semibold", 16), fg=TEXT, bg=BG_ROOT)
        self.lbl_price_hdr.pack(anchor="e")

    def _build_badge(self):
        outer = tk.Frame(self.root, bg=BG_ROOT)
        outer.pack(fill="x", padx=10, pady=4)
        self.badge_frame = tk.Frame(outer, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        self.badge_frame.pack(fill="x")
        self.lbl_badge = tk.Label(
            self.badge_frame, text="WAIT", font=("Segoe UI Semibold", 20),
            fg=YELLOW, bg=BG_PANEL, pady=10
        )
        self.lbl_badge.pack()

    def _build_table(self):
        outer = tk.Frame(self.root, bg=BG_ROOT)
        outer.pack(fill="x", padx=10, pady=4)
        card = tk.Frame(outer, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x")

        self.table_frame = tk.Frame(card, bg=BG_PANEL)
        self.table_frame.pack(fill="x", padx=6, pady=6)

        headers = ["TF", "CMP", "VR", "CF", "ACTION"]
        weights = [1, 1, 2, 2, 4]
        for c, w in enumerate(weights):
            self.table_frame.grid_columnconfigure(c, weight=w)

        for col_idx, text in enumerate(headers):
            lbl = tk.Label(
                self.table_frame, text=text, font=("Segoe UI Semibold", 8),
                fg=TEXT_DIM, bg=BG_PANEL, anchor="w" if col_idx == 4 else "center", pady=3
            )
            lbl.grid(row=0, column=col_idx, sticky="ew", padx=4)

        sep = tk.Frame(card, bg=BORDER, height=1)
        sep.pack(fill="x")

        self.table_frame2 = tk.Frame(card, bg=BG_PANEL)
        self.table_frame2.pack(fill="x", padx=6, pady=(2, 6))
        for c, w in enumerate(weights):
            self.table_frame2.grid_columnconfigure(c, weight=w)

        self.row_labels = {}
        rows_info = ["D", "H4", "H1", "M30", "M15", "M5", "M1"]

        for row_idx, tf_key in enumerate(rows_info):
            row_bg = BG_PANEL if row_idx % 2 == 0 else BG_PANEL_ALT

            lbl_tf = tk.Label(self.table_frame2, text=tf_key, font=FONT_MONO_SM, fg=TEXT,
                               bg=row_bg, anchor="center", pady=3)
            lbl_tf.grid(row=row_idx, column=0, sticky="ew", padx=1, pady=1)

            lbl_cmp = tk.Label(self.table_frame2, text="WAIT", font=("Segoe UI Semibold", 8), fg="#ffffff",
                                bg="#3a3f4b", anchor="center", pady=3)
            lbl_cmp.grid(row=row_idx, column=1, sticky="ew", padx=1, pady=1)

            lbl_vr = tk.Label(self.table_frame2, text="–", font=FONT_MONO_SM, fg=GOLD_DIM,
                               bg=row_bg, anchor="center")
            lbl_vr.grid(row=row_idx, column=2, sticky="ew", padx=1, pady=1)

            lbl_cf = tk.Label(self.table_frame2, text="–", font=FONT_MONO_SM, fg=GREEN,
                               bg=row_bg, anchor="center")
            lbl_cf.grid(row=row_idx, column=3, sticky="ew", padx=1, pady=1)

            lbl_act = tk.Label(self.table_frame2, text="MONITOR", font=FONT_MONO_SM, fg=TEXT_DIM,
                                bg=row_bg, anchor="w", padx=6)
            lbl_act.grid(row=row_idx, column=4, sticky="ew", padx=1, pady=1)

            self.row_labels[tf_key] = (lbl_cmp, lbl_vr, lbl_cf, lbl_act, row_bg)

    def _build_wall_panel(self):
        outer = tk.Frame(self.root, bg=BG_ROOT)
        outer.pack(fill="x", padx=10, pady=4)
        card = tk.Frame(outer, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x")

        tk.Label(card, text="WALL AREA · nearest to price", font=("Segoe UI Semibold", 8),
                 fg=CYAN, bg=BG_PANEL, anchor="w").pack(fill="x", padx=10, pady=(8, 4))

        row = tk.Frame(card, bg=BG_PANEL)
        row.pack(fill="x", padx=10, pady=(0, 6))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        res_col = tk.Frame(row, bg=BG_PANEL)
        res_col.grid(row=0, column=0, sticky="nw", padx=(0, 6))
        tk.Label(res_col, text="RESISTANCE (ask)", font=("Segoe UI", 7), fg=TEXT_DIM,
                 bg=BG_PANEL, anchor="w").pack(fill="x")
        self.ask_wall_labels = []
        for _ in range(3):
            lbl = tk.Label(res_col, text="—", font=FONT_MONO_SM, fg=TEXT_DIM, bg=BG_PANEL, anchor="w")
            lbl.pack(fill="x", pady=1)
            self.ask_wall_labels.append(lbl)

        sup_col = tk.Frame(row, bg=BG_PANEL)
        sup_col.grid(row=0, column=1, sticky="ne", padx=(6, 0))
        tk.Label(sup_col, text="SUPPORT (bid)", font=("Segoe UI", 7), fg=TEXT_DIM,
                 bg=BG_PANEL, anchor="e").pack(fill="x")
        self.bid_wall_labels = []
        for _ in range(3):
            lbl = tk.Label(sup_col, text="—", font=FONT_MONO_SM, fg=TEXT_DIM, bg=BG_PANEL, anchor="e")
            lbl.pack(fill="x", pady=1)
            self.bid_wall_labels.append(lbl)

        self.lbl_wall_note = tk.Label(card, text="", font=("Segoe UI", 7), fg=GOLD_DIM,
                                       bg=BG_PANEL, anchor="w")
        self.lbl_wall_note.pack(fill="x", padx=10, pady=(0, 8))

    def _build_reason_panel(self):
        outer = tk.Frame(self.root, bg=BG_ROOT)
        outer.pack(fill="both", expand=True, padx=10, pady=4)
        self.reason_frame = tk.Frame(outer, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        self.reason_frame.pack(fill="both", expand=True)

        tk.Label(self.reason_frame, text="ALASAN & KESIMPULAN", font=("Segoe UI Semibold", 8),
                 fg=CYAN, bg=BG_PANEL, anchor="w").pack(fill="x", padx=10, pady=(8, 2))

        self.lbl_reasons = tk.Label(
            self.reason_frame, text="Loading real-time market data...", font=FONT_MONO_SM,
            fg=TEXT, bg=BG_PANEL, justify="left", anchor="w", wraplength=540
        )
        self.lbl_reasons.pack(fill="x", padx=12)

        sep = tk.Frame(self.reason_frame, bg=BORDER, height=1)
        sep.pack(fill="x", padx=10, pady=6)

        self.lbl_conclusion = tk.Label(
            self.reason_frame, text="", font=("Segoe UI Semibold", 8),
            fg=GOLD, bg=BG_PANEL, justify="left", anchor="w", wraplength=540
        )
        self.lbl_conclusion.pack(fill="x", padx=12)

        self.lbl_wall = tk.Label(
            self.reason_frame, text="", font=FONT_MONO_SM,
            fg=TEXT_DIM, bg=BG_PANEL, justify="left", anchor="w", wraplength=540
        )
        self.lbl_wall.pack(fill="x", padx=12, pady=(6, 10))

    def _build_live_bar(self):
        self.live_frame = tk.Frame(self.root, bg=BG_PANEL_ALT, highlightbackground=BORDER, highlightthickness=1)
        self.live_frame.pack(fill="x", padx=10, pady=(4, 10))

        inner = tk.Frame(self.live_frame, bg=BG_PANEL_ALT)
        inner.pack(fill="x", padx=8, pady=5)

        self.lbl_heartbeat = tk.Label(inner, text="●", font=("Segoe UI", 9), fg=GREEN, bg=BG_PANEL_ALT)
        self.lbl_heartbeat.pack(side="left", padx=(0, 6))
        self.lbl_live = tk.Label(inner, text="waiting for data...", font=FONT_MONO_SM,
                                  fg=TEXT_DIM, bg=BG_PANEL_ALT, anchor="w")
        self.lbl_live.pack(side="left", fill="x", expand=True)

    # ── Data polling ─────────────────────────────────────────────────────
    def _poll_status(self):
        try:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._update_ui(data)
        except Exception:
            pass
        finally:
            self.root.after(200, self._poll_status)

    def _update_ui(self, data: dict):
        # Badge
        badge_text = data.get("status_badge", "WAIT").replace("🟡", "").replace("🟢", "").replace("🔴", "").strip()
        rec = data.get("recommendation", "WAIT")
        badge_color = GREEN if rec == "BUY" else (RED if rec == "SELL" else YELLOW)
        self.lbl_badge.config(text=badge_text or "WAIT", fg=badge_color)
        self.badge_frame.config(highlightbackground=badge_color, highlightthickness=2)

        # Header price
        price = data.get("current_price", 0.0)
        self.lbl_price_hdr.config(text=f"{price:,.2f}")
        self.lbl_symbol.config(text="GCZ6 · COMEX GOLD")

        # Matrix
        tf_matrix = data.get("tf_matrix", {})
        for tf_key, labels in self.row_labels.items():
            if tf_key in tf_matrix:
                info = tf_matrix[tf_key]
                lbl_cmp, lbl_vr, lbl_cf, lbl_act, row_bg = labels
                cmp_val = info.get("cmp", "WAIT")
                cmp_bg = GREEN if cmp_val == "BUY" else (RED if cmp_val == "SELL" else "#3a3f4b")
                lbl_cmp.config(text=cmp_val, bg=cmp_bg)
                lbl_vr.config(text=info.get("vr", "–") or "–")
                lbl_cf.config(text=info.get("cf", "–") or "–")
                lbl_act.config(text=info.get("action", "MONITOR"))

        # Reasons & Conclusion
        reasons = data.get("reason_lines", [])
        clean_reasons = [r.replace("✔ ", "").replace("⏳ ", "").replace("⚡ ", "")
                          .replace("📈 ", "").replace("👁 ", "").replace("⚠ ", "! ") for r in reasons]
        self.lbl_reasons.config(text="\n".join(clean_reasons))

        conclusion = data.get("conclusion", "")
        self.lbl_conclusion.config(text=f"Kesimpulan: {conclusion}")

        target_adv = data.get("target_advice", "Normal TP")
        sizing_adv = data.get("sizing_advice", "Full Position Size")
        self.lbl_wall.config(text=f"Target: {target_adv}  |  Position: {sizing_adv}")

        # Wall Area panel — asks (resistance) / bids (support) ladder
        wall_ladder = data.get("wall_ladder", {})
        asks = wall_ladder.get("asks", [])
        bids = wall_ladder.get("bids", [])
        for i, lbl in enumerate(self.ask_wall_labels):
            if i < len(asks):
                p, s = asks[i]
                lbl.config(text=f"{p:,.2f}   {s:,.0f}ct", fg=(RED if i == 0 else TEXT))
            else:
                lbl.config(text="—", fg=TEXT_DIM)
        for i, lbl in enumerate(self.bid_wall_labels):
            if i < len(bids):
                p, s = bids[i]
                lbl.config(text=f"{s:,.0f}ct   {p:,.2f}", fg=(GREEN if i == 0 else TEXT))
            else:
                lbl.config(text="—", fg=TEXT_DIM)

        notes = []
        if wall_ladder.get("ask_jebol"):
            notes.append("Ask wall JEBOL -> pindah wall berikutnya")
        if wall_ladder.get("bid_jebol"):
            notes.append("Bid wall JEBOL -> pindah wall berikutnya")
        if not notes and not asks and not bids:
            notes.append("Belum ada wall signifikan terdeteksi")
        self.lbl_wall_note.config(text=" | ".join(notes) if notes else "Ref wall aktif ditandai warna")

        # Live status bar
        pulse = data.get("buyer_aggression_pct", 50.0)
        cvd = data.get("cvd_30s", 0.0)
        overlay = data.get("tv_overlay_active", [])
        overlay_tag = f"  |  Pine: {','.join(overlay)}" if overlay else ""
        self._last_data_wall_time = time.time()
        self._live_line = f"Pulse {pulse:.1f}%   CVD {cvd:+.1f}{overlay_tag}"
        self.lbl_live.config(text=self._live_line)

    def _tick_heartbeat(self):
        self._heartbeat_on = not self._heartbeat_on
        self.lbl_heartbeat.config(fg=GREEN if self._heartbeat_on else "#1a3d24")

        if self._last_data_wall_time is not None:
            age = time.time() - self._last_data_wall_time
            stale_mark = "   ⚠ STALE" if age > 5 else ""
            self.lbl_live.config(text=f"{self._live_line}   ·  {age:.0f}s ago{stale_mark}",
                                  fg=(RED if age > 5 else TEXT_DIM))

        self.root.after(1000, self._tick_heartbeat)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = CRDashboardApp()
    app.run()
