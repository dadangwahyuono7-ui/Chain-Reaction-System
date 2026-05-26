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

  // Upsert each context variable
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
    }
    // Skip unknown keys — panel only shows seeded vars
  }

  // Return updated context
  const fresh = await db.select().from(marketContext);
  return Response.json({ success: true, data: fresh, rawState: result.rawState });
}
