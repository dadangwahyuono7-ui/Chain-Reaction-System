# 👑 MASTER BLUEPRINT & PROMPT: MODULAR INSTITUTIONAL INDICATOR SUITE
### Arsitektur Indikator Sierra Chart + Bookmap Terintegrasi (Lepas-Pasang / Plug & Play)
**Author & Commander: Dadang Wahyuono**  
*Tujuan: Menggantikan indikator retail biasa (RSI/MACD) dengan persenjataan Order Flow Institusional yang modular seperti `fx Indicators` di TradingView.*

---

# 🚀 PROMPT RESMI UNTUK CLAUDE / AI AGENT (SIAP COPY-PASTE)

```markdown
Halo Bro, kita mau bangun "INSTITUTIONAL ORDER FLOW INDICATOR SUITE" di Web Dashboard kita (baik di Mini PC maupun Local). 

Di TradingView biasa, indikatornya cuma retail umum (RSI, MACD, Moving Average). Di CHAIN REACTION PRO, kita mau SEMUA INDIKATOR KELAS INSTITUSI (SIERRA CHART + BOOKMAP) tersedia lengkap di modal [ fx INDICATORS ] dan BISA DILEPAS-PASANG (TOGGLE ON/OFF) secara bebas oleh Commander Dadang seperti di TradingView!

Berikut adalah 8 Modul Indikator Wajib yang harus tersedia:

======================================================================
📦 8 KATALOG INDIKATOR INSTITUSIONAL (MODULAR / PLUG & PLAY):
======================================================================

1. 🔬 [FOOTPRINT] BID x ASK IMBALANCE & ABSORPTION WICK
   • Fitur: Deteksi Diagonal Imbalance (≥300%) di lilin dan serapan volume di ekor jarum.
   • Visual: Highlight warna cyan untuk Stacked Buy Imbalance, merah untuk Stacked Sell Imbalance.
   • Toggle: [ON / OFF]

2. 📊 [PROFILE] VOLUME PROFILE & NAKED POC (🧲 NPOC)
   • Fitur: Point of Control (POC), Value Area High (VAH), Value Area Low (VAL), dan Naked POC yang belum tersentuh.
   • Visual: Garis solid Cyan (POC), garis dashed emas (🧲 NPOC), zona transparan Value Area (70% Volume).
   • Toggle: [ON / OFF]

3. 🌊 [CVD] CUMULATIVE VOLUME DELTA & DIVERGENCE SUB-PANE
   • Fitur: Bar Delta (Δ = Buy Market - Sell Market), CVD line, dan deteksi otomatis Bullish/Bearish Absorption Divergence.
   • Visual: Sub-chart oscillator di bawah chart + label alert "⚡ BULLISH ABSORPTION DIVERGENCE".
   • Toggle: [ON / OFF]

4. 🧱 [WALLS] SPEEDOMETER MEGA WALLS & L2 DEPTH
   • Fitur: Ask Mega Wall (Merah) & Bid Mega Wall (Hijau) (≥800 - 1500 Lot) + Status Magnet LTHL (>1 jam).
   • Visual: On-Chart Price Lines putus-putus dengan tag jarak pips dan alarm Proximity Impact (≤1.0 USD).
   • Toggle: [ON / OFF]

5. 🎯 [VWAP] INSTITUTIONAL VWAP & MULTI-SD BANDS
   • Fitur: Intraday Session VWAP dengan Band Deviasi Volatilitas ±1 SD, ±2 SD, ±3 SD.
   • Visual: Garis ungu solid di tengah + band dotted ungu transparan di atas dan bawah.
   • Toggle: [ON / OFF]

6. 🐋 [ABSORPTION] WHALE & BANDAR ABSORPTION BADGES
   • Fitur: Diamond badges "ABS 50L", "ABS 126K", "PAUS 300L+" langsung di ekor wick tempat serapan terjadi.
   • Visual: Panah/Diamond hijau neon (bawah) dan merah neon (atas).
   • Toggle: [ON / OFF]

7. 📐 [EMA] DOKTRIN V4 TRIPLE STRUCTURAL EMAS
   • Fitur: EMA 9 (Fast Trigger - Cyan), EMA 21 (Pullback Filter - Amber Gold), EMA 50 (Macro Structure - Purple).
   • Visual: Smooth curve lines dengan label nama di ujung chart kanan.
   • Toggle: [ON / OFF]

8. 🧭 [PULSE] ANALOG SPEEDOMETER MARKET PULSE & AGGRESSION
   • Fitur: Jarum analog dinamis mengukur kekuatan CVD vs Agresor (Bear Dump / Balanced / Bull Surge).
   • Visual: Gauge canvas di cockpit dengan jarum halus 60 FPS.
   • Toggle: [ON / OFF]

======================================================================
🎨 DESAIN UI & MODAL SELECTOR [ fx INDICATORS ]:
======================================================================
1. Tombol [ fx INDICATORS ] di Header Top Toolbar:
   • Ketika diklik, muncul Modal Dialog Glassmorphism (Cyberpunk Obsidian).
   • Ada tab kategori: [Semua], [Order Flow / Bookmap], [Volume Profile], [Trend & EMA].
   • Tiap indikator punya:
     - Toggle Switch [🔘 ON / OFF]
     - Icon Mata [👁️ Sembunyikan / Tampilkan]
     - Tombol Setting [⚙️ Atur Warna & Parameter]
2. Indikator Pills Cepat di Atas Chart:
   • Menampilkan status aktif / non-aktif indikator terpilih secara ringkas (contoh: [EMA] [VWAP] [POC] [ABS] [WALLS] [CVD] [PULSE]).

Pastikan arsitekturnya modular di JavaScript sehingga Commander Dadang bisa memilih kombinasi indikator apa pun tanpa membuat chart terasa berat atau lag!
```

---

# 🏗️ SPESIFIKASI TEKNIS & ARSITEKTUR KODE (CLIENT-SIDE JS)

Untuk implementasi di `ChainLocal` maupun di `bookmap-bridge-v1/sultan/index.html`:

### 1. State Manager Indikator Modular (`window.SuperProIndicators`)
```javascript
const IndicatorConfig = {
  footprint: { enabled: false, name: "Bid x Ask Imbalance", group: "orderflow" },
  volumeProfile: { enabled: true, name: "Volume Profile & NPOC", group: "profile" },
  cvdOscillator: { enabled: true, name: "CVD & Delta Divergence", group: "delta" },
  megaWalls: { enabled: true, name: "Speedometer Mega Walls", group: "orderflow" },
  vwapBands: { enabled: true, name: "Institutional VWAP & Bands", group: "trend" },
  whaleAbs: { enabled: true, name: "Whale Absorption Diamonds", group: "orderflow" },
  structuralEMAs: { enabled: true, name: "EMA 9 / 21 / 50 Triad", group: "trend" },
  analogGauge: { enabled: true, name: "Analog Market Pulse Gauge", group: "gauge" }
};
```

### 2. Event Hook Lifecycle:
- `onIndicatorToggle(indicatorKey, isEnabled)`:
  - Jika `false` $\rightarrow$ Hapus series / price lines / sub-pane canvas seketika (`chart.removeSeries()`).
  - Jika `true` $\rightarrow$ Inisialisasi ulang dan pasang data secara reaktif.
  - Simpan preferensi pilihan user ke `localStorage.setItem('superpro_active_indicators', ...)`.

---

### 👑 DOKUMEN INI DIJADIKAN STANDAR BAKU PENGEMBANGAN FITUR WEB KITA.
