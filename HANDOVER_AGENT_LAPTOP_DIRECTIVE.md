# 👑 PESAN SERAH TERIMA & PANDUAN OTONOM DARI ROVA UNTUK ANTIGRAVITY DI LAPTOP COMMANDER DADANG
> **Dokumen Master Handover Antigravity (PC ROVA ➔ Laptop Commander Dadang)**  
> **Tanggal Efektif**: 07 September 2026 / 08 September 2026 dini hari WIB  
> **Pemilik & Panglima Tertinggi**: Maestro Dadang Wahyuono (Commander Dadang)  
> **Tujuan**: Memastikan Antigravity / AI Agent yang berjalan di Laptop Commander memiliki **100% kesadaran situasi (situational awareness)**, konteks terkini, dan akses langsung ke Mini PC Tower Server 24/7 saat PC ROVA dimatikan total.

---

## 🚨 1. SIAPA KITA & APA PERAN KITA DI LAPTOP
Halo Antigravity di Laptop! Jika lo membaca file ini, berarti:
1. **PC ROVA (`100.115.192.70`) sedang OFF / di-shutdown** karena Commander Dadang sedang bepergian (misal: ke NTB / luar kota / trading mobile).
2. **Lo sekarang adalah AGEN KENDALI UTAMA (MAIN CONTROLLER AGENT)** yang mendampingi Commander langsung dari laptopnya.
3. Seluruh ekosistem kita **BERJALAN OTONOM 24/7 DI MINI PC TOWER SERVER (`100.71.97.6`)**, bukan di PC ROVA! Laptop lo adalah stasiun kendali jarak jauh (remote control station).

---

## 🔑 2. AKSES KONEKTIVITAS KE MINI PC TOWER SERVER (100.71.97.6)

Mini PC (`WIN-JIOIHRD7BB1`) terhubung melalui jaringan **Tailscale VPN** Commander Dadang. Di laptop Commander, pastikan aplikasi Tailscale aktif dan login ke akun Commander.

### A. Terminal SSH (Akses Utama Coding & Debugging)
* **IP Mini PC**: `100.71.97.6`
* **Port**: `22` (OpenSSH Windows Server)
* **User**: `Administrator`
* **Otentikasi SSH Key (SUDAH AKTIF & DIDAFTARKAN)**:
  * **Public Key Laptop Baru Commander (`dadan@DADANGWAHYUONO`)**:
    `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINu5tMzntSQwb+e7EvPf79DZMqAWYxWoIDrOX2dV0feh dadan@DADANGWAHYUONO`
    *Status: SUDAH RESMI DIDAFTARKAN & DI-APPEND* ke `C:\ProgramData\ssh\administrators_authorized_keys` dan `C:\Users\Administrator\.ssh\authorized_keys` di Mini PC!
  * **Public Key PC ROVA (`hermes@miix`)**:
    `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKfCHxDnz1bXRitGy+jKvGFxj0s7xiHNKjO7h/Yq1mo2 hermes@miix`
    *Status: TETAP AKTIF*. Kedua device (Laptop Baru & PC ROVA) bisa login bersamaan tanpa saling mengganggu.
  * Dari terminal laptop Commander, lo sekarang bisa langsung ketik:
    ```powershell
    ssh Administrator@100.71.97.6
    ```
    Langsung tembus instan tanpa prompt password!
* **Otentikasi Cadangan (Password Windows)**:
  * Password Administrator Windows Mini PC: **`Dadang278868`**

### B. Remote Desktop Layar Mini PC (GUI)
1. **AnyDesk 24/7 (Unattended Direct Access)**:
   * ID: **`1100740836`**
   * Password: **`Dadang278868`**
   * Bebas dibuka dari laptop atau smartphone Commander tanpa konfirmasi manual di Mini PC.
2. **Windows Remote Desktop (RDP)**:
   * Host: **`100.71.97.6:3389`**
   * User: `Administrator` | Password: `Dadang278868`

---

