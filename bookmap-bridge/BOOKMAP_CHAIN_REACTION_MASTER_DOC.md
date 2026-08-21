# 📘 CHAIN REACTION — BOOKMAP BRIDGE SYSTEM v6.2
## Master Specification & Architectural Blueprint
**System Developer & Author:** DADANG WAHYUONO — Chain Reaction Trading System  
**Document Version:** 6.2 (Bookmap Master Edition)  
**File Location:** `C:/Bookmap/Python/BOOKMAP_CHAIN_REACTION_MASTER_DOC.md` & `f:/MCP TRADING VIEW/BOOKMAP_CHAIN_REACTION_MASTER_DOC.md`

---

## 1. FILOSOFI & DOKTRIN UTAMA SYSTEM

```
[ MT5 / TradingView Chart ]  ───>  MAPPING ZONE (PETA)  ───>  Chain Reaction Engine
                                                                      │
                                                                      ▼
[ Bookmap L1/L2 Order Flow ] ───>  KONDISI LAPANGAN     ───>  Validation Layer
                                                                      │
                                                                      ▼
[ Decision Recommendation ] ───>  🟢 BUY / 🔴 SELL / 🟡 WAIT ───> Manual Trader Execution
```

1. **Chain Reaction adalah PETA (Map):** Menentukan area penting (CMP Zone), hierarki tren (Daily > H4 > H1 > M30), dan arah hipotesis.
2. **Bookmap adalah KONDISI LAPANGAN (Field Validator):** Bookmap hanya mengonfirmasi atau melemahkan hipotesis Chain Reaction. Bookmap **TIDAK PERNAH** mengambil alih keputusan atau menjadi penentu utama.
3. **Decision Recommendation Engine (Bukan Signal Generator):** System tidak menghasilkan sinyal indikator acak. System menghasilkan **Rekomendasi Keputusan Biner** berdasarkan rulebook murni Chain Reaction yang divalidasi oleh order flow (Market Pulse & CVD Delta).
4. **Aturan Utama:**
   - Bookmap tidak boleh membuat trader takut entry.
   - Bookmap tidak boleh membuat trader overthinking.
   - Bookmap hanya memberikan informasi tambahan ketika harga sudah berada di area penting menurut Chain Reaction.

---

## 2. HIERARKI KEPUTUSAN (8-STEP DECISION HIERARCHY)

Mesin wajib mengeksekusi analisis berdasarkan urutan hierarki ketat berikut:

```
1. Timeframe Hierarchy (Daily / H4 / H1 / M30)
   ↓
2. Level CMP (Minor Support / Minor Resistance Zone)
   ↓
3. Status VR & CF (Volume Reaction & Chain Flip)
   ↓
4. Market Pulse (Buyer/Seller Aggression %)
   ↓
5. CVD Delta (Akumulasi Volume Order Flow 30 Detik)
   ↓
6. M5 Breakout (BO) Confirmation
   ↓
7. REKOMENDASI STATUS BINER: 🟢 BUY  /  🔴 SELL  /  🟡 WAIT
   ↓
8. Liquidity Wall (Target TP & Position Sizing — TIDAK MERUBAH DIRECTION)
```

---

## 3. ATURAN REKOMENDASI BINER (RULEBOOK)

### 🟢 RULE BUY (Re-Entry Continuation)
* **Kondisi:**
  - H4 CMP = `BUY`
  - M30 VR = `SELL` (Retest Area)
  - Market Pulse = `+` (Buyer Aggression ≥ 50%)
  - CVD Delta = `+` (CVD Delta > 0)
  - M5 BO = `BUY` (M5 Breakout Buy)
* **Output Status:** **`🟢 BUY`**
* **Interpretasi Sistem:**  
  `VR M30 Lemah. Buyer menguasai Order Flow. Probabilitas tinggi kembali mengikuti H4 BUY.`

---

### 🔴 RULE SELL (VR Strong / Reversal Flip)
* **Kondisi:**
  - H4 CMP = `BUY` (atau Sell Zone)
  - M30 VR = `SELL`
  - Market Pulse = `-` (Seller Aggression ≥ 50%)
  - CVD Delta = `-` (CVD Delta < 0)
  - M5 BO = `SELL` (M5 Breakout Sell)
* **Output Status:** **`🔴 SELL`**
* **Interpretasi Sistem:**  
  `VR M30 Kuat. Seller menguasai Order Flow. Probabilitas H4 CMP flip meningkat.`

---

### 🟡 RULE WAIT (Ambiguous / Strict Discipline)
* **Kondisi:**
  - Market Pulse `+` tetapi CVD `-` (Divergence / Bertolak Belakang), **ATAU**
  - Market Pulse `-` tetapi CVD `+`, **ATAU**
  - Belum ada konfirmasi M5 Breakout, **ATAU**
  - Harga berada di luar Zone CMP Active.
