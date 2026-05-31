import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { chatBus, addPresence, getOnline, type BusEvent } from "@/lib/team-chat-bus";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const userName = session.user.name || session.user.email.split("@")[0];
  const encoder = new TextEncoder();

  let removePresence: (() => void) | null = null;
  let heartbeat: ReturnType<typeof setInterval> | null = null;
  let onEvent: ((e: BusEvent) => void) | null = null;

  const stream = new ReadableStream({
    start(controller) {
      const send = (data: object) => {
        try { controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`)); }
        catch { /* closed */ }
      };

      // Snapshot presence awal
      send({ type: "presence", online: getOnline() });

      // Listen bus → forward ke client ini
      onEvent = (e: BusEvent) => send(e);
      chatBus.on("event", onEvent);

      // Daftarkan presence user ini (broadcast ke semua)
      removePresence = addPresence(userName);

      // Heartbeat tiap 25s biar koneksi gak diputus proxy/tunnel
      heartbeat = setInterval(() => {
        try { controller.enqueue(encoder.encode(`: ping\n\n`)); } catch { /* closed */ }
      }, 25000);
    },
    cancel() {
      if (heartbeat) clearInterval(heartbeat);
      if (onEvent) chatBus.off("event", onEvent);
      if (removePresence) removePresence();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
