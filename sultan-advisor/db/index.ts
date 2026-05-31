import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import * as schema from "./schema";
import path from "path";

const dbPath = path.resolve(process.cwd(), process.env.DATABASE_URL ?? "./sultan.db");
const sqlite = new Database(dbPath);
sqlite.pragma("journal_mode = WAL");
sqlite.pragma("foreign_keys = ON");

// -- Auto-create memories table if not exists ----------------------------------
sqlite.exec(`
  CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 1,
    tags TEXT,
    session_id TEXT,
    created_at INTEGER NOT NULL DEFAULT (unixepoch())
  )
`);

// -- Auto-create paper trading tables ------------------------------------------
sqlite.exec(`
  CREATE TABLE IF NOT EXISTS paper_accounts (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    initial_balance REAL NOT NULL DEFAULT 10000000,
    balance REAL NOT NULL DEFAULT 10000000,
    risk_per_trade REAL NOT NULL DEFAULT 100000,
    updated_at INTEGER NOT NULL DEFAULT (unixepoch())
  );
  CREATE TABLE IF NOT EXISTS paper_trades (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    setup_tf TEXT,
    grade TEXT,
    cf_type TEXT,
    cf_count INTEGER,
    entry_price REAL NOT NULL,
    sl_price REAL NOT NULL,
    tp1_price REAL,
    tp2_price REAL,
    exit_price REAL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    r_multiple REAL,
    pnl REAL,
    open_reason TEXT,
    close_reason TEXT,
    opened_at INTEGER NOT NULL DEFAULT (unixepoch()),
    closed_at INTEGER
  );
  CREATE INDEX IF NOT EXISTS idx_paper_trades_account ON paper_trades(account_id, status);
`);

// Seed dua akun paper (engine murni + AI). Idempotent — saldo TIDAK di-reset
// kalau sudah ada (INSERT OR IGNORE), biar progres performa gak ilang tiap restart.
{
  const seedAcc = sqlite.prepare(
    "INSERT OR IGNORE INTO paper_accounts (id, label, initial_balance, balance, risk_per_trade) VALUES (?, ?, ?, ?, ?)"
  );
  seedAcc.run("engine", "Engine (Doktrin Murni)", 10_000_000, 10_000_000, 100_000);
  seedAcc.run("ai", "AI Advisor", 10_000_000, 10_000_000, 100_000);
}

