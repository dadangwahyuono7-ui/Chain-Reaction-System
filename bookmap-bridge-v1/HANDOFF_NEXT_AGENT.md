# HANDOFF — Bookmap Chain Reaction Bridge
**Ditulis:** 2026-08-07 (sesi sebelumnya kena limit, agent baru lanjutin dari sini)
**Baca ini SEBELUM ubah apapun.** Owner: Dadang Wahyuono. Proyek: `D:\PROJECT TRADING\bookmap-bridge\`

---

## RINGKASAN 1 MENIT

Bridge Bookmap (order flow real) + doktrin Chain Reaction (CMP/VR/CF breakout minor-SNR) Dadang, auto-execute ke MT5 **DEMO** akun (#52643789 ICMarketsSC-Demo), semua trade tercatat di `trades.db` (SQLite) buat validasi doktrin jadi database nyata.

**Status barusan:** abis benerin bug PARAH (9 entry whipsaw dalam 10 detik gara-gara Absorption-exit + TP kejar-kejaran) dan lagi di tengah rombak dashboard.html biar lebih clean (baru aja hapus duplikasi CMP display). Semua proses restart terakhir SEHAT, 0 posisi kebuka, test suite 9/9 PASS.

**UPDATE 2026-08-08:**
1. **Dashboard sempet keganti eksternal jadi mockup dengan FAKE DATA** (order book padding sintetis, candle M5 sine-wave, fake CVD/system_status) — semua sudah dihapus & diganti data real (`order_book`/`spread`/`m5_bars` baru di `cr_master_engine.py`, `dashboard_logic.js` ditulis ulang total). Jangan kaget kalau nemu commit/diff besar di file itu.
2. **Proyek baru terpisah** (market lagi closed, Dadang mau validasi metodologi entry pakai MT5 Strategy Tester): dibikin `D:\PROJECT TRADING\DD_CMP_Indicator.mq5` (port CMP-detection-only dari `DD_CMP_Marker.v7.pine`, TANPA VR/CF/entry logic) + `D:\PROJECT TRADING\DD_ChainReaction_MultiTF_EA.mq5` (EA baru, baca CMP dari indikator via `iCustom()`, Master TF/Entry TF configurable pair, entry logic simpel "follow searah master" — SENGAJA beda dari doktrin bookmap-bridge/production, bukan pengganti). Keduanya sudah compile 0 error & di-deploy ke MT5 data folder. Ini BUKAN bagian dari bookmap-bridge pipeline — proyek riset validasi terpisah, jangan disambung logic-nya ke `cmp_engine.py`/`cr_master_engine.py`.

---

## BACA DULU SEBELUM APA-APA

```powershell
# Cek proses masih jalan
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*udp_listener.py*' -or $_.CommandLine -like '*tv_poll.mjs*' -or $_.CommandLine -like '*dashboard_web.py*' }

# Cek posisi kebuka di MT5 (JANGAN restart kalau ada posisi tanpa cek reconciliation jalan!)
cd "D:\PROJECT TRADING\bookmap-bridge"
python -c "import MetaTrader5 as mt5; mt5.initialize(); print([(p.ticket,p.magic,p.profit) for p in mt5.positions_get(symbol='XAUUSD') or []])"

