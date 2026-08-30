# CLAUDE.md — Sultan Sniper Engine
**Owner:** Dadang Wahyuono (Commander Dadang)  
**Instrument:** XAUUSD CFD  
**Engine:** Chain Reaction v4.0 OVERLORD

---

## 🗺️ TOPOLOGI EKOSISTEM (BACA DULUAN)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Mini PC "WIN-JIOIHRD7BB1" (100.71.97.6) — TOWER SERVER 24/7             │
│  • Bookmap 7.4 + Rithmic CME GC + Python UDP Ingest (port 9000)         │
│  • Web produksi LIVE: http://100.71.97.6:8766/                          │
│    Source: C:\bookmap-bridge-v1\ di Mini PC (bukan folder polos          │
│    bookmap-bridge\ — itu versi lama/berbeda, lihat SND_ZONE_ENGINE_...) │
│  • trades.db di sana = histori EKSEKUSI MT5 DEMO ASLI (udp_listener.py  │
│    + mt5_bridge_executor.py), BUKAN paper-trading simulasi software     │
├─────────────────────────────────────────────────────────────────────────┤
│ PC ROVA (100.115.192.70) — workstation dev, root "D:\PROJECT TRADING"   │
│  Deploy web ke Mini PC: edit lokal → scp ke index.html + dashboard.html │
│  di sultan/ (harus identik) → cp balik ke repo lokal → verify via       │
│  browser dengan ?_cachebust=N (caching agresif tanpa itu)               │
└─────────────────────────────────────────────────────────────────────────┘
```

**⚠️ Antigravity (AI lain) kerja PARALEL di `D:\ChainReactionAndroidApp\`** —
sandbox-nya sendiri (`ChainLocal`, port 8899), EA MT5 "V3" sendiri (beda dari
EA V2 kita di sini), dan startup-protocol MD sendiri (`AGENTS.md`,
`.agents\rules\MANDATORY_STARTUP_MAP.md`, `PROJECT_MASTER_MAP_COMMANDER_
DADANG.md`). Dokumen DOKTRIN di folder itu (lihat tabel referensi di bawah)
tetap dianggap rujukan sah — itu doktrin trading Commander Dadang, bukan
punya Antigravity — tapi jangan sentuh kode/sandbox Antigravity di folder
itu tanpa diminta eksplisit, dan jangan bingung EA "V3" dengan EA V2 kita.

---

## BACA INI DULU SEBELUM MULAI

Setiap session baru, jalankan ini untuk cek kondisi market:
```powershell
# 1. Pastikan TradingView sudah jalan dengan CDP
$exe = (Get-AppxPackage *TradingView*).InstallLocation + "\TradingView.exe"
Start-Process $exe -ArgumentList "--remote-debugging-port=9222"

# 2. Baca dashboard TradingView
cd "D:\PROJECT TRADING\tradingview-mcp-jackson"
node read_indicators.mjs

# 3. Jalankan engine check
cd "D:\PROJECT TRADING"
venv\Scripts\python.exe -c "
from engine.connection import connect_mt5
from engine.core import SacredDoctrineAnalyst, DailyDeployAnalyst
import MetaTrader5 as mt5
if connect_mt5():
    a = SacredDoctrineAnalyst('XAUUSD', master_tf='H4')
    d = DailyDeployAnalyst('XAUUSD')
    a.update(); d.update(a)
    for n in ['D1','H4','H1','M30','M15','M5']:
        st = a.states[n]
        print(f'{n}: CMP={st.cmp} SUP={st.sup:.2f} RES={st.res:.2f}')
    print('DD:', [(s['layer'],s['type'],s['action']) for s in d.active_signals])
    mt5.shutdown()
