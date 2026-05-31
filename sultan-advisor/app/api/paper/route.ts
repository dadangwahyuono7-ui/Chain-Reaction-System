import { db } from "@/db";
import { paperAccounts, paperTrades, memories } from "@/db/schema";
import { eq, and, desc } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { nanoid } from "nanoid";
import { generateText } from "ai";
import { createAnthropic } from "@ai-sdk/anthropic";

// ── Helpers ──────────────────────────────────────────────────────────────────

function isGold(sym: string) { return /XAU|GOLD/i.test(sym || ""); }

// R-multiple universal (instrument-agnostic): seberapa banyak kelipatan risk.
// BUY  : reward = exit - entry, risk = |entry - sl|
// SELL : reward = entry - exit, risk = |entry - sl|
function computeR(direction: string, entry: number, sl: number, exit: number): number {
  const riskDist = Math.abs(entry - sl);
  if (riskDist === 0) return 0;
  const reward = direction === "BUY" ? exit - entry : entry - exit;
  return reward / riskDist;
}

function classify(r: number): "WIN" | "LOSS" | "BE" {
  if (r > 0.05) return "WIN";
  if (r < -0.05) return "LOSS";
  return "BE";
}

async function getAccounts() {
  return db.select().from(paperAccounts);
}

// ── GET: list akun + trades (+ stats ringkas) ────────────────────────────────

export async function GET(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const url = new URL(req.url);
  const accountId = url.searchParams.get("account"); // optional filter

  const accounts = await getAccounts();
  const tradesRaw = accountId
    ? await db.select().from(paperTrades).where(eq(paperTrades.accountId, accountId)).orderBy(desc(paperTrades.openedAt)).limit(200)
    : await db.select().from(paperTrades).orderBy(desc(paperTrades.openedAt)).limit(200);

  // Stats per akun
  const stats: Record<string, {
    open: number; wins: number; losses: number; be: number;
    totalR: number; winRate: number; avgR: number; expectancy: number;
  }> = {};
  for (const acc of accounts) {
    const t = tradesRaw.filter(x => x.accountId === acc.id);
    const closed = t.filter(x => x.status !== "OPEN");
    const wins = closed.filter(x => x.status === "WIN").length;
    const losses = closed.filter(x => x.status === "LOSS").length;
    const be = closed.filter(x => x.status === "BE").length;
    const totalR = closed.reduce((s, x) => s + (x.rMultiple ?? 0), 0);
    stats[acc.id] = {
      open: t.filter(x => x.status === "OPEN").length,
      wins, losses, be,
      totalR: +totalR.toFixed(2),
      winRate: closed.length ? +(wins / closed.length * 100).toFixed(1) : 0,
      avgR: closed.length ? +(totalR / closed.length).toFixed(2) : 0,
      expectancy: closed.length ? +(totalR / closed.length).toFixed(2) : 0,
    };
  }

  return Response.json({ accounts, trades: tradesRaw, stats });
}

// ── POST: actions open | close | close_all | reset ───────────────────────────

