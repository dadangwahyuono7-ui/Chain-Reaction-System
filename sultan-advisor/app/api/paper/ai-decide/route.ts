/**
 * /api/paper/ai-decide
 *
 * Dipanggil tiap CF fire. AI evaluasi setup pakai Claude,
 * lalu DECIDE: ENTER atau SKIP.
 *
 * Kalau ENTER → buka trade di akun "ai".
 * Kalau SKIP  → catat alasan, tidak buka trade.
 */

import { generateText } from "ai";
import { createAnthropic } from "@ai-sdk/anthropic";
import { db } from "@/db";
import { marketContext, paperAccounts, paperTrades, memories } from "@/db/schema";
import { eq, desc, and } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { nanoid } from "nanoid";

export const dynamic = "force-dynamic";

// SNR keys untuk compute auto SL/TP (sama dengan di market-panel)
const SNR_KEYS = [
  "PDH","PDL","DAILY_OPEN","PWH","PWL","WEEKLY_OPEN",
  "PMH","PML","ASIA_H","ASIA_L","LONDON_H","LONDON_L",
  "ROUND_ABOVE","ROUND_BELOW",
];

function computeLevels(dir: "BUY"|"SELL", entry: number, ctx: Record<string,string>) {
  const levels = SNR_KEYS.map(k => parseFloat(ctx[k] || "")).filter(v => !isNaN(v) && v > 0);
  const above  = levels.filter(v => v > entry).sort((a,b) => a-b);
  const below  = levels.filter(v => v < entry).sort((a,b) => b-a);
  const pct    = entry * 0.003;
  if (dir === "BUY")  return { sl: below[0] ?? entry - pct, tp1: above[0] ?? entry + pct*2, tp2: above[1] ?? null };
  return               { sl: above[0] ?? entry + pct, tp1: below[0] ?? entry - pct*2, tp2: below[1] ?? null };
}

