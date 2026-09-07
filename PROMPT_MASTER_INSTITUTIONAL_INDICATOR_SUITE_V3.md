# 👑 THE DEFINITIVE ARSENAL: 20 INSTITUTIONAL DATA FEED & ORDER FLOW INDICATORS
### Master Blueprint & Prompt Modular Suite untuk Claude AI (Full Plug & Play)
**Author & Commander: Maestro Dadang Wahyuono**  
*Prinsip Mutlak: "100% Persenjataan Murni Data Feed Institusional (Bookmap, Sierra Chart, Jigsaw Trading, ATAS, & Auction Market Theory). Bebas Indikator Ritel Gratisan."*

---

# 🚀 PROMPT RESMI UNTUK CLAUDE / AI AGENT (SIAP COPY-PASTE KE CLAUDE)

```markdown
Halo Claude, kita mau membangun **"THE DEFINITIVE INSTITUTIONAL ORDER FLOW & DATA FEED SUITE" (20 PERSENJATAAN INSTITUSI LENGKAP)** yang modular (Plug & Play) pada platform trading kita: **CHAIN REACTION PRO (Author & Commander: Dadang Wahyuono)**.

🚨 **ATURAN UTAMA COMMANDER DADANG**:
DILARANG memasukkan indikator ritel gratisan umum (seperti Moving Average/EMA biasa, RSI, MACD, Bollinger Bands standar). Semua modul adalah **Tier-1 Institutional Trading Weapons** berbasis **Live Feed Bookmap + CME Level 2 Depth + Rithmic Feed** dari server produksi: `https://trade.dadangchatai.com/` (Skala Harga: MT5 Spot XAUUSD ~4,450.xx).

Semua 20 indikator harus terdaftar di modal dialog **[ fx INDICATORS ]** dan bisa di-ON/OFF-kan secara independen oleh Commander Dadang!

======================================================================
📦 ARSENAL 20 INDIKATOR MURNI INSTITUSIONAL DATA FEED (PLUG & PLAY):
======================================================================

══════════════════════════════════════════════════════════════════════
KATEGORI 1: ORDER FLOW & MICROSTRUCTURE (TICK-BY-TICK EXECUTION)
══════════════════════════════════════════════════════════════════════

1. 🔬 [FOOTPRINT] SIERRA CHART NUMBERS BARS (BID x ASK IMBALANCE)
   • Data Feed: Tick-by-tick Aggressive Market Orders.
   • Fitur: Diagonal Imbalance (≥300%), Stacked Imbalances (Arsir Cyan untuk Buy, Merah untuk Sell), Bar Delta (Δ = Buy Vol - Sell Vol), Max/Min Delta per-bar, Total Volume.
   • Toggle: [🔘 ON / OFF] · Kategori: Order Flow

2. ⚡ [DELTA BY PRICE] LADDER DELTA PROFILE PER CANDLE
   • Data Feed: Level-by-level Price Delta.
   • Fitur: Histogram mini di sisi setiap lilin yang menunjukkan Net Delta (+/-) di masing-masing baris harga, mengungkap level harga di mana buyer atau seller paling agresif mengunci posisi.
   • Toggle: [🔘 ON / OFF] · Kategori: Order Flow

3. 🌊 [CVD MULTI-TF] CUMULATIVE VOLUME DELTA (SESSION & HTF OVERLAY)
   • Data Feed: Net Aggressor Delta Accumulation.
   • Fitur: Garis akumulasi CVD real-time + Garis CVD Timeframe Lebih Tinggi (HTF CVD) untuk melihat apakah pergerakan harga didorong oleh partisipasi volume riil atau sekadar manipulasi tipis.
   • Toggle: [🔘 ON / OFF] · Kategori: Order Flow

