import { streamText, tool, stepCountIs, type LanguageModel } from "ai";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { createAnthropic } from "@ai-sdk/anthropic";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { messages, chatSessions, marketContext } from "@/db/schema";
import { eq } from "drizzle-orm";
import { buildSystemPrompt } from "@/lib/system-prompt";
import { headers } from "next/headers";
import { nanoid } from "nanoid";
import { z } from "zod";

// ─── Model Builder ────────────────────────────────────────────────────────────

function buildLocalModel(): LanguageModel {
  const client = createOpenAICompatible({
    name: "local",
    apiKey:   process.env.LLM_API_KEY  ?? "local",
    baseURL:  process.env.LLM_BASE_URL ?? "http://localhost:8080/v1",
    fetch: async (url, options) => {
      if (options?.body) {
        try {
          const body = JSON.parse(options.body as string);
          body.chat_template_kwargs = { enable_thinking: false };
          return fetch(url, { ...options, body: JSON.stringify(body) });
        } catch { /* fall through */ }
      }
      return fetch(url, options as RequestInit);
    },
  });
  return client(process.env.LLM_MODEL ?? "qwen3-8b-q4.gguf");
}

function buildCloudModel(): LanguageModel {
  const client = createAnthropic({
    apiKey:  process.env.BLUEPACK_API_KEY ?? "",
    baseURL: process.env.BLUEPACK_BASE_URL ?? "https://ai.bluepack.my.id/v1",
  });
  return client(process.env.BLUEPACK_MODEL ?? "claude-3-5-haiku-20241022") as LanguageModel;
}

// ─── Web Search Tool ──────────────────────────────────────────────────────────

// ── Parse Yahoo Finance RSS ────────────────────────────────────────────────
async function fetchYFRss(symbol: string, maxItems = 5): Promise<string[]> {
  const res = await fetch(
    `https://finance.yahoo.com/rss/headline?s=${encodeURIComponent(symbol)}`,
    { headers: { "User-Agent": "Mozilla/5.0 SultanAdvisor/1.0" }, signal: AbortSignal.timeout(8000) }
  );
  if (!res.ok) throw new Error(`RSS ${res.status}`);
  const xml = await res.text();
  const items: string[] = [];
  const re = /<item[\s\S]*?<title>([\s\S]*?)<\/title>[\s\S]*?(?:<pubDate>([\s\S]*?)<\/pubDate>)?[\s\S]*?(?:<description>([\s\S]*?)<\/description>)?[\s\S]*?<\/item>/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(xml)) !== null && items.length < maxItems) {
    const title = m[1].replace(/<!\[CDATA\[|\]\]>/g, "").trim();
    const date  = m[2]?.trim().slice(0, 16) ?? "";
    const desc  = m[3]?.replace(/<!\[CDATA\[|\]\]>/g, "").replace(/<[^>]+>/g, " ").trim().slice(0, 120) ?? "";
    if (title) items.push(`• [${date}] ${title}${desc ? ` — ${desc}` : ""}`);
  }
  return items;
}