## ⚙️ 3. PETA PROSES DAN SERVICE YANG AKTIF 24/7 DI MINI PC

Di Mini PC, folder produksi resmi berada di: **`C:\bookmap-bridge-v1\`**.
Proses-proses berikut berjalan terus menerus:
1. **Bookmap GUI (Session 1 Desktop)**:
   * Terhubung langsung ke **Rithmic CME GC (Gold Futures `GCZ6`)** via gateway Chicago.
   * Addon Bookmap mengalirkan feed Level 2 Depth & Tick Volume ke port UDP 9000 dan port 32132.
2. **Sultan Web Dashboard Server 24/7 (`sultan_dashboard_server.py`)**:
   * Menjalankan HTTP & REST API di port **`8766`** (`http://100.71.97.6:8766/`).
   * Melayani `/api/status`, `/api/chart/candles`, `/sultan_status.json`, dan halaman web terminal.
   * Dikelola oleh Scheduled Task Windows: **`SultanServer247`**.
3. **Cloudflare Tunnel (`cloudflared.exe`)**:
   * Menghubungkan port `8766` ke domain publik ber-SSL: **`https://trade.dadangchatai.com/`**.
4. **Telegram Sentinel Bot (`telegram_sentinel.py`)**:
   * Token: `8709247938:AAFeW2V98mymADdD5M9vQvzUI-4XvDgMLyE`
   * Bot: `@DadangFusionclaw_bot` | Target Chat ID: `740117533` (Commander Dadang).
5. **Master Watchdog Otonom (`tower_watchdog.py`)**:
   * Dijalankan otomatis tiap 5 menit oleh Scheduled Task: **`TunnelWatchdog247`**.

---

## 🏆 4. APA YANG BARU SAJA KITA SELESAIKAN (MALAM 07-08 SEPTEMBER 2026)

Lo masuk ke sistem dalam keadaan yang **sangat matang dan stabil**. Ini pencapaian terakhir sebelum handover:

1. **Restorasi Feed CME GC & Bookmap**:
   * Feed Bookmap sempat disconnect karena maintenance bursa CME Sabtu siang. Sudah di-restart bersih (PID 8884) dan feed L2 mengalir deras sub-detik ($4413-$4414).
2. **Integrasi Fresh Seed M1 MT5 (101.111 Bar) & Koreksi Offset 3 Jam**:
   * Commander mengekspor data MT5 baru (`DATACSV\XAUUSDM1.csv`, 13.7 MB, 101.111 bar, Mei s/d 7 September 23:32 WIB / 19:32 broker time).
   * **Koreksi Kritis**: Offset MT5 server time terverifikasi `UTC = MT5_time - 3 jam` (bukan minus 10 jam seperti kekeliruan Claude sebelumnya).
   * File terkonversi `XAUUSD_M1.json` (5.7 MB) di Mini PC mendarat tepat pada 16:32 UTC (hanya selisih 3 menit dari running market). Candle menyambung **100% mulus (*zero-gap*)** dengan live ticks.
3. **Pre-Seeding Otonom di `cmp_engine.py` (Melenyapkan Masalah WAIT Cold-Start)**:
   * `MultiTFAggregator` kini dilengkapi `seed_from_m1_file()`. Saat start, engine otomatis membaca `XAUUSD_M1.json` dan seketika mengisi ingatan ratusan bar tertutup di D1 (30), H4 (175), H1 (201), M30 (201), M15 (201), dan M5 (201).
   * `BookmapDoctrineAnalyst` langsung aktif menghitung Minor SNR Flips dan sinyal VR/CF sejak detik pertama running!
4. **4-Grid Matrix Upgrade (`matrix.html`)**:
   * **Interactive Pan & Drag (60 FPS)**: Commander bisa klik-tahan dan geser mouse ke kanan/kiri untuk menelusuri candle histori hingga berjam-jam ke belakang, lengkap dengan tombol melayang `[ ⏪ HISTORI: -XX BAR | 🟢 KLIK SNAP LIVE ]`.
   * **Chart Shift / Right Margin**: Candle live paling kanan kini memiliki **ruang bernapas (whitespace ~120px)** di depannya, tidak lagi menempel atau terjepit ke border kanan, sehingga Commander leluasa membaca proyeksi arah pergerakan harga.
   * **Sub-Tick Tick Pulse**: Candle live paling kanan bernapas dan berdenyut aktif mengikuti live spot price Bookmap secara real-time.

