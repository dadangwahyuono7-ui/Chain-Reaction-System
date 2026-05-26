import { streamText, type LanguageModel } from "ai";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { messages, chatSessions, marketContext } from "@/db/schema";
import { eq } from "drizzle-orm";
import { buildSystemPrompt } from "@/lib/system-prompt";
import { headers } from "next/headers";
import { nanoid } from "nanoid";

function buildModel(): LanguageModel {
  const apiKey  = process.env.LLM_API_KEY;
  const baseURL = process.env.LLM_BASE_URL;
  const modelId = process.env.LLM_MODEL;

  const client = createOpenAICompatible({
    name: "local",
    apiKey,
    baseURL: baseURL ?? "",
    // Disable Qwen3 thinking mode — llama.cpp sends thinking to `reasoning_content`
    // (not `content`) which the AI SDK can't read, causing empty responses.
    fetch: async (url, options) => {
      if (options?.body) {
        try {
          const body = JSON.parse(options.body as string);
          // llama.cpp: disable Qwen3 <think> tokens
          body.chat_template_kwargs = { enable_thinking: false };
          return fetch(url, { ...options, body: JSON.stringify(body) });
        } catch { /* fall through to normal fetch */ }
      }
      return fetch(url, options as RequestInit);
    },
  });
  return client(modelId ?? "qwen3-8b-q4");
}

export async function POST(req: Request) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const body = await req.json();
  const { messages: chatMessages, id: sessionId } = body;

  const ctxRows = await db.select().from(marketContext);
  const ctx = Object.fromEntries(
    ctxRows.map((r) => [r.variableName, { label: r.label, value: r.value }])
  );

  const systemPrompt = buildSystemPrompt(ctx);

  if (sessionId) {
    const existing = await db.select().from(chatSessions).where(eq(chatSessions.id, sessionId)).get();
    if (!existing) {
      await db.insert(chatSessions).values({ id: sessionId, userId: session.user.id, title: "Sesi Baru" });
    }
  }

  const lastUserMsg = chatMessages?.at(-1);
  const userText = lastUserMsg?.role === "user"
    ? (lastUserMsg.content || (lastUserMsg.parts?.find((p: { type: string }) => p.type === "text")?.text ?? ""))
    : null;

  if (userText && sessionId) {
    await db.insert(messages).values({ id: nanoid(), sessionId, role: "user", content: userText });

    const existing = await db.select().from(chatSessions).where(eq(chatSessions.id, sessionId)).get();
    if (existing?.title === "Sesi Baru") {
      await db.update(chatSessions).set({ title: userText.slice(0, 60) }).where(eq(chatSessions.id, sessionId));
    }
  }

  const coreMessages = (chatMessages ?? [])
    .filter((m: { role: string }) => m.role === "user" || m.role === "assistant")
    .map((m: { role: string; content?: string; parts?: Array<{ type: string; text?: string }> }) => ({
      role: m.role as "user" | "assistant",
      content: m.content || (m.parts?.filter((p) => p.type === "text").map((p) => p.text).join("") ?? ""),
    }));

  const result = streamText({
    model: buildModel(),
    system: systemPrompt,
    messages: coreMessages,
    maxOutputTokens: 4096,
    onFinish: async ({ text }) => {
      if (sessionId && text) {
        await db.insert(messages).values({ id: nanoid(), sessionId, role: "assistant", content: text });
      }
    },
  });

  return result.toUIMessageStreamResponse();
}