* **Output Status:** **`🟡 WAIT`**
* **Interpretasi Sistem:**  
  `Kondisi ambigu / Order flow belum sepakat. DILARANG ENTRY / SABAR!`

---

## 4. ATURAN KOLOM CMP (MULTI-TIMEFRAME MATRIX)

> [!IMPORTANT]
> **TIDAK ADA WAIT DI KOLOM CMP!**  
> Kolom CMP untuk seluruh Timeframe (`Daily`, `H4`, `H1`, `M30`, `M15`, `M5`, `M1`) **SELALU** bernilai definitif **`BUY`** atau **`SELL`** mengikuti garis CMP terkanan/terbaru.  
> Status **`WAIT`** HANYA diperuntukkan bagi Badge Rekomendasi Utama paling atas.

---

## 5. ATURAN POST-RECOMMENDATION LIQUIDITY WALL

> [!NOTE]
> **Wall Likuiditas (L2 Limit Orders) TIDAK PERNAH merubah `BUY ➔ SELL` atau `SELL ➔ BUY`.**  
> Wall dievaluasi strictly **SETELAH** rekomendasi BUY/SELL terbentuk. Wall dapat berpindah, ditarik (pulling), atau spoofing.

### Peran Wall:
1. **Estimasi Target Take Profit (TP):**
   - **BUY** + Ask Wall Terdekat (≤ 10 ticks) ➔ **Target Dekat (Conservative TP @ Ask Wall)**.
   - **BUY** + Ask Wall Jauh ➔ **Normal TP (Potensi Besar)**.
2. **Pengaturan Ukuran Posisi (Position Sizing):**
   - **SELL** + Bid Wall Terdekat ➔ **Reduce Position Size (Kurangi Lot)**.
   - **SELL** + Bid Wall Jauh ➔ **Full Position Size**.

---

## 6. ARSITEKTUR FILE SYSTEM & KOMPONEN (v9 — UDP Bridge Edition, FINAL)

