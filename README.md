<div align="center">

# ⚡ CHAIN REACTION SYSTEM

### XAUUSD Trading Engine — Price Action Murni

**CMP → VR → CF**

*by Commander Dadang Wahyuono*

![Version](https://img.shields.io/badge/version-v52.72-gold?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-Windows-blue?style=for-the-badge&logo=windows)
![Engine](https://img.shields.io/badge/engine-MT5_%2B_Bookmap-black?style=for-the-badge)
![License](https://img.shields.io/badge/license-Private-red?style=for-the-badge)

</div>

---

## Tentang

**Chain Reaction System** adalah mesin trading XAUUSD yang menggabungkan doktrin price-action murni (CMP/VR/CF — tanpa Fibonacci, EMA, atau indikator eksternal apapun) dengan data order-flow real dari Bookmap (wall, sweep, absorption, CVD). EA MT5 mengeksekusi + memvisualisasikan langsung di chart; Bookmap bridge menyuplai data liquidity; dashboard **Sultan Sniper Engine** menampilkan semuanya real-time — lokal maupun dari jarak jauh.

## Doktrin: CMP → VR → CF

```
CMP ──────► VR ──────► CF ──────► ENTRY
 │           │           │
 │           │           └─ Breakout SEARAH setelah VR (bisa berkali-kali)
 │           └─ Breakout BERLAWANAN pertama di TF 1 level bawah (sekali per siklus)
 └─ Candle CLOSE melampaui minor SNR (body only — wick diabaikan)
```

**Barrier** = CMP lama yang harus jebol dulu sebelum harga lanjut, satu per TF (makin besar TF, makin kuat).
**Wall Sweep** = wall besar di order book yang tersapu — kalau harga reclaim balik, itu reversal terkonfirmasi, bukan tebakan dari bentuk candle.

Doktrin lengkap, arsitektur, dan riwayat perubahan: lihat [`CLAUDE.md`](CLAUDE.md).

## Fitur

| Modul | Fungsi |
|---|---|
| **EA MT5** — `DD_ChainReaction_MultiTF_EA_v2.mq5` | Cascade H4→M30→M5, Barrier Veto, Sweep Reversal Veto, Momentum Entry, panel live di chart |
| **Bookmap Bridge** — `bookmap-bridge/` | CVD, wall ladder, iceberg, absorption, volume profile — langsung dari order book GCZ6 |
| **Sultan Sniper Engine Dashboard** | Layout fluid (selalu pas di layar berapa pun ukurannya), bisa diakses remote lewat Cloudflare Tunnel |

## Instalasi

### Prasyarat (install manual sekali per PC — software berlisensi, tidak bisa diotomatisin)

| Software | Keterangan |
|---|---|
| [MetaTrader 5](https://www.metatrader5.com/) | Login akun broker |
| [Bookmap](https://bookmap.com/) | Connect ke Rithmic / data feed |
| [Python 3.x](https://python.org) | Centang **Add to PATH** saat install |
| [cloudflared](https://github.com/cloudflare/cloudflared) *(opsional)* | Buat akses dashboard dari luar rumah |

### Setup

```powershell
git clone https://github.com/dadangwahyuono7-ui/Chain-Reaction-System.git
cd Chain-Reaction-System
.\setup.ps1
```

`setup.ps1` otomatis bikin virtual environment Python + install dependency. Yang tersisa manual:

1. Buka MT5, login, drag `DD_ChainReaction_MultiTF_EA_v2` ke chart **XAUUSD M5**.
2. Buka Bookmap, connect Rithmic, load `bookmap-bridge\bookmap_addon.py` di chart **GCZ6** (Code Editor → Build → Configure add-ons).
3. *(Opsional, remote access)* Copy folder `.cloudflared\` dari PC lama ke `%USERPROFILE%\.cloudflared\`, atau `cloudflared tunnel login` buat setup baru.

## Menjalankan

```powershell
bookmap-bridge\start_trading.ps1
```

Nyalain bridge, dashboard (window **Sultan Sniper Engine**, auto-maximize), dan tunnel (kalau sudah dikonfigurasi). Matikan semua dengan:

```powershell
bookmap-bridge\stop_trading.ps1
```

## Struktur

```
Chain-Reaction-System/
├── DD_ChainReaction_MultiTF_EA_v2.mq5   EA produksi
├── DD_CMP_Indicator.mq5                 Indikator CMP dasar
├── chain_settings.json                  Config runtime (lot, risk, magic number)
├── setup.ps1                            Setup sekali per PC
├── CLAUDE.md                            Doktrin lengkap + arsitektur + changelog
└── bookmap-bridge/
    ├── bookmap_addon.py                 Load ke Bookmap Code Editor
    ├── udp_listener.py                  Proses engine utama (venv)
    ├── sultan_dashboard_server.py       Dashboard window + web server
    ├── sultan/                          HTML/CSS/JS dashboard
    ├── start_trading.ps1
    └── stop_trading.ps1
```

---

<div align="center">

**Private repository — Chain Reaction doctrine & system by Commander Dadang Wahyuono**

</div>