"
```

---

## DOKTRIN DAILY DEPLOY — REFERENSI CEPAT

**Siklus per TF:** `CMP → VR → CF → ENTRI`

| Istilah | Definisi |
|---------|----------|
| **CMP** | Candle CLOSE melampaui minor SNR (bukan wick). Paling kanan = aktif. |
| **VR** | Breakout BERLAWANAN pertama di TF 1 level bawah. Hanya SEKALI per siklus. |
| **CF** | Breakout SEARAH kembali setelah VR. Trigger entry. Bisa berkali-kali. |
| **Minor SNR** | V-shape (prev bearish + curr bullish) = support. A-shape = resistance. |

**Hierarki VR:**

| Setup TF | VR terjadi di |
|----------|--------------|
| H4 | H1 |
| H1 | M30 |
| M30 | M15 |
| M15 | M5 |

**H1 belum VR → scalp 10-30 pts. H1 sudah VR → gerakan 50-150 pts.**

**Dua Hukum Absolut:**
1. VR = satu-satunya yang gagalkan CMP
2. CF = satu-satunya yang lanjutkan CMP
- SL kena ≠ setup gagal. Gagal HANYA kalau CMP flip.

**JANGAN:** Fibonacci, pivot standar, EMA/SMA, atau framework eksternal apapun.

---

## ARSITEKTUR ENGINE

```
main.py
├── SacredDoctrineAnalyst     → CMP/VR/CF detection per TF, H4 sebagai master
│   ├── get_strike_signal()   → Chain signals: MINOR_CF, CF_LOW, CF_HIGH, H4_CF_HIGH
│   └── get_chain_status()    → Status lengkap untuk dashboard
├── DailyDeployAnalyst        → Multi-layer: D1_DEPLOY, H4_DEPLOY, H1_DEPLOY
│   ├── get_best_signal()     → Prioritas: CF_LOW > CF_HIGH > CONTI
│   └── get_layer_summary()   → Status tiap layer untuk UI
└── ChainReactionExecutor     → Guard checks + order execution
    ├── check_barrier_guard() → Veto jika > barrier_limit USD dari master barrier
    ├── check_session_and_spread()
    ├── check_news_blackout()
    └── execute_strike()      → Send order ke MT5

engine/
├── core.py      → CMPDetector, TFState, SacredDoctrineAnalyst, DailyDeployAnalyst
├── executor.py  → ChainReactionExecutor
└── connection.py → connect_mt5()

backtest/
├── backtest.py  → Historical replay engine (pakai TFState & CMPDetector saja)
└── run.py       → Konfigurasi dan entry point backtest

tradingview-mcp-jackson/   → TradingView integration via CDP port 9222
├── read_indicators.mjs    → Baca CMP Engine + DD CMP Marker dashboard
├── fundamental_snr.mjs    → Harga + PDH/PDL/Daily Open + TP suggestion
└── draw_snr_global.mjs    → Gambar SNR di chart
```

**chain_settings.json — config runtime:**
```json
{
  "auto_trade": true,       // false = monitor only, true = execute otomatis
  "lot_size": 0.01,
  "max_layers": 3,          // max posisi bersamaan
  "barrier_limit": 3.5,     // USD — veto jika terlalu jauh dari master barrier
  "be_protect_pips": 10.0,  // pips profit sebelum SL geser ke BEP
  "news_blackout_minutes": 15
}
```

---

## SIGNAL TYPES

### Chain Reaction (SacredDoctrineAnalyst)

| Signal | Kondisi | SL | TP |
|--------|---------|----|----|
| `MINOR_CF` | M30+M15 solid + M5 VR→CF | M5 | M15 |
| `CF_LOW` | M30 solid + M15 VR→CF | M15 | M30 |
| `CF_HIGH` | M30 solid + M15 VR + M5 CF | M15 | M30 |
| `H4_CF_HIGH` | H1 VR + M30 CF | H1 | H4 |

### Daily Deploy (DailyDeployAnalyst)

| Layer | Signal | SL | TP |
|-------|--------|----|----|
| `H1_DEPLOY` | `CF_LOW` | M30 | H1 |
| `H1_DEPLOY` | `CF_HIGH` | M30 | M30 |
| `H4_DEPLOY` | `CF_LOW` | H1 | H4 |
| `H4_DEPLOY` | `CF_HIGH` | H1 | H1 |
| `D1_DEPLOY` | `CF_LOW` | H4 | D1 |

**CONTI signals TIDAK dieksekusi** — terlalu berisiko tanpa VR terjadi dulu.

---

## WEB DASHBOARD — SULTAN CHART TERMINAL (Mini PC :8766)

Single-page app, satu file besar: `bookmap-bridge-v1/sultan/index.html`
(HTML+CSS+JS inline). `dashboard.html` di folder yang sama harus SELALU
byte-identik (dua nama, satu isi).

**Deploy pipeline (wajib diikuti tiap kali edit):**
```powershell
# 1. Verify syntax dulu sebelum deploy (extract <script> lalu parse pakai acorn)
node acorncheck.js extracted.js   # "Parsed OK" baru lanjut