async function webSearch(query: string): Promise<string> {
  const isGoldQuery  = /gold|xauusd|xau|comex|bullion|emas|silver|precious/i.test(query);
  const isMacroQuery = /dollar|dxy|yield|bond|fed|fomc|cpi|nfp|inflation|rate|treasury/i.test(query);

  // ── 1. Yahoo Finance RSS — reliable, no rate-limit ─────────────────────────
  // Gold + macro queries benefit most from YF headlines
  if (isGoldQuery || isMacroQuery) {
    try {
      const parts: string[] = [];

      // 10Y Treasury Yield news → most relevant gold catalyst (yields ↑ = gold ↓)
      const tnxItems = await fetchYFRss("^TNX", 4);
      if (tnxItems.length > 0) parts.push(`📊 Treasury/Yield News:\n${tnxItems.join("\n")}`);

      // Gold futures news (GC=F) — mining + price commentary
      if (isGoldQuery) {
        const gcItems = await fetchYFRss("GC=F", 3);
        if (gcItems.length > 0) parts.push(`🥇 Gold (GC=F) News:\n${gcItems.join("\n")}`);
      }

      if (parts.length > 0) {
        return `📰 Yahoo Finance — query: "${query}"\n\n${parts.join("\n\n")}`;
      }
    } catch { /* fallthrough */ }
  }

  // ── 2. Brave Search HTML — general / non-financial queries ─────────────────
  try {
    const res = await fetch(
      `https://search.brave.com/search?q=${encodeURIComponent(query)}&source=web`,
      {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
          "Accept": "text/html,application/xhtml+xml",
          "Accept-Language": "en-US,en;q=0.9",
        },
        signal: AbortSignal.timeout(12000),
      }
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const html = await res.text();
    const snippets: string[] = [];
    const snipRe = /class="generic-snippet[^"]*"[^>]*>([\s\S]*?)<\/div>\s*<\/div>/gi;
    let m: RegExpExecArray | null;
    while ((m = snipRe.exec(html)) !== null && snippets.length < 5) {
      const text = m[1]
        .replace(/<[^>]+>/g, " ")
        .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
        .replace(/\s{2,}/g, " ").trim();
      if (text.length > 20) snippets.push(text.slice(0, 200));
    }
    if (snippets.length > 0) {
      return `🌐 Web search: "${query}"\n${snippets.map((s, i) => `${i+1}. ${s}`).join("\n")}`;
    }
  } catch { /* fallthrough */ }

  // ── 3. Fallback ────────────────────────────────────────────────────────────
  return `Tidak ada hasil untuk "${query}". Coba kata kunci lebih spesifik, atau info sudah ada di context market.`;
}

async function fetchOHLC(tf: string, bars: number): Promise<string> {
  const intervalMap: Record<string, string> = {
    H4: "4h", H1: "1h", M30: "30m", M15: "15m", M5: "5m",
  };
  const rangeMap: Record<string, string> = {
    H4: "5d", H1: "2d", M30: "1d", M15: "1d", M5: "1d",
  };

  const interval = intervalMap[tf] ?? "1h";
  const range    = rangeMap[tf]    ?? "2d";
  const apiUrl   = `https://query2.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=${interval}&range=${range}&includePrePost=false`;

  const res = await fetch(apiUrl, {
    headers: {
      "User-Agent": "Mozilla/5.0 SultanAdvisor/1.0",
      "Accept": "application/json",
    },
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`Yahoo Finance HTTP ${res.status}`);

  const data = await res.json() as {
    chart: {
      result: Array<{
        timestamp: number[];
        indicators: {
          quote: Array<{
            open:  (number | null)[];
            high:  (number | null)[];
            low:   (number | null)[];
            close: (number | null)[];
          }>;
        };
      }> | null;
    };
  };

  const result = data.chart?.result?.[0];
  if (!result) throw new Error("Tidak ada data chart dari Yahoo Finance");

  const timestamps = result.timestamp ?? [];
  const quote      = result.indicators?.quote?.[0] ?? { open: [], high: [], low: [], close: [] };
  const opens      = quote.open  ?? [];
  const highs      = quote.high  ?? [];
  const lows       = quote.low   ?? [];
  const closes     = quote.close ?? [];

  // Filter indeks candle valid (tidak null)
  const validIdx = timestamps
    .map((_, i) => i)
    .filter(i => opens[i] != null && closes[i] != null);

  const n = Math.min(bars, validIdx.length);
  const sliceIdx = validIdx.slice(-n);

  if (sliceIdx.length === 0) throw new Error("Tidak ada candle valid di data yang dikembalikan");

  const lines: string[] = [
    `📊 OHLC ${tf} — GC=F COMEX Gold Futures — ${sliceIdx.length} candle terakhir`,
    `(Referensi presisi untuk SL/TP placement sesuai doktrin)`,
    ``,
    `No | Waktu WIB            | Open      | High      | Low       | Close    `,
    `---|----------------------|-----------|-----------|-----------|----------`,
  ];

  sliceIdx.forEach((i, idx) => {
    const wibStr = new Date(timestamps[i] * 1000).toLocaleString("id-ID", {
      timeZone: "Asia/Jakarta",
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
    const o = ((opens[i]  ?? 0) as number).toFixed(2).padStart(9);
    const h = ((highs[i]  ?? 0) as number).toFixed(2).padStart(9);
    const l = ((lows[i]   ?? 0) as number).toFixed(2).padStart(9);
    const c = ((closes[i] ?? 0) as number).toFixed(2).padStart(9);
    const flag = idx === sliceIdx.length - 1 ? " ← CANDLE AKTIF" : "";
    lines.push(`${String(idx + 1).padStart(2)} | ${wibStr.padEnd(20)} | ${o} | ${h} | ${l} | ${c}${flag}`);
  });

  // Ringkasan referensi SL berdasarkan doktrin VR high/low
  if (sliceIdx.length >= 2) {
    const prevI = sliceIdx[sliceIdx.length - 2];
    const prevH = ((highs[prevI] ?? 0) as number).toFixed(2);
    const prevL = ((lows[prevI]  ?? 0) as number).toFixed(2);
    lines.push(``);
    lines.push(`💡 REFERENSI SL (doktrin: SL di high/low candle VR + buffer 3-5 pts):`);
    lines.push(`   Candle [-1] High : ${prevH} → SL SELL jika ${tf} adalah TF VR naik`);
    lines.push(`   Candle [-1] Low  : ${prevL} → SL BUY  jika ${tf} adalah TF VR turun`);
    lines.push(`   Candle aktif High: ${((highs[sliceIdx[sliceIdx.length - 1]] ?? 0) as number).toFixed(2)}`);
    lines.push(`   Candle aktif Low : ${((lows[sliceIdx[sliceIdx.length - 1]]  ?? 0) as number).toFixed(2)}`);
  }

  return lines.join("\n");
}

async function fetchUrl(url: string): Promise<string> {
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
      },
      signal: AbortSignal.timeout(12000),
    });
    if (!res.ok) return `Fetch gagal: HTTP ${res.status}`;
    const html = await res.text();

    // Strip scripts, styles, nav, footer, ads
    const cleaned = html
      .replace(/<script[\s\S]*?<\/script>/gi, "")
      .replace(/<style[\s\S]*?<\/style>/gi, "")
      .replace(/<nav[\s\S]*?<\/nav>/gi, "")
      .replace(/<footer[\s\S]*?<\/footer>/gi, "")
      .replace(/<header[\s\S]*?<\/header>/gi, "")
      .replace(/<aside[\s\S]*?<\/aside>/gi, "")
      .replace(/<!--[\s\S]*?-->/g, "")
      .replace(/<[^>]+>/g, " ")
      .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
      .replace(/&nbsp;/g, " ").replace(/&#\d+;/g, " ")
      .replace(/\s{3,}/g, "\n")
      .trim();

    // Take first 4000 chars (enough for article content)
    const text = cleaned.slice(0, 4000);
    return text || "Konten kosong atau tidak bisa dibaca.";
  } catch (e) {
    return `Fetch URL gagal: ${e instanceof Error ? e.message : String(e)}`;
  }
}

