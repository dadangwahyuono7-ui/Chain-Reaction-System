# TUNE-UP WORKFLOW — Cara Aman Ngoprek AI Local

> **BACA INI tiap mau tune-up / upgrade AI local.** Tujuannya: produksi (yang dipakai team live di trade.dadangchatai.com) TIDAK PERNAH ikut rusak pas kita eksperimen.

---

## PRINSIP UTAMA — 2 Jebakan yang Wajib Diingat

### ⚠️ Jebakan 1: Port beda ≠ aman
Kalau web di port 3003 baca file dari folder `sultan-advisor` yang SAMA dengan port 3002,
maka edit `route.ts` / `system-prompt.ts` bikin **produksi ikut berubah**.
→ Isolasi sesungguhnya = **folder terpisah (git worktree)**, bukan sekadar port beda.

### ⚠️ Jebakan 2: llama.cpp cuma SATU di :8080
Web 3002 dan 3003 dua-duanya nembak `localhost:8080`. Kalau restart llama.cpp buat
coba model/setting baru → **produksi langsung kena model uji-coba**.
→ Isolasi model = **llama.cpp ke-2 di :8081** khusus buat lab.

---

## ARSITEKTUR: PRODUKSI vs LAB

```
PRODUKSI (JANGAN DISENTUH saat ngoprek):
  folder : D:\PROJECT TRADING\sultan-advisor   (branch master)
  web    : port 3002 → cloudflare tunnel → trade.dadangchatai.com
  model  : llama.cpp :8080 (Gemma 4 stabil)

LAB (tempat ngoprek bebas):
  folder : D:\PROJECT TRADING\sultan-advisor-lab  (worktree, branch feat/tune-up)
  web    : port 3003
  model  : llama.cpp :8081
  env    : LLM_BASE_URL=http://localhost:8081/v1
```

Kalau hasil lab udah mantap → merge `feat/tune-up` ke `master` → restart produksi.

---

## SETUP LAB (sekali aja per siklus tune-up)

```powershell
cd "D:\PROJECT TRADING"

# 1. Bikin worktree terpisah dari branch baru
git worktree add "D:\PROJECT TRADING\sultan-advisor-lab" -b feat/tune-up

# 2. Copy env produksi ke lab, lalu edit port model
Copy-Item "D:\PROJECT TRADING\sultan-advisor\.env.local" "D:\PROJECT TRADING\sultan-advisor-lab\.env.local"
# Edit di lab\.env.local:
#   LLM_BASE_URL=http://localhost:8081/v1
#   BETTER_AUTH_URL=http://localhost:3003

# 3. Install deps di lab (worktree punya node_modules sendiri)
cd "D:\PROJECT TRADING\sultan-advisor-lab"
npm install --include=dev
```

### Bikin llama.cpp ke-2 di :8081 (buat lab)
Copy `F:\AI-AGENT\start-gemma4-e4b.bat` → `start-gemma4-e4b-LAB.bat`, ganti `--port 8080` jadi `--port 8081`.
Jalankan yang LAB ini terpisah dari yang produksi.

---

## SIKLUS KERJA HARIAN

```powershell
# Jalankan web lab di port 3003
cd "D:\PROJECT TRADING\sultan-advisor-lab"
npm run dev -- --port 3003

# Ngoprek bebas di folder lab: edit route.ts, system-prompt.ts, bat model, dll
# Produksi (3002 + :8080) sama sekali tidak terganggu
```

### Kalau hasil lab BAGUS → promosikan ke produksi
```powershell
cd "D:\PROJECT TRADING\sultan-advisor-lab"
git add -A && git commit -m "feat: <deskripsi tune-up>"
git push origin feat/tune-up

cd "D:\PROJECT TRADING"
git checkout master
git merge feat/tune-up --no-edit
git push origin master

# Restart produksi dengan kode baru
npx kill-port 3002
npm run build ; npx next start -p 3002   # di folder sultan-advisor
```

### Kalau hasil lab JELEK → buang aja
```powershell
cd "D:\PROJECT TRADING\sultan-advisor-lab"
git reset --hard   # buang semua perubahan di lab
# atau hapus worktree sekalian:
cd "D:\PROJECT TRADING"
git worktree remove "D:\PROJECT TRADING\sultan-advisor-lab" --force
```

---

## SAFETY NET — Kalau Produksi Kadung Rusak

```powershell
cd "D:\PROJECT TRADING"
git reset --hard origin/master   # balik ke kondisi master terakhir yang aman
```

`origin/master` selalu = checkpoint stabil terakhir. Commit ke master HANYA setelah teruji di lab.

---

## CATATAN PENTING (jangan lupa)

- **`.env.local` di-gitignore** → `git reset` TIDAK menimpa config lo. Aman, tapi worktree baru perlu di-copy manual.
- **`backtest/DATACSV/` di-gitignore** (29MB) → data aman di lokal, gak masuk repo.
- **Cloudflare tunnel pakai `protocol: http2`** di `C:\Users\R O V A\.cloudflared\config.yml` — WAJIB, karena WARP VPN blok QUIC/UDP. Jangan dibalik ke quic.
- **`BETTER_AUTH_URL`** produksi = `https://trade.dadangchatai.com` (biar login via domain publik jalan). Lab = `http://localhost:3003`.
- **Model GGUF** ada di `F:\AI-AGENT\models\`, bat launcher di `F:\AI-AGENT\`.
- **Jangan commit logic langsung ke master** — selalu lewat branch `feat/xxx` → uji di lab → merge.
