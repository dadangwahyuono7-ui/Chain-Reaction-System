# TASK ORDER (KRITIS — KOREKSI ARSITEKTUR) — Non-Rigid Market Reading
### Doktrin ini MENGGANTIKAN cara pakai Chain Reaction System V2 (Step 1-4 AND-gate). Modul-modul yang sudah dibangun TETAP DIPAKAI, tapi sebagai OBSERVASI, bukan GATE.

---

## 0. PERINGATAN UNTUK AGENT — BACA SEBELUM MENYENTUH KODE APA PUN

Dokumen "COMMANDER DADANG — MARKET READING DOCTRINE" (dilampirkan penuh oleh Dadang) adalah **doktrin utama** yang mengoreksi kesalahan mendasar dalam arsitektur yang sudah dibangun sejauh ini. Baca doktrin itu penuh sebelum lanjut.

**Sesuai instruksi eksplisit dari doktrin (Bagian 25):** kode yang ada sekarang di `decision_engine.py` dan `CMP Zone Engine` (khususnya fungsi `IsWithinActiveCMPZone()` sebagai hard boolean skip, dan struktur "Step 1 CMP Zone → Step 2 Liquidity → Step 3 Footprint → Step 4 ENTRY" dari Chain Reaction System V2) **HARUS DI-FLAG SEBAGAI RIGID LOGIC**. Ini persis pola yang doktrin larang secara eksplisit di Bagian 2, 11, dan 18.

**JANGAN memperluas logic rigid tersebut sebelum direview ulang sesuai task ini.**

---

## 1. INTI KOREKSI

```
SALAH (yang sudah dibangun, Chain Reaction V2):
    CMP Zone VALID
        AND Liquidity VALID
        AND Footprint VALID
        → ENTRY
    (kalau satu gagal, SKIP TOTAL — tidak ada nuansa)

BENAR (doktrin ini):
    CMP, VR, CF = STATUS/LABEL KONTEKS, bukan syarat AND
    Wall, CVD, Footprint = DATA TAMBAHAN, bukan gate boolean
    Sistem MEMBACA kondisi market secara holistik, menghasilkan
    LAPORAN KONTEKS (Bagian 22 doktrin), BUKAN keputusan
    otomatis dari rangkaian IF/AND
```

**Prinsip inti yang harus dipegang (dikutip langsung dari doktrin):**
- "Status ≠ Signal" — CMP/VR/CF tidak pernah diimplementasikan sebagai BUY/SELL signal otomatis
- "Tidak ada mandatory sequence" — CMP→VR→CF→ENTRY BUKAN alur wajib
- "Conflict adalah informasi" — kalau CMP bilang BUY tapi order flow bilang bearish, sistem HARUS tampilkan `CONTEXT CONFLICT`, bukan memaksa salah satu menang
- "Market boleh membatalkan hipotesis" — setiap status adalah observasi/hipotesis, bukan kebenaran mutlak, harus bisa berubah jadi `INVALIDATED`/`WEAKENED`/`CONFLICT`/`CONFIRMED`
- "Location penting, tapi bukan hakim mutlak" — CF di luar zona relevan BUKAN otomatis salah, itu cuma informasi kualitas konteks yang berbeda (Bagian 21, Case D)

---

## 2. YANG TETAP DIPAKAI (Tidak Dibuang, Cuma Beda Peran)

Semua modul berikut **tetap jalan sebagai penghasil OBSERVASI/DATA**, TIDAK diubah logic internalnya, cuma perannya di sistem yang berubah — dari "gate boolean" jadi "input ke laporan konteks":

```
wall_detector.py, spoof_filter.py, liquidity_classifier.py
    → tetap menghasilkan data wall (posisi, status LTHL/STHL,
      confidence) — SEKARANG dipakai sebagai bagian dari
      "ORDER FLOW" di laporan konteks (Bagian 22), bukan syarat
      lolos/gagal

footprint_delta.py (CVD, delta)
    → tetap menghasilkan data momentum — SEKARANG dipakai sebagai
      bagian dari "PRICE RESPONSE" dan "ORDER FLOW" di laporan
      konteks

CMP Zone Engine (native MQL5, termasuk SNR HTF Zone dari
    task order sebelumnya)
    → tetap menghitung status CMP/VR/CF per timeframe dan
      rectangle zona — SEKARANG dipakai sebagai "LOCATION" dan
      "CMP/VR/CF STATUS" di laporan konteks, BUKAN sebagai
      IsWithinActiveCMPZone() yang men-skip total wall di luar
      zona

basis_converter.py, market_recorder.py, EA MT5 receiver,
    Bookmap Bridge Recorder (Phase 1)
    → TIDAK TERPENGARUH sama sekali oleh koreksi ini — ini murni
      soal bagaimana data-data di atas DIRANGKAI jadi keputusan,
      bukan soal bagaimana data itu DIKUMPULKAN
```

