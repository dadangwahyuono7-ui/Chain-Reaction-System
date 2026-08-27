# Chain Reaction System — Native Android Application

Aplikasi Native Android (Kotlin + Jetpack Compose) untuk sistem trading otomatis XAUUSD (Gold) 24 jam milik **Commander Dadang**.

Aplikasi ini bertindak sebagai **Client Terminal** murni tanpa auth/login yang melakukan live polling ke 4 endpoint JSON dari backend di `https://trade.dadangchatai.com`.

---

## 📱 Arsitektur & Teknologi

- **Bahasa**: Kotlin (100% Native)
- **UI Framework**: Jetpack Compose + Material 3
- **Design Theme**: Cyberpunk / Bloomberg Terminal Style (Dark Navy `#070B12`, Neon Green `#00E676`, Neon Red `#FF1744`, Neon Cyan `#00E5FF`, Neon Amber `#FFB300`, Gold Accent `#FFD700`)
- **Arsitektur**: Clean Architecture / MVVM + Coroutines StateFlow
- **Networking**: Retrofit 2 + OkHttp 4 (Resilient Timeout, Auto Reconnecting & Retry)
- **Background Resilience**: Persistent Foreground Service + WakeLock + Battery Optimization Exemption

---

## 🌐 Sumber Data & Interval Polling

| Endpoint | Interval | Data yang Dikelola |
|---|---|---|
| `GET /sultan_status.json` | ~1.000 ms (1 detik) | Harga live XAUUSD, Regime multi-timeframe, Order flow (CVD, delta), Likuiditas wall (bid/ask ladders), Conviction score, Sinyal & Bar timers. |
| `GET /news_feed.json` | ~60 detik | Berita Kitco (ID), Tone sentiment, AI Analysis dengan highlight `[[level]]`, Confluence chips. |
| `GET /ff_calendar.json` | ~60 detik | Kalender ekonomi Forex Factory (USD/Gold) dengan filter impact dan countdown menit. |
| `GET /api/system_health` | ~5 detik | CPU %, RAM %, dan Disk % dari Mini-PC yang menjalankan backend MT5/Python. |

---

## 🧭 Struktur Navigasi & Fitur

1. **COMMAND (Tab 1)**:
   - Live Price Header dengan flash animasi pergerakan tick (Green Up / Red Down).
   - Primary Action Hero Banner (`WAIT_OBSERVE` / `BUY` / `SELL`).
   - Countdown Timers untuk M1, M5, M15, M30, H1, H4.
   - Conviction Matrix Card (Score, Grade, Chain Done vs Next, Against factors).
   - Order Flow & Momentum Pulse (CVD, Delta 1m, Buy Vol %).
   - Nearest Liquidity Wall (Distance, Lot, Wall Imbalance).
   - **Market Overview Card (Option A)**: Expandable Card untuk POC, VAH, VAL, ATR(14), 24H Range Distance, dan DXY Context.
   - **Commander Mode (Minimal HUD)**: Fullscreen minimal mode yang dapat di-toggle dari Top Bar untuk ditaruh di meja trading.

2. **BOOKMAP (Tab 2)**:
   - Order Flow Bookmap Read (Wall ratio, CVD, Absorption, Iceberg detection, Verdict).
   - Live Wall Sweep Alert Banner.
   - Liquidity Imbalance Gauge & Total Lot meter.
   - Bid & Ask Order Book Depth Ladder table dengan visualisasi ketebalan lot.

3. **CHAIN (Tab 3)**:
   - **S&D Zones Engine & Momentum Break (v1.5.0)**: Live Supply/Demand wall roadmap (S1..S2, D1..D2) dengan lot, kekuatan, status (AUS/AKTIF/DIUJI), hit serap order-flow, Buyer/Seller control %, serta Break Status engine.
   - Timeframe Regime Matrix (D1, H4, H1, M30, M15, M5, M1) + Alignment %.
   - Chain Progression Tracker & Layer status.
   - Momentum Triad (M5 Core EA, Bookmap Momentum, Footprint Momentum).
   - Barriers, IVB Locked Status & Volume Node confluences.

4. **NEWS (Tab 4)**:
   - AI Market Analysis Card dengan marker `[[level]]` yang di-highlight + **Disclaimer finansial permanen**: *"⚠️ Bukan saran finansial — keputusan & risiko di tangan Anda."*
   - News Sentiment Conclusion (Bullish/Bearish/Neutral counts).
   - List berita berbahasa Indonesia lengkap dengan Confluence key levels chips.
   - Economic Calendar (Forex Factory) dengan filter High/Medium/Low impact.
   - **News Detail Sub-screen**: Membuka artikel penuh, level konfluensi, related value area levels, dan tombol buka link sumber asli.

5. **SYSTEM (Tab 5)**:
   - Backend Server PC Health (CPU %, RAM %, Disk % gauges).
   - Data Bridge Latency & Bookmap Online status.
   - Account Capital Metrics (Balance, Equity, Floating P&L).
   - 24/7 Keep-Alive Controls: Switch Foreground Service & Tombol izin Abaikan Optimasi Baterai.

---

## 🚀 Cara Build & Menjalankan

Silakan baca file panduan lengkap di:
👉 [`BUILD_GUIDE.md`](file:///d:/ChainReactionAndroidApp/BUILD_GUIDE.md)
