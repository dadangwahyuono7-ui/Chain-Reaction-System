# MARKET READING LOGIC — Dokumen Konsep Murni
### Tidak menyebut nama file, fungsi, atau struktur kode apa pun. Ini murni PENJELASAN CARA BACA MARKET yang harus diterjemahkan agent ke dalam engine yang SUDAH ADA SEKARANG (bukan versi lama).

---

## 0. CATATAN UNTUK AGENT

Dokumen ini TIDAK mengasumsikan struktur kode tertentu. Silakan petakan konsep di bawah ini ke bagian engine yang relevan di codebase SAAT INI — jangan mencari file/fungsi dengan nama yang mungkin disebut di percakapan/dokumen lain sebelumnya, karena arsitektur sudah banyak berubah. Fokus HANYA pada logika membaca market yang dijelaskan di sini.

---

## 1. PRINSIP DASAR

CMP, VR, CF adalah **STATUS/LABEL KONTEKS**, bukan sinyal otomatis, bukan syarat wajib berurutan, bukan gate boolean.

```
SALAH: CMP → VR → CF → ENTRY (sequence wajib, AND-chain)
BENAR: CMP/VR/CF = bahasa untuk membaca kondisi market,
       keputusan diambil dari pembacaan holistik seluruh
       konteks, bukan checklist status
```

**Status ≠ Signal.** Jangan pernah mengimplementasikan "kalau status = X maka otomatis entry Y".

---

## 2. VR DAN CF = PENANDA MODE, BUKAN IZIN ENTRY

```
CF = trader sedang bertransaksi SEARAH konteks utama
     → mode: boleh lebih agresif, TP lebih panjang, boleh hold
        posisi lebih lama, boleh menambah posisi

VR = trader sedang bertransaksi DI DALAM RETRACEMENT
     → TETAP BOLEH ENTRY — VR TIDAK PERNAH BERARTI "DILARANG
        ENTRY"
     → mode: TP lebih pendek, lebih waspada, exit lebih cepat
        begitu ada bukti hipotesis retracement ini gagal
```

---

## 3. TIGA PERAN YANG HARUS DIPISAH: ARAH, LOKASI, EKSEKUSI

```
ARAH (Direction)
    → Diberikan oleh timeframe acuan yang lebih besar (misal H4)
    → Trading TIDAK dilakukan di TF ini — ini cuma sumber bias

LOKASI (Location)
    → Area-area penting dari TF acuan itu (level CMP, baik yang
       lama maupun yang baru setelah flip — lihat Bagian 7)
    → Bukan tempat eksekusi — ini tempat MENUNGGU dan MENGAMATI

EKSEKUSI (Execution)
    → Terjadi di timeframe kecil, DIPILIH SECARA SITUASIONAL
       (lihat Bagian 5) — bukan fix ke satu TF tertentu
    → Trigger sebenarnya (breakout, price response, momentum)
       muncul di sini, TEPAT SAAT harga sampai di LOKASI yang
       relevan dari ARAH yang sudah diketahui
```

Urutan berpikir yang benar: "Arah utamanya ke mana?" → "Area penting mana dari arah itu yang sekarang relevan?" → "Apa yang terjadi di timeframe kecil saat harga sampai di sana?" — baru dari situ keputusan diambil.

---

## 4. CONFIDENCE HARUS DUA LAPIS: LOCAL VS ROOT

**Masalah yang harus dihindari:** confidence yang hanya mengukur seberapa kompak timeframe-timeframe kecil saling align satu sama lain (misal H1-M30-M15-M5 semua searah) bisa MENYESATKAN kalau timeframe paling besar (root/primary context, misal Daily) sebenarnya BELUM berubah arah dan masih berlawanan.

```
LOCAL CASCADE CONFIDENCE
    = seberapa align timeframe-timeframe kecil satu sama lain
    = berguna untuk mengukur kekuatan momentum jangka pendek

ROOT ALIGNMENT
    = apakah cascade ini SEARAH atau MELAWAN primary context
       tertinggi yang relevan (misal Daily)
    = ALIGNED → mode CF (boleh agresif)
    = COUNTER → mode VR, TIDAK PEDULI seberapa tinggi local
       cascade confidence-nya — TP tetap pendek, tidak boleh
       hold lama, tidak boleh tambah posisi, tetap waspada
       root context bisa "menang" kapan saja
```

