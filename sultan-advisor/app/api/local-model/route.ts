/**
 * /api/local-model
 * GET  — status llama.cpp server + model aktif
 * POST — switch model (kill llama-server, start bat file baru)
 */

import { exec } from "child_process";
import { promisify } from "util";
const execAsync = promisify(exec);

export const dynamic = "force-dynamic";

// Definisi semua model lokal yang tersedia
export const LOCAL_MODELS = [
  {
    id:    "qwen3-8b",
    label: "Qwen3 8B",
    desc:  "Tercepat — daily trading, quick analysis",
    size:  "4.7 GB",
    stars: 3,
    bat:   "F:\\AI-AGENT\\start-qwen3-8b.bat",
    fast:  true,
  },
  {
    id:    "gemma3-12b",
    label: "Gemma 3 12B Vision",
    desc:  "Vision capable — analisis screenshot chart",
    size:  "7.6 GB",
    stars: 4,
    bat:   "F:\\AI-AGENT\\start-gemma3-12b.bat",
    fast:  false,
  },
  {
    id:    "qwen36-moe",
    label: "Qwen3.6 35B MoE",
    desc:  "Best balance — kualitas 35B, speed 3B aktif",
    size:  "10 GB",
    stars: 5,
    bat:   "F:\\AI-AGENT\\start-qwen36.bat",
    fast:  false,
  },
  {
    id:    "qwen25-32b",
    label: "Qwen2.5 32B",
    desc:  "Analisis mendalam — tidak buru-buru",
    size:  "18.5 GB",
    stars: 5,
    bat:   "F:\\AI-AGENT\\start-qwen2.5-32b.bat",
    fast:  false,
  },
] as const;

async function getLlamaStatus() {
  try {
    const res = await fetch("http://localhost:8080/health", {
      signal: AbortSignal.timeout(2000),
    });
    if (!res.ok) return { running: false, model: null };
    // Try /v1/models untuk dapat nama model
    try {
      const m = await fetch("http://localhost:8080/v1/models", {
        signal: AbortSignal.timeout(2000),
      });
      const j = await m.json();
      const modelId = j?.data?.[0]?.id || j?.models?.[0]?.id || null;
      return { running: true, model: modelId };
    } catch {
      return { running: true, model: "unknown" };
    }
  } catch {
    return { running: false, model: null };
  }
}

export async function GET() {
  const status = await getLlamaStatus();
  return Response.json({ ...status, models: LOCAL_MODELS });
}

export async function POST(req: Request) {
  const { modelId } = await req.json().catch(() => ({}));
  const model = LOCAL_MODELS.find(m => m.id === modelId);
  if (!model) {
    return Response.json({ error: "Model tidak ditemukan" }, { status: 400 });
  }

  try {
    // 1. Kill llama-server yang sedang jalan
    await execAsync('taskkill /F /IM "llama-server.exe" 2>nul').catch(() => {});
    await new Promise(r => setTimeout(r, 1500));

    // 2. Start bat file baru di background
    const cmd = `start "" /B cmd /C "${model.bat}"`;
    await execAsync(cmd);

    // 3. Poll sampai server ready (max 180 detik untuk model besar)
    const maxWait = model.fast ? 30 : 180;
    let ready = false;
    for (let i = 0; i < maxWait; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const s = await getLlamaStatus();
      if (s.running) { ready = true; break; }
    }

    return Response.json({
      success: ready,
      modelId,
      label: model.label,
      message: ready
        ? `${model.label} siap digunakan`
        : `${model.label} butuh waktu lebih lama — tunggu sebentar lalu coba chat`,
    });
  } catch (e) {
    return Response.json({
      error: `Gagal switch model: ${e instanceof Error ? e.message : "unknown"}`,
    }, { status: 500 });
  }
}
