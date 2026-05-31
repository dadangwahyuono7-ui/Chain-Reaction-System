/**
 * /api/news-sync — Fundamental Intelligence Engine
 *
 * Fetches all external data sources relevant to XAUUSD CFD trading:
 *  1. ForexFactory  — high-impact USD economic calendar
 *  2. CFTC Socrata  — COT positioning (large spec net long/short on COMEX gold)
 *  3. Yahoo Finance — DXY, 10Y yield, COMEX GC futures price/PDH/PDL
 *  4. Investing.com — gold/metals news headlines (RSS)
 *  5. FRED API      — real 10Y TIPS yield (optional, requires FRED_API_KEY in .env.local)
 *
 * All data upserted into market_context table → auto-injected into system prompt.
 */

import { db } from "@/db";
import { marketContext } from "@/db/schema";
import { eq } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

// ─── Types ───────────────────────────────────────────────────────────────────

interface FFEvent {
  title:    string;
  country:  string;
  impact:   string;
  date:     string;     // ISO datetime e.g. "2026-05-28T08:30:00-04:00"
  time?:    string;     // legacy field, may be absent
  forecast?: string;
  previous?: string;
  actual?:   string;
}

interface COTRow {
  report_date_as_yyyy_mm_dd:  string;
  noncomm_positions_long_all:  string;
  noncomm_positions_short_all: string;
  open_interest_all:           string;
}

interface YFMeta {
  regularMarketPrice:    number;
  regularMarketDayHigh:  number;
  regularMarketDayLow:   number;
  previousClose?:        number;  // spot/index symbols
  chartPreviousClose?:   number;  // futures (GC=F, etc) pakai ini
  currency?:             string;
}

// ─── Fetchers ────────────────────────────────────────────────────────────────

interface NextEvent { name: string; epoch: number; timeWIB: string }
interface CalendarResult { text: string; nextEvent: NextEvent | null }

/** ForexFactory economic calendar — official CDN, no key */
async function fetchEconCalendar(): Promise<CalendarResult> {
  // Try multiple FF CDN endpoints
  const FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
  ];
  const FF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":     "application/json, */*",
    "Referer":    "https://www.forexfactory.com/",
  };

  let res: Response | null = null;
  for (const url of FF_URLS) {
    try {
      res = await fetch(url, { headers: FF_HEADERS, signal: AbortSignal.timeout(15_000) });
      if (res.ok) break;
    } catch { continue; }
  }
  if (!res || !res.ok) throw new Error(`FF calendar gagal di semua endpoint`);

  const events: FFEvent[] = await res.json();
  const highImpact = events.filter(e => e.impact === "High" && (e.country === "USD" || e.country === "ALL"));

  // ── Next upcoming event for news blackout countdown ───────────────────────
  const nowMs = Date.now();
  const upcoming = highImpact
    .filter(e => { try { return new Date(e.date).getTime() > nowMs; } catch { return false; } })
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const nextRaw = upcoming[0] ?? null;
  const nextEvent: NextEvent | null = nextRaw ? {
    name:    nextRaw.title,
    epoch:   new Date(nextRaw.date).getTime(),
    timeWIB: new Date(nextRaw.date).toLocaleString("id-ID", {
      timeZone: "Asia/Jakarta", hour: "2-digit", minute: "2-digit", hour12: false,
    }) + " WIB",
  } : null;

  const lines = highImpact.map(e => {
    // Parse ISO date → readable WIB (UTC+7)
    const dt  = new Date(e.date);
    const wib = dt.toLocaleString("id-ID", { timeZone: "Asia/Jakarta", month:"short", day:"2-digit", hour:"2-digit", minute:"2-digit", hour12:false });
    const fc  = e.forecast ? ` | Est: ${e.forecast}` : "";
    const prv = e.previous ? ` | Prev: ${e.previous}` : "";
    const act = e.actual   ? ` | Aktual: ${e.actual}` : "";
    return `${wib} WIB — ${e.title}${fc}${prv}${act}`;
  });

  return {
    text: lines.length > 0 ? lines.join("\n") : "Tidak ada high-impact USD event minggu ini.",
    nextEvent,
  };
}

/** CFTC COT — COMEX Gold large speculator net position. No key needed. */
async function fetchCOTGold(): Promise<string> {
  const url =
    "https://publicreporting.cftc.gov/resource/6dca-aqww.json" +
    "?$limit=1" +
    "&$where=market_and_exchange_names='GOLD - COMMODITY EXCHANGE INC.'" +
    "&$order=report_date_as_yyyy_mm_dd DESC";

  const res = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0 (compatible; SultanAdvisor/1.0)" },
    signal:  AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`CFTC COT HTTP ${res.status}`);

  const rows: COTRow[] = await res.json();
  if (!rows.length) throw new Error("CFTC: no data returned");

  const row      = rows[0];
  const lng      = parseInt(row.noncomm_positions_long_all,  10);
  const sht      = parseInt(row.noncomm_positions_short_all, 10);
  const oi       = parseInt(row.open_interest_all,           10);
  const net      = lng - sht;
  const netK     = (net / 1000).toFixed(1);
  const bias     = net > 0 ? "NET LONG (bullish spec)" : "NET SHORT (bearish spec)";
  const pct      = oi ? ((Math.abs(net) / oi) * 100).toFixed(1) : "?";
  const date     = row.report_date_as_yyyy_mm_dd;

  return `[${date}] Large Spec: Long ${lng.toLocaleString()} | Short ${sht.toLocaleString()} | Net ${net > 0 ? "+" : ""}${netK}K → ${bias} (${pct}% of OI ${oi.toLocaleString()})`;
}

