# Daily Deploy Trading System
**by Dadang Wahyuono**  
Referensi sistem untuk analisa bersama di TradingView via CDP.

---

## KONSEP DASAR

### Apa itu CMP (Current Market Price)?
CMP bukan harga sekarang. CMP dalam sistem ini adalah **level breakout yang sedang aktif** — candle yang CLOSE di atas resistance (CMP BUY) atau CLOSE di bawah support (CMP SELL).

- **CMP BUY** = candle yang close di atas resistance → momentum naik aktif
- **CMP SELL** = candle yang close di bawah support → momentum turun aktif
- **CMP paling kanan (terbaru)** = CMP yang sedang aktif dan menjadi referensi entry

> CMP bukan harga market. CMP adalah level breakout yang menjadi "rumah" momentum saat ini.

---

### Apa itu Breakout (BO)?
Breakout = **candle CLOSE** melewati level SNR — bukan wick, bukan body menyentuh. Harus close.

- Close di atas resistance → BO BUY
- Close di bawah support → BO SELL
- CMP ke-3 yang paling baru = CMP aktif

---

### SNR: Lama vs Minor Paling Kanan

| Jenis SNR | Fungsi |
|-----------|--------|
| **SNR Lama** (historical) | Barrier area = target TP. Bukan untuk entry. |
| **Minor SNR Paling Kanan** | Swing high/low terbaru di kanan chart = referensi CMP aktif, entry zone |

SNR lama = tembok/target. Minor SNR paling kanan = lokasi momentum sekarang.

---

## SIKLUS DAILY DEPLOY

Setiap TF berjalan dalam siklus 3 fase:

```
CMP (Breakout) → VR (Valid Retracement) → CF (Confirmation)
```

### 1. CMP — Current Market Price (Breakout)
Candle close melampaui SNR. Ini menentukan arah CMP TF tersebut (BUY atau SELL).

### 2. VR — Valid Retracement
**Breakout BERLAWANAN pertama** setelah CMP setup TF terjadi — pada TF SATU LEVEL DI BAWAH.

- VR hanya terjadi **SEKALI** per siklus CMP
- VR = sinyal bahwa CMP sedang aktif dan harga sudah "tes balik" dulu
- VR = indikator kita untuk mengetahui CMP mana yang aktif

**Hierarki TF untuk VR:**
| Setup TF | VR terjadi di |
|----------|--------------|
| Daily | H4 |
| H4 | H1 |
| H1 | M30 |
| M30 | M15 |
| M15 | M5 |

> Jika suatu TF belum VR → CMP TF itu **belum bisa dientry**. Tunggu VR dulu.

### 3. CF — Confirmation
**Breakout BERLAWANAN pertama** setelah VR — searah CMP asli (kembali ke arah).  
CF bisa terjadi **lebih dari sekali** dan menjadi momen entry.

---

## TRADING TF vs SETUP TF — KONSEP PALING PENTING

> **"Trading H4 bukan berarti entry di H4. Setup entry selalu di TF bawahnya."**

### Contoh: Trading H4 SELL

```
H4 CMP SELL terbentuk
       ↓
H1 belum VR?
  ├── YA (H1 belum VR)
  │     → H4 belum siap ENTRI penuh
  │     → BOLEH scalp SELL di M30/M15 searah H4
  │     → Tapi TP PENDEK — karena H1 belum konfirmasi
  │     → Expect: gerakan 10-30 pts, bukan 100 pts
  │
  └── TIDAK (H1 sudah VR = ada BUY M30 dulu)
        → H4 sekarang CONFIRMED
        → Cari ENTRI SELL di M30/M15 searah H1 = searah H4
        → TP PANJANG — siklus H4 sudah institutional confirmed
        → Expect: gerakan besar, bisa 50-150 pts
```

### Kenapa gerakan PENDEK selama H1 belum VR?

Karena H1 VR belum terjadi = institusional belum semua masuk. Harga masih "membangun fondasi" untuk siklus H4. Setiap push searah H4 akan tertahan — belum ada momentum institutional penuh di TF menengah.

Begitu H1 VR terjadi → institusional H1 masuk → H4 cycle confirmed → gerakan panjang dan deras.

### Tabel Trading TF vs Setup TF

