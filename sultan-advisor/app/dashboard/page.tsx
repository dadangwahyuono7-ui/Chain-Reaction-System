"use client";

import React, { useState, useEffect } from "react";
import { useSession, signOut } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { ChatInterface } from "@/components/chat-interface";
import { SessionSidebar } from "@/components/session-sidebar";
import { MarketPanel } from "@/components/market-panel";
import { StatusBar } from "@/components/status-bar";
import { LogoSidebar } from "@/components/logo";
import { TeamChat } from "@/components/team-chat";
import dynamic from "next/dynamic";
import { LogOutIcon, PanelLeftIcon, ZapIcon, PlusIcon, UsersIcon, BookOpenIcon, BarChart2Icon } from "lucide-react";

// WebGL bg di-load client-only (hindari SSR mismatch + nggak blok first paint)
const ThreeBg = dynamic(() => import("@/components/three-bg").then(m => m.ThreeBg), { ssr: false });
const Chain3DLive = dynamic(() => import("@/components/chain-3d").then(m => m.Chain3DLive), { ssr: false });
import { TiltCard } from "@/components/tilt-card";
import { CursorGlow } from "@/components/cursor-glow";

const ADMIN_EMAIL = "dadangwahyuono@gmail.com";
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
  const [currentPrice,      setCurrentPrice]      = useState<string | undefined>();
  const [activeInstrument,  setActiveInstrument]  = useState("XAUUSD");
  const [autoPrompt,        setAutoPrompt]        = useState<string | null>(null);
  const [newSessionKey, setNewSessionKey] = useState(0);

  useEffect(() => {
    if (!selectedId) { setSelectedTitle(undefined); return; }
    fetch("/api/sessions")
      .then(r => r.json())
      .then((list: Session[]) => {
        setSessions(list);
        setSelectedTitle(list.find(s => s.id === selectedId)?.title);
      });
  }, [selectedId]);

  const redirectingRef = React.useRef(false);

  useEffect(() => {
    if (isPending) return;
    if (!session && !redirectingRef.current) {
      redirectingRef.current = true;
      router.replace("/login");
    }
  }, [isPending, session, router]);

  // Timeout fallback: kalau isPending > 5 detik DAN masih belum ada session, paksa ke login
  useEffect(() => {
    const t = setTimeout(() => {
      if (!session && !redirectingRef.current) {
        redirectingRef.current = true;
        router.replace("/login");
      }
    }, 5000);
    return () => clearTimeout(t);
  }, [session, router]);

  if (isPending || !session) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-amber-500/70 text-xs tracking-widest">LOADING...</div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-transparent text-slate-100 overflow-hidden">

      {/* ── WebGL 3D wireframe background + cursor glow ────────── */}
      <ThreeBg />
      <CursorGlow />

      {/* ── WATERMARK ─────────────────────────────────────────── */}
      <div
        className="fixed inset-0 pointer-events-none select-none z-50 overflow-hidden"
        aria-hidden="true"
      >
        <div className="absolute inset-0" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='360' height='210'%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='12' font-weight='600' fill='rgba(148,163,184,0.028)' transform='rotate(-30,180,105)'%3EChainReaction · Dadang Wahyuono%3C/text%3E%3C/svg%3E")`,
          backgroundRepeat: "repeat",
          backgroundSize: "360px 210px",
        }} />
      </div>

      {/* ── Mobile overlay ────────────────────────────────────── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-20 xl:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ════════════════════════════════════════════════════════
          LEFT — Session Sidebar
      ════════════════════════════════════════════════════════ */}
      <div className={cn(
        "flex flex-col border-r border-slate-800/60 bg-slate-950 transition-all duration-200 shrink-0 z-30",
        "fixed xl:relative h-full",
        sidebarOpen ? "w-48 2xl:w-60 left-0" : "w-0 -left-48 xl:left-0 overflow-hidden"
      )}>
        <div className="px-3 py-3.5 border-b border-slate-800/60 shrink-0">
          <LogoSidebar />
        </div>
        <div className="px-2 pt-2 shrink-0">
          <button
            onClick={() => { setNewSessionKey(k => k + 1); setSelectedId(null); setSelectedTitle(undefined); }}
            className="w-full flex items-center gap-2 px-3 py-2 xl:py-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] xl:text-[13px] text-slate-400 hover:border-indigo-600/60 hover:text-indigo-300 transition-all"
          >
            <PlusIcon className="w-3 h-3 shrink-0" />
            <span>Sesi Baru</span>
          </button>
        </div>
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
        <div className="border-t border-slate-800/60 px-2 py-2.5 shrink-0 space-y-1.5">
          <button
            onClick={() => router.push("/paper-trading")}
            className="flex items-center gap-2 text-[11px] xl:text-[13px] text-emerald-500 hover:text-emerald-300 hover:bg-emerald-500/10 transition-all w-full px-1 py-1 rounded-lg border border-transparent hover:border-emerald-500/20"
          >
            <BarChart2Icon className="w-3.5 h-3.5 xl:w-4 xl:h-4 shrink-0" />
            <span>Paper Trading</span>
          </button>
          <button
            onClick={() => router.push("/journal")}
            className="flex items-center gap-2 text-[11px] xl:text-[13px] text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 transition-all w-full px-1 py-1 rounded-lg border border-transparent hover:border-indigo-500/20"
          >
            <BookOpenIcon className="w-3.5 h-3.5 xl:w-4 xl:h-4 shrink-0" />
            <span>Journal</span>
          </button>
          {session.user.email === ADMIN_EMAIL && (
            <button
              onClick={() => router.push("/admin")}
              className="flex items-center gap-2 text-[11px] xl:text-[13px] text-purple-400 hover:text-purple-300 hover:bg-purple-500/10 transition-all w-full px-1 py-1 rounded-lg border border-transparent hover:border-purple-500/20"
            >
              <UsersIcon className="w-3.5 h-3.5 xl:w-4 xl:h-4 shrink-0" />
              <span>Kelola Users</span>
            </button>
          )}
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

      {/* ════════════════════════════════════════════════════════
          CENTER — Market Intelligence Dashboard
      ════════════════════════════════════════════════════════ */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-slate-800/60">

        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-slate-800/60 shrink-0 bg-slate-950/80 backdrop-blur-sm">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-zinc-500 hover:text-zinc-300 transition-colors p-1 rounded-lg hover:bg-zinc-800 shrink-0"
          >
            <PanelLeftIcon className="w-4 h-4" />
          </button>
          <span className="text-[10px] xl:text-xs text-slate-500 tracking-wide">
            Market Intelligence · {activeInstrument} Daily Deploy
          </span>
          <div className="flex-1" />
          <div className="flex items-center gap-1.5 px-2.5 py-1 xl:px-3 xl:py-1.5 rounded-lg bg-slate-900/70 border border-slate-800 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500/80" />
            <span className="text-[10px] xl:text-xs font-semibold text-slate-400 tracking-wide">Dadang Wahyuono</span>
            <span className="text-[9px] xl:text-[11px] text-slate-600">· Private</span>
          </div>
        </div>

        {/* Dashboard scroll area */}
        <div className="flex-1 overflow-y-auto">
          {/* 3D CMP→VR→CF chain (live H4) */}
          <div className="p-3 pb-0">
            <TiltCard className="p-3" intensity={5}>
              <Chain3DLive tf="H4" />
            </TiltCard>
          </div>
          <MarketPanel
            onAutoAnalysis={(prompt) => setAutoPrompt(prompt)}
            onPriceUpdate={(price) => setCurrentPrice(price)}
            onInstrumentUpdate={(sym) => setActiveInstrument(sym)}
            layout="dashboard"
          />
        </div>
      </div>

      {/* ════════════════════════════════════════════════════════
          RIGHT — AI Advisor Chat Panel
      ════════════════════════════════════════════════════════ */}
      <div className="w-[380px] xl:w-[460px] 2xl:w-[520px] flex flex-col shrink-0 bg-slate-950 relative z-10">

        {/* Chat header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800/60 shrink-0 bg-slate-950">
          <div className="flex items-center gap-2">
            <ZapIcon className="w-3.5 h-3.5 xl:w-4 xl:h-4 text-indigo-400" />
            <span className="text-xs xl:text-sm font-semibold text-slate-200 tracking-tight">AI Advisor</span>
            {selectedTitle && selectedTitle !== "Sesi Baru" && (
              <span className="text-[10px] xl:text-xs text-slate-500 truncate max-w-[140px] xl:max-w-[200px]">· {selectedTitle}</span>
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


      {/* ── Team Chat (floating) ──────────────────────────────── */}
      <TeamChat />

    </div>
  );
}