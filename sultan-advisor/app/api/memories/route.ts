import { auth } from "@/lib/auth";
import { db } from "@/db";
import { memories } from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import { headers } from "next/headers";
import { nanoid } from "nanoid";

// GET — list all memories (sorted by importance + recency)
export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const rows = await db
    .select()
    .from(memories)
    .orderBy(desc(memories.importance), desc(memories.createdAt))
    .limit(100);

  return Response.json(rows);
}

// POST — manually add a memory
export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const body = await req.json();
  const { content, category, importance = 2, tags } = body;

  if (!content || !category) {
    return Response.json({ error: "content and category required" }, { status: 400 });
  }

  const id = nanoid();
  await db.insert(memories).values({
    id,
    content,
    category,
    importance,
    tags: tags || null,
    sessionId: null,
  });

  return Response.json({ id, status: "saved" });
}

// DELETE — remove a specific memory
export async function DELETE(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");

  if (!id) return Response.json({ error: "id required" }, { status: 400 });

  await db.delete(memories).where(eq(memories.id, id));
  return Response.json({ status: "deleted" });
}