// ─── Tools definition ─────────────────────────────────────────────────────────

const searchTools = {
  web_search: tool({
    description: [
      "Cari informasi di internet.",
      "Gunakan HANYA untuk: berita gold/XAUUSD terbaru, data fundamental (DXY, yields, NFP, CPI, FOMC), atau info yang TIDAK ada di system context.",
      "JANGAN gunakan untuk: analisis CMP/VR/CF (sudah ada di context), setup trade (gunakan context saja).",
      "Tips: query bahasa Inggris lebih akurat. Contoh: 'gold price news today', 'XAUUSD market catalyst', 'US dollar index today'.",
    ].join(" "),
    inputSchema: z.object({
      query: z.string().describe("Kata kunci pencarian dalam bahasa Inggris, spesifik, 3-8 kata"),
    }),
    execute: async ({ query }: { query: string }) => webSearch(query),
  }),
  fetch_url: tool({
    description: [
      "Buka dan baca konten halaman web dari URL tertentu.",
      "Gunakan kalau: user minta baca artikel spesifik, cek analisis dari situs tertentu (Reuters, Bloomberg, Kitco, Investing.com), atau user paste URL.",
      "Tidak perlu untuk pencarian umum — pakai web_search untuk itu.",
    ].join(" "),
    inputSchema: z.object({
      url: z.string().url().describe("URL lengkap halaman yang ingin dibaca (harus https://)"),
    }),
    execute: async ({ url }: { url: string }) => fetchUrl(url),
  }),
  get_ohlc: tool({
    description: [
      "Ambil data OHLC (Open, High, Low, Close) beberapa candle terakhir dari GC=F (COMEX Gold Futures) via Yahoo Finance.",
      "WAJIB dipanggil sebelum menulis trade plan untuk SL/TP presisi berdasarkan high/low candle VR.",
      "Gunakan untuk: (1) menentukan SL di puncak/bawah candle VR, bukan angka bulat, (2) cek struktur swing terkini, (3) validasi apakah entry area sudah di zona CF atau masih mid-range.",
      "Contoh pemakaian: setup SELL H1 → fetch get_ohlc M30 5 bars → SL = High candle VR M30 tertinggi + buffer 3-5 pts.",
    ].join(" "),
    inputSchema: z.object({
      tf:   z.enum(["H4", "H1", "M30", "M15", "M5"]).describe("Timeframe candle yang ingin dilihat"),
      bars: z.number().min(1).max(20).optional().describe("Jumlah candle terakhir (default 5, max 20)"),
    }),
    execute: async ({ tf, bars = 5 }: { tf: string; bars?: number }) => {
      try {
        return await fetchOHLC(tf, bars);
      } catch (e) {
        return `Gagal fetch OHLC ${tf}: ${e instanceof Error ? e.message : String(e)}. Coba lagi atau gunakan level fundamental SNR dari context sebagai referensi SL sementara.`;
      }
    },
  }),
};

