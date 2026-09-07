# 👑 MASTER BLUEPRINT & PROMPT: PURE INSTITUTIONAL DATA FEED SUITE
### Arsitektur Indikator 100% Berbasis Order Flow & Level 2 Data Feed (Bebas Indikator Retail)
**Author & Commander: Maestro Dadang Wahyuono**  
*Prinsip Mutlak: "Hapus semua indikator retail umum/gratisan (seperti Moving Average biasa). Maksimalkan 100% kekuatan Data Feed Institusional Bookmap, CME Futures L2, & Rithmic."*

---

# 🚀 PROMPT RESMI UNTUK CLAUDE / AI AGENT (SIAP COPY-PASTE KE CLAUDE)

```markdown
Halo Claude, kita mau membangun **"100% PURE INSTITUTIONAL ORDER FLOW & DATA FEED SUITE"** yang modular (Plug & Play) pada platform trading kita: **CHAIN REACTION PRO (Author & Commander: Dadang Wahyuono)**.

🚨 **ATURAN UTAMA DARI COMMANDER DADANG**:
DILARANG memasukkan indikator retail gratisan/umum yang lag (seperti Moving Average/EMA biasa, RSI, MACD). Platform kita adalah **Institutional-Grade Order Flow Terminal** yang memanfaatkan 100% kekuatan **Live Data Feed Bookmap + CME Level 2 Depth + Rithmic Feed** dari server produksi: `https://trade.dadangchatai.com/` (Skala Harga: MT5 Spot XAUUSD ~4,450.xx).

Semua modul harus tersedia di modal dialog **[ fx INDICATORS ]** dan bisa diaktifkan/dimatikan (Toggle ON/OFF) secara bebas oleh Commander Dadang!

======================================================================
📦 KATALOG PERSENJATAAN MURNI INSTITUTIONAL DATA FEED (PLUG & PLAY):
======================================================================

----------------------------------------------------------------------
1. 🔬 [FOOTPRINT] SIERRA CHART NUMBERS BARS (BID x ASK IMBALANCE)
----------------------------------------------------------------------
• Sumber Data: Tick-by-tick Level 2 Trade Stream.
• Fitur & Logika:
  - Diagonal Imbalance: Membandingkan Market Buy pada Ask(P+1) vs Market Sell pada Bid(P).
  - Stacked Imbalance (≥300%): Tiga baris imbalance berturut-turut diarsir warna **Cyan Neon** (Buy Imbalance) atau **Merah Crimson** (Sell Imbalance).
  - Bar Delta Statistics: Di bawah tiap candle ditampilkan nilai Delta (Δ = Buy Vol - Sell Vol), Max Delta, Min Delta, dan Total Volume.
  - Absorption Wick: Deteksi ekor jarum lilin dengan serapan volume agresif yang ditahan bandar.
• Toggle: [🔘 ON / OFF] · Kategori: Order Flow Feed

----------------------------------------------------------------------
2. 📊 [VOLUME PROFILE] AUCTION MARKET VOLUME PROFILE & NAKED POC
----------------------------------------------------------------------
• Sumber Data: Aggregated CME Traded Volume Profile.
• Fitur & Logika:
  - Point of Control (POC): Level harga dengan konsentrasi volume transaksi terpadat.
  - Value Area (VA 70%): Batas VAH (Value Area High) dan VAL (Value Area Low) lelang 70% pasar.
  - Naked POC (🧲 NPOC): Level POC historis dari sesi/hari sebelumnya yang BELUM PERNAH disentuh ulang. Menjadi magnet likuiditas terkuat untuk target Take Profit atau area pantulan.
  - High Volume Nodes (HVN) & Low Volume Nodes (LVN / Slippage Sinks).
• Toggle: [🔘 ON / OFF] · Kategori: Profile Feed

----------------------------------------------------------------------
3. 🏛️ [MARKET PROFILE] TPO (TIME PRICE OPPORTUNITY) & INITIAL BALANCE
----------------------------------------------------------------------
• Sumber Data: Time-at-Price Distribution (Sierra Chart / Peter Steidlmayer Engine).
• Fitur & Logika:
  - Initial Balance (IB): Range harga lelang 1 jam pertama sesi London/New York (IB High & IB Low).
  - Single Prints: Area eksekusi kilat (lelang tidak efisien) yang wajib diuji ulang oleh pasar.
  - Poor Highs & Poor Lows: Ujung lelang tumpul tanpa ekor rejection (Unfinished Auction).
  - TPO Value Area (TPO POC, TPO VAH, TPO VAL).
• Toggle: [🔘 ON / OFF] · Kategori: Profile Feed

----------------------------------------------------------------------
4. 🌊 [CVD] CUMULATIVE VOLUME DELTA & ABSORPTION DIVERGENCE SUB-PANE
----------------------------------------------------------------------
• Sumber Data: Net Aggressor Delta Accumulation.
• Fitur & Logika:
  - Garis kumulatif delta per-detik/menit yang menghitung selisih pembeli vs penjual agresif.
  - Bullish Absorption Divergence: Harga membuat *Lower Low* (LL) tapi CVD membuat *Higher Low* (HL) -> Sinyal serapan agresif oleh Limit Buy Paus. Muncul alert `⚡ BULLISH ABSORPTION`.
  - Bearish Absorption Divergence: Harga membuat *Higher High* (HH) tapi CVD membuat *Lower High* (LH) -> Sinyal serapan agresif oleh Limit Sell Paus. Muncul alert `⚡ BEARISH ABSORPTION`.
  - Exhaustion Divergence: Deteksi hilangnya tenaga volume saat breakout palsu.
