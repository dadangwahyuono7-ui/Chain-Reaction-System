import { auth } from "@/lib/auth";
import { db } from "@/db";
import { chatSessions, messages } from "@/db/schema";
import { eq, asc } from "drizzle-orm";
import { headers } from "next/headers";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });
  const { id } = await params;
  const msgs = await db.select().from(messages).where(eq(messages.sessionId, id)).orderBy(asc(messages.createdAt));
  return Response.json(msgs);
}

export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });
  const { id } = await params;
  const { title } = await req.json();
  await db.update(chatSessions).set({ title: title.slice(0, 80) }).where(eq(chatSessions.id, id));
  return Response.json({ ok: true });
}

export async function DELETE(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });
  const { id } = await params;
  await db.delete(chatSessions).where(eq(chatSessions.id, id));
  return Response.json({ ok: true });
}
