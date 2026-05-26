"use client";

import { useChat } from "@ai-sdk/react";
import { useEffect, useRef, useState, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import { SendIcon, MicIcon, SquareIcon, ShieldCheckIcon, TrendingUpIcon, LayoutDashboardIcon, AlertOctagonIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { MessageBubble } from "./message-bubble";
import type { UIMessage } from "ai";

interface Props {
  sessionId: string | null;
  sessionTitle?: string;
  onSessionId: (id: string) => void;
  /** When set, auto-fires this prompt immediately (from TV sync) */
  autoPrompt?: string | null;
  onAutoPromptConsumed?: () => void;
}

const QUICK_PROMPTS = [
  {
    icon: ShieldCheckIcon,
    label: "Cek Setup Valid?",
    prompt: "Berdasarkan state market yang ada, apakah ada setup valid untuk entry sekarang? Jalankan full analisis CMP/VR/CF per TF dan cek semua guard rules.",
  },
  {
    icon: LayoutDashboardIcon,
    label: "Storyline Aktif",
    prompt: "Jelaskan storyline aktif saat ini per TF. Untuk setiap TF yang ada CMP-nya: VR dari mana, sudah terjadi belum, CF LowRisk dan HighRisk dari TF mana, dan trading di TF mana. Mana setup paling matang?",
  },
  {
    icon: TrendingUpIcon,
    label: "Bias & Momentum",
    prompt: "Apa bias market H4 saat ini? Siapa yang bagi VR dan seberapa kuat momentumnya? Implikasinya terhadap setup di TF bawah (H1, M30)?",
  },
  {
    icon: AlertOctagonIcon,
    label: "Guard Check",
    prompt: "Jalankan guard check lengkap: barrier guard, session, spread, dan news blackout. Apakah kondisi saat ini aman untuk entry?",
  },
];

export function ChatInterface({ sessionId, sessionTitle, onSessionId, autoPrompt, onAutoPromptConsumed }: Props) {
  const [input, setInput] = useState("");
  const bottomRef    = useRef<HTMLDivElement>(null);
  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const [isListening, setIsListening] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const autoFiredRef   = useRef<string | null>(null);

  const { messages, sendMessage, setMessages, status, stop, id, error } = useChat({
    id: sessionId ?? undefined,
  });

  const isLoading = status === "streaming" || status === "submitted";

  useEffect(() => { if (id && !sessionId) onSessionId(id); }, [id, sessionId, onSessionId]);

  useEffect(() => {
    if (!sessionId) { setMessages([]); return; }
    fetch(`/api/sessions/${sessionId}`)
      .then(r => r.json())
      .then((dbMsgs: Array<{ id: string; role: string; content: string }>) => {
        setMessages(dbMsgs.map(m => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          parts: [{ type: "text" as const, text: m.content }],
        })));
      });
  }, [sessionId, setMessages]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleSend = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || isLoading) return;
    if (!text) setInput("");
    await sendMessage({ role: "user", parts: [{ type: "text" as const, text: msg }] });
  }, [input, isLoading, sendMessage]);

  // Auto-fire prompt when TV sync completes
  useEffect(() => {
    if (!autoPrompt) return;
    if (autoFiredRef.current === autoPrompt) return; // deduplicate
    if (isLoading) return;
    autoFiredRef.current = autoPrompt;
    onAutoPromptConsumed?.();
    // Small delay so UI settles after sync
    const t = setTimeout(() => { handleSend(autoPrompt); }, 400);
    return () => clearTimeout(t);
  }, [autoPrompt, isLoading, handleSend, onAutoPromptConsumed]);

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  function startVoice() {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const w = window as any;
    const SR = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!SR) return alert("Browser tidak mendukung voice input.");
    const recognition = new SR();
    recognition.lang = "id-ID";
    recognition.continuous = false;
    recognition.interimResults = false;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      setInput(prev => prev ? prev + " " + event.results[0][0].transcript : event.results[0][0].transcript);
      setIsListening(false);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend   = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }

  const visibleMessages = messages.filter(m => m.role === "user" || m.role === "assistant");
  const isEmpty = visibleMessages.length === 0;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5">

        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full space-y-8 text-center">
            <div>
              <div className="text-2xl font-black text-amber-500 tracking-tighter">CHAIN REACTION</div>
              <div className="text-xs text-zinc-500 mt-1">Trading Advisor — XAUUSD Daily Deploy</div>
            </div>
            <div className="grid grid-cols-2 gap-2 max-w-lg w-full">
              {QUICK_PROMPTS.map(qp => (
                <button
                  key={qp.label}
                  onClick={() => { setInput(qp.prompt); textareaRef.current?.focus(); }}
                  className="flex items-start gap-2 p-3 bg-zinc-900 border border-zinc-800 rounded-xl text-left hover:bg-zinc-800 hover:border-zinc-700 transition-all group"
                >
                  <qp.icon className="w-3.5 h-3.5 text-zinc-500 group-hover:text-amber-400 mt-0.5 shrink-0" />
                  <span className="text-xs text-zinc-400 group-hover:text-zinc-200">{qp.label}</span>
                </button>
              ))}
            </div>
            <p className="text-xs text-zinc-600 max-w-sm">
              Klik ⚡ Sync di panel kanan — analisis storyline muncul otomatis.
            </p>
          </div>
        ) : (
          <>
            {visibleMessages.map((m, i) => (
              <MessageBubble
                key={m.id}
                message={m}
                sessionTitle={sessionTitle}
                isStreaming={isLoading && i === visibleMessages.length - 1 && m.role === "assistant"}
                onInject={handleSend}
              />
            ))}

            {isLoading && visibleMessages.at(-1)?.role === "user" && (
              <div className="flex justify-start">
                <div className="bg-zinc-900 border border-zinc-800 rounded-2xl rounded-tl-sm px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce [animation-delay:0ms]" />
                      <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce [animation-delay:150ms]" />
                      <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-bounce [animation-delay:300ms]" />
                    </div>
                    <span className="text-xs text-zinc-500">Menganalisis storyline...</span>
                  </div>
                </div>
              </div>
            )}

            {error && !isLoading && (
              <div className="flex justify-start">
                <div className="bg-red-950 border border-red-900 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[85%]">
                  <p className="text-xs text-red-400 font-medium mb-1">Gagal mendapat respons</p>
                  <p className="text-xs text-red-300/70">
                    {error.message?.includes("401")
                      ? "Model tidak merespons. Pastikan Qwen3-8B server jalan di port 8080."
                      : error.message ?? "Cek server log untuk detail."}
                  </p>
                  <button onClick={() => handleSend()} className="mt-2 text-xs text-red-400 hover:text-red-300 underline">
                    Coba lagi
                  </button>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-zinc-800 px-4 py-4 bg-zinc-950">
        <div className="flex gap-2 items-end max-w-4xl mx-auto">
          <div className="flex-1">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Tanya setup, storyline, CMP/VR/CF... (Enter kirim)"
              rows={1}
              className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-600 resize-none min-h-[44px] max-h-40 text-sm focus:border-amber-700 rounded-xl"
              style={{ height: "auto" }}
              onInput={e => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 160) + "px";
              }}
            />
          </div>
          <button
            type="button"
            onClick={isListening
              ? () => { recognitionRef.current?.stop(); setIsListening(false); }
              : startVoice}
            className={cn(
              "h-11 w-11 rounded-xl border flex items-center justify-center transition-all shrink-0",
              isListening
                ? "bg-red-500 border-red-600 text-white animate-pulse"
                : "bg-zinc-900 border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-500"
            )}
          >
            <MicIcon className="w-4 h-4" />
          </button>
          {isLoading ? (
            <button onClick={() => stop()} className="h-11 w-11 bg-red-600 hover:bg-red-700 rounded-xl flex items-center justify-center shrink-0">
              <SquareIcon className="w-4 h-4 text-white" />
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim()}
              className="h-11 w-11 bg-amber-500 hover:bg-amber-400 text-black rounded-xl flex items-center justify-center shrink-0 disabled:opacity-30 transition-colors"
            >
              <SendIcon className="w-4 h-4" />
            </button>
          )}
        </div>
        <p className="text-center text-xs text-zinc-700 mt-2">
          Chain Reaction — doktrin CMP/VR/CF. Bukan financial advice.
        </p>
      </div>
    </div>
  );
}