---

## 3. YANG BERUBAH: `decision_engine.py` Menjadi Context Report Generator

**Buang struktur AND-chain lama.** Ganti dengan struktur laporan konteks, PERSIS mengikuti format Bagian 22 doktrin:

```python
class MarketContextReport:
    # --- MARKET CONTEXT ---
    primary_direction: str        # BUY / SELL / NEUTRAL (dari CMP
                                   # timeframe tertinggi yang relevan)
    cmp_status: dict               # status CMP per timeframe
    vr_status: dict                 # status VR per timeframe (LABEL,
                                     # bukan gate)
    cf_status: dict                 # status CF per timeframe (LABEL,
                                     # bukan gate)

    # --- LOCATION ---
    nearest_relevant_zone: float
    location: str                   # INSIDE / ABOVE / BELOW /
                                     # BETWEEN / NONE
    distance_to_zone: float

    # --- PRICE RESPONSE ---
    current_structure: str          # BULLISH / BEARISH / RANGE /
                                     # TRANSITION
    momentum: str

    # --- ORDER FLOW ---
    delta: float
    cvd: float
    footprint_summary: str
    absorption: str
    liquidity_walls: list           # data wall_detector, TIDAK
                                     # difilter berdasar lokasi zona

    # --- CONTEXT EVALUATION ---
    context_state: str              # ALIGNED / CONFLICT / WEAK /
                                     # TRANSITION / UNKNOWN

    # --- RISK ---
    invalidation_price: float
    invalidation_condition: str
    risk_value: float

    # --- DECISION ---
    decision: str                   # BUY / SELL / WAIT / INVALID
```

**Bagaimana `context_state` dan `decision` dihasilkan — INI YANG PALING PENTING:**

TIDAK BOLEH ditulis sebagai:
```python
# SALAH — persis pola yang dilarang doktrin Bagian 11
if cmp_status == "BUY" and vr_status == True and cf_status == True:
    decision = "BUY"
```

HARUS ditulis sebagai evaluasi kontekstual yang mempertimbangkan **kesesuaian antar sumber data**, mengikuti pola contoh di Bagian 23 doktrin (Case A-D):

```
- Primary direction (dari CMP timeframe besar) DAN price response
  (dari timeframe kecil di lokasi relevan) SEARAH, meski status
  formalnya masih VR (bukan CF) → context_state = ALIGNED,
  decision bisa BUY/SELL (Case A doktrin: JANGAN tunggu CF)

- Status formal bilang CF SELL, tapi order flow/price response
  menunjukkan buyer dominan, absorption buyer, resistance tertembus
  → context_state = CONFLICT, decision = WAIT (JANGAN paksa SELL
  hanya karena label CF SELL — Case B & Bagian 14)

- Primary direction, location, DAN price response semua melemah/
  berlawanan → context_state = TRANSITION atau WEAK, decision
  perlu re-evaluasi primary_direction itu sendiri (Case C)

- Sinyal (misal CF) muncul JAUH dari zona relevan → BUKAN otomatis
  invalid, tapi dicatat location = OUTSIDE, kualitas konteks
  diturunkan, sistem menunggu price response lebih lanjut sebelum
  memutuskan (Case D)
```

**Implementasi konkret yang disarankan:** karena ini pada dasarnya adalah *scoring/pembobotan kontekstual*, bukan boolean, gunakan pendekatan yang MIRIP dual-wall confidence scoring yang sudah pernah dirancang sebelumnya (tapi jangan sebagai gate keras) — tiap sumber (primary direction, location, price response, order flow) memberi kontribusi ke `context_state`, dan `context_state` itulah yang jadi dasar `decision`, bukan AND-chain dari status mentah.

---

## 4. LOKASI TETAP RELEVAN, TAPI SEBAGAI KUALITAS BUKAN GATE (Revisi ke `IsWithinActiveCMPZone()`)

Sesuai Bagian 21 doktrin: "Jangan menganggap: CF di luar zona = salah. Lebih tepat: CF terjadi di luar zona → contextual quality berbeda."

