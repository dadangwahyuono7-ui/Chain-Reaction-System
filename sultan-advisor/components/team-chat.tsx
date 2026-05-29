"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState, useCallback } from "react";
import { useSession } from "@/lib/auth-client";
import { MessagesSquareIcon, SendIcon, XIcon, VideoIcon, UsersIcon, MicIcon, ImageIcon, Loader2Icon } from "lucide-react";
import { cn } from "@/lib/utils";

type ChatMessage = {
  id: string;
  userId: string;
  userName: string;
  text: string;
  imageUrl?: string | null;
  createdAt: number;
};

// Kompres gambar di browser (resize + JPEG) biar upload ringan & cepat
async function compressImage(file: File, maxDim = 1600, quality = 0.82): Promise<Blob> {
  try {
    const img = await createImageBitmap(file);
    let { width, height } = img;
    if (width > maxDim || height > maxDim) {
      const scale = Math.min(maxDim / width, maxDim / height);
      width = Math.round(width * scale);
      height = Math.round(height * scale);
    }
    const canvas = document.createElement("canvas");
    canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(img, 0, 0, width, height);
    const blob: Blob | null = await new Promise((res) => canvas.toBlob(res, "image/jpeg", quality));
    return blob ?? file;
  } catch {
    return file; // fallback: kirim original
  }
}

// Room Jitsi — string panjang & gak gampang ditebak = berfungsi sbg "password"
const JITSI_ROOM = "SultanAdvisorTeam-035ea0552ced4d2da4d0";

function loadJitsiScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if ((window as any).JitsiMeetExternalAPI) return resolve();
    const s = document.createElement("script");
    s.src = "https://meet.jit.si/external_api.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Gagal memuat Jitsi"));
    document.body.appendChild(s);
  });
}

function fmtTime(ms: number): string {
  return new Date(ms).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}

