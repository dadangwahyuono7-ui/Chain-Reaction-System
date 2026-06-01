import { streamText, tool, stepCountIs, type LanguageModel } from "ai";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { createAnthropic } from "@ai-sdk/anthropic";
import { auth } from "@/lib/auth";
import { db } from "@/db";

// Model lokal (Gemma-12B / Qwen-32B via llama.cpp) butuh 3-4 menit
// untuk ingest system prompt 13K token pertama kali.
// 300 detik = batas maksimum Next.js edge/node route duration.
export const maxDuration = 300;
import { messages, chatSessions, marketContext, memories, paperAccounts, paperTrades } from "@/db/schema";
import { eq, desc } from "drizzle-orm";
import { buildSystemPrompt, buildSystemPromptLite, type Memory } from "@/lib/system-prompt";
import { computeFundData } from "@/lib/fund-data";
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
  // 1. Jina Reader — render JS pages, return clean markdown (free, no key)
  try {
    const jinaRes = await fetch(`https://r.jina.ai/${url}`, {
      headers: {
        "Accept": "text/plain",
        "X-Return-Format": "markdown",
        "User-Agent": "SultanAdvisor/1.0",
      },
      signal: AbortSignal.timeout(20000),
    });
    if (jinaRes.ok) {
      const text = (await jinaRes.text()).trim();
      if (text.length > 200) {
        return `📄 **${url}**\n\n${text.slice(0, 6000)}${text.length > 6000 ? "\n\n...[truncated]" : ""}`;
      }
    }
  } catch { /* fallthrough ke plain fetch */ }

  // 2. Plain fetch + HTML strip (fallback untuk SSR pages)
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      },
      signal: AbortSignal.timeout(12000),
    });
    if (!res.ok) return `Fetch gagal: HTTP ${res.status}`;
    const html = await res.text();
    const cleaned = html
      .replace(/<script[\s\S]*?<\/script>/gi, "")
      .replace(/<style[\s\S]*?<\/style>/gi, "")
      .replace(/<nav[\s\S]*?<\/nav>/gi, "")
      .replace(/<footer[\s\S]*?<\/footer>/gi, "")
      .replace(/<[^>]+>/g, " ")
      .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&")
      .replace(/\s{3,}/g, "\n").trim();
    const text = cleaned.slice(0, 5000);
    return text || "Konten kosong — halaman mungkin butuh JavaScript.";
  } catch (e) {
    return `Fetch URL gagal: ${e instanceof Error ? e.message : String(e)}`;
  }
}

// ─── Playwright Browser (persistent singleton) ───────────────────────────────

let _pwBrowser: import("playwright").Browser | null = null;
let _pwPage:    import("playwright").Page    | null = null;

async function getPwPage(): Promise<import("playwright").Page> {
  if (!_pwBrowser || !_pwBrowser.isConnected()) {
    const { chromium } = await import("playwright");
    _pwBrowser = await chromium.launch({ headless: true });
  }
  if (!_pwPage || _pwPage.isClosed()) {
    _pwPage = await _pwBrowser.newPage();
    await _pwPage.setViewportSize({ width: 1280, height: 800 });
    await _pwPage.setExtraHTTPHeaders({ "Accept-Language": "en-US,en;q=0.9" });
  }
  return _pwPage;
}

async function playwrightAction(action: string, params: Record<string, unknown>): Promise<string> {
  const path = require("path");
  const fs   = require("fs");
  try {
    switch (action) {
      case "navigate": {
        const page = await getPwPage();
        await page.goto(params.url as string, { waitUntil: "domcontentloaded", timeout: 30000 });
        await page.waitForTimeout(1800);
        return `✅ Navigated → ${page.url()}\nTitle: ${await page.title()}`;
      }
      case "screenshot": {
        const page   = await getPwPage();
        const fname  = `pw-${Date.now()}.png`;
        const outDir = path.join(process.cwd(), "public", "uploads");
        fs.mkdirSync(outDir, { recursive: true });
        await page.screenshot({ path: path.join(outDir, fname), fullPage: false });
        return `📸 Screenshot siap:\n![page](/uploads/${fname})\nURL: ${page.url()}\nTitle: ${await page.title()}`;
      }
      case "get_text": {
        const page = await getPwPage();
        const text = await page.evaluate(() => {
          ["script","style","nav","footer","header","aside"].forEach(t =>
            document.querySelectorAll(t).forEach(e => e.remove())
          );
          return (document.body?.innerText ?? "").trim();
        });
        return `📄 **${page.url()}**\n\n${text.slice(0, 7000)}${text.length > 7000 ? "\n...[truncated]" : ""}`;
      }
      case "click": {
        const page = await getPwPage();
        await page.click(params.selector as string, { timeout: 10000 });
        await page.waitForTimeout(600);
        return `✅ Clicked: ${params.selector}`;
      }
      case "type": {
        const page = await getPwPage();
        await page.fill(params.selector as string, params.text as string);
        return `✅ Typed into ${params.selector}: "${params.text}"`;
      }
      case "scroll": {
        const page   = await getPwPage();
        const amount = ((params.amount as number) ?? 3) * 350;
        await page.evaluate((px: number) => window.scrollBy(0, px),
          params.direction === "up" ? -amount : amount);
        return `✅ Scrolled ${params.direction} ${params.amount ?? 3}x`;
      }
      case "close": {
        if (_pwPage && !_pwPage.isClosed()) await _pwPage.close();
        _pwPage = null;
        return "✅ Browser tab closed";
      }
      default:
        return `❌ Unknown action: ${action}`;
    }
  } catch (e) {
    return `Browser error [${action}]: ${e instanceof Error ? e.message : String(e)}`;
  }
}

// ─── Full Agent Capabilities ─────────────────────────────────────────────────

