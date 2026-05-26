import { auth } from "@/lib/auth";
import { db } from "@/db";
import { chatSessions } from "@/db/schema";
import { eq, desc } from "drizzle-orm";
import { headers } from "next/headers";

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });
  const rows = await db.select().from(chatSessions)
    .where(eq(chatSessions.userId, session.user.id))
    .orderBy(desc(chatSessions.updatedAt));
  return Response.json(rows);
}