# 2. scp ke KEDUA nama file di Mini PC
scp -i <ssh-key> index.html Administrator@100.71.97.6:C:/bookmap-bridge-v1/sultan/index.html
scp -i <ssh-key> index.html Administrator@100.71.97.6:C:/bookmap-bridge-v1/sultan/dashboard.html

# 3. Sync balik ke repo lokal
cp index.html "D:\PROJECT TRADING\bookmap-bridge-v1\sultan\index.html"

# 4. Verify LIVE via browser dengan cachebust (?_cachebust=N, N naik tiap kali)
```

**Fitur inti yang sudah jalan (per tab):**
- **DASHBOARD** — chart utama (Lightweight Charts v4.2), EMA/VWAP/POC/MAKER/
  ABS/Momentum(volume-delta bar)/MTF/ICE overlay toggle, alat gambar
  (trendline dkk, nama inline-editable, lock/unlock per-gambar, snap ke
  candle asli), grid layout switcher, fullscreen focus mode.
- **CMP ENGINE / MULTI TIMEFRAME** — `CMPMasterEngine` (port dari kode
  Python referensi Commander Dadang): hierarki H4→H1→M30→M15→M5, role
  CO_TIMESTAMP_ROOT/CF_CONFIRMATION/VR_RETRACEMENT/HISTORICAL_TP, data dari
  `/api/chart/history` (candle asli, bukan tf_matrix live yang cuma
  snapshot). Shared cache `latestCmpEngine`, dipakai juga oleh tabel Multi
  Timeframe & panel Dashboard — SATU sumber kebenaran, jangan pecah lagi.
- **WALL ANALYSIS** — wall ladder + persistence (age) dari `wall_ladder`.
- **NEWS & EVENT** — **real**, bukan placeholder: kalender ForexFactory
  (`/ff_calendar.json`) + berita Kitco (`/news_feed.json`, ada `ai_analysis`
  hasil LLM beneran dari `news_engine.py`) + terjemahan Indonesia + highlight
  zona pantau. Kedua JSON ditulis langsung oleh `news_engine.py` di Mini PC,
  fetch langsung dari web (same-origin, gak perlu proxy).
- **SYSTEM STATUS → AKUN (MT5 DEMO)** — histori EKSEKUSI MT5 DEMO ASLI, dari
  `trade_db.py`/`trades.db` di Mini PC (via `udp_listener.py` +
  `mt5_bridge_executor.py`). **BEDA** dari Web Paper Trading di bawah.
- **SYSTEM STATUS → 🧪 WEB PAPER TRADING** — simulasi paper trading yang
  jalan MURNI di browser (localStorage, key `chainReactionWebPaperTrades_v1`),
  gak butuh MT5 connect. Logic dari `DOKTRIN_ENTRY_CHAIN_REACTION_MASTER.md`
  (lihat tabel referensi) — 4 skenario entry + 3 veto S&D + lot sizing +
  split TP 50:50. **Keterbatasan yang disadari**: footprint per-harga
  (`footprint_engine.py` di Mini PC) belum ke-expose ke `/api/status`, jadi
  Skenario 2 (Sniper Sweep) pakai Absorption+CVD-divergence sebagai proxy;
  Naked POC pakai POC biasa (bukan tracking "belum pernah disentuh"); Veto
  Compression pakai jarak wall terdekat (bukan zona S&D beneran, gak ada
  zone-engine di backend). Kalau mau upgrade presisi, itu perlu perubahan di
  backend Python Mini PC (`sultan_dashboard_server.py`/`udp_listener.py`),
  BUKAN sekadar edit index.html.

**Backend Python relevan (Mini PC, `C:\bookmap-bridge-v1\`)** — semuanya
LIVE, jangan disamakan dengan mirror lokal `C:\Bookmap\Python\` yang beda
nama file (contoh: Mini PC pakai `cr_master_engine.py`, lokal ada
`cr_master_engine_v2.py` — dua hal beda, mirror lokal itu stale):
- `sultan_dashboard_server.py` — file server pasif buat `/api/status`,
  `/api/chart/history`, static files. TIDAK menghitung apa-apa sendiri.
- `udp_listener.py` — orkestrator ASLI, panggil `CRDecisionRecommendationEngine.
  evaluate()` dari `cr_master_engine.py` tiap cycle, tulis hasil ke
  `live_status.json`/`sultan_status.json`, jalanin auto-execute MT5 real.
- `trade_db.py` — interface `trades.db` (SQLite): `log_entry`/`log_exit`/
  `get_recent_trades`/`get_stats`. Ini punya MT5 Demo, JANGAN dipakai buat
  Web Paper Trading (data harus tetap terpisah, lihat di atas).
- `footprint_engine.py` — per-price buy/sell dominance, SUDAH jalan/wired
  tapi datanya belum diteruskan ke JSON yang dibaca web.

---

## CARA MENJALANKAN

```powershell
# Live engine (dashboard + auto-trade)
cd "D:\PROJECT TRADING"
venv\Scripts\python.exe main.py