**Revisi fungsi ini:**
```
SEBELUM (rigid gate):
    IsWithinActiveCMPZone(wall_price) → bool
    → kalau false, wall di-SKIP TOTAL, tidak diproses sama sekali

SESUDAH (kualitas kontekstual):
    GetZoneContext(wall_price) → {
        location: "INSIDE" | "OUTSIDE" | "NEAR",
        distance_to_nearest_zone: float,
        confluence_count: int  (tetap dipakai dari 3B sebelumnya)
    }
    → wall TETAP dicatat dan ditampilkan APAPUN lokasinya, tapi
      informasi lokasi ini masuk sebagai bagian dari LOCATION di
      context report, mempengaruhi context_state, TIDAK
      menghilangkan data sama sekali
```

Dashboard/EA tetap boleh secara VISUAL membedakan (misal wall di luar zona relevan digambar lebih redup/kecil) — itu bagian dari UX yang sah, BUKAN filtering data yang menghilangkan informasi.

---

## 5. REVIEW ULANG — Daftar yang Perlu Di-flag Sesuai Instruksi Doktrin Bagian 25

Agent WAJIB me-review file-file berikut dan menandai bagian mana yang berisi rigid AND-chain/mandatory sequence, sebelum melanjutkan pengembangan apa pun di atasnya:

```
[ ] decision_engine.py — Step 1→2→3→4 AND-chain dari Chain
    Reaction V2 (TASK_ORDER lama) — HARUS DIROMBAK sesuai
    Bagian 3 di atas
[ ] CMP Zone Engine MQL5 — fungsi IsWithinActiveCMPZone()
    sebagai hard skip — HARUS DIROMBAK sesuai Bagian 4 di atas
[ ] Modul manapun lain yang mengasumsikan "VR harus diikuti CF
    baru boleh entry", atau "CMP master menentukan arah entry
    secara mutlak" (dari diskusi-diskusi sebelumnya soal
    VR_ENTRY/CF_CONFIRMED sebagai gate) — SEMUA bentuk gate
    kaku ini harus di-flag dan direvisi ke model context report
```

---

## 6. YANG TIDAK BERUBAH (Penegasan, Supaya Tidak Disalahpahami sebagai "Mulai dari Nol")

```
- Backend Bookmap Bridge Recorder (Phase 1, seluruh 10 modul,
  RAW vs DERIVED, health monitor) — TIDAK TERPENGARUH, tetap
  jalan seperti dirancang
- wall_detector.py, spoof_filter.py, liquidity_classifier.py,
  footprint_delta.py — LOGIC INTERNAL tidak berubah, cuma
  cara HASILNYA dipakai di decision_engine yang berubah
- CMP Zone Engine — perhitungan CMP/VR/CF per timeframe (native
  MQL5, port dari Pine) TIDAK berubah caranya menghitung, cuma
  cara STATUSNYA dipakai untuk keputusan yang berubah
- EA MT5 (TCP receiver), basis_converter, market_recorder —
  semua tidak berubah
- Auto-execute (5 gatekeeper, demo-only) — prinsip fail-safe
  TETAP BERLAKU, cuma sekarang keputusan ENTRY yang jadi input
  gatekeeper itu datang dari context report, bukan AND-chain
```

---

## 7. INSTRUKSI RINGKAS UNTUK AGENT