# Jalanin test suite (WAJIB sebelum restart abis edit apapun)
PYTHONIOENCODING=utf-8 python test_master_engine.py
```

**Cara start/stop (semua proses jalan HIDDEN background, gak ada window cmd nongol):**
- Start: double-klik `START_TRADING.bat` (atau `powershell -File start_trading.ps1`)
- Stop: double-klik `STOP_TRADING.bat` (atau `powershell -File stop_trading.ps1`)
- **SELALU stop dulu → edit → test → clear log (`rm *.log`) → start lagi.** Jangan edit sambil proses jalan.
- Log ada di `udp_listener.log` dan `dashboard_web.log` (dibuat ulang tiap restart karena di-`rm` di awal).

---

## DOKTRIN INTI (jangan diubah tanpa Dadang minta)

- **CMP** = candle CLOSE (bukan wick) lewatin minor-SNR (V-shape=support, A-shape=resistance)
- **VR** = child TF breakout LAWAN parent (retracement) — **BUKAN syarat yang harus ditunggu**, itu cuma status. Kalau muncul, itu artinya PAUSE continuation-entry dan malah jadi peluang entri SEARAH VR (scalp)
- **CF** = child TF balik SEARAH parent lagi (continuation) — entry-nya di sini
- **Fraktal bottom-up**: M1 bentuk M5 bentuk M15 bentuk M30 bentuk H1 bentuk H4 bentuk D1 — breakout CMP M5 itu LITERALLY pembentukan real-time candle M30 yang lagi jalan
- **Entry logic FINAL: cuma H4 → M30 → M5.** M15 DIBUANG dari entry logic (masih ditampilin buat info doang). Dadang: *"gw gak pernah bilang ikut m15... fokus aja di h4 m30 m5"*
- **Wall-based entry** (fitur baru): harga di area wall (liquidity ASLI Bookmap) + Footprint per-harga (bukan per-bar) dukung arah = entri LANGSUNG, gak perlu nunggu CMP breakout sama sekali. Ini prioritas TERTINGGI.
- **SL = backstop finansial doang** (2.5% modal, JAUH dari harga), BUKAN level teknis kecuali WALL_ENTRY (SL = seberang wall). Exit SEBENARNYA 100% doktrin-driven (M30 flip / M5 gagal), SL cuma jaring pengaman kalau bot crash.
- **TP = TIDAK ADA SAMA SEKALI** (baru dihapus total, lihat "BUG TERAKHIR" di bawah). Dadang: *"JANGAN TP KECUALI ADA SIGNAL SELL... gw trading gak pernah TP 10 pip."*
- **CVD & Market Pulse = kalkulasi kita SENDIRI dari raw tick, BUKAN mirror gauge Bookmap** (formula gauge Bookmap gak dipublikasi, jangan coba-coba samain lagi — udah dicek WebSearch, gak ada formulanya di manapun).

---

## ARSITEKTUR FILE

```
bookmap_bridge.py (di Bookmap sendiri, JANGAN sentuh)
  → UDP 127.0.0.1:9000
  → udp_listener.py (proses utama, standalone Python, BUKAN di editor Bookmap yang buggy)
      ├── cmp_engine.py       — CMP/VR/CF doctrine (TFState, CMPDetector, BookmapDoctrineAnalyst)
      ├── cr_master_engine.py — CRDecisionRecommendationEngine (orchestrator), WallLadderTracker
      ├── cvd_engine.py       — session-cumulative CVD (reset 07:00 WIB)
      ├── market_pulse_engine.py — replika "Price Change" algorithm Bookmap (deviasi harga)
      ├── absorption_engine.py — CVD window delta vs price move (exhaustion detector)
      ├── footprint_engine.py — buy/sell volume PER-HARGA (buat WALL_ENTRY confirmation)
      ├── mt5_bridge_executor.py — eksekusi MT5 (magic 2027, isolated dari engine lain)
      ├── trade_db.py         — SQLite trades.db logger
      └── live_status.json    — output tiap 0.1s, dibaca dashboard
  → dashboard_web.py (pywebview + http.server port 8765, bind 0.0.0.0 jadi bisa diakses HP/tablet)
      → dashboard.html (institutional terminal layout: header 44px, kiri 288px, tengah flex, kanan 384px, footer 32px)

tv_poll.mjs (di tradingview-mcp-jackson/) — overlay CMP dari Pine DD_CMP_Marker.v6.2 via CDP,
  dipake SEMENTARA sampe Bookmap sendiri punya cukup bar (≥3) per TF