• Toggle: [🔘 ON / OFF] · Kategori: Order Flow Feed

----------------------------------------------------------------------
5. 🧱 [WALLS] SPEEDOMETER MEGA WALLS & L2 HEATMAP DEPTH BARS
----------------------------------------------------------------------
• Sumber Data: Resting Passive Limit Orders (Bookmap Live COB Feed).
• Fitur & Logika:
  - Sierra Chart Style Horizontal Depth Bars: Batang kedalaman likuiditas di margin kanan chart (semakin panjang bar = semakin banyak lot pasif yang tertanam).
  - Ask Mega Wall: Merah Crimson (#ff334b) untuk benteng penjual (≥800 - 1500 Lot).
  - Bid Mega Wall: Hijau Emerald (#00e676) untuk benteng pembeli (≥800 - 1500 Lot).
  - Long-Term High Liquidity (LTHL): Tembok yang bertahan >1 jam tanpa ditarik/spoofed.
  - Proximity Impact Alert: Peringatan jika harga mendekati benteng dalam jarak ≤1.0 USD.
• Toggle: [🔘 ON / OFF] · Kategori: Order Flow Feed

----------------------------------------------------------------------
6. 🐋 [ABSORPTION] WHALE ABSORPTION DIAMONDS & ICEBERG DETECTOR
----------------------------------------------------------------------
• Sumber Data: Microstructure Order Fill / Trade Execution Feed.
• Fitur & Logika:
  - Diamond Badges di Lilin: Lencana `🐋 ABS 50L`, `ABS 150L`, `PAUS 300L+` langsung di titik harga ekor wick tempat serapan terjadi.
  - Iceberg Reload Detection: Deteksi pesanan tersembunyi yang otomatis mengisi ulang (auto-reload) setiap kali dihantam market order oleh pelaku ritel.
• Toggle: [🔘 ON / OFF] · Kategori: Order Flow Feed

----------------------------------------------------------------------
7. 📐 [MARKET CHANGE] STRUCTURE BREAKS (CHoCH, BOS, FVG, & ORDER BLOCKS)
----------------------------------------------------------------------
• Sumber Data: Smart Money Structure & Auction Gaps.
• Fitur & Logika:
  - Change of Character (CHoCH): Titik pembalikan arah struktur lelang pertama kali.
  - Break of Structure (BOS): Kelanjutan tren searah yang divalidasi oleh volume agresor.
  - Fair Value Gaps (FVG): Zona ketidakseimbangan likuiditas 3 lilin yang belum terisi.
  - Institutional Order Blocks (OB): Blok pesanan institusi sebelum ekspansi harga besar.
• Toggle: [🔘 ON / OFF] · Kategori: Structure Feed

----------------------------------------------------------------------
8. 🎯 [INSTITUTIONAL VWAP] VOLUME-WEIGHTED BENCHMARK & VOLATILITY BANDS
----------------------------------------------------------------------
• Sumber Data: Volume Weighted Price Feed (London & New York Institutional Standard).
• Fitur & Logika:
  - Session VWAP: Garis utama acuan harga rata-rata institusi dunia.
  - Volatility Standard Deviation Bands (±1.0 SD, ±2.0 SD, ±3.0 SD): Menghitung batas deviasi ekstrem lelang (Area Mean Reversion 99.7%).
• Toggle: [🔘 ON / OFF] · Kategori: Benchmark Feed

----------------------------------------------------------------------
9. 🧭 [TAPE SPEED] ANALOG MARKET PULSE & TAPE VELOCITY GAUGE
----------------------------------------------------------------------
• Sumber Data: Millisecond Tape Execution Velocity (Ticks/Sec + Agresor Split).
• Fitur & Logika:
  - Jarum analog 60 FPS bergerak reaktif mengukur kecepatan lelang (Speed of Tape) dan dominasi Buyer vs Seller secara real-time.
  - Zona: Hijau (Bullish Surge >60%), Kuning (Neutral 45-55%), Merah (Bearish Dump <40%).
• Toggle: [🔘 ON / OFF] · Kategori: Gauges & Radar

======================================================================
🎨 DESAIN UI / UX MODAL DIALOG [ fx INDICATORS ]:
======================================================================
1. Tombol [ fx INDICATORS ] di Top Toolbar dengan badge aktif (contoh: [ 5 Active ]).
2. Modal Dialog Obsidian Cyberpunk Glassmorphism dengan tab filter kategori & pencarian cepat:
   `[ Semua ]` · `[ Order Flow & Bookmap ]` · `[ Volume & Market Profile ]` · `[ Structure & Gaps ]` · `[ Benchmark & Gauges ]`
3. Card tiap indikator memiliki:
   - Toggle Switch [🔘 ON / OFF]
   - Icon Mata [👁️ Hide / Show]
   - Tombol Setting [⚙️ Parameter / Ambang Lot]
4. Semua state tersimpan otomatis di `localStorage` dan layer canvas/series langsung di-destroy saat di-turn OFF untuk performa super ringan dan bebas lag!
```

---

### 💡 File Master Prompt:
File ini tersimpan di: [`d:\ChainReactionAndroidApp\PROMPT_MASTER_INSTITUTIONAL_INDICATOR_SUITE_V2.md`](file:///d:/ChainReactionAndroidApp/PROMPT_MASTER_INSTITUTIONAL_INDICATOR_SUITE_V2.md).  
Tinggal salin blok teks di atas ke Claude, Commander! Persenjataan murni 100% Data Feed tanpa indikator gratisan! 🫡🔥🚀