/** Yahoo Finance chart API — returns meta for a given symbol. No key needed. */
async function fetchYFMeta(symbol: string): Promise<YFMeta> {
  const encoded = encodeURIComponent(symbol);
  // Try query2 first (more reliable), fallback to query1
  const endpoints = [
    `https://query2.finance.yahoo.com/v8/finance/chart/${encoded}?interval=1d&range=5d`,
    `https://query1.finance.yahoo.com/v8/finance/chart/${encoded}?interval=1d&range=5d`,
  ];

  const YF_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://finance.yahoo.com/",
    "Origin":          "https://finance.yahoo.com",
  };

  for (const url of endpoints) {
    try {
      const res = await fetch(url, {
        headers: YF_HEADERS,
        signal:  AbortSignal.timeout(12_000),
      });
      if (!res.ok) continue;
      const json = await res.json();
      const meta = json?.chart?.result?.[0]?.meta as YFMeta | undefined;
      if (meta) return meta;
    } catch { continue; }
  }
  throw new Error(`Yahoo Finance ${symbol}: semua endpoint gagal`);
}

/** COMEX Gold futures PDH/PDL/close — reference price (not CFD broker price) */
async function fetchCOMEXGold(): Promise<string> {
  const m = await fetchYFMeta("GC=F");
  // Futures pakai chartPreviousClose, spot/index pakai previousClose
  const prevClose = m.chartPreviousClose ?? m.previousClose;
  return (
    `COMEX GC=F: ${m.regularMarketPrice.toFixed(2)} USD/oz | ` +
    `Day High: ${m.regularMarketDayHigh.toFixed(2)} | ` +
    `Day Low: ${m.regularMarketDayLow.toFixed(2)} | ` +
    `Prev Close: ${prevClose?.toFixed(2) ?? "n/a"}`
  );
}

/** DXY (ICE US Dollar Index) */
async function fetchDXY(): Promise<string> {
  const m = await fetchYFMeta("DX-Y.NYB");
  const prevClose = m.previousClose ?? m.chartPreviousClose ?? m.regularMarketPrice;
  const dir = m.regularMarketPrice > prevClose ? "▲" : "▼";
  const chg = (m.regularMarketPrice - prevClose).toFixed(3);
  return `DXY: ${m.regularMarketPrice.toFixed(3)} ${dir}${chg} | High: ${m.regularMarketDayHigh.toFixed(3)} | Low: ${m.regularMarketDayLow.toFixed(3)}`;
}

