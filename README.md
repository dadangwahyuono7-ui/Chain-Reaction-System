# Sultan Sniper Engine
### Chain Reaction v4.0 OVERLORD

> Sistem trading otomatis berbasis doktrin **CMP → VR → CF** yang dikembangkan oleh **Commander Dadang Wahyuono** untuk instrumen XAUUSD CFD dan multi-instrumen lainnya.

---

## Apa Ini?

Sultan Sniper Engine adalah ekosistem trading yang menggabungkan:

- **Doktrin Price Action murni** — CMP, VR, CF. Tanpa Fibonacci, EMA, atau indikator eksternal apapun.
- **AI Trading Advisor** — web dashboard berbasis Claude AI yang membaca TradingView secara real-time, analisis storyline fractal, dan eksekusi paper trading otomatis.
- **AI Learning Loop** — AI akun paper trading yang belajar dari setiap trade: masuk → evaluasi → refleksi → simpan lesson → keputusan makin tajam.
- **Engine Python + MT5** — deteksi CMP/VR/CF di semua timeframe, eksekusi order otomatis.

---

## Konsep Inti: Doktrin Chain Reaction

```
Siklus per TF:  CMP → VR → CF → ENTRY

CMP  = Candle CLOSE melampaui Minor SNR (bukan wick)
VR   = Breakout BERLAWANAN pertama di TF 1 level bawah. Hanya SEKALI per siklus.
CF   = Breakout SEARAH kembali setelah VR. Bisa berkali-kali. = Trigger entry.
```

**Hierarki Timeframe:**
```
Daily → H4 → H1 → M30 → M15 → M5
```

**TP Rules (baku):**
| CF Entry TF | TP Target |
|-------------|-----------|
| CF M5       | SNR M15   |
| CF M15      | SNR M30   |
| CF M30      | SNR H1    |
| CF H1       | SNR H4    |
| CF H4       | SNR Daily |

**Doktrin lanjutan — VR = CMP baru:**
> Ketika H4 BUY dan H1 sedang VR (SELL), H1 VR bisa dijadikan CMP SELL baru. Scalp SELL valid selama M30 belum VR BUY. Ini membuka setup scalp sambil menunggu setup utama H4 selesai.

---

## Arsitektur Sistem

```
Sultan Sniper Engine
├── sultan-advisor/          ← Web Dashboard (Next.js + AI)
│   ├── app/
│   │   ├── dashboard/       ← Dashboard utama
│   │   ├── paper-trading/   ← Halaman paper trading
│   │   ├── journal/         ← Jurnal trade
│   │   └── api/
│   │       ├── tv-sync/     ← Baca TradingView via CDP
│   │       ├── chat/        ← AI streaming chat (Claude)
│   │       ├── paper/       ← Paper trading API
│   │       └── paper/ai-decide/ ← AI judge: ENTER atau SKIP?
│   ├── components/
│   │   ├── dashboard-pro.tsx    ← Dashboard visual utama
│   │   ├── market-panel.tsx     ← Panel sync + autopilot
│   │   └── ...
│   └── lib/
│       └── system-prompt.ts ← Doktrin Chain Reaction untuk AI
│
├── engine/                  ← Python Engine (MT5 + CMP/VR/CF)
│   ├── core.py              ← SacredDoctrineAnalyst, CMPDetector
│   ├── executor.py          ← Order execution ke MT5
│   └── connection.py        ← MT5 connection
│
├── tradingview-mcp-jackson/ ← TradingView CDP integration
│   ├── read_indicators.mjs  ← Baca CMP Engine + DD Marker
│   └── fundamental_snr.mjs  ← PDH/PDL/Round numbers
│
├── backtest/                ← Historical replay engine
├── DD_CMP_Marker.v5.pine    ← Indikator TradingView (referensi)
├── START TRADING.ps1        ← Launcher semua komponen
└── INSTALL.ps1              ← Setup otomatis PC/laptop baru
```

---

## Paper Trading: Engine vs AI Learning

Sistem memiliki **2 akun paper trading** yang berjalan paralel:

| Akun | Cara Kerja | Tujuan |
|------|-----------|--------|
| **Engine** | Masuk setiap CF fire — murni doktrin, no filter | Benchmark keakuratan doktrin |
| **AI** | Evaluasi setiap CF — ENTER atau SKIP pakai Claude | Training AI jadi master trader |