**Aturan:** root SELALU menang atas local confidence dalam menentukan mode risiko. Local confidence tinggi hanya berarti "momentum jangka pendek kuat", BUKAN "aman untuk trading agresif". Tampilan ke trader harus menunjukkan KEDUA angka ini secara eksplisit, jangan digabung jadi satu angka tunggal yang bisa menyesatkan.

---

## 5. PEMILIHAN TIMEFRAME EKSEKUSI ITU SITUASIONAL

Timeframe yang dipakai sebagai "gate" atau titik keputusan tidak boleh di-hardcode selalu sama (misal "selalu pakai anak langsung dari parent TF"). Kadang timeframe anak langsung terlalu lambat bereaksi — dalam situasi begitu, timeframe yang lebih kecil lagi bisa dipilih sebagai gate praktis, karena dia yang akan lebih dulu memberi sinyal tepat waktu.

**Kriteria sukses eksekusi:** keberhasilan entry di timeframe kecil diukur dari apakah dia **sanggup mengubah/flip arah** timeframe di atasnya (bukan sekadar harga memantul sedikit).

**Confluence antar-zona berdekatan:** area penting suatu timeframe besar (misal H4) sering sejajar atau berdekatan dengan area penting timeframe di bawahnya (misal H1) — ini bentuk confluence tambahan. Kalau dua timeframe "setuju" di area yang sama, timeframe anak dari yang lebih kecil (misal M30, anak dari H1) menjadi proxy yang lebih andal untuk membaca reaksi di area itu, dibanding timeframe yang dipilih tanpa dasar confluence ini.

---

## 6. POLA PENGUJIAN BERULANG (Bukan Sekali Coba Lalu Selesai)

Level struktural penting sering diuji **lebih dari sekali** sebelum akhirnya benar-benar break ke satu arah. Setiap kali harga menyentuh level itu, itu adalah **kesempatan entry baru**, bukan "percobaan pertama gagal = selesai total".

```
Jika percobaan pertama gagal (level tidak break, dan usaha
    lanjutan di timeframe lebih kecil juga tidak berhasil
    mengubah arah):
    → BUKAN akhir — level yang sama kemungkinan akan diuji
       ulang lagi
    → Setiap pantulan/oscillasi di level itu = kesempatan entry
       baru dengan pola yang sama, sampai akhirnya salah satu
       sisi benar-benar break
```

**Peran monitoring pembentukan candle secara real-time (bukan cuma tunggu close):** selama candle timeframe acuan masih terbentuk/berjalan, data momentum real-time (delta, tekanan beli/jual) berfungsi sebagai **petunjuk dini** ke arah mana kemungkinan besar candle itu akan close — ini TIDAK menggantikan aturan bahwa keputusan resmi tetap menunggu bar-close (Bagian 7), tapi berfungsi sebagai antisipasi.

---

## 7. OTORITAS "BREAK" — HANYA TIMEFRAME PEMILIK LEVEL YANG BERHAK MENENTUKAN

**Aturan ketat yang wajib ditegakkan:** status "break" suatu level struktural HANYA BOLEH ditentukan oleh **candle close pada timeframe yang memiliki level itu** — bukan oleh candle di timeframe manapun di bawahnya, TIDAK PEDULI seberapa banyak candle timeframe kecil yang sudah close melewati level tersebut secara visual.

```
Contoh: level penting milik H4
    → HANYA candle H4 sendiri, saat close, yang berhak
       menentukan level ini break atau tidak
    → Candle H1/M30/M15/M5 yang close melewati level itu BUKAN
       bukti break, berapa pun banyaknya
    → Selama candle H4 sendiri belum close melewati level itu,
       status level = BELUM BREAK
```

**Kenapa ini wajib:** tanpa aturan ini, sistem rawan salah membaca "sudah break" hanya karena noise di timeframe kecil, padahal timeframe pemilik level belum benar-benar mengonfirmasi.