```

**Test suite**: `test_master_engine.py` — 9 test group, WAJIB pass sebelum restart live. Run: `PYTHONIOENCODING=utf-8 python test_master_engine.py`

---

## BUG TERAKHIR YANG DIFIX (paling penting dipahami dulu)

**Kejadian:** Dadang nangkep LIVE ada 9 entry dalam <10 detik, semua whipsaw exit dalam 0.6-0.7 detik, rugi kecil berkali-kali. Root cause DUA hal:

1. **Absorption-driven exit** (yang gw pasang di giliran sebelumnya) — kalau Absorption exhaustion kedeteksi di arah posisi kita, langsung force-exit walau doktrin bilang HOLD. Ini SALAH — Dadang: *"meski ada absorption di buy nya lanjut."* **DIHAPUS TOTAL.**
2. **TP price target** (wall-based atau apapun) — begitu TP kena, posisi ketutup, terus KARENA M30/M5 masih align, engine re-entry LAGI SAAT ITU JUGA (gak ada cooldown), seringnya pas harga lagi di pucuk (top) tepat sebelum pullback. **TP DIHAPUS TOTAL** — order MT5 sekarang selalu `tp=0` (gak ada take-profit order).

**Fix yang udah masuk:**
- `cr_master_engine.py`: absorption exit REMOVED dari position-monitoring branch
- `cr_master_engine.py`: tp_price REMOVED dari wall-based injection DAN dari `get_wall_entry_signal()`
- `mt5_bridge_executor.py`: `execute_entry()` selalu kirim `"tp": 0.0` ke MT5, gak ada parameter tp_hint lagi
- `udp_listener.py`: `handle_mt5_auto_execute()` gak resolve tp_tf/tp_price lagi, `_resolve_price()` dihapus (dead code)
- **Re-entry cooldown BARU**: `cr_master_engine.py`'s `evaluate()` — setelah EXIT, catat `self._last_exit_m5_time = M5.cmp_change_time`. Entry CF (M5-sourced) BARU boleh fire lagi kalau M5 punya `cmp_change_time` yang LEBIH BARU dari itu (artinya M5 beneran dapet candle-close event baru, bukan re-fire di state basi yang sama). Ini otomatis mensyaratkan minimal 1 "candle merah" (retracement) dulu sebelum re-entry, sesuai request Dadang: *"mana ada mau buy entri pas candle ijo, nunggu merah dulu lah minimal."*

**Test coverage**: `test_no_tp_absorption_does_not_exit_and_reentry_cooldown()` di `test_master_engine.py` — verifikasi 3 hal: (1) CF gak pernah bawa tp_price, (2) Absorption doang gak bisa force-exit posisi valid, (3) re-fire di state M5 basi ke-block, re-fire di state fresh diizinin. **SEMUA PASS.**

**Verifikasi live**: abis restart, cuma 1 entry normal fire (gak whipsaw), `tp=None` di trades.db, posisi HOLD stabil.

---

## KERJAAN YANG LAGI JALAN — DASHBOARD REDESIGN (BELUM SELESAI)

Dadang minta dashboard di-resize (bilang "kebesaran"), gw kasih spec Tailwind detail dia (institutional terminal: header 44px, kolom kiri 288px/`w-72`, tengah flex-1, kanan 384px/`w-96`, footer 32px) buat dijadiin acuan UKURAN doang — **tapi gw KEBABLASAN bikin ulang STRUKTUR-nya juga** (nambah panel Wall Memory/History/Filter yang dia gak minta). Dadang marah:

> "KENAPA WEB NYA LO RUBAH KAN GW HANYA MINTA UKURAN NYA... TRUS APA FUNGSINYA CMP GW ADA 2 LOKASI ANJING... LO BUAT SE PROFESIOANL MUNGKIN KAYAJ QUANT TRADING AJA DEH... DHASBOARD SKERANG KEK TAI"

**Yang UDAH difix (sesi ini, sebelum limit):**
- Hapus tabel TF DETAIL yang REDUNDANT sama CMP CASCADE (dulu ada 2 tempat nampilin CMP, sekarang cuma 1 — cascade vertikal di kolom kiri, dengan `title` tooltip buat action text biar info gak ilang)
- Hapus CSS mati (table/th/td/tr.alt/cmp-pill/vr-tag/cf-tag, pos-tile.tp)
- Panel POSISI AKTIF: hapus tile TP (karena TP udah gak ada lagi), sekarang cuma Entry/SL/Lot (3 kolom)

**BELUM selesai / PERLU DICEK agent baru:**
1. **Belum di-restart & di-verify visual** — barusan lagi coba `mcp__Claude_Browser__navigate` pas kena limit, GAGAL ("navigation denied or failed"). **Langkah pertama**: coba buka lagi `http://127.0.0.1:8765/dashboard.html` di browser, screenshot/read_page, pastiin:
   - Gak ada JS console error
   - CMP cuma muncul 1 kali (cascade doang, kolom kiri)
   - Layout 3-kolom masih presisi (288px | flex | 384px)
   - Panel Wall Memory/History/Filter (kolom kanan) — Dadang BELUM eksplisit bilang mau dihapus atau dipertahanin, tapi given dia bilang "cuma minta ukuran", kemungkinan dia mau itu SEMUA disederhanain balik. **Tanya Dadang dulu** apa mau dipertahanin atau di-strip lagi ke versi lebih simpel (mungkin cukup 2 kolom kayak sebelumnya, atau bahkan versi paling awal yang lebih ringkas).