# Backtest
venv\Scripts\python.exe backtest\run.py

# Cek MT5 connection saja
venv\Scripts\python.exe engine\connection.py
```

---

## GIT WORKFLOW — WAJIB DIIKUTI

> **🔧 MAU TUNE-UP / UPGRADE AI LOCAL? BACA `TUNEUP_WORKFLOW.md` DULU.**
> Aturan inti: produksi (web port 3002 + llama.cpp :8080 → trade.dadangchatai.com)
> JANGAN disentuh saat ngoprek. Eksperimen di LAB terpisah: worktree
> `sultan-advisor-lab` (branch `feat/tune-up`) + web port 3003 + llama.cpp :8081.
> Port beda ≠ aman — isolasi sejati = folder worktree + instance llama.cpp ke-2.
> Promosi ke master HANYA setelah teruji di lab. Safety net: `git reset --hard origin/master`.

```
master       — production, selalu stabil
feat/xxx     — fitur baru
fix/xxx      — bug fix
refactor/xxx — refactoring tanpa behavior change
```

**Rules:**
1. **Jangan commit langsung ke `master`** untuk logic changes
2. Selalu buat feature branch → PR → merge
3. Commit message format: `type: deskripsi singkat`
   - `feat:` — fitur baru
   - `fix:` — bug fix
   - `refactor:` — restructuring tanpa behavior change
4. **Backtest dulu** sebelum merge perubahan logic CMP/VR/CF

```powershell
# Mulai fitur baru
git checkout -b feat/nama-fitur

