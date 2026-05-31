import { auth } from "@/lib/auth";
import { db } from "@/db";
import { user, session, account, messages, chatSessions } from "@/db/schema";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { nanoid } from "nanoid";

const ADMIN_EMAIL = "dadangwahyuono@gmail.com";

async function requireAdmin() {
  const s = await auth.api.getSession({ headers: await headers() });
  if (!s) return null;
  if (s.user.email !== ADMIN_EMAIL) return null;
  return s;
}

// GET — list all users
export async function GET() {
  const s = await requireAdmin();
  if (!s) return new Response("Forbidden", { status: 403 });

  const users = await db.select({
    id: user.id,
    name: user.name,
    email: user.email,
    emailVerified: user.emailVerified,
    createdAt: user.createdAt,
  }).from(user);

  return Response.json(users);
}

// DELETE — delete a user by id (cascade: sessions, accounts, messages, chat sessions)
export async function DELETE(req: Request) {
  const s = await requireAdmin();
  if (!s) return new Response("Forbidden", { status: 403 });

  const { searchParams } = new URL(req.url);
  const userId = searchParams.get("id");
  if (!userId) return Response.json({ error: "id required" }, { status: 400 });

  // Prevent self-deletion
  if (userId === s.user.id) {
    return Response.json({ error: "Tidak bisa hapus akun sendiri" }, { status: 400 });
  }

  // Cascade delete: messages → chatSessions → account → session → user
  const userSessions = await db.select({ id: chatSessions.id }).from(chatSessions).where(eq(chatSessions.userId, userId));
  for (const cs of userSessions) {
    await db.delete(messages).where(eq(messages.sessionId, cs.id));
  }
  await db.delete(chatSessions).where(eq(chatSessions.userId, userId));
  await db.delete(account).where(eq(account.userId, userId));
  await db.delete(session).where(eq(session.userId, userId));
  await db.delete(user).where(eq(user.id, userId));

  return Response.json({ ok: true, deleted: userId });
}

// PATCH — verify a user's email (admin only)
export async function PATCH(req: Request) {
  const s = await requireAdmin();
  if (!s) return new Response("Forbidden", { status: 403 });

  const { searchParams } = new URL(req.url);
  const userId = searchParams.get("id");
  if (!userId) return Response.json({ error: "id required" }, { status: 400 });

  await db.update(user)
    .set({ emailVerified: true, updatedAt: new Date() })
    .where(eq(user.id, userId));

  return Response.json({ ok: true });
}

// POST — create new user (admin only)
export async function POST(req: Request) {
  const s = await requireAdmin();
  if (!s) return new Response("Forbidden", { status: 403 });

  const body = await req.json();
  const { name, email, password } = body as { name?: string; email?: string; password?: string };

  if (!name?.trim() || !email?.trim() || !password?.trim()) {
    return Response.json({ error: "Nama, email, dan password wajib diisi" }, { status: 400 });
  }
  if (password.length < 6) {
    return Response.json({ error: "Password minimal 6 karakter" }, { status: 400 });
  }

  // Check email already exists
  const existing = await db.select({ id: user.id }).from(user).where(eq(user.email, email.trim().toLowerCase())).get();
  if (existing) {
    return Response.json({ error: "Email sudah terdaftar" }, { status: 400 });
  }

  // Use better-auth to create the user (handles password hashing)
  try {
    const result = await auth.api.signUpEmail({
      body: {
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
      },
    });
    if (!result) return Response.json({ error: "Gagal membuat akun" }, { status: 500 });

    // Auto-verify email — admin yang buat, tidak perlu konfirmasi email
    const newUserId = (result as { user?: { id: string } }).user?.id;
    if (newUserId) {
      await db.update(user)
        .set({ emailVerified: true, updatedAt: new Date() })
        .where(eq(user.id, newUserId));
    }

    return Response.json({ ok: true, userId: newUserId ?? nanoid() });
  } catch (e) {
    return Response.json({ error: e instanceof Error ? e.message : "Gagal membuat akun" }, { status: 500 });
  }
}