export function TeamChat() {
  const { data: session } = useSession();
  const myId   = session?.user?.id ?? "";
  const myName = session?.user?.name || session?.user?.email?.split("@")[0] || "Saya";

  const [open, setOpen]         = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [online, setOnline]     = useState<string[]>([]);
  const [input, setInput]       = useState("");
  const [unread, setUnread]     = useState(0);
  const [connected, setConnected] = useState(false);

  const [meetingOpen, setMeetingOpen] = useState(false);
  const jitsiBoxRef = useRef<HTMLDivElement>(null);
  const jitsiApiRef = useRef<any>(null);

  // Pending image (screenshot/gambar yang siap dikirim)
  const [pendingBlob, setPendingBlob]       = useState<Blob | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const [uploading, setUploading]           = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [lightbox, setLightbox]             = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const seenIds   = useRef<Set<string>>(new Set());
  const openRef   = useRef(open);
  useEffect(() => { openRef.current = open; }, [open]);

  // ── Load history sekali ────────────────────────────────────────────────
  useEffect(() => {
    if (!session) return;
    fetch("/api/team-chat")
      .then(r => r.json())
      .then((d: { messages: ChatMessage[] }) => {
        if (!d.messages) return;
        d.messages.forEach(m => seenIds.current.add(m.id));
        setMessages(d.messages);
      })
      .catch(() => {});
  }, [session]);

  // ── SSE realtime: pesan baru + presence ────────────────────────────────
  useEffect(() => {
    if (!session) return;
    const es = new EventSource("/api/team-chat/stream");
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "presence") {
          setOnline(data.online ?? []);
        } else if (data.type === "message" && data.message) {
          const m: ChatMessage = data.message;
          if (seenIds.current.has(m.id)) return;
          seenIds.current.add(m.id);
          setMessages(prev => [...prev, m]);
          // unread badge kalau panel ketutup & pesan dari orang lain
          if (!openRef.current && m.userId !== myId) setUnread(u => u + 1);
        }
      } catch { /* ignore */ }
    };
    return () => es.close();
  }, [session, myId]);

  // ── Auto scroll ke bawah ───────────────────────────────────────────────
  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  // ── Reset unread saat panel dibuka ─────────────────────────────────────
  useEffect(() => { if (open) setUnread(0); }, [open]);

  // Set gambar pending (dari paste atau pilih file)
  const stageImage = useCallback(async (file: File) => {
    if (!file.type.startsWith("image/")) return;
    const blob = await compressImage(file);
    setPendingBlob(blob);
    setPendingPreview(prev => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob); });
  }, []);

  const clearPending = useCallback(() => {
    setPendingPreview(prev => { if (prev) URL.revokeObjectURL(prev); return null; });
    setPendingBlob(null);
  }, []);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text && !pendingBlob) return;
    setInput("");
    let imageUrl: string | null = null;
    try {
      if (pendingBlob) {
        setUploading(true);
        const fd = new FormData();
        fd.append("file", pendingBlob, "screenshot.jpg");
        const up = await fetch("/api/team-chat/upload", { method: "POST", body: fd });
        const j = await up.json();
        imageUrl = j.url ?? null;
        clearPending();
        setUploading(false);
      }
      await fetch("/api/team-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, imageUrl }),
      });
      // pesan masuk balik via SSE (dedup id)
    } catch { setUploading(false); }
  }, [input, pendingBlob, clearPending]);

  // Paste screenshot (Ctrl+V) di area chat
  const onPaste = useCallback((e: React.ClipboardEvent) => {
    const item = Array.from(e.clipboardData.items).find(i => i.type.startsWith("image/"));
    if (item) {
      const file = item.getAsFile();
      if (file) { e.preventDefault(); void stageImage(file); }
    }
  }, [stageImage]);

  // ── Jitsi meeting lifecycle ────────────────────────────────────────────
  useEffect(() => {
    if (!meetingOpen) return;
    let disposed = false;
    (async () => {
      try {
        await loadJitsiScript();
        if (disposed || !jitsiBoxRef.current) return;
        jitsiBoxRef.current.innerHTML = "";
        jitsiApiRef.current = new (window as any).JitsiMeetExternalAPI("meet.jit.si", {
          roomName: JITSI_ROOM,
          parentNode: jitsiBoxRef.current,
          width: "100%",
          height: "100%",
          userInfo: { displayName: myName },
          configOverwrite: {
            startWithVideoMuted: true,   // voice-first
            startWithAudioMuted: false,
            prejoinPageEnabled: false,
            disableDeepLinking: true,
            // Tombol toolbar — 'desktop' = SHARE SCREEN (eksplisit biar selalu kelihatan)
            toolbarButtons: [
              "microphone", "camera", "desktop", "tileview", "chat",
              "raisehand", "fullscreen", "settings", "videoquality", "hangup",
            ],
          },
          interfaceConfigOverwrite: {
            MOBILE_APP_PROMO: false,
            SHOW_JITSI_WATERMARK: false,
            TOOLBAR_BUTTONS: [
              "microphone", "camera", "desktop", "tileview", "chat",
              "raisehand", "fullscreen", "settings", "videoquality", "hangup",
            ],
          },
        });
        jitsiApiRef.current.addEventListener("readyToClose", () => setMeetingOpen(false));
      } catch { /* ignore */ }
    })();
    return () => {
      disposed = true;
      try { jitsiApiRef.current?.dispose(); } catch { /* ignore */ }
      jitsiApiRef.current = null;
    };
  }, [meetingOpen, myName]);

  if (!session) return null;

  return (
    <>
      {/* ── Floating toggle button ─────────────────────────────────────── */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-5 right-5 z-[60] h-14 w-14 rounded-full bg-amber-500 hover:bg-amber-400 text-black shadow-lg shadow-amber-900/40 flex items-center justify-center transition-all"
          title="Team Chat"
        >
          <MessagesSquareIcon className="w-6 h-6" />
          {unread > 0 && (
            <span className="absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full bg-red-600 text-white text-[11px] font-bold flex items-center justify-center border-2 border-zinc-950">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
          {online.length > 0 && (
            <span className="absolute -bottom-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-emerald-500 text-black text-[9px] font-bold flex items-center justify-center border-2 border-zinc-950">
              {online.length}
            </span>
          )}
        </button>
      )}

      {/* ── Chat panel ─────────────────────────────────────────────────── */}
      {open && (
        <div className="fixed bottom-5 right-5 z-[60] w-[340px] sm:w-[380px] h-[520px] max-h-[80vh] flex flex-col bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl shadow-black/60 overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2 px-3 py-2.5 border-b border-zinc-800 bg-zinc-900/60 shrink-0">
            <MessagesSquareIcon className="w-4 h-4 text-amber-500" />
            <span className="text-xs font-black text-amber-500 tracking-tighter">TEAM CHAT</span>
            <span className={cn("w-1.5 h-1.5 rounded-full", connected ? "bg-emerald-500" : "bg-zinc-600")} title={connected ? "Tersambung" : "Terputus"} />
            <div className="flex-1" />
            <button
              onClick={() => setMeetingOpen(true)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-600/15 border border-emerald-700/40 text-emerald-400 hover:bg-emerald-600/25 text-[10px] font-bold transition-all"
              title="Mulai voice meeting"
            >
              <VideoIcon className="w-3 h-3" /> Meeting
            </button>
            <button onClick={() => setOpen(false)} className="text-zinc-500 hover:text-zinc-300 p-1">
              <XIcon className="w-4 h-4" />
            </button>
          </div>

          {/* Online bar */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-zinc-800/60 bg-zinc-900/30 shrink-0">
            <UsersIcon className="w-3 h-3 text-emerald-500 shrink-0" />
            <span className="text-[10px] text-zinc-500 shrink-0">Online:</span>
            <div className="flex gap-1 flex-wrap overflow-hidden">
              {online.length === 0
                ? <span className="text-[10px] text-zinc-600">—</span>
                : online.map(u => (
                    <span key={u} className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/40 text-emerald-400 border border-emerald-800/40">
                      {u}{u === myName ? " (kamu)" : ""}
                    </span>
                  ))}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
            {messages.length === 0 ? (
              <div className="h-full flex items-center justify-center text-center px-4">
                <p className="text-[11px] text-zinc-600">Belum ada pesan. Mulai obrolan tim di sini — semua yang buka dashboard bisa lihat real-time.</p>
              </div>
            ) : messages.map(m => {
              const mine = m.userId === myId;
              return (
                <div key={m.id} className={cn("flex flex-col", mine ? "items-end" : "items-start")}>
                  {!mine && <span className="text-[9px] text-amber-600/80 font-mono mb-0.5 px-1">{m.userName}</span>}
                  {m.imageUrl && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={m.imageUrl}
                      alt="screenshot"
                      onClick={() => setLightbox(m.imageUrl!)}
                      className="max-w-[80%] max-h-52 rounded-xl border border-zinc-700 mb-1 cursor-zoom-in object-contain bg-zinc-900"
                    />
                  )}
                  {m.text && (
                    <div className={cn(
                      "max-w-[80%] px-2.5 py-1.5 rounded-2xl text-[12px] break-words whitespace-pre-wrap",
                      mine ? "bg-amber-500 text-black rounded-tr-sm" : "bg-zinc-800 text-zinc-100 rounded-tl-sm"
                    )}>
                      {m.text}
                    </div>
                  )}
                  <span className="text-[8px] text-zinc-600 mt-0.5 px-1">{fmtTime(m.createdAt)}</span>
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>

          {/* Pending image preview */}
          {pendingPreview && (
            <div className="px-3 pt-2 shrink-0">
              <div className="relative inline-block">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={pendingPreview} alt="preview" className="max-h-24 rounded-lg border border-zinc-700" />
                <button
                  onClick={clearPending}
                  className="absolute -top-2 -right-2 h-5 w-5 rounded-full bg-red-600 text-white flex items-center justify-center border-2 border-zinc-950"
                >
                  <XIcon className="w-3 h-3" />
                </button>
                <span className="absolute bottom-1 left-1 text-[8px] bg-black/60 text-white px-1 rounded">siap dikirim</span>
              </div>
            </div>
          )}

          {/* Input */}
          <div className="flex items-end gap-2 px-3 py-2.5 border-t border-zinc-800 bg-zinc-900/40 shrink-0">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) void stageImage(f); e.target.value = ""; }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="h-9 w-9 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 flex items-center justify-center shrink-0 transition-colors"
              title="Lampirkan gambar/screenshot"
            >
              <ImageIcon className="w-4 h-4" />
            </button>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onPaste={onPaste}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder="Ketik pesan / paste screenshot (Ctrl+V)..."
              rows={1}
              className="flex-1 resize-none bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-[12px] text-white placeholder:text-zinc-600 focus:border-amber-700 outline-none max-h-24"
            />
            <button
              onClick={send}
              disabled={(!input.trim() && !pendingBlob) || uploading}
              className="h-9 w-9 rounded-xl bg-amber-500 hover:bg-amber-400 text-black flex items-center justify-center shrink-0 disabled:opacity-30 transition-colors"
            >
              {uploading ? <Loader2Icon className="w-4 h-4 animate-spin" /> : <SendIcon className="w-4 h-4" />}
            </button>
          </div>
        </div>
      )}

      {/* ── Lightbox gambar ────────────────────────────────────────────── */}
      {lightbox && (
        <div
          className="fixed inset-0 z-[80] bg-black/90 flex items-center justify-center p-4"
          onClick={() => setLightbox(null)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={lightbox} alt="full" className="max-w-full max-h-full object-contain rounded-lg" />
          <button className="absolute top-4 right-4 h-10 w-10 rounded-full bg-zinc-800 text-white flex items-center justify-center">
            <XIcon className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* ── Meeting modal (Jitsi) ──────────────────────────────────────── */}
      {meetingOpen && (
        <div className="fixed inset-0 z-[70] bg-black/80 backdrop-blur-sm flex flex-col">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-zinc-950 border-b border-zinc-800 shrink-0">
            <MicIcon className="w-4 h-4 text-emerald-500" />
            <span className="text-sm font-black text-emerald-400 tracking-tighter">TEAM MEETING</span>
            <span className="text-[10px] text-zinc-600">· voice/video · screen share</span>
            <div className="flex-1" />
            <button
              onClick={() => setMeetingOpen(false)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-all"
            >
              <XIcon className="w-3.5 h-3.5" /> Tutup Meeting
            </button>
          </div>
          <div ref={jitsiBoxRef} className="flex-1 bg-zinc-900" />
        </div>
      )}
    </>
  );
}
