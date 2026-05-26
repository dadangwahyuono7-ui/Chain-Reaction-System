import { auth } from "@/lib/auth";
import { db } from "@/db";
import { marketContext } from "@/db/schema";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { nanoid } from "nanoid";

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });
  return Response.json(await db.select().from(marketContext));
}

export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const { variableName, label, value } = await req.json();
  const existing = await db.select().from(marketContext).where(eq(marketContext.variableName, variableName)).get();

  if (existing) {
    await db.update(marketContext).set({ value, updatedAt: new Date() }).where(eq(marketContext.variableName, variableName));
  } else {
    await db.insert(marketContext).values({ id: nanoid(), variableName, label, value });
  }

  return Response.json({ ok: true });
}