const fs = require("fs") as typeof import("fs");

async function agentShellExec(command: string, cwd?: string, timeoutMs = 30000): Promise<string> {
  const { spawn } = require("child_process");
  const workDir = cwd || PROJECT_ROOT;
  return new Promise((resolve) => {
    const child = spawn("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", command], {
      cwd: workDir,
      timeout: timeoutMs,
      env: { ...process.env },
    });
    let stdout = "";
    let stderr = "";
    child.stdout?.on("data", (d: Buffer) => { stdout += d.toString(); });
    child.stderr?.on("data", (d: Buffer) => { stderr += d.toString(); });
    child.on("close", (code: number | null) => {
      const out = [
        stdout.trim() && `[stdout]\n${stdout.trim()}`,
        stderr.trim() && `[stderr]\n${stderr.trim()}`,
        `[exit code: ${code ?? "?"}]`,
      ].filter(Boolean).join("\n\n");
      resolve(out || `(no output, exit ${code})`);
    });
    child.on("error", (err: Error) => resolve(`[spawn error] ${err.message}`));
  });
}

async function agentReadFile(filePath: string): Promise<string> {
  try {
    const content = fs.readFileSync(filePath, "utf-8");
    const lines = content.split("\n");
    const preview = lines.length > 300 ? lines.slice(0, 300).join("\n") + `\n...[truncated, ${lines.length} total lines]` : content;
    return `📄 ${filePath} (${lines.length} lines):\n\n${preview}`;
  } catch (e) {
    return `Error reading file: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function agentWriteFile(filePath: string, content: string): Promise<string> {
  try {
    const dir = require("path").dirname(filePath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(filePath, content, "utf-8");
    const lines = content.split("\n").length;
    return `✅ Written: ${filePath} (${lines} lines)`;
  } catch (e) {
    return `Error writing file: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function agentListDir(dirPath: string): Promise<string> {
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    const lines = entries.map((e: { isDirectory: () => boolean; name: string }) => {
      const icon = e.isDirectory() ? "📁" : "📄";
      return `${icon} ${e.name}`;
    });
    return `📂 ${dirPath} (${lines.length} items):\n${lines.join("\n")}`;
  } catch (e) {
    return `Error listing dir: ${e instanceof Error ? e.message : String(e)}`;
  }
}

const ASISTEN_SCREENSHOTS = "D:\\PROJECT TRADING\\asisten dadang\\screenshots";
const PUBLIC_UPLOADS = require("path").join(process.cwd(), "public", "uploads");

async function agentScreenshotAndAnalyze(focus?: string): Promise<string> {
  try {
    const ts      = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const fname   = `screenshot-${ts}.png`;
    const savePath = require("path").join(ASISTEN_SCREENSHOTS, fname);
    const pubPath  = require("path").join(PUBLIC_UPLOADS, fname);

    // 1. Take screenshot via PowerShell — simpan langsung ke asisten dadang
    const psCmd = `
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
New-Item -ItemType Directory -Force -Path '${ASISTEN_SCREENSHOTS.replace(/\\/g, "\\\\")}' | Out-Null
$bitmap.Save('${savePath.replace(/\\/g, "\\\\")}')
$graphics.Dispose(); $bitmap.Dispose()
Write-Output 'OK'
`.trim();

    const { spawn } = require("child_process");
    const psResult: string = await new Promise((resolve) => {
      const child = spawn("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", psCmd], { timeout: 10000 });
      let out = "";
      child.stdout?.on("data", (d: Buffer) => { out += d.toString(); });
      child.on("close", () => resolve(out.trim()));
      child.on("error", (e: Error) => resolve(`error: ${e.message}`));
    });

    if (!fs.existsSync(savePath)) {
      return `Screenshot gagal: ${psResult}. Pastikan desktop bisa diakses.`;
    }

    // 2. Copy ke public/uploads biar bisa ditampilkan di browser
    const imgBuffer = fs.readFileSync(savePath);
    const base64    = imgBuffer.toString("base64");
    require("fs").mkdirSync(PUBLIC_UPLOADS, { recursive: true });
    fs.writeFileSync(pubPath, imgBuffer);

    // 3. Analisis via Claude Vision
    const { createAnthropic: createAnthropicVision } = await import("@ai-sdk/anthropic");
    const { generateText } = await import("ai");
    const visionClient = createAnthropicVision({
      apiKey:  process.env.BLUEPACK_API_KEY ?? "",
      baseURL: process.env.BLUEPACK_BASE_URL ?? "https://ai.bluepack.my.id/v1",
    });

    const { text } = await generateText({
      model: visionClient("claude-3-5-haiku-20241022") as import("ai").LanguageModel,
      messages: [{
        role: "user",
        content: [
          { type: "image", image: base64, mediaType: "image/png" as const },
          { type: "text", text: focus
            ? `Analisis screenshot ini. Fokus pada: ${focus}. Deskripsikan apa yang kamu lihat secara detail.`
            : `Deskripsikan apa yang ada di screenshot ini. Fokus pada: konten trading, chart, kode, error, atau apapun yang relevan.`
          },
        ],
      }],
      maxOutputTokens: 1024,
    });

    // Return analisis + URL gambar (ditampilkan di chat bubble)
    const imgUrl = `/uploads/${fname}`;
    return `📸 **Screenshot diambil** — tersimpan di \`asisten dadang\\screenshots\\${fname}\`\n\n![Screenshot](${imgUrl})\n\n---\n${text}`;
  } catch (e) {
    return `Screenshot/vision error: ${e instanceof Error ? e.message : String(e)}`;
  }
}

// ─── Engine Execution (scoped, safe commands) ───────────────────────────────

