import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { db } from "@/db";
import { teamMessages } from "@/db/schema";
import { desc } from "drizzle-orm";
import { nanoid } from "nanoid";
import { broadcast, type ChatMessage } from "@/lib/team-chat-bus";

const ADMIN_EMAIL = "dadangwahyuono@gmail.com";

export const dynamic = "force-dynamic";

// Ambil 100 pesan terakhir (urutan lama → baru)
export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const rows = await db
    .select()
    .from(teamMessages)
    .orderBy(desc(teamMessages.createdAt))
    .limit(100);

  const messages: ChatMessage[] = rows
    .reverse()
    .map((r) => ({
      id: r.id,
      userId: r.userId,
      userName: r.userName,
      text: r.text,
      imageUrl: r.imageUrl ?? null,
      createdAt: (r.createdAt instanceof Date ? r.createdAt.getTime() : Number(r.createdAt) * 1000),
    }));

  return Response.json({ messages });
}

// Kirim pesan baru
export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const body = (await req.json()) as { text?: string; imageUrl?: string };
  const text = (body.text ?? "").trim();
  const imageUrl = (body.imageUrl ?? "").trim() || null;
  // Pesan harus ada teks ATAU gambar
  if (!text && !imageUrl) return Response.json({ error: "Pesan kosong" }, { status: 400 });
  if (text.length > 2000) return Response.json({ error: "Pesan terlalu panjang" }, { status: 400 });
  // imageUrl hanya boleh path upload internal (anti-abuse)
  if (imageUrl && !imageUrl.startsWith("/uploads/")) {
    return Response.json({ error: "imageUrl tidak valid" }, { status: 400 });
  }

  const userName = session.user.name || session.user.email.split("@")[0];
  const now = new Date();
  const id = nanoid();

  await db.insert(teamMessages).values({
    id,
    userId: session.user.id,
    userName,
    text,
    imageUrl,
    createdAt: now,
  });

  const message: ChatMessage = {
    id,
    userId: session.user.id,
    userName,
    text,
    imageUrl,
    createdAt: now.getTime(),
  };

  broadcast({ type: "message", message });

  return Response.json({ ok: true, message });
}

// Clear all messages — admin only
export async function DELETE() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });
  if (session.user.email !== ADMIN_EMAIL) return new Response("Forbidden", { status: 403 });

  await db.delete(teamMessages);

  // Broadcast clear event so all clients clear their UI
  broadcast({ type: "clear" } as never);

  return Response.json({ ok: true });
}
