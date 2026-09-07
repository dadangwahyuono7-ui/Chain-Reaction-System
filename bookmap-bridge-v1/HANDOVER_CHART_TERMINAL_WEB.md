# 🚀 HANDOVER — SULTAN CHART TERMINAL (Web Chart Tab)

**Kalau agent sebelumnya (Claude) kena limit di tengah kerjaan ini, baca file ini dulu sebelum lanjut. Ditulis 2026-08-27, update terakhir: fitur Replay/Backtest.**

**UPDATE (round 5) — Replay/Backtest SUDAH ADA.** Tombol "⏮ Replay" di header, mutar ulang candle MT5 asli + histori penuh EA (DNA Vault, `dna_vault_YYYY-MM-DD.jsonl` di `Common\Files\`, 1 snapshot/menit sejak 2026-08-23). Endpoint baru: `/api/chart/history-range`, `/api/chart/replay-dates`, `/api/chart/replay-snapshots` (SEMUA di bawah prefix `/api/chart/`, BUKAN `/api/replay/` - lihat Bagian 2 buat alasannya, ini WAJIB DIIKUTI kalau nambah endpoint baru lagi ke chart_engine_server.py). **Gotcha timezone kritis**: MT5 Python API di mesin ini (`copy_rates_range`) nafsirin naive datetime pakai jam LOKAL sistem (WIB/UTC+7), BUKAN UTC walau dokumentasinya bilang UTC - pakai `datetime.fromtimestamp()`, JANGAN `datetime.utcfromtimestamp()`, kalau nambah endpoint MT5-Python baru yang butuh date range eksplisit. Detail lengkap lihat memory `project_sultan_chart_terminal.md` bagian "Replay / Backtest feature (round 5)".

---

## 0. KENAPA INI ADA

Dadang: layar chart di MT5 udah terlalu sempit buat nampung semua overlay yang udah dibangun di EA V3 (S&D zone, Sierra Chart suite, root alignment, dll). Solusinya: bikin tab baru di web dashboard yang sudah ada — chart terminal ala TradingView (multi-window, `lightweight-charts`), yang nampilin data REAL dari EA yang sama, bukan simulasi/dummy.

Sumber awal: Antigravity bikin standalone chart engine terpisah di `D:\PROJECT TRADING\bookmap-bridge-v1\custom-chart-engine-20260827T111543Z-1-001\custom-chart-engine\` (baca `README_HANDOVER_PC.md`-nya kalau mau lihat versi aslinya). Claude PORT ini jadi bagian dari web dashboard yang sudah ada (bukan situs terpisah), dan **buang semua perhitungan CMP/storyline yang dia bikin sendiri** — diganti baca `sultan_status.json` yang sama persis dipakai panel dashboard utama, biar gak ada dua sumber kebenaran yang bisa beda angka.

---

## 1. ARSITEKTUR — 2 PROSES

```
Port 8766 (SUDAH ADA, sultan_dashboard_server.py, http.server biasa)
    → serve semua file statis di bookmap-bridge-v1/sultan/ TERMASUK file baru:
        sultan/chart.html                          <- halaman chart terminal
        sultan/chart-assets/style.css
        sultan/chart-assets/core/App.js             <- entry point, event handler UI
        sultan/chart-assets/core/Constants.js       <- daftar TF & simbol
        sultan/chart-assets/charts/WindowManager.js <- JANTUNG-nya, baca di bawah
        sultan/chart-assets/drawings/DrawingEngine.js  <- tool gambar (trendline dll, TIDAK disentuh)
        sultan/chart-assets/drawings/DrawingStore.js   <- state gambar (TIDAK disentuh)
    → TIDAK BUTUH restart buat file baru nongol - dia serve langsung dari folder,
      tapi restart TETAP DIBUTUHKAN kalau /sultan_status.json sendiri berubah shape
      di EA (lihat Bagian 4)

Port 8800 (BARU, chart_engine_server.py, FastAPI, file terpisah di
           bookmap-bridge-v1/chart_engine_server.py)
    → HANYA data candle + tick MT5 real (via python MetaTrader5 lib), TIDAK
      serve halaman apa pun sendiri
    → Endpoint: /api/chart/history, /api/chart/status, /api/chart/symbols,
      /api/chart/timeframes, websocket /ws/chart-stream
    → BELUM masuk startup script mana pun - nyalain manual:
        cd "D:\PROJECT TRADING\bookmap-bridge-v1"
        "D:\PROJECT TRADING\venv\Scripts\python.exe" chart_engine_server.py
      (TODO buat next agent: tambahin ke START_TRADING.bat biar Dadang gak lupa)
```

**Kenapa 2 proses, bukan 1?** `sultan_dashboard_server.py` pakai `http.server.SimpleHTTPRequestHandler` (sync, gak support websocket/FastAPI). Nyatuin ke situ berarti rewrite total server produksi yang udah stabil — risikonya gak sepadan buat sekarang. Kalau nanti mau digabung beneran, itu kerjaan besar tersendiri, JANGAN dicoba sambil buru-buru.

---

## 2. FILE KUNCI — BACA INI DULU SEBELUM EDIT

### `sultan/chart-assets/charts/WindowManager.js` — SATU-SATUNYA tempat integrasi data EA

- `class ChartWindow` — 1 instance per window chart (Single/Dual/Quad layout)
  - `updateSDZones(zones)` — gambar/hapus price line zona S&D di kanvas (v53-style: HAPUS DULU baru gambar ulang, jangan numpuk - lihat komentar di kode)
  - `setSymbol()` — juga update teks watermark tiap simbol ganti
  - `this.sdZonePriceLines[]` — array price line aktif, buat di-cleanup
- `class WindowManager` — orkestrator semua window + koneksi data
  - `fetchSultanStatus()` — polling tiap 5 detik ke `/sultan_status.json` (relatif, same-origin port 8766). **INI PENGGANTI** `fetchStorylineAnalysis()` versi asli Antigravity yang manggil `/api/storyline/analysis` (data PALSU - CMP itung sendiri + wall ladder `random.randint()`). JANGAN PERNAH balikin ke situ.
  - `mapSultanStatusToCockpit(raw)` — mapper dari shape `sultan_status.json` ASLI ke shape yang dibutuhin `renderCockpitData()` (fungsi ini SENDIRI TIDAK DIUBAH, cuma sumber datanya). **Ini titik utama buat nambah data baru** - lihat Bagian 4.
  - `nearestSDZones(raw)` — filter zona S&D ke 3 terdekat per sisi (SUPPLY/DEMAND) dari harga sekarang, biar chart gak kepenuhan garis (awalnya 17 zona = 34 garis, kacau)

### `chart_engine_server.py`
- `MT5DataAdapter` / `DemoDataAdapter` / `MarketDataStore` — TIDAK PERNAH diubah dari versi asli, itu logic candle history yang udah bener (real MT5 via `copy_rates_from_pos`, fallback DEMO_DATA yang jujur dilabelin `is_demo_data:true`, bukan disamarin)
- Endpoint `/api/storyline/analysis` **SUDAH DIHAPUS** dari versi asli - JANGAN ditambahin lagi, itu sumber data ganda yang mau dihindarin

### Cache-buster — WAJIB tiap edit WindowManager.js
`sultan/chart-assets/core/App.js` import `WindowManager.js?v=N`. **Tiap kali edit WindowManager.js, naikin angka N di App.js**, kalau enggak browser Dadang bisa serve versi lama dari cache. Sekarang di angka **v=10**.

---

## 3. YANG SUDAH JALAN (verified live di browser, 2026-08-27)

- ✅ Multi-window sync (Single/Dual/Quad), candle real MT5 (H4/M30/M15/M5 dst)
- ✅ Live tick via websocket (`ws://<host>:8800/ws/chart-stream`)
- ✅ Cockpit HUD sidebar baca data ASLI: `regime.d1/h4/h1/m30/m15/m5` (arah CMP per TF), `conviction.score/max/grade/dir/against` (kedalaman chain + alasan), `context.action`, wall ladder ASLI dari `liquidity.bid_ladder/ask_ladder`
- ✅ `ea_version` EA V3 kelihatan langsung di HUD (bukti data live nyambung beneran, bukan cache)
- ✅ Zona S&D digambar sebagai price line di kanvas (dashed, merah=SUPPLY/hijau=DEMAND), 3 terdekat per sisi, label lot+kekuatan
- ✅ Watermark "{SYMBOL} · COMMANDER DADANG WAHYUONO" redup di tiap window (permintaan Dadang: biar gak gampang dicopas orang)
- ✅ Nav link "Chart Terminal →" di `sultan/index.html` (pola sama kayak link "News & Catalyst")

## 4. BELUM DIKERJAIN — INI YANG DIMINTA DADANG SELANJUTNYA ("masukin juga data biar hidup chartnya")

`sultan_status.json` py masih punya field yang BELUM dipetakan ke chart web ini:

- `sd_zones.break` — status S&D Momentum Break Engine (ZONE_TEST/WICK_BREAK/CLOSE_BREAK/BREAK_CONFIRMED dst) - belum ada marker di chart
- `flow.cvd`, `flow.delta_history`, `flow.pulse_pct`, `flow.absorption` — CVD/delta real-time, belum ditampilin sama sekali di web (padahal ada di panel MT5)
- `wall_sweep` — sweep reversal detection, belum ada
- `macro` / `usd` — DXY bias + news blackout countdown, belum ada
- `signals.barrier` — level barrier per TF (H4/H1/M30/M15/M5), belum digambar
- ~~**Sierra Chart Pro Order Flow Suite**~~ **SUDAH DIKERJAIN** (v53.56-V3-SCEXPORT, 2026-08-27, round 3). EA sekarang export blok `"sierra_chart":{imbalance_side, naked_poc_active/price, divergence_type, whale_side/lots, unfinished_found/price/time, profile_shape}` di `WriteSultanStatus()` - state-nya di-set DI DALAM tiap `Update*Engine()` MQL5 (titik yang sama dia mutusin gambar di chart MT5), bukan dihitung ulang. Web-side: `ChartWindow.updateSierraChart(sc)` di `WindowManager.js` pakai `candleSeries.setMarkers()` buat imbalance/divergence/whale/unfinished, `createPriceLine()` buat Naked POC, profile_shape jadi baris teks di card "Order Flow". **BELUM 100% divisualverifikasi** - semua field kebetulan "NONE" pas dicek (gak ada event live saat itu), jadi marker RENDERING beneran belum kelihatan langsung, cuma jalur kodenya udah confirmed gak error. Kalau Dadang bilang marker gak muncul pas ada event beneran, cek dulu di sini.

- Confluence Radar % (`CalculateConfluenceScore()`, yang barusan dibenerin dari bug fake-baseline) — **JUGA belum di-export ke JSON**, HUD web sekarang pakai `conviction.score/max` sebagai gantinya (real, tapi beda metric). Kalau Dadang mau angka Confluence Radar yang PERSIS sama kayak di MT5, itu juga butuh field baru di `WriteSultanStatus()`.

---

## 5. PROTOKOL WAJIB TIAP UBAH EA (`DD_ChainReaction_MultiTF_EA_v3.mq5`)

Ini bukan cuma soal chart web - ini aturan baku SELURUH sesi ini buat EA V3:

1. `rm -f "D:/PROJECT TRADING/compile_log_v3.txt"`
2. Compile via PowerShell (BUKAN fire-and-forget, WAJIB `-Wait`):
   ```powershell
   Start-Process -FilePath 'C:\Program Files\MetaTrader 5\MetaEditor64.exe' -ArgumentList '/compile:"D:\PROJECT TRADING\DD_ChainReaction_MultiTF_EA_v3.mq5"','/log:"D:\PROJECT TRADING\compile_log_v3.txt"' -PassThru -Wait
   ```
3. VERIFIKASI log-nya genuinely fresh (`stat` timestamp-nya), baca hasil "Result: X errors, Y warnings"
4. VERIFIKASI `.ex5` mtime juga berubah (bukti compile beneran jalan, MetaEditor kadang silent-fail kalau Terminal lagi kebuka)
5. Deploy ke 3 lokasi, `md5sum` semua buat mastiin sama:
   - `D:\PROJECT TRADING\DD_ChainReaction_MultiTF_EA_v3.mq5` + `.ex5` (source)
   - `...\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\` (yang MT5 beneran load)
   - `D:\PROJECT TRADING\bookmap-bridge-v1\` (mirror kedua)
6. Naikin `EA_VERSION` di `#define EA_VERSION "..."` - CEK DULU versi tertinggi yang udah kepake di comment (`grep -oE "v53\.[0-9]+"`), karena banyak versi udah "dipesen" duluan di comment tanpa EA_VERSION-nya ikut naik
7. Minta Dadang detach/reattach EA di chart (MT5 gak hot-reload)
8. Verifikasi LIVE `ea_version` di `sultan_status.json` beneran berubah SEBELUM lapor "beres" ke Dadang

---

## 6. GOTCHA / JANGAN

- JANGAN restart proses Python bookmap-bridge (CVD/wall/sweep data AKUMULATIF, restart = reset ke nol) - TAPI `chart_engine_server.py` (port 8800) ini AMAN di-restart kapan saja, dia gak nyimpen state akumulatif, cuma proxy MT5 live
- JANGAN kembaliin `CMPLogic.js` atau `storyline_calc.py` ke jalur aktif manapun - keduanya sengaja dead/dihapus
- JANGAN gambar semua zona S&D mentah-mentah (bisa sampai 17+) - selalu filter/cap kayak `nearestSDZones()`
- Server port 8800 SEKARANG jalan manual (bukan service), kalau PC restart dia MATI - perlu Dadang nyalain lagi atau next agent tambahin ke startup script