| Trading TF | VR terjadi di | Setup TF (entry) | Gerakan expected |
|------------|--------------|-----------------|-----------------|
| H4 (belum VR H1) | H1 belum VR | Scalp M30/M15 searah | Pendek (10-30 pts) |
| H4 (H1 sudah VR) | H1 VR done | Entry M30/M15 searah | Panjang (50-150 pts) |
| H1 (belum VR M30) | M30 belum VR | Scalp M15/M5 searah | Pendek |
| H1 (M30 sudah VR) | M30 VR done | Entry M15/M5 searah | Medium-Panjang |
| M30 (belum VR M15) | M15 belum VR | Scalp M5/M1 searah | Sangat pendek |
| M30 (M15 sudah VR) | M15 VR done | Entry M5/M1 searah | Normal |

### Praktis: Cara Baca Potensi Gerakan

**Sebelum entry, tanya:**
1. Gw trading TF berapa? (misal H4)
2. TF di bawahnya (H1) sudah VR belum?
   - Belum VR → scalp, TP pendek, jangan ngarep jauh
   - Sudah VR → entry normal, TP bisa panjang sesuai SNR lama

### Aplikasi ke Situasi Sekarang (contoh real):

```
Daily  : SELL — arah besar confirmed
H4     : SELL | VR belum (H1 belum VR)
H1     : SELL | VR belum (M30 belum bounce berlawanan untuk H1)
M30    : SELL | VR done (BUY M15) | CF done (SELL M5) | ENTRI

→ Kita bisa scalp SELL di M30
→ Tapi karena H1 belum VR = gerakan PENDEK
→ Target TP: SNR terdekat bawah, bukan SNR jauh
→ Jangan hold posisi terlalu lama — begitu M30 kena VR berikutnya, exit

→ Kalau mau gerakan BESAR:
   Tunggu H1 VR (= ada BUY M30 dulu sebagai retracement H1)
   Setelah BUY M30 = H1 VR done
   Baru cari entry SELL lagi di M30/M15 = H4 cycle confirmed
   Di situlah gerakan bisa 100+ pts
```

---

## ATURAN ENTRY

### Syarat Entry Penuh (1 TF):
1. CMP TF sudah terbentuk (ada BO)
2. VR sudah terjadi (1 TF di bawah, berlawanan)
3. CF terjadi (konfirmasi, searah CMP) → **ENTRI**
4. Entry di minor SNR paling kanan (swing high/low terbaru)

### Syarat Entry Cross TF (jika HTF belum VR):
Jika H4 belum VR, tapi M30 sudah VR → bisa entry menggunakan:
- **CMP M30** sebagai referensi
- **VR M30** sebagai validasi aktif
- **CF M30** sebagai trigger entry

> Prinsip: Trade TF yang sudah punya VR. VR = tanda CMP itu hidup.

---

## HIERARKI TIMEFRAME

```
Daily  → Arah utama / MONITOR ONLY
  H4  → Trend context (butuh VR dari H1)
  H1  → Confluence (butuh VR dari M30)
  M30 → KEY entry TF (butuh VR dari M15)
  M15 → Entry execution (butuh VR dari M5)
  M5  → CF / trigger terkecil
```

- **Daily**: Hanya untuk bias arah. Tidak dientry langsung.
- **H4**: Trend. Entry saat VR (H1) dan CF terjadi.
- **M30 ⚡**: TF paling sering jadi entry utama di sistem ini.
- **M15**: TF eksekusi entry, dikonfirmasi CF dari M5.

---

## MEMBACA DASHBOARD CMP ENGINE v6.3

Kolom dashboard:

| Kolom | Artinya |
|-------|---------|
| TF | Timeframe |
| CMP MASTER | Arah CMP aktif (BUY / SELL) |
| VALID RETRACEMENT | VR sudah terjadi? (WAIT = belum, BUY/SELL = sudah) |
| CONFIRMATION | CF sudah terjadi? (WAIT = belum) |
| ACTION | Status: MONITOR ONLY / MENUNGGU VR / MENUNGGU CF / **ENTRI** |

**Status ACTION:**
- `MONITOR ONLY` → Daily, hanya baca arah
- `MENUNGGU VR` → CMP terbentuk tapi VR belum
- `MENUNGGU CF` → VR sudah, tunggu CF untuk entry
- `ENTRI ⚡` → Siap entry sekarang