2. **Aesthetic "professional/elegant/quant trading"** — belum ada polish visual lanjutan (warna, spacing, konsistensi) di luar cleanup structural yang udah dilakuin. Pertimbangin: apakah masih perlu dipoles lagi, atau tanya Dadang dulu reaksinya ke versi yang udah di-cleanup ini sebelum nambah lebih jauh.
3. Kemungkinan BESAR: tanya Dadang secara eksplisit "mau gw balikin ke versi lama yang lebih simpel (2 kolom, gak ada Wall Memory/History/Filter), atau lanjut polish versi 3-kolom yang sekarang tapi lebih clean?" — JANGAN asumsi sendiri lagi, ini udah 2x salah tebak scope dashboard dalam 1 sesi.

**File terkait**: `dashboard.html` (udah di-edit, BELUM di-restart/verify), `dashboard_web.py` (window 1000x700, bind 0.0.0.0 buat akses HP/tablet — LAN IP: `192.168.0.104:8765`, cek ulang kalau IP berubah).

---

## HAL LAIN YANG PERLU DIINGET

- **Restart process WAJIB pas ada perubahan file .py** (Python gak hot-reload). Dashboard.html/dashboard_web.py TIDAK perlu restart seluruh pipeline kalau cuma edit HTML — cukup reload browser/window (file di-serve fresh dari disk tiap request). Kalau edit dashboard_web.py sendiri (window config dll), restart proses dashboard_web.py aja (cari PID-nya, jangan restart semua).
- **Posisi yang masih kebuka pas restart**: `udp_listener.py` punya reconciliation logic (`get_open_position_dict()` di `mt5_bridge_executor.py`, dipanggil di awal `udp_listener.py`) — otomatis restore `active_position` dari MT5 kalau ada yang masih kebuka. JANGAN hapus fitur ini, ini fix buat bug duplicate-entry yang udah kejadian sebelumnya.
- **Jangan pernah ngejar formula EXACT gauge Bookmap** (Market Pulse/CVD widget) — udah dicek, gak dipublikasi. Lihat `feedback_jangan_kejar_gauge_bookmap.md` di memory.
- **6 modul final (dikunci Dadang)**: Chain Reaction (CMP/VR/CF) + Market Pulse + CVD + Absorption + Wall + Footprint (per-harga, khusus WALL_ENTRY). Delta-per-Price, Iceberg, DOM, Heatmap, Bubble, Volume Profile SEMUA ditolak eksplisit.
- **Magic number 2027** buat semua order kita (isolated dari `engine/executor.py` produksi yang magic=2026 — JANGAN disamain, biar posisi 2 sistem gak ke-mix).
- **Akun DEMO**: #52643789 ICMarketsSC-Demo. **JANGAN PERNAH** ubah kode buat nyambung ke akun REAL tanpa instruksi eksplisit Dadang.

---

## MEMORY (baca ini juga)

Ada di `C:\Users\R O V A\.claude\projects\D--PROJECT-TRADING\memory\project_bookmap_bridge.md` — histori lengkap keputusan sesi ini + sesi sebelumnya. Baca dari atas ke bawah, urutan kronologis. Juga:
- `feedback_h4_m30_m5_only_no_m15.md`
- `feedback_jangan_kejar_gauge_bookmap.md`

**UPDATE memory file itu setelah kerjaan dashboard ini kelar** dengan hasil final + keputusan Dadang soal Wall Memory/History/Filter mau dipertahanin atau nggak.
