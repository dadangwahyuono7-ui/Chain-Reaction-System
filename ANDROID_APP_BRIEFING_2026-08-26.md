# Briefing buat Antigravity — Port S&D Zone Engine + Break Engine ke Android App
**Dari:** sesi kerja hari ini (2026-08-26) di `D:\PROJECT TRADING\` bareng Claude Code.
**Tujuan dokumen ini:** paste ke chat Antigravity biar dia paham semua yang baru dibangun hari ini di sistem trading Chain Reaction, dan bisa masukin fitur + tampilan yang sama ke Android app.

**Lokasi app:** `D:\ChainReactionAndroidApp\` — Kotlin + Jetpack Compose, package `com.dadang.chainreaction`, Retrofit+Gson buat networking, tema visual "cyber neon" dark (lihat `ui/theme/Color.kt`: `BgCyberDark`, `NeonCyan`, `NeonGreen`, `NeonRed`, `NeonAmber`, `GoldAccent`).

**File kunci yang relevan buat kerjaan ini:**
- `app/src/main/java/com/dadang/chainreaction/data/model/SultanStatus.kt` — data class Gson yang mirror `sultan_status.json`. **BELUM ADA field `sd_zones` sama sekali** - ini yang paling penting ditambahin duluan, kalau gak ditambah di sini, datanya gak akan pernah sampai ke UI walau API-nya udah kebaca.
- `app/src/main/java/com/dadang/chainreaction/data/api/ChainReactionApi.kt` — Retrofit interface, endpoint `sultan_status.json` udah ada dan dipakai (`getSultanStatus()`), TIDAK PERLU diubah - begitu `SultanStatus.kt` punya field `sd_zones`, otomatis ke-parse.
- `app/src/main/java/com/dadang/chainreaction/data/repository/TradingRepository.kt` — layer yang expose data ke ViewModel/UI.
- `app/src/main/java/com/dadang/chainreaction/ui/screens/chain/ChainScreen.kt` — screen yang paling dekat konsepnya (nampilin Chain Reaction cascade data) - kandidat tempat nambahin S&D card, atau bisa juga screen baru sendiri.
- `app/src/main/java/com/dadang/chainreaction/ui/components/` — komponen Compose reusable yang udah ada (`CyberCard`, `DirectionPill`, `MetricBox`, `SectionHeader`, dll) - PAKAI ini buat konsistensi visual, jangan bikin gaya baru dari nol.

---

## Sumber data — SATU file JSON

Semua yang dijelasin di bawah ini datang dari **satu file**: `sultan_status.json`, ditulis oleh EA MetaTrader 5 (`DD_ChainReaction_MultiTF_EA_v2.mq5`, versi terbaru `v53.26`) setiap ~1 detik, disajikan lewat HTTP di:

```
http://<IP-PC-trading>:8766/sultan_status.json
```

(Kalau Android app-nya dipakai dari luar rumah, ini juga yang lewat tunnel `trade.dadangchatai.com` — cek konfigurasi tunnel-nya kalau perlu endpoint publik.)

Android app tinggal `fetch`/poll endpoint ini (sama persis kayak web dashboard-nya, poll tiap 800ms) — gak perlu integrasi baru ke MT5, semua udah ada di JSON ini.

---

## 1. S&D Zone Engine — data supply/demand real dari order-flow Bookmap

Field: `sd_zones` di root JSON.

```json
"sd_zones": {
  "available": true,
  "zones": [
    {
      "side": "SUPPLY",           // atau "DEMAND"
      "lo": 4628.55, "hi": 4633.31,
      "wall_count": 3,
      "total_lot": 158.0,
      "status": "TESTED",          // FRESH / ACTIVE / TESTED / WEAKENED / BROKEN
      "strength": "KUAT",          // LEMAH / SEDANG / KUAT
      "retest_count": 18,
      "absorption_hits": 4,
      "score": 82
    }
    // ... bisa puluhan zona
  ],
  "roadmap": {
    "supply": [ /* top 5 zona SUPPLY terdekat dari harga, sorted */ ],
    "demand": [ /* top 5 zona DEMAND terdekat */ ]
  },
  "decision": {
    "location": "INSIDE_DEMAND",         // INSIDE_SUPPLY / NEAR_SUPPLY / INSIDE_DEMAND / NEAR_DEMAND / BETWEEN_ZONES / OUTSIDE_ACTIVE_RANGE
    "location_text": "DI DALAM ZONA DEMAND",
    "market_state": "ZONE COMPRESSION",
    "setup": "NONE",                      // NONE / BUY_WATCH / SELL_WATCH
    "reason_text": "Supply & demand lagi ketemu/sempit - tunggu salah satu jebol dulu",
    "focus": "FOKUS: TUNGGU (zona sempit)",
    "buyer_pct": 50, "seller_pct": 50,
    "compression": true
  },
  "break": {
    "supply_state": "MOMENTUM_BREAK",
    "supply_momentum": "NORMAL",         // WEAK / NORMAL / STRONG
    "demand_state": "NONE",
    "demand_momentum": "NORMAL",
    "market_read": "COMPRESSION",        // NORMAL / COMPRESSION / CHOPPY
    "direction": "-",                    // "-" / "BUY" / "SELL" - HANYA informational, BUKAN sinyal entry
    "status_text": "COMPRESSION - WAIT",
    "no_trade_zone": true
  }
}
```

### Doktrin baca data ini (WAJIB dipahami, bukan cuma angka mentah)

1. **`strength` (KUAT/SEDANG/LEMAH) ≠ `status` (AUS/AKTIF/DIUJI/BARU)** — dua sumbu beda:
   - `strength` = seberapa TERBUKTI zona ini (udah diuji berapa kali + selamat, umur, serap) - `retest_count` masuk komponen skornya.
   - `status = WEAKENED` (ditampilkan "AUS") = lot-nya lagi TREND TURUN belakangan ini - **BUKAN otomatis tanda lemah**, bisa juga cuma order dibatalin/reposisi.
   - Contoh nyata: zona "KUAT 82 (AUS) | diuji 39x" itu VALID - terbukti kuat lewat 39x diuji, tapi lot-nya lagi menipis sekarang. Jangan tampilin sebagai kontradiksi.

2. **`absorption_hits` ("serap") adalah bukti erosi ASLI** (order beneran dimakan transaksi) - **`total_lot` turun doang BUKAN bukti** (bisa cuma dibatalin). Kalau mau kasih indikator visual "zona mulai lemah", pakai `absorption_hits` naik, JANGAN pakai `total_lot` turun doang.

3. **`compression: true`** berarti zona SUPPLY dan DEMAND terdekat lagi ketemu/nempel (<1 USD) - UI harus jelas nunjukin "TUNGGU, jangan pilih arah dulu" di state ini, bukan kasih rekomendasi BUY/SELL.

4. **`break.direction`, `break.status_text` itu informational, BUKAN sinyal entry** - JANGAN dibikin tombol "ENTRI SEKARANG" atau semacamnya. Baca aturan public-surface di bawah.

### Doktrin S&D Momentum Break Engine (state `break.supply_state`/`demand_state`)

State machine: `NONE → ZONE_TEST → WICK_BREAK/CLOSE_BREAK → MOMENTUM_BREAK → FOLLOW_THROUGH → BREAK_CONFIRMED`, dengan `FALSE_BREAK`/`REJECTION`/`RETEST` sebagai state tambahan.

**ATURAN PALING PENTING — CLOSE ONLY:** `WICK_BREAK`/`CLOSE_BREAK`/`MOMENTUM_BREAK`/`FOLLOW_THROUGH` artinya **BELUM CONFIRMED**. JANGAN PERNAH tampilkan sebagai "sudah breakout" atau kasih warna hijau/merah solid seolah udah pasti - itu masih "lagi mencoba". Cuma `BREAK_CONFIRMED` yang boleh dibilang breakout beneran. `FALSE_BREAK`/`REJECTION` artinya percobaan GAGAL, zona-nya malah bertahan.

Saran UI: badge/warna beda-beda per tingkat kepastian (misal abu-abu untuk WICK, kuning/oranye untuk CLOSE/MOMENTUM/FOLLOW_THROUGH, hijau/merah SOLID cuma untuk BREAK_CONFIRMED).

---

## 2. Desain visual yang udah divalidasi hari ini (MT5 + web)

Ini bukan wajib ditiru 1:1 (Android app punya bahasa desain sendiri), tapi ini pola yang udah teruji lewat banyak iterasi bareng Dadang hari ini - dan mencerminkan apa yang dia SUKA:

- **Kotak zona = OUTLINE aja, JANGAN solid fill.** Solid fill nutupin candle/chart di belakangnya - Dadang eksplisit menolak itu ("pusing gw liat breakoutnya, gw masih butuh liat candlenya").
- **Zona terdekat (S1/D1) = paling menonjol** (border tebal), zona lebih jauh (S2, S3, dst) = makin tipis/redup, tapi JANGAN sampai invisible (ini kejadian - opacity terlalu rendah bikin gak kelihatan, harus ada batas minimum).
- **Label zona = lot, kekuatan, status, diuji, serap** - format: `"S1 158L | KUAT 82 (AUS) | diuji 18x, serap 4x"`. JANGAN pakai range harga di label (Dadang bisa baca posisi dari sumbu harga sendiri) - fokus ke lot & kekuatan.
- **Warna: SUPPLY = merah, DEMAND = hijau** - jangan diubah, itu udah jadi bahasa yang dia hafal.
- **Panel/ringkasan (kalau ada di Android app) HARUS beda peran dari chart**: chart = visual lokasi, panel/card = ringkasan singkat (FOKUS, Posisi, Buyer/Seller%, Break Status) - JANGAN duplikasi info yang sama di dua tempat.
- **Kalau ada peringatan zona sempit/mendekati zona** - satu baris warning yang jelas (warna oranye buat compression, merah/hijau buat approaching supply/demand), bukan wall of text.

---

## 3. ATURAN KERAS — permukaan publik (kalau Android app bisa diakses orang lain / bukan cuma Dadang sendiri)

Ini SANGAT PENTING dan sudah jadi aturan tetap di seluruh sistem ini:

- **JANGAN PERNAH** tampilkan sinyal eksplisit kayak "BUY SEKARANG" / "ENTRI DI SINI" sebagai perintah langsung.
- **JANGAN** kasih TP/SL spesifik - itu keputusan manajemen risiko Dadang sendiri.
- Kalau mau nyebut arah/zona, framing-nya HARUS "zona pantau" / observasi, bukan komando.
- **WAJIB** ada disclaimer visible: "Bukan saran finansial - keputusan dan risiko di tangan Anda."
- Alasan: Dadang trading manual, khawatir kalau dia live streaming/share app-nya, orang lain ikut entri dari sinyal yang ditampilkan lalu nyalahin dia kalau rugi.

Kalau Android app ini CUMA buat Dadang sendiri (private, gak pernah di-share), aturan ini bisa lebih longgar - tapi confirm dulu ke Dadang sebelum Antigravity nge-loosen batasan ini.

---

## 4. Yang TIDAK perlu di-porting (di luar scope hari ini)

- Buyer/Seller control PER ZONA (masih proxy symbol-level, belum akurat per-zona)
- Trigger Engine (WATCH→REACTION→CLOSE CONFIRM state machine buat entry beneran)
- MASTER/CORE zone merging
- Entry logic apapun - semua yang dijelasin di sini adalah DATA/TAMPILAN, bukan auto-trading

---

## 5. Kalau butuh detail lebih lanjut

Semua histori keputusan/alasan ada di:
- `D:\PROJECT TRADING\SND_ZONE_ENGINE_AND_WEB_DASHBOARD.md` (arsitektur lengkap, versi EA, cara verifikasi)
- `D:\PROJECT TRADING\DD_ChainReaction_MultiTF_EA_v2.mq5` (source EA, cari `S&D MOMENTUM BREAK ENGINE` buat implementasi state machine-nya kalau perlu contoh logic)
- Web dashboard yang udah jadi contoh implementasi: `D:\PROJECT TRADING\bookmap-bridge-v1\sultan\index.html` + `logic.js` (cari `sdm-` buat elemen S&D Price Map, ini referensi visual paling dekat buat Android app)
