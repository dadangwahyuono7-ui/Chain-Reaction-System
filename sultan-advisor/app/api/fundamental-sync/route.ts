import { spawn } from "child_process";
import path from "path";
import { db } from "@/db";
import { marketContext } from "@/db/schema";
import { eq } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

type FundamentalOk  = { success: true;  snr: Record<string, string>; levels: unknown[] };
type FundamentalErr = { success: false; error: string };
type FundamentalResult = FundamentalOk | FundamentalErr;

function runFundamentalSnapshot(): Promise<FundamentalResult> {
  return new Promise((resolve) => {
    const scriptPath = path.join(process.cwd(), "scripts", "fundamental-snapshot.mjs");
    const child = spawn(process.execPath, [scriptPath], {
      timeout: 30_000, // TF switching takes time
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    child.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });

    child.on("close", () => {
      try {
        const result = JSON.parse(stdout.trim());
        resolve(result as FundamentalResult);
      } catch {
        resolve({
          success: false,
          error: stderr.slice(0, 400) || "Script tidak menghasilkan output valid",
        });
      }
    });

    child.on("error", (err: Error) => {
      resolve({ success: false, error: err.message });
    });
  });
}

// SNR keys we allow to be upserted (all keys output by fundamental-snapshot.mjs)
const ALLOWED_SNR_KEYS = new Set([
  "HARGA",
  "PDH", "PDL",
  "DAILY_OPEN",
  "PWH", "PWL",
  "WEEKLY_OPEN",
  "PMH", "PML",
  "ASIA_H", "ASIA_L",
  "LONDON_H", "LONDON_L",
  "ROUND_ABOVE", "ROUND_BELOW",
  "TP_ABOVE_1", "TP_ABOVE_2",
  "TP_BELOW_1", "TP_BELOW_2",
]);

export async function POST() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const result = await runFundamentalSnapshot();

  if (!result.success) {
    return Response.json({ success: false, error: result.error });
  }

  // Upsert each SNR value into market_context
  const existing = await db.select().from(marketContext);
  const byName = new Map(existing.map(r => [r.variableName, r]));

  for (const [key, value] of Object.entries(result.snr)) {
    if (!ALLOWED_SNR_KEYS.has(key)) continue;
    if (value === undefined || value === null || value === "") continue;

    const row = byName.get(key);
    if (row) {
      await db
        .update(marketContext)
        .set({ value: String(value), updatedAt: new Date() })
        .where(eq(marketContext.variableName, key));
    }
    // If the key doesn't exist yet (not seeded), skip — seeding is handled by the panel
  }

  // Return updated context
  const fresh = await db.select().from(marketContext);
  return Response.json({ success: true, data: fresh, levels: result.levels });
}