---

## CARA MEMBACA STORYLINE

Urutan bacanya selalu dari atas ke bawah:

1. **Daily** → Apa arah besarnya? SELL atau BUY?
2. **H4** → Sudah VR? Kalau belum, H4 belum actionable.
3. **H1** → Sudah VR? Confluence dengan Daily?
4. **M30** → Sudah VR + CF? Kalau ya → **ENTRI aktif**.
5. **M15** → Sudah VR? Kalau ya → bisa eksekusi M15.
6. **Minor SNR paling kanan** → Di mana harga sekarang relatif terhadap swing terbaru?

### Contoh Storyline Bearish:
```
Daily SELL → H4 SELL tapi belum VR → H1 SELL belum VR
→ M30 SELL sudah VR (BUY M15) + CF (SELL M5) = ENTRI M30
→ Entry SELL di minor SNR atas paling kanan
→ Target: SNR lama di bawah sebagai TP
```

---

## MANAJEMEN POSISI

| Level harga | Aksi |
|-------------|------|
| Entry terisi | Hold, monitor CF berikutnya |
| Harga ±50% ke TP1 | Geser SL ke BEP (break even) |
| TP1 tercapai | Ambil 50% profit, geser SL ke entry area |
| TP2 tercapai | Close semua |
| CF berlawanan muncul | Evaluasi: potensi reversal, pertimbangkan exit |

**TP target** = SNR lama di arah CMP (bukan minor SNR paling kanan).

---

## FUNDAMENTAL SNR — LAYER INSTITUTIONAL

Fundamental SNR adalah level harga yang terbentuk dari **keputusan institusional** — bukan dari swing teknikal biasa. Level ini diwatch oleh bank, hedge fund, dan market maker sehingga sering menjadi magnet dan reversal point yang kuat.

### Jenis Fundamental SNR (dari tinggi ke rendah kepentingan)

| Level | Keterangan | Kepentingan |
|-------|------------|-------------|
| **PDH / PDL** | Previous Day High / Low | ⭐⭐⭐⭐⭐ |
| **PWH / PWL** | Previous Week High / Low | ⭐⭐⭐⭐⭐ |
| **Round Number** | 4400, 4450, 4500 (tiap 50 pts) | ⭐⭐⭐⭐ |
| **Half Round** | 4425, 4475, 4525 (tiap 25 pts) | ⭐⭐⭐ |
| **Daily Open** | Harga open candle Daily hari ini | ⭐⭐⭐⭐ |
| **Weekly Open** | Harga open candle Weekly | ⭐⭐⭐⭐ |
| **Session H/L** | High/Low sesi Asia, London, NY | ⭐⭐⭐ |
| **PMH / PML** | Previous Month High / Low | ⭐⭐⭐⭐ |
| **Event SNR** | Spike level post-NFP/FOMC/CPI | ⭐⭐⭐⭐⭐ |

### Event SNR — Level Permanen dari Berita Besar
- **NFP** (Jumat pertama tiap bulan) → spike gold = SNR permanen berminggu-minggu
- **FOMC** (tiap 6-7 minggu) → reaction high/low = institutional reference
- **CPI** (tiap bulan) → level sebelum/sesudah rilis = order cluster
- Level ini tidak hilang sampai ada catalyst baru yang lebih besar

### Fungsi Fundamental SNR dalam Daily Deploy

| Situasi | Fungsi |
|---------|--------|
| CMP terbentuk DI AREA fundamental SNR | Entry lebih valid — institutional confluence |
| Minor SNR paling kanan ada DI/DEKAT fundamental SNR | Entry zone berkualitas tinggi |
| TP target = fundamental SNR berikutnya | TP lebih reliable — bukan asal tebak |
| CMP breakout MENEMBUS fundamental SNR | Momentum sangat kuat — lanjutkan posisi |
| Harga DITOLAK di fundamental SNR | Potential reversal — waspadai CF berlawanan |

---

## SIAPA YANG BAGI VR — INDIKATOR KEKUATAN MOMENTUM

> Saat CMP breakout terjadi, SEMUA TF di bawahnya breakout di waktu yang SAMA — karena itu 1 candle yang sama, hanya dilihat dari lensa TF berbeda.