/** US 10-Year Treasury Yield (nominal) — Yahoo Finance dengan fallback FRED DGS10 */
async function fetchYield10Y(): Promise<string> {
  // Try Yahoo Finance first
  try {
    const m = await fetchYFMeta("%5ETNX");
    const prevClose = m.previousClose ?? m.chartPreviousClose ?? m.regularMarketPrice;
    const dir = m.regularMarketPrice > prevClose ? "▲" : "▼";
    const chg = (m.regularMarketPrice - prevClose).toFixed(3);
    return `10Y Yield (nominal): ${m.regularMarketPrice.toFixed(3)}% ${dir}${chg} | Prev: ${prevClose.toFixed(3)}%`;
  } catch { /* fall through to FRED */ }

  // Fallback: FRED DGS10 (nominal 10Y constant maturity)
  const key = process.env.FRED_API_KEY;
  if (!key) throw new Error("Yahoo Finance gagal & tidak ada FRED_API_KEY untuk fallback");
  const res = await fetch(
    `https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key=${key}&file_type=json&limit=2&sort_order=desc`,
    { signal: AbortSignal.timeout(10_000) }
  );
  if (!res.ok) throw new Error(`FRED DGS10 HTTP ${res.status}`);
  const json = await res.json();
  const obs: { date: string; value: string }[] = json.observations ?? [];
  const latest = obs.find(o => o.value !== ".");
  if (!latest) throw new Error("FRED DGS10: no valid data");
  const prev = obs.find(o => o.value !== "." && o.date !== latest.date);
  const curr = parseFloat(latest.value);
  const prvV = prev ? parseFloat(prev.value) : null;
  const dir  = prvV !== null ? (curr > prvV ? "▲" : "▼") : "";
  const chg  = prvV !== null ? ` (${curr - prvV >= 0 ? "+" : ""}${(curr - prvV).toFixed(3)})` : "";
  return `10Y Yield (nominal/FRED DGS10): ${curr.toFixed(3)}%${dir}${chg} [${latest.date}]`;
}

/** FRED API — Real 10Y TIPS yield. Needs FRED_API_KEY in .env.local (free) */
async function fetchRealYieldFRED(): Promise<string> {
  const key = process.env.FRED_API_KEY;
  if (!key) return "";  // silently skip if no key configured

  const res = await fetch(
    `https://api.stlouisfed.org/fred/series/observations` +
    `?series_id=DFII10&api_key=${key}&file_type=json&limit=2&sort_order=desc`,
    { signal: AbortSignal.timeout(10_000) }
  );
  if (!res.ok) throw new Error(`FRED HTTP ${res.status}`);

  const json = await res.json();
  const obs: { date: string; value: string }[] = json.observations ?? [];
  const latest  = obs[0];
  const prev    = obs[1];
  if (!latest || latest.value === ".") throw new Error("FRED: no valid observation");

  const curr  = parseFloat(latest.value);
  const prvV  = prev && prev.value !== "." ? parseFloat(prev.value) : null;
  const dir   = prvV !== null ? (curr > prvV ? "▲" : "▼") : "";
  const chg   = prvV !== null ? ` (${(curr - prvV) >= 0 ? "+" : ""}${(curr - prvV).toFixed(3)})` : "";

  return `Real 10Y Yield (TIPS/DFII10): ${curr.toFixed(3)}%${dir}${chg} [${latest.date}]`;
}

/** Investing.com metals RSS — gold-focused news headlines */
async function fetchRssTitles(url: string, maxItems = 6): Promise<string[]> {
  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Accept": "application/rss+xml, application/xml, text/xml, */*",
    },
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`RSS HTTP ${res.status}`);
  const xml = await res.text();
  return [...xml.matchAll(/<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/g)]
    .slice(1, maxItems + 1)
    .map(m => m[1].replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'").trim())
    .filter(t => t.length > 10);
}

async function fetchGoldNews(): Promise<string> {
  const parts: string[] = [];

  // ── 1. Investing.com metals (best: actual gold price analysis) ─────────────
  try {
    const titles = await fetchRssTitles("https://www.investing.com/rss/commodities_Metals.rss", 5);
    if (titles.length > 0) parts.push("🥇 Gold/Metals (Investing.com):\n" + titles.map((t, i) => `${i + 1}. ${t}`).join("\n"));
  } catch { /* fallthrough */ }

  // ── 2. Treasury/Yield news (key gold inverse catalyst) ─────────────────────
  try {
    const titles = await fetchRssTitles("https://finance.yahoo.com/rss/headline?s=%5ETNX", 3);
    if (titles.length > 0) parts.push("📊 Treasury Yield News:\n" + titles.map((t, i) => `${i + 1}. ${t}`).join("\n"));
  } catch { /* fallthrough */ }

  if (parts.length > 0) return parts.join("\n\n");

  // ── 3. Fallback: YF COMEX GC=F ────────────────────────────────────────────
  try {
    const titles = await fetchRssTitles("https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC%3DF&region=US&lang=en-US", 5);
    if (titles.length > 0) return titles.map((t, i) => `${i + 1}. ${t}`).join("\n");
  } catch { /* ignore */ }

  return "Headlines tidak tersedia saat ini.";
}