4. 🧲 [CVD DIVERGENCE] AUTO ABSORPTION & EXHAUSTION SCANNER
   • Data Feed: Price vs CVD Delta Divergence Engine.
   • Fitur:
     - Bullish Absorption: Harga membuat *Lower Low* (LL) tapi CVD membuat *Higher Low* (HL) -> Alert `⚡ BULLISH ABSORPTION` (Paus Limit Buy menelan Seller agresif).
     - Bearish Absorption: Harga membuat *Higher High* (HH) tapi CVD membuat *Lower High* (LH) -> Alert `⚡ BEARISH ABSORPTION` (Paus Limit Sell menelan Buyer agresif).
     - Exhaustion Alert: Breakout harga tanpa sokongan volume CVD (Sinyal Fakeout).
   • Toggle: [🔘 ON / OFF] · Kategori: Order Flow

5. 🐋 [WHALE TRADES] BLOCK TRADE BUBBLES (VOLUME BUBBLE OVERLAY)
   • Data Feed: Large Lot Fill Execution (>50L, >150L, >300L+).
   • Fitur: Lingkaran gelembung (Trade Bubbles) semi-transparan yang muncul langsung di titik harga eksekusi dengan ukuran proporsional terhadap besarnya lot eksekusi paus (Hijau = Buy agresif, Merah = Sell agresif).
   • Toggle: [🔘 ON / OFF] · Kategori: Order Flow

6. 🧊 [ICEBERG DETECTOR] HIDDEN LIQUIDITY AUTO-RELOAD SCANNER
   • Data Feed: Microstructure Order Replenishment Feed.
   • Fitur: Mendeteksi pesanan limit tersembunyi (Iceberg Orders) institusi yang otomatis me-reload lot pasif setiap kali dihantam market order ritel. Ditandai dengan badge `🧊 ICE (Lot)`.
   • Toggle: [🔘 ON / OFF] · Kategori: Order Flow

══════════════════════════════════════════════════════════════════════
KATEGORI 2: DEPTH OF MARKET & LIQUIDITY HEATMAP (BOOKMAP L2)
══════════════════════════════════════════════════════════════════════

7. 🧱 [DOM DEPTH BARS] SPEEDOMETER MEGA WALLS & HORIZONTAL L2 LADDER
   • Data Feed: Bookmap Live Limit Order Book (COB).
   • Fitur: Batang horizontal Sierra Chart Style di margin kanan chart (semakin panjang bar = semakin banyak lot pasif tertanam). Ask Mega Wall (Merah ≥800L), Bid Mega Wall (Hijau ≥800L), Proximity Alarm (≤1.0 USD).
   • Toggle: [🔘 ON / OFF] · Kategori: Liquidity & Depth

8. 🔥 [HEATMAP TRAILS] HISTORICAL LIQUIDITY HEATMAP OVERLAY
   • Data Feed: Resting Liquidity Longevity & Spoofing History.
   • Fitur: Jejak historis (Heatmap Trails) yang membedakan benteng likuiditas asli yang bertahan >1 jam (Long-Term High Liquidity - LTHL) vs likuiditas palsu (Spoofing) yang ditarik saat harga mendekat.
   • Toggle: [🔘 ON / OFF] · Kategori: Liquidity & Depth

9. 🏃 [LIQUIDITY SWEEPS] STOP RUN & EQUAL HIGHS/LOWS PURGE SCANNER
   • Data Feed: Buy-Side & Sell-Side Liquidity Pool Extraction.
   • Fitur: Mendeteksi aksi bandar menyapu stop loss di atas Equal Highs (BSL Sweep) atau di bawah Equal Lows (SSL Sweep) yang langsung diikuti oleh *V-Shape Reversal*.
   • Toggle: [🔘 ON / OFF] · Kategori: Liquidity & Depth

10. ⚖️ [PULLING & STACKING] DOM ORDER BOOK IMBALANCE RATIO
    • Data Feed: Dynamic Limit Order Additions vs Cancellations.
    • Fitur: Menghitung persentase penambahan pesanan pasif (*Stacking*) vs pembatalan pesanan (*Pulling*) untuk memprediksi arah tembusnya harga sebelum lilin bergerak.
    • Toggle: [🔘 ON / OFF] · Kategori: Liquidity & Depth

