"use client";

import { useState, useEffect } from "react";
import { useSession, signOut } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { ChatInterface } from "@/components/chat-interface";
import { SessionSidebar } from "@/components/session-sidebar";
import { MarketPanel } from "@/components/market-panel";
import { StatusBar } from "@/components/status-bar";
import { LogoSidebar } from "@/components/logo";
import { LogOutIcon, PanelLeftIcon, ZapIcon, PlusIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Session = { id: string; title: string };

export default function DashboardPage() {
  const { data: session, isPending } = useSession();
  const router = useRouter();

  const [selectedId,    setSelectedId]    = useState<string | null>(null);
  const [selectedTitle, setSelectedTitle] = useState<string | undefined>();
  const [sessions,      setSessions]      = useState<Session[]>([]);
  const [sidebarOpen,   setSidebarOpen]   = useState(
    typeof window !== "undefined" ? window.innerWidth >= 1280 : true
  );
  const [currentPrice,  setCurrentPrice]  = useState<string | undefined>();
  const [autoPrompt,    setAutoPrompt]    = useState<string | null>(null);
  // Setiap kali "Sesi Baru" diklik, increment ini agar ChatInterface re-mount
  // sehingga useChat hook benar-benar fresh — tidak ada sisa state dari sesi lama
  const [newSessionKey, setNewSessionKey] = useState(0);

  // currentPrice is now fed by MarketPanel's live SSE tick — no polling needed

  useEffect(() => {
    if (!selectedId) { setSelectedTitle(undefined); return; }
    fetch("/api/sessions")
      .then(r => r.json())
      .then((list: Session[]) => {
        setSessions(list);
        setSelectedTitle(list.find(s => s.id === selectedId)?.title);
      });
  }, [selectedId]);

  if (isPending) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-amber-500/70 text-xs tracking-widest">LOADING...</div>
      </div>
    </div>
  );

  if (!session) { router.push("/login"); return null; }

  return (
    <div className="flex h-screen bg-zinc-950 text-white overflow-hidden">

      {/* ── WATERMARK — Dadang Wahyuono ───────────────────────────────── */}
      <div
        className="fixed inset-0 pointer-events-none select-none z-50 overflow-hidden"
        aria-hidden="true"
      >
        <div className="absolute inset-0" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='340' height='200'%3E%3Ctext x='50%25' y='45%25' dominant-baseline='middle' text-anchor='middle' font-family='monospace' font-size='13' font-weight='bold' fill='rgba(245,158,11,0.055)' transform='rotate(-30,170,100)'%3EDADANG WAHYUONO%3C/text%3E%3Ctext x='50%25' y='72%25' dominant-baseline='middle' text-anchor='middle' font-family='monospace' font-size='9' fill='rgba(245,158,11,0.04)' transform='rotate(-30,170,100)'%3ECHAIN REACTION v4.0 · PRIVATE%3C/text%3E%3C/svg%3E")`,
          backgroundRepeat: "repeat",
          backgroundSize: "340px 200px",
        }} />
      </div>

      {/* ── Mobile overlay ────────────────────────────────────────────── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-20 xl:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ══════════════════════════════════════════════════════════════
          LEFT — Session Sidebar (narrow)
      ══════════════════════════════════════════════════════════════ */}
      <div className={cn(
        "flex flex-col border-r border-zinc-800/60 bg-zinc-950 transition-all duration-200 shrink-0 z-30",
        "fixed xl:relative h-full",
        sidebarOpen ? "w-48 2xl:w-60 left-0" : "w-0 -left-48 xl:left-0 overflow-hidden"
      )}>
        {/* Logo */}
        <div className="px-3 py-3.5 border-b border-zinc-800/60 shrink-0">
          <LogoSidebar />
        </div>

        {/* New session button */}
        <div className="px-2 pt-2 shrink-0">
          <button
            onClick={() => { setNewSessionKey(k => k + 1); setSelectedId(null); setSelectedTitle(undefined); }}
            className="w-full flex items-center gap-2 px-3 py-2 xl:py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-[11px] xl:text-[13px] text-zinc-400 hover:border-amber-700/60 hover:text-amber-400 transition-all"
          >
            <PlusIcon className="w-3 h-3 shrink-0" />
            <span>Sesi Baru</span>
          </button>
        </div>

        {/* Sessions list */}
        <div className="flex-1 py-2 overflow-hidden">
          <SessionSidebar
            currentId={selectedId}
            onSelect={(id) => {
              setSelectedId(id);
              setSelectedTitle(sessions.find(s => s.id === id)?.title);
            }}
            onNew={() => { setNewSessionKey(k => k + 1); setSelectedId(null); setSelectedTitle(undefined); }}
          />
        </div>

        {/* Footer */}
        <div className="border-t border-zinc-800/60 px-2 py-2.5 shrink-0 space-y-1.5">
          <button
            onClick={() => { signOut(); router.push("/login"); }}
            className="flex items-center gap-2 text-[11px] xl:text-[13px] text-zinc-500 hover:text-zinc-300 transition-colors w-full px-1"
          >
            <LogOutIcon className="w-3.5 h-3.5 xl:w-4 xl:h-4 shrink-0" />
            Keluar
          </button>
          <div className="text-[9px] xl:text-[11px] text-zinc-700 truncate font-mono px-1">
            {session.user.email}
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════
          CENTER — Market Intelligence Dashboard
      ══════════════════════════════════════════════════════════════ */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-zinc-800/60">

        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-zinc-800/60 shrink-0 bg-zinc-950/90 backdrop-blur-sm">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-zinc-500 hover:text-zinc-300 transition-colors p-1 rounded-lg hover:bg-zinc-800 shrink-0"
          >
            <PanelLeftIcon className="w-4 h-4" />
          </button>
          <span className="text-[10px] xl:text-xs text-zinc-600 uppercase tracking-widest">
            Market Intelligence · XAUUSD Daily Deploy
          </span>
          <div className="flex-1" />
          {/* Owner tag — always visible in screenshot */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 xl:px-3 xl:py-1.5 rounded-lg bg-amber-500/8 border border-amber-500/20 shrink-0">
            <span className="text-[9px] xl:text-[11px] text-amber-600 font-mono">©</span>
            <span className="text-[10px] xl:text-xs font-black font-mono text-amber-500/70 tracking-widest">DADANG WAHYUONO</span>
            <span className="text-[9px] xl:text-[11px] text-zinc-700 font-mono">· CHAIN REACTION v4.0 · PRIVATE</span>
          </div>
        </div>

        {/* Dashboard scroll area */}
        <div className="flex-1 overflow-y-auto">
          <MarketPanel
            onAutoAnalysis={(prompt) => setAutoPrompt(prompt)}
            onPriceUpdate={(price) => setCurrentPrice(price)}
            layout="dashboard"
          />
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════
          RIGHT — AI Advisor Chat Panel
      ══════════════════════════════════════════════════════════════ */}
      <div className="w-[380px] xl:w-[460px] 2xl:w-[520px] flex flex-col shrink-0">

        {/* Chat header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800/60 shrink-0 bg-zinc-950/90 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <ZapIcon className="w-3.5 h-3.5 xl:w-4 xl:h-4 text-amber-500" />
            <span className="text-xs xl:text-sm font-black text-amber-500 tracking-tighter">AI ADVISOR</span>
            {selectedTitle && selectedTitle !== "Sesi Baru" && (
              <span className="text-[10px] xl:text-xs text-zinc-600 truncate max-w-[140px] xl:max-w-[200px]">· {selectedTitle}</span>
            )}
          </div>
          <StatusBar price={currentPrice} />
        </div>

        {/* Chat interface */}
        <div className="flex-1 overflow-hidden">
          <ChatInterface
            key={selectedId ?? `new-${newSessionKey}`}
            sessionId={selectedId}
            sessionTitle={selectedTitle}
            onSessionId={(id) => setSelectedId(id)}
            autoPrompt={autoPrompt}
            onAutoPromptConsumed={() => setAutoPrompt(null)}
          />
        </div>
      </div>

    </div>
  );
}
