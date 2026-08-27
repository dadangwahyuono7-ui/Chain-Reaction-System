# 🗺️ PETA LOKASI FOLDER & ARSITEKTUR SISTEM (PROJECT DIRECTORY MAP)
**Project**: Chain Reaction Ecosystem (MT5 EA + Web Chart 4K + Android App)  
**Pemilik**: Commander Dadang Wahyuono  
**Terakhir Diperbarui**: 28 Agustus 2026

---

## 📌 PANDUAN PENTING UNTUK AGENT / DEVELOPER BERIKUTNYA:
Workspace ini (`d:\ChainReactionAndroidApp`) adalah bagian dari satu kesatuan ekosistem besar yang tersebar di beberapa folder pada komputer Commander Dadang. Jangan bingung jika mencari file EA, Web Chart, atau Bridge, ikuti peta direktori di bawah ini:

---

## 📂 1. FOLDER PROJECT TRADING UTAMA (MT5, BRIDGE & WEB CHART)
**Lokasi**: `D:\PROJECT TRADING\`

### A. Source Code EA & Indikator MT5
- `D:\PROJECT TRADING\DD_ChainReaction_MultiTF_EA_v3.mq5` & `.ex5`  
  👉 **EA Utama**. Berisi engine Quant Discretionary Box Scanner, Origin TF Lock, Speedometer Jarak Tembok, Whale Footprint, Spoofing Radar, dan eksekusi order.
- `D:\PROJECT TRADING\DD_SND_Barrier_Zone_Indicator.mq5` & `.ex5`  
  👉 **Indikator S&D Barrier MT5**.
- `D:\PROJECT TRADING\DD_CMP_Indicator.mq5` & `.ex5`  
  👉 **Indikator CMP**.

### B. Dokumentasi & Handover Master
- `D:\PROJECT TRADING\HANDOVER_DISCRETIONARY_BOX_QUANT_ENGINE_2026_08_28.md`  
  👉 Rekam jejak lengkap seluruh pembaruan fitur, logika, dan kompilasi per 28 Agustus 2026.

### C. Folder Bridge & Web Chart 4K
**Lokasi**: `D:\PROJECT TRADING\bookmap-bridge-v1\`
- `sultan_dashboard_server.py`  
  👉 Server backend Python (FastAPI / Port 8000 & 8080) yang menyuplai data live ke Web Chart dan Android.
- `bookmap_live_signal.csv` & `sultan_status.json`  
  👉 Pipa data real-time aliran order Bookmap dan status MT5.
- `sultan\chart.html`  
  👉 Tampilan Web Chart 4K (`https://trade.dadangchatai.com/chart.html`).
- `sultan\chart-assets\charts\WindowManager.js`  
  👉 Logika grafik Web Chart (Speedometer Mega Wall on-chart, garis POC/VAH/VAL, candle series).
- `sultan\chart-assets\drawings\DrawingEngine.js`  
  👉 Engine gambar canvas (Discretionary Box Scanner, Auto RR Sizing, Origin TF Lock).

---

## 📱 2. FOLDER APLIKASI ANDROID (MOBILE APP)
**Lokasi**: `d:\ChainReactionAndroidApp\`
- `app\src\main\java\com\dadang\chainreaction\`  
  👉 Seluruh kode Kotlin Jetpack Compose aplikasi Android (APK v1.6.0).
- `service\KeepAliveService.kt` & `NotificationHelper.kt`  
  👉 Service background 24/7 & notifikasi prioritas tinggi (Confluence Radar & Wall Alert).
- `HANDOVER_DISCRETIONARY_BOX_QUANT_ENGINE_2026_08_28.md`  
  👉 Salinan handover dokumen capaian.

---

## 🖥️ 3. FOLDER TERMINAL MT5 (METATRADER 5 PRODUCTION)
**Lokasi**: `C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\`
- `Experts\DD_ChainReaction_MultiTF_EA_v3.ex5`  
  👉 Binary EA yang sedang terpasang dan aktif di chart MT5 live.
- `Indicators\DD_SND_Barrier_Zone_Indicator.ex5`  
  👉 Binary Indikator MT5.
- `Files\bookmap_live_signal.csv` & `Files\sultan_status.json`  
  👉 File data yang dibaca/tulis langsung oleh MT5.

---

## 🛠️ 4. COMPILER TOOLS
- **MetaEditor64 CLI**: `C:\Program Files\MetaTrader 5\MetaEditor64.exe`
- Perintah kompilasi EA:
  ```powershell
  & "C:\Program Files\MetaTrader 5\MetaEditor64.exe" /compile:"D:\PROJECT TRADING\DD_ChainReaction_MultiTF_EA_v3.mq5" /log:"D:\PROJECT TRADING\compile_log_ea.txt"
  ```

---

## 🐙 5. GITHUB REPOSITORY & BACKUP
- **Repository URL**: `https://github.com/dadangwahyuono7-ui/Chain-Reaction-System.git`
- **Active Branch**: `feat/fusion-h1h4-intrabar-signal`
