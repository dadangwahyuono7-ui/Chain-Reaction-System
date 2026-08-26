# SND Zone Engine + Web Dashboard — Project State
**Ditulis:** 2026-08-26 (sesi marathon sehari penuh). Baca ini duluan kalau buka chat baru dan mau lanjut kerjaan zone/web/AI analysis.

---

## TL;DR — 4 hal yang PALING sering bikin bingung

1. **EA gak auto-reload.** Setiap kali file `.mq5`/`.ex5` diganti, EA yang lagi nempel di chart Dadang TETAP jalanin versi LAMA sampai di-detach lalu di-attach ulang manual. **Sebelum bilang "sudah selesai" ke Dadang, SELALU cek versi yang benar-benar jalan** dengan baca `ea_version` di `sultan_status.json` (lihat cara cek di bawah) — jangan asumsi deploy = langsung kepakai.

2. **Ada 3 folder bridge yang isinya hampir sama**, dan cuma 1 yang benar-benar LIVE:
   - `bookmap-bridge\` (folder paling lama, kadang sudah drift/beda isi)
   - `bookmap-bridge-v1\` — **INI YANG LIVE.** `sultan_dashboard_server.py` (port 8766) dan `news_engine.py` jalan dari sini. Cek dengan lihat file `.log`-nya (`sultan_dashboard.log`, `news_engine.log`) — yang mtime-nya paling baru itu yang aktif.
   - `bookmap-bridge-v2\` — kopi dev, disinkronkan tapi TIDAK benar-benar jalan.
   
   **Kalau edit `sultan/index.html`, `sultan/logic.js`, `news_engine.py`, `bookmap_addon_v2.py`, atau `zone_engine.py` — copy ke SEMUA TIGA folder.** Verifikasi hasil edit benar-benar kepakai dengan `fetch()` langsung ke `http://127.0.0.1:8766/...`, jangan cuma percaya file di source tree.

