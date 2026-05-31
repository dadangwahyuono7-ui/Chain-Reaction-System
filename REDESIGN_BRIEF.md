> ⛔⛔ MANDAT UTAMA (BACA DULU) ⛔⛔
> User TEGAS: **JANGAN recolor / ganti tema lagi.** Sesi sebelumnya cuma ganti warna
> (amber→indigo, zinc→slate) + poles logo/chrome — LAYOUT & MODEL MASIH SAMA PERSIS 3002.
> Itu BUKAN yang diminta. User mau **MODEL/STRUKTUR/LAYOUT BERUBAH TOTAL.**
>
> TUGAS SESI BARU = BONGKAR ARSITEKTUR TAMPILAN:
> 1. Buang layout 3-kolom padat (sidebar|market|chat) → ganti susunan BARU (lihat "LAYOUT BARU").
> 2. Bikin komponen primitif BARU (Card, Stat, StepDot) — JANGAN pakai panel lama apa adanya.
> 3. Susun ulang: Command Card hero full-width → card grid lega → chain progress besar.
> 4. Hasil harus kelihatan SEBAGAI APLIKASI BEDA, bukan 3002 yang dicat ulang.
> JANGAN cuma ganti class warna. Kalau hasilnya masih "mirip 3002 beda warna" = GAGAL.

# REDESIGN BRIEF — ChainReaction Dashboard v2 (Clean Institutional)

> **Tujuan:** Build dashboard BARU dari nol (bukan poles 3002). Arah: **Clean Institutional**
> (Bloomberg-modern × fintech 2026). Tenang buat mantau lama, rapi buat screenshot ke tim.
>
> **ATURAN MUTLAK:**
> - `:3002` (prod, branch utama) **JANGAN disentuh** — itu yang dipakai team via tunnel `trade.dadangchatai.com`.
> - Semua build redesign di **worktree** `D:\PROJECT TRADING\sultan-advisor-redesign\sultan-advisor`,
>   branch `feat/ui-redesign`, jalan di **port 3003** (`npm run dev -- -p 3003`).
> - **Logika trading & doktrin (CMP/VR/CF), engine, API, tunnel, team-chat, auth — JANGAN diubah.**
>   Ini murni lapisan visual/presentasi. Data tetap dari indikator TV v4.

---

## STATUS SAAT INI (sudah dikerjakan di feat/ui-redesign)
- ✅ Logo baru (`components/logo.tsx`) — wordmark "ChainReaction" mixed-case + mark 3-node biru
- ✅ Base slate (`app/layout.tsx`), chrome dashboard bersih (`app/dashboard/page.tsx`)
- ✅ PanelBox/PanelTitle clean (hapus scan-line + hex gimmick)
- ✅ Command bar (verdict "ngapain sekarang")
- ✅ SCALP.CYCLE → pipeline stepper
- ⚠️ **MASIH POLES, BELUM REDESAIN STRUKTURAL.** Layout 3-kolom masih sama persis 3002.
  Isi panel (heatmap, neural, delta, snr) masih warna lama (amber/cyan) → campur, belum konsisten.

**Kesimpulan feedback user:** ini baru ganti baju, belum ganti badan. Sesi baru harus berani
ubah LAYOUT & STRUKTUR, bukan cuma warna.

---

## DESIGN TOKENS (pakai CSS variables di globals.css — satu sumber)
```
/* Surface */
--bg:        #0a0e16   (slate-950 kebiruan)
--surface:   #111722   (panel)
--surface-2: #161d2b   (panel elevated / hover)
--border:    #1e2733   (garis tipis)
--border-hi: #2a3647   (garis aktif)

/* Text */
--text:      #e2e8f0   (slate-200, utama)
--text-dim:  #94a3b8   (slate-400, sekunder)
--text-mute: #64748b   (slate-500, label)

/* Accent & semantic */
--primary:   #4f7cff   (indigo/biru institusi — brand & "info/nunggu")
--buy:       #10b981   (emerald)
--sell:      #f43f5e   (rose)
--warn:      #f59e0b   (amber — HANYA untuk alert/caution, jangan jadi brand)
--signal:    #fbbf24   (kuning terang — HANYA entry valid / actionable)
```
**Disiplin warna:** 90% layar netral (slate). Hijau/merah cuma untuk arah. Indigo untuk brand/nunggu.
Amber/kuning HANYA pas actionable (entry). Kalau semua warna → gak ada yang menonjol.

## TIPOGRAFI
- UI label/teks: **Geist Sans** (udah ada) — sentence case / refined caps, JANGAN allcaps-mono di mana-mana.
- Angka (harga, level, %): **Geist Mono + tabular-nums**, rata kanan.
- Hierarki jelas: angka penting = besar & tebal; label = kecil & muted.

## MOTION — 2 LAPIS (penting, ini permintaan inti user)
User SENGAJA mau ada gerakan biar gak bosen nunggu setup. Tapi pisahkan:
- **AMBIENT** (kalem, nemenin nunggu): napas pelan 3-4s, low-contrast, cool. Cuma di step "yang lagi ditunggu".
- **SIGNAL** (tajam, terang, + bunyi): CUMA pas entry valid (F3/CF fire). Karena ambient kalem, signal langsung nonjok.
- Keyframes ambient/signal sudah ada di `<style>` market-panel (anim-ambient-breathe/ring/dot, anim-signal-pulse/pop).