> **PERUBAHAN PENTING v9:** Bookmap punya fitur "Python API" yang masih ALPHA
> dan editor bawaannya (`RSyntaxTextArea`'s `PythonFoldParser`) CRASH secara
> reproducible (`NullPointerException: currentFold is null`) begitu file
> Python-nya cukup kompleks (banyak class). Ini bug di Bookmap sendiri, bukan
> di kode kita — sudah dicoba disable "Code Folding" di editor tapi settingnya
> gak persist antar restart Bookmap dan tetap crash berulang.
>
> **SOLUSI FINAL:** Ketemu project lama `D:\PROJECT TRADING\wall-breakout-engine\`
> yang punya `bookmap_bridge.py` STABIL (kecil, ~98 baris, gak kena bug fold-parser)
> yang udah jalan sebagai addon Bookmap dan broadcast L1 trades + L2 depth via
> **UDP ke 127.0.0.1:9000**. Semua logic CMP/CVD/Pulse/decision kita sekarang
> jalan sebagai **proses Python BIASA** (`udp_listener.py`, di venv kita, gak
> nyentuh editor Bookmap sama sekali) yang dengerin UDP itu. Data tetap 100%
> murni dari Bookmap — cuma jalur masuknya UDP yang udah terbukti stabil,
> BUKAN via Bookmap's buggy embedded Python API editor.
>
> `bookmap_addon.py` dan `cr_decision_engine.py` (versi self-contained yang
> sempat dicoba load LANGSUNG ke Bookmap) masih ada di folder ini sebagai
> referensi/fallback kalau suatu saat Bookmap fix bug fold-parser-nya, tapi
> **TIDAK dipakai** di alur utama sekarang.
>
> CMP tetap doktrin SAMA PERSIS `DD_CMP_Marker.v6.2.pine` (minor-SNR
> body-breakout V/A-shape). Entry = breakout (CF) TF kecil DIDUKUNG order flow
> (Market Pulse + CVD). Bookmap L1 API TIDAK punya historical bars — history
> dibangun live sejak listener dijalankan. M5-H1 warm-up menit-jam; H4/D1
> butuh jam-hari — itu bukan bug, tinggal pantau H4 manual sambil nunggu.
>
> **PENTING — konflik port:** kalau `wall-breakout-engine`'s backend
> (`main.py`/`server.py`) dijalankan juga, dia bakal rebutan port UDP 9000
> sama `udp_listener.py` kita. Cuma boleh SATU yang jalan dengerin port itu
> di satu waktu.

```
bookmap-bridge/
├── udp_listener.py         # ★ ENTRY POINT — proses Python biasa, dengerin UDP 9000
│                           #   dari C:\Bookmap\Python\bookmap_bridge.py (stabil, punya
│                           #   wall-breakout-engine), jalanin seluruh pipeline di bawah
├── cmp_engine.py           # PURE PYTHON: bar aggregator dari tick + CMPDetector/TFState
│                           #   (port 1:1 dari engine/core.py, tanpa pandas/MT5) +
│                           #   BookmapDoctrineAnalyst (get_strike_signal, get_watch_reason)
├── market_data_engine.py   # Last price, bid/ask depth, nearest liquidity wall
├── cvd_engine.py           # Cumulative Volume Delta dari trade tape
├── market_pulse_engine.py  # Buyer/seller aggression % dari trade tape
├── cr_master_engine.py     # CRDecisionRecommendationEngine — gabung CMP+breakout+order flow
├── cr_dashboard_app.py     # Overlay Dashboard (Tkinter), baca live_status.json tiap 500ms
├── live_status.json        # Output udp_listener.py — rekomendasi final buat dashboard
├── bookmap_addon.py        # (fallback, TIDAK dipakai) — versi native-Bookmap-addon
├── cr_decision_engine.py   # (fallback, TIDAK dipakai) — versi self-contained buat editor Bookmap
└── start_dashboard.bat     # 1-Click Launcher Dashboard
```

### Detail Modul:

1. **`udp_listener.py`** (★ entry point utama):
   - Bind UDP socket `127.0.0.1:9000`, terima payload JSON `{"type":"trade"/"depth"/"instrument", ...}`
     yang dikirim `bookmap_bridge.py` (addon Bookmap yang stabil, sudah dipakai wall-breakout-engine).
   - Tiap payload trade → feed ke `bar_aggregator` (CMP) + `cvd_engine` + `market_pulse`.
   - Tiap payload depth → feed ke `market_data` (wall detection).
   - Tiap 0.5 detik: `master_engine.evaluate()` → tulis `live_status.json`.
   - Jalan sebagai proses Python BIASA (venv kita) — bisa di-edit/debug/restart kapan aja
     tanpa nyentuh Bookmap sama sekali.

2. **`cmp_engine.py`** (inti — pure Python, no external SDK):
   - `MultiTFAggregator`: tiap trade tick masuk → dibucket jadi candle OHLC per TF
     (M5/M15/M30/H1/H4/D1), sama kayak chart mana pun ngebentuk bar dari tick.
   - `CMPDetector` + `TFState`: port 1:1 dari `engine/core.py` — deteksi minor-SNR
     V-shape (support)/A-shape (resistance) body-breakout, tracking VR/CF/cf_count.
   - `BookmapDoctrineAnalyst`: cascade H4→H1→M30→M15→M5 (`update()`),
     `get_strike_signal()` = 4-tier breakout (MINOR_CF/CF_LOW/CF_HIGH/H4_CF_HIGH),
     `get_watch_reason()` = alasan hidup pas belum ada breakout.

3. **`cr_master_engine.py`:**
   - `CRDecisionRecommendationEngine.evaluate()`: H4 belum warm-up → WAIT (warm-up
     reason); belum ada breakout → WAIT (MONITORING, CMP kolom tetap live); ada
     breakout → ENTRY kalau Pulse+CVD align ke arah breakout, WAIT kalau belum align.
   - Alasan (`reason_lines`) & kesimpulan dibangun live dari data asli, bukan template statis.

4. **`cr_dashboard_app.py`:**
   - Overlay independen, baca `live_status.json`. Tabel multi-TF nunjuk CMP/VR/CF **live**
     murni dari tick Bookmap (kolom action nunjuk "WARMUP (n bars)" selama TF itu
     belum punya cukup candle).

---

## 7. CARA JALANIN

1. **Load addon ke Bookmap** (satu-satunya proses yang perlu jalan — gak ada proses lain):
   - Buka Bookmap ➔ **Bookmap Code Editor**.
   - Buka `bookmap_addon.py`, klik **Build**, centang di *Configure add-ons*.
   - CMP mulai kebangun otomatis dari tick pertama yang masuk.

2. **Jalanin Overlay Dashboard:**
   - Double-click `start_dashboard.bat` (atau `python cr_dashboard_app.py`).
   - Window **`DD — CMP Marker v6.2`** nongol. Awal-awal beberapa TF (terutama H4/D1)
     bakal nunjuk WARMUP — normal, tunggu tick Bookmap ngumpul.

---

*Dokumen ini spesifikasi Chain Reaction Bookmap Bridge System v7 (Live CMP Edition) oleh Dadang Wahyuono.*
