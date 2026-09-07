# 👑 DOKTRIN ENTRY & INTEGRASI ORDER FLOW BOOKMAP (V4 MASTER)
### Spesifikasi Logika Eksekusi, Konfluensi Order Flow, & Engine Paper Trading Web
**Author & Commander: Dadang Wahyuono**  
*Prinsip Dasar: "Storyline Hidup, Bukan Skema Kaku — Sistem Mengikuti Market, Bukan Memaksa Market."*

---

# 📜 BAB 1: FILOSOFI DASAR — "PASAR MEMIMPIN, KITA MENGIKUTI"

## 1.1 Dilarang Menggunakan Skema Kaku (Anti-Rigid Checklist)
Pasar keuangan bukanlah mesin biner (`IF condition_A AND condition_B THEN entry`). Pasar adalah **aliran lelang likuiditas dinamis (Auction Market Theory)** yang digerakkan oleh pertarungan dua kekuatan:
1. **Aggressive Market Orders** (Trader yang butuh transaksi instan, menggerakkan harga).
2. **Passive Limit Orders** (Bandar / Institusi penyedia likuiditas, membentuk benteng / Mega Wall).

> 💡 **Hukum Emas Maestro Dadang:**  
> *"Jangan pernah mendikte market harus begini atau begitu. Tugas kita adalah membaca jalan cerita (storyline) pergerakan antar-timeframe, mengamati di mana likuiditas diserap oleh bandar, lalu menunggangi gelombang rantai tersebut (Ride the Chain)."*

---

# 🌊 BAB 2: ANATOMI LENGKAP DATA BOOKMAP & ORDER FLOW

Data Bookmap dari Mini PC (Port 9000 / Rithmic L2 Feed) adalah **mikroskop X-Ray** yang melihat isi di balik lilin candlestick:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STRUKTUR ORDER FLOW BOOKMAP                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. SPEEDOMETER MEGA WALLS (Limit Orders Buku Pesanan)                       │
│    • Ask Wall (Tembok Penjual): Merah Coral @4460.00 [1,400 Lot]            │
│    • Bid Wall (Tembok Pembeli): Hijau Mint @4448.00 [1,350 Lot]             │
│    • Fungsi: (A) Tembok Penahan / Benteng SL, (B) Magnet Likuiditas Target TP│
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. LIVE DELTA PER LILIN (Δ = Agresor Buy - Agresor Sell)                    │
│    • Δ +35: Buyer agresif menghantam ask limit order (Bullish pressure)     │
│    • Δ -18: Seller agresif menghantam bid limit order (Bearish pressure)     │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. CUMULATIVE VOLUME DELTA (CVD - Akumulasi Energi)                         │
│    • Mengukur akumulasi delta jangka menengah untuk mendeteksi DIVERGENCE   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. ABSORPTION PAUS (Diamond Marker 🐋 ABS 50L - 300L+)                      │
│    • Terjadi saat ribuan lot market order diserap habis oleh passive limit  │
│      di satu level harga tanpa sanggup menembusnya.                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ 5. VALUE AREA SUITE (POC, VAH, VAL, Naked POC 🧲 NPOC)                      │
│    • NPOC (Naked Point of Control): Area transaksi terpadat yang belum      │
│      pernah diuji ulang -> Magnet harga sangat kuat!                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# ⚔️ BAB 3: INTEGRASI 4 PILAR KONFLUENSI ENTRY

Entry yang berkualitas tinggi lahir dari keselarasan **4 Pilar Doktrin**:

```
                 👑 4 PILAR KONFLUENSI CHAIN REACTION
                                  │
       ┌──────────────────────────┼──────────────────────────┐
       ▼                          ▼                          ▼
  [PILAR 1]                  [PILAR 2]                  [PILAR 3]
RANTAI WAKTU (CMP)      ORDER FLOW BOOKMAP         S&D BARRIER RUNWAY
• Arah Master H4        • Delta Agresor Flip       • Origin TF Lock
• Zone Co-Timestamp     • CVD Divergence           • Jarak Runway >= 30p
• Hukum Otoritas Close  • Absorption Paus          • Barrier Tidak Menumpuk
                                  │
                                  ▼
                             [PILAR 4]
                        FOREXFACTORY SHIELD
                        • Volatility Clearance
                        • No High-Impact News <= 15m
```

---

# 🎯 BAB 4: SYARAT ENTRY BERDASARKAN STORYLINE PASAR

Sistem mengidentifikasi **3 Skenario Storyline Utama** di pasar:

---

## 🟢 SKENARIO 1: MOMENTUM CASCADE BREAKOUT (RIDE THE CHAIN)
*Kondisi saat harga menembus barrier penting dan didukung oleh agresi volume besar.*

### Syarat Terpenuhi:
1. **Arah & Rantai:** Lilin M5/M30 mencetak `CMP BUY` searah dengan `Root H4 BUY` (**Status CF**).
2. **Otoritas Break:** Lilin M5 **BODY CLOSE** menembus Barrier Resistance terdekat (bukan cuma ekor).
3. **Agresi Delta Bookmap:**
   - Live Delta lilin breakout bernilai **positif kuat ($\Delta \ge +25\text{ s/d }+80$)**.
   - CVD bergerak naik tajam mencetak *Higher High*.