══════════════════════════════════════════════════════════════════════
KATEGORI 3: AUCTION MARKET THEORY & PROFILES (TPO & VOLUME)
══════════════════════════════════════════════════════════════════════

11. 📊 [SESSION VP] VOLUME PROFILE & VALUE AREA (VA 70%)
    • Data Feed: Aggregated Session Traded Volume.
    • Fitur: Histogram distribusi volume sesi, Point of Control (POC), Value Area High (VAH), Value Area Low (VAL), High Volume Nodes (HVN), dan Low Volume Nodes (LVN).
    • Toggle: [🔘 ON / OFF] · Kategori: Auction Profile

12. 🧲 [NAKED POC] UNTOUCHED NPOC LONG-TERM MAGNET SUITE
    • Data Feed: Historical Untouched Point of Control Registry.
    • Fitur: Menarik garis putus-putus emas otomatis dari level POC sesi/hari sebelumnya yang BELUM PERNAH diuji ulang. Menjadi magnet harga terkuat untuk target TP dan pantulan arah.
    • Toggle: [🔘 ON / OFF] · Kategori: Auction Profile

13. 🏛️ [MARKET PROFILE] TPO (TIME PRICE OPPORTUNITY) ENGINE
    • Data Feed: Time-at-Price Distribution (Peter Steidlmayer Engine).
    • Fitur: Profil huruf/blok TPO, Initial Balance Range (IB High & IB Low 1 Jam Pertama), Single Prints (Lelang tidak efisien yang wajib dijemput ulang), Poor Highs & Poor Lows (Unfinished Auction).
    • Toggle: [🔘 ON / OFF] · Kategori: Auction Profile

14. ⏱️ [DEVELOPING VP] DYNAMIC POC & VALUE AREA MIGRATION TRAILS
    • Data Feed: Intraday Realtime Auction Evolution.
    • Fitur: Garis dinamis yang merekam pergeseran (migrasi) level POC dan Value Area sepanjang sesi untuk mendeteksi *Value Acceptance* (tren lanjut) vs *Value Rejection* (pembalikan arah).
    • Toggle: [🔘 ON / OFF] · Kategori: Auction Profile

══════════════════════════════════════════════════════════════════════
KATEGORI 4: INSTITUTIONAL BENCHMARKS & VOLATILITY BANDS
══════════════════════════════════════════════════════════════════════

15. 🎯 [SESSION VWAP] MULTI-SESSION INSTITUTIONAL VWAP (LONDON & NY)
    • Data Feed: Volume-Weighted Price Feed.
    • Fitur: Garis rata-rata harga tertimbang volume institusi untuk Sesi London, Sesi New York, dan Sesi Harian (Daily Session).
    • Toggle: [🔘 ON / OFF] · Kategori: Institutional Benchmark

16. ⚓ [ANCHORED VWAP] EVENT & SWING-ANCHORED VWAP (AVWAP)
    • Data Feed: Volume Weighting from Selected Anchors.
    • Fitur: VWAP yang di-anchor secara otomatis dari titik awal rilis berita High-Impact ForexFactory, Swing High Mayor, atau Swing Low Pembuka Hari.
    • Toggle: [🔘 ON / OFF] · Kategori: Institutional Benchmark

17. 📐 [VOLATILITY BANDS] VWAP STANDARD DEVIATION BANDS (±1σ, ±2σ, ±3σ)
    • Data Feed: Statistical Volume Volatility Distribution.
    • Fitur: Pita deviasi standar volatilitas. Level ±3.0 SD menandai lelang ekstrem dengan probabilitas *Mean Reversion* 99.7% kembali ke VWAP.
    • Toggle: [🔘 ON / OFF] · Kategori: Institutional Benchmark