VR akan datang dari salah satu TF. **Siapa yang pertama bagi VR = indikator seberapa kuat momentum TF di atasnya.**

### Prinsip:
**Semakin kecil TF yang bagi VR → semakin kuat momentum → semakin panjang gerakan.**

### Tabel Kekuatan:

| VR datang dari | TF di atas masih | Kekuatan momentum | Gerakan expected | Entry |
|---------------|-----------------|-------------------|-----------------|-------|
| M1 | M5 sangat kuat | ⭐⭐⭐⭐⭐ Sangat kencang | Panjang banget | CF M1 |
| M5 | M15 masih kuat | ⭐⭐⭐⭐ Kencang | Panjang | CF M1 |
| M15 | M30 masih kuat | ⭐⭐⭐ Moderat | Medium | CF M5 |
| M30 | H1 mulai lemah | ⭐⭐ Melemah | Pendek | CF M15, hati-hati |
| H1 | H4 konfirmasi balik | ⭐ Hampir habis | Reversal besar | Waspada, cari arah baru |

### Contoh Real:
```
H1 BUY terbentuk → semua TF (M30/M15/M5/M1) juga BUY di waktu bersamaan
         ↓
Tunggu VR muncul — siapa yang pertama balik?
         ↓
VR dari M5 (M5 turun dulu, M15/M30 masih naik)
         ↓
H1 masih SANGAT kencang naik (VR hanya dari M5 = TF kecil)
         ↓
Tunggu CF M1 (satu level di bawah yang bagi VR)
         ↓
ENTRI BUY — TP panjang karena M15/M30 masih solid
```

### Peta VR → CMP Aktif → CF:

| VR dari | CMP yang sedang RUNNING | Tunggu CF dari | Highrisk CF |
|---------|------------------------|----------------|-------------|
| M1 bagi VR | **M5 CMP aktif** | M1 CF | — |
| M5 bagi VR | **M15 CMP aktif** | M5 CF | M1 CF |
| M15 bagi VR | **M30 CMP aktif** | M15 CF | M5 CF |
| M30 bagi VR | **H1 CMP aktif** | M30 CF | M15 CF |
| H1 bagi VR | **H4 CMP aktif** | H1 CF | M30 CF |

### VR dan CF adalah CMP di TF mereka sendiri:

> **VR bukan sekadar sinyal balik — VR adalah CMP breakout di TF yang lebih rendah. CF juga sama. Sistem ini fractal.**

```
H1 CMP BUY
  └── VR = M30 CMP SELL  (breakout SELL di M30 itu sendiri)
        └── VR M30 = M15 CMP BUY  (breakout BUY di M15 itu sendiri)
              └── VR M15 = M5 CMP SELL  (breakout SELL di M5 itu sendiri)
                    └── VR M5 = M1 CMP BUY  (breakout BUY di M1 itu sendiri)
                          └── CF M1 = M1 CMP SELL → ENTRI highrisk H1 BUY
```

Inilah kenapa entry M1 CF bukan noise — itu adalah CMP legitimate di M1, yang merupakan CF dari M5 CMP, yang merupakan CF dari M15 CMP, yang merupakan CF dari M30 CMP (VR H1). Semuanya terhubung dalam 1 struktur fractal.

### Aturan Validasi CF:
> **Selama CMP aktif TIDAK FLIP → CF masih valid → entry boleh dilakukan.**
> **Jika CMP flip sebelum CF datang → setup BATAL → reset, tunggu CMP baru.**

```
Contoh:
  M5 bagi VR → M15 CMP BUY aktif
       ↓
  Tunggu CF M5 (atau M1 highrisk)
       ↓
  Cek: apakah M15 CMP masih BUY? (belum flip ke SELL?)
  ├── M15 CMP masih BUY → CF valid → ENTRI ✅
  └── M15 CMP sudah flip ke SELL → setup BATAL ❌ → tunggu siklus baru
```

### Cara Membaca "Siapa yang Bagi VR":
1. Setelah CMP breakout, monitor TF dari bawah (M1) ke atas
2. TF mana yang PERTAMA breakout berlawanan? → itu yang bagi VR
3. TF satu level di atas yang bagi VR = CMP yang sedang running/aktif
4. Tunggu VR selesai → tunggu CF → cek CMP aktif belum flip → ENTRI