---

## LAYOUT BARU (ide fresh — BUKAN clone 3-kolom 3002)

Konsep: **"Command-first"** — jawaban "ngapain sekarang" jadi pusat, detail jadi pendukung.

```
┌──────────────────────────────────────────────────────────────────────┐
│ TOPBAR: logo · harga live besar (tabular) · session · status koneksi  │
├──────────────────────────────────────────────────────────────────────┤
│ ╔══ COMMAND CARD (hero, lebar penuh) ═══════════════════════════════╗ │
│ ║  VERDICT BESAR: ⏳ TUNGGU CF / ⚡ SIAP ENTRY BUY / ⛔ NEWS / SKIP  ║ │
│ ║  + sub: alasan singkat   |  GRADE  BIAS  PRIME  SCALP  NEWS chips ║ │
│ ╚════════════════════════════════════════════════════════════════════╝ │
├───────────────────────────────┬──────────────────────────────────────┤
│ KIRI (2/3) — card grid:        │ KANAN (1/3):                         │
│  • CHAIN PROGRESS (stepper     │  • SNR LADDER (level + jarak)        │
│    besar: D→H4→H1→M30→M15→M5   │  • TICK PRESSURE (delta mini)        │
│    tiap TF kartu, fase jelas)  │  • NEWS / countdown                  │
│  • SETUP MATANG (ranking TF    │                                      │
│    paling siap entry)          │                                      │
│  • per-TF cards (CMP/VR/CF #N) │                                      │
└───────────────────────────────┴──────────────────────────────────────┘
```
AI Advisor chat: tetap panel kanan (atau jadi tab/drawer biar layar market lebih lega — diskusi dulu).
Team-chat floating widget: pertahankan (sudah jalan), kasih aksen indigo biar nyatu.

### Prinsip layout
- **Card-based**: tiap metrik = kartu (surface, border tipis, rounded-xl, padding lega, soft shadow).
- **Whitespace lega** antar kartu (gap-3/gap-4), jangan padat kayak 3002.
- **1 fokus utama** = Command Card. Sisanya pendukung, visual lebih tenang.
- **Mini-graph dalam card** (sparkline tick, mini progress) — info sekilas.
- Responsif: desktop = grid; mobile/tablet (tim akses HP) = stack 1 kolom, command card tetap atas.

---

## URUTAN BUILD (sesi baru)
1. **globals.css**: taruh CSS variables tokens di atas. Set base bg, font, scrollbar halus.
2. **Komponen primitif baru**: `<Card>`, `<Stat>`, `<Pill>`, `<StepDot>` — reusable, konsisten.
3. **TopBar** baru: logo + harga live besar tabular + session + koneksi.
4. **CommandCard** (hero): verdict + chips. (logika verdict sudah ada di market-panel command bar).
5. **ChainProgress**: stepper besar full chain D→M5, fase per TF, 2-lapis motion.
6. **SetupRanking**: TF mana paling siap entry (pakai computeAutoGrade + fase).
7. **SNR ladder, Tick pressure, News** → versi card bersih.
8. Pasang semua di layout grid baru di `app/dashboard/page.tsx` (atau page khusus redesign).
9. Konsistenin: hapus sisa amber/cyan/glow/blink lama → token baru + 2-lapis motion.

## DATA / API (JANGAN diubah, tinggal dipakai)
- Market context: `byName["H4_CMP"]`, `_VR`, `_CF`, `_CF_COUNT`, `_CF_TYPE` per TF (DAILY,H4,H1,M30,M15,M5).
- `computeAutoGrade(tfData, byName)` → grade A+/A/B/C/SKIP.
- SITREP fields: biasDir/biasLabel, primeLabel, scalpLabel, newsLabel, gradeLabel.
- Live price: SSE `/api/price-stream`. Sync: `/api/tv-sync`. News: NEXT_EVENT_EPOCH/NAME/TIME_WIB.
- Semua sudah ada di `components/market-panel.tsx` (referensi logika, jangan ubah hitungannya).

## CARA JALANIN PREVIEW (sesi baru)
```
cd "D:\PROJECT TRADING\sultan-advisor-redesign\sultan-advisor"
npm run dev -- -p 3003       # node_modules sudah ter-install di worktree
# buka http://localhost:3003  (login: trustedOrigins sudah include localhost:3003)
# bandingin dengan http://localhost:3002 (prod lama, JANGAN disentuh)
```

## REFERENSI VISUAL (2026 fintech/trading dashboard)
- Muzli "50 Best Dashboard Design 2026", TailAdmin stock dashboard, Telerik Fintech template,
  Eleken fintech design guide. Pola kunci: card layout, whitespace, hierarki, warna terbatas,
  soft gradient/shadow, bold typography, mini-graph in cards, trust via clarity.

---

**Catatan untuk sesi baru:** mulai dengan baca file ini + lihat `:3002` (jangan ubah) sebagai
referensi DATA/FITUR (apa aja yang harus ada), lalu build layout BARU di worktree. Fokus: struktur
& hierarki baru, bukan recolor. Tanya user dulu soal: (a) AI chat tetap sidebar atau jadi drawer,
(b) tema dark-slate (default) atau ada opsi light.