> "PENTING — review dulu dokumen 'COMMANDER DADANG — MARKET READING DOCTRINE' secara penuh sebelum menyentuh kode apa pun terkait decision engine. Doktrin ini mengoreksi kesalahan arsitektur mendasar: CMP/VR/CF TIDAK BOLEH diimplementasikan sebagai mandatory AND-chain sequence (CMP→VR→CF→ENTRY) atau sebagai boolean gate yang men-skip data. Flag decision_engine.py yang sekarang (struktur Step 1-4 dari Chain Reaction System V2) dan fungsi IsWithinActiveCMPZone() di CMP Zone Engine sebagai RIGID LOGIC sesuai instruksi eksplisit doktrin Bagian 25 — JANGAN diperluas sebelum direview. Rombak decision_engine.py menjadi generator MarketContextReport (struktur lengkap ada di Bagian 3 dan Bagian 9 task order ini, mengikuti format Bagian 22 doktrin: Market Context, Location, Price Response, Order Flow, Context Evaluation, Risk, Decision). CMP/VR/CF menjadi LABEL/STATUS yang masuk laporan, bukan syarat lolos. Wall, CVD, footprint tetap dihitung oleh modul yang sudah ada (JANGAN diubah logic internalnya) tapi sekarang menjadi DATA MASUKAN ke context report, bukan gate boolean — wall di luar zona CMP TIDAK LAGI di-skip total, tapi dicatat dengan informasi lokasi (INSIDE/OUTSIDE/NEAR + distance) yang mempengaruhi context_state (ALIGNED/CONFLICT/WEAK/TRANSITION/UNKNOWN), bukan menghilangkan datanya. Decision (BUY/SELL/WAIT/INVALID) dihasilkan dari evaluasi holistik context_state, bukan AND-chain dari status individual — ikuti pola Case A-E di Bagian 23 doktrin dan Bagian 9 task order ini sebagai contoh konkret cara membaca konflik antar sumber data. WAJIB IMPLEMENTASI CONFIDENCE DUA LAPIS (Bagian 9, subbagian 'Koreksi Penting'): local_cascade_confidence (kekompakan TF-TF kecil, yang sudah ada di Cockpit sekarang) HARUS dipisah dari root_alignment (apakah cascade ini align atau melawan primary context tertinggi seperti D1) — effective_mode (CF_STYLE vs VR_STYLE, yang menentukan aturan TP/hold/tambah posisi) ditentukan dari root_alignment, BUKAN dari local_cascade_confidence semata, karena confidence lokal yang tinggi bisa menyesatkan trader jika root context sebenarnya masih melawan. Update tampilan Cockpit agar menampilkan kedua lapis ini secara eksplisit (bukan cuma 1 angka confidence gabungan). Semua modul lain (Bookmap Bridge Recorder Phase 1, wall_detector, spoof_filter, liquidity_classifier, footprint_delta, EA MT5, basis_converter) TIDAK BERUBAH — ini murni koreksi di lapisan pengambilan keputusan paling atas."

---

## 9. INTI PALING PENTING — VR/CF = MODE TRADING, BUKAN IZIN ENTRY

Ini kalimat yang merangkum seluruh doktrin di atas, dan HARUS jadi acuan utama saat mengimplementasikan `MarketContextReport`:

```
STATUS (VR/CF) = PENANDA MODE, BUKAN GATE BOLEH/TIDAK BOLEH ENTRY

CF = trader sedang bertransaksi SEARAH konteks utama (primary
     direction)
     → mode: boleh lebih agresif, TP lebih panjang, boleh hold
        posisi lebih lama, boleh menambah posisi (pyramiding)

VR = trader sedang bertransaksi DI DALAM RETRACEMENT terhadap
     konteks utama
     → TETAP BOLEH ENTRY — VR TIDAK PERNAH BERARTI "DILARANG
        ENTRY"
     → mode: TP lebih pendek, lebih waspada, exit lebih cepat
        begitu ada bukti hipotesis retracement ini gagal
```

### Contoh Kasus Nyata (dari live trading Dadang, dijadikan Case E)

```
Setup:
    D1: BUY [BASE]           ← primary context terjauh
    H4: SELL [VR]            ← retrace terhadap D1
    H1: SELL [CF]            ← searah H4
    M30: SELL [CF]           ← searah H1
    M15: BUY [VR]            ← retrace terhadap M30
    M5: BUY [WAIT]           ← breakout buy, price response

Lokasi: harga sampai di barrier CMP H4 LAMA (level breakout H4
    di masa lalu, sekarang berfungsi sebagai support) — INI BUKAN
    level sembarang, ini level yang PERNAH signifikan secara
    struktural (nyambung ke wall_memory/zone map yang menyimpan
    level historis, bukan cuma real-time)

Keputusan trader: BUY di M5, MESKIPUN status cascade besar (H1,
    M30) masih SELL — karena lokasi (barrier H4 lama) + price
    response (BO buy M5 tepat di situ) memberi alasan struktural
    yang valid, meski status formalnya "cuma" VR/WAIT.

Titik keputusan berikutnya — M30 CANDLE CLOSE di area itu:
    │
    ├── M30 CLOSE flip jadi BUY
    │      → hipotesis "M5 BUY sanggup flip M30" TERBUKTI
    │      → hold posisi, upgrade mode dari VR ke lebih percaya
    │         diri (mendekati CF)
    │
    └── M30 CLOSE GAGAL flip (tetap SELL)
           → TAKE PROFIT SEGERA saat itu juga (bukan tunggu SL
              kena) — exit di titik paling awal yang membuktikan
              hipotesis salah, bukan menunggu bukti lebih jauh
           → SEKALIGUS: kegagalan ini adalah INFORMASI TAMBAHAN
              yang memperkuat primary direction SELL dari H4 —
              karena H4 memang masih SELL, kegagalan barrier lama
              menahan itu KONSISTEN dengan konteks besar
           → SWITCH MODE: dari "mencari peluang BUY" ke "mencari
              peluang SELL" — sekarang menunggu BO sell balik di
              M5/M15/M30 di area yang sama atau berikutnya
```

