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
  LayersIcon, GaugeIcon, Volume2Icon, VolumeXIcon,
} from "lucide-react";

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
  blink: boolean; blinkFast: boolean;
}

// ── MOTION: 2 lapis (AMBIENT kalem · SIGNAL sangar) — vibe hacker ────────────
const DP_ANIM = `
/* data stream mengalir di konektor (ambient) */
@keyframes dp-flow { from { background-position: 0 0; } to { background-position: 24px 0; } }
/* napas pelan untuk step yang lagi DITUNGGU */
@keyframes dp-breathe {
  0%,100% { box-shadow: 0 0 0 0 rgba(79,124,255,0.0); border-color: rgba(79,124,255,0.5); }
  50%     { box-shadow: 0 0 0 5px rgba(79,124,255,0.12); border-color: rgba(79,124,255,0.95); }
}
/* SIGNAL: tajam + terang, cuma pas entry valid (CF fase-3) */
@keyframes dp-signal {
  0%,100% { box-shadow: 0 0 8px rgba(251,191,36,0.45); }
  50%     { box-shadow: 0 0 22px rgba(251,191,36,0.95), 0 0 44px rgba(251,191,36,0.4); }
}
/* scanline nyapu (hacker) */
@keyframes dp-scan { 0% { transform: translateX(-30%); opacity: 0; } 12% { opacity: .9; } 88% { opacity: .9; } 100% { transform: translateX(560%); opacity: 0; } }
/* grid hidup di hero */
@keyframes dp-grid { from { background-position: 0 0, 0 0; } to { background-position: 24px 24px, 24px 24px; } }
/* gradient border bergerak pas GO */
@keyframes dp-slide { from { background-position: 0 0; } to { background-position: 200% 0; } }
/* flicker halus angka harga (CRT) */
@keyframes dp-flicker { 0%,96%,100% { opacity: 1; } 97% { opacity: .82; } 98% { opacity: 1; } 99% { opacity: .9; } }
/* radar blip dot */
@keyframes dp-blip { 0% { transform: scale(.6); opacity: .9; } 100% { transform: scale(2.6); opacity: 0; } }
/* SNR proximity — baris menyala saat harga mendekat level (warna via --gc) */
@keyframes dp-approach-glow {
  0%,100% { box-shadow: inset 0 0 0 1px var(--gc-dim), 0 0 0 0 transparent; }
  50%     { box-shadow: inset 0 0 0 1px var(--gc), 0 0 16px -3px var(--gc); }
}
/* sweep tipis melintas baris yang lagi HOT */
@keyframes dp-approach-sweep { 0% { transform: translateX(-120%); } 100% { transform: translateX(420%); } }
/* sparkline bar denyut */
@keyframes dp-bar { 0%,100% { opacity: .55; } 50% { opacity: 1; } }

.dp-stream      { background-image: repeating-linear-gradient(90deg, var(--c) 0 7px, transparent 7px 14px); background-size: 24px 100%; animation: dp-flow .7s linear infinite; }
.dp-breathe     { animation: dp-breathe 3.2s ease-in-out infinite; }
.dp-signal      { animation: dp-signal .9s ease-in-out infinite; }
.dp-grid        { background-image: linear-gradient(rgba(79,124,255,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(79,124,255,.05) 1px, transparent 1px); background-size: 24px 24px; animation: dp-grid 7s linear infinite; }
.dp-flicker     { animation: dp-flicker 4s steps(1) infinite; }
.dp-bar         { animation: dp-bar 1.4s ease-in-out infinite; }
.dp-approach    { animation: dp-approach-glow 1.6s ease-in-out infinite; }
.dp-approach-hot { animation: dp-approach-glow .85s ease-in-out infinite; }
.dp-sweep       { position:absolute; top:0; bottom:0; width:38px; pointer-events:none;
                  background: linear-gradient(90deg, transparent, var(--gc), transparent);
                  opacity:.35; animation: dp-approach-sweep 1.8s ease-in-out infinite; }
.dp-scanline    { position: absolute; top: 0; bottom: 0; width: 90px; pointer-events: none;
                  background: linear-gradient(90deg, transparent, rgba(79,124,255,0.10), transparent);
                  animation: dp-scan 5.5s ease-in-out infinite; }
.dp-border-go::before {
  content: ''; position: absolute; inset: 0; border-radius: 1rem; padding: 1px;
  background: linear-gradient(90deg, #fbbf24, #f59e0b, #fbbf24, #f59e0b); background-size: 200% 100%;
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude; animation: dp-slide 2s linear infinite; pointer-events: none;
}
/* radar ping (dipakai via class biar bisa dimatikan reduced-motion) */
@keyframes dp-ping-k { 0% { transform: scale(.6); opacity: .85; } 100% { transform: scale(2.6); opacity: 0; } }
.dp-ping { animation: dp-ping-k 1.1s ease-out infinite; }

/* ── DESIGN TOKENS (satu sumber) ─────────────────────────────────────────── */
.dp-scope {
  /* elevation */
  --dp-sh-1: 0 1px 0 0 rgba(255,255,255,.025) inset, 0 8px 24px -14px rgba(0,0,0,.66);
  --dp-sh-2: 0 1px 0 0 rgba(255,255,255,.04) inset, 0 16px 44px -18px rgba(0,0,0,.78);
  /* skala spasi 4pt */
  --dp-1: 4px; --dp-2: 8px; --dp-3: 12px; --dp-4: 16px; --dp-5: 24px; --dp-6: 32px;
}
/* ── TYPE SCALE (ganti px ad-hoc — 1 tangga konsisten) ───────────────────── */
.dp-micro { font-size: 9px;    line-height: 1.2;  letter-spacing: .14em; }
.dp-label { font-size: 10.5px; line-height: 1.25; letter-spacing: .12em; }
.dp-cap   { font-size: 11.5px; line-height: 1.35; }
.dp-body  { font-size: 13px;   line-height: 1.4; }
.dp-sub   { font-size: 15px;   line-height: 1.3; }
.dp-h     { font-size: 20px;   line-height: 1.15; }
.dp-xl    { font-size: 28px;   line-height: 1.05; }
.dp-num   { font-variant-numeric: tabular-nums; }
/* ── MATERIAL ────────────────────────────────────────────────────────────── */
.dp-card  { box-shadow: var(--dp-sh-1); transition: box-shadow .25s ease, border-color .25s ease; }
.dp-card:hover { box-shadow: var(--dp-sh-2); }

/* ── REDUCED MOTION: nemenin nunggu lama / device lemah / aksesibilitas ──── */
@media (prefers-reduced-motion: reduce) {
  .dp-stream, .dp-breathe, .dp-signal, .dp-grid, .dp-flicker, .dp-bar,
  .dp-approach, .dp-approach-hot, .dp-ping, .animate-pulse,
  .dp-border-go::before { animation: none !important; }
  .dp-sweep, .dp-scanline { display: none !important; }
  .dp-card { transition: none !important; }
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
      "dp-card relative rounded-2xl border border-slate-800/70 bg-slate-900/50 backdrop-blur-sm",
      glow === "go" && "ring-1 ring-amber-400/40",
      className
    )}>
      {title && (
        <div className="flex items-center justify-between px-4 pt-3.5 pb-2">
          <div className="flex items-center gap-2 text-slate-400">
            {icon}
            <span className="dp-label font-semibold uppercase">{title}</span>
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
    <div className="relative w-[92px] h-[92px] shrink-0">
      <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
        <circle cx="40" cy="40" r={R} fill="none" stroke="#1e293b" strokeWidth="7" />
        <circle cx="40" cy="40" r={R} fill="none" stroke={g.ring} strokeWidth="7"
          strokeLinecap="round" strokeDasharray={C} strokeDashoffset={off}
          style={{ transition: "stroke-dashoffset 0.7s ease" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[26px] font-bold leading-none tabular-nums" style={{ color: g.color }}>{grade}</span>
        <span className="dp-micro uppercase text-slate-500 mt-0.5">grade</span>
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
          "h-1.5 rounded-full transition-all",
          n <= fase ? "w-4" : "w-1.5",
          n <= fase
            ? color === "emerald" ? "bg-emerald-400" : color === "rose" ? "bg-rose-400" : "bg-indigo-400"
            : "bg-slate-700"
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
    <div className="px-4 pb-4">
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
                "flex-1 min-w-0 rounded-xl border px-2.5 py-2.5 text-center transition-all",
                isTrigger && "border-dashed",
                has ? (isTrigger ? "bg-slate-900/40" : "bg-slate-900/70") : "bg-slate-900/30 opacity-50",
                isMaster ? "border-indigo-500/50"
                  : isTrigger ? (has ? "border-amber-500/40" : "border-amber-500/20")
                  : has ? "border-slate-700/70" : "border-slate-800/50",
                // ring entry HANYA buat setup — M5 trigger gak pernah dianggap entry-ready
                !isTrigger && d?.fase === 3 && aligned && "ring-1 ring-amber-400/60 dp-signal",
                !isTrigger && d?.fase === 2 && aligned && "dp-breathe"
              )}>
                <div className="flex items-center justify-center gap-1">
                  <span className={cn("text-[11px] font-bold tracking-wide",
                    isMaster ? "text-indigo-300" : isTrigger ? "text-amber-300/90" : "text-slate-300")}>{TF_SHORT[tf]}</span>
                  {isMaster && <span className="text-[8px] text-indigo-400">★</span>}
                </div>
                {isTrigger && (
                  <div className="text-[7px] font-bold uppercase tracking-[0.12em] text-amber-500/70 leading-none -mt-0.5 mb-0.5">trigger</div>
                )}
                <div className={cn("text-[12px] font-bold tabular-nums mt-1",
                  col === "emerald" ? "text-emerald-400" : col === "rose" ? "text-rose-400" : "text-slate-600")}>
                  {has ? dirWord(d!.cmp) : "—"}
                </div>
                {/* trigger = monitor momentum, gak ada fase setup → skip phase dots */}
                {!isTrigger && (
                  <div className="flex justify-center mt-1.5">
                    <PhaseDots fase={d?.fase || 0} color={col} />
                  </div>
                )}
                {isTrigger ? (
                  // status running vs pullback — biar tau breakout langsung jalan atau balik dulu
                  has && (
                    <div className={cn("mt-1.5 text-[8px] font-bold uppercase tracking-wide",
                      aligned ? "text-emerald-400/80" : "text-rose-400/80")}>
                      {aligned ? "running" : "pullback"}
                    </div>
                  )
                ) : has && d!.fase === 3 ? (
                  // ⚡ ENTRY AKTIF — CF fired, boleh entry
                  <div className="mt-1.5 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-amber-500/15 border border-amber-400/40">
                    <span className="text-[8px] font-bold text-amber-300 tabular-nums">
                      ⚡ CF{d!.cfCount || 1}{d!.cfType ? ` ${d!.cfType}` : ""}
                    </span>
                  </div>
                ) : has && d!.fase === 2 && (d!.cfCount || 0) > 0 ? (
                  // 🔄 CF FLIP — entry ILANG, sub-TF balik arah. Nunggu CF berikutnya.
                  <div className="mt-1.5 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-rose-500/10 border border-rose-500/30">
                    <span className="text-[8px] font-bold text-rose-300 tabular-nums">
                      FLIP · #{d!.cfCount + 1}
                    </span>
                  </div>
                ) : null}
              </div>
              {/* connector — data stream mengalir kalau selaras */}
              {i < RAIL_TFS.length - 1 && (
                connOn ? (
                  <div className="dp-stream w-3 sm:w-4 h-[2px] mx-0.5 shrink-0 rounded-full"
                    style={{ ["--c" as string]: h4Dir === "BULLISH" ? "#10b981" : "#f43f5e" }} />
                ) : (
                  <div className="w-3 sm:w-4 h-[2px] mx-0.5 shrink-0 rounded-full bg-slate-800" />
                )
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-2.5 text-center text-[10px] text-slate-500">
        {present.filter(d => d.cmp === h4Dir).length}/{present.length} timeframe selaras H4 master
        {h4Dir && <span className={cn("ml-1.5 font-semibold", h4Dir === "BULLISH" ? "text-emerald-400" : "text-rose-400")}>· {dirWord(h4Dir)}</span>}
      </div>
    </div>
  );
}

// ── SEQUENCE per CMP (CMP → VR → CF) — eksplisit tiap timeframe ───────────────
function SequenceList({ tfData, h4Dir }: { tfData: TFRow[]; h4Dir: string }) {
  const rows = SETUP_TFS.map(tf => tfData.find(d => d.tf === tf)).filter(d => d && d.cmp) as TFRow[];
  if (rows.length === 0)
    return <div className="pb-3"><State icon={<LayersIcon className="w-4 h-4" />} title="Belum ada CMP aktif" sub="sync tradingview untuk mulai" pulse /></div>;

  const Step = ({ label, done, active, waiting, flipped, tone, sub, tfTag }: {
    label: string; done: boolean; active?: boolean; waiting?: boolean; flipped?: boolean; tone: string; sub?: string; tfTag?: string;
  }) => (
    <div className="flex flex-col items-center gap-1 shrink-0 w-9">
      <div className={cn(
        "w-7 h-7 rounded-full border-2 flex items-center justify-center text-[10px] font-bold transition-all",
        active
          ? "border-amber-400 bg-amber-400/15 text-amber-300 dp-signal"
          : done
            ? tone === "emerald" ? "border-emerald-500 bg-emerald-500/15 text-emerald-300"
              : tone === "rose" ? "border-rose-500 bg-rose-500/15 text-rose-300"
              : "border-indigo-500 bg-indigo-500/15 text-indigo-300"
            : flipped
              ? "border-rose-500 bg-rose-500/10 text-rose-300 border-dashed"
              : waiting
                ? "border-indigo-500 bg-indigo-500/10 text-indigo-300 dp-breathe"
                : "border-slate-700 bg-slate-800/40 text-slate-600"
      )}>
        {done || active ? "✓" : flipped ? "↻" : waiting ? "◌" : "○"}
      </div>
      <span className={cn("text-[8.5px] font-semibold tracking-wide",
        done || active || waiting ? "text-slate-300" : "text-slate-600")}>{label}</span>
      {tfTag && <span className="text-[7.5px] font-bold tracking-wide text-slate-500 leading-none">@{tfTag}</span>}
      {sub && <span className="text-[8px] text-amber-400/90 tabular-nums leading-none">{sub}</span>}
    </div>
  );

  // konektor sejajar TENGAH lingkaran: circle h-7 (28px) → center 14px, line 2px → mt 13px
  const Conn = ({ on, tone }: { on: boolean; tone: string }) => (
    on ? (
      <div className="dp-stream flex-1 h-[2px] mx-1 mt-[13px] rounded-full self-start"
        style={{ ["--c" as string]: tone === "emerald" ? "#10b981" : tone === "rose" ? "#f43f5e" : "#4f7cff" }} />
    ) : (
      <div className="flex-1 h-[2px] mx-1 mt-[13px] rounded-full self-start bg-slate-800" />
    )
  );

  return (
    <div className="px-3 pb-3 space-y-1.5">
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
            "rounded-xl border px-3 py-2.5 flex items-center gap-3",
            d.fase === 3 && aligned ? "border-amber-500/40 bg-amber-500/[0.04]"
              : cfFlipped ? "border-rose-500/30 bg-rose-500/[0.03]"
              : isMaster ? "border-indigo-500/30 bg-slate-900/40"
              : "border-slate-800/70 bg-slate-900/40"
          )}>
            {/* TF + arah */}
            <div className="w-16 shrink-0">
              <div className="flex items-center gap-1">
                <span className={cn("text-[12px] font-bold", isMaster ? "text-indigo-300" : "text-slate-200")}>{TF_SHORT[d.tf]}</span>
                {isMaster && <span className="text-[8px] text-indigo-400">★</span>}
              </div>
              <div className={cn("text-[11px] font-bold",
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
            <div className="w-24 shrink-0 text-right">
              <div className={cn("text-[10px] font-semibold",
                d.fase === 3 ? "text-amber-300" : cfFlipped ? "text-rose-300" : d.fase === 2 ? "text-indigo-300" : "text-slate-400")}>
                {faseLabel}
              </div>
              <div className={cn("text-[8.5px]", aligned ? "text-emerald-500/80" : "text-amber-500/80")}>
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
        <span className={cn("relative text-[10.5px] w-12 shrink-0 truncate", near ? "text-slate-200" : "text-slate-400")}>{l.short}</span>
        <span className={cn("relative text-[12px] font-semibold tabular-nums flex-1 text-right", near ? "text-slate-50" : "text-slate-200")}>{l.price.toFixed(2)}</span>
        <span className="relative text-[9.5px] tabular-nums w-14 text-right font-semibold" style={near ? { color: `rgb(${rgb})` } : { color: "#64748b" }}>
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
                <span className="text-[11px] tabular-nums text-slate-400">{nearest.l.price.toFixed(2)}</span>
                <span className="ml-auto text-[13px] font-bold tabular-nums" style={{ color: nNear ? `rgb(${nRgb})` : "#94a3b8" }}>
                  {nHot ? "▸ " : ""}{nearest.dist.toFixed(1)}p
                </span>
              </div>
              <div className="mt-1.5 h-1 rounded-full bg-slate-800 overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${meterPct}%`, background: `linear-gradient(90deg, rgba(${nRgb},0.35), rgba(${nRgb},${nNear ? 0.95 : 0.4}))` }} />
              </div>
            </>
          ) : <span className="text-[10px] text-slate-600">— belum ada level —</span>}
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
        <div className="my-1.5 mx-1.5 rounded-xl bg-gradient-to-r from-indigo-500/10 via-indigo-500/15 to-indigo-500/10 border border-indigo-500/30 px-3 py-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={cn("w-2 h-2 rounded-full", livePrice ? "bg-emerald-400 animate-pulse" : "bg-slate-600")} />
            <span className="dp-micro uppercase text-indigo-300/80">harga</span>
          </div>
          <span className="text-[17px] font-bold tabular-nums text-indigo-200">{displayPrice}</span>
        </div>
        {atLevel.length > 0 && (
          <div className="mx-3 mb-1 flex items-center gap-1.5 text-[9.5px] font-semibold text-amber-300">
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
    <div className="px-4 pb-4">
      {nTicks < 5 ? (
        <State icon={<GaugeIcon className="w-4 h-4" />} title="Mengumpulkan tick…" sub="butuh ≥5 tick" pulse />
      ) : (
        <>
          {/* split bar */}
          <div className="flex items-center gap-2 mb-2.5">
            <span className="text-[11px] font-bold tabular-nums text-emerald-400 w-9">{buyPct}%</span>
            <div className="flex-1 h-2 rounded-full overflow-hidden bg-slate-800 flex">
              <div className="h-full bg-emerald-500/80 transition-all duration-500" style={{ width: `${buyPct}%` }} />
              <div className="h-full bg-rose-500/80 transition-all duration-500" style={{ width: `${sellPct}%` }} />
            </div>
            <span className="text-[11px] font-bold tabular-nums text-rose-400 w-9 text-right">{sellPct}%</span>
          </div>
          {/* sparkline bars */}
          <div className="flex items-end justify-between gap-1 h-12 mb-2.5">
            {barDeltas.map((d, i) => {
              const h = Math.max(8, Math.abs(d) / maxBarAbs * 100);
              return (
                <div key={i} className="flex-1 flex flex-col justify-end h-full">
                  <div className={cn("dp-bar w-full rounded-sm transition-all", d >= 0 ? "bg-emerald-500/60" : "bg-rose-500/60")}
                    style={{ height: `${h}%`, animationDelay: `${i * 0.12}s` }} />
                </div>
              );
            })}
          </div>
          <div className="flex items-center justify-between">
            <span className={cn("text-[11px] font-semibold", momCol)}>
              {momentum === "BULL" ? "▲ Tekanan Beli" : momentum === "BEAR" ? "▼ Tekanan Jual" : "─ Seimbang"}
            </span>
            <span className={cn("text-[11px] tabular-nums font-medium", cumDelta >= 0 ? "text-emerald-400" : "text-rose-400")}>
              Δ {cumDelta > 0 ? "+" : ""}{cumDelta}
            </span>
          </div>
          {divergence && (
            <div className="mt-2 text-[9.5px] text-amber-300/90 bg-amber-500/10 border border-amber-500/25 rounded-lg px-2 py-1">
              ⚠ Divergence — tekanan berbalik arah
            </div>
          )}
        </>
      )}
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
    <div className="px-4 pb-4">
      <div className="flex items-baseline gap-2.5">
        <span className="dp-xl font-bold tracking-tight text-slate-100">{TF_SHORT[top.tf]}</span>
        <span className={cn("text-[18px] font-bold",
          col === "emerald" ? "text-emerald-400" : col === "rose" ? "text-rose-400" : "text-slate-500")}>
          {dirWord(top.cmp)}
        </span>
        {top.fase === 3 ? (
          <span className="text-[11px] font-semibold text-amber-300 px-1.5 py-0.5 rounded-md bg-amber-500/15 border border-amber-400/40">
            ⚡ CF{top.cfCount || 1}{top.cfType ? ` ${top.cfType}` : ""}
          </span>
        ) : topCfFlipped ? (
          <span className="text-[11px] font-semibold text-rose-300 px-1.5 py-0.5 rounded-md bg-rose-500/10 border border-rose-500/30">
            FLIP · #{top.cfCount + 1}
          </span>
        ) : top.cfCount > 0 ? (
          <span className="text-[11px] font-semibold text-amber-300 px-1.5 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/25">CF{top.cfCount}</span>
        ) : null}
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <PhaseDots fase={top.fase} color={col} />
        <span className={cn("text-[11px]",
          top.fase === 3 ? "text-amber-300" : topCfFlipped ? "text-rose-300" : "text-slate-400")}>{faseLabel}</span>
      </div>
      <div className={cn("mt-2 text-[10.5px]", aligned ? "text-emerald-400/90" : "text-amber-400/90")}>
        {aligned ? "✓ searah H4 master" : "⚠ berlawanan H4 — hati-hati"}
      </div>
      {VRCF_TF[top.tf] && (
        <div className="mt-1.5 text-[9.5px] text-slate-500">
          VR & CF di <span className="font-bold text-slate-400">{TF_SHORT[VRCF_TF[top.tf].vr]}</span>
          {VRCF_TF[top.tf].cfHigh && <> · CF-HIGH di <span className="font-bold text-slate-400">{TF_SHORT[VRCF_TF[top.tf].cfHigh!]}</span></>}
        </div>
      )}
      {sl && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-slate-800/40 border border-slate-700/50 px-2.5 py-1.5">
            <div className="dp-micro uppercase text-slate-500">eksekusi</div>
            <div className="text-[11px] font-semibold text-slate-200">{sl.tradeTF || top.tf}</div>
          </div>
          <div className="rounded-lg bg-slate-800/40 border border-slate-700/50 px-2.5 py-1.5">
            <div className="dp-micro uppercase text-slate-500">SL acuan</div>
            <div className="text-[11px] font-semibold text-slate-200">puncak VR</div>
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
        <span className={cn("text-[11px] font-semibold", tone)}>{icon} {label}</span>
      </div>
      {nextEventName ? (
        <div className="mt-2">
          <div className="text-[11px] text-slate-300 truncate">{nextEventName}</div>
          <div className="text-[10px] text-slate-500 tabular-nums">{nextEventTimeWIB} WIB</div>
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
      "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10.5px] font-medium border transition-all",
      busy ? "bg-slate-800/50 border-slate-700/50 text-slate-500 cursor-wait"
        : ok ? "bg-slate-800/40 border-slate-700/60 text-slate-300 hover:border-indigo-500/50 hover:text-indigo-300"
        : "bg-slate-800/40 border-slate-700/60 text-slate-400 hover:border-indigo-500/50"
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
    <div className="dp-scope px-4 py-4 max-w-[1180px] mx-auto space-y-3.5">
      <style>{DP_ANIM}</style>

      {/* ══ TOP STRIP: price + session + sync ══════════════════════════════ */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className={cn(
          "dp-card flex items-center gap-3 rounded-2xl border border-slate-800/70 bg-slate-900/50 px-4 py-2.5",
          p.priceFlash === "up" && "border-emerald-600/40",
          p.priceFlash === "dn" && "border-rose-600/40",
        )}>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-semibold tracking-wide text-slate-300">XAUUSD</span>
              <span className={cn("inline-flex items-center gap-1 text-[9px]", p.livePrice ? "text-emerald-400" : "text-slate-600")}>
                {p.livePrice ? <WifiIcon className="w-2.5 h-2.5" /> : <WifiOffIcon className="w-2.5 h-2.5" />}
                {p.livePrice ? "LIVE" : "OFF"}
              </span>
            </div>
            <span className="text-[9px] text-slate-500 tabular-nums">{p.sess} · spr {p.spread}</span>
          </div>
          <div className={cn("text-[30px] font-bold tabular-nums leading-none",
            p.livePrice && "dp-flicker",
            p.priceFlash === "up" ? "text-emerald-300" : p.priceFlash === "dn" ? "text-rose-300" : "text-slate-100"
          )}>{p.displayPrice}</div>
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          <SyncPill label={p.syncing ? "Reading…" : "Sync TV"} onClick={p.syncTV} busy={p.syncing} ok={p.tvStatus === "connected"} />
          <SyncPill label="SNR" onClick={p.syncSNR} busy={p.syncingSNR} ok />
          <SyncPill label="News" onClick={p.syncNews} busy={p.syncingNews} ok />
          <button onClick={() => p.setAutoSync(!p.autoSync)} className={cn(
            "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10.5px] font-medium border transition-all",
            p.autoSync ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-300" : "bg-slate-800/40 border-slate-700/60 text-slate-500"
          )}>
            <span className={cn("w-1.5 h-1.5 rounded-full", p.autoSync ? "bg-emerald-400 animate-pulse" : "bg-slate-600")} />
            Auto
          </button>
        </div>
      </div>

      {/* ══ HERO COMMAND CARD ══════════════════════════════════════════════ */}
      <div className={cn(
        "relative rounded-2xl border overflow-hidden",
        v.tone === "go" ? "border-amber-500/40 dp-border-go" : v.tone === "stop" ? "border-rose-500/30" : "border-slate-800/70",
        "bg-slate-900/50"
      )}>
        {/* grid hidup + scanline (hacker ambient) */}
        <div className="dp-grid absolute inset-0 opacity-50 pointer-events-none" />
        <div className="dp-scanline" />
        <div className={cn("absolute inset-0 bg-gradient-to-r pointer-events-none", accentBg[v.tone])} />
        <div className="relative flex items-center gap-5 px-6 py-5">
          <div className={cn("text-[40px] leading-none shrink-0 transition-transform duration-300",
            v.tone === "go" ? "drop-shadow-[0_0_14px_rgba(251,191,36,0.7)]" : v.tone === "stop" ? "drop-shadow-[0_0_12px_rgba(244,63,94,0.5)]" : "",
            v.tone === "go" && (p.blinkFast ? "scale-110" : "scale-100"),
          )}>{v.icon}</div>
          <div className="flex-1 min-w-0">
            <div className={cn("dp-xl font-bold tracking-tight", accentText[v.accent])}>{v.head}</div>
            <div className="dp-body text-slate-400 mt-0.5">{v.sub}</div>
          </div>
          <GradeRing grade={p.autoGrade.grade} />
        </div>
        {/* chips */}
        <div className="relative flex flex-wrap gap-2 px-6 pb-4">
          <Chip label="BIAS" value={p.h4Dir ? dirWord(p.h4Dir) : "—"} tone={p.h4Dir === "BULLISH" ? "emerald" : p.h4Dir === "BEARISH" ? "rose" : "slate"} />
          <Chip label="PRIME" value={p.tfData.filter(d => d.fase === 3 && d.cmp && SETUP_TFS.includes(d.tf)).map(d => TF_SHORT[d.tf]).join("·") || "—"} tone="indigo" />
          <Chip label="MOMENTUM" value={p.momentum === "BULL" ? "Beli" : p.momentum === "BEAR" ? "Jual" : p.momentum === "SCANNING" ? "Scan" : "Netral"} tone={p.momentum === "BULL" ? "emerald" : p.momentum === "BEAR" ? "rose" : "slate"} />
          <Chip label="NEWS" value={p.newsBlackout ? `${p.minutesUntilNews}m ⛔` : p.minutesUntilNews !== null && p.minutesUntilNews >= 0 ? `${p.minutesUntilNews}m` : "clear"} tone={p.newsBlackout ? "rose" : "slate"} />
        </div>
      </div>

      {/* ══ CHAIN RAIL ═════════════════════════════════════════════════════ */}
      <Card title="Chain Reaction" icon={<LayersIcon className="w-3.5 h-3.5" />}>
        <ChainRail tfData={p.tfData} h4Dir={p.h4Dir} />
      </Card>

      {/* ══ SEQUENCE per CMP (CMP → VR → CF) ═══════════════════════════════ */}
      <Card title="Sequence per CMP — CMP → VR → CF" icon={<ZapIcon className="w-3.5 h-3.5" />}
        right={<span className="text-[9.5px] text-slate-500">tiap timeframe</span>}>
        <SequenceList tfData={p.tfData} h4Dir={p.h4Dir} />
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
        right={<span className="text-[9.5px] text-slate-500">resistance ▲ · support ▼</span>}>
        <SnrLadder aboveLevels={p.aboveLevels} belowLevels={p.belowLevels} atLevel={p.atLevel}
          cmpFloat={p.cmpFloat} displayPrice={p.displayPrice} livePrice={p.livePrice} />
      </Card>

      <div className="text-center text-[9px] text-slate-700 pt-1 pb-4">
        ChainReaction v2 · Clean Institutional · port 3003 (eksperimen)
      </div>
    </div>
  );
}

function Chip({ label, value, tone }: { label: string; value: string; tone: string }) {
  const c: Record<string, string> = {
    emerald: "text-emerald-300 border-emerald-500/30 bg-emerald-500/8",
    rose: "text-rose-300 border-rose-500/30 bg-rose-500/8",
    indigo: "text-indigo-300 border-indigo-500/30 bg-indigo-500/8",
    amber: "text-amber-300 border-amber-500/30 bg-amber-500/8",
    slate: "text-slate-300 border-slate-700/60 bg-slate-800/40",
  };
  return (
    <div className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border", c[tone] || c.slate)}>
      <span className="dp-micro uppercase opacity-60">{label}</span>
      <span className="dp-cap font-semibold tabular-nums">{value}</span>
    </div>
  );
}
