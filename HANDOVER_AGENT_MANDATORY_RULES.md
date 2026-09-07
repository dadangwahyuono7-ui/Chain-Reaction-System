# 👑 HANDOVER MASTER & PROTOKOL MUTLAK AGENT (COMMANDER DADANG WAHYUONO)
> **DOKUMEN INI WAJIB DIBACA OLEH SETIAP AGENT BARU (CLAUDE, ANTIGRAVITY, GEMINI, DLL) SEBELUM MENYENTUH KODE APA PUN DI WORKSPACE INI!**
> **PELANGGARAN TERHADAP ATURAN DI BAWAH INI AKAN MERUSAK SISTEM DAN MEMPEROLEH TEGURAN KERAS DARI COMMANDER DADANG WAHYUONO.**

---

## 🚨 1. ATURAN INTEGRITAS KODE (PANTANGAN RUSAK FILE)
1. **DILARANG KERAS FULL-OVERWRITE FILE**:
   - Dilarang menimpa file `heatmap.html`, `matrix.html`, atau `superpro_server.py` dengan versi usang atau membuat ulang dari awal!
   - Setiap modifikasi **WAJIB SURGICAL EDIT** (hanya ubah fungsi/baris yang ditargetkan).
2. **DILARANG MENYENTUH MINI PC SECARA SERAMPANGAN**:
   - **Mini PC (`100.71.97.6:8766`)** = SERVER PRODUKSI 24/7 (Bookmap + Rithmic Live).
   - **Local PC ROVA (`localhost:8899`)** = SANDBOX RISET & LAB PENGUJIAN.
   - Sebelum mendeploy ke Mini PC, WAJIB minta persetujuan eksplisit dari Commander Dadang!

---

## 🧭 2. IDENTITAS & PERBEDAAN VERSI TERMINAL
- **Produksi (Mini PC)**: Versi stabil **`v2.8`** (URL: `http://100.71.97.6:8766/`).
- **Sandbox Riset (Localhost)**: Versi **`v3.0 LAB`** (URL: `http://localhost:8899/`).
  - Badge navbar lokal: `<span class="badge-v2">v3.0 LAB</span>` dengan pendar gradien ungu-emas (*purple-amber glow*).
  - Dilarang mengganti versi ini menjadi 2.8 agar tidak rancu dengan server produksi!

---

## 🧱 3. DOKTRIN TEMBOK: HEATMAP TIMERS VS TOMBOL WALLS (PENTING!)
Pada sesi 5 September 2026, Commander Dadang menegaskan pemisahan mutlak antara Heatmap dan Wall:

### A. Teks Lot & Timer Durasi (`59L ⏱ 1377m 58s`)
- **Teks ini MURNI mengikat ke Layer HEATMAP (`showHeatmap`)**, BUKAN ke tombol Wall!
- Di dalam kode `drawHeatmap()`, rak likuiditas paus (Whale Shelves) dan timer durasi (`⏱ Xm Xs`) berada di bawah guard `if (lastSlice)`, bukan `if (showWalls)`.
- **Hasil**: Kapan pun tombol `[ 🧱 WALLS ]` dimatikan oleh Commander, teks timer durasi ketahanan paus di heatmap **HARUS TETAP MUNCUL**.

### B. Tombol `[ 🧱 WALLS ]` (`showWalls` & Shortcut `[W]`)
- Tombol ini adalah **RADAR TAKTIS ON-DEMAND** yang hanya dinyalakan saat Commander butuh melihat barrier dekat running price.
- **Hanya Menampilkan 1 Resistance & 1 Support Terdekat**:
  - Filter proximity ketat: hanya mencari barrier dalam radius taktis $\le \$40\text{ USD}$ dari running price.
  - Mengambil maksimal 1 Resistance terdekat di atas spot dan 1 Support terdekat di bawah spot.
- **PANTANGAN BESAR (PROYEKSI RUNWAY RAY)**:
  - Garis putus-putus Wall **DILARANG ditarik dari ujung kiri (`x = 0`)** karena akan menusuk/memotong teks timer durasi heatmap (`59L ⏱ ...`) di area histori!
  - Garis putus-putus Wall **HARUS ditarik murni secara maju (Runway Ray)**: mulai dari lilin running/runway space (`xRayStart`) ke arah kanan menuju DOM ladder. Area sebelah kiri (histori lilin dan timer heatmap) harus 100% bersih tanpa garis tembus!
  - Badge di tepi kanan (`🧱 25L RES $...` / `🧱 50L SUP $...`) menggunakan kapsul gelap semi-transparan `rgba(11, 15, 25, 0.90)` agar rapi dan tidak silau.
  - Jika barrier terdekat berada di luar jangkauan vertikal zoom saat ini, sistem menampilkan indikator navigasi off-screen di sudut kanan (`▲ 🧱 RES` atau `▼ 🧱 SUP`).