**Implikasi teknis ke `MarketContextReport` (Bagian 3):** tambahkan field berikut untuk menangkap pola ini:

```python
class MarketContextReport:
    # ... (field yang sudah ada di Bagian 3)

    # --- HYPOTHESIS TRACKING (untuk kasus VR yang mencoba flip) ---
    active_hypothesis: str          # contoh: "M5 BUY berpotensi
                                     # flip M30 SELL"
    hypothesis_decision_point: dict # { "tf": "M30",
                                     #   "trigger": "bar_close",
                                     #   "reference_level": float }
    hypothesis_status: str          # PENDING / CONFIRMED / FAILED

    # --- MULTI-TF PRICE RESPONSE (bukan cuma 1 TF fix) ---
    price_response_by_tf: dict      # { "M5": "...", "M15": "...",
                                     #   "M30": "..." } — trader
                                     # (atau logic non-rigid) yang
                                     # pilih mana yang paling
                                     # meyakinkan SAAT ITU, bukan
                                     # selalu dari 1 TF yang sama
```

**Aturan penting:** `hypothesis_decision_point` HARUS berbasis **bar-close** dari timeframe yang relevan (di contoh ini M30), bukan pergerakan tick real-time — sesuai cara kerja CMP Zone Engine yang sudah bar-close driven. Ini titik re-evaluasi wajib, bukan exit otomatis oleh sistem — sistem memberi ALERT/notifikasi tegas ke trader di titik itu, keputusan akhir tetap di tangan trader (konsisten dengan seluruh doktrin: sistem membaca, bukan memutuskan secara otomatis untuk trader).

**Pemilihan TF untuk `hypothesis_decision_point` juga situasional, TIDAK BOLEH di-hardcode ke "selalu anak langsung dari parent TF"** (misal H1 untuk H4). Kadang TF anak langsung terlalu lambat bereaksi (H1 relatif terhadap H4 yang VR-nya berpotensi jalan jauh/dalam) — dalam kasus begitu, trader bisa memilih TF lebih kecil (misal M30) sebagai gate praktis, karena TF itu yang akan lebih dulu memberi sinyal tepat waktu saat harga menguji ulang level acuan (misal level M30 sebelumnya, saat H4 gagal menembus CMP BUY H4 lama dan berbalik naik). Field `hypothesis_decision_point.tf` harus bisa diisi TF manapun yang trader anggap paling responsif untuk situasi saat itu — bukan field yang nilainya ditentukan otomatis secara kaku dari posisi hierarki TF.

### Kriteria Sukses Eksekusi & Confluence Zona HTF yang Berdekatan

**Definisi "berhasil" untuk eksekusi di TF kecil (misal M5) di area penting H4:** M5 dianggap **berhasil** bukan sekadar karena harga memantul sedikit, tapi karena M5 **sanggup merubah/flip arah M30**. Ini kriteria konkret untuk `hypothesis_status` berubah dari PENDING ke CONFIRMED.

**Kenapa M30 sering menjadi tolok ukur yang tepat (bukan pilihan sembarang):** area CMP H4 SERING sejajar atau berdekatan dengan area CMP H1 (kadang overlap, kadang cuma berdekatan). Ini adalah bentuk **confluence** tambahan (sejalan dengan doktrin poin 9: "makin banyak SNR HTF berkumpul, makin kuat area itu") — kalau H4 dan H1 "setuju" di area yang sama, maka M30 (anak langsung dari H1) menjadi proxy yang andal untuk membaca apakah reaksi di area itu benar-benar bermakna sampai ke level H1, bukan sekadar noise sesaat di M30 sendiri.

**Implikasi ke `MarketContextReport`:** tambahkan pengecekan confluence antar-zona HTF yang berdekatan (bukan cuma overlap presisi, tapi juga "dekat" dalam rentang tertentu) sebagai bagian dari `location` — kalau zona H4 dan H1 yang sedang aktif ternyata berdekatan/overlap, catat sebagai confluence tambahan, dan ini memperkuat alasan memilih TF anak dari H1 (M30) sebagai `hypothesis_decision_point.tf` yang lebih andal dibanding TF lain yang dipilih tanpa dasar confluence ini.

