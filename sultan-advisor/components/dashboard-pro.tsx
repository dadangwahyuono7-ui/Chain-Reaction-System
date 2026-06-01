"use client";

/* ============================================================================
   DASHBOARD PRO — ChainReaction v2 (Clean Institutional)
   ----------------------------------------------------------------------------
   Visual language baru — BUKAN terminal/HUD lama. Fintech 2026:
   - Kartu lega rounded-2xl, border tipis, soft shadow, whitespace banyak
   - Data-viz beneran: grade ring (SVG), pressure gauge, SNR price-ladder, chain rail
   - Warna disiplin: 90% slate netral, indigo=brand/nunggu, emerald/rose=arah,
     amber/kuning HANYA pas actionable (entry valid)
   - Tipografi: angka besar tabular-nums, label kecil muted uppercase
   Semua data DITERIMA via props dari market-panel (logika trading TIDAK diubah).
============================================================================ */

import { cn } from "@/lib/utils";
import { useEffect, useRef, useState } from "react";
import {
  RefreshCwIcon, ArrowUpIcon, ArrowDownIcon, ZapIcon,
  WifiIcon, WifiOffIcon, ClockIcon, TargetIcon, ActivityIcon,
  LayersIcon, GaugeIcon, Volume2Icon, VolumeXIcon, CpuIcon,
} from "lucide-react";
import { LocalModelSwitcher } from "@/components/local-model-switcher";

// ── Tick halus (WebAudio) pas level masuk HOT — beda dari beep entry ──────────
let _ac: AudioContext | null = null;
function snrTick(side: "up" | "dn") {
  try {
    if (typeof window === "undefined") return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    _ac = _ac || new (window.AudioContext || (window as any).webkitAudioContext)();
    if (_ac.state === "suspended") _ac.resume();
    const t = _ac.currentTime;
    const o = _ac.createOscillator();
    const g = _ac.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(side === "up" ? 880 : 660, t); // resistance lebih tinggi
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.06, t + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    o.connect(g); g.connect(_ac.destination);
    o.start(t); o.stop(t + 0.18);
  } catch { /* diam kalau browser blokir audio */ }
}

// ── Types (longgar — cocok dgn yg dihitung di market-panel) ──────────────────
type TFRow = {
  tf: string; cmp: string; vr: string; cf: string;
  cfCount: number; cfType: string; fase: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  sl?: any;
};
type Lvl = { key: string; short: string; price: number; stars: number };

export interface DashboardProProps {
  displayPrice: string;
  livePrice: string;
  priceFlash: "up" | "dn" | null;
  spread: string;
  sess: string;
  tfData: TFRow[];
  h4Dir: string;
  hasTFData: boolean;
  autoGrade: { grade: string; reason: string };
  // pressure
  buyPct: number; sellPct: number; cumDelta: number;
  momentum: string; momentumStr: string;
  barDeltas: number[]; maxBarAbs: number; divergence: boolean; nTicks: number;
  // SNR
  aboveLevels: Lvl[]; belowLevels: Lvl[]; atLevel: Lvl[]; cmpFloat: number;
  tp1Up?: string; tp2Up?: string; tp1Dn?: string; tp2Dn?: string;
  // news
  minutesUntilNews: number | null; newsBlackout: boolean; newsApproaching: boolean;
  nextEventName: string; nextEventTimeWIB: string;
  // sync
  syncTV: () => void; syncing: boolean; tvStatus: string; lastSync: number | null;
  syncSNR: () => void; syncingSNR: boolean;
  syncNews: () => void; syncingNews: boolean;
  autoSync: boolean; setAutoSync: (b: boolean) => void;
  autopilot?: boolean; setAutopilot?: (b: boolean) => void;
  blink: boolean; blinkFast: boolean;
  // active TV symbol (pair)
  tvSymbol?: string; tvSymbolDesc?: string;
}

// ── MOTION SYSTEM: Premium Fintech 2026 ─────────────────────────────────────
const DP_ANIM = `
/* ═══ CORE KEYFRAMES ═══ */
@keyframes dp-flow { from { background-position: 0 0; } to { background-position: 24px 0; } }
@keyframes dp-breathe {
  0%,100% { box-shadow: 0 0 0 0 rgba(99,145,255,0.0); border-color: rgba(99,145,255,0.45); }
  50%     { box-shadow: 0 0 0 6px rgba(99,145,255,0.08), 0 0 20px rgba(99,145,255,0.06); border-color: rgba(99,145,255,0.9); }
}
@keyframes dp-signal {
  0%,100% { box-shadow: 0 0 10px rgba(251,191,36,0.4), inset 0 0 30px rgba(251,191,36,0.03); }
  50%     { box-shadow: 0 0 28px rgba(251,191,36,0.85), 0 0 56px rgba(251,191,36,0.3), inset 0 0 30px rgba(251,191,36,0.06); }
}
@keyframes dp-scan { 0% { transform: translateX(-30%); opacity: 0; } 12% { opacity: .7; } 88% { opacity: .7; } 100% { transform: translateX(560%); opacity: 0; } }
@keyframes dp-grid { from { background-position: 0 0, 0 0; } to { background-position: 32px 32px, 32px 32px; } }
@keyframes dp-slide { from { background-position: 0 0; } to { background-position: 200% 0; } }
@keyframes dp-flicker { 0%,96%,100% { opacity: 1; } 97% { opacity: .85; } 98% { opacity: 1; } 99% { opacity: .92; } }
@keyframes dp-blip { 0% { transform: scale(.6); opacity: .9; } 100% { transform: scale(2.6); opacity: 0; } }
@keyframes dp-approach-glow {
  0%,100% { box-shadow: inset 0 0 0 1px var(--gc-dim), 0 0 0 0 transparent; }
  50%     { box-shadow: inset 0 0 0 1px var(--gc), 0 0 20px -3px var(--gc); }
}
@keyframes dp-approach-sweep { 0% { transform: translateX(-120%); } 100% { transform: translateX(420%); } }
@keyframes dp-bar { 0%,100% { opacity: .45; } 50% { opacity: 1; } }
@keyframes dp-ping-k { 0% { transform: scale(.6); opacity: .85; } 100% { transform: scale(2.6); opacity: 0; } }
/* ═══ PREMIUM: shimmer overlay untuk hero ═══ */
@keyframes dp-shimmer {
  0% { transform: translateX(-100%) rotate(12deg); }
  100% { transform: translateX(200%) rotate(12deg); }
}
/* ═══ PREMIUM: ambient glow pulse di background ═══ */
@keyframes dp-ambient {
  0%,100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(1.05); }
}
/* ═══ PREMIUM: gradient hue rotate untuk border aktif ═══ */
@keyframes dp-hue { from { filter: hue-rotate(0deg); } to { filter: hue-rotate(30deg); } }

/* ═══ CLASS MAPPINGS ═══ */
/* heartbeat sweep — blip cahaya nyapu kiri→kanan kayak monitor jantung */
@keyframes dp-hb { from { background-position: 140% 0; } to { background-position: -40% 0; } }
.dp-stream      {
  background-color: rgba(148,163,184,0.10);
  background-image: linear-gradient(90deg, transparent 0%, transparent 38%, var(--c) 47%, #fff 50%, var(--c) 53%, transparent 62%, transparent 100%);
  background-size: 220% 100%;
  background-repeat: no-repeat;
  box-shadow: 0 0 6px -1px var(--c);
  animation: dp-hb 1.15s linear infinite;
}
.dp-breathe     { animation: dp-breathe 3s ease-in-out infinite; }
.dp-signal      { animation: dp-signal .85s ease-in-out infinite; }
/* lingkaran step = koin 3D muter pelan */
@keyframes dp-coin { 0%,100% { transform: rotateY(-24deg); } 50% { transform: rotateY(24deg); } }
.dp-coin        { animation: dp-coin 4.5s ease-in-out infinite; transform-style: preserve-3d; }
/* CF aktif & belum flip = pulse terus (denyut entry hidup) */
@keyframes dp-cf-pulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(251,191,36,0.45); transform: scale(1); }
  50%     { box-shadow: 0 0 15px 4px rgba(251,191,36,0.6); transform: scale(1.15); }
}
.dp-cf-pulse    { animation: dp-cf-pulse 0.95s ease-in-out infinite; }
.dp-coin:nth-child(odd) { animation-delay: -2s; }
/* baris/kartu = miring 3D pas hover (kayak diangkat & diputar) */
.dp-row3d       { transition: transform .45s cubic-bezier(.22,.61,.36,1), box-shadow .4s ease; transform-style: preserve-3d; }
.dp-row3d:hover { transform: perspective(900px) rotateX(4deg) translateY(-3px) scale(1.012); box-shadow: 0 14px 36px -14px rgba(99,102,241,0.34); z-index: 10; }
/* ═══ ELEGAN 3D MENYELURUH ═══ */
/* depth halus cuma di teks BESAR — teks kecil dibiarin crisp biar jelas */
.dp-xl          { text-shadow: 0 1px 3px rgba(0,0,0,.5); }
.dp-h           { text-shadow: 0 1px 2px rgba(0,0,0,.45); }
/* tombol = timbul, mencet pas diklik (tactile 3D) */
.dp-scope button { transition: transform .12s ease, box-shadow .2s ease, filter .2s ease; }
.dp-scope button:hover  { transform: translateY(-1px); filter: brightness(1.08); }
.dp-scope button:active { transform: translateY(1px) scale(.985); }
/* badge/pill kecil = sedikit timbul */
.dp-scope [class*="rounded-md"], .dp-scope [class*="rounded-lg"] { box-shadow: inset 0 1px 0 rgba(255,255,255,.05); }
.dp-grid        { background-image: linear-gradient(rgba(99,145,255,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(99,145,255,.04) 1px, transparent 1px); background-size: 32px 32px; animation: dp-grid 8s linear infinite; }
.dp-flicker     { animation: dp-flicker 4s steps(1) infinite; }
.dp-bar         { animation: dp-bar 1.4s ease-in-out infinite; }
.dp-approach    { animation: dp-approach-glow 1.6s ease-in-out infinite; }
.dp-approach-hot { animation: dp-approach-glow .8s ease-in-out infinite; }
.dp-sweep       { position:absolute; top:0; bottom:0; width:40px; pointer-events:none;
                  background: linear-gradient(90deg, transparent, var(--gc), transparent);
                  opacity:.3; animation: dp-approach-sweep 1.8s ease-in-out infinite; }
.dp-scanline    { position: absolute; top: 0; bottom: 0; width: 120px; pointer-events: none;
                  background: linear-gradient(90deg, transparent, rgba(99,145,255,0.07), transparent);
                  animation: dp-scan 6s ease-in-out infinite; }
.dp-ping { animation: dp-ping-k 1.1s ease-out infinite; }
.dp-border-go::before {
  content: ''; position: absolute; inset: 0; border-radius: 1rem; padding: 1.5px;
  background: linear-gradient(90deg, #fbbf24, #f59e0b, #fbbf24, #ef4444, #fbbf24); background-size: 200% 100%;
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude; animation: dp-slide 1.8s linear infinite; pointer-events: none;
}
/* hero shimmer */
.dp-shimmer::after {
  content: ''; position: absolute; inset: -50%; width: 50%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent);
  animation: dp-shimmer 4s ease-in-out infinite; pointer-events: none;
}

/* ═══ DESIGN TOKENS ═══ */
.dp-scope {
  --dp-sh-1: 0 1px 0 0 rgba(255,255,255,.03) inset, 0 8px 32px -16px rgba(0,0,0,.7);
  --dp-sh-2: 0 1px 0 0 rgba(255,255,255,.05) inset, 0 20px 60px -20px rgba(0,0,0,.85);
  --dp-sh-glow: 0 0 40px -12px;
  --dp-glass: rgba(15,23,42,0.72);
  --dp-glass-border: rgba(148,163,184,0.08);
  perspective: 2000px;
  transform-style: preserve-3d;
}
/* ═══ TYPE SCALE — optimised for 27" monitor ═══ */
.dp-micro { font-size: 11px;   line-height: 1.2;  letter-spacing: .12em; }
.dp-label { font-size: 12px;   line-height: 1.25; letter-spacing: .10em; }
.dp-cap   { font-size: 13px;   line-height: 1.35; }
.dp-body  { font-size: 14.5px; line-height: 1.4; }
.dp-sub   { font-size: 16px;   line-height: 1.3; }
.dp-h     { font-size: 22px;   line-height: 1.15; }
.dp-xl    { font-size: 32px;   line-height: 1.05; }
.dp-num   { font-variant-numeric: tabular-nums; }
/* ═══ GLASS MATERIAL ═══ */
/* ═══ KARTU = SLAB 3D NGAMBANG — perspective di dalam transform biar 3D-nya KELIATAN ═══ */
@keyframes dp-slab {
  0%,100% { transform: perspective(900px) translateZ(0) translateY(0) rotateX(0deg) rotateY(0deg); }
  50%     { transform: perspective(900px) translateZ(34px) translateY(-6px) rotateX(2.6deg) rotateY(-1.8deg); }
}
.dp-card  {
  box-shadow: var(--dp-sh-1);
  transition: box-shadow .4s ease, border-color .4s ease, filter .4s ease;
  transform-style: preserve-3d;
  animation: dp-slab 7s ease-in-out infinite;
}
.dp-card:nth-child(2n) { animation-duration: 8.5s; animation-delay: -3s; }
.dp-card:nth-child(3n) { animation-duration: 6.5s; animation-delay: -1.5s; }
.dp-card:nth-child(5n) { animation-duration: 9.5s; animation-delay: -4.5s; }
/* hover: glow + brightness (TANPA transform) → float 3D tetap mulus, gak nyentak */
.dp-card:hover {
  box-shadow: var(--dp-sh-2), 0 22px 60px -12px rgba(99,102,241,0.5);
  border-color: rgba(99,102,241,0.55);
  filter: brightness(1.1);
  z-index: 20;
}
.dp-glass { background: var(--dp-glass); backdrop-filter: blur(16px) saturate(1.5); -webkit-backdrop-filter: blur(16px) saturate(1.5); }

/* ═══ BULAT = BOLA 3D ═══ */
@keyframes dp-orb-float {
  0%,100% { transform: translateY(0) translateZ(0); }
  50%     { transform: translateY(-2px) translateZ(8px); }
}
.dp-scope span[class*="rounded-full"] {
  background-image: radial-gradient(circle at 32% 28%, rgba(255,255,255,0.55), rgba(255,255,255,0.05) 45%, transparent 62%);
  box-shadow: 0 2px 5px rgba(0,0,0,0.45), inset 0 -1px 3px rgba(0,0,0,0.35), inset 0 1px 2px rgba(255,255,255,0.35);
  transform-style: preserve-3d;
}

/* ═══ REDUCED MOTION ═══ */
@media (prefers-reduced-motion: reduce) {
  .dp-stream, .dp-breathe, .dp-signal, .dp-grid, .dp-flicker, .dp-bar,
  .dp-approach, .dp-approach-hot, .dp-ping, .animate-pulse,
  .dp-border-go::before, .dp-shimmer::after { animation: none !important; }
  .dp-sweep, .dp-scanline { display: none !important; }
  .dp-card { transition: none !important; transform: none !important; animation: none !important; }
}
`;