export async function POST(req: Request) {
  // Auth tidak wajib karena dipanggil dari server-side autopilot,
  // tapi kita tetap cek kalau ada session
  try { await auth.api.getSession({ headers: await headers() }); } catch { /* ok */ }

  const body = await req.json().catch(() => ({}));
  const { tf, direction, instrument, entryPrice, cfType, cfCount, slPrice, tp1Price, tp2Price } = body;

  if (!tf || !direction || !instrument || !entryPrice) {
    return Response.json({ decision: "SKIP", reason: "Parameter tidak lengkap" }, { status: 400 });
  }

  // 1. Ambil market context + memori AI dari DB
  const ctxRows = await db.select().from(marketContext);
  const ctx: Record<string,string> = Object.fromEntries(ctxRows.map(r => [r.variableName, r.value]));

  // Ambil 5 memori terakhir dari trade result — AI belajar dari pengalaman sendiri
  const recentMemories = await db.select().from(memories)
    .where(eq(memories.category, "trade_result"))
    .orderBy(desc(memories.createdAt)).limit(5).all();

  // Performa AI terakhir
  const aiTrades = await db.select().from(paperTrades)
    .where(and(eq(paperTrades.accountId, "ai")))
    .orderBy(desc(paperTrades.closedAt)).limit(20).all();
  const aiClosed = aiTrades.filter(t => t.status !== "OPEN");
  const aiWins   = aiClosed.filter(t => t.status === "WIN").length;
  const aiLosses = aiClosed.filter(t => t.status === "LOSS").length;
  const aiTotalR = aiClosed.reduce((s, t) => s + (t.rMultiple ?? 0), 0);

  // 2. Build state table
  const TFS = ["DAILY","H4","H1","M30","M15","M5"];
  const tfLines = TFS.map(t => {
    const cmp = ctx[`${t}_CMP`]; if (!cmp) return null;
    const vr  = ctx[`${t}_VR`]  || "—";
    const cf  = ctx[`${t}_CF`]  || "—";
    const fase = (vr === "YA" && cf === "YA") ? "F3" : vr === "YA" ? "F2" : "F1";
    return `${t.padEnd(6)}| ${(cmp === "BULLISH" ? "BUY" : "SELL").padEnd(6)}| VR:${vr.padEnd(5)}| CF:${cf.padEnd(6)}| ${fase}`;
  }).filter(Boolean);

  const snrInfo = SNR_KEYS.filter(k => ctx[k]).map(k => `${k}:${ctx[k]}`).join(" ");
  const harga   = ctx["HARGA"] || String(entryPrice);
  const spread  = ctx["SPREAD"] || "—";
  const session = ctx["SESSION"] || "—";
  const nextEvt = ctx["NEXT_EVENT_NAME"] || "";
  const nextMin = ctx["NEXT_EVENT_EPOCH"] ? Math.floor((parseInt(ctx["NEXT_EVENT_EPOCH"]) - Date.now()) / 60000) : null;
  const newsWarn = nextMin !== null && nextMin >= 0 && nextMin <= 15 ? `⚠️ NEWS DALAM ${nextMin} MENIT: ${nextEvt}` : "";

  // 3. Tanya Claude — structured decision dengan konteks memori
  const memorySection = recentMemories.length > 0
    ? `\nPENGALAMAN KAMU SEBELUMNYA (dari trade nyata):\n${recentMemories.map(m => `- ${m.content}`).join("\n")}\n`
    : "\nPENGALAMAN: Belum ada trade selesai — ini awal pembelajaran.\n";

  const perfSection = aiClosed.length > 0
    ? `PERFORMA AI SEJAUH INI: ${aiWins}W/${aiLosses}L | Total R: ${aiTotalR.toFixed(2)} dari ${aiClosed.length} trade`
    : "PERFORMA AI: Belum ada trade selesai.";

  const prompt = `Kamu adalah AI trading advisor yang sedang belajar menjadi master trader. Setiap keputusan kamu dicatat dan kamu belajar dari hasilnya.
${memorySection}
${perfSection}

Buat keputusan MASUK atau SKIP untuk setup berikut:

CF BARU FIRE:
- Instrumen : ${instrument}
- TF Setup  : ${tf}
- Arah      : ${direction}
- CF Type   : ${cfType || "—"} | CF #${cfCount || "?"}
- Harga     : ${harga}
- Spread    : ${spread} | Session: ${session}
${newsWarn}

STATE MARKET SAAT INI:
TF     | CMP    | VR     | CF     | FASE
-------+--------+--------+--------+-----
${tfLines.join("\n")}

SNR LEVELS: ${snrInfo || "belum sync"}

ATURAN KEPUTUSAN (doktrin Chain Reaction):
- ENTER kalau: setup F3 di TF relevan SEARAH dengan H4/Daily, spread wajar, tidak ada news blackout
- SKIP kalau: berlawanan H4/Daily, F1 semua TF, spread > 35, news < 15 menit, atau setup lemah (CF #1 HIGH tanpa konfirmasi TF besar)
- Untuk ${tf} setup: perlu minimal H4 searah atau Daily searah sebagai master
- Grade A/A+: masuk. Grade B: masuk tapi catat. Grade C: SKIP.

Jawab HANYA dalam format JSON berikut (tidak ada teks lain):
{
  "decision": "ENTER" or "SKIP",
  "grade": "A+" or "A" or "B" or "C",
  "reason": "alasan singkat 1 kalimat",
  "risk_note": "catatan risiko kalau ada, atau kosong"
}`;

  let decision = "SKIP";
  let grade    = "C";
  let reason   = "AI tidak bisa evaluasi";
  let riskNote = "";

  try {
    const client = createAnthropic({
      apiKey:  process.env.BLUEPACK_API_KEY ?? "",
      baseURL: process.env.BLUEPACK_BASE_URL ?? "https://ai.bluepack.my.id/v1",
    });
    const { text } = await generateText({
      model: client(process.env.BLUEPACK_MODEL ?? "claude-3-5-haiku-20241022") as Parameters<typeof generateText>[0]["model"],
      messages: [{ role: "user", content: prompt }],
      maxOutputTokens: 200,
    });

    // Parse JSON dari respons AI
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      decision = parsed.decision === "ENTER" ? "ENTER" : "SKIP";
      grade    = parsed.grade    || grade;
      reason   = parsed.reason   || reason;
      riskNote = parsed.risk_note || "";
    }
  } catch (e) {
    // Kalau AI gagal → default SKIP untuk keamanan
    reason = `AI error: ${e instanceof Error ? e.message.slice(0,80) : "unknown"} → default SKIP`;
  }

  // 4. Kalau ENTER → buka trade di akun AI
  if (decision === "ENTER") {
    const acc = await db.select().from(paperAccounts).where(eq(paperAccounts.id, "ai")).get();
    const levels = computeLevels(
      direction as "BUY"|"SELL",
      Number(entryPrice),
      ctx
    );
    const tradeId = nanoid();
    await db.insert(paperTrades).values({
      id:         tradeId,
      accountId:  "ai",
      instrument,
      direction,
      setupTf:    tf,
      grade,
      cfType:     cfType ?? null,
      cfCount:    cfCount ?? null,
      entryPrice: Number(entryPrice),
      slPrice:    slPrice ?? levels.sl,
      tp1Price:   tp1Price ?? levels.tp1,
      tp2Price:   tp2Price ?? levels.tp2,
      status:     "OPEN",
      openReason: `[AI-Judge ${grade}] ${reason}${riskNote ? ` | ${riskNote}` : ""}`,
    });

    // Update saldo (belum berubah sampai trade ditutup)
    if (acc) {
      await db.update(paperAccounts).set({ updatedAt: new Date() }).where(eq(paperAccounts.id, "ai"));
    }

    return Response.json({ decision: "ENTER", grade, reason, riskNote, tradeId });
  }

  // 5. SKIP — catat di log tapi jangan buka trade
  return Response.json({ decision: "SKIP", grade, reason, riskNote });
}