### Pola Pengujian Berulang (Recursive HTF Level Test) — Bukan Sekali Coba Lalu Selesai

Level struktural penting (seperti CMP H4 lama) sering diuji **lebih dari sekali** sebelum akhirnya benar-benar jebol ke satu arah. Setiap kali harga menyentuh level itu, itu adalah **kesempatan entry baru**, bukan cuma "percobaan pertama gagal = selesai":

```
M5 BO SELL → menguji CMP H4 LAMA
        │
        ▼ (H4 close)
        │
        ├── TIDAK BREAK (support H4 lama masih dihormati)
        │      → market cenderung NAIK LAGI DULU
        │      → potensi M30 FLIP BUY → target H1 BUY → berharap
        │         H4 balik BUY → jadi CF terhadap D1
        │      → ENTRY BUY didapat justru dari momen kegagalan
        │         H4 jebol level lamanya
        │
        └── BREAK (level lama jebol)
               → cascade turun terkonfirmasi

KALAU SETELAH NAIK M30 TIDAK JADI FLIP (percobaan gagal juga):
        → BUKAN akhir, tapi ULANGI — H4 akan MENGUJI ULANG level
           yang sama lagi
        → Setiap oscillasi/pantulan di level itu = kesempatan
           entry baru dengan pola hipotesis+decision point yang
           SAMA, sampai akhirnya salah satu sisi benar-benar jebol
```

**Peran monitoring "pembentukan candle" (real-time, bukan cuma tunggu close):** selama candle H4 (atau TF acuan lainnya) masih terbentuk/berjalan, footprint dan CVD real-time berfungsi sebagai **petunjuk dini** — sesuai peran aslinya di Chain Reaction V2 (footprint = timing, bukan arah). Contoh: kalau delta buyer mulai dominan padahal candle H4 belum close, itu clue awal ke arah mana kemungkinan besar candle itu akan close, sebelum bar-close event itu sendiri terjadi. Ini tidak menggantikan aturan "keputusan resmi tetap di bar-close" (Bagian 9 sebelumnya) — real-time footprint di sini berfungsi sebagai **antisipasi**, bukan pemicu keputusan final.

**Implikasi ke `MarketContextReport`:** field `hypothesis_status` (PENDING/CONFIRMED/FAILED) perlu mendukung siklus berulang — begitu satu hipotesis FAILED di satu titik uji, sistem boleh langsung membuka `active_hypothesis` baru untuk pengujian berikutnya di level struktural yang sama, bukan berhenti setelah satu kali gagal.

### Aturan Otoritas "Break" — Hanya TF Pemilik Level yang Berhak Menentukan

**Ini aturan ketat yang wajib ditegakkan di kode, bukan sekadar pedoman:** status "jebol/break" suatu level struktural HANYA BOLEH ditentukan oleh **candle close pada timeframe yang memiliki level itu** — bukan oleh candle close di timeframe manapun di bawahnya, tidak peduli seberapa banyak.

```
Level CMP H4 lama = MILIK H4
    → HANYA candle H4 sendiri, saat close, yang berhak
       menentukan status level ini BREAK atau TIDAK

Candle H1/M30/M15/M5 yang close di luar level itu:
    → BUKAN bukti break, TIDAK PEDULI BERAPA BANYAK candle TF
       kecil yang close di luar level tersebut
    → Selama candle H4 SENDIRI belum close melewati level itu,
       status level = BELUM BREAK — meski secara visual harga
       "kelihatan" sudah menembus berkali-kali di TF kecil
```

**Kenapa ini wajib ditegakkan ketat:** tanpa aturan ini, sistem rawan salah membaca "level sudah break" hanya karena beberapa candle TF kecil menembus (yang bisa jadi cuma noise/wick sementara), padahal TF pemilik level (H4) belum pernah benar-benar close di sana. Ini bisa memicu sinyal breakout palsu yang terlalu dini.

**Implementasi:** setiap level/zona di `MarketContextReport` (baik dari CMP Zone Engine maupun SNR HTF Zone) harus menyimpan `owning_timeframe` eksplisit, dan fungsi cek "apakah level ini break" WAJIB hanya membaca candle close dari `owning_timeframe` tersebut — bukan dari timeframe manapun yang lebih kecil, berapa pun banyaknya candle yang tampak menembus secara visual di chart TF kecil.

### Sifat Rekursif CMP — Level yang Jebol Menjadi CMP Baru DAN Zona Kunci Berikutnya