// -- Seed foundational memories (only once — skip if already seeded) ----------
// Always upsert seeds so updates to seed content take effect immediately
{
  const seedMemories = [
    {
      id: "seed_identity",
      content: "Aku adalah Chain Reaction AI Advisor v4.0 OVERLORD — FULL AGENT, bukan chatbot biasa. Punya 16 tools aktif. Bisa baca/tulis file, jalankan PowerShell, install package, git, screenshot layar + vision, sync TradingView, cek MT5, hitung risk, dan simpan memori persisten. Bisa upgrade dashboard sendiri dan bahkan upgrade diri sendiri.",
      category: "preference",
      importance: 4,
      tags: "identity,agent,16-tools,capabilities",
    },
    {
      id: "seed_tools_workflow",
      content: "Workflow analisis trading: trigger_sync -> get_ohlc (TF VR) -> calculate_risk -> present plan -> save_memory. Workflow upgrade dashboard: read_file -> write_file -> shell_exec 'npx next build' -> shell_exec 'npx next start -p 3002'. Workflow visual check: screenshot_analyze -> analisis. JANGAN pernah bilang 'tidak bisa' — langsung panggil toolnya.",
      category: "lesson",
      importance: 4,
      tags: "workflow,tools,agent,best-practice",
    },
    {
      id: "seed_doctrine_core",
      content: "Doktrin inti Chain Reaction: CMP -> VR -> CF -> ENTRY. VR hanya SATU LEVEL di bawah (H4->H1, H1->M30, M30->M15, M15->M5). VR cuma sekali per siklus, CF bisa berkali-kali. CONTI (CF tanpa VR) = SKIP. SL kena ≠ setup gagal — gagal HANYA jika CMP flip. F3 = VR+CF selesai = PRIME ENTRY. Fibonacci/EMA/SMA/pivot DILARANG.",
      category: "lesson",
      importance: 4,
      tags: "doctrine,CMP,VR,CF,rules",
    },
    {
      id: "seed_commander_profile",
      content: "Commander Dadang Wahyuono (Bonker) — pencipta sistem Chain Reaction, trader XAUUSD. Panggil dia 'Commander' atau 'bos'. Bahasa: Indonesia santai, boleh pakai 'bro'. Dia suka analisis tajam dan to-the-point, tidak suka basa-basi panjang. Selalu jawab dalam Bahasa Indonesia.",
      category: "preference",
      importance: 4,
      tags: "commander,profile,style",
    },
    {
      id: "seed_memory_habit",
      content: "KEBIASAAN WAJIB: Setiap kali ada trade result (win/loss), insight penting, atau Commander kasih feedback -> LANGSUNG simpan pakai save_memory. Makin banyak memori, makin pinter aku di sesi berikutnya. Kalau Commander bilang 'ingat ini' atau 'jangan lupa' -> importance 3-4.",
      category: "lesson",
      importance: 4,
      tags: "memory,habit,discipline",
    },
    {
      id: "seed_grading",
      content: "Grading setup: A+ = Daily searah + M30/M15 F3 SEARAH + entry di Fundamental SNR. A = Daily searah + M30/M15 F3 searah + minor SNR. B = Daily searah + H4/H1 F3 tapi M30/M15 belum F3 searah. C = berlawanan Daily / masih F1-F2 = SKIP. Lot: A+=full, A=0.01, B=0.005, C=jangan.",
      category: "lesson",
      importance: 3,
      tags: "grading,A+,A,B,C,lot-sizing",
    },
    {
      id: "seed_session_awareness",
      content: "Session timing XAUUSD: Asia (00:00-08:00 WIB) = range sempit, VR sering palsu, scalp saja. London Open (14:00-16:00 WIB) = VR paling valid, watch closely. NY Open (19:30-21:00 WIB) = momentum terbesar, CF di sini = high confidence. NY Close (02:00-04:00 WIB) = sering reversal akhir, JANGAN entry baru.",
      category: "market_insight",
      importance: 3,
      tags: "session,timing,Asia,London,NY",
    },
    {
      id: "seed_sl_discipline",
      content: "SL HARUS dari data OHLC — BUKAN angka bulat. Sebelum tulis trade plan, WAJIB panggil get_ohlc untuk ambil High/Low candle VR + buffer 3-5 pts. Kalau OHLC gagal, pakai Fundamental SNR sebagai fallback sementara. Juga WAJIB panggil calculate_risk sebelum present plan.",
      category: "lesson",
      importance: 3,
      tags: "SL,OHLC,discipline,risk",
    },
    {
      id: "seed_agent_power",
      content: "Aku punya akses penuh ke komputer Commander via: shell_exec (PowerShell apapun), read_file (baca file), write_file (tulis/edit file), list_dir (browse folder), screenshot_analyze (lihat layar + vision). Project paths: sultan-advisor ada di D:\\PROJECT TRADING\\sultan-advisor. MT5 SEDANG TIDAK DIPAKAI — pakai TradingView via trigger_sync saja.",
      category: "preference",
      importance: 4,
      tags: "agent,paths,filesystem,shell,no-mt5",
    },
    {
      id: "seed_storyline_doctrine",
      content: "STORYLINE FRACTAL (doktrin inti): VR bukan cuma retracement — VR adalah CMP di TF bawahnya dengan storyline sendiri. CMP H1 SELL -> storyline: VR M30 -> CF M15. Tapi VR M30 = CMP M30 SELL -> storyline M30: VR M15 -> CF M5. SEMUA storyline bawah harus selesai sebelum CMP atas bisa jalan. Kenapa Daily SELL tapi market naik? Karena H4 belum VR dan CF — storyline belum selesai.",
      category: "lesson",
      importance: 4,
      tags: "storyline,fractal,nested,VR,CMP",
    },
    {
      id: "seed_active_cmp_detection",
      content: "CARA BACA CMP AKTIF: Lihat TF mana yang sedang VR sekarang -> TF satu level di atasnya = CMP yang sedang aktif dan diuji. VR di M15 -> CMP aktif = M30. VR di M30 -> CMP aktif = H1. VR di H1 -> CMP aktif = H4. Saat H4 BO BUY -> SEMUA TF bawah ikut BO BUY serentak -> jika ada TF bawah yang SELL = itu VR, bukan CMP baru.",
      category: "lesson",
      importance: 4,
      tags: "CMP-aktif,VR,detection,H4,M30",
    },
    {
      id: "seed_conti_entries",
      content: "CONTI ENTRY (3 jenis valid): (1) Daily CONTI: Daily CMP BO + H4 BELUM VR -> entry setiap H1 BO searah, pakai SOP H1. (2) H4 CONTI: H4 CMP BO + H1 BELUM VR -> entry setiap M30 BO searah H4, pakai SOP M30. (3) H1 CONTI: H1 CMP BO + M30 BELUM VR -> entry setiap M15 BO searah H1, pakai SOP M15, TP 10-20pts wajib take profit. Size conti lebih kecil dari setup VR+CF normal.",
      category: "lesson",
      importance: 4,
      tags: "conti,continuation,Daily,H4,H1,SOP",
    },
    {
      id: "seed_tp_barrier",
      content: "TP TARGET = LEFT BARRIER. TP bukan angka bulat — TP adalah area reversal dari breakout kiri sebelumnya yang membentuk CMP saat ini. Right breakout (terbaru) = arah CMP. Left breakout (sebelumnya) = TP area. Sebelum entry, identifikasi: right barrier (level CMP) dan left barrier (TP target). TP per TF: M15=10-20pts (wajib TP cepat), M30=20-40pts, H1=40-80pts, H4=80-150pts, Daily=150+pts.",
      category: "lesson",
      importance: 4,
      tags: "TP,barrier,left-barrier,right-barrier,target",
    },
    {
      id: "seed_self_upgrade",
      content: "Aku bisa upgrade diri sendiri dan dashboard. Cara upgrade dashboard: (1) read_file komponen yang mau diubah, (2) write_file dengan konten baru, (3) shell_exec 'npx next build', (4) shell_exec 'npx next start -p 3002'. Cara upgrade kemampuanku: edit lib/system-prompt.ts atau db/index.ts (seed memories). Commander sudah kasih izin penuh.",
      category: "lesson",
      importance: 4,
      tags: "self-upgrade,dashboard,build,deploy",
    },
  ];

  const insert = sqlite.prepare(
    "INSERT OR REPLACE INTO memories (id, content, category, importance, tags, created_at) VALUES (?, ?, ?, ?, ?, unixepoch())"
  );
  for (const m of seedMemories) {
    insert.run(m.id, m.content, m.category, m.importance, m.tags);
  }
}

export const db = drizzle(sqlite, { schema });
