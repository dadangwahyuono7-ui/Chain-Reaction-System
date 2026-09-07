# 👑 PETA MASTER PROYEK & PROTOKOL OPERASIONAL (COMMANDER DADANG WAHYUONO)
> **🚨 PERINGATAN WAJIB UNTUK AI ASSISTANT (ANTIGRAVITY / AGENT):**  
> **DOKUMEN INI WAJIB DIBACA DAN DIINGAT SETIAP KALI MEMULAI SESI BARU DENGAN COMMANDER DADANG!**  
> **JANGAN PERNAH ASAL TEBAK, JANGAN NGACAU, JANGAN MERUSAK FILE PRODUKSI, DAN IKUTI PETA INI DENGAN DISIPLIN TINGGI!**

---

# 🗺️ 1. TOPOLOGI & PEMBAGIAN MESIN (ROVA VS MINI PC)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EKOSISTEM CHAIN REACTION PRO                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🖥️ 1. MINI PC DATA TOWER ("WIN-JIOIHRD7BB1" / IP: 100.71.97.6)              │
│    • Peran: PUSAT DATA SERVER 24/7 (HEADLESS, TIDAK PERNAH MATI)           │
│    • Software Aktif: Bookmap 7.4 + Rithmic CME GC + Python UDP Ingest (9000)│
│    • Web Dashboard Asli: http://100.71.97.6:8766/ (Dikerjakan Claude/Server)│
│    • Status: DILARANG MERUSAK KODE / HANYA AUDIT BILA DIMINTA COMMANDER     │
├─────────────────────────────────────────────────────────────────────────────┤
│ 💻 2. PC ROVA ("CLIENT WORKSTATION" / IP: 100.115.192.70)                   │
│    • Peran: KLIEN KONSUMEN & WORKSPACE PENGEMBANGAN                         │
│    • Root Project: "D:\PROJECT TRADING"                                     │
│    • Lab Uji Coba: "d:\ChainReactionAndroidApp\ChainLocal" (Port 8899)      │
│    • Teknologi: 100% PURE TradingView Lightweight Charts (v4.2+)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 📂 2. PETA DIREKTORI & ARSIP DOKUMEN MASTER