# Selesai → push → PR
git push origin feat/nama-fitur
gh pr create --base master --head feat/nama-fitur
```

---

## BACKLOG — IMPROVEMENTS YANG SUDAH DIIDENTIFIKASI

### Priority 1 — Kritikal

- [ ] **M15 VR flag tidak reset** — engine.M15.vr_occurred=True dari siklus lama tidak di-reset ketika CMP baru terbentuk. Bisa bikin signal salah.
- [ ] **DD signals belum ditampilkan di SIGNAL.HEATMAP** — hanya ada di TARGET.ACQUISITION. Perlu tambah kolom atau panel terpisah.
- [ ] **Backtest untuk DailyDeployAnalyst** — `backtest.py` hanya test TFState & CMPDetector, belum test layer D1/H4/H1 DEPLOY.

### Priority 2 — Penting

- [ ] **Fundamental SNR integration** — PDH/PDL, PWH/PWL, round numbers belum di-cross-check di engine sebelum entry. Sekarang hanya di `fundamental_snr.mjs`.
- [ ] **VR dari siapa indicator** — engine belum tracking "VR datang dari M1/M5/M15" untuk grading kekuatan momentum.
- [ ] **Grade setup otomatis** — A+/A/B/C grading per doktrin belum diimplementasi di engine.

### Priority — Web Dashboard (bookmap-bridge-v1/sultan)

- [ ] **Web Paper Trading server-side sync** — sekarang localStorage doang (per-browser). Kalau Dadang mau state ikut di semua device, perlu endpoint JSON baru di `sultan_dashboard_server.py` (read-only file server, aman disentuh — beda dari `udp_listener.py` yang jalanin MT5 real).
- [ ] **Footprint per-harga belum ke-expose** — `footprint_engine.py` sudah jalan di Mini PC tapi datanya gak ikut ditulis ke `live_status.json`/`sultan_status.json`. Kalau mau Skenario 2 (Sniper Sweep) presisi penuh, ini prasyaratnya.
- [ ] **Gak ada S&D zone engine di backend** — Veto Compression/Runway saat ini pakai jarak wall terdekat sebagai proxy, bukan lebar zona S&D beneran.
- [ ] **Reports tab** masih placeholder "Coming Soon" — journal Paper Trading detail belum ada di sana.
- [ ] **Alerts tab** masih contoh statis (dilabeli jelas, bukan live) — belum ada backend event-log buat alert historis.

### Priority 3 — Nice to Have

- [ ] **DNA Vault logging** — `dna_vault.json` ada di architecture tapi belum diimplementasi.
- [ ] **News calendar otomatis** — sekarang manual di `news_schedule_wib`. Perlu fetch dari ekonomi kalender.
- [ ] **Multi-symbol support** — engine hanya XAUUSD. Bisa extend ke EURUSD, GBPUSD.
- [ ] **Web dashboard** — Next.js dashboard dari implementation_plan.md belum dimulai.
- [ ] **Telegram alert** — notifikasi ke HP ketika signal CF_LOW/CF_HIGH fire.

---

## ATURAN CODING

1. **Jangan ubah indikator TradingView user** — CMP Engine v6.3 dan DD CMP Marker adalah referensi. Engine Python harus mengikuti doktrin yang sama.
2. **Tidak ada Fibonacci, EMA, atau framework eksternal** — murni CMP/VR/CF.
3. **Time Law wajib dipertahankan** — child CMP time harus > parent CMP time.
4. **Test dengan MT5 Demo dulu** — jangan pernah test logic baru di live account.
5. **Setiap perubahan logic engine → jalankan backtest** sebelum merge ke master.
6. **Posisi comment** — Chain positions prefix `Chain_`, DD positions prefix `DD_`.

---

## HISTORY PERUBAHAN PENTING

| Commit | Perubahan |
|--------|-----------|
| `0549c5e` | Refactor: no-blocking signal logic per Daily Deploy doctrine |
| `5609db3` | Fix: NO BLOCK — VR/CF adalah CMP status, bukan gate blocking |
| `4a5070d` | Fix: H1 VR bukan gate — H1 belum VR = CONTI territory |
| `475a218` | Feat: TF pairs doctrine — H1 VR gate sebelum entry |
| `8a656cf` | Fix: TF-specific data buffers untuk resolve M5 no data error |
| `09ef3ce` | **Feat: Wire DailyDeployAnalyst ke main loop (PR #1)** |

---

## REFERENSI FILE PENTING

| File | Fungsi |
|------|--------|
| `DAILY_DEPLOY_SYSTEM.md` | Doktrin lengkap sistem Daily Deploy |
| `implementation_plan.md` | Roadmap Chain Reaction engine |
| `chain_settings.json` | Config runtime (auto_trade, lot, barrier, dll) |
| `DD_CMP_Marker.pine` | Indikator TradingView referensi |
| `tradingview-mcp-jackson/CLAUDE.md` | Panduan tools TradingView CDP |
| `SND_ZONE_ENGINE_AND_WEB_DASHBOARD.md` | ⚠️ BACA DULU kalau lanjut kerjaan SND Zone Engine / web dashboard / Analisa AI — cara cek versi EA yang bener-bener jalan, folder mana yang LIVE (bookmap-bridge-v1), dan histori versi v53.0-v53.15 |
| `D:\ChainReactionAndroidApp\DOKTRIN_ENTRY_CHAIN_REACTION_MASTER.md` | **Master Blueprint V4 syarat entry** — 4 skenario entry, 3 veto S&D, SL/lot/split-TP. Dasar Web Paper Trading di dashboard (`bookmap-bridge-v1/sultan/index.html`). |
| `D:\ChainReactionAndroidApp\DOKTRIN_ENTRY_PAPER_TRADING_ORDERFLOW_MASTER_V4.md` | Doktrin Order Flow & Paper Trading Engine — integrasi Delta/CVD/Wall/Absorption |
| `D:\ChainReactionAndroidApp\DOKTRIN_UNIFIED_MASTER_V4.md` | Teori setup & Time Law — Zone Co-Timestamp H4, otoritas Body Close |
| `D:\ChainReactionAndroidApp\DOKTRIN_RANTAI_WAKTU_DAN_BARRIER_V4.md` | Hukum Waktu & hierarki barrier — timestamp bawaan H4 vs noise TF kecil |
| `C:\Users\R O V A\.claude\plans\inherited-twirling-deer.md` | Plan (approved) buat fitur Web Paper Trading — mapping doktrin→data real yang tersedia, apa yang full-fidelity vs approksimasi |