const PROJECT_ROOT = "D:\\PROJECT TRADING";
const PYTHON_EXE  = `${PROJECT_ROOT}\\venv\\Scripts\\python.exe`;
const SETTINGS_PATH = `${PROJECT_ROOT}\\chain_settings.json`;

function spawnCommand(cmd: string, args: string[], timeoutMs = 15000): Promise<{ stdout: string; stderr: string; code: number | null }> {
  const { spawn } = require("child_process");
  return new Promise((resolve) => {
    const child = spawn(cmd, args, {
      timeout: timeoutMs,
      cwd: PROJECT_ROOT,
      env: { ...process.env },
    });
    let stdout = "";
    let stderr = "";
    child.stdout?.on("data", (d: Buffer) => { stdout += d.toString(); });
    child.stderr?.on("data", (d: Buffer) => { stderr += d.toString(); });
    child.on("close", (code: number | null) => resolve({ stdout, stderr, code }));
    child.on("error", (err: Error) => resolve({ stdout, stderr: err.message, code: -1 }));
  });
}

async function runEngineCheck(): Promise<string> {
  const script = `
import sys
sys.path.insert(0, r'${PROJECT_ROOT}')
try:
    from engine.connection import connect_mt5
    from engine.core import SacredDoctrineAnalyst, DailyDeployAnalyst
    import MetaTrader5 as mt5
    if not connect_mt5():
        print("MT5 CONNECTION FAILED — pastikan MetaTrader 5 running dan login.")
        sys.exit(0)
    a = SacredDoctrineAnalyst('XAUUSD', master_tf='H4')
    d = DailyDeployAnalyst('XAUUSD')
    a.update(); d.update(a)
    print("=== ENGINE STATE ===")
    for n in ['D1','H4','H1','M30','M15','M5']:
        st = a.states[n]
        vr = 'YA' if st.vr_occurred else 'BELUM'
        cf = 'YA' if st.cf_occurred else 'BELUM'
        print(f'{n}: CMP={st.cmp} SUP={st.sup:.2f} RES={st.res:.2f} VR={vr} CF={cf}')
    print("\\n=== DAILY DEPLOY SIGNALS ===")
    sigs = d.active_signals
    if sigs:
        for s in sigs:
            print(f"  [{s.get('layer','?')}] {s.get('type','?')} {s.get('action','?')} — conf={s.get('confidence','?')}")
    else:
        print("  Tidak ada signal aktif.")
    price = mt5.symbol_info_tick('XAUUSD')
    if price:
        print(f"\\nHarga: bid={price.bid} ask={price.ask} spread={price.ask-price.bid:.2f}")
    mt5.shutdown()
except Exception as e:
    print(f"ERROR: {e}")
`;
  const { stdout, stderr, code } = await spawnCommand(PYTHON_EXE, ["-c", script], 20000);
  if (code !== 0 && !stdout) return `Engine check gagal: ${stderr.slice(0, 300)}`;
  return stdout || stderr || "Tidak ada output dari engine.";
}