// ─── POST handler ─────────────────────────────────────────────────────────────

export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const body = await req.json();
  const { messages: chatMessages, id: sessionId, model: modelChoice } = body;

  // Build system prompt from market context
  const ctxRows = await db.select().from(marketContext);
  const ctx = Object.fromEntries(
    ctxRows.map((r) => [r.variableName, { label: r.label, value: r.value }])
  );
  const systemPrompt = buildSystemPrompt(ctx);

  // Upsert session
  if (sessionId) {
    const existing = await db.select().from(chatSessions).where(eq(chatSessions.id, sessionId)).get();
    if (!existing) {
      await db.insert(chatSessions).values({ id: sessionId, userId: session.user.id, title: "Sesi Baru" });
    }
  }

  // Save user message
  const lastUserMsg = chatMessages?.at(-1);
  const userText = lastUserMsg?.role === "user"
    ? (lastUserMsg.content || (lastUserMsg.parts?.find((p: { type: string }) => p.type === "text")?.text ?? ""))
    : null;

  if (userText && sessionId) {
    await db.insert(messages).values({ id: nanoid(), sessionId, role: "user", content: userText });
    const existing = await db.select().from(chatSessions).where(eq(chatSessions.id, sessionId)).get();
    if (existing?.title === "Sesi Baru") {
      await db.update(chatSessions).set({ title: userText.slice(0, 60) }).where(eq(chatSessions.id, sessionId));
    }
  }

  const coreMessages = (chatMessages ?? [])
    .filter((m: { role: string }) => m.role === "user" || m.role === "assistant")
    .map((m: { role: string; content?: string; parts?: Array<{ type: string; text?: string }> }) => ({
      role: m.role as "user" | "assistant",
      content: m.content || (m.parts?.filter((p) => p.type === "text").map((p) => p.text).join("") ?? ""),
    }));

  // Auto-detect: kalau local minta → cek dulu apakah server hidup
  // Kalau mati → auto-fallback ke cloud (biar tidak perlu manual switch)
  let useCloud = modelChoice === "cloud";
  if (!useCloud) {
    const localBase = process.env.LLM_BASE_URL ?? "http://localhost:8080/v1";
    const localOk = await fetch(`${localBase}/models`, {
      signal: AbortSignal.timeout(1500),
    }).then(r => r.ok).catch(() => false);
    if (!localOk) useCloud = true; // fallback ke cloud
  }

  const selectedModel = useCloud ? buildCloudModel() : buildLocalModel();

  const result = streamText({
    model: selectedModel,
    system: systemPrompt,
    messages: coreMessages,
    maxOutputTokens: 4096,
    stopWhen: stepCountIs(5),  // max 5 tool call rounds (web search → answer)
    tools: searchTools,        // AI bisa browse web + fetch URL
    onFinish: async ({ text }) => {
      if (sessionId && text) {
        await db.insert(messages).values({ id: nanoid(), sessionId, role: "assistant", content: text });
      }
    },
  });

  return result.toUIMessageStreamResponse();
}