export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const action = body.action as string;

  // ── OPEN ───────────────────────────────────────────────────────────────────
  if (action === "open") {
    const {
      accountId, instrument, direction, entryPrice, slPrice,
      tp1Price, tp2Price, setupTf, grade, cfType, cfCount, openReason,
    } = body;

    if (!accountId || !instrument || !direction || entryPrice == null || slPrice == null) {
      return Response.json({ error: "Field wajib: accountId, instrument, direction, entryPrice, slPrice" }, { status: 400 });
    }
    if (Math.abs(Number(entryPrice) - Number(slPrice)) === 0) {
      return Response.json({ error: "SL tidak boleh sama dengan entry (risk 0)" }, { status: 400 });
    }

    // Anti-dobel: skip kalau sudah ada trade OPEN dgn instrument+direction+TF sama di akun ini
    const dupes = await db.select().from(paperTrades).where(
      and(eq(paperTrades.accountId, accountId), eq(paperTrades.status, "OPEN"))
    );
    const dup = dupes.find(t => t.instrument === instrument && t.direction === direction && (t.setupTf ?? "") === (setupTf ?? ""));
    if (dup) return Response.json({ success: false, skipped: true, reason: "Sudah ada posisi OPEN serupa", trade: dup });

    const id = nanoid();
    const row = {
      id, accountId, instrument, direction,
      setupTf: setupTf ?? null, grade: grade ?? null,
      cfType: cfType ?? null, cfCount: cfCount ?? null,
      entryPrice: Number(entryPrice), slPrice: Number(slPrice),
      tp1Price: tp1Price != null ? Number(tp1Price) : null,
      tp2Price: tp2Price != null ? Number(tp2Price) : null,
      status: "OPEN" as const,
      openReason: openReason ?? null,
    };
    await db.insert(paperTrades).values(row);
    return Response.json({ success: true, trade: row });
  }

  // ── CLOSE (satu trade) ───────────────────────────────────────────────────────
  if (action === "close") {
    const { tradeId, exitPrice, closeReason } = body;
    if (!tradeId || exitPrice == null) {
      return Response.json({ error: "Field wajib: tradeId, exitPrice" }, { status: 400 });
    }
    const t = await db.select().from(paperTrades).where(eq(paperTrades.id, tradeId)).get();
    if (!t) return Response.json({ error: "Trade tidak ditemukan" }, { status: 404 });
    if (t.status !== "OPEN") return Response.json({ success: false, reason: "Trade sudah ditutup", trade: t });

    const r = computeR(t.direction, t.entryPrice, t.slPrice, Number(exitPrice));
    const status = classify(r);
    const acc = await db.select().from(paperAccounts).where(eq(paperAccounts.id, t.accountId)).get();
    const risk = acc?.riskPerTrade ?? 100_000;
    const pnl = +(r * risk).toFixed(2);

    await db.update(paperTrades).set({
      exitPrice: Number(exitPrice), status, rMultiple: +r.toFixed(3), pnl,
      closeReason: closeReason ?? null, closedAt: new Date(),
    }).where(eq(paperTrades.id, tradeId));

    if (acc) {
      await db.update(paperAccounts).set({
        balance: +(acc.balance + pnl).toFixed(2), updatedAt: new Date(),
      }).where(eq(paperAccounts.id, acc.id));
    }
    // ── POST-TRADE REFLECTION (hanya akun AI) ────────────────────────────────
    // Setiap trade AI tutup → Claude refleksi → simpan lesson ke memories table
    if (t.accountId === "ai") {
      // fire-and-forget — jangan block response
      void (async () => {
        try {
          const recentAI = await db.select().from(paperTrades)
            .where(and(eq(paperTrades.accountId, "ai")))
            .orderBy(desc(paperTrades.closedAt)).limit(10).all();
          const wins   = recentAI.filter(x => x.status === "WIN").length;
          const losses = recentAI.filter(x => x.status === "LOSS").length;
          const totalR = recentAI.reduce((s, x) => s + (x.rMultiple ?? 0), 0);

          const reflectPrompt = `Kamu adalah AI trading advisor yang sedang belajar trading menggunakan sistem Chain Reaction (CMP→VR→CF) milik Commander Dadang.

TRADE BARU SAJA TUTUP (akun AI kamu):
- Instrumen : ${t.instrument}
- Setup TF  : ${t.setupTf}
- Arah      : ${t.direction}
- CF Type   : ${t.cfType || "—"} #${t.cfCount || "?"}
- Grade     : ${t.grade || "?"}
- Entry     : ${t.entryPrice}
- SL        : ${t.slPrice}
- Exit      : ${exitPrice}
- Hasil     : ${status} | R = ${r.toFixed(2)}
- Alasan masuk: ${t.openReason || "—"}
- Alasan tutup: ${closeReason || "SL/TP hit"}

PERFORMA AI TERAKHIR (10 trade):
- WIN: ${wins} | LOSS: ${losses} | Total R: ${totalR.toFixed(2)}

Refleksikan trade ini dalam 2-3 kalimat:
1. Kenapa hasilnya ${status}? Apakah ada yang bisa dipelajari dari setup ini?
2. Pola apa yang terlihat dari hasil ${wins}W/${losses}L terakhir?
3. Satu pelajaran konkret untuk keputusan berikutnya.

Jawab dalam format JSON:
{
  "lesson": "pelajaran utama 1-2 kalimat",
  "pattern": "pola yang terdeteksi (atau 'belum cukup data')",
  "importance": 1-4
}`;

          const client = createAnthropic({
            apiKey:  process.env.BLUEPACK_API_KEY ?? "",
            baseURL: process.env.BLUEPACK_BASE_URL ?? "https://ai.bluepack.my.id/v1",
          });
          const { text } = await generateText({
            model: client(process.env.BLUEPACK_MODEL ?? "claude-3-5-haiku-20241022") as Parameters<typeof generateText>[0]["model"],
            messages: [{ role: "user", content: reflectPrompt }],
            maxOutputTokens: 300,
          });

          const jsonMatch = text.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            const parsed = JSON.parse(jsonMatch[0]);
            const lesson    = parsed.lesson    || "";
            const pattern   = parsed.pattern   || "";
            const importance = Math.min(4, Math.max(1, parseInt(parsed.importance) || 2));
            if (lesson) {
              await db.insert(memories).values({
                id:         nanoid(),
                content:    `[TRADE ${status} R=${r.toFixed(2)}] ${t.instrument} ${t.direction} ${t.setupTf} CF${t.cfType||""} — ${lesson}${pattern ? ` | POLA: ${pattern}` : ""}`,
                category:   "trade_result",
                importance,
                tags:       `${t.instrument},${t.setupTf},${t.direction},${status}`,
                createdAt:  new Date(),
              });
            }
          }
        } catch { /* non-fatal — jangan ganggu response */ }
      })();
    }

    return Response.json({ success: true, status, rMultiple: +r.toFixed(3), pnl });
  }

  // ── RESET (kosongkan trades + balikin saldo) ─────────────────────────────────
  if (action === "reset") {
    const { accountId } = body;
    if (accountId) {
      await db.delete(paperTrades).where(eq(paperTrades.accountId, accountId));
      const acc = await db.select().from(paperAccounts).where(eq(paperAccounts.id, accountId)).get();
      if (acc) await db.update(paperAccounts).set({ balance: acc.initialBalance, updatedAt: new Date() }).where(eq(paperAccounts.id, accountId));
    } else {
      await db.delete(paperTrades);
      const accs = await getAccounts();
      for (const a of accs) await db.update(paperAccounts).set({ balance: a.initialBalance, updatedAt: new Date() }).where(eq(paperAccounts.id, a.id));
    }
    return Response.json({ success: true });
  }

  return Response.json({ error: `Action tidak dikenal: ${action}` }, { status: 400 });
}
