<div align="center">

```
 ██████╗██╗  ██╗ █████╗ ██╗███╗   ██╗    ██████╗ ███████╗ █████╗  ██████╗████████╗██╗ ██████╗ ███╗   ██╗
██╔════╝██║  ██║██╔══██╗██║████╗  ██║    ██╔══██╗██╔════╝██╔══██╗██╔════╝╚══██╔══╝██║██╔═══██╗████╗  ██║
██║     ███████║███████║██║██╔██╗ ██║    ██████╔╝█████╗  ███████║██║        ██║   ██║██║   ██║██╔██╗ ██║
██║     ██╔══██║██╔══██║██║██║╚██╗██║    ██╔══██╗██╔══╝  ██╔══██║██║        ██║   ██║██║   ██║██║╚██╗██║
╚██████╗██║  ██║██║  ██║██║██║ ╚████║    ██║  ██║███████╗██║  ██║╚██████╗   ██║   ██║╚██████╔╝██║ ╚████║
 ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
```

# Sultan Sniper Engine
### Chain Reaction v4.0 OVERLORD

**Sistem trading berbasis Price Action murni — CMP → VR → CF**

*Diciptakan oleh Commander Dadang Wahyuono*

---

![Version](https://img.shields.io/badge/version-4.0_OVERLORD-gold?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-Windows-blue?style=for-the-badge&logo=windows)
![AI](https://img.shields.io/badge/AI-Claude_Sonnet-purple?style=for-the-badge&logo=anthropic)
![Stack](https://img.shields.io/badge/stack-Next.js_%2B_Python_%2B_MT5-black?style=for-the-badge)
![License](https://img.shields.io/badge/license-Private-red?style=for-the-badge)

</div>

---

## Tentang Sistem Ini

**Sultan Sniper Engine** adalah ekosistem trading otomatis yang menggabungkan doktrin price action murni dengan kecerdasan buatan. Tidak ada Fibonacci, tidak ada EMA, tidak ada indikator eksternal — hanya **CMP, VR, dan CF**.

Sistem ini terdiri dari:

- 🧠 **AI Trading Advisor** — Web dashboard real-time yang membaca TradingView, menganalisis storyline fractal, dan memberikan rekomendasi entry
- 🤖 **AI Learning Loop** — AI paper trader yang belajar dari setiap trade dan makin pintar seiring waktu
- ⚡ **Python Engine + MT5** — Deteksi CMP/VR/CF di semua timeframe dan eksekusi order otomatis
- 📊 **TradingView Integration** — Sinkronisasi live dengan indikator custom via Chrome DevTools Protocol

---

## Doktrin: Chain Reaction

> *"Market hanya muter-muter. Selama lo tau storyline-nya, lo akan selamat."* — Commander Dadang

### Siklus Fundamental

```
CMP ──────► VR ──────► CF ──────► ENTRY
 │           │           │
 │           │           └─ Breakout SEARAH setelah VR
 │           │              Bisa berkali-kali = multi-entry
 │           └─ Breakout BERLAWANAN pertama di TF 1 level bawah
 │              Hanya SEKALI per siklus
 └─ Candle CLOSE melampaui Minor SNR
    Wicks diabaikan — body only
```

### Hierarki Timeframe

```
  Daily  ──► context & bias jangka panjang
    │
    H4   ──► master direction (referensi utama)
    │
    H1   ──► VR monitor untuk H4
    │
    M30  ──► entry zone utama
    │
    M15  ──► konfirmasi & fine-tune
    │
    M5   ──► trigger terkecil yang valid (M1 = noise, tidak dipakai)
```

### TP Rules — Baku & Pasti Sampai

| Entry CF di | TP Target Area |
|:-----------:|:--------------:|
| M5          | SNR M15        |
| M15         | SNR M30        |
| M30         | SNR H1         |
| H1          | SNR H4         |
| H4          | SNR Daily      |

### VR = CMP Baru (Doktrin Lanjutan)

Setiap TF yang sedang VR ke parent-nya **adalah CMP baru di level TF-nya sendiri**. Ini membuka peluang scalp di arah VR sambil menunggu setup utama selesai.

```
H4 BUY aktif + H1 VR (SELL)
  └─ H1 SELL = CMP baru untuk scalp
     Syarat: M30 belum VR BUY (M30 masih SELL = CONTI)
     Entry:  M15 SELL → M5 VR BUY → M5 CF SELL → MASUK
     TP:     SNR M30 (CF M15) atau SNR M15 (CF M5)
     Stop:   M30 VR BUY terjadi → H1 mau CF BUY → hentikan scalp SELL
```

---

## Arsitektur

```
Sultan Sniper Engine
│
├── 🌐 sultan-advisor/              Web Dashboard (Next.js 16 + TypeScript)
│   ├── app/
│   │   ├── dashboard/              Dashboard utama — chain rail, VR scalp, SNR ladder
│   │   ├── paper-trading/          Paper trading — Engine vs AI performance
│   │   ├── journal/                Jurnal trade
│   │   └── api/
│   │       ├── tv-sync/            Baca TradingView via CDP port 9222
│   │       ├── chat/               AI streaming chat (Claude Sonnet)
│   │       ├── paper/              Paper trading CRUD + akuntansi R-multiple
│   │       └── paper/ai-decide/    AI judge otomatis: ENTER atau SKIP?
│   ├── components/
│   │   ├── dashboard-pro.tsx       Dashboard visual premium
│   │   └── market-panel.tsx        Sidebar: sync, autopilot, heatmap, VR scalp
│   └── lib/system-prompt.ts        Doktrin Chain Reaction → injected ke AI context
│
├── 🐍 engine/                      Python Trading Engine
│   ├── core.py                     SacredDoctrineAnalyst — CMP/VR/CF detection
│   ├── executor.py                 ChainReactionExecutor — order ke MT5
│   └── connection.py               MT5 connection helper
│
├── 📡 tradingview-mcp-jackson/     TradingView CDP Bridge
│   ├── read_indicators.mjs         Baca CMP Engine v6.3 + DD Marker dashboard
│   └── fundamental_snr.mjs         PDH/PDL/round numbers dari chart
│
├── 📈 backtest/                    Historical replay engine
├── 🌲 DD_CMP_Marker.v5.pine        Indikator TradingView (Pine Script referensi)
├── 🚀 START TRADING.ps1            Launcher — satu klik start semua komponen
└── ⚙️  INSTALL.ps1                  Setup wizard untuk PC/laptop baru
```

---

## Paper Trading: Engine vs AI Learning

Sistem menjalankan **2 akun paper trading secara paralel dan otomatis** — tanpa intervensi user.

| | Engine Account | AI Account |
|---|---|---|
| **Cara kerja** | Masuk setiap CF fire | Evaluasi setiap CF, decide sendiri |
| **Filter** | Tidak ada — murni doktrin | Grade A/B = ENTER · Grade C = SKIP |
| **Tujuan** | Benchmark akurasi doktrin | Training AI jadi master trader |
| **Saldo awal** | Rp 10.000.000 | Rp 10.000.000 |
| **Risk/trade** | 1R = Rp 100.000 | 1R = Rp 100.000 |

### AI Learning Loop

```
CF Fire
  ├─ Baca 5 memori trade terakhir dari DB
  ├─ Lihat performa W/L/R terkini
  ├─ Evaluasi setup (searah H4? spread? news? grade?)
  └─ ENTER atau SKIP + alasan tertulis
           │
           ▼  (setelah trade tutup: SL/TP hit)
  ├─ Claude refleksi: mengapa WIN atau LOSS?
  ├─ Deteksi pola dari riwayat
  ├─ Simpan lesson → memories table (persistent)
  └─ Trade berikutnya → AI pakai semua lesson ini
```

> Makin banyak trade → memori makin kaya → keputusan makin tajam. Doktrin Dadang didrilled ke AI sampai level master.

---

## Web Dashboard

### Fitur Utama

| Panel | Fungsi |
|-------|--------|
| **Chain Rail** | Visualisasi status CMP/VR/CF semua TF secara real-time |
| **VR Scalp** | Setup scalp valid di arah VR + guard condition check |
| **Storyline & Conti** | Jalan cerita fractal + peluang CONTI entry |
| **SNR Price Ladder** | PDH/PDL/PWH/PWL/Round number dengan proximity alert |
| **Tekanan Pasar** | Tick delta buy/sell pressure + mini chart 8 bar |
| **Paper Performance** | Engine vs AI: winrate, total R, saldo real-time |
| **AI Chat** | Analisis setup, trade plan, upload chart screenshot |
| **News Blackout** | Countdown event high-impact USD, auto-alert |
| **Telegram Alert** | CF/VR fire → notifikasi HP dalam detik |

### Auto-Sync & Autopilot

- Auto-sync TradingView setiap **30 detik** di background
- **Autopilot selalu ON** — tidak perlu klik apa-apa
- CF terdeteksi → Engine masuk + AI evaluate → alert toast + beep + Telegram
- SL/TP hit → trade tutup otomatis + AI tulis lesson ke memory

---

## Instalasi

### Prasyarat

| Software | Link | Keterangan |
|----------|------|-----------|
| Node.js LTS v18+ | [nodejs.org](https://nodejs.org) | **Wajib** |
| Git | [git-scm.com](https://git-scm.com) | **Wajib** |
| TradingView Desktop | [Microsoft Store](https://apps.microsoft.com) | Untuk CDP sync |
| MetaTrader 5 | Dari broker | Untuk live Python engine |
| cloudflared | Auto-install via INSTALL.ps1 | Untuk tunnel HTTPS |

### Setup Otomatis — Satu Script

```powershell
# 1. Buka PowerShell sebagai Administrator

# 2. Izinkan script execution
Set-ExecutionPolicy Bypass -Scope Process

# 3. Clone repo
git clone https://github.com/dadangwahyuono-eng/Sultan-Sniper-Engine.git "D:\PROJECT TRADING"

# 4. Masuk ke folder
cd "D:\PROJECT TRADING"

# 5. Jalankan installer — ikuti instruksinya
.\INSTALL.ps1
```

**`INSTALL.ps1` menangani:**
- ✅ Cek Node.js & Git
- ✅ Clone atau update repo
- ✅ Buka `.env.local` di Notepad untuk diisi API keys
- ✅ `npm install --include=dev` (install semua dependencies)
- ✅ `npx next build` (build production)
- ✅ Install & setup Cloudflare tunnel
- ✅ Buat shortcut `START TRADING` di Desktop

### Environment Variables

Buat file `sultan-advisor/.env.local` dari template `.env.example`:

```env
# ── WAJIB ────────────────────────────────────────────────
BLUEPACK_API_KEY=your_api_key          # dari ai.bluepack.my.id
BLUEPACK_BASE_URL=https://ai.bluepack.my.id/v1
BLUEPACK_MODEL=claude-3-5-haiku-20241022

BETTER_AUTH_SECRET=random_string_min_32_chars
BETTER_AUTH_URL=http://localhost:3002
DATABASE_URL=./sultan.db

# ── OPSIONAL ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=        # notifikasi HP saat CF/VR fire
TELEGRAM_CHAT_ID=          # dari @BotFather Telegram
FRED_API_KEY=              # US Treasury yield (fred.stlouisfed.org)
LLM_BASE_URL=http://localhost:8080/v1  # local LLM (Qwen3-8B)
```

### Cloudflare Tunnel

**Cara termudah — copy dari PC lain:**
```
Salin folder: C:\Users\<username>\.cloudflared\
ke laptop baru di path yang sama.
```

**Atau setup baru:**
```powershell
cloudflared tunnel login
cloudflared tunnel create sultan-sniper
cloudflared tunnel route dns sultan-sniper yourdomain.com
```

### Start Trading

```
Double-click  →  "START TRADING"  di Desktop
```

Sistem otomatis start: TradingView CDP → Web UI → Cloudflare tunnel → buka browser.

---

## Update ke Versi Terbaru

```powershell
cd "D:\PROJECT TRADING"
.\INSTALL.ps1
# Otomatis: git pull + npm install + rebuild
```

---

## Tech Stack

<div align="center">

| Layer | Teknologi |
|:-----:|:---------:|
| Frontend | Next.js 16 · TypeScript · Tailwind CSS |
| AI | Claude Sonnet (Bluepack) · AI SDK v4 |
| Database | SQLite · Drizzle ORM |
| Auth | Better Auth |
| TradingView | Chrome DevTools Protocol (CDP) |
| Engine | Python 3.11 · MetaTrader5 · pandas |
| Tunnel | Cloudflare Tunnel |
| Notifications | Telegram Bot API |

</div>

---

## Branch Strategy

```
master                          ← Production — selalu stabil
feat/tv-python-integration      ← Development aktif
fix/xxx                         ← Bug fixes
```

> Setiap perubahan logic engine di-backtest dulu sebelum merge ke master.

---

<div align="center">

## Disclaimer

*Sistem ini digunakan untuk edukasi, riset, dan paper trading.*
*Tidak ada eksekusi dengan uang nyata tanpa persetujuan eksplisit Commander.*
*Pahami risiko trading sebelum menggunakan sistem ini dengan dana nyata.*

---

**Sultan Sniper Engine** — Chain Reaction v4.0 OVERLORD

*Doktrin diciptakan oleh Commander Dadang Wahyuono*
*Dibangun dengan Claude Code · Anthropic*

</div>