**AI Learning Loop:**
```
CF Fire
  └─ AI baca memori trade sebelumnya
  └─ Evaluasi setup (searah H4? spread? news blackout?)
  └─ ENTER / SKIP + alasan
       ↓ (setelah trade tutup: SL/TP hit)
  └─ Claude refleksi: kenapa WIN/LOSS?
  └─ Simpan lesson ke memories table
  └─ Trade berikutnya → AI pakai lesson ini
```

Semakin banyak trade → AI makin kaya pengalaman → keputusan makin tajam.

---

## Web Dashboard Features

- **Chain Rail** — visualisasi CMP/VR/CF tiap TF real-time dari TradingView
- **VR Scalp Panel** — deteksi setup scalp di arah VR sambil nunggu setup utama
- **Storyline & CONTI** — baca jalan cerita fractal per TF
- **SNR Price Ladder** — level PDH/PDL/PWH/PWL/Round Number
- **Alert System** — CF/VR fire → toast + beep + Telegram notification
- **Paper Performance** — Engine vs AI: winrate, total R, saldo
- **AI Chat** — tanya analisis, minta trade plan, upload screenshot chart

---

## Instalasi

### Prasyarat
- Windows 10/11
- [Node.js LTS](https://nodejs.org) (v18+)
- [Git](https://git-scm.com)
- TradingView Desktop App
- MetaTrader 5 (untuk live engine Python)

### Setup Otomatis (PC/Laptop Baru)

```powershell
# Buka PowerShell sebagai Administrator
Set-ExecutionPolicy Bypass -Scope Process

# Clone repo
git clone https://github.com/dadangwahyuono-eng/Sultan-Sniper-Engine.git "D:\PROJECT TRADING"
cd "D:\PROJECT TRADING"

# Jalankan installer
.\INSTALL.ps1
```

Script `INSTALL.ps1` otomatis:
1. Cek Node.js & Git
2. Clone/update repo
3. Tanya isi `.env.local` (API keys)
4. `npm install --include=dev`
5. `npx next build`
6. Setup Cloudflare tunnel
7. Buat shortcut `START TRADING` di Desktop

### Environment Variables

Copy `.env.example` → `.env.local` di folder `sultan-advisor/`, lalu isi:

```env
# WAJIB — API untuk AI trading advisor
BLUEPACK_API_KEY=your_key_here
BLUEPACK_BASE_URL=https://ai.bluepack.my.id/v1
BLUEPACK_MODEL=claude-3-5-haiku-20241022

# WAJIB — Auth secret (string random panjang)
BETTER_AUTH_SECRET=random_string_min_32_chars
BETTER_AUTH_URL=http://localhost:3002

# Opsional — Telegram notifikasi HP
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Opsional — Local LLM (Qwen3-8B via llama.cpp)
LLM_API_KEY=local
LLM_BASE_URL=http://localhost:8080/v1
```

### Cloudflare Tunnel (akses dari luar)

**Copy dari PC lain (mudah):**
Salin folder `C:\Users\<username>\.cloudflared\` dari PC yang sudah setup ke PC baru.

**Setup baru:**
```powershell
cloudflared tunnel login
cloudflared tunnel create sultan-sniper
cloudflared tunnel route dns sultan-sniper yourdomain.com
```

### Jalankan

Setelah setup selesai, setiap kali trading:
```
Double-click "START TRADING" di Desktop
```

Atau manual:
```powershell
cd "D:\PROJECT TRADING"
.\START TRADING.ps1
```

---

## Cara Update

Setiap kali ada perubahan terbaru di repo:

```powershell
cd "D:\PROJECT TRADING"
.\INSTALL.ps1
# Script otomatis git pull + rebuild
```

---

## Teknologi

| Layer | Stack |
|-------|-------|
| Web Dashboard | Next.js 16, TypeScript, Tailwind CSS |
| AI | Claude (via Bluepack API), AI SDK v4 |
| Database | SQLite + Drizzle ORM |
| Auth | Better Auth |
| TradingView | Chrome DevTools Protocol (CDP port 9222) |
| Engine | Python 3.11, MetaTrader5, pandas |
| Tunnel | Cloudflare Tunnel |

---

## Struktur Branch

```
master                  ← production, selalu stabil
feat/tv-python-integration ← development aktif
```

---

## Disclaimer

> Sistem ini digunakan untuk edukasi dan riset trading. Paper trading tidak menggunakan uang nyata. Gunakan dengan bijak dan pahami risikonya sebelum trading dengan dana nyata.

---

*Dikembangkan oleh Commander Dadang Wahyuono — doktrin Chain Reaction.*