---

## 🕯️ 4. STANDAR CANDLESTICK LINUS (CONTOH DARI GRID 4 `matrix.html`)
Lilin pada `heatmap.html` dan `matrix.html` harus selalu menggunakan styling Grid 4:
- **Body Lilin**: 2px modern rounded corners (`ctx.roundRect([2])`) dengan ketebalan sumbu (*wick*) razor-sharp 1.0px.
- **Warna Trend Murni**: Bullish = Emerald Green (`#089981`), Bearish = Crimson Red (`#f23645`).
- **Institutional Vivid Bar Accents**:
  1. **Inside Bar (Coil)**: Border emas (`#ffd700`), wick emas (`#ffd700`), marker titik emas `●` di atas lilin.
  2. **Outside Bar (Sweep Breakout)**: Border ungu (`#c084fc`), wick ungu (`#c084fc`), marker berlian ungu `◆` di atas lilin.
  3. **Whale Absorption**: Border coral (`#ff6b81`), wick coral (`#ff6b81`), marker paus biru `🐋` di atas lilin.
- **Legenda Mikro di Pojok Kiri Atas**:
  - Terdapat teks legenda: `■ INSIDE COIL` (emas) | `■ OUTSIDE SWEEP` (ungu) | `■ WHALE ABSORPTION` (coral pink).
  - Posisi X legenda adaptif: berada di sebelah kanan Volume Profile (`x = showProfile ? profileWidth + 16 : 16`) agar tidak pernah bertumpuk.

---

## 🪤 5. FITUR TRAPPED TRADERS (NONAKTIF DEFAULT)
- Sesuai arahan Commander Dadang (*"seller trap buy trap ini gak akurat, kita gak pakai aja"*):
  - `showTraps = false;` (Nonaktif default).
  - Tombol `#btn-toggle-traps` di menu layers tidak aktif default.
  - Fungsi `drawTrappedTraders()` memiliki guard `if (!showTraps) return;` di baris pertama.
  - **JANGAN PERNAH menyalakan fitur Traps secara default**, karena box hijau/merah `[ 🏷️ TRAPPED SELLERS ] SL: $...` akan menutupi lilin dan mengganggu fokus trading Commander.

---

## 🧲 6. DOKTRIN NAKED POC (NPOC)
- **Haram Menampilkan POC Bertatus `[TESTED]`**: POC yang sudah tersentuh harga adalah sampah visual. Skip 100% dari render loop.
- **Maksimal 2 NPOC Perawan**: Hanya tampilkan 1 NPOC `[UNTESTED]` terdekat di atas harga dan 1 NPOC `[UNTESTED]` terdekat di bawah harga dalam radius $\le 45\text{ USD}$.

---

## 📅 7. DATABASE HISTORI MT5 & MEKANISME SENIN
- Data historis lilin di-anchor pada penutupan Jumat MT5 ($4431.23) dari file CSV MT5 (`candle_vault.json`).
- Saat akhir pekan bursa libur: `superpro_server.py` membekukan market (Weekend Closure Guard) dan TIDAK mencetak bar flat 0-range.
- Saat Senin subuh bursa CME/Rithmic buka kembali: server otomatis menyambung pembentukan candle live di atas histori MT5 secara mulus tanpa gap.

---

## 📝 8. PROSEDUR SEBELUM & SESUDAH BEKERJA
1. **SEBELUM MENULIS KODE**:
   - Baca dokumen ini (`HANDOVER_AGENT_MANDATORY_RULES.md`).
   - Baca log koordinasi terbaru di `STATUS - Koordinasi Claude & Antigravity.md`.
2. **SETELAH SELESAI PEKERJAAN**:
   - Lakukan verifikasi visual di browser (`browser_subagent`) dan capture screenshot.
   - Update file `STATUS - Koordinasi Claude & Antigravity.md` dengan nomor poin baru.
   - Laporkan hasil dengan ringkas dan presisi kepada Maestro Dadang Wahyuono.

---