async function readSettings(): Promise<string> {
  try {
    const fs = require("fs");
    const raw = fs.readFileSync(SETTINGS_PATH, "utf-8");
    const settings = JSON.parse(raw);
    const lines = Object.entries(settings).map(([k, v]) => {
      if (typeof v === "object") return `${k}: ${JSON.stringify(v)}`;
      return `${k}: ${v}`;
    });
    return `📋 chain_settings.json:\n\n${lines.join("\n")}`;
  } catch (e) {
    return `Gagal baca settings: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function updateSettings(key: string, value: unknown): Promise<string> {
  try {
    const fs = require("fs");
    const raw = fs.readFileSync(SETTINGS_PATH, "utf-8");
    const settings = JSON.parse(raw);

    // Whitelist — hanya key yang aman boleh diubah
    const ALLOWED = [
      "auto_trade", "lot_size", "max_layers", "barrier_limit",
      "be_protect_pips", "trail_stop_pips", "max_spread_points",
      "news_blackout_minutes", "session_filter", "enable_daily_deploy",
      "ninja_enabled", "ninja_be_pips", "ninja_sl_buffer",
      "risk_per_trade_percent", "drawdown_block_percent",
    ];
    if (!ALLOWED.includes(key)) {
      return `⛔ Key "${key}" tidak boleh diubah via AI. Allowed: ${ALLOWED.join(", ")}`;
    }

    const oldVal = settings[key];
    settings[key] = value;
    fs.writeFileSync(SETTINGS_PATH, JSON.stringify(settings, null, 4), "utf-8");
    return `✅ chain_settings.json updated:\n  ${key}: ${JSON.stringify(oldVal)} → ${JSON.stringify(value)}\n\n⚠️ Perubahan berlaku saat engine restart atau reload next cycle.`;
  } catch (e) {
    return `Gagal update settings: ${e instanceof Error ? e.message : String(e)}`;
  }
}

async function runBacktest(): Promise<string> {
  const { stdout, stderr, code } = await spawnCommand(
    PYTHON_EXE,
    [`${PROJECT_ROOT}\\backtest\\run.py`],
    60000  // backtest bisa lama
  );
  if (code !== 0 && !stdout) return `Backtest gagal: ${stderr.slice(0, 500)}`;
  // Ambil summary akhir saja (biasanya di 30 baris terakhir)
  const lines = (stdout || stderr).split("\n");
  const summary = lines.slice(-30).join("\n");
  return `📊 BACKTEST RESULT (last 30 lines):\n\n${summary}`;
}

// ─── TradingView Sync (AI can trigger sync itself) ──────────────────────────

async function triggerTVSync(): Promise<string> {
  try {
    const scriptPath = require("path").join(process.cwd(), "scripts", "tv-snapshot.mjs");
    const { spawn } = require("child_process");

    const result: { success: boolean; ctx?: Record<string, string>; error?: string } = await new Promise((resolve) => {
      const child = spawn(process.execPath, [scriptPath], {
        timeout: 12000,
        env: { ...process.env },
      });
      let stdout = "";
      let stderr = "";
      child.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
      child.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });
      child.on("close", () => {
        try { resolve(JSON.parse(stdout.trim())); }
        catch { resolve({ success: false, error: stderr.slice(0, 200) || "Parse error" }); }
      });
      child.on("error", (err: Error) => resolve({ success: false, error: err.message }));
    });

    if (!result.success || !result.ctx) {
      return `Sync gagal: ${result.error ?? "Unknown error"}. Minta Commander cek TradingView.`;
    }

    // Upsert ke DB
    const { eq: eqOp } = await import("drizzle-orm");
    const existing = await db.select().from(marketContext);
    const byName = new Map(existing.map(r => [r.variableName, r]));

    for (const [key, value] of Object.entries(result.ctx)) {
      if (value === undefined || value === null) continue;
      const row = byName.get(key);
      if (row) {
        await db.update(marketContext).set({ value: String(value) }).where(eqOp(marketContext.variableName, key));
      } else {
        const label = key.endsWith('_CF_COUNT') ? `${key.replace('_CF_COUNT', '')} CF Count`
          : key.endsWith('_CF_TYPE') ? `${key.replace('_CF_TYPE', '')} CF Type` : key;
        await db.insert(marketContext).values({
          id: nanoid(), variableName: key, label, value: String(value),
        });
      }
    }

    // Format summary
    const TFS = ["DAILY", "H4", "H1", "M30", "M15", "M5"];
    const lines = TFS.map(tf => {
      const cmp = result.ctx![`${tf}_CMP`] || "—";
      const vr = result.ctx![`${tf}_VR`] || "—";
      const cf = result.ctx![`${tf}_CF`] || "—";
      return `${tf}: CMP=${cmp} VR=${vr} CF=${cf}`;
    }).filter(l => !l.includes("CMP=—"));

    return `✅ TradingView sync berhasil!\n\nState terbaru:\n${lines.join("\n")}\n\nHarga: ${result.ctx!["HARGA"] ?? "N/A"}\nSession: ${result.ctx!["SESSION"] ?? "N/A"}\n\nData sudah diupdate — analisis sekarang pakai state terbaru.`;
  } catch (e) {
    return `Sync error: ${e instanceof Error ? e.message : String(e)}`;
  }
}

// ─── Risk Calculator ─────────────────────────────────────────────────────────

function calculateRisk(
  direction: "BUY" | "SELL",
  entry: number,
  sl: number,
  tp1: number,
  tp2: number | undefined,
  lotSize: number
): string {
  const pipValue = 0.1; // XAUUSD: 1 pip = $0.1 per 0.01 lot (per point)
  const slPips = Math.abs(entry - sl);
  const tp1Pips = Math.abs(tp1 - entry);
  const tp2Pips = tp2 ? Math.abs(tp2 - entry) : 0;

  const riskUSD = slPips * (lotSize / 0.01) * pipValue;
  const tp1USD = tp1Pips * (lotSize / 0.01) * pipValue;
  const tp2USD = tp2Pips ? tp2Pips * (lotSize / 0.01) * pipValue : 0;

  const rr1 = slPips > 0 ? (tp1Pips / slPips).toFixed(2) : "N/A";
  const rr2 = (slPips > 0 && tp2Pips > 0) ? (tp2Pips / slPips).toFixed(2) : "N/A";

  // Validasi arah
  const dirOk = direction === "BUY"
    ? (sl < entry && tp1 > entry && (!tp2 || tp2 > entry))
    : (sl > entry && tp1 < entry && (!tp2 || tp2 < entry));

  const lines = [
    `📐 RISK CALCULATOR — ${direction} XAUUSD`,
    ``,
    `Entry : ${entry.toFixed(2)}`,
    `SL    : ${sl.toFixed(2)} (${slPips.toFixed(1)} pts)`,
    `TP1   : ${tp1.toFixed(2)} (${tp1Pips.toFixed(1)} pts) → R:R ${rr1}`,
    tp2 ? `TP2   : ${tp2.toFixed(2)} (${tp2Pips.toFixed(1)} pts) → R:R ${rr2}` : null,
    ``,
    `Lot   : ${lotSize}`,
    `Risk  : $${riskUSD.toFixed(2)}`,
    `TP1 $  : $${tp1USD.toFixed(2)}`,
    tp2USD ? `TP2 $  : $${tp2USD.toFixed(2)}` : null,
    ``,
    dirOk ? `✅ Arah SL/TP valid untuk ${direction}` : `⚠️ PERINGATAN: Arah SL/TP tidak valid untuk ${direction}! Cek ulang.`,
  ].filter(Boolean);

  return lines.join("\n");
}

// ─── Memory functions ────────────────────────────────────────────────────────

async function saveMemory(content: string, category: string, importance: number, tags?: string, sessionId?: string): Promise<string> {
  const id = nanoid();
  await db.insert(memories).values({
    id,
    content,
    category,
    importance,
    tags: tags || null,
    sessionId: sessionId || null,
  });
  return `Memori tersimpan [${category}] importance:${importance}${tags ? ` tags:${tags}` : ""}: "${content.slice(0, 80)}..."`;
}

async function recallMemories(limit = 30): Promise<Memory[]> {
  const rows = await db.select().from(memories).orderBy(desc(memories.importance), desc(memories.createdAt)).limit(limit);
  return rows.map(r => ({
    id: r.id,
    content: r.content,
    category: r.category,
    importance: r.importance,
    tags: r.tags,
    createdAt: r.createdAt,
  }));
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
  get_fund_data: tool({
    description: [
      "Ambil 'Jejak Fund' / data institutional dari Yahoo Finance: Volume Profile (POC/HVN/LVN), Liquidity zones (stop pool equal high/low), basis COMEX-Spot, DXY & US10Y + macro bias gold.",
      "Gunakan untuk: tau area akumulasi/distribusi fund (HVN/POC = magnet harga), di mana stop numpuk (liquidity pool yang sering di-grab sebelum gerak), dan filter makro (DXY/yield naik = tekanan jual gold).",
      "WAJIB cek ini sebelum analisis swing besar atau pas Commander tanya 'di mana fund main / area institusi / kenapa harga ke situ'. Ini proxy delay (bukan order book real-time) tapi valid buat baca akumulasi.",
    ].join(" "),
    inputSchema: z.object({}),
    execute: async () => {
      try {
        const d = await computeFundData();
        return `🏦 JEJAK FUND (Yahoo, delay):\n${d.summary}\n\nInterpretasi: POC/HVN = zona akumulasi (harga ketarik balik ke sini). LVN = area rejection (harga cepat lewat). Liquidity pool = stop numpuk, sering di-grab fund sebelum gerak arah sebenarnya. Macro bias = filter; jangan lawan arah makro buat swing.`;
      } catch (e) {
        return `Gagal ambil fund data: ${e instanceof Error ? e.message : String(e)}`;
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

  // Build system prompt from market context + persistent memories
  const ctxRows = await db.select().from(marketContext);
  const ctx = Object.fromEntries(
    ctxRows.map((r) => [r.variableName, { label: r.label, value: r.value }])
  );
  const recentMemories = await recallMemories(30);
  // Prompt dibangun setelah model selection (lihat bawah)
  // placeholder dulu, diganti setelah isLocal diketahui
  const _ctxForPrompt = ctx;
  const _memForPrompt = recentMemories;

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

  // Auto-inject URL content — fetch sebelum AI baca, jadi AI gak perlu call tool
  // Handles JS-rendered pages via Jina Reader (r.jina.ai)
  if (userText) {
    const urlMatches = userText.match(/https?:\/\/[^\s>\"\'<\]]+/g) ?? [];
    if (urlMatches.length > 0) {
      const fetched = await Promise.all(
        urlMatches.slice(0, 2).map((url: string) =>
          fetchUrl(url).then(c => `\n\n---\n🌐 KONTEN DARI ${url}\n${c}`).catch(() => null)
        )
      );
      const injected = fetched.filter(Boolean).join("");
      if (injected) {
        const last = coreMessages.at(-1);
        if (last?.role === "user") {
          coreMessages[coreMessages.length - 1] = {
            ...last,
            content: last.content + injected,
          };
        }
      }
    }
  }

  // Smart selection: local → Gemma4/Qwen via llama.cpp | cloud → Claude via Bluepack
  // Auto-fallback: local mati → cloud
  let modelType: "local" | "cloud" = modelChoice === "cloud" ? "cloud" : "local";

  if (modelType === "local") {
    // Auto-fallback: llama.cpp gak nyala / gak respon → otomatis ke cloud (Claude premium)
    const localBase = process.env.LLM_BASE_URL ?? "http://localhost:8080/v1";
    const localOk = await fetch(`${localBase}/models`, {
      signal: AbortSignal.timeout(1800),
    }).then(r => r.ok).catch(() => false);
    if (!localOk) modelType = "cloud";
  }

  const isLocal = modelType === "local";
  const selectedModel = modelType === "local" ? buildLocalModel() : buildCloudModel();

  // Gemma 4 E4B: 128K context → full prompt, bukan lite
  // Cloud (Claude): full prompt juga
  const systemPrompt = buildSystemPrompt(_ctxForPrompt, _memForPrompt);

  // Build tools with session context
  const toolsWithContext = {
    ...searchTools,

    // ── Memory: Save ──────────────────────────────────────────────────────────
    save_memory: tool({
      description: [
        "Simpan informasi penting ke memori jangka panjang yang PERSISTEN lintas sesi chat.",
        "WAJIB digunakan saat: (1) trade selesai win/loss — simpan detail entry/SL/TP/result,",
        "(2) insight penting tentang market ditemukan, (3) pola berulang terdeteksi,",
        "(4) Commander kasih feedback/pelajaran, (5) Commander minta kamu ingat sesuatu.",
        "JANGAN simpan hal trivial — hanya insight yang berguna untuk analisis masa depan.",
      ].join(" "),
      inputSchema: z.object({
        content: z.string().describe("Isi memori — deskriptif dan spesifik"),
        category: z.enum(["trade_result", "market_insight", "pattern", "lesson", "preference", "general"])
          .describe("Kategori memori"),
        importance: z.number().min(1).max(4).optional()
          .describe("1=rendah, 2=sedang, 3=tinggi, 4=kritis. Default 2."),
        tags: z.string().optional()
          .describe("Tags dipisah koma. Contoh: 'H1,SELL,CF2,win'"),
      }),
      execute: async ({ content, category, importance = 2, tags }: { content: string; category: string; importance?: number; tags?: string }) => {
        return saveMemory(content, category, importance, tags, sessionId);
      },
    }),

    // ── Memory: Search ────────────────────────────────────────────────────────
    search_memories: tool({
      description: [
        "Cari memori lama berdasarkan keyword atau kategori.",
        "Gunakan untuk: recall insight lama, cek trade history, cari pola yang pernah terjadi.",
        "Contoh: search 'H1 SELL' untuk cari semua trade SELL H1 sebelumnya.",
      ].join(" "),
      inputSchema: z.object({
        keyword: z.string().optional().describe("Kata kunci untuk dicari di content/tags"),
        category: z.enum(["trade_result", "market_insight", "pattern", "lesson", "preference", "general"]).optional()
          .describe("Filter berdasarkan kategori"),
        limit: z.number().min(1).max(20).optional().describe("Jumlah hasil (default 10)"),
      }),
      execute: async ({ keyword, category, limit = 10 }: { keyword?: string; category?: string; limit?: number }) => {
        let rows = await db.select().from(memories).orderBy(desc(memories.createdAt)).limit(50);
        if (category) rows = rows.filter(r => r.category === category);
        if (keyword) {
          const kw = keyword.toLowerCase();
          rows = rows.filter(r =>
            r.content.toLowerCase().includes(kw) ||
            (r.tags && r.tags.toLowerCase().includes(kw))
          );
        }
        rows = rows.slice(0, limit);
        if (rows.length === 0) return `Tidak ada memori yang cocok dengan "${keyword ?? category ?? "all"}".`;
        return `📚 ${rows.length} memori ditemukan:\n\n${rows.map((r, i) => {
          const date = r.createdAt instanceof Date ? r.createdAt.toLocaleDateString("id-ID") : "?";
          return `${i + 1}. [${r.category}] ${date} — ${r.content}${r.tags ? ` #${r.tags}` : ""}`;
        }).join("\n")}`;
      },
    }),

    // ── TradingView Sync ──────────────────────────────────────────────────────
    trigger_sync: tool({
      description: [
        "Trigger sync TradingView untuk mendapatkan data CMP/VR/CF terbaru langsung dari chart.",
        "Gunakan SEBELUM analisis kalau data terasa stale, atau Commander minta update.",
        "Setelah sync, state market di system prompt akan terupdate otomatis untuk pesan berikutnya.",
      ].join(" "),
      inputSchema: z.object({}),
      execute: async () => triggerTVSync(),
    }),

    // ── Risk Calculator ───────────────────────────────────────────────────────
    calculate_risk: tool({
      description: [
        "Hitung risk/reward ratio, risk dalam USD, dan validasi arah SL/TP.",
        "WAJIB digunakan sebelum present trade plan ke Commander — pastikan R:R masuk akal.",
        "Input: arah trade, entry, SL, TP1, TP2 (opsional), lot size.",
      ].join(" "),
      inputSchema: z.object({
        direction: z.enum(["BUY", "SELL"]).describe("Arah trade"),
        entry: z.number().describe("Harga entry"),
        sl: z.number().describe("Harga stop loss"),
        tp1: z.number().describe("Harga take profit 1"),
        tp2: z.number().optional().describe("Harga take profit 2 (opsional)"),
        lot_size: z.number().optional().describe("Ukuran lot (default 0.01)"),
      }),
      execute: async ({ direction, entry, sl, tp1, tp2, lot_size = 0.01 }: {
        direction: "BUY" | "SELL"; entry: number; sl: number; tp1: number; tp2?: number; lot_size?: number;
      }) => calculateRisk(direction, entry, sl, tp1, tp2, lot_size),
    }),

    // ── Paper Trading Performance (buat AI belajar) ───────────────────────────
    get_paper_performance: tool({
      description: [
        "Baca rekam jejak paper trading (autopilot). Ada 2 akun: 'engine' (entry otomatis murni doktrin CF) dan 'ai' (diputus AI).",
        "Gunakan untuk: belajar dari hasil trade nyata, lihat win rate / total R / saldo, evaluasi setup mana yang sering profit/loss,",
        "bandingkan performa engine vs AI. Panggil sebelum kasih insight performa atau saat Commander tanya soal hasil autopilot.",
      ].join(" "),
      inputSchema: z.object({
        account: z.enum(["engine", "ai"]).optional().describe("Filter akun. Kosongkan untuk lihat dua-duanya."),
      }),
      execute: async ({ account }: { account?: string }) => {
        try {
          const accs = await db.select().from(paperAccounts);
          const allTrades = await db.select().from(paperTrades).orderBy(desc(paperTrades.openedAt)).limit(100);
          const lines: string[] = [];
          for (const a of accs) {
            if (account && a.id !== account) continue;
            const t = allTrades.filter(x => x.accountId === a.id);
            const closed = t.filter(x => x.status !== "OPEN");
            const wins = closed.filter(x => x.status === "WIN").length;
            const losses = closed.filter(x => x.status === "LOSS").length;
            const totalR = closed.reduce((s, x) => s + (x.rMultiple ?? 0), 0);
            const wr = closed.length ? (wins / closed.length * 100).toFixed(1) : "0";
            const pnl = a.balance - a.initialBalance;
            lines.push(`【${a.label}】 saldo Rp${Math.round(a.balance).toLocaleString("id-ID")} (P&L ${pnl >= 0 ? "+" : ""}Rp${Math.round(pnl).toLocaleString("id-ID")}) | closed:${closed.length} W:${wins} L:${losses} | winrate:${wr}% | total ${totalR >= 0 ? "+" : ""}${totalR.toFixed(2)}R | open:${t.filter(x => x.status === "OPEN").length}`);
            const recent = t.slice(0, 8).map(x => `  - ${x.direction} ${x.instrument}${x.setupTf ? `·${x.setupTf}` : ""} @${x.entryPrice.toFixed(2)} → ${x.status}${x.rMultiple != null ? ` ${x.rMultiple >= 0 ? "+" : ""}${x.rMultiple.toFixed(2)}R` : ""}${x.closeReason ? ` (${x.closeReason})` : ""}`);
            if (recent.length) lines.push(...recent);
          }
          return lines.length ? lines.join("\n") : "Belum ada data paper trading. Autopilot mungkin belum dinyalakan.";
        } catch (e) {
          return `Gagal baca paper performance: ${e instanceof Error ? e.message : String(e)}`;
        }
      },
    }),

    // ── Paper Trade: buka manual dari AI ────────────────────────────────────
    open_paper_trade: tool({
      description: [
        "Buka paper trade di akun AI (buat lo sendiri yang mutusin, bukan engine otomatis).",
        "WAJIB pakai ini kalau Commander minta 'buka trade', 'entry paper', 'masuk posisi AI', dll.",
        "Sebelum panggil: WAJIB sudah jalankan get_ohlc untuk SL presisi + calculate_risk untuk validasi R:R.",
        "Tool ini HANYA buka di akun 'ai' — jangan dipakai untuk akun 'engine'.",
      ].join(" "),
      inputSchema: z.object({
        instrument:  z.string().describe("Simbol instrumen, misal XAUUSD atau BTCUSD"),
        direction:   z.enum(["BUY","SELL"]).describe("Arah trade"),
        entryPrice:  z.number().describe("Harga entry"),
        slPrice:     z.number().describe("Harga stop loss (dari OHLC VR, bukan angka bulat)"),
        tp1Price:    z.number().describe("Harga TP1"),
        tp2Price:    z.number().optional().describe("Harga TP2 (opsional)"),
        setupTf:     z.string().optional().describe("TF setup, misal H4 atau M30"),
        grade:       z.enum(["A+","A","B","C"]).optional().describe("Grade setup"),
        openReason:  z.string().describe("Alasan entry singkat (wajib)"),
      }),
      execute: async ({ instrument, direction, entryPrice, slPrice, tp1Price, tp2Price, setupTf, grade, openReason }) => {
        try {
          const id = nanoid();
          await db.insert(paperTrades).values({
            id, accountId: "ai", instrument, direction,
            setupTf: setupTf ?? null, grade: grade ?? null,
            entryPrice, slPrice, tp1Price, tp2Price: tp2Price ?? null,
            status: "OPEN",
            openReason: `[AI-Manual] ${openReason}`,
          });
          const risk = Math.abs(entryPrice - slPrice);
          const rr = tp1Price ? (Math.abs(tp1Price - entryPrice) / risk).toFixed(2) : "?";
          return `✅ Paper trade dibuka di akun AI:\n${direction} ${instrument} @ ${entryPrice}\nSL: ${slPrice} | TP1: ${tp1Price}${tp2Price ? ` | TP2: ${tp2Price}` : ""}\nR:R TP1 = ${rr} | Grade: ${grade ?? "—"}\nAlasan: ${openReason}`;
        } catch (e) {
          return `Gagal buka trade: ${e instanceof Error ? e.message : String(e)}`;
        }
      },
    }),

    // ── Read Market Context ───────────────────────────────────────────────────
    get_market_context: tool({
      description: [
        "Baca ulang market context terbaru dari database (harga, SNR, state CMP/VR/CF).",
        "Gunakan kalau perlu double-check data yang sudah ada di system prompt,",
        "atau setelah trigger_sync untuk memastikan data sudah update.",
      ].join(" "),
      inputSchema: z.object({}),
      execute: async () => {
        const rows = await db.select().from(marketContext);
        const relevant = rows.filter(r => r.value && r.value.trim());
        if (relevant.length === 0) return "Belum ada market context. Minta Commander sync TradingView dulu.";
        return relevant.map(r => `${r.label}: ${r.value}`).join("\n");
      },
    }),

    // ── Engine Execution Tools ────────────────────────────────────────────────

    run_engine_check: tool({
      description: [
        "DISABLED — Commander sedang tidak pakai MT5. Gunakan trigger_sync untuk data dari TradingView.",
        "Tool ini akan memberitahu user bahwa MT5 tidak aktif saat ini.",
      ].join(" "),
      inputSchema: z.object({}),
      execute: async () => "⚠️ MT5 sedang tidak dipakai Commander. Gunakan trigger_sync untuk sync data dari TradingView, atau get_market_context untuk baca data yang sudah ada.",
    }),

    read_settings: tool({
      description: [
        "Baca chain_settings.json — konfigurasi runtime engine.",
        "Isinya: auto_trade, lot_size, max_layers, barrier_limit, spread max, news blackout, dll.",
        "Gunakan kalau Commander tanya soal setting saat ini atau mau review sebelum ubah.",
      ].join(" "),
      inputSchema: z.object({}),
      execute: async () => readSettings(),
    }),

    update_settings: tool({
      description: [
        "Ubah setting di chain_settings.json. HANYA key yang di-whitelist yang boleh diubah.",
        "Allowed: auto_trade, lot_size, max_layers, barrier_limit, be_protect_pips, trail_stop_pips,",
        "max_spread_points, news_blackout_minutes, session_filter, enable_daily_deploy, ninja_enabled, dll.",
        "SELALU konfirmasi dengan Commander sebelum ubah setting. Jangan ubah tanpa izin.",
      ].join(" "),
      inputSchema: z.object({
        key: z.string().describe("Nama setting yang mau diubah, misal 'lot_size' atau 'auto_trade'"),
        value: z.union([z.string(), z.number(), z.boolean()]).describe("Nilai baru untuk setting tersebut"),
      }),
      execute: async ({ key, value }: { key: string; value: unknown }) => updateSettings(key, value),
    }),

    run_backtest: tool({
      description: [
        "Jalankan backtest engine (backtest/run.py) untuk test strategi secara historical.",
        "Output: hasil backtest termasuk win rate, total trades, profit factor, dll.",
        "PERINGATAN: Ini bisa makan waktu hingga 60 detik. Gunakan hanya kalau Commander minta.",
      ].join(" "),
      inputSchema: z.object({}),
      execute: async () => runBacktest(),
    }),

    // ── Full Agent Tools ──────────────────────────────────────────────────────

    shell_exec: tool({
      description: [
        "Jalankan PowerShell command apapun di komputer Commander. Tool PALING POWERFUL.",
        "Bisa: install npm/pip package, build app, git commit/push, jalankan script Python/Node, rename file, dll.",
        "Contoh: 'npm install axios', 'npx next build', 'git status', 'pip install pandas', 'Get-Process'.",
        "Untuk command destructive (rm, delete, format) → tanya Commander dulu.",
        "Default cwd: D:\\PROJECT TRADING\\sultan-advisor",
      ].join(" "),
      inputSchema: z.object({
        command: z.string().describe("PowerShell command yang dijalankan"),
        cwd: z.string().optional().describe("Working directory. Default: sultan-advisor folder"),
        timeout_seconds: z.number().min(1).max(300).optional().describe("Timeout detik (default 30)"),
      }),
      execute: async ({ command, cwd, timeout_seconds = 30 }: { command: string; cwd?: string; timeout_seconds?: number }) => {
        const workDir = cwd ?? `${PROJECT_ROOT}\\sultan-advisor`;
        return agentShellExec(command, workDir, timeout_seconds * 1000);
      },
    }),

    read_file: tool({
      description: [
        "Baca isi file apapun di komputer Commander.",
        "Gunakan untuk: baca source code, config, log, atau file apapun yang perlu dilihat.",
        "Contoh path: D:\\PROJECT TRADING\\sultan-advisor\\components\\dashboard-pro.tsx",
        "Otomatis truncate di 300 baris untuk file besar.",
      ].join(" "),
      inputSchema: z.object({
        path: z.string().describe("Path lengkap file yang dibaca"),
      }),
      execute: async ({ path }: { path: string }) => agentReadFile(path),
    }),

    write_file: tool({
      description: [
        "Tulis atau overwrite file di komputer Commander.",
        "Gunakan untuk: edit source code React/TypeScript, update config JSON, buat file baru.",
        "Ini bisa langsung edit komponen dashboard, API routes, system prompt, dll.",
        "Untuk file yang sudah ada: tunjukkan perubahan ke Commander sebelum write jika significant.",
      ].join(" "),
      inputSchema: z.object({
        path: z.string().describe("Path lengkap file yang ditulis"),
        content: z.string().describe("Konten lengkap file (akan overwrite seluruh file)"),
      }),
      execute: async ({ path, content }: { path: string; content: string }) => agentWriteFile(path, content),
    }),

    list_dir: tool({
      description: [
        "List isi direktori — lihat file dan folder.",
        "Gunakan untuk navigasi filesystem, cek struktur project, atau cari file yang akan dibaca/diedit.",
      ].join(" "),
      inputSchema: z.object({
        path: z.string().describe("Path direktori yang ingin dilihat"),
      }),
      execute: async ({ path }: { path: string }) => agentListDir(path),
    }),

    screenshot_analyze: tool({
      description: [
        "Ambil screenshot layar Commander SEKARANG dan analisis dengan AI vision (Claude).",
        "Bisa lihat: chart TradingView, MetaTrader 5, web dashboard, terminal error, apapun yang tampil di layar.",
        "Gunakan untuk: cek visual dashboard, debug error yang terlihat, verifikasi chart, lihat kondisi MT5.",
        "Output: deskripsi detail apa yang ada di layar beserta analisis.",
      ].join(" "),
      inputSchema: z.object({
        focus: z.string().optional().describe("Apa yang difokuskan? Contoh: 'chart TradingView H1', 'error di terminal', 'MT5 open positions'"),
      }),
      execute: async ({ focus }: { focus?: string }) => agentScreenshotAndAnalyze(focus),
    }),

    // ── Playwright Browser ────────────────────────────────────────────────────
    browser: tool({
      description: [
        "Kontrol browser headless (Chromium/Playwright) — bisa buka URL, screenshot, klik, isi form, scroll, baca teks.",
        "GUNAKAN untuk: buka website JS-rendered, scraping konten dinamis, cek harga real-time, baca berita, isi form pencarian.",
        "JANGAN gunakan fetch_url jika halaman butuh JS — pakai browser ini.",
        "WORKFLOW: navigate → get_text atau screenshot → close.",
        "Actions: navigate=buka URL, screenshot=foto halaman, get_text=baca konten, click=klik elemen CSS, type=isi input, scroll=gulir, close=tutup tab.",
        "Browser instance persist dalam session — navigate baru di tab yang sama.",
      ].join(" "),
      inputSchema: z.object({
        action: z.enum(["navigate","screenshot","get_text","click","type","scroll","close"])
          .describe("Aksi browser"),
        url:       z.string().optional().describe("URL tujuan (untuk navigate)"),
        selector:  z.string().optional().describe("CSS selector (untuk click/type)"),
        text:      z.string().optional().describe("Teks yang diketik (untuk type)"),
        direction: z.enum(["up","down"]).optional().describe("Arah scroll"),
        amount:    z.number().min(1).max(20).optional().describe("Jumlah scroll step (default 3)"),
      }),
      execute: async ({ action, url, selector, text, direction, amount }) =>
        playwrightAction(action, { url, selector, text, direction, amount }),
    }),
  };

  // Gemma 4 E4B: full tools + 10 steps + temp 0.7 (reliable tool calling)
  // Cloud: full tools + 15 steps
  const result = streamText({
    model: selectedModel,
    system: systemPrompt,
    messages: coreMessages,
    maxOutputTokens: 4096,
    temperature: isLocal ? 0.7 : undefined,
    ...(modelType === "cloud" ? {
      stopWhen: stepCountIs(15),
      tools: toolsWithContext,
    } : {
      stopWhen: stepCountIs(10),
      tools: toolsWithContext,
    }),
    onFinish: async ({ text }) => {
      if (sessionId && text) {
        await db.insert(messages).values({ id: nanoid(), sessionId, role: "assistant", content: text });
      }
    },
  });

  return result.toUIMessageStreamResponse();
}