const TF_ORDER = ["DAILY", "H4", "H1", "M30", "M15", "M5", "M1"];
const TF_SHORT: Record<string, string> = { DAILY: "D1", H4: "H4", H1: "H1", M30: "M30", M15: "M15", M5: "M5", M1: "M1" };

// SETUP timeframes: M5 BUKAN setup — dia trigger terkecil (VR/CF-nya M15).
// Setup terkecil = CMP M15 → VR M5 → CF M5 → ENTRI M5.
const SETUP_TFS = ["DAILY", "H4", "H1", "M30", "M15"];
// TRIGGER timeframes: ditampilkan di Chain Rail buat MONITOR breakout & momentum —
// liat CF langsung running atau M5/M1 pullback dulu. BUKAN setup (gak masuk verdict/PRIME).
const TRIGGER_TFS = ["M5", "M1"];
// Urutan node di Chain Rail = setup + trigger (M5 nempel paling kanan).
const RAIL_TFS = [...SETUP_TFS, ...TRIGGER_TFS];
// Tiap setup TF: di TF mana VR-nya & CF-HIGH-nya terjadi (fractal — VR/CF = CMP di TF bawah).
const VRCF_TF: Record<string, { vr: string; cfHigh: string | null }> = {
  DAILY: { vr: "H4",  cfHigh: "H1"  },
  H4:    { vr: "H1",  cfHigh: "M30" },
  H1:    { vr: "M30", cfHigh: "M15" },
  M30:   { vr: "M15", cfHigh: "M5"  },
  M15:   { vr: "M5",  cfHigh: null  }, // CF HIGH butuh M1 → dihapus di v4. M15 CF LOW only.
};

const dirColor = (cmp: string) =>
  cmp === "BULLISH" ? "emerald" : cmp === "BEARISH" ? "rose" : "slate";
const dirWord = (cmp: string) =>
  cmp === "BULLISH" ? "BUY" : cmp === "BEARISH" ? "SELL" : "—";

// ── Verdict (mirror command-bar lama, dibuat ulang bersih) ───────────────────
function buildVerdict(p: DashboardProProps) {
  const { tfData, h4Dir, newsBlackout, newsApproaching, autoGrade, hasTFData } = p;
  if (!hasTFData)
    return { tone: "idle", icon: "○", head: "MENUNGGU DATA", sub: "Sync TradingView untuk mulai", accent: "slate" };
  if (newsBlackout)
    return { tone: "stop", icon: "⛔", head: "NEWS BLACKOUT", sub: `Tunggu ${p.minutesUntilNews}m — jangan entry`, accent: "rose" };

  // M5 BUKAN setup — jangan dianggap entry-ready di verdict (dia trigger M15)
  const f3Aligned = tfData.filter(d => d.fase === 3 && d.cmp && d.cmp === h4Dir && SETUP_TFS.includes(d.tf));
  if (f3Aligned.length) {
    const dir = dirWord(h4Dir);
    const tfs = f3Aligned.map(d => TF_SHORT[d.tf]).join(" · ");
    return { tone: "go", icon: "⚡", head: `SIAP ENTRY ${dir}`, sub: `${tfs} fase CF — eksekusi sesuai SL/TP`, accent: dir === "BUY" ? "emerald" : "rose" };
  }
  if (autoGrade.grade === "SKIP")
    return { tone: "stop", icon: "✕", head: "SKIP SETUP", sub: autoGrade.reason || "Berlawanan master", accent: "rose" };

  // CF FLIP — entry ilang, sub-TF balik arah. Beda dari tunggu CF pertama.
  const flipped = tfData.find(d => d.fase === 2 && d.vr === "YA" && d.cf !== "YA" && d.cfCount > 0 && SETUP_TFS.includes(d.tf));
  if (flipped)
    return { tone: "wait", icon: "↻", head: `CF FLIP — ${TF_SHORT[flipped.tf]}`, sub: `Entry #${flipped.cfCount} ilang. Nunggu CF #${flipped.cfCount + 1}`, accent: "rose" };
  const f2 = tfData.find(d => d.fase === 2 && SETUP_TFS.includes(d.tf));
  if (f2)
    return { tone: "wait", icon: "⏳", head: "TUNGGU CF", sub: `${TF_SHORT[f2.tf]} sudah VR — tunggu konfirmasi CF`, accent: "indigo" };

  if (newsApproaching)
    return { tone: "wait", icon: "⚠", head: "NEWS DEKAT", sub: `${p.minutesUntilNews}m lagi — hati-hati`, accent: "amber" };

  return { tone: "wait", icon: "⏳", head: "TUNGGU SETUP", sub: "Belum ada fase matang searah H4 master", accent: "indigo" };
}