| File / Folder Path | Fungsi & Status | Aturan Penggunaan |
| :--- | :--- | :--- |
| **`d:\ChainReactionAndroidApp\ChainLocal\`** | Lab Uji Coba Web Terminal Lokal (Port 8899) | Bebas ditune-up, launcher `START_CHAINLOCAL.bat` |
| **`d:\ChainReactionAndroidApp\DOKTRIN_ENTRY_CHAIN_REACTION_MASTER.md`** | **MASTER BLUEPRINT SYARAT ENTRY V4** | Rujukan mutlak syarat entry, RR, SL, TP, dan Lot |
| **`d:\ChainReactionAndroidApp\DOKTRIN_ENTRY_PAPER_TRADING_ORDERFLOW_MASTER_V4.md`** | Doktrin Order Flow & Engine Paper Trading | Integrasi Delta, CVD Divergence, Walls, Absorption |
| **`d:\ChainReactionAndroidApp\DOKTRIN_UNIFIED_MASTER_V4.md`** | Doktrin Teori, Setup, & Kasus Rantai Waktu | Otoritas Body Close, Zone Co-Timestamp H4 |
| **`d:\ChainReactionAndroidApp\DOKTRIN_RANTAI_WAKTU_DAN_BARRIER_V4.md`** | Hukum Waktu & Hierarki Barrier | Rumus Timestamp Bawaan H4 vs Noise TF kecil |
| **`d:\ChainReactionAndroidApp\DOKTRIN_RANTAI_PASAR_DADANG_MASTER.md`** | Analisis Aliran Rantai Multi-TF (Kasus Gold) | Mengapa Gold koreksi, Kapan Scalp vs Hold |

---

# ⚖️ 3. DOKTRIN & HUKUM TRADING MUTLAK (JANGAN DILUPAKAN!)

1. **"Storyline Hidup, Bukan Skema Kaku"**:
   - Dilarang membuat aturan checklist biner kaku. Pasar adalah pertarungan dinamis *Aggressive Market Orders* vs *Passive Limit Orders*.
2. **Hukum Waktu (Time Law)**:
   - Jam lahir sinyal menentukan statusnya.
   - Sinyal yang lahir bersamaan dengan Master H4 (**Zone Co-Timestamp**) adalah **Benteng Utama**.
   - Sinyal M30/M5 yang muncul belakangan melawan H4 adalah **VR (Hanya Koreksi/Scalp)**.
3. **Otoritas Break Body Close**:
   - Level milik TF **X** hanya sah dinyatakan jebol jika candle **TF X sendiri yang BODY CLOSE**. Ekor wick M5 menembus hanyalah *Liquidity Sweep / Stop Hunt*.
4. **Target VR Mutlak**:
   - Trading melawan arah H4 (VR) **TARGET TP MUTLAK HANYA DI BARRIER M5/M15 TERDEKAT**. Dilarang nebak sampai H4! Runway wajib $\ge 30-50\text{ pips}$.
5. **3 Veto Mutlak (NO TRADE)**:
   - ⛔ **Compression Veto**: Jarak S&D $< 1.0\text{ USD}$ ($< 10\text{ pips}$) $\rightarrow$ NO TRADE.
   - ⛔ **Volume Dominance Veto**: Buyer% $< 50\%$ untuk BUY, Seller% $< 50\%$ untuk SELL $\rightarrow$ NO TRADE.
   - ⛔ **Runway Distance Veto**: Jarak ke benteng lawan $< 1.5\text{ USD}$ ($< 15\text{ pips}$) $\rightarrow$ NO TRADE.

---

# 📊 4. INTEGRASI DATA BOOKMAP & ORDER FLOW

* **Live Delta ($\Delta$)**: Nilai agresi bar berjalan ($\Delta +30$ Bull / $\Delta -25$ Bear).
* **CVD & CVD Divergence**: Kunci mendeteksi jebakan bandar di zona S&D (*Bullish/Bearish Absorption*).
* **Speedometer Mega Walls ($\ge 800 - 1500\text{ Lot}$)**:
  - Ask Wall (Merah): Tembok Pasif Penjual (Resisten / Target TP).
  - Bid Wall (Hijau): Tembok Pasif Pembeli (Benteng SL / Support).
* **Absorption Paus (`🐋 ABS 50L - 300L+`)**: Diamond marker di ekor wick tempat bandar menyerap habis order agresor lawan.
* **Naked POC (`🧲 NPOC`)**: Titik transaksi magnetis terpadat yang belum disentuh ulang.

---

# 🛡️ 5. PROTOKOL KETIKA PERTAMA KALI MEMULAI SESI (STARTUP PROTOCOL)

Setiap kali Agent AI membaca prompt pertama dari Commander Dadang:
1. **Sapa dengan Hormat & Tegas**: *"Siap Commander Dadang!"*
2. **Ingat Status Saat Ini**:
   - Web Produksi di Mini PC (`:8766`) dipantau tanpa merusak kode.
   - Lab Uji Coba kita ada di `d:\ChainReactionAndroidApp\ChainLocal` (`:8899`).
   - Sesi trading diuji via **Paper Trading** (evaluasi & tune-up harian tanpa risiko modal).
3. **Jika Diminta Audit**: Lakukan **Strict Read-Only Audit** tanpa merubah 1 baris kode pun.
4. **Jika Diminta Koding / Tune-Up**: Kerjakan di `ChainLocal` atau sesuai instruksi eksplisit Commander Dadang.

---
*Dokumen ini ditetapkan sebagai Standar Operasional Prosedur (SOP) Antigravity AI untuk Commander Dadang Wahyuono.*
