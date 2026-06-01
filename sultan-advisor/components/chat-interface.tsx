"use client";

import { useChat } from "@ai-sdk/react";
import { useEffect, useRef, useState, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import { SendIcon, MicIcon, SquareIcon, ShieldCheckIcon, TrendingUpIcon, LayoutDashboardIcon, AlertOctagonIcon, CloudIcon, CpuIcon, PaperclipIcon, XIcon, FileTextIcon, ImageIcon, ZapIcon, TargetIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { MessageBubble } from "./message-bubble";
import { useSession } from "@/lib/auth-client";
import type { UIMessage } from "ai";

interface Props {
  sessionId: string | null;
  sessionTitle?: string;
  onSessionId: (id: string) => void;
  /** When set, auto-fires this prompt immediately (from TV sync) */
  autoPrompt?: string | null;
  onAutoPromptConsumed?: () => void;
}

function useActiveInstrument() {
  const [instrument, setInstrument] = useState("XAUUSD");
  useEffect(() => {
    fetch("/api/context")
      .then(r => r.json())
      .then((rows: { variableName: string; value: string }[]) => {
        const sym = rows.find(r => r.variableName === "TV_SYMBOL")?.value?.trim();
        if (sym) setInstrument(sym);
      })
      .catch(() => {});
    // poll tiap 15s biar ikut saat chart TV di-switch
    const t = setInterval(() => {
      fetch("/api/context")
        .then(r => r.json())
        .then((rows: { variableName: string; value: string }[]) => {
          const sym = rows.find(r => r.variableName === "TV_SYMBOL")?.value?.trim();
          if (sym) setInstrument(sym);
        })
        .catch(() => {});
    }, 15_000);
    return () => clearInterval(t);
  }, []);
  return instrument;
}

const QUICK_PROMPTS = [
  {
    icon: TargetIcon,
    label: "Analisa Lengkap + Entry/SL/TP",
    prompt: [
      "ANALISA LENGKAP MODE ELITE. Ikuti URUTAN WAJIB ini, jangan skip langkah, jangan ngarang angka:",
      "1) Panggil get_market_context dulu (kalau data terasa stale, panggil trigger_sync) untuk state CMP/VR/CF terbaru tiap TF.",
      "2) Panggil get_fund_data — baca Volume Profile (POC/HVN/LVN = zona akumulasi fund), liquidity pool (stop numpuk), basis, DXY & US10Y + macro bias.",
      "3) Tentukan setup terbaik per DOKTRIN murni (CMP→VR→CF, fase F1/F2/F3). HANYA F3 (VR=YA & CF=YA) yang PRIME ENTRY. F1/F2 = belum, bilang apa adanya.",
      "4) Panggil get_ohlc di TF tempat VR terjadi untuk SL PRESISI (high/low candle VR + buffer 3-5 pts). DILARANG pakai angka bulat tebakan untuk SL.",
      "5) Panggil calculate_risk untuk validasi arah SL/TP & R:R sebelum present plan.",
      "",
      "ATURAN ANTI-HALU (WAJIB): Kalau belum sync / belum ada CMP / belum F3 → JUJUR bilang 'belum ada setup prime, ini alasannya' dan JANGAN bikin entry/SL/TP karangan. Semua angka HARUS dari data nyata (OHLC, SNR, fund), bukan tebakan.",
      "",
      "OUTPUT: (a) Konfirmasi state literal dari tabel, (b) Storyline per TF, (c) Setup terbaik + Grade A+/A/B/C dengan alasan, (d) TRADE PLAN: Arah/Entry/SL/TP1/TP2/Size, (e) CONFLUENCE FUND: apakah entry dekat HVN/POC/liquidity pool & apakah SEARAH macro bias DXY/yield (kalau lawan makro → turunkan grade), (f) Watchlist.",
    ].join("\n"),
  },
  {
    icon: ShieldCheckIcon,
    label: "Cek Setup Valid?",
    prompt: "Berdasarkan state market yang ada, apakah ada setup valid untuk entry sekarang? Jalankan full analisis CMP/VR/CF per TF dan cek semua guard rules.",
  },
  {
    icon: LayoutDashboardIcon,
    label: "Storyline Aktif",
    prompt: "Jelaskan storyline aktif saat ini per TF. Sambungkan relasi parent→child: TF mana yang jadi VR untuk TF di atasnya, TF mana yang masih CONTI territory, TF mana yang sudah masuk siklus VR→CF. Mana setup paling matang?",
  },
  {
    icon: TrendingUpIcon,
    label: "CONTI / Scalp",
    prompt: "Cek CONTI territory sekarang. Untuk setiap TF besar yang sudah CMP tapi belum VR: (1) sebutkan arah & TF master-nya, (2) TF entry yang valid (searah master), (3) SOP entry-nya (VR TF kecil → CF), (4) TP target & size yang aman. Ini untuk scalping ikut arah TF besar.",
  },
  {
    icon: AlertOctagonIcon,
    label: "Guard Check",
    prompt: "Jalankan guard check lengkap: barrier guard, session, spread, dan news blackout. Apakah kondisi saat ini aman untuk entry?",
  },
];

export function ChatInterface({ sessionId, sessionTitle, onSessionId, autoPrompt, onAutoPromptConsumed }: Props) {
  const instrument = useActiveInstrument();
  const [input, setInput] = useState("");

  // -- Attachment state -------------------------------------------------------
  type Attachment = {
    name: string; size: number; kind: "image" | "file";
    url: string;           // /uploads/... untuk preview + link
    base64?: string;       // image only — dikirim ke AI sebagai content block
    mimeType?: string;
    savedPath?: string;    // file only — path lokal
  };
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading,   setUploading]   = useState(false);
  const fileInputRef  = useRef<HTMLInputElement>(null);
  const bottomRef    = useRef<HTMLDivElement>(null);
  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const [isListening, setIsListening] = useState(false);
  const [modelChoice, setModelChoice] = useState<"local" | "cloud">("local");
  // System Access (owner-only): gate tool sakti (shell/file/browser/settings). Default OFF.
  const [systemAccess, setSystemAccess] = useState(false);
  const { data: authData } = useSession();
  const isOwner = authData?.user?.email === "dadangwahyuono@gmail.com";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef  = useRef<any>(null);
  const autoFiredRef    = useRef<string | null>(null);
  // Ref so handleSend always reads current modelChoice without needing it as dependency
  const modelChoiceRef  = useRef(modelChoice);
  useEffect(() => { modelChoiceRef.current = modelChoice; }, [modelChoice]);
  const systemAccessRef = useRef(systemAccess);
  useEffect(() => { systemAccessRef.current = systemAccess; }, [systemAccess]);

  const { messages, sendMessage, setMessages, status, stop, id, error } = useChat({
    id: sessionId ?? undefined,
    // body is passed per-message in handleSend so we always use current modelChoice
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

  // -- Upload file/gambar ke server -----------------------------------------
  const handleAttach = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    const newAtts: Attachment[] = [];
    for (const file of Array.from(files)) {
      try {
        const form = new FormData();
        form.append("file", file);
        const r = await fetch("/api/chat-upload", { method: "POST", body: form });
        const j = await r.json();
        if (r.ok) newAtts.push(j as Attachment);
        else alert(`Upload gagal: ${j.error}`);
      } catch (e) { alert(`Upload error: ${e}`); }
    }
    setAttachments(prev => [...prev, ...newAtts]);
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  // -- Paste gambar dari clipboard (Ctrl+V / screenshot langsung) ------------
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData?.items ?? []);
    const imgItems = items.filter(i => i.kind === "file" && i.type.startsWith("image/"));
    if (imgItems.length === 0) return;
    e.preventDefault();
    const files = imgItems.map(i => i.getAsFile()).filter(Boolean) as File[];
    const dt = new DataTransfer();
    files.forEach(f => dt.items.add(f));
    handleAttach(dt.files);
  }, [handleAttach]);

  const handleSend = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim();
    const hasAttachments = attachments.length > 0;
    if (!msg && !hasAttachments) return;
    if (isLoading) return;
    if (!text) setInput("");

    // Build multimodal content — AI SDK v4 pakai experimental_attachments
    // untuk gambar (vision). Kita juga encode URL di text buat MessageBubble bisa render.
    const textParts: string[] = [];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const experimentalAttachments: any[] = [];

    for (const att of attachments) {
      if (att.kind === "image") {
        // Tag buat bubble render gambar
        textParts.push(`[img:${att.url}]`);
        // Kirim ke AI sebagai attachment (vision)
        experimentalAttachments.push({
          url: `data:${att.mimeType};base64,${att.base64}`,
          name: att.name,
          contentType: att.mimeType,
        });
      } else {
        textParts.push(`[File terlampir: ${att.name} — tersimpan di: ${att.savedPath ?? att.url}. Kamu bisa baca isinya via read_file.]`);
      }
    }

    if (msg) textParts.push(msg);
    const fullText = textParts.join("\n");
    setAttachments([]);

    await sendMessage(
      { role: "user", parts: [{ type: "text" as const, text: fullText }] },
      {
        body: { model: modelChoiceRef.current, systemAccess: systemAccessRef.current },
        ...(experimentalAttachments.length > 0 ? { experimental_attachments: experimentalAttachments } : {}),
      }
    );
  }, [input, attachments, isLoading, sendMessage]);

  // Auto-fire prompt when TV sync detects CF/VR event
  useEffect(() => {
    if (!autoPrompt) return;
    if (autoFiredRef.current === autoPrompt) return; // deduplicate
    if (isLoading) return;
    const prompt = autoPrompt;        // capture sebelum parent clear via onAutoPromptConsumed
    autoFiredRef.current = prompt;
    onAutoPromptConsumed?.();         // clear parent state — tapi captured prompt aman di closure
    void handleSend(prompt);          // fire langsung, no setTimeout race condition
    // (tidak ada cleanup — tidak ada timer yang perlu di-cancel)
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
    <div className="flex flex-col h-full bg-slate-950">
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">

        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full space-y-6 text-center">
            {/* Hero emblem */}
            <div className="relative">
              <div className="absolute inset-0 blur-2xl rounded-full bg-indigo-500/10" />
              <div className="relative">
                <div className="text-xl font-bold text-slate-200 tracking-tight">Chain Reaction</div>
                <div className="text-[11px] text-slate-500 mt-0.5 tracking-wide">AI Advisor · {instrument} Daily Deploy</div>
              </div>
            </div>
            {/* Quick prompts */}
            <div className="grid grid-cols-2 gap-2 max-w-md w-full">
              {QUICK_PROMPTS.map(qp => (
                <button
                  key={qp.label}
                  onClick={() => { setInput(qp.prompt); textareaRef.current?.focus(); }}
                  className="flex items-start gap-2.5 p-3 bg-slate-900 border border-slate-800/50 rounded-xl text-left hover:bg-slate-800 hover:border-indigo-500/30 transition-all group"
                >
                  <qp.icon className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 mt-0.5 shrink-0 transition-colors" />
                  <span className="text-[11px] text-slate-400 group-hover:text-slate-200 transition-colors">{qp.label}</span>
                </button>
              ))}
            </div>
            <p className="text-[11px] text-slate-600 max-w-xs leading-relaxed">
              Klik ⚡ Sync di panel market untuk update data. AI bisa sync sendiri via tool.
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
                <div className="bg-slate-900 border border-slate-800/50 rounded-2xl rounded-tl-sm px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0ms]" />
                      <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:150ms]" />
                      <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:300ms]" />
                    </div>
                    <span className="text-[11px] text-slate-500">Menganalisis...</span>
                  </div>
                </div>
              </div>
            )}

            {error && !isLoading && (
              <div className="flex justify-start">
                <div className="bg-red-950 border border-red-900/50 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[85%]">
                  <p className="text-xs text-red-400 font-medium mb-1">Gagal mendapat respons</p>
                  <p className="text-[11px] text-red-300/60 leading-relaxed">
                    {error.message?.includes("401")
                      ? modelChoice === "cloud"
                        ? "Bluepack API key error. Cek koneksi internet & API key."
                        : "Qwen3-8B tidak merespons. Pastikan server jalan di port 8080."
                      : error.message ?? "Cek server log untuk detail."}
                  </p>
                  <button onClick={() => handleSend()} className="mt-2 text-[11px] text-red-400 hover:text-red-300 underline">
                    Coba lagi
                  </button>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar — glass morphism ─────────────────────────────────────── */}
      <div className="border-t border-slate-800/50 px-4 py-3 bg-slate-950">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.pdf,.txt,.csv,.json"
          multiple
          className="hidden"
          onChange={e => handleAttach(e.target.files)}
        />

        {/* Attachment preview strip */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2.5">
            {attachments.map((att, i) => (
              <div key={i} className="relative group flex items-center gap-1.5 bg-slate-800 border border-slate-700/50 rounded-xl px-2.5 py-1.5 text-[11px] text-slate-300 max-w-[160px]">
                {att.kind === "image"
                  ? <img src={att.url} alt={att.name} className="w-8 h-8 rounded-lg object-cover shrink-0" />
                  : <FileTextIcon className="w-4 h-4 text-indigo-400 shrink-0" />
                }
                <span className="truncate text-[10px]">{att.name}</span>
                <button
                  onClick={() => setAttachments(prev => prev.filter((_, j) => j !== i))}
                  className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-slate-600 hover:bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"
                >
                  <XIcon className="w-2.5 h-2.5 text-white" />
                </button>
              </div>
            ))}
          </div>
        )}
        {/* Model selector — LOCAL / GROQ / CLOUD */}
        <div className="flex items-center gap-1.5 mb-2.5">
          <button
            onClick={() => setModelChoice("local")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono tracking-wider border transition-all",
              modelChoice === "local"
                ? "bg-slate-800/60 border-slate-600/50 text-slate-200"
                : "bg-transparent border-slate-800/40 text-slate-600 hover:text-slate-400 hover:border-slate-700/50"
            )}
          >
            <CpuIcon className="w-3 h-3" />
            LOCAL
          </button>

          <button
            onClick={() => setModelChoice("cloud")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono tracking-wider border transition-all",
              modelChoice === "cloud"
                ? "bg-indigo-950/50 border-indigo-500/30 text-indigo-300"
                : "bg-transparent border-slate-800/40 text-slate-600 hover:text-slate-400 hover:border-slate-700/50"
            )}
          >
            <CloudIcon className="w-3 h-3" />
            DADANG
          </button>

          {/* System Access toggle — OWNER ONLY. Gate tool sakti (shell/file/browser). */}
          {isOwner && (
            <button
              onClick={() => setSystemAccess(v => !v)}
              title="System Access — izinkan AI pakai tool sistem (shell/file/browser/settings). Owner only. Default OFF demi keamanan."
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono tracking-wider border transition-all",
                systemAccess
                  ? "bg-rose-950/50 border-rose-500/40 text-rose-300 shadow-[0_0_10px_-2px_rgba(244,63,94,0.4)]"
                  : "bg-transparent border-slate-800/40 text-slate-600 hover:text-slate-400 hover:border-slate-700/50"
              )}
            >
              <ShieldCheckIcon className="w-3 h-3" />
              {systemAccess ? "SYS ON" : "SYS OFF"}
            </button>
          )}
          <div className="flex-1" />
          <span className="text-[9px] text-slate-600 font-mono">
            {modelChoice === "cloud" ? "sonnet · premium" : "gemma4 · local"}
          </span>
        </div>

        <div className="flex gap-2 items-end">
          {/* Attach button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className={cn(
              "h-11 w-11 rounded-xl border flex items-center justify-center transition-all shrink-0",
              uploading
                ? "bg-indigo-950/50 border-indigo-500/30 text-indigo-400 animate-pulse"
                : "bg-slate-900 border-slate-800/60 text-slate-500 hover:text-indigo-400 hover:border-indigo-500/40"
            )}
            title="Lampirkan gambar / file"
          >
            {uploading ? <ImageIcon className="w-4 h-4" /> : <PaperclipIcon className="w-4 h-4" />}
          </button>
          <div className="flex-1">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              onPaste={handlePaste}
              placeholder="Tanya setup, storyline, atau ngobrol biasa... (Ctrl+V untuk paste gambar)"
              rows={1}
              className="bg-slate-900 border-slate-800/60 text-slate-100 placeholder:text-slate-600 resize-none min-h-[44px] max-h-40 text-sm focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 rounded-xl"
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
                ? "bg-red-500/80 border-red-500/50 text-white animate-pulse"
                : "bg-slate-900 border-slate-800/60 text-slate-500 hover:text-slate-300 hover:border-slate-600"
            )}
          >
            <MicIcon className="w-4 h-4" />
          </button>
          {isLoading ? (
            <button onClick={() => stop()} className="h-11 w-11 bg-red-500/80 hover:bg-red-500 border border-red-500/30 rounded-xl flex items-center justify-center shrink-0 transition-colors">
              <SquareIcon className="w-4 h-4 text-white" />
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() && attachments.length === 0}
              className="h-11 w-11 bg-indigo-500 hover:bg-indigo-400 text-white rounded-xl flex items-center justify-center shrink-0 disabled:opacity-20 transition-colors shadow-lg shadow-indigo-500/20"
            >
              <SendIcon className="w-4 h-4" />
            </button>
          )}
        </div>
        <p className="text-center text-[10px] text-slate-700 mt-2">
          Chain Reaction · {modelChoice === "cloud" ? "Dadang · Cloud API" : "Qwen3 · Local"} · Memori persisten
        </p>
      </div>
    </div>
  );
}