---

## GRADING SETUP — SKENARIO TERBAIK

Gabungan Daily Deploy + Fundamental SNR menghasilkan grading kualitas:

### Grade A+ (Probability Tertinggi)
```
✓ Daily CMP searah
✓ M30/M15 ENTRI aktif (VR + CF complete)
✓ Entry di minor SNR paling kanan
✓ Minor SNR entry BERTEPATAN dengan Fundamental SNR (PDH/PDL, round number)
✓ TP target = Fundamental SNR berikutnya
```
→ **Full size entry. Aggressive hold.**

### Grade A (Probability Tinggi)
```
✓ Daily CMP searah
✓ M30/M15 ENTRI aktif
✓ Entry di minor SNR paling kanan
✗ Entry tidak di Fundamental SNR (tapi tidak berlawanan)
✓ TP target ada Fundamental SNR dalam range
```
→ **Normal size entry. Standar manajemen.**

### Grade B (Probability Sedang)
```
✓ Daily CMP searah
✓ M30 ENTRI aktif
✗ Entry minor SNR biasa, tidak ada confluence fundamental
```
→ **Kecil size. Tight SL. Quick TP.**

### Grade C (Highrisk / Skip)
```
- M1/M5 CF entry tanpa M30 confluence
- Entry berlawanan dengan Daily CMP
- Entry di area antara fundamental SNR (no man's land)
```
→ **Skip atau scalp kecil dengan sadar risiko.**

---

## CARA BACA CONFLUENSI SEBELUM ENTRY

Sebelum entry, checklist:

```
1. Daily arah?           → SELL / BUY
2. M30 ACTION?           → ENTRI / MENUNGGU
3. Minor SNR paling kanan ada di mana?
4. Ada Fundamental SNR di dekat entry? (dalam 5-10 pts)
   - PDH/PDL?
   - Round number?
   - Weekly open/high/low?
5. TP target = Fundamental SNR mana?
6. SL di bawah/atas minor SNR + buffer
→ Grade berapa? → Tentukan size
```

---

## TUGAS CLAUDE DALAM SISTEM INI

1. **Baca dashboard CMP Engine** → identifikasi ACTION per TF
2. **Baca minor SNR paling kanan** → dari Pine labels indicator (swing terbaru di chart)
3. **Baca storyline** → TF mana yang aktif? VR di mana? CF sudah?
4. **Komunikasikan potensi** → bukan memaksakan framework lain
5. **Tandai SNR lama** sebagai barrier/TP — bukan entry
6. **Jangan** pakai SNR algorithm eksternal, Fibonacci, dsb kecuali diminta
7. **Gambar di chart** hanya kalau diminta: hline entry/SL/TP + note posisi

---

## CATATAN PENTING

- **VR hanya SEKALI** per siklus — setelah VR terjadi tidak bisa di-reset kecuali CMP baru terbentuk
- **CF bisa berkali-kali** — setiap CF adalah peluang entry baru searah CMP
- **Candle CLOSE** adalah segalanya — bukan wick, bukan body
- **M30 adalah TF paling sering aktif** — kebanyakan setup masuk dari M30 ENTRI
- **Jika posisi berlawanan dengan M30 ENTRI** → hati-hati, momentum melawan posisi
- **CMP lama** = barrier / TP zone. **CMP terbaru (paling kanan)** = entry reference.

---

## REFERENSI FILE

| File | Fungsi |
|------|--------|
| `read_indicators.mjs` | Baca dashboard CMP Engine + Pine labels + tables |
| `reanalysis.mjs` | Scan minor SNR paling kanan H4/H1/M15 |
| `latest.mjs` | Monitor posisi aktif + last 6 candles |
| `clear_draw.mjs` | Hapus semua drawing di chart |
| `update_entry.mjs` | Gambar entry/SL/TP + note posisi di chart |

**Launch TradingView dengan CDP:**
```powershell
$exe = (Get-AppxPackage *TradingView*).InstallLocation + "\TradingView.exe"
Start-Process $exe -ArgumentList "--remote-debugging-port=9222"
```

**Run analisa:**
```powershell
cd "F:\MCP TRADING VIEW\tradingview-mcp-jackson"
node read_indicators.mjs
```