Sesuai definisi CMP dari doktrin v0.1 ("CMP = breakout terakhir paling kanan pada tiap TF"), setiap kali sebuah level CMP jebol (sesuai aturan otoritas break di atas), **level itu sendiri langsung menjadi CMP baru untuk arah yang berlawanan** — dan otomatis menjadi **zona kunci berikutnya** yang harus diuji ulang kalau harga ingin membalik arah lagi:

```
CMP BUY H4 lama → JEBOL (H4 close di bawahnya, sesuai owning_timeframe)
        │
        ▼
Level itu → JADI CMP BARU untuk H4 SELL
        │
        ▼
Level yang SAMA → berubah peran jadi RESISTANCE
        │
        ▼
Kapan pun nanti harga ingin naik lagi (bahkan setelah H4 turun
    jauh terlebih dahulu) → level INI yang harus dijebol lagi
    ke atas
        │
        ▼
Kalau level ini GAGAL dijebol ke atas → hampir pasti terjadi
    reaksi kuat ("drama") di situ, karena level ini sekarang
    jadi titik pivot struktural paling signifikan untuk H4
```

**Ini pola rekursif yang berulang di setiap flip CMP, bukan kejadian sekali saja.** Setiap TF terus "mewariskan" level breakout terbarunya sebagai zona kunci berikutnya — rantai level ini yang harus disimpan dan dipantau terus-menerus, bukan cuma 1 level statis.

**Implementasi:** setiap kali `owning_timeframe` suatu level tercatat break (CMP flip), sistem harus otomatis: (1) mencatat level tersebut sebagai CMP baru untuk arah berlawanan pada TF yang sama, (2) menyimpan level ini ke `wall_memory`/zone map sebagai zona kunci dengan peran yang sudah terbalik (resistance↔support), dan (3) menjadikannya kandidat `hypothesis_decision_point` berikutnya untuk pengujian arah balik di masa depan — sesuai pola pengujian berulang yang sudah dijelaskan sebelumnya, kali ini dengan peran level yang sudah terbalik.

---

### Koreksi Penting: Confidence Score Harus Dua Lapis (Local vs Root)

**Masalah nyata yang ditemukan Dadang saat live trading:** setelah M5 gagal flip M30 dan sistem beralih ke SELL, Cockpit menampilkan confidence **80% PREMIUM** untuk SELL SNIPER — padahal **D1 (primary context tertinggi) masih BUY, tidak berubah sama sekali**. Cascade H1-M30-M15-M5 yang sekarang kompak SELL itu HANYA align terhadap H4 (yang statusnya sendiri masih VR terhadap D1) — bukan align terhadap primary context sebenarnya.

**Ini adalah bug logika confidence, bukan cuma nuansa kecil.** Confidence tinggi yang dihitung dari kekompakan TF-TF kecil bisa MENYESATKAN trader untuk memperlakukan entry ini seolah "sekuat CF penuh" (boleh hold lama, boleh tambah posisi, TP lebar), padahal secara root, seluruh cascade SELL ini **tetap VR terhadap D1 BUY** — D1 bisa "menarik balik" cascade ini kapan saja.

**Wajib ditambahkan ke `MarketContextReport`:**

```python
class MarketContextReport:
    # ... (field yang sudah ada)

    # --- CONFIDENCE: DUA LAPIS, JANGAN DIGABUNG JADI 1 ANGKA ---
    local_cascade_confidence: float   # 0-100, seberapa align TF-TF
                                       # kecil satu sama lain (yang
                                       # sudah ada sekarang, contoh:
                                       # 80% dari H1-M30-M15-M5 SELL)
    root_context: str                  # status primary context
                                        # TERTINGGI yang relevan
                                        # (contoh: "D1: BUY")
    root_alignment: str                # ALIGNED / COUNTER
                                        # — apakah cascade SEARAH
                                        # atau MELAWAN root_context
    effective_mode: str                 # CF_STYLE / VR_STYLE
                                         # — ditentukan dari
                                         # root_alignment, BUKAN dari
                                         # local_cascade_confidence
```

**Aturan penentuan `effective_mode` (ini yang menentukan cara pegang risiko, BUKAN angka confidence lokal):**