4. **Mega Wall Status:** Ask Mega Wall di atas harga mulai termakan (`HIST LOT` bertambah) atau mundur ke atas (penjual panik mengangkat offer).
5. **Runway Target:** Ruang gerak menuju benteng berikutnya / Ask Mega Wall berikutnya $\ge 30 - 50\text{ Pips}$.

### Eksekusi & Manajemen:
* **Eksekusi:** Buka posisi **BUY Market Order** saat lilin M5 berikutnya open setelah body-close.
* **Stop Loss (SL):** 2–3 pips di bawah batas atas barrier yang baru saja dijebol (Role Reversal: Resistance menjadi Support). Maksimal 25–35 pips.
* **Take Profit (TP):**
  - **TP1 (50%):** Di Barrier M5/M15 lama berikutnya $\rightarrow$ Geser SL ke BEP.
  - **TP2 (50% Runner):** Di Ask Mega Wall utama atau Naked POC (`🧲 NPOC`).

---

## 🔵 SKENARIO 2: SNIPER LIQUIDITY SWEEP & ABSORPTION REJECTION (BOTTOM / TOP FISHING)
*Kondisi saat bandar melakukan stop-hunt / sweep ke zona likuiditas lalu menyerap semua order lawan.*

### Syarat Terpenuhi:
1. **Lokasi Medan Tempur:** Harga menusuk tajam ke dalam **Zona Bawaan H4 Co-Timestamp** atau **Fresh Demand/Supply Barrier**.
2. **Liquidity Sweep (Wick Spike):** Terjadi jarum suntik tajam (wick panjang) menembus level support/resistance sesaat.
3. **Order Flow Absorption (Serapan Paus):**
   - Muncul marker serapan bandar **`ABS (PAUS) ≥ 50L - 150L+`** persis di ujung ekor wick.
   - **CVD Divergence:** Harga membuat Low baru di M5, tetapi CVD **GAGAL** membuat Low baru (malah naik $\rightarrow$ pertanda seller agresif dijebak dan diserap oleh limit buyer).
4. **Dominasi Volume:** Buyer Volume Ratio $\ge 50\%$ (untuk sinyal BUY) atau Seller Volume Ratio $\ge 50\%$ (untuk sinyal SELL).

### Eksekusi & Manajemen:
* **Eksekusi:** Buka posisi **BUY / SELL Langsung di ekor jarum (Fast Sniper)** saat delta berbalik arah!
* **Stop Loss (SL):** Sangat tipis! Cukup **2–3 pips di luar ujung ekor wick sweep**. (Seringkali hanya berisiko 10–15 pips!).
* **Take Profit (TP):**
  - **TP1 (50%):** Di Mid-Point / Equilibrium (50% Retracement) atau POC harian.
  - **TP2 (50% Runner):** Di seberang zona S&D / Opposite Mega Wall. Rasio Risk/Reward sering mencapai **1:5 hingga 1:8+**!

---

## 🟡 SKENARIO 3: RETEST REJECTION DI ZONE BARRIER (SAFE DISCIPLINE)
*Kondisi saat harga kembali (pullback/retest) menguji zona yang valid setelah breakout awal.*

### Syarat Terpenuhi:
1. **Pullback Volume Rendah:** Harga kembali ke zona barrier dengan volume rendah / CVD melandai (tanda bukan dorongan agresor sungguhan, hanya koreksi).
2. **Mega Wall Defense:** Terdapat **Bid Wall $\ge 1,000\text{ Lot}$** yang duduk diam menjaga dasar zona.
3. **Rejection Confirmation:** Lilin M5 menyentuh zona lalu mencetak lilin *Pin Bar* atau *Engulfing* yang **BODY CLOSE** di luar zona menolak penurunan.
4. **Delta Agresor Bangkit:** Delta bar berubah dari merah menjadi hijau neon ($\Delta > 0$).

### Eksekusi & Manajemen:
* **Eksekusi:** Buka posisi **BUY / SELL pada Open lilin setelah Rejection Close**.
* **Stop Loss (SL):** Di balik Bid/Ask Wall pelindung (2–3 pips di bawah zona).
* **Take Profit (TP):** Di swing high/low sebelumnya dan Mega Wall target.

---

## 🔴 SKENARIO 4: VR (VOLATILITY REACTION / SCALPING LAWAN MASTER)
*Kondisi saat TF kecil (M30/M5) bergerak melawan Master H4.*

### Syarat Mutlak & Pembatasan Ketat:
1. **Status:** Diakui secara sadar sebagai **VR (Hanya Koreksi)** yang sedang menguji benteng H4.
2. **Wajib di Zona:** Entry **HANYA** boleh dilakukan di dalam Zona CMP TF kecil saat jam kelahirannya.
3. **Filter Runway Wajib:** Jarak ke Barrier M5/M15 terdekat wajib **$\ge 30 - 50\text{ Pips}$**. Jika hanya 5–10 pips $\rightarrow$ **MUTLAK VETO SKIP!**
4. **Target TP Dibatasi:** **HANYA SAMPAI BARRIER M5/M15 LAMA TERDEKAT!**  
   ❌ *DILARANG KERAS MENGHARAPKAN HARGA REVERSAL TEMBUS SAMPAI H4!* Begitu menyentuh barrier atau masuk zona H4, **WAJIB CLOSE 100%!**

