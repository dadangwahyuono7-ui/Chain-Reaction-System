# Panduan Instalasi APK Chain Reaction

File APK sudah otomatis terkompilasi dan siap dipasang langsung ke HP Android Anda:

- **Versi Terkini (Versioned)**: [`ChainReaction-v1.6.0.apk`](file:///d:/ChainReactionAndroidApp/ChainReaction-v1.6.0.apk)
- **Shortcut File Terbaru**: [`ChainReaction-LATEST.apk`](file:///d:/ChainReactionAndroidApp/ChainReaction-LATEST.apk)

---

## 📋 Changelog Versi:
- **v1.6.0 (Confluence Radar CF/VR & S&D Touch Alert Edition)**:
  - 🔔 **Push Alert Radar Konfluensi Tinggi (80%+ BUY/SELL)**: Otomatis memicu push notification instan saat konfluensi mencapai $\ge 80\%$, dengan diferensiasi tegas antara **`CF MODE (WITH TREND)`** dan **`VR RETEST (PULLBACK)`** lengkap dengan instruksi aksi (`🔴 SELL PULLBACK (VR)` / `🟢 BUY BREAKOUT (CF)`) dan target TP.
  - 🎯 **Notifikasi Sentuhan Zona S&D Multi-TF (Supply S1 / Demand D1)**: Berdering otomatis saat harga menyentuh zona Supply S1 atau Demand D1 dengan label sumber timeframe (`[D1]`, `[H4]`, `[H1]`, `[M30]`) dan lot tembok Bookmap.
  - 🐋 **Notifikasi Tembok Likuiditas Raksasa Bookmap ($\ge 100\text{L}$)**: Deteksi otomatis tembok penahan atau penghalang besar dari kedalaman Bookmap.
- **v1.5.0 (S&D Zone Engine & Momentum Break Edition)**:
  - 🧱 **Supply & Demand Zone Engine Integration**: Live order-flow Bookmap S&D wall roadmap (S1..S2, D1..D2) dengan visualisasi lot, kekuatan (KUAT/SEDANG/LEMAH), status (AUS/AKTIF/DIUJI/BARU), hit serap erosi nyata, dan Buyer/Seller control %.
  - ⚡ **S&D Momentum Break State Engine**: Visual status penembusan zona dengan doktrin *"Close Only Confirmed"* (state WICK, CLOSE, MOMENTUM, FOLLOW THROUGH berstatus amber/abu-abu, solid neon hanya untuk BREAK_CONFIRMED).
  - 🚨 **Dynamic S&D Compression Warning**: Notifikasi otomatis saat zona Supply & Demand saling menjepit (< 1 USD) di layar utama Command.
- **v1.4.0 (Multi-Timeframe Breakout & Flip Notification Edition)**:
  - 🔔 **Pemantauan Breakout 6 Timeframe Sekaligus**: Notifikasi otomatis saat terjadi perubahan arah/flip pada **`D1`**, **`H4`**, **`H1`**, **`M30`**, **`M15`**, maupun **`M5`**.
  - 🏷️ **Judul Notifikasi Jelas & Informatif**: Judul pop-up mencantumkan nama timeframe secara spesifik, misal: **`🟢 H1 FLIP: BUY`**, **`🔴 M30 FLIP: SELL`**, atau **`🟢 D1 FLIP: BUY`**.
  - ⚙️ **Chip Toggle Per-Timeframe**: Di tab SYSTEM, Anda bisa menyalakan/mematikan notifikasi untuk masing-masing TF secara independen (`[D1] [H4] [H1] [M30] [M15] [M5]`).
- **v1.3.0**:
  - Redesign Layar COMMAND (Prioritas 1-4) + Slot Warning Dinamis + Smooth Speedometer.
- **v1.2.0**:
  - Speedometer Breakout Velocity + Order Flow Delta Histogram + Keep Screen On.
- **v1.0.0**:
  - Rilis awal 5 Tab + Commander HUD.

---

## Cara Pasang (Install) di HP Android Anda

### Cara Paling Mudah (Kirim File):
1. Kirim file `ChainReaction-v1.0.0.apk` ke HP Anda melalui salah satu cara berikut:
   - **Kabel USB**: Copy file ke memori internal HP (folder Download).
   - **WhatsApp Web / Telegram**: Kirim file APK sebagai *Document* ke nomor/chat pribadi Anda.
   - **Google Drive**: Upload file ke Google Drive lalu download di HP.
2. Di HP Android Anda, buka file `ChainReaction-v1.0.0.apk`.
3. Jika muncul pop-up *"Untuk alasan keamanan, ponsel Anda tidak diizinkan memasang aplikasi dari sumber ini"*:
   - Klik **Setelan / Settings** ➔ aktifkan centang **"Izinkan dari sumber ini" (Allow from this source)**.
4. Klik **Install (Pasang)**.
5. Selesai! Buka aplikasi **Chain Reaction** di HP Anda.

---

## Cara Build Ulang di Masa Depan (1-Click Tanpa Android Studio)

Jika suatu saat Anda mengubah kode dan ingin membuat APK baru:
1. Klik kanan file `build_apk.ps1` ➔ pilih **Run with PowerShell**.
2. File `ChainReaction-v1.0.0.apk` baru akan otomatis diperbarui.

---

## Cara 1: Langsung Jalankan di HP Android (Recommended)

1. **Aktifkan Developer Options di HP Android Anda**:
   - Buka **Settings** ➔ **About Phone** (Tentang Ponsel).
   - Ketuk **Build Number** sebanyak 7 kali berturut-turut sampai muncul notifikasi *"You are now a developer!"*.
   - Masuk ke **Settings** ➔ **System** ➔ **Developer Options** ➔ aktifkan **USB Debugging** (Debugging USB).
2. Sambungkan HP ke PC menggunakan kabel USB.
3. Di HP, jika muncul pop-up *"Allow USB debugging?"*, centang *"Always allow from this computer"* lalu tekan **Allow**.
4. Di toolbar atas Android Studio, nama HP Anda akan terdeteksi di dropdown device.
5. Klik tombol hijau **Run** (segitiga hijau `▶` atau tekan `Shift + F10`).
6. Aplikasi akan otomatis ter-compile dan langsung terpasang serta terbuka di HP Anda!

---

## Cara 2: Generate File APK Siap Pasang

Jika Anda ingin membuat file APK mandiri (bisa dikirim via WA / Telegram / Google Drive lalu di-install):

1. Di menu atas Android Studio, klik:
   ```
   Build ➔ Build App(s) / Bundle(s) ➔ Build APK(s)
   ```
2. Tunggu proses build beberapa detik.
3. Saat selesai, akan muncul notifikasi pop-up di pojok kanan bawah:
   ```
   APK(s) generated successfully for module 'ChainReactionApp.app' with 1 build variant: debug
   [locate]
   ```
4. Klik tombol **[locate]**. File explorer Windows akan terbuka langsung mengarah ke file APK:
   ```
   app\build\outputs\apk\debug\app-debug.apk
   ```
5. Kirim file `app-debug.apk` tersebut ke HP Anda, lalu tap file tersebut di HP untuk meng-install.

---

## Pengaturan Agar App Tahan Nyala 24 Jam di HP

Sesuai kebutuhan monitoring trading 24 jam tanpa dimatikan paksa oleh Android:

1. **Foreground Service**:
   - Saat aplikasi dibuka, notifikasi live status akan otomatis muncul di status bar HP ("XAUUSD: $4644.25 • Bias: BEARISH").
2. **Abaikan Optimasi Baterai**:
   - Masuk ke tab **SYSTEM** di dalam aplikasi.
   - Klik tombol **"Buka Izin Abaikan Optimasi Baterai"**.
   - Pilih **Allow / Jangan Optimalkan** agar sistem operasi Android tidak membekukan polling aplikasi saat layar HP mati dalam waktu lama.

---

## Ringkasan Fitur Navigasi

| Tab / Mode | Fungsi & Data |
|---|---|
| **COMMAND** | Dashboard utama: Live price XAUUSD, Primary Action alert, Matrix Conviction 5/6, CVD/Delta flow pulse, Bar timers (M1..H4), dan **Market Overview expandable card** (Option A). |
| **HUD MODE** | Mode layar penuh minimalis (angka harga besar, bias, score, nearest wall) untuk ditaruh di meja trading. Dibuka via tombol **HUD** di Top Bar. |
| **BOOKMAP** | Order flow & liquidity: Bid vs Ask wall summary, Imbalance ratio bar, Visual Depth Ladder table, dan Wall Sweep live alert. |
| **CHAIN** | Multi-timeframe matrix D1 s/d M1, Alignment %, Chain done sequence, Momentum triad (EA, Bookmap, Footprint), Barrier warning & IVB. |
| **NEWS** | AI Market Analysis dengan marker `[[level]]` yang di-highlight, Permanent Disclaimer, News sentiment conclusion, list berita dengan tone chips, dan Economic Calendar (Forex Factory) dengan filter impact. |
| **SYSTEM** | Mini-PC server health (CPU %, RAM %, Disk %), Bridge latency ping, Bookmap online state, modal & equity, serta saklar Keep-Alive 24 jam. |