// ── Primitif: Card ───────────────────────────────────────────────────────────
function Card({ title, icon, right, children, className, glow }: {
  title?: string; icon?: React.ReactNode; right?: React.ReactNode;
  children: React.ReactNode; className?: string; glow?: "go" | "wait" | "stop" | null;
}) {
  return (
    <div className={cn(
      "dp-card dp-glass relative rounded-2xl border overflow-hidden",
      glow === "go" ? "ring-1 ring-amber-400/30 border-amber-500/25" : "border-slate-700/30",
      className
    )}>
      {/* glass top edge */}
      <div className="absolute top-0 left-[8%] right-[8%] h-px bg-gradient-to-r from-transparent via-white/[0.07] to-transparent" />
      {title && (
        <div className="flex items-center justify-between px-5 pt-4 pb-2.5">
          <div className="flex items-center gap-2.5 text-slate-400">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-slate-700/40 to-slate-800/30 border border-slate-600/20 flex items-center justify-center shadow-sm">
              {icon}
            </div>
            <span className="dp-label font-bold uppercase tracking-[0.15em]">{title}</span>
          </div>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

// ── State kosong / loading / off — dirancang, bukan teks abu polos ───────────
function State({ icon, title, sub, pulse }: {
  icon?: React.ReactNode; title: string; sub?: string; pulse?: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-7 text-center">
      <div className={cn(
        "flex items-center justify-center w-9 h-9 rounded-xl border border-slate-700/60 bg-slate-800/40 text-slate-500",
        pulse && "dp-breathe"
      )}>
        {icon ?? <ActivityIcon className="w-4 h-4" />}
      </div>
      <div className="dp-cap font-medium text-slate-400">{title}</div>
      {sub && <div className="dp-micro uppercase text-slate-600">{sub}</div>}
    </div>
  );
}

// ── Grade Ring (SVG gauge) ───────────────────────────────────────────────────
function GradeRing({ grade }: { grade: string }) {
  const map: Record<string, { pct: number; color: string; ring: string }> = {
    "A+": { pct: 1.0, color: "#10b981", ring: "#10b981" },
    "A":  { pct: 0.82, color: "#34d399", ring: "#34d399" },
    "B":  { pct: 0.6, color: "#4f7cff", ring: "#4f7cff" },
    "C":  { pct: 0.38, color: "#f59e0b", ring: "#f59e0b" },
    "SKIP": { pct: 0.18, color: "#f43f5e", ring: "#f43f5e" },
    "—":  { pct: 0, color: "#475569", ring: "#334155" },
  };
  const g = map[grade] || map["—"];
  const R = 34, C = 2 * Math.PI * R;
  const off = C * (1 - g.pct);
  return (
    <div className="relative w-[100px] h-[100px] shrink-0">
      {/* ambient glow behind ring */}
      <div className="absolute inset-2 rounded-full opacity-20 blur-md" style={{ background: g.ring }} />
      <svg viewBox="0 0 80 80" className="relative w-full h-full -rotate-90">
        <circle cx="40" cy="40" r={R} fill="none" stroke="rgba(30,41,59,0.8)" strokeWidth="5" />
        <circle cx="40" cy="40" r={R} fill="none" stroke={g.ring} strokeWidth="5.5"
          strokeLinecap="round" strokeDasharray={C} strokeDashoffset={off}
          style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(.4,0,.2,1)", filter: `drop-shadow(0 0 8px ${g.ring}50)` }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[30px] font-black leading-none tabular-nums" style={{ color: g.color, textShadow: `0 0 20px ${g.color}30` }}>{grade}</span>
        <span className="text-[13px] uppercase text-slate-500/70 mt-1.5 font-bold tracking-[0.25em]">grade</span>
      </div>
    </div>
  );
}

// ── Phase dots (F1/F2/F3) ────────────────────────────────────────────────────
function PhaseDots({ fase, color }: { fase: number; color: string }) {
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3].map(n => (
        <span key={n} className={cn(
          "h-[6px] rounded-full transition-all duration-300",
          n <= fase ? "w-[18px]" : "w-[6px]",
          n <= fase
            ? color === "emerald" ? "bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.4)]"
              : color === "rose" ? "bg-rose-400 shadow-[0_0_4px_rgba(251,113,133,0.4)]"
              : "bg-indigo-400 shadow-[0_0_4px_rgba(129,140,248,0.4)]"
            : "bg-slate-700/60"
        )} />
      ))}
    </div>
  );
}

// ── CHAIN RAIL — horizontal timeline D1→M5 ───────────────────────────────────
function ChainRail({ tfData, h4Dir }: { tfData: TFRow[]; h4Dir: string }) {
  const nodes = RAIL_TFS.map(tf => tfData.find(d => d.tf === tf)).filter(Boolean) as TFRow[];
  const present = nodes.filter(n => n.cmp);
  return (
    <div className="px-5 pb-5">
      <div className="flex items-stretch gap-0">
        {RAIL_TFS.map((tf, i) => {
          const d = tfData.find(x => x.tf === tf);
          const has = !!d?.cmp;
          const col = has ? dirColor(d!.cmp) : "slate";
          const aligned = has && d!.cmp === h4Dir;
          const isMaster = tf === "H4";
          const isTrigger = TRIGGER_TFS.includes(tf);
          const next = tfData.find(x => x.tf === RAIL_TFS[i + 1]);
          const connOn = has && !!next?.cmp && next.cmp === h4Dir && aligned;
          return (
            <div key={tf} className="flex items-center flex-1 min-w-0">
              {/* node */}
              <div className={cn(
                "dp-row3d flex-1 min-w-0 rounded-xl border px-3 py-3 text-center transition-all relative overflow-hidden",
                isTrigger && "border-dashed",
                has ? (isTrigger ? "bg-slate-900/50" : "bg-gradient-to-b from-slate-800/40 to-slate-900/60") : "bg-slate-900/20 opacity-40",
                isMaster ? "border-indigo-500/50 shadow-[0_0_12px_-4px_rgba(79,124,255,0.3)]"
                  : isTrigger ? (has ? "border-amber-500/30" : "border-amber-500/15")
                  : has ? "border-slate-700/60" : "border-slate-800/40",
                // ring entry HANYA buat setup — M5 trigger gak pernah dianggap entry-ready
                !isTrigger && d?.fase === 3 && aligned && "ring-1 ring-amber-400/60 dp-signal shadow-[0_0_16px_-4px_rgba(251,191,36,0.4)]",
                !isTrigger && d?.fase === 2 && aligned && "dp-breathe"
              )}>
                {/* subtle inner glow for entry nodes */}
                {!isTrigger && d?.fase === 3 && aligned && (
                  <div className="absolute inset-0 bg-gradient-to-b from-amber-500/8 to-transparent pointer-events-none" />
                )}
                <div className="relative flex items-center justify-center gap-1">
                  <span className={cn("text-[14px] font-extrabold tracking-wide",
                    isMaster ? "text-indigo-300" : isTrigger ? "text-amber-300/80" : "text-slate-200")}>{TF_SHORT[tf]}</span>
                  {isMaster && <span className="text-[12px] text-indigo-400">★</span>}
                </div>
                {isTrigger && (
                  <div className="relative text-[13px] font-bold uppercase tracking-[0.14em] text-amber-500/60 leading-none mt-0.5 mb-0.5">trigger</div>
                )}
                <div className={cn("relative text-[12.5px] font-extrabold tabular-nums mt-1",
                  col === "emerald" ? "text-emerald-400" : col === "rose" ? "text-rose-400" : "text-slate-600")}>
                  {has ? dirWord(d!.cmp) : "—"}
                </div>
                {/* trigger = monitor momentum, gak ada fase setup → skip phase dots */}
                {!isTrigger && (
                  <div className="relative flex justify-center mt-2">
                    <PhaseDots fase={d?.fase || 0} color={col} />
                  </div>
                )}
                {isTrigger ? (
                  // status running vs pullback
                  has && (
                    <div className={cn("relative mt-1.5 text-[13px] font-bold uppercase tracking-wider",
                      aligned ? "text-emerald-400/90" : "text-rose-400/90")}>
                      {aligned ? "running" : "pullback"}
                    </div>
                  )
                ) : has && d!.fase === 3 ? (
                  // ⚡ ENTRY AKTIF
                  <div className="relative mt-2 inline-flex items-center gap-0.5 px-2 py-1 rounded-lg bg-amber-500/15 border border-amber-400/40 shadow-[0_0_8px_-2px_rgba(251,191,36,0.3)]">
                    <span className="text-[14px] font-bold text-amber-300 tabular-nums">
                      ⚡ CF{d!.cfCount || 1}{d!.cfType ? ` ${d!.cfType}` : ""}
                    </span>
                  </div>
                ) : has && d!.fase === 2 && (d!.cfCount || 0) > 0 ? (
                  // CF FLIP
                  <div className="relative mt-2 inline-flex items-center gap-0.5 px-2 py-1 rounded-lg bg-rose-500/10 border border-rose-500/30">
                    <span className="text-[14px] font-bold text-rose-300 tabular-nums">
                      FLIP · #{d!.cfCount + 1}
                    </span>
                  </div>
                ) : null}
              </div>
              {/* connector — animated data stream when aligned */}
              {i < RAIL_TFS.length - 1 && (
                connOn ? (
                  <div className="dp-stream w-4 sm:w-5 h-[2px] mx-0.5 shrink-0 rounded-full"
                    style={{ ["--c" as string]: h4Dir === "BULLISH" ? "#10b981" : "#f43f5e" }} />
                ) : (
                  <div className="w-4 sm:w-5 h-[2px] mx-0.5 shrink-0 rounded-full bg-slate-800/60" />
                )
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-3 text-center">
        <span className="text-[13px] text-slate-500 font-medium">{present.filter(d => d.cmp === h4Dir).length}/{present.length} timeframe selaras H4 master</span>
        {h4Dir && <span className={cn("ml-1.5 text-[13px] font-bold", h4Dir === "BULLISH" ? "text-emerald-400" : "text-rose-400")}>· {dirWord(h4Dir)}</span>}
      </div>
    </div>
  );
}

// ── SEQUENCE per CMP (CMP → VR → CF) — eksplisit tiap timeframe ───────────────
function SequenceList({ tfData, h4Dir }: { tfData: TFRow[]; h4Dir: string }) {
  const rows = SETUP_TFS.map(tf => tfData.find(d => d.tf === tf)).filter(d => d && d.cmp) as TFRow[];
  if (rows.length === 0)
    return <div className="pb-3"><State icon={<LayersIcon className="w-4 h-4" />} title="Belum ada CMP aktif" sub="sync tradingview untuk mulai" pulse /></div>;

  const Step = ({ label, done, active, waiting, flipped, tone, sub, tfTag, pulse }: {
    label: string; done: boolean; active?: boolean; waiting?: boolean; flipped?: boolean; tone: string; sub?: string; tfTag?: string; pulse?: boolean;
  }) => (
    <div className="flex flex-col items-center gap-1.5 shrink-0 w-10">
      <div className={cn(
        pulse ? "dp-cf-pulse" : "dp-coin",
        "w-8 h-8 rounded-full border-2 flex items-center justify-center text-[13px] font-bold transition-all",
        active
          ? "border-amber-400 bg-amber-400/15 text-amber-300 shadow-[0_0_12px_-2px_rgba(251,191,36,0.4)]"
          : done
            ? tone === "emerald" ? "border-emerald-500 bg-emerald-500/15 text-emerald-300"
              : tone === "rose" ? "border-rose-500 bg-rose-500/15 text-rose-300"
              : "border-indigo-500 bg-indigo-500/15 text-indigo-300"
            : flipped
              ? "border-rose-500 bg-rose-500/10 text-rose-300 border-dashed"
              : waiting
                ? "border-indigo-500/70 bg-indigo-500/8 text-indigo-300 dp-breathe"
                : "border-slate-700/60 bg-slate-800/30 text-slate-600"
      )}>
        {done || active ? "✓" : flipped ? "↻" : waiting ? "◌" : "○"}
      </div>
      <span className={cn("text-[12px] font-semibold tracking-wide",
        active ? "text-amber-300" : done || waiting ? "text-slate-300" : "text-slate-600")}>{label}</span>
      {tfTag && <span className="text-[13px] font-bold tracking-wide text-slate-500/80 leading-none">@{tfTag}</span>}
      {sub && <span className="text-[13px] text-amber-400/90 tabular-nums leading-none font-bold">{sub}</span>}
    </div>
  );

  // konektor sejajar TENGAH lingkaran: circle h-8 (32px) → center 16px, line 2px → mt 15px
  const Conn = ({ on, tone }: { on: boolean; tone: string }) => (
    on ? (
      <div className="dp-stream flex-1 h-[2px] mx-1.5 mt-[15px] rounded-full self-start"
        style={{ ["--c" as string]: tone === "emerald" ? "#10b981" : tone === "rose" ? "#f43f5e" : "#4f7cff" }} />
    ) : (
      <div className="flex-1 h-[2px] mx-1.5 mt-[15px] rounded-full self-start bg-slate-800/50 border-t border-slate-700/30" />
    )
  );

  return (
    <div className="px-4 pb-4 space-y-2">
      {rows.map(d => {
        const tone = dirColor(d.cmp);
        const vrDone = d.vr === "YA";
        const cfDone = d.cf === "YA";
        const cfFlipped = !cfDone && vrDone && d.cfCount > 0; // CF was active → sub-TF flip → entry ILANG
        const aligned = d.cmp === h4Dir;
        const isMaster = d.tf === "H4";
        const faseLabel = d.fase === 3
          ? `ENTRI CF#${d.cfCount || 1}${d.cfType ? " " + d.cfType : ""}`
          : cfFlipped
            ? `CF FLIP · #${d.cfCount + 1}`
            : d.fase === 2 ? "tunggu CF" : "tunggu VR";
        return (
          <div key={d.tf} className={cn(
            "dp-row3d rounded-xl border px-4 py-3 flex items-center gap-4 transition-all",
            d.fase === 3 && aligned ? "border-amber-500/35 bg-gradient-to-r from-amber-500/[0.06] to-transparent shadow-[0_0_12px_-6px_rgba(251,191,36,0.2)]"
              : cfFlipped ? "border-rose-500/25 bg-gradient-to-r from-rose-500/[0.04] to-transparent"
              : isMaster ? "border-indigo-500/25 bg-gradient-to-r from-indigo-500/[0.04] to-transparent"
              : "border-slate-800/60 bg-slate-900/30 hover:bg-slate-800/20"
          )}>
            {/* TF + arah */}
            <div className="w-16 shrink-0">
              <div className="flex items-center gap-1">
                <span className={cn("text-[13px] font-extrabold", isMaster ? "text-indigo-300" : "text-slate-200")}>{TF_SHORT[d.tf]}</span>
                {isMaster && <span className="text-[12px] text-indigo-400">★</span>}
              </div>
              <div className={cn("text-[14px] font-bold mt-0.5",
                tone === "emerald" ? "text-emerald-400" : tone === "rose" ? "text-rose-400" : "text-slate-500")}>
                {dirWord(d.cmp)}
              </div>
            </div>
            {/* sequence stepper — VR & CF dilabeli TF tempat ia terjadi (fractal) */}
            <div className="flex-1 flex items-start min-w-0">
              <Step label="CMP" done tone={tone} tfTag={TF_SHORT[d.tf]} />
              <Conn on={vrDone || cfDone} tone={tone} />
              <Step label="VR" done={vrDone} waiting={!vrDone} tone={tone}
                tfTag={VRCF_TF[d.tf]?.vr ? TF_SHORT[VRCF_TF[d.tf].vr] : undefined} />
              <Conn on={cfDone} tone={tone} />
              <Step label="CF" done={cfDone && d.fase !== 3} active={cfDone && d.fase === 3}
                pulse={cfDone && !cfFlipped}
                waiting={!cfDone && vrDone && !cfFlipped} flipped={cfFlipped} tone={tone}
                tfTag={
                  // CF LOW = dari TF yang sama kasih VR. CF HIGH = 1 level bawah VR TF.
                  d.cfType === "HIGH" && VRCF_TF[d.tf]?.cfHigh
                    ? TF_SHORT[VRCF_TF[d.tf].cfHigh!]
                    : VRCF_TF[d.tf]?.vr ? TF_SHORT[VRCF_TF[d.tf].vr] : undefined
                }
                sub={d.cfCount > 0 ? `×${d.cfCount}${d.cfType ? " " + d.cfType : ""}` : undefined} />
            </div>
            {/* status */}
            <div className="w-28 shrink-0 text-right space-y-1">
              <div className={cn("text-[13.5px] font-bold",
                d.fase === 3 ? "text-amber-300" : cfFlipped ? "text-rose-300" : d.fase === 2 ? "text-indigo-300" : "text-slate-400")}>
                {faseLabel}
              </div>
              <div className={cn("inline-flex items-center gap-1 text-[14px] font-medium px-1.5 py-0.5 rounded-md",
                aligned ? "text-emerald-400/90 bg-emerald-500/8" : "text-amber-400/90 bg-amber-500/8")}>
                <span className={cn("w-1 h-1 rounded-full", aligned ? "bg-emerald-400" : "bg-amber-400")} />
                {aligned ? "selaras H4" : "lawan H4"}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── SNR PRICE LADDER ─────────────────────────────────────────────────────────
function SnrLadder({ aboveLevels, belowLevels, atLevel, cmpFloat, displayPrice, livePrice }: {
  aboveLevels: Lvl[]; belowLevels: Lvl[]; atLevel: Lvl[]; cmpFloat: number;
  displayPrice: string; livePrice: string;
}) {
  const above = aboveLevels.slice(0, 3).reverse();
  const below = belowLevels.slice(0, 3);
  // ambang kedekatan (XAUUSD, satuan ~ USD): NEAR mulai menyala, HOT = pulse keras
  const NEAR = 8, HOT = 3, METER_SCALE = 30;

  // level terdekat overall + tracking HOT untuk audio tick
  const withDist = [
    ...above.map(l => ({ l, side: "up" as const, dist: Math.abs(l.price - cmpFloat) })),
    ...below.map(l => ({ l, side: "dn" as const, dist: Math.abs(l.price - cmpFloat) })),
  ];
  const nearest = withDist.length ? withDist.reduce((a, b) => (b.dist < a.dist ? b : a)) : null;
  const hotList = withDist.filter(x => x.dist <= HOT);
  const hotSig = hotList.map(x => x.l.key).sort().join(",");

  const [muted, setMuted] = useState(false);
  const prevHot = useRef<Set<string>>(new Set());
  useEffect(() => {
    const cur = new Set(hotList.map(x => x.l.key));
    if (!muted) for (const x of hotList) if (!prevHot.current.has(x.l.key)) snrTick(x.side);
    prevHot.current = cur;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotSig, muted]);

  const Row = ({ l, side }: { l: Lvl; side: "up" | "dn" }) => {
    const dist = Math.abs(l.price - cmpFloat);
    const near = dist <= NEAR;
    const hot = dist <= HOT;
    const rgb = side === "up" ? "244,63,94" : "16,185,129"; // rose / emerald
    const fill = near ? Math.max(0, Math.min(1, 1 - dist / NEAR)) : 0;
    return (
      <div
        style={near ? ({ ["--gc" as string]: `rgba(${rgb},${hot ? 0.9 : 0.55})`, ["--gc-dim" as string]: `rgba(${rgb},0.18)` } as React.CSSProperties) : undefined}
        className={cn(
          "relative flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors overflow-hidden",
          hot ? "bg-slate-800/55 dp-approach-hot" : near ? "bg-slate-800/30 dp-approach" : "hover:bg-slate-800/40"
        )}
      >
        {near && (
          <span className="absolute inset-y-0 left-0 pointer-events-none"
            style={{ width: `${fill * 100}%`, background: `linear-gradient(90deg, rgba(${rgb},${hot ? 0.20 : 0.09}), transparent)` }} />
        )}
        {hot && <span className="dp-sweep" />}
        <span className="relative w-1.5 h-1.5 rounded-full shrink-0" style={{ background: `rgba(${rgb},${near ? 1 : 0.7})` }}>
          {hot && <span className="dp-ping absolute inset-0 rounded-full" style={{ background: `rgba(${rgb},0.7)` }} />}
        </span>
        <span className={cn("relative text-[13.5px] w-12 shrink-0 truncate", near ? "text-slate-200" : "text-slate-400")}>{l.short}</span>
        <span className={cn("relative text-[12px] font-semibold tabular-nums flex-1 text-right", near ? "text-slate-50" : "text-slate-200")}>{l.price.toFixed(2)}</span>
        <span className="relative text-[12.5px] tabular-nums w-14 text-right font-semibold" style={near ? { color: `rgb(${rgb})` } : { color: "#64748b" }}>
          {hot ? "▸ " : ""}{dist.toFixed(1)}p
        </span>
      </div>
    );
  };
  // warna & meter level terdekat
  const nRgb = nearest ? (nearest.side === "up" ? "244,63,94" : "16,185,129") : "148,163,184";
  const nHot = nearest ? nearest.dist <= HOT : false;
  const nNear = nearest ? nearest.dist <= NEAR : false;
  const meterPct = nearest ? Math.max(2, Math.min(100, (1 - nearest.dist / METER_SCALE) * 100)) : 0;
  const railOpacity = nearest && nNear ? (nHot ? 0.95 : 0.55) : 0.12;

  return (
    <div className="px-1.5 pb-3">
      {/* ── APPROACH METER — level terdekat, hidup ─────────────────────────── */}
      <div className={cn("mx-1.5 mb-2 rounded-xl border bg-slate-900/40 px-3 py-2 flex items-center gap-3",
        nHot ? "dp-approach-hot" : nNear ? "dp-approach" : "border-slate-700/60")}
        style={nNear ? ({ ["--gc" as string]: `rgba(${nRgb},${nHot ? 0.9 : 0.5})`, ["--gc-dim" as string]: `rgba(${nRgb},0.18)` } as React.CSSProperties) : undefined}>
        <div className="flex-1 min-w-0">
          {nearest ? (
            <>
              <div className="flex items-center justify-between dp-micro uppercase text-slate-500 mb-1">
                <span>level terdekat</span>
                <span className="font-semibold" style={{ color: nNear ? `rgb(${nRgb})` : undefined }}>
                  {nearest.side === "up" ? "▲ resistance" : "▼ support"}
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-[12.5px] font-semibold text-slate-100 truncate">{nearest.l.short}</span>
                <span className="text-[13px] tabular-nums text-slate-400">{nearest.l.price.toFixed(2)}</span>
                <span className="ml-auto text-[13px] font-bold tabular-nums" style={{ color: nNear ? `rgb(${nRgb})` : "#94a3b8" }}>
                  {nHot ? "▸ " : ""}{nearest.dist.toFixed(1)}p
                </span>
              </div>
              <div className="mt-1.5 h-1 rounded-full bg-slate-800 overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${meterPct}%`, background: `linear-gradient(90deg, rgba(${nRgb},0.35), rgba(${nRgb},${nNear ? 0.95 : 0.4}))` }} />
              </div>
            </>
          ) : <span className="text-[13px] text-slate-600">— belum ada level —</span>}
        </div>
        <button onClick={() => setMuted(m => !m)} title={muted ? "Bunyi mati" : "Bunyi nyala"}
          className={cn("shrink-0 rounded-lg p-1.5 transition-colors", muted ? "text-slate-600 hover:text-slate-400" : "text-indigo-300 hover:text-indigo-200")}>
          {muted ? <VolumeXIcon className="w-3.5 h-3.5" /> : <Volume2Icon className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* ── LADDER + guide-rail kiri ───────────────────────────────────────── */}
      <div className="relative pl-2">
        <span aria-hidden className="absolute left-0 top-1 bottom-1 w-[3px] rounded-full transition-all duration-500"
          style={{ background: `linear-gradient(180deg, transparent, rgba(${nRgb},${railOpacity}), transparent)`,
            boxShadow: nNear ? `0 0 8px rgba(${nRgb},${nHot ? 0.7 : 0.35})` : "none" }} />

        {/* resistance */}
        <div className="space-y-0.5">
          {above.length === 0 && <div className="px-3 py-1.5 dp-micro uppercase text-slate-600">tidak ada resistance</div>}
          {above.map((l, i) => <Row key={`u${i}`} l={l} side="up" />)}
        </div>
        {/* current price band */}
        <div className="my-2 mx-1.5 rounded-xl bg-gradient-to-r from-indigo-500/12 via-indigo-500/18 to-indigo-500/12 border border-indigo-500/30 px-4 py-2.5 flex items-center justify-between shadow-[0_0_16px_-6px_rgba(79,124,255,0.25)]">
          <div className="flex items-center gap-2">
            <span className={cn("w-2 h-2 rounded-full", livePrice ? "bg-emerald-400 animate-pulse" : "bg-slate-600")} />
            <span className="text-[12px] font-bold uppercase tracking-[0.15em] text-indigo-300/70">harga saat ini</span>
          </div>
          <span className="text-[18px] font-extrabold tabular-nums text-indigo-100 tracking-tight">{displayPrice}</span>
        </div>
        {atLevel.length > 0 && (
          <div className="mx-3 mb-1 flex items-center gap-1.5 text-[12.5px] font-semibold text-amber-300">
            <span className="relative flex w-1.5 h-1.5">
              <span className="dp-ping absolute inset-0 rounded-full bg-amber-400" />
              <span className="relative w-1.5 h-1.5 rounded-full bg-amber-400" />
            </span>
            MENEMPEL: {atLevel.map(l => l.short).join(", ")}
          </div>
        )}
        {/* support */}
        <div className="space-y-0.5">
          {below.length === 0 && <div className="px-3 py-1.5 dp-micro uppercase text-slate-600">tidak ada support</div>}
          {below.map((l, i) => <Row key={`d${i}`} l={l} side="dn" />)}
        </div>
      </div>
    </div>
  );
}

// ── PRESSURE GAUGE ───────────────────────────────────────────────────────────
function Pressure({ buyPct, sellPct, cumDelta, momentum, barDeltas, maxBarAbs, divergence, nTicks }: {
  buyPct: number; sellPct: number; cumDelta: number; momentum: string;
  barDeltas: number[]; maxBarAbs: number; divergence: boolean; nTicks: number;
}) {
  const momCol = momentum === "BULL" ? "text-emerald-400" : momentum === "BEAR" ? "text-rose-400" : "text-slate-400";
  return (
    <div className="px-5 pb-5">
      {nTicks < 5 ? (
        <State icon={<GaugeIcon className="w-4 h-4" />} title="Mengumpulkan tick…" sub="butuh ≥5 tick" pulse />
      ) : (
        <>
          {/* split bar */}
          <div className="flex items-center gap-2.5 mb-3">
            <span className="text-[12px] font-extrabold tabular-nums text-emerald-400 w-10">{buyPct}%</span>
            <div className="flex-1 h-2.5 rounded-full overflow-hidden bg-slate-800/60 flex shadow-inner">
              <div className="h-full bg-gradient-to-r from-emerald-500/90 to-emerald-400/70 transition-all duration-500 rounded-l-full" style={{ width: `${buyPct}%` }} />
              <div className="h-full bg-gradient-to-r from-rose-400/70 to-rose-500/90 transition-all duration-500 rounded-r-full" style={{ width: `${sellPct}%` }} />
            </div>
            <span className="text-[12px] font-extrabold tabular-nums text-rose-400 w-10 text-right">{sellPct}%</span>
          </div>
          {/* sparkline bars */}
          <div className="flex items-end justify-between gap-[3px] h-16 mb-3 px-0.5">
            {barDeltas.map((d, i) => {
              const h = Math.max(8, Math.abs(d) / maxBarAbs * 100);
              return (
                <div key={i} className="flex-1 flex flex-col justify-end h-full">
                  <div className={cn("dp-bar w-full rounded-sm transition-all",
                    d >= 0 ? "bg-gradient-to-t from-emerald-500/70 to-emerald-400/40" : "bg-gradient-to-t from-rose-500/70 to-rose-400/40")}
                    style={{ height: `${h}%`, animationDelay: `${i * 0.12}s` }} />
                </div>
              );
            })}
          </div>
          <div className="flex items-center justify-between">
            <span className={cn("text-[13px] font-semibold", momCol)}>
              {momentum === "BULL" ? "▲ Tekanan Beli" : momentum === "BEAR" ? "▼ Tekanan Jual" : "─ Seimbang"}
            </span>
            <span className={cn("text-[13px] tabular-nums font-medium", cumDelta >= 0 ? "text-emerald-400" : "text-rose-400")}>
              Δ {cumDelta > 0 ? "+" : ""}{cumDelta}
            </span>
          </div>
          {divergence && (
            <div className="mt-2 text-[12.5px] text-amber-300/90 bg-amber-500/10 border border-amber-500/25 rounded-lg px-2 py-1">
              ⚠ Divergence — tekanan berbalik arah
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── STORYLINE + CONTI + ACTIVE CMP ───────────────────────────────────────────
function StorylineConti({ tfData, h4Dir }: { tfData: TFRow[]; h4Dir: string }) {
  const get = (tf: string) => tfData.find(d => d.tf === tf);

  // ── Active CMP Detection ─────────────────────────────────────────────────
  // TF yang sedang di-VR (fase 2 = VR sudah tapi CF belum) = CMP yang sedang aktif diuji
  // Priority: smallest TF first (most granular / most current)
  const activeTF = ["M15","M30","H1","H4","DAILY"].find(tf => {
    const d = get(tf);
    return d?.cmp && d.vr === "YA" && d.cf !== "YA";
  });
  const activeD = activeTF ? get(activeTF) : null;
  const activeDir = activeD ? dirWord(activeD.cmp) : "—";
  const activeVrFrom: Record<string, string> = { DAILY:"H4", H4:"H1", H1:"M30", M30:"M15", M15:"M5" };
  const activeCol = activeDir === "BUY" ? "emerald" : activeDir === "SELL" ? "rose" : "slate";

  // ── CONTI Status ─────────────────────────────────────────────────────────
  // CONTI valid = CMP ada + VR BELUM terjadi (H4/H1/M30 belum berlawanan arah)
  // Begitu VR terjadi (vr === "YA") → CONTI window tutup → sekarang nunggu CF
  const contiRows = [
    {
      name: "Daily CONTI", entry: "→ entry H1",
      sop: "SOP H1: VR M30 → CF M30/M15",
      tp: "150+ pts",
      d: get("DAILY"),
      ok: !!get("DAILY")?.cmp && get("DAILY")?.cmp !== "WAIT" && get("DAILY")?.vr !== "YA",
    },
    {
      name: "H4 CONTI", entry: "→ entry M30",
      sop: "SOP M30: VR M15 → CF M15/M5",
      tp: "80–150 pts",
      d: get("H4"),
      ok: !!get("H4")?.cmp && get("H4")?.cmp !== "WAIT" && get("H4")?.vr !== "YA",
    },
    {
      name: "H1 CONTI", entry: "→ entry M15",
      sop: "SOP M15: VR M5 → CF M5",
      tp: "10–30 pts ⚡",
      d: get("H1"),
      ok: !!get("H1")?.cmp && get("H1")?.cmp !== "WAIT" && get("H1")?.vr !== "YA",
    },
  ];
  const anyConti = contiRows.some(c => c.ok);

  return (
    <div className="px-4 pb-4 space-y-3">
      {/* ── Active CMP ──────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-slate-700/30 bg-slate-900/40 px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[12px] font-bold uppercase tracking-[0.18em] text-slate-500">CMP Aktif Sekarang</span>
          <div className="flex-1 h-px bg-slate-800/60" />
          <span className="text-[12px] text-slate-600">diuji VR</span>
        </div>
        {activeTF ? (
          <div className="flex items-center gap-3">
            <div className={cn("text-[26px] font-extrabold tabular-nums",
              activeCol === "emerald" ? "text-emerald-400" : activeCol === "rose" ? "text-rose-400" : "text-slate-500")}>
              {TF_SHORT[activeTF]}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className={cn("text-[13px] font-bold",
                  activeCol === "emerald" ? "text-emerald-400" : activeCol === "rose" ? "text-rose-400" : "text-slate-400")}>
                  {activeDir}
                </span>
                <span className="text-[12px] text-slate-500">CMP sedang diuji</span>
              </div>
              <div className="text-[13px] text-slate-500 mt-0.5">
                VR dari <span className="font-bold text-slate-400">{activeVrFrom[activeTF] || "?"}</span>
                {" · "}setelah VR selesai → tunggu CF searah
              </div>
            </div>
            <div className="ml-auto">
              <span className="dp-breathe inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-[13px] font-semibold text-indigo-300">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                F2 · Menunggu CF
              </span>
            </div>
          </div>
        ) : (
          <div className="text-[13px] text-slate-500 py-1">
            {tfData.some(d => d.fase === 3) ? "🟢 CF sudah aktif — siap entry" : "Tidak ada VR berlangsung · Tunggu CMP breakout"}
          </div>
        )}
      </div>

      {/* ── CONTI Panel ─────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-slate-700/30 bg-slate-900/40 px-4 py-3">
        <div className="flex items-center gap-2 mb-2.5">
          <span className="text-[12px] font-bold uppercase tracking-[0.18em] text-slate-500">Conti Entry</span>
          <div className="flex-1 h-px bg-slate-800/60" />
          <span className={cn("text-[12px] font-bold",
            anyConti ? "text-emerald-400" : "text-slate-600"
          )}>{anyConti ? `${contiRows.filter(c=>c.ok).length} valid` : "semua tutup"}</span>
        </div>
        <div className="space-y-2">
          {contiRows.map(c => {
            const dir = c.d ? dirWord(c.d.cmp) : "—";
            const col = dir === "BUY" ? "emerald" : dir === "SELL" ? "rose" : "slate";
            return (
              <div key={c.name} className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 border transition-all",
                c.ok
                  ? col === "emerald" ? "bg-emerald-500/6 border-emerald-500/20"
                    : col === "rose" ? "bg-rose-500/6 border-rose-500/20"
                    : "bg-slate-800/30 border-slate-700/40"
                  : "bg-slate-900/20 border-slate-800/30 opacity-50"
              )}>
                {/* status dot */}
                <div className={cn("w-2 h-2 rounded-full shrink-0",
                  c.ok ? col === "emerald" ? "bg-emerald-400" : "bg-rose-400" : "bg-slate-700"
                )} />
                {/* name + entry */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className={cn("text-[13px] font-bold",
                      c.ok ? "text-slate-200" : "text-slate-500")}>{c.name}</span>
                    {c.ok && (
                      <span className={cn("text-[13px] font-semibold",
                        col === "emerald" ? "text-emerald-400" : "text-rose-400")}>{dir}</span>
                    )}
                    <span className="text-[12px] text-slate-500">{c.entry}</span>
                  </div>
                  {c.ok && (
                    <div className="text-[12px] text-slate-500 mt-0.5">{c.sop}</div>
                  )}
                </div>
                {/* TP */}
                <div className={cn("text-[13px] font-bold tabular-nums shrink-0",
                  c.ok ? "text-amber-300/90" : "text-slate-700")}>
                  {c.tp}
                </div>
                {/* valid/invalid badge */}
                <div className={cn("shrink-0 text-[12px] font-bold px-1.5 py-0.5 rounded-md",
                  c.ok ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/25"
                    : "bg-slate-800/40 text-slate-600 border border-slate-800/60"
                )}>
                  {c.ok ? "✓ VALID" : "✕ VR"}
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-2.5 text-[12px] text-slate-600 leading-relaxed">
          CONTI valid selama TF parent belum VR · Begitu VR terjadi → window tutup, tunggu CF
        </div>
      </div>
    </div>
  );
}

// ── VR SCALP PANEL — Scalp Sambil Nunggu Setup Besar ─────────────────────────
// Doktrin: VR adalah CMP di TF bawahnya. Scalp searah VR sambil nunggu CF utama.
function VrScalpPanel({ tfData }: { tfData: TFRow[] }) {
  const get = (tf: string) => tfData.find(d => d.tf === tf);

  const TP_MAP: Record<string, string> = {
    M5: "M15", M15: "M30", M30: "H1", H1: "H4", H4: "DAILY",
  };

  // VR pairs: scalp TF berlawanan parent → scalp valid
  // guard = TF satu level di bawah scalp (kondisi kunci "belum VR parent dir")
  // sub   = TF untuk deteksi CF_HIGH (2 level bawah scalp)
  const PAIRS = [
    { scalp: "H1",  parent: "H4",  guard: "M30", sub: "M5"  },
    { scalp: "M30", parent: "H1",  guard: "M15", sub: null   },
    { scalp: "M15", parent: "M30", guard: "M5",  sub: null   },
  ] as const;

  type VrOpp = {
    scalp: string; parent: string; guard: string; sub: string | null;
    scalpDir: string; parentDir: string;
    status: "VALID" | "STOP";
    signal: "CF_LOW" | "CF_HIGH" | "WAITING_CF" | "CONTI" | null;
    entryTF: string | null; tpTF: string | null;
  };

  const opps: VrOpp[] = [];

  for (const pair of PAIRS) {
    const scalpD  = get(pair.scalp);
    const parentD = get(pair.parent);
    const guardD  = get(pair.guard);
    const subD    = pair.sub ? get(pair.sub) : null;

    if (!scalpD?.cmp || !parentD?.cmp) continue;
    if (scalpD.cmp === "WAIT" || parentD.cmp === "WAIT") continue;
    if (scalpD.cmp === parentD.cmp) continue; // aligned = tidak VR

    const scalpDir  = scalpD.cmp;
    const parentDir = parentD.cmp;

    // STOP: guard sudah flip ke parent direction = scalp master mau CF balik
    if (guardD?.cmp === parentDir) {
      opps.push({ scalp: pair.scalp, parent: pair.parent, guard: pair.guard, sub: pair.sub ?? null,
        scalpDir, parentDir, status: "STOP", signal: null, entryTF: null, tpTF: null });
      continue;
    }

    // Signal detection dari fase guard
    let signal: VrOpp["signal"] = "CONTI";
    let entryTF: string | null = null;

    if (guardD?.cmp === scalpDir) {
      if (guardD.fase === 3) {
        // Guard complete VR→CF cycle di scalp direction = CF_LOW entry
        signal = "CF_LOW"; entryTF = pair.guard;
      } else if (guardD.fase === 2 && subD?.cmp === scalpDir) {
        // Guard F2 (sub VR-ing guard), sub sudah CF balik ke scalp dir = CF_HIGH
        signal = "CF_HIGH"; entryTF = pair.sub ?? null;
      } else if (guardD.fase === 2) {
        signal = "WAITING_CF";
      }
      // fase 1 → CONTI (guard belum VR = pre-VR territory)
    }

    const tpTF = entryTF ? (TP_MAP[entryTF] ?? null) : null;
    opps.push({ scalp: pair.scalp, parent: pair.parent, guard: pair.guard, sub: pair.sub ?? null,
      scalpDir, parentDir, status: "VALID", signal, entryTF, tpTF });
  }

  if (opps.length === 0) {
    return (
      <div className="px-5 pb-4">
        <State icon={<ZapIcon className="w-4 h-4" />}
          title="Semua TF aligned" sub="Tidak ada VR aktif · pakai CONTI atau tunggu setup" />
      </div>
    );
  }

  return (
    <div className="px-5 pb-4 space-y-2.5">
      <div className="dp-micro uppercase text-slate-600 tracking-wider pt-1">
        TP · CF M5→M15 · CF M15→M30 · CF M30→H1 · CF H1→H4
      </div>
      {opps.map(o => {
        const scalpWord = dirWord(o.scalpDir);
        const parentWord = dirWord(o.parentDir);
        const isStop  = o.status === "STOP";
        const isEntry = o.signal === "CF_LOW" || o.signal === "CF_HIGH";
        const scalpC  = o.scalpDir === "BULLISH" ? "emerald" : "rose";
        const parentC = o.parentDir === "BULLISH" ? "emerald" : "rose";

        return (
          <div key={`${o.scalp}-${o.parent}`} className={cn(
            "rounded-xl border px-4 py-3 transition-all",
            isStop  ? "bg-slate-900/30 border-slate-700/20 opacity-50"
            : isEntry ? (scalpC === "emerald" ? "bg-emerald-500/6 border-emerald-500/20"
                                               : "bg-rose-500/6 border-rose-500/20")
            : "bg-slate-900/20 border-slate-800/30"
          )}>
            {/* ── Header row ─────────────────────────────────────────────── */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 flex-wrap">
                {/* parent chip */}
                <span className={cn("dp-label font-extrabold",
                  parentC === "emerald" ? "text-emerald-400" : "text-rose-400")}>
                  {TF_SHORT[o.parent] || o.parent}
                </span>
                <span className={cn("dp-micro font-bold",
                  parentC === "emerald" ? "text-emerald-400/70" : "text-rose-400/70")}>
                  {parentWord}
                </span>
                <span className="dp-micro text-slate-600">·</span>
                {/* scalp chip */}
                <span className={cn("dp-label font-extrabold",
                  scalpC === "emerald" ? "text-emerald-400" : "text-rose-400")}>
                  {TF_SHORT[o.scalp] || o.scalp}
                </span>
                <span className="dp-micro text-slate-500">VR →</span>
                <span className={cn("dp-label font-extrabold",
                  scalpC === "emerald" ? "text-emerald-400" : "text-rose-400")}>
                  SCALP {scalpWord}
                </span>
              </div>
              {/* badge */}
              {isStop ? (
                <span className="shrink-0 dp-micro font-bold px-2 py-0.5 rounded-lg bg-slate-800/60 text-slate-500 border border-slate-700/40">
                  ⛔ STOP
                </span>
              ) : isEntry ? (
                <span className={cn("shrink-0 dp-micro font-bold px-2.5 py-1 rounded-lg border",
                  scalpC === "emerald" ? "bg-emerald-500/15 text-emerald-200 border-emerald-400/30"
                                       : "bg-rose-500/15 text-rose-200 border-rose-400/30")}>
                  ⚡ {o.signal}
                </span>
              ) : o.signal === "WAITING_CF" ? (
                <span className="shrink-0 dp-micro font-bold px-2 py-0.5 rounded-lg bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  ⏳ WAIT CF
                </span>
              ) : (
                <span className="shrink-0 dp-micro px-2 py-0.5 rounded-lg bg-slate-800/40 text-slate-600 border border-slate-700/30">
                  CONTI
                </span>
              )}
            </div>

            {/* ── Detail row ─────────────────────────────────────────────── */}
            <div className="mt-1.5 flex items-center flex-wrap gap-x-2 gap-y-1 dp-micro">
              {isStop ? (
                <span className="text-slate-500">
                  {TF_SHORT[o.guard] || o.guard} flip {parentWord} → {TF_SHORT[o.scalp] || o.scalp} mau CF {parentWord} · stop scalp
                </span>
              ) : (
                <>
                  <span className={cn("font-semibold",
                    scalpC === "emerald" ? "text-emerald-400/80" : "text-rose-400/80")}>
                    {TF_SHORT[o.guard] || o.guard} belum VR {parentWord} ✓
                  </span>
                  {isEntry && o.entryTF && o.tpTF && (
                    <>
                      <span className="text-slate-600">·</span>
                      <span className="text-slate-500">entry</span>
                      <span className="font-bold text-amber-300">CF {TF_SHORT[o.entryTF] || o.entryTF}</span>
                      <span className="text-slate-600">·</span>
                      <span className="text-slate-500">TP</span>
                      <span className="font-bold text-amber-300">SNR {TF_SHORT[o.tpTF] || o.tpTF}</span>
                    </>
                  )}
                  {o.signal === "WAITING_CF" && (
                    <span className="text-slate-500">
                      {TF_SHORT[o.guard] || o.guard} F2 — tunggu CF {scalpWord}
                      {o.sub ? ` atau ${TF_SHORT[o.sub] || o.sub} CF ${scalpWord}` : ""}
                    </span>
                  )}
                  {o.signal === "CONTI" && (
                    <span className="text-slate-500">
                      {TF_SHORT[o.guard] || o.guard} F1 — cari CF {scalpWord} di sub-TF
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
        );
      })}
      <div className="pt-1 dp-micro text-slate-600">
        Scalp valid selama guard TF belum VR ke arah parent · Stop begitu guard flip
      </div>
    </div>
  );
}

// ── SETUP FOCUS — TF paling siap entry ───────────────────────────────────────
function SetupFocus({ tfData, h4Dir }: { tfData: TFRow[]; h4Dir: string }) {
  // ranking: fase desc, aligned first — HANYA setup TF (M5 bukan setup, dia trigger)
  const ranked = [...tfData.filter(d => d.cmp && SETUP_TFS.includes(d.tf))].sort((a, b) => {
    const aa = a.cmp === h4Dir ? 1 : 0, ba = b.cmp === h4Dir ? 1 : 0;
    if (b.fase !== a.fase) return b.fase - a.fase;
    return ba - aa;
  });
  const top = ranked[0];
  if (!top) return <div className="pb-3"><State icon={<TargetIcon className="w-4 h-4" />} title="Belum ada setup matang" sub="tunggu fase cf searah h4" pulse /></div>;
  const col = dirColor(top.cmp);
  const aligned = top.cmp === h4Dir;
  const topVrDone = top.vr === "YA";
  const topCfDone = top.cf === "YA";
  const topCfFlipped = !topCfDone && topVrDone && top.cfCount > 0;
  const faseLabel = top.fase === 3
    ? `F3 · ENTRI CF#${top.cfCount || 1}${top.cfType ? " " + top.cfType : ""}`
    : topCfFlipped
      ? `F2 · CF FLIP — nunggu #${top.cfCount + 1}`
      : top.fase === 2 ? "F2 · tunggu CF" : "F1 · tunggu VR";
  const sl = top.sl;
  return (
    <div className="px-5 pb-5">
      <div className="flex items-baseline gap-3">
        <span className="text-[28px] font-extrabold tracking-tight text-slate-50">{TF_SHORT[top.tf]}</span>
        <span className={cn("text-[20px] font-extrabold",
          col === "emerald" ? "text-emerald-400" : col === "rose" ? "text-rose-400" : "text-slate-500")}>
          {dirWord(top.cmp)}
        </span>
        {top.fase === 3 ? (
          <span className="text-[13px] font-bold text-amber-300 px-2 py-0.5 rounded-lg bg-amber-500/15 border border-amber-400/35 shadow-[0_0_8px_-2px_rgba(251,191,36,0.3)]">
            ⚡ CF{top.cfCount || 1}{top.cfType ? ` ${top.cfType}` : ""}
          </span>
        ) : topCfFlipped ? (
          <span className="text-[13px] font-bold text-rose-300 px-2 py-0.5 rounded-lg bg-rose-500/10 border border-rose-500/30">
            FLIP · #{top.cfCount + 1}
          </span>
        ) : top.cfCount > 0 ? (
          <span className="text-[13px] font-bold text-amber-300 px-2 py-0.5 rounded-lg bg-amber-500/10 border border-amber-500/25">CF{top.cfCount}</span>
        ) : null}
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <PhaseDots fase={top.fase} color={col} />
        <span className={cn("text-[13px]",
          top.fase === 3 ? "text-amber-300" : topCfFlipped ? "text-rose-300" : "text-slate-400")}>{faseLabel}</span>
      </div>
      <div className={cn("mt-2 text-[13.5px]", aligned ? "text-emerald-400/90" : "text-amber-400/90")}>
        {aligned ? "✓ searah H4 master" : "⚠ berlawanan H4 — hati-hati"}
      </div>
      {VRCF_TF[top.tf] && (
        <div className="mt-1.5 text-[12.5px] text-slate-500">
          VR & CF di <span className="font-bold text-slate-400">{TF_SHORT[VRCF_TF[top.tf].vr]}</span>
          {VRCF_TF[top.tf].cfHigh && <> · CF-HIGH di <span className="font-bold text-slate-400">{TF_SHORT[VRCF_TF[top.tf].cfHigh!]}</span></>}
        </div>
      )}
      {sl && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-slate-800/40 border border-slate-700/50 px-2.5 py-1.5">
            <div className="dp-micro uppercase text-slate-500">eksekusi</div>
            <div className="text-[13px] font-semibold text-slate-200">{sl.tradeTF || top.tf}</div>
          </div>
          <div className="rounded-lg bg-slate-800/40 border border-slate-700/50 px-2.5 py-1.5">
            <div className="dp-micro uppercase text-slate-500">SL acuan</div>
            <div className="text-[13px] font-semibold text-slate-200">puncak VR</div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── NEWS CARD ────────────────────────────────────────────────────────────────
function NewsCard({ minutesUntilNews, newsBlackout, newsApproaching, nextEventName, nextEventTimeWIB }: {
  minutesUntilNews: number | null; newsBlackout: boolean; newsApproaching: boolean;
  nextEventName: string; nextEventTimeWIB: string;
}) {
  let tone = "text-slate-400", label = "CLEAR", icon = "✓";
  if (minutesUntilNews === null) { label = "NO DATA"; icon = "—"; }
  else if (newsBlackout) { tone = "text-rose-400"; label = "BLACKOUT"; icon = "⛔"; }
  else if (newsApproaching) { tone = "text-amber-400"; label = "DEKAT"; icon = "⚠"; }
  else if (minutesUntilNews < 0) { label = "LEWAT"; icon = "✓"; }
  else { tone = "text-emerald-400"; label = "AMAN"; icon = "✓"; }
  return (
    <div className="px-4 pb-4">
      <div className="flex items-center justify-between">
        <span className={cn("text-[20px] font-bold tabular-nums", tone)}>
          {minutesUntilNews !== null && minutesUntilNews >= 0 ? `${minutesUntilNews}m` : "—"}
        </span>
        <span className={cn("text-[13px] font-semibold", tone)}>{icon} {label}</span>
      </div>
      {nextEventName ? (
        <div className="mt-2">
          <div className="text-[13px] text-slate-300 truncate">{nextEventName}</div>
          <div className="text-[13px] text-slate-500 tabular-nums">{nextEventTimeWIB} WIB</div>
        </div>
      ) : (
        <div className="mt-2 dp-cap text-slate-500">Belum ada jadwal news</div>
      )}
    </div>
  );
}

// ── Sync pill ────────────────────────────────────────────────────────────────
function SyncPill({ label, onClick, busy, ok }: { label: string; onClick: () => void; busy: boolean; ok: boolean }) {
  return (
    <button onClick={onClick} disabled={busy} className={cn(
      "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[13.5px] font-semibold border transition-all duration-200",
      busy ? "bg-slate-800/40 border-slate-700/40 text-slate-500 cursor-wait"
        : ok ? "bg-slate-800/30 border-slate-700/50 text-slate-300 hover:border-indigo-500/50 hover:text-indigo-300 hover:bg-indigo-500/5"
        : "bg-slate-800/30 border-slate-700/50 text-slate-400 hover:border-indigo-500/50 hover:bg-indigo-500/5"
    )}>
      <RefreshCwIcon className={cn("w-3 h-3", busy && "animate-spin")} />
      {label}
    </button>
  );
}

// ============================================================================
// MAIN
// ============================================================================
export function DashboardPro(p: DashboardProProps) {
  const v = buildVerdict(p);
  const accentBg: Record<string, string> = {
    go: "from-amber-500/15 via-amber-500/5 to-transparent",
    wait: "from-indigo-500/12 via-indigo-500/4 to-transparent",
    stop: "from-rose-500/12 via-rose-500/4 to-transparent",
    idle: "from-slate-500/8 via-transparent to-transparent",
  };
  const accentText: Record<string, string> = {
    emerald: "text-emerald-400", rose: "text-rose-400",
    indigo: "text-indigo-300", amber: "text-amber-300", slate: "text-slate-300",
  };

  return (
    <div className="dp-scope relative px-5 py-5 max-w-[1200px] mx-auto space-y-4">
      <style>{DP_ANIM}</style>


      {/* ══ TOP STRIP: price + session + sync ══════════════════════════════ */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className={cn(
          "dp-card dp-glass relative flex items-center gap-5 rounded-2xl border px-6 py-3.5 transition-all duration-300 overflow-hidden",
          p.priceFlash === "up" ? "border-emerald-500/40 shadow-[0_0_30px_-8px_rgba(16,185,129,0.35)]"
            : p.priceFlash === "dn" ? "border-rose-500/40 shadow-[0_0_30px_-8px_rgba(244,63,94,0.35)]"
            : "border-slate-700/30",
        )}>
          {/* top edge */}
          <div className="absolute top-0 left-[10%] right-[10%] h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2.5">
              <span className="text-[14px] font-extrabold tracking-[0.1em] text-slate-100">{p.tvSymbol || "XAUUSD"}</span>
              {p.tvSymbolDesc && p.tvSymbolDesc !== p.tvSymbol && (
                <span className="text-[13px] text-slate-500 font-normal">{p.tvSymbolDesc}</span>
              )}
              <span className={cn(
                "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[13px] font-bold tracking-[0.12em]",
                p.livePrice ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20" : "bg-slate-800/60 text-slate-600 border border-slate-700/30"
              )}>
                {p.livePrice ? <><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> LIVE</> : <><WifiOffIcon className="w-2.5 h-2.5" /> OFF</>}
              </span>
            </div>
            <span className="text-[12px] text-slate-500 tabular-nums font-medium tracking-wide">{p.sess} · spread {p.spread}</span>
          </div>
          <div className={cn("text-[38px] font-black tabular-nums leading-none tracking-tighter",
            p.livePrice && "dp-flicker",
            p.priceFlash === "up" ? "text-emerald-300" : p.priceFlash === "dn" ? "text-rose-300" : "text-white"
          )}>{p.displayPrice}</div>
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          <SyncPill label={p.syncing ? "Reading…" : "Sync TV"} onClick={p.syncTV} busy={p.syncing} ok={p.tvStatus === "connected"} />
          <SyncPill label="SNR" onClick={p.syncSNR} busy={p.syncingSNR} ok />
          <SyncPill label="News" onClick={p.syncNews} busy={p.syncingNews} ok />
          <button onClick={() => p.setAutoSync(!p.autoSync)} className={cn(
            "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[13.5px] font-medium border transition-all",
            p.autoSync ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-300" : "bg-slate-800/40 border-slate-700/60 text-slate-500"
          )}>
            <span className={cn("w-1.5 h-1.5 rounded-full", p.autoSync ? "bg-emerald-400 animate-pulse" : "bg-slate-600")} />
            Auto
          </button>
          {p.setAutopilot && (
            <button onClick={() => p.setAutopilot!(!p.autopilot)} className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[13.5px] font-medium border transition-all",
              p.autopilot ? "bg-emerald-600/20 border-emerald-500/60 text-emerald-300 animate-pulse" : "bg-slate-800/40 border-slate-700/60 text-slate-500"
            )}>
              <span className="text-[11px]">🤖</span>
              {p.autopilot ? "Autopilot ON" : "Autopilot"}
            </button>
          )}
        </div>
      </div>

      {/* ══ HERO COMMAND CARD — Premium Glass Morphism ════════════════════ */}
      <div className={cn(
        "dp-shimmer relative rounded-2xl border overflow-hidden",
        v.tone === "go" ? "border-amber-500/40 dp-border-go" : v.tone === "stop" ? "border-rose-500/25" : "border-slate-700/40",
        "dp-glass"
      )}>
        {/* living grid + scanline */}
        <div className="dp-grid absolute inset-0 opacity-40 pointer-events-none" />
        <div className="dp-scanline" />
        {/* gradient overlay per state */}
        <div className={cn("absolute inset-0 pointer-events-none",
          v.tone === "go" ? "bg-gradient-to-br from-amber-500/12 via-amber-500/3 to-transparent"
            : v.tone === "stop" ? "bg-gradient-to-br from-rose-500/10 via-rose-500/3 to-transparent"
            : "bg-gradient-to-br from-indigo-500/8 via-indigo-500/2 to-transparent")} />
        {/* top edge glow */}
        <div className={cn("absolute top-0 left-[10%] right-[10%] h-px",
          v.tone === "go" ? "bg-gradient-to-r from-transparent via-amber-400/60 to-transparent"
            : v.tone === "stop" ? "bg-gradient-to-r from-transparent via-rose-400/40 to-transparent"
            : "bg-gradient-to-r from-transparent via-indigo-400/30 to-transparent")} />

        <div className="relative flex items-center gap-7 px-8 py-7">
          {/* icon container with ambient glow */}
          <div className="relative shrink-0">
            <div className={cn(
              "w-[72px] h-[72px] rounded-2xl flex items-center justify-center text-[38px] leading-none transition-all duration-300 border",
              v.tone === "go"
                ? "bg-gradient-to-br from-amber-500/20 to-amber-600/10 border-amber-400/30 shadow-[0_0_32px_rgba(251,191,36,0.3)]"
                : v.tone === "stop"
                ? "bg-gradient-to-br from-rose-500/20 to-rose-600/10 border-rose-400/25 shadow-[0_0_24px_rgba(244,63,94,0.2)]"
                : "bg-gradient-to-br from-indigo-500/15 to-indigo-600/5 border-indigo-400/20 shadow-[0_0_20px_rgba(99,145,255,0.15)]",
              v.tone === "go" && (p.blinkFast ? "scale-110" : "scale-100"),
            )}>{v.icon}</div>
            {/* ambient ring behind icon */}
            {v.tone === "go" && (
              <div className="absolute -inset-2 rounded-3xl opacity-30 pointer-events-none animate-pulse"
                style={{ background: "radial-gradient(circle, rgba(251,191,36,0.4), transparent 70%)" }} />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className={cn("text-[26px] font-extrabold tracking-tight leading-none", accentText[v.accent])}>
              {v.head}
            </div>
            <div className="text-[14px] text-slate-400/80 mt-2 leading-relaxed">{v.sub}</div>
            {/* inline chips */}
            {(() => {
              // compute active CMP + conti for hero chips
              const get2 = (tf: string) => p.tfData.find(d => d.tf === tf);
              const activeTF2 = ["M15","M30","H1","H4","DAILY"].find(tf => {
                const d = get2(tf); return d?.cmp && d.vr === "YA" && d.cf !== "YA";
              });
              const contiActive = (["DAILY","H4","H1"] as const).filter(tf => {
                const d = get2(tf); return d?.cmp && d.cmp !== "WAIT" && d.vr !== "YA";
              });
              return (
                <div className="flex flex-wrap gap-2 mt-3">
                  <Chip label="BIAS" value={p.h4Dir ? dirWord(p.h4Dir) : "—"} tone={p.h4Dir === "BULLISH" ? "emerald" : p.h4Dir === "BEARISH" ? "rose" : "slate"} />
                  <Chip label="PRIME" value={p.tfData.filter(d => d.fase === 3 && d.cmp && SETUP_TFS.includes(d.tf)).map(d => TF_SHORT[d.tf]).join("·") || "—"} tone="indigo" />
                  <Chip label="AKTIF" value={activeTF2 ? TF_SHORT[activeTF2] : "—"} tone={activeTF2 ? "indigo" : "slate"} />
                  <Chip label="CONTI" value={contiActive.length > 0 ? contiActive.map(tf => TF_SHORT[tf]).join("·") : "—"} tone={contiActive.length > 0 ? "amber" : "slate"} />
                  <Chip label="MOMENTUM" value={p.momentum === "BULL" ? "Beli" : p.momentum === "BEAR" ? "Jual" : p.momentum === "SCANNING" ? "Scan" : "Netral"} tone={p.momentum === "BULL" ? "emerald" : p.momentum === "BEAR" ? "rose" : "slate"} />
                  <Chip label="NEWS" value={p.newsBlackout ? `${p.minutesUntilNews}m ⛔` : p.minutesUntilNews !== null && p.minutesUntilNews >= 0 ? `${p.minutesUntilNews}m` : "clear"} tone={p.newsBlackout ? "rose" : "slate"} />
                </div>
              );
            })()}
          </div>
          <GradeRing grade={p.autoGrade.grade} />
        </div>
      </div>

      {/* ══ CHAIN RAIL ═════════════════════════════════════════════════════ */}
      <Card title="Chain Reaction" icon={<LayersIcon className="w-3.5 h-3.5" />}>
        <ChainRail tfData={p.tfData} h4Dir={p.h4Dir} />
      </Card>

      {/* ══ SEQUENCE per CMP (CMP → VR → CF) ═══════════════════════════════ */}
      <Card title="Sequence per CMP — CMP → VR → CF" icon={<ZapIcon className="w-3.5 h-3.5" />}
        right={<span className="text-[12.5px] text-slate-500">tiap timeframe</span>}>
        <SequenceList tfData={p.tfData} h4Dir={p.h4Dir} />
      </Card>

      {/* ══ STORYLINE — Active CMP + Conti Status ═══════════════════════════ */}
      <Card title="Storyline · Active CMP & Conti" icon={<ActivityIcon className="w-3.5 h-3.5" />}
        right={<span className="text-[12.5px] text-slate-500">fractal · TP = left barrier</span>}>
        <StorylineConti tfData={p.tfData} h4Dir={p.h4Dir} />
      </Card>

      {/* ══ VR SCALP — Scalp Sambil Nunggu ════════════════════════════════ */}
      <Card title="VR Scalp — Sambil Nunggu Setup Besar" icon={<ZapIcon className="w-3.5 h-3.5" />}
        right={<span className="text-[12.5px] text-slate-500">VR = CMP baru · scalp arah VR</span>}>
        <VrScalpPanel tfData={p.tfData} />
      </Card>

      {/* ══ 3-UP GRID ══════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        <Card title="Setup Fokus" icon={<TargetIcon className="w-3.5 h-3.5" />}>
          <SetupFocus tfData={p.tfData} h4Dir={p.h4Dir} />
        </Card>
        <Card title="Tekanan Pasar" icon={<GaugeIcon className="w-3.5 h-3.5" />}>
          <Pressure buyPct={p.buyPct} sellPct={p.sellPct} cumDelta={p.cumDelta} momentum={p.momentum}
            barDeltas={p.barDeltas} maxBarAbs={p.maxBarAbs} divergence={p.divergence} nTicks={p.nTicks} />
        </Card>
        <Card title="News" icon={<ClockIcon className="w-3.5 h-3.5" />}>
          <NewsCard minutesUntilNews={p.minutesUntilNews} newsBlackout={p.newsBlackout}
            newsApproaching={p.newsApproaching} nextEventName={p.nextEventName} nextEventTimeWIB={p.nextEventTimeWIB} />
        </Card>
      </div>

      {/* ══ SNR LADDER ═════════════════════════════════════════════════════ */}
      <Card title="SNR Price Ladder" icon={<ActivityIcon className="w-3.5 h-3.5" />}
        right={<span className="text-[12.5px] text-slate-500">resistance ▲ · support ▼</span>}>
        <SnrLadder aboveLevels={p.aboveLevels} belowLevels={p.belowLevels} atLevel={p.atLevel}
          cmpFloat={p.cmpFloat} displayPrice={p.displayPrice} livePrice={p.livePrice} />
      </Card>

      {/* ══ LOCAL MODEL SWITCHER ════════════════════════════════════════ */}
      <Card title="Local AI Model" icon={<CpuIcon className="w-3.5 h-3.5" />}
        right={<span className="text-[12.5px] text-slate-500">hemat Claude Sonnet · switch model lokal</span>}>
        <div className="px-5 pb-5">
          <LocalModelSwitcher />
        </div>
      </Card>

      <div className="text-center text-[12px] text-slate-600/60 pt-2 pb-6 tracking-widest uppercase font-medium">
        Chain Reaction v4.0 OVERLORD · Sultan Sniper Engine
      </div>
    </div>
  );
}

function Chip({ label, value, tone }: { label: string; value: string; tone: string }) {
  const c: Record<string, string> = {
    emerald: "text-emerald-300 border-emerald-500/25 bg-emerald-500/8",
    rose: "text-rose-300 border-rose-500/25 bg-rose-500/8",
    indigo: "text-indigo-300 border-indigo-500/25 bg-indigo-500/8",
    amber: "text-amber-300 border-amber-500/25 bg-amber-500/8",
    slate: "text-slate-300 border-slate-700/50 bg-slate-800/30",
  };
  return (
    <div className={cn("inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border backdrop-blur-sm", c[tone] || c.slate)}>
      <span className="text-[14px] font-bold uppercase tracking-[0.15em] opacity-50">{label}</span>
      <span className="text-[12px] font-bold tabular-nums">{value}</span>
    </div>
  );
}