```
root_alignment == ALIGNED
    → effective_mode = CF_STYLE (boleh agresif, TP lebar, boleh
       hold/tambah posisi) — local_cascade_confidence tinggi DAN
       root juga align, dua-duanya mendukung

root_alignment == COUNTER
    → effective_mode = VR_STYLE, TIDAK PEDULI SEBERAPA TINGGI
       local_cascade_confidence-nya (meski 80%, 90%, berapa pun)
    → TP tetap pendek, TIDAK boleh hold lama, TIDAK boleh nambah
       posisi, tetap waspada root context bisa "menang" kapan saja
    → Local confidence tinggi di sini HANYA berarti "momentum
       jangka pendek kuat", BUKAN berarti "aman untuk trading
       agresif seperti CF penuh"
```

**Dampak ke tampilan Cockpit:** label seperti "SELL SNIPER 80% PREMIUM" berpotensi menyesatkan kalau tidak disertai indikator root alignment. Cockpit harus menampilkan KEDUANYA secara eksplisit — misalnya "SELL SNIPER · Local 80% · Counter-Trend to D1(BUY)" — supaya trader (Dadang) selalu sadar bahwa entry ini, walau lokal terlihat kuat, tetap dalam mode kehati-hatian VR terhadap konteks tertinggi, bukan mode CF penuh.

**Contoh penerapan ke Case E (lanjutan dari kejadian nyata sebelumnya):**
```
Setelah M5 gagal flip M30 → SWITCH ke SELL:
    root_context = "D1: BUY"
    root_alignment = COUNTER (karena D1 masih BUY, SELL ini
                      melawan root)
    local_cascade_confidence = 80% (H1/M30/M15/M5 kompak SELL)
    effective_mode = VR_STYLE (root menang atas local confidence)

    → TP tetap pendek/terukur (bukan target agresif meski local
       confidence tinggi), posisi TIDAK ditambah, tetap monitor
       apakah D1 mulai menunjukkan tanda melemah (baru root_context
       itu sendiri boleh dianggap berubah)
```

---

## 11. PRINSIP OPERASIONAL PENUTUP (Rangkuman Satu Kalimat dari Seluruh Bagian 9-10)

Ini kalimat pemersatu yang menjelaskan KENAPA seluruh detail di Bagian 9 (mode VR/CF, confidence dua lapis, TF gate situasional, pengujian berulang, otoritas break, sifat rekursif CMP) itu penting — semuanya berputar di sekitar 3 peran yang harus dipisah dengan jelas:

```
ARAH (Direction)
    → Diberikan oleh TF acuan yang lebih besar (contoh: H4)
    → Trading TIDAK DILAKUKAN di TF ini — TF ini cuma sumber bias

LOKASI (Location)
    → Area-area penting dari TF acuan itu (CMP lama, CMP baru
       setelah flip, level yang sudah berganti peran
       resistance↔support — hasil dari sifat rekursif CMP di
       Bagian 9)
    → Ini BUKAN tempat eksekusi juga — ini tempat sistem/trader
       MENUNGGU dan MENGAMATI

EKSEKUSI (Execution)
    → Terjadi di timeframe kecil (M5/M15/M30), DIPILIH SECARA
       SITUASIONAL (bukan fix satu TF tertentu — sesuai Bagian 9)
    → Trigger sebenarnya (BO, price response, footprint/CVD)
       muncul di sini, TEPAT SAAT harga sampai di LOKASI yang
       relevan dari ARAH yang sudah diketahui
```

**Implikasi arsitektur:** `MarketContextReport` harus secara eksplisit memisahkan ketiga peran ini sebagai field/section yang berbeda (Market Context untuk ARAH, Location untuk LOKASI, Price Response + Order Flow untuk EKSEKUSI) — jangan pernah mencampur ketiganya jadi satu keputusan tunggal yang kaku. Trader (Dadang) selalu bertanya dalam urutan ini: "H4 arahnya ke mana?" → "Area penting H4 yang mana yang relevan sekarang?" → "Apa yang terjadi di TF kecil saat harga sampai di area itu?" — baru dari situ keputusan diambil.

---

## 12. CATATAN PENTING UNTUK DADANG

Ini adalah pergeseran filosofis yang signifikan dari beberapa iterasi sebelumnya dalam sesi ini (termasuk konsep VR_ENTRY/CF_CONFIRMED sebagai gate, dan Chain Reaction System V2 dengan Step 1-4 AND-chain). Bukan berarti kerja-kerja sebelumnya sia-sia — semua komponen pengumpul data (wall, CVD, CMP per-timeframe, dst) tetap terpakai penuh. Yang berubah adalah **cara komponen-komponen itu dirangkai jadi keputusan**: dari "checklist kaku" menjadi "pembacaan kontekstual holistik", sesuai prinsip inti doktrin ini — sistem membaca market, bukan memaksa market ikut skema sistem.
