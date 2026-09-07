"""
Chain Reaction DD v6.2 Floating Overlay Dashboard for Bookmap
Location: C:/Bookmap/Python/cr_dashboard.py
Author: DADANG WAHYUONO - Chain Reaction System
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
from typing import Dict, Any

class CRDashboardOverlay:
    def __init__(self):
        self.root = None
        self.is_running = False
        self.data_store = {
            "D": {"cmp": "BUY", "vr": "BREAK H4", "cf": "BUY LOW #4", "action": "CF H4✓→prediksi Daily IJO", "time": "03:45/19:45"},
            "H4": {"cmp": "BUY", "vr": "BREAK H1", "cf": "BUY LOW #2", "action": "CF H1✓→prediksi H4 IJO", "time": "11:45/15:45"},
            "H1": {"cmp": "BUY", "vr": "BREAK M30", "cf": "BUY LOW #2", "action": "CF M30✓→prediksi H1 IJO", "time": "08:45/15:45"},
            "M30": {"cmp": "BUY", "vr": "–", "cf": "–", "action": "★ MASTER — liat MESIN ⬇", "time": "12:45/12:30"},
            "M15": {"cmp": "BUY", "vr": "–", "cf": "–", "action": "cerita: tunggu VR M5", "time": "12:30/11:45"},
            "M5": {"cmp": "SELL", "vr": "–", "cf": "–", "action": "MONITOR", "time": "–"},
            "M1": {"cmp": "SELL", "vr": "–", "cf": "–", "action": "MONITOR", "time": "–"},
            "recommendation": "WAIT",
            "status_badge": "🟡 WAIT",
            "reason_lines": ["Waiting for Order Flow Confirmation..."],
            "conclusion": "Menunggu konfirmasi area & order flow.",
            "wall_summary": "No Wall Near",
            "target_advice": "Normal TP",
            "sizing_advice": "Full Position Size"
        }

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        thread = threading.Thread(target=self._run_gui, daemon=True)
        thread.start()

    def _run_gui(self):
        try:
            self.root = tk.Tk()
            self.root.title("DD — CMP Marker v6.2 | Decision Recommendation Engine")
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.94)
            self.root.configure(bg="#0a0a14")
            self.root.geometry("520x460+20+60")

            # Title Header Frame
            title_frame = tk.Frame(self.root, bg="#15110a", bd=1, relief="solid")
            title_frame.pack(fill="x", padx=4, pady=2)
            lbl_title = tk.Label(
                title_frame, text="DADANG WAHYUONO — CHAIN REACTION SYSTEM v6.2",
                font=("Segoe UI", 9, "bold"), fg="#E0B33A", bg="#15110a"
            )
            lbl_title.pack(pady=2)

            # Recommendation Badge Frame
            self.badge_frame = tk.Frame(self.root, bg="#101018", bd=1, relief="ridge")
            self.badge_frame.pack(fill="x", padx=4, pady=2)

            self.lbl_badge = tk.Label(
                self.badge_frame, text="🟡 WAIT", font=("Segoe UI", 16, "bold"),
                fg="#FFD700", bg="#101018", pady=4
            )
            self.lbl_badge.pack()

            # Multi-Timeframe Matrix Frame
            self.table_frame = tk.Frame(self.root, bg="#0a0a14")
            self.table_frame.pack(fill="x", padx=4, pady=2)
            self._build_table()

            # Reason & Conclusion Panel Frame
            self.reason_frame = tk.Frame(self.root, bg="#101018", bd=1, relief="ridge")
            self.reason_frame.pack(fill="both", expand=True, padx=4, pady=4)

            lbl_reason_hdr = tk.Label(
                self.reason_frame, text="📌 ALASAN & KESIMPULAN REKOMENDASI:",
                font=("Segoe UI", 8, "bold"), fg="#7FE7FF", bg="#101018", anchor="w"
            )
            lbl_reason_hdr.pack(fill="x", padx=6, pady=2)

            self.lbl_reasons = tk.Label(
                self.reason_frame, text="", font=("Consolas", 8),
                fg="#D1D5DB", bg="#101018", justify="left", anchor="w"
            )
            self.lbl_reasons.pack(fill="x", padx=10)

            self.lbl_conclusion = tk.Label(
                self.reason_frame, text="", font=("Segoe UI", 8, "bold"),
                fg="#E0B33A", bg="#101018", justify="left", anchor="w"
            )
            self.lbl_conclusion.pack(fill="x", padx=10, pady=2)

            # Wall & Target Advice Panel
            self.lbl_wall = tk.Label(
                self.reason_frame, text="", font=("Consolas", 8),
                fg="#00E676", bg="#101018", justify="left", anchor="w"
            )
            self.lbl_wall.pack(fill="x", padx=10, pady=2)

            self.root.mainloop()
        except Exception as e:
            print(f"[CR-Dashboard] GUI Error: {e}", flush=True)

    def _build_table(self):
        headers = ["⏱ TF", "📊 CMP", "🔄 VR", "✅ CF", "🚀 ACTION", "🕐 JAM"]
        col_widths = [8, 7, 10, 11, 24, 11]

        for col_idx, text in enumerate(headers):
            bg_col = "#000080" if col_idx == 0 else ("#800000" if col_idx == 1 else ("#FF8C00" if col_idx == 2 else ("#008080" if col_idx == 3 else ("#800080" if col_idx == 4 else "#404040"))))
            lbl = tk.Label(
                self.table_frame, text=text, font=("Consolas", 8, "bold"),
                fg="#FFFFFF", bg=bg_col, width=col_widths[col_idx], anchor="center", bd=1, relief="ridge"
            )
            lbl.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)

        self.row_labels = {}
        rows_info = [
            ("Daily", "D", "#000080"),
            ("H4 ◆CTRL", "H4", "#800080"),
            ("H1", "H1", "#008080"),
            ("M30 ★", "M30", "#FF8C00"),
            ("M15", "M15", "#FF00FF"),
            ("M5", "M5", "#202020"),
            ("M1", "M1", "#202020")
        ]

        for row_idx, (tf_display, tf_key, tf_bg) in enumerate(rows_info, start=1):
            lbl_tf = tk.Label(self.table_frame, text=tf_display, font=("Consolas", 8, "bold"), fg="#FFFFFF", bg=tf_bg, bd=1, relief="ridge")
            lbl_tf.grid(row=row_idx, column=0, sticky="nsew", padx=1, pady=1)

            cmp_val = self.data_store[tf_key]["cmp"]
            cmp_bg = "#00E676" if cmp_val == "BUY" else ("#FF3B30" if cmp_val == "SELL" else "#404040")
            lbl_cmp = tk.Label(self.table_frame, text=cmp_val, font=("Consolas", 8, "bold"), fg="#FFFFFF", bg=cmp_bg, bd=1, relief="ridge")
            lbl_cmp.grid(row=row_idx, column=1, sticky="nsew", padx=1, pady=1)

            lbl_vr = tk.Label(self.table_frame, text=self.data_store[tf_key]["vr"], font=("Consolas", 7), fg="#C9A227", bg="#101015", bd=1, relief="ridge")
            lbl_vr.grid(row=row_idx, column=2, sticky="nsew", padx=1, pady=1)

            lbl_cf = tk.Label(self.table_frame, text=self.data_store[tf_key]["cf"], font=("Consolas", 7), fg="#00E676", bg="#101015", bd=1, relief="ridge")
            lbl_cf.grid(row=row_idx, column=3, sticky="nsew", padx=1, pady=1)

            act_bg = "#15110a" if "MASTER" in self.data_store[tf_key]["action"] else "#101015"
            act_fg = "#E0B33A" if "MASTER" in self.data_store[tf_key]["action"] else "#8B92A0"
            lbl_act = tk.Label(self.table_frame, text=self.data_store[tf_key]["action"], font=("Consolas", 7), fg=act_fg, bg=act_bg, anchor="w", bd=1, relief="ridge")
            lbl_act.grid(row=row_idx, column=4, sticky="nsew", padx=1, pady=1)

            lbl_time = tk.Label(self.table_frame, text=self.data_store[tf_key]["time"], font=("Consolas", 7), fg="#7FE7FF", bg="#101015", bd=1, relief="ridge")
            lbl_time.grid(row=row_idx, column=5, sticky="nsew", padx=1, pady=1)

            self.row_labels[tf_key] = (lbl_cmp, lbl_vr, lbl_cf, lbl_act, lbl_time)

    def update_data(self, new_data: Dict[str, Any]):
        self.data_store.update(new_data)
        if self.root:
            self.root.after(0, self._refresh_ui)

    def _refresh_ui(self):
        if not self.root:
            return

        # 1. Update Badge
        badge_text = self.data_store.get("status_badge", "🟡 WAIT")
        badge_color = "#00E676" if "BUY" in badge_text else ("#FF3B30" if "SELL" in badge_text else "#FFD700")
        self.lbl_badge.config(text=badge_text, fg=badge_color)

        # 2. Update Table Rows
        for tf_key, labels in self.row_labels.items():
            if tf_key in self.data_store:
                info = self.data_store[tf_key]
                lbl_cmp, lbl_vr, lbl_cf, lbl_act, lbl_time = labels
                cmp_val = info.get("cmp", "WAIT")
                cmp_bg = "#00E676" if cmp_val == "BUY" else ("#FF3B30" if cmp_val == "SELL" else "#404040")
                lbl_cmp.config(text=cmp_val, bg=cmp_bg)
                lbl_vr.config(text=info.get("vr", "–"))
                lbl_cf.config(text=info.get("cf", "–"))
                lbl_act.config(text=info.get("action", "–"))
                lbl_time.config(text=info.get("time", "–"))

        # 3. Update Reason Lines & Conclusion Panel
        reasons = self.data_store.get("reason_lines", [])
        self.lbl_reasons.config(text="\n".join(reasons))

        conclusion = self.data_store.get("conclusion", "")
        self.lbl_conclusion.config(text=f"💡 Kesimpulan: {conclusion}")

        wall_sum = self.data_store.get("wall_summary", "No Wall Near")
        target_adv = self.data_store.get("target_advice", "Normal TP")
        sizing_adv = self.data_store.get("sizing_advice", "Full Position Size")
        self.lbl_wall.config(text=f"🧱 Wall: {wall_sum}\n🎯 Target: {target_adv} | Position: {sizing_adv}")