// ─── Upsert helper ────────────────────────────────────────────────────────────

async function upsert(variableName: string, label: string, value: string) {
  const existing = await db
    .select()
    .from(marketContext)
    .where(eq(marketContext.variableName, variableName))
    .get();

  if (existing) {
    await db
      .update(marketContext)
      .set({ value, updatedAt: new Date() })
      .where(eq(marketContext.variableName, variableName));
  } else {
    const { nanoid } = await import("nanoid");
    await db.insert(marketContext).values({
      id: nanoid(),
      variableName,
      label,
      value,
      updatedAt: new Date(),
    });
  }
}

// ─── POST handler ─────────────────────────────────────────────────────────────

export async function POST() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return Response.json({ error: "Unauthorized" }, { status: 401 });

  type Result = { source: string; status: "ok" | "error"; error?: string };
  const results: Result[] = [];

  async function run(
    source: string,
    fn: () => Promise<string>,
    key: string,
    label: string
  ) {
    try {
      const value = await fn();
      if (value) await upsert(key, label, value);
      results.push({ source, status: "ok" });
    } catch (e) {
      results.push({
        source,
        status: "error",
        error: e instanceof Error ? e.message : String(e),
      });
    }
  }

  // ── ForexFactory calendar first (need structured result for next-event) ────
  let calResult: CalendarResult | null = null;
  try {
    calResult = await fetchEconCalendar();
    await upsert("ECON_CALENDAR", "Economic Calendar High Impact USD", calResult.text);
    results.push({ source: "ForexFactory Calendar", status: "ok" });
  } catch (e) {
    results.push({ source: "ForexFactory Calendar", status: "error", error: e instanceof Error ? e.message : String(e) });
  }

  // ── Store next event data for news blackout countdown ────────────────────
  const evt = calResult?.nextEvent ?? null;
  await upsert("NEXT_EVENT_EPOCH",    "Next High-Impact Event Epoch",   evt ? String(evt.epoch) : "");
  await upsert("NEXT_EVENT_NAME",     "Next High-Impact Event Name",    evt?.name    ?? "");
  await upsert("NEXT_EVENT_TIME_WIB", "Next Event Time WIB",           evt?.timeWIB ?? "");

  // ── Other fetchers in parallel ────────────────────────────────────────────
  await Promise.allSettled([
    run("CFTC COT Gold",          fetchCOTGold,       "COT_GOLD",      "COT Gold COMEX Large Speculator"),
    run("COMEX GC=F Futures",     fetchCOMEXGold,     "COMEX_GOLD",    "COMEX Gold Futures Price"),
    run("Yahoo Finance DXY",      fetchDXY,           "DXY",           "US Dollar Index (DXY)"),
    run("Yahoo Finance 10Y Yield",fetchYield10Y,      "YIELD_10Y",     "US 10Y Treasury Yield (nominal)"),
    run("FRED Real TIPS Yield",   fetchRealYieldFRED, "REAL_YIELD",    "Real 10Y TIPS Yield (FRED)"),
    run("Gold News Headlines",    fetchGoldNews,      "NEWS_GOLD",     "Gold/XAUUSD News Headlines"),
  ]);

  // Timestamp WIB
  const now = new Date().toLocaleString("id-ID", {
    timeZone: "Asia/Jakarta",
    hour12:   false,
  });
  await upsert("NEWS_UPDATED", "News Last Updated", now);

  const hasErrors = results.some(r => r.status === "error");
  const fresh     = await db.select().from(marketContext);

  return Response.json({ success: !hasErrors, results, data: fresh });
}