## 👑 9. DOKTRIN WAR ROOM 4-GRID (`matrix.html`) V61 ARSENAL (STATUS: SIAP PRODUKSI)
Pada sesi 6 September 2026 subuh, Commander Dadang Wahyuono menyetujui penggabungan total seluruh persenjataan institusional ke dalam 4-Grid War Room ([matrix.html](file:///d:/ChainReactionAndroidApp/ChainLocal/matrix.html)). Seluruh agent penerus **WAJIB MENJAGA 100% ARSITEKTUR INI AGAR TIDAK RUSAK/TERGANTI**:

### A. Grid 1: Zenobi Multi-Session Volume Profile (`Formula.TotalAndBidAsk`)
- Mengimplementasikan algoritma C# NinjaTrader 8 dari repositori `gbzenobi/CSharp-NT8-OrderFlowKit`.
- Menampilkan 3 sesi perdagangan: Sesi 1 Asia, Sesi 2 London, Sesi 3 Live US.
- 3 Tombol formula di header: `[ BID/ASK ]` (batang dual-tone cyan/gold), `[ DELTA ]` (net buy/sell hijau/merah), `[ TOTAL ]` (volume total + Value Area 70% Steidlmayer).
- Garis batas sesi atas: Label Cyan `V: <TotalVol>L` (misal `V: 39,673L`).
- Garis batas sesi bawah: Label `D: <NetDelta>L` (misal `D: -3,494L` merah, `D: +1,948L` hijau).
- Garis POC emas solid dengan label harga `POC $4419.00`, `$4424.50`, dll.

### B. Grid 2: Footprint Cluster Ladder & Trapped Traders
- 3 Tombol mode Footprint di header: `[ BIDxASK ]`, `[ DELTA ]`, `[ VOL ]`.
- **Trapped Traders / Unfinished Auction**:
  - `🩸 TRAP BUY`: Agresif buying di puncak high tapi bar ditutup bearish.
  - `🟢 TRAP SELL`: Agresif selling di lembah low tapi bar ditutup bullish.
- **Tangga Harga Kanan (Right Price Axis Ladder)**:
  - Lebar 52px dengan garis harga per $0.50/$1.00 dan badge spot emas live (`$4431.20`).
- **Maximized Scaling (`[ 2 ]`)**:
  - Menampilkan 14 bar footprint selebar layar dengan lebar rung hingga 85px.

### C. Grid 3: Cumulative Volume Delta (CVD) & OFI Oscillator
- Kurva running CVD riil terhadap Zero Baseline (0L).
- Deteksi otomatis Wyckoff Bull Absorption (`▲ BULL ABSORPTION`) dan Wyckoff Bear Exhaustion (`▼ BEAR EXHAUSTION`).
- Histogram Order Flow Imbalance (OFI) di subplot bawah.

### D. Grid 4: Multi-TF Cascade & Central Execution
- **Session Anchored VWAP (AVWAP)**: Garis tengah emas solid dengan pita Cyan $\pm 1\sigma$ dan Ungu $\pm 2\sigma$ serta koridor volatilitas transparan.
  - Tombol toggle `[ 🎯 AVWAP ±2σ ]` di header Grid 4.
- **Dynamic Fair Value Gap (FVG)**: Kotak likuiditas Cyan (Bullish FVG) dan Merah (Bearish FVG).
- **Multi-TF Fractal Alignment Ribbon**: 5 Chip status (`M1`, `M5`, `M15`, `H1`, `H4`) di pojok kiri bawah.
- **Tactical Entry Markers**: Penanda entri candle `▲ GOLDEN #1 BUY`.

### 🚨 PANTANGAN MUTLAK UNTUK AGENT PENERUS:
1. **DILARANG MENGGUNAKAN DATA SINTETIS / FAKE DATA**:
   - Semua data mikrostruktur berasal dari real feed `candlesM5` CME Gold Futures.
   - Dilarang memasukkan fungsi `Math.sin`/`Math.cos` ke dalam kalkulasi volume/delta!
2. **JANGAN MERUSAK HEATMAP MONITOR 1**:
   - File `heatmap.html` di Port 8899 dan Mini PC Port 8766 tidak boleh dirusak timernya!
3. **PROSEDUR PRODUKSI KE MINI PC (`100.71.97.6`)**:
   - File yang siap diproduksi: `d:\ChainReactionAndroidApp\ChainLocal\matrix.html`.
   - Backup file lokal: `d:\ChainReactionAndroidApp\ChainLocal\matrix.html.bak_20260906_prearsenal`.
   - Sinkronisasi ke Mini PC (`C:\bookmap-bridge-v1\matrix.html`) **HANYA DILAKUKAN ATAS KOMANDO LANGSUNG DARI COMMANDER DADANG WAHYUONO**. Jangan deploy diam-diam!
