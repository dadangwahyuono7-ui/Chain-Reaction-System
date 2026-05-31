import { spawn } from "child_process";
import path from "path";
import { db } from "@/db";
import { marketContext } from "@/db/schema";
import { eq } from "drizzle-orm";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

type SnapshotOk  = { success: true;  ctx: Record<string, string>; rawState: Record<string, unknown> };
type SnapshotErr = { success: false; error: string };
type SnapshotResult = SnapshotOk | SnapshotErr;

function runSnapshot(): Promise<SnapshotResult> {
  return new Promise((resolve) => {
    const scriptPath = path.join(process.cwd(), "scripts", "tv-snapshot.mjs");
    const child = spawn(process.execPath, [scriptPath], {
      timeout: 12000,
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    child.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });

    child.on("close", () => {
      try {
        const result = JSON.parse(stdout.trim());
        resolve(result as SnapshotResult);
      } catch {
        resolve({ success: false, error: stderr.slice(0, 300) || "Script tidak menghasilkan output valid" });
      }
    });

    child.on("error", (err: Error) => {
      resolve({ success: false, error: err.message });
    });
  });
}

export async function POST() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const result = await runSnapshot();

  if (!result.success) {
    return Response.json({ success: false, error: result.error });
  }

  // Upsert each context variable — auto-insert kalau key belum ada di DB
  // (untuk v4 vars seperti M30_CF_COUNT, M30_CF_TYPE yang baru)
  const existing = await db.select().from(marketContext);
  const byName = new Map(existing.map(r => [r.variableName, r]));

  for (const [key, value] of Object.entries(result.ctx)) {
    if (value === undefined || value === null) continue;
    const row = byName.get(key);
    if (row) {
      await db
        .update(marketContext)
        .set({ value: String(value) })
        .where(eq(marketContext.variableName, key));
    } else {
      // Auto-derive label dari key untuk vars baru
      const label = key.endsWith('_CF_COUNT') ? `${key.replace('_CF_COUNT','')} CF Count`
                  : key.endsWith('_CF_TYPE')  ? `${key.replace('_CF_TYPE','')} CF Type`
                  : key;
      await db.insert(marketContext).values({
        id: crypto.randomUUID(),
        variableName: key,
        label,
        value: String(value),
      });
    }
  }

  // Return updated context
  const fresh = await db.select().from(marketContext);
  return Response.json({ success: true, data: fresh, rawState: result.rawState });
}