**Implementasi:** setiap level/zona yang dilacak harus punya atribut "timeframe pemilik" yang eksplisit, dan pengecekan break HARUS hanya membaca candle dari timeframe pemilik tersebut.

---

## 8. SIFAT REKURSIF: LEVEL YANG BREAK MENJADI ACUAN BARU

Ketika sebuah level struktural break (sesuai aturan otoritas di Bagian 7), **level itu sendiri langsung menjadi acuan baru untuk arah yang berlawanan** — dan otomatis menjadi **zona kunci berikutnya** yang harus diuji ulang kalau harga ingin membalik arah lagi.

```
Level lama (misal area breakout BUY sebelumnya) → BREAK
        │
        ▼
Level itu → JADI ACUAN BARU untuk arah SELL
        │
        ▼
Level yang SAMA → berubah peran jadi RESISTANCE
        │
        ▼
Kapan pun nanti harga ingin naik lagi (bahkan setelah bergerak
    jauh ke bawah dulu) → level INI yang harus di-break lagi
    ke atas
        │
        ▼
Kalau level ini GAGAL di-break ke atas → hampir pasti terjadi
    reaksi kuat di situ, karena level ini sekarang jadi titik
    pivot struktural paling signifikan
```

**Ini pola rekursif yang berulang setiap kali ada flip**, bukan kejadian sekali saja. Setiap timeframe terus "mewariskan" level breakout terbarunya sebagai zona kunci berikutnya — rantai level ini harus disimpan dan dipantau terus-menerus, bukan cuma satu level statis.

**Implementasi:** setiap kali level tercatat break, sistem harus: (1) mencatat level tersebut sebagai acuan baru untuk arah berlawanan pada timeframe yang sama, (2) menyimpan level ini sebagai zona kunci dengan peran yang sudah terbalik (resistance↔support), (3) menjadikannya kandidat titik pengujian berikutnya untuk arah balik di masa depan.

---

## 9. LOKASI PENTING, TAPI BUKAN HAKIM MUTLAK

Jangan menganggap "sinyal di luar zona relevan = otomatis salah". Yang lebih tepat: sinyal di luar zona relevan punya **kualitas kontekstual berbeda** (lebih lemah), bukan otomatis tidak valid. Catat status, lokasi, jarak ke zona terdekat, dan respons harga — jangan sekadar biner "di dalam zona = valid, di luar zona = tidak valid".

---

## 10. KONFLIK ADALAH INFORMASI, BUKAN SESUATU YANG HARUS DIPAKSA SELARAS

Kalau arah utama bilang BUY tapi price action atau order flow menunjukkan bearish, JANGAN memaksa semua data jadi BUY. Ini harus dibaca sebagai **konflik konteks** — itu sendiri adalah informasi penting tentang kondisi market saat ini, bukan sesuatu yang perlu "diselesaikan" secara paksa ke satu arah.

---

## 11. SETIAP STATUS ADALAH HIPOTESIS, BUKAN KEBENARAN MUTLAK

Status (CMP/VR/CF, atau kesimpulan dari pembacaan lainnya) bisa berubah kapan saja market memberi informasi baru — dari valid jadi lemah, dari lemah jadi konflik, dari hipotesis jadi terkonfirmasi, atau jadi tidak berlaku sama sekali. Jangan mempertahankan bias hanya karena kesimpulan sebelumnya mengatakan demikian.

---

## 12. RINGKASAN — CARA BERPIKIR YANG BENAR

Jangan bertanya: "Apakah market memenuhi skema saya?"

Pertanyaan yang benar, berurutan:
```
1. Market sedang melakukan apa?
2. Di mana market melakukan itu?
3. Apakah pergerakan ini searah arah utama, atau retracement?
4. Apa respons harga di lokasi tersebut?
5. Apa yang dikatakan momentum/order flow?
6. Di mana titik pembatalan (invalidation) dan bagaimana risikonya?

Baru: KEPUTUSAN.
```

Sistem harus mengikuti market, bukan memaksa market mengikuti skema sistem.