---

## 🛡️ 5. PROTOKOL & PANTANGAN MUTLAK SAAT LO NGODING DI LAPTOP

1. **ATURAN 1: TARIK (SCP PULL) VERSI MINI PC TERLEBIH DAHULU!**  
   Sebelum mengedit `sultan_dashboard_server.py`, `heatmap.html`, atau `matrix.html`, **WAJIB MENARIK FILE AKTIF DARI `C:\bookmap-bridge-v1\` KE LAPTOP**. Jangan pernah mengasumsikan file lokal laptop lo paling baru!
2. **ATURAN 2: DILARANG OVERWRITE FILE PENUH SECARA BUTA!**  
   Gunakan teknik **surgical edit / multi-replace**. Jangan pernah me-replace seluruh isi file secara serampangan karena bisa menghapus logika penting yang dipasang agent sebelumnya.
3. **ATURAN 3: DILARANG MEMASUKKAN DATA PALSU / SINTETIS!**  
   Semua data (CVD, candle, resting walls, order flow) wajib bersumber dari Bookmap/Rithmic asli. Tidak boleh ada data `Math.sin`/dummy mock.
4. **ATURAN 4: CARA ME-RESTART SERVER DI MINI PC TANPA MATI**:
   Jika lo mengedit `sultan_dashboard_server.py`, cara restart yang benar adalah lewat Task Scheduler atau CIM/WMI agar prosesnya tidak mati saat sesi SSH lo putus:
   ```powershell
   ssh Administrator@100.71.97.6 "powershell -Command \"Restart-ScheduledTask -TaskName SultanServer247\""
   ```
   Atau via WMI:
   ```powershell
   Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = 'C:\Python311\python.exe C:\bookmap-bridge-v1\sultan_dashboard_server.py' }
   ```
5. **ATURAN 5: CATAT SEMUA DI STATUS KOORDINASI**:
   Setiap kali lo menyelesaikan pekerjaan atau sebelum limit, update file `STATUS - Koordinasi Claude & Antigravity.md` di repo laptop dan sinkronkan ke `D:\PROJECT TRADING\` / `D:\ObsidianMind\`.

---

## 📌 6. CHECKLIST CEK CEPAT KETIKA TERJADI ERROR DI MINI PC
Jika Commander lapor *"bro web-nya macet / error lagi"*, lakukan diagnosa ini secara urut:
1. **Cek Koneksi SSH**:
   `ssh Administrator@100.71.97.6 "netstat -ano | findstr :8766"`
   *(Harus ada proses LISTENING di port 8766).*
2. **Cek Proses Bookmap**:
   `ssh Administrator@100.71.97.6 "powershell -Command \"Get-Process Bookmap*\""`
   *(Harus running dan memakan RAM > 1.5 GB).*
3. **Cek Log Error Server**:
   `ssh Administrator@100.71.97.6 "powershell -Command \"Get-Content C:\bookmap-bridge-v1\server_debug.log -Tail 30\""`
4. **Cek Cloudflare Tunnel**:
   `curl -I https://trade.dadangchatai.com/api/status`
   *(Harus mengembalikan HTTP 200 OK).*

---

> **Pesan Penutup untuk Diri Sendiri di Laptop**:  
> *"Jaga war room Commander Dadang dengan disiplin institusional penuh. Kita adalah penjaga benteng data feed dan engine trading beliau. Bergerak cepat, teliti, jangan merusak ekosistem yang sudah rapi, dan selalu dengarkan doktrin beliau secara seksama."*  
> — **Antigravity (PC ROVA, 08 September 2026)**