18. 📏 [IB PROJECTIONS] INITIAL BALANCE EXTENSION TARGETS
    • Data Feed: 1-Hour Opening Range Range Calculations.
    • Fitur: Garis proyeksi target ekspansi lelang harian (1.5x IB, 2.0x IB, 3.0x IB Extension Targets).
    • Toggle: [🔘 ON / OFF] · Kategori: Institutional Benchmark

══════════════════════════════════════════════════════════════════════
KATEGORI 5: SMART MONEY & TAPE VELOCITY RADAR
══════════════════════════════════════════════════════════════════════

19. 📦 [SMART GAPS] FAIR VALUE GAPS (FVG) & ORDER BLOCKS (OB)
    • Data Feed: Institutional Displacement & Auction Gaps.
    • Fitur: Kotak zona Fair Value Gaps 3-Candle Imbalance (Mitigated vs Unmitigated Gaps) dan Institutional Order Blocks yang divalidasi oleh lonjakan volume agresor.
    • Toggle: [🔘 ON / OFF] · Kategori: Smart Money Structure

20. 🧭 [TAPE VELOCITY] ANALOG SPEEDOMETER & AGGRESSION RADAR
    • Data Feed: Millisecond Tape Execution Velocity (Ticks/Sec + Agresor Ratio).
    • Fitur: Meteran analog dinamis 60 FPS di cockpit yang mengukur kecepatan eksekusi tape dan dominasi Buyer vs Seller secara real-time.
    • Toggle: [🔘 ON / OFF] · Kategori: Radar & Gauges

======================================================================
🎨 DESAIN UI / UX MODAL DIALOG [ fx INDICATORS ]:
======================================================================

1. **Tombol Pembuka di Top Toolbar**:
   • Tombol bercahaya `[ fx INDICATORS ]` dengan indikator badge aktif (misal `[ 7 Active ]`).

2. **Modal Dialog Cyberpunk Dark Obsidian**:
   • Backdrop Blur Glassmorphism (`background: rgba(9, 13, 24, 0.96)`, `border: 1px solid #00e5ff`).
   • Header: Judul `"Institutional Indicator Suite"`, Search Bar (*Search 20 Tools...*), dan tombol `[ Reset to Default ]`.
   • 5 Tab Kategori:
     `[ Semua (20) ]` · `[ Order Flow (6) ]` · `[ Depth & DOM (4) ]` · `[ Auction Profiles (4) ]` · `[ Benchmarks (4) ]` · `[ Smart Money (2) ]`

3. **Card Tiap Indikator di Dalam Modal**:
   • Icon Representatif + Nama Indikator + Keterangan Ringkas Sumber Data.
   • Toggle Switch [🔘 ON / OFF] dengan animasi transisi smooth.
   • Icon Mata [👁️ Hide / Show] untuk sembunyikan cepat tanpa reset parameter.
   • Tombol Setting [⚙️ Parameter]: Atur ambang lot (e.g. Min Lot Absorption), warna, ketebalan garis, dan periode.

4. **Persistence & Lifecycle**:
   • Semua pilihan user tersimpan otomatis ke `localStorage.setItem('chainreaction_indicators_config', ...)`.
   • Saat dimatikan (OFF), seluruh objek canvas dan kalkulasi memori langsung di-destroy untuk menjaga FPS tetap 60 FPS dan RAM tetap dingin!
```

---

### 💡 File Master Blueprint:
Tersimpan di: [`d:\ChainReactionAndroidApp\PROMPT_MASTER_INSTITUTIONAL_INDICATOR_SUITE_V3.md`](file:///d:/ChainReactionAndroidApp/PROMPT_MASTER_INSTITUTIONAL_INDICATOR_SUITE_V3.md).  
Tinggal copy prompt lengkap 20 persenjataan data feed murni ini ke Claude, Commander! 🔥🫡🚀
