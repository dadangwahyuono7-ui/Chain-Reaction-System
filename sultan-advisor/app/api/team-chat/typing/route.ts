import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { broadcast } from "@/lib/team-chat-bus";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const body = (await req.json().catch(() => ({}))) as { isTyping?: boolean };
  const userName = session.user.name || session.user.email.split("@")[0];

  broadcast({ type: "typing", userName, isTyping: !!body.isTyping });
  return Response.json({ ok: true });
}