---

# 🚫 BAB 5: 3 VETO S&D & FILTER ORDER FLOW (ANTI-TRAP)

Jika salah satu dari kondisi veto ini aktif, **PAPER TRADING ENGINE MUTLAK MENOLAK ENTRY (NO TRADE)**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             3 VETO S&D MUTLAK                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. COMPRESSION VETO (Pasar Terjepit / Squeeze)                              │
│    • Jarak antara Supply terdekat & Demand terdekat < 1.0 USD (< 10 Pips)   │
│    • STATUS: NO TRADE! (Pasar sedang terjepit, tunggu ledakan keluar).      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. VOLUME DOMINANCE VETO (Dilarang Menangkap Pisau Jatuh)                   │
│    • Ingin BUY tetapi Buyer Dominance < 50% (Seller masih berkuasa)         │
│    • Ingin SELL tetapi Seller Dominance < 50% (Buyer masih berkuasa)        │
│    • STATUS: VETO! Tunggu sampai dominasi volume berbalik arah.             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. RUNWAY DISTANCE VETO (Ruang Gerak Tidak Layak)                           │
│    • Jarak harga saat ini ke benteng lawan terdekat < 1.5 USD (< 15 Pips)   │
│    • STATUS: SKIP! Rasio Risk:Reward buruk (Risk 25 pip demi TP 10 pip).    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 📊 BAB 6: MATEMATIKA MONEY MANAGEMENT & AUTO LOT SIZING

Paper Trading Engine menghitung ukuran lot secara dinamis berdasarkan persentase risiko akun:

### Formula Lot:
$$\text{Lot Size} = \frac{\text{Virtual Balance (USD)} \times \text{Risk \%}}{\text{Jarak SL (Points)} \times \text{Tick Value}}$$

### Tabel Matriks Risiko Standar (Gold XAUUSD - Tick Value = $1.00 / Point):

| Modal Virtual | Risk % | Dollar Risk | Jarak SL (Pips) | Lot Sizing Otomatis | Target TP 1:3.5 | Potensi Profit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$10,000** | 1.0% | $100 | 25 Pips ($2.50) | **0.40 Lot** | 87.5 Pips ($8.75) | **+$350.00** |
| **$10,000** | 1.5% | $150 | 25 Pips ($2.50) | **0.60 Lot** | 87.5 Pips ($8.75) | **+$525.00** |
| **$50,000** | 1.0% | $500 | 25 Pips ($2.50) | **2.00 Lot** | 87.5 Pips ($8.75) | **+$1,750.00** |
| **$100,000**| 1.0% | $1,000 | 25 Pips ($2.50) | **4.00 Lot** | 87.5 Pips ($8.75) | **+$3,500.00** |

---

# 💻 BAB 7: ARSITEKTUR ENGINE PAPER TRADING WEB (CLIENT-SIDE)

Engine Paper Trading yang disematkan di Web Dashboard kita memiliki spesifikasi:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SPESIFIKASI ENGINE PAPER TRADING WEB                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. STATE & STORAGE PERSISTENCE                                              │
│    • Tersimpan otomatis di browser localStorage ('superpro_paper_account')  │
│    • Modal Awal: $10,000 USD (Bisa di-reset atau diatur bebas).             │
│    • Equity, Margin Terpakai, Free Margin, Floating PnL ter-update tiap 1s. │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. ORDER TYPES                                                              │
│    • 🟢 BUY MARKET / 🔴 SELL MARKET (Eksekusi instan di harga tick live)   │
│    • ⏳ BUY LIMIT / SELL LIMIT (Pending order di level barrier / wall)      │
│    • 🎯 BRACKET OCO: Auto Stop Loss & Auto Take Profit Terkunci             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. ON-CHART VISUAL POSITIONS (TradingView Lines)                            │
│    • Garis Biru/Hijau Putus-putus untuk Entry Price + Tag Floating PnL Live │
│    • Garis Merah Putus-putus untuk Level Stop Loss (Bisa di-drag di chart!) │
│    • Garis Hijau Neon Putus-putus untuk Level Take Profit (Bisa di-drag!)   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. STATISTIK PERFORMA REAL-TIME                                             │
│    • Win Rate (%) | Total Trades | Profit Factor | Max Drawdown             │
│    • Average R:R Realized | Riwayat Jurnal Transaksi (Exportable to CSV)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 👑 KESIMPULAN DOKTRIN:
Dengan memadukan **Rantai Waktu HTF (Kompas)**, **Barrier S&D (Ring Pertarungan)**, dan **Data Bookmap Delta/CVD/Mega Walls (Mikroskop Agresor)**, sistem Paper Trading ini menjadi replika trading institusional sejati tanpa memerlukan ketergantungan pada terminal MT5.
