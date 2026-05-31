import { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;

  if (!token || !chatId) {
    return Response.json({ skipped: true, reason: "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set" });
  }

  const body = await req.json() as { message: string };
  if (!body.message) {
    return Response.json({ error: "message required" }, { status: 400 });
  }

  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: body.message,
        parse_mode: "HTML",
      }),
    });

    const data = await res.json() as { ok: boolean; description?: string };

    if (!data.ok) {
      console.error("[telegram-alert] Telegram API error:", data.description);
      return Response.json({ error: data.description }, { status: 502 });
    }

    return Response.json({ ok: true });
  } catch (err) {
    console.error("[telegram-alert] fetch error:", err);
    return Response.json({ error: "network error" }, { status: 500 });
  }
}