3. **`DD_ChainReaction_MultiTF_EA_v2.mq5`** (root `D:\PROJECT TRADING\`) adalah SATU-SATUNYA EA produksi Dadang — bukan file terpisah untuk preview/testing. Dadang eksplisit menolak pola "bikin v2 EA buat coba-coba, nanti gabung ke v1" — semua fitur baru masuk langsung ke file ini. Setelah compile, deploy ke:
   - `C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\` (folder yang MT5 benar-benar baca)
   - `D:\PROJECT TRADING\bookmap-bridge-v1\` (kopi referensi, diminta Dadang 2026-08-26 biar "on hand" bareng file bridge lainnya)

4. **Compile bisa DIAM-DIAM GAK JALAN kalau gak pakai `-Wait`** (lihat detail di bawah) - selama MT5 Terminal lagi kebuka, compile command yang fire-and-forget bisa silently no-op dan `compile_log.txt` yang dibaca ulang cuma isi LAMA. SELALU verifikasi `compile_log.txt`'s LastWriteTime beneran baru sebelum percaya "0 errors 0 warnings".

## Cara cek versi EA yang BENAR-BENAR jalan (jangan skip ini)

```powershell
python -c "import json,time; d=json.load(open(r'C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files\sultan_status.json', encoding='ascii')); print('ea_version:', d['ea_version']); print('age sec:', time.time()-d['timestamp'])"
```

Kalau `ea_version` yang muncul BUKAN versi yang baru dikompile → EA belum di-reattach. Cara reattach (Dadang butuh langkah eksplisit tiap kali, sering lupa/bingung):
1. Klik kanan chart XAUUSD → **Expert Advisors** → **Remove** (atau klik icon EA di pojok kanan atas chart → hapus).
2. **Navigator** (Ctrl+N) → Expert Advisors → drag `DD_ChainReaction_MultiTF_EA_v2` ke chart lagi.
3. Tab **Common** → centang **"Allow Algo Trading"** → OK.

## Cara compile

**⚠️ PAKAI `-Wait`, JANGAN fire-and-forget.** 2026-08-26: compile via `& "...\MetaEditor64.exe" /compile:... /log:...` (tanpa `-Wait`, cuma `Start-Sleep` abis itu) ternyata bisa DIAM-DIAM GAK JALAN kalau MT5 Terminal lagi kebuka (`terminal64.exe` aktif) - `compile_log.txt` gak keupdate sama sekali, tapi kalau dibaca ulang ISI-nya kelihatan sama kayak compile sukses sebelumnya ("0 errors, 0 warnings") karena itu FILE LAMA yang gak ketimpa, bukan hasil compile baru. 3 kali fix EA (v53.13/v53.14/v53.15) ke-deploy dengan binary yang SALAH (isinya masih compile v53.12) gara-gara ini - Dadang udah reload/reattach berkali-kali dan gak ada yang berubah, root cause-nya ternyata bukan di sisi dia sama sekali.

**Cara yang TERBUKTI benar** (selalu pakai `-PassThru -Wait`, dan WAJIB cek `compile_log.txt`'s LastWriteTime beneran baru - jangan cuma percaya isinya):
```powershell
Remove-Item "D:\PROJECT TRADING\compile_log.txt" -ErrorAction SilentlyContinue   # biar gak ketipu file lama
$p = Start-Process -FilePath "C:\Program Files\MetaTrader 5\MetaEditor64.exe" -ArgumentList '/compile:"D:\PROJECT TRADING\DD_ChainReaction_MultiTF_EA_v2.mq5"','/log:"D:\PROJECT TRADING\compile_log.txt"' -PassThru -Wait
Write-Host "ExitCode: $($p.ExitCode)"   # selalu 1 baik sukses maupun gagal - JANGAN dipakai buat cek sukses/gagal
Get-Item "D:\PROJECT TRADING\compile_log.txt" | Select-Object LastWriteTime   # HARUS barusan, bukan bekas
Get-Content "D:\PROJECT TRADING\compile_log.txt" -Encoding Unicode | Select-String -Pattern "error|warning|Result"
```
Setelah itu, sebelum deploy, cek juga `.ex5`-nya beneran ke-generate ulang (mtime + MD5 beda dari sebelumnya) - jangan cuma percaya log-nya doang.

---

## Arsitektur (ringkas)

```
Bookmap (native addon, Configure Add-ons)
  bookmap_addon_v2.py → zone_engine.py (ZoneEngine class)
  → tulis zones_v2.csv setiap siklus
  → MetaQuotes\Terminal\Common\Files\zones_v2.csv

DD_ChainReaction_MultiTF_EA_v2.mq5 (SATU EA produksi)
  ReadZonesCsv() → g_zone* arrays
  DrawAllZones() → gambar box di chart (S1/D1 solid, S2/S3/D2/D3 outline redup)
  BuildDecisionContext() → g_sdmLocation/Setup/Reason/BuyerPct/dst (Zone Relevance Engine)
  CheckZoneBreakoutEntry() → entry logic pakai zona real
  WriteSultanStatus() → tulis sultan_status.json (termasuk blok "sd_zones" - v53.12+)
  → MetaQuotes\Terminal\Common\Files\sultan_status.json

sultan_dashboard_server.py (port 8766, jalan dari bookmap-bridge-v1\)
  → proxy sultan_status.json ke web
  → serve sultan/index.html + logic.js (dashboard utama, termasuk panel "S&D Price Map")

news_engine.py (jalan dari bookmap-bridge-v1\, proses Python terpisah, stateless)
  → fetch berita Kitco + baca sultan_status.json (termasuk sd_zones)
  → generate_ai_analysis() → tulis sultan/news_feed.json
  → tampil di card "System Pulse · Analisa AI" (dashboard utama) + tab News & Catalyst
```

## Yang sudah dibangun (urutan versi EA, sesi 2026-08-26)

| Versi | Yang berubah |
|-------|--------------|
| v53.0-ZONECF | Zone engine pertama kali disambungkan ke EA produksi — `CheckZoneBreakoutEntry()`, gambar zone box + label detail (lot/diuji/serap) |
| v53.1-53.9 | Iterasi UI zone box (proporsi zoom, label collision, cluster width cap di zone_engine.py) |
| v53.10-RELEVANCE | Zone Relevance Engine (`MarketLocation`/`ZoneCompressionActive`/`BuildDecisionContext`), S&D Price Map panel digabung ke panel utama (bukan panel terpisah lagi) |
| v53.11 | Roadmap HLINE full-width (garis dari kiri ke kanan) ditambah, lalu label SEMPIT dipendekin |
| v53.12-WEBZONE | Export blok `sd_zones` ke `sultan_status.json` → dipakai buat panel S&D Price Map versi FULL di web dashboard |
| v53.13-SEMPITFIX | Label "SEMPIT - nempel..." dipendekin jadi "ZONA SEMPIT" (1 sisi aja, gak dobel) |
| v53.14-NOROADMAPLINE | **Roadmap HLINE dihapus total** — Dadang bilang redundan sama zone box + panel |
| v53.15-CLEANVISUAL | **Overhaul visual besar** — cuma S1/D1 (zona terdekat) yang digambar solid, S2/S3-D2/D3 outline tipis+redup (opacity disimulasikan lewat `BlendToBlack()`, MQL5 gak punya alpha channel asli). Label chart dipangkas jadi cuma `"S1  4628.55-4633.31"` (gak ada lagi lot/skor/diuji/serap di chart — detail itu sekarang cuma ada di panel). Panel MT5 dapat tambahan list S1-S3/D1-D3. |

| v53.16-22 | Trim/expand siklus panel & label (iteratif, lihat memory `project_snd_zone_engine.md` buat detail tiap versi) - berakhir di: SEMUA zona (bukan cuma S1/D1) outline-only (bukan solid fill, biar candle keliatan), cap chart naik ke 20/sisi ("tampilin semua"), label full detail (lot/kuat/status/diuji/serap) di SEMUA rank, FRESH dapet garis putus-titik sendiri |
| v53.18-25-SDBREAKENGINE | **S&D Momentum Break Engine** - state machine CLOSE-only (`NONE→ZONE_TEST→WICK_BREAK/CLOSE_BREAK→MOMENTUM_BREAK→FOLLOW_THROUGH→BREAK_CONFIRMED`, +`FALSE_BREAK`/`REJECTION`/`RETEST`). Deteksi doang, ENTRY LOGIC TIDAK DIUBAH. Diekspor ke `sultan_status.json` (`sd_zones.break`), ditampilkan di panel MT5 + web dashboard, dan dibaca `news_engine.py` buat Analisa AI. **Verified end-to-end live** (2026-08-26) - lihat memory buat detail lengkap |

**Status v53.25 (2026-08-26, akhir sesi ini): terverifikasi live jalan di MT5+web+AI sekaligus.** Kalau lanjut sesi baru, tetap cek dulu `ea_version` live sebelum asumsi versi mana yang kepakai - jangan percaya versi terakhir yang disebut di sini tanpa verifikasi ulang.

## Web dashboard (v53.12 companion, 2026-08-26)

- Panel baru "8 · S&D Price Map" di `sultan/index.html` (kolom ke-4, antara wall ladder dan kolom kanan) — FOKUS headline, Posisi, Buyer/Seller, sampai 3 zona SUPPLY + 3 DEMAND terdekat (range, strength, lot, diuji, serap). Pulse animasi kalau harga lagi di dalam zona itu, warning banner kalau mendekati/ZONA SEMPIT.
- **Aturan permukaan publik** (dashboard ini bisa diakses via tunnel `trade.dadangchatai.com`): FOKUS ditulis "ZONA PANTAU: BUY/SELL" (bukan perintah "BUY SEKARANG"), selalu ada disclaimer "bukan saran finansial". Lihat memory `feedback_no_explicit_signals_on_public_surfaces` kalau mau nambah fitur serupa di permukaan publik lain.
- `news_engine.py`'s `generate_ai_analysis()` sekarang baca `sd_zones` juga (bukan cuma POC/VAH/VAL) dan diajarin doktrin "serap" (lot turun tanpa serap naik = kemungkinan cancel, bukan bukti jebol) — hasilnya AI ngasih analisa+saran entri (zona pantau) yang grounded di zona real, sudah diverifikasi live.

## File-file kunci

| File | Fungsi |
|------|--------|
| `DD_ChainReaction_MultiTF_EA_v2.mq5` | EA produksi satu-satunya |
| `bookmap-bridge-v2\bookmap_addon_v2.py` | Native Bookmap addon, hitung zona, tulis `zones_v2.csv` |
| `bookmap-bridge-v2\zone_engine.py` | `ZoneEngine` class — clustering wall jadi zona, scoring, lifecycle |
| `bookmap-bridge-v1\sultan_dashboard_server.py` | Web server port 8766 (folder yang BENAR-BENAR jalan) |
| `bookmap-bridge-v1\sultan\index.html` + `logic.js` | Dashboard utama |
| `bookmap-bridge-v1\news_engine.py` | Fetch berita + AI analysis |
| `sultan_status.json` (Common\Files, ditulis EA) | Sumber data tunggal buat web + news_engine |
| `zones_v2.csv` (Common\Files, ditulis addon) | Sumber data zona tunggal buat EA |

## Belum dikerjakan / sengaja ditunda

- Buyer/Seller control per-zona masih pakai proxy Vol Ratio symbol-level (bukan per-zona asli)
- Trigger Engine (WATCH → REACTION → CLOSE CONFIRM state machine) — entry masih langsung fire, belum ada tahap konfirmasi
- MASTER/CORE zone merging (zona besar yang membungkus beberapa zona kecil) — belum dibangun
- EA-side MTF zone detection (D1/H4/H1/M30 price-structure zones, beda dari layer Bookmap-microstructure ini)

---

*Memory Claude yang lebih detail (per-topik, per-keputusan) ada di sistem memory internal — dokumen ini cuma ringkasan "on-hand" yang bisa dibaca langsung tanpa akses ke memory itu.*
