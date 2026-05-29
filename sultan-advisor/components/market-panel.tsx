"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { DEFAULT_MARKET_CONTEXT } from "@/lib/system-prompt";
import { cn } from "@/lib/utils";
import {
  RefreshCwIcon, WifiIcon, WifiOffIcon,
  ZapIcon, ClockIcon, PencilIcon, CheckIcon, XIcon,
  BarChart2Icon, ArrowUpIcon, ArrowDownIcon, GlobeIcon,
} from "lucide-react";

type CtxVar = { id: string; variableName: string; label: string; value: string };

interface Props {
  onAutoAnalysis?: (prompt: string) => void;
  onPriceUpdate?:  (price: string) => void;
  layout?: "panel" | "dashboard";
}

// ── CSS animations injected once ─────────────────────────────────────────────
const ANIM_CSS = `
@keyframes scan-h {
  0%   { transform: translateX(-100%); opacity: 0; }
  20%  { opacity: 1; }
  80%  { opacity: 1; }
  100% { transform: translateX(400%); opacity: 0; }
}
@keyframes scan-v {
  0%   { transform: translateY(-100%); opacity: 0; }
  20%  { opacity: 0.6; }
  80%  { opacity: 0.6; }
  100% { transform: translateY(600%); opacity: 0; }
}
@keyframes glow-breathe {
  0%,100% { box-shadow: 0 0 8px rgba(245,158,11,0.25), inset 0 0 12px rgba(245,158,11,0.04); }
  50%      { box-shadow: 0 0 28px rgba(245,158,11,0.65), inset 0 0 24px rgba(245,158,11,0.10); }
}
@keyframes glow-blue {
  0%,100% { box-shadow: 0 0 6px rgba(59,130,246,0.2); }
  50%      { box-shadow: 0 0 22px rgba(59,130,246,0.55); }
}
@keyframes glow-red {
  0%,100% { box-shadow: 0 0 8px rgba(248,113,113,0.2); }
  50%      { box-shadow: 0 0 24px rgba(248,113,113,0.5); }
}
@keyframes flash-up {
  0%   { background: rgba(52,211,153,0.30); }
  100% { background: transparent; }
}
@keyframes flash-dn {
  0%   { background: rgba(248,113,113,0.30); }
  100% { background: transparent; }
}
@keyframes delta-fill {
  from { width: 0%; }
}
@keyframes pulse-dot {
  0%,100% { opacity:1; transform:scale(1); }
  50%      { opacity:0.2; transform:scale(1.6); }
}
@keyframes pulse-dot-fast {
  0%,100% { opacity:1; transform:scale(1); }
  50%      { opacity:0.1; transform:scale(2); }
}
@keyframes row-fire {
  0%,100% { background: rgba(245,158,11,0.10); }
  50%      { background: rgba(245,158,11,0.26); }
}
@keyframes row-fire-fast {
  0%,100% { background: rgba(245,158,11,0.15); border-left-color: rgba(245,158,11,0.7); }
  50%      { background: rgba(245,158,11,0.32); border-left-color: rgba(245,158,11,1.0); }
}
@keyframes chain-flow {
  0%   { opacity:0.2; }
  50%  { opacity:1; }
  100% { opacity:0.2; }
}
@keyframes neon-border {
  0%,100% { border-color: rgba(192,38,211,0.25); }
  50%      { border-color: rgba(192,38,211,0.75); box-shadow: 0 0 16px rgba(192,38,211,0.15); }
}
@keyframes amber-border {
  0%,100% { border-color: rgba(245,158,11,0.4); box-shadow: 0 0 8px rgba(245,158,11,0.1); }
  50%      { border-color: rgba(245,158,11,0.9); box-shadow: 0 0 22px rgba(245,158,11,0.3); }
}
@keyframes sniper-flash {
  0%,49%  { opacity:1; }
  50%,100%{ opacity:0.15; }
}
@keyframes marquee-left {
  0%   { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}
@keyframes crt-flicker {
  0%,97%,100% { opacity:1; }
  98%          { opacity:0.85; }
  99%          { opacity:1; }
}
@keyframes matrix-fall {
  0%   { transform: translateY(-40px); opacity:0; }
  20%  { opacity:0.6; }
  80%  { opacity:0.4; }
  100% { transform: translateY(200px); opacity:0; }
}
@keyframes price-glow {
  0%,100% { text-shadow: 0 0 10px rgba(245,158,11,0.3); }
  50%      { text-shadow: 0 0 30px rgba(245,158,11,0.8), 0 0 60px rgba(245,158,11,0.3); }
}
@keyframes price-glow-up {
  0%,100% { text-shadow: 0 0 10px rgba(52,211,153,0.4); }
  50%      { text-shadow: 0 0 30px rgba(52,211,153,0.9), 0 0 60px rgba(52,211,153,0.4); }
}
@keyframes price-glow-dn {
  0%,100% { text-shadow: 0 0 10px rgba(248,113,113,0.4); }
  50%      { text-shadow: 0 0 30px rgba(248,113,113,0.9), 0 0 60px rgba(248,113,113,0.4); }
}
.anim-scan-h        { animation: scan-h 3.5s ease-in-out infinite; }
.anim-scan-v        { animation: scan-v 4s ease-in-out infinite; }
.anim-glow-breathe  { animation: glow-breathe 1.6s ease-in-out infinite; }
.anim-glow-blue     { animation: glow-blue 1.8s ease-in-out infinite; }
.anim-glow-red      { animation: glow-red 1.8s ease-in-out infinite; }
.anim-flash-up      { animation: flash-up 0.55s ease-out forwards; }
.anim-flash-dn      { animation: flash-dn 0.55s ease-out forwards; }
.anim-delta-fill    { animation: delta-fill 0.5s ease-out; }
.anim-pulse-dot     { animation: pulse-dot 1s ease-in-out infinite; }
.anim-pulse-dot-fast{ animation: pulse-dot-fast 0.4s ease-in-out infinite; }
.anim-row-fire      { animation: row-fire 1.0s ease-in-out infinite; }
.anim-row-fire-fast { animation: row-fire-fast 0.5s ease-in-out infinite; }
.anim-chain-flow    { animation: chain-flow 1.2s ease-in-out infinite; }
.anim-neon-border   { animation: neon-border 1.8s ease-in-out infinite; }
.anim-amber-border  { animation: amber-border 0.8s ease-in-out infinite; }
.anim-sniper        { animation: sniper-flash 0.5s step-end infinite; }
.anim-marquee       { animation: marquee-left 12s linear infinite; }
.anim-crt           { animation: crt-flicker 8s infinite; }
.anim-price-glow    { animation: price-glow 2s ease-in-out infinite; }
.anim-price-glow-up { animation: price-glow-up 1.5s ease-in-out infinite; }
.anim-price-glow-dn { animation: price-glow-dn 1.5s ease-in-out infinite; }

/* ══ 2-TIER MOTION SYSTEM ══════════════════════════════════════════════
   AMBIENT = kalem, nemenin nunggu (anti-bosen, gak bikin mata capek)
   SIGNAL  = tajam & terang, CUMA buat yang actionable (entry valid) */
@keyframes ambient-breathe {
  0%,100% { opacity:0.5; }
  50%      { opacity:1; }
}
@keyframes ambient-ring {
  0%,100% { box-shadow: 0 0 0 0 rgba(34,211,238,0); }
  50%      { box-shadow: 0 0 0 3px rgba(34,211,238,0.14); }
}
@keyframes ambient-flow {
  0%   { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}
@keyframes ambient-dot {
  0%,100% { opacity:0.35; transform:scale(0.85); }
  50%      { opacity:0.9;  transform:scale(1.1); }
}
@keyframes signal-pulse {
  0%,100% { box-shadow: 0 0 10px rgba(245,158,11,0.35); transform: scale(1); }
  50%      { box-shadow: 0 0 28px rgba(245,158,11,0.9);  transform: scale(1.02); }
}
@keyframes signal-pop {
  0%   { transform: scale(0.92); opacity:0.4; }
  60%  { transform: scale(1.04); }
  100% { transform: scale(1); opacity:1; }
}
.anim-ambient-breathe { animation: ambient-breathe 3.4s ease-in-out infinite; }
.anim-ambient-ring    { animation: ambient-ring 2.6s ease-in-out infinite; }
.anim-ambient-dot     { animation: ambient-dot 2.2s ease-in-out infinite; }
.anim-ambient-flow    { background-size: 200% 100%; animation: ambient-flow 3.2s linear infinite; }
.anim-signal-pulse    { animation: signal-pulse 0.85s ease-in-out infinite; }
.anim-signal-pop      { animation: signal-pop 0.4s ease-out; }

/* ── 27-inch / large screen scaling (≥1536px) ────────────────────────── */
@media (min-width: 1536px) {
  .cr-price-display   { font-size: 54px !important; }
  .cr-panel-header    { padding: 5px 16px !important; }
  .cr-heatmap-table   { font-size: 12px; }
  .cr-heatmap-table th,
  .cr-heatmap-table td { padding-top: 7px !important; padding-bottom: 7px !important; }
  .cr-cmp-badge       { font-size: 11px !important; padding: 2px 6px !important; }
  .cr-fase-pill       { font-size: 10px !important; padding: 1px 6px !important; }
  .cr-neural-node     { min-width: 74px !important; padding: 6px 10px !important; }
  .cr-label-xs        { font-size: 11px; }
  .cr-label-sm        { font-size: 12px; }
  .cr-label-md        { font-size: 14px; }
  .cr-buybar-track,
  .cr-sellbar-track   { height: 20px !important; }
  .cr-minichart       { height: 40px !important; }
  .cr-snr-row         { font-size: 11px; padding: 4px 0; }
  .cr-sync-btn        { padding: 8px 0 !important; font-size: 12px; }
  .cr-sniper-banner   { padding: 7px 16px !important; }
  .cr-sniper-banner .anim-marquee { font-size: 11px; }
  .cr-hd-title        { font-size: 13px; }
  .cr-hd-sub          { font-size: 10px; }
  .cr-section-label   { font-size: 11px; }
}
`;

// ── Constants ─────────────────────────────────────────────────────────────────
const BLOCKS = "▁▂▃▄▅▆▇█";

const STORYLINE_MAP: Record<string, { vrFrom: string; cfLow: string; cfHigh: string | null; tradeTF: string }> = {
  DAILY: { vrFrom: "H4",  cfLow: "H4",  cfHigh: null,  tradeTF: "H4"      },
  H4:    { vrFrom: "H1",  cfLow: "H1",  cfHigh: "M30", tradeTF: "M30/M15" },
  H1:    { vrFrom: "M30", cfLow: "M30", cfHigh: "M15", tradeTF: "M15/M5"  },
  M30:   { vrFrom: "M15", cfLow: "M15", cfHigh: "M5",  tradeTF: "M5"      },
  M15:   { vrFrom: "M5",  cfLow: "M5",  cfHigh: null,  tradeTF: "M5"      },
  // M5 removed — no M1 CF; M5 is terkecil
};

const TF_ROWS = ["DAILY", "H4", "H1", "M30", "M15", "M5"];

const SNR_AUTO_GROUPS = [
  { label: "Daily",   keys: [{ key: "PDH", short: "PDH", stars: 5 }, { key: "PDL", short: "PDL", stars: 5 }, { key: "DAILY_OPEN", short: "DOpen", stars: 4 }] },
  { label: "Weekly",  keys: [{ key: "PWH", short: "PWH", stars: 5 }, { key: "PWL", short: "PWL", stars: 5 }, { key: "WEEKLY_OPEN", short: "WOpen", stars: 4 }] },
  { label: "Monthly", keys: [{ key: "PMH", short: "PMH", stars: 4 }, { key: "PML", short: "PML", stars: 4 }] },
  { label: "Session", keys: [{ key: "ASIA_H", short: "AsiaH", stars: 3 }, { key: "ASIA_L", short: "AsiaL", stars: 3 }, { key: "LONDON_H", short: "LdnH", stars: 3 }, { key: "LONDON_L", short: "LdnL", stars: 3 }] },
  { label: "Round",   keys: [{ key: "ROUND_ABOVE", short: "↑Rnd", stars: 4 }, { key: "ROUND_BELOW", short: "↓Rnd", stars: 4 }] },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function getFase(vr: string, cf: string): 1 | 2 | 3 {
  if (vr === "YA" && cf === "YA") return 3;
  if (vr === "YA") return 2;
  return 1;
}

function timeAgo(ts: number | null) {
  if (!ts) return null;
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 5)  return "just now";
  if (s < 60) return `${s}s ago`;
  return `${Math.floor(s / 60)}m ago`;
}

type FiredEvent = { tf: string; type: "CF" | "VR"; dir: string };

function buildAutoPrompt(vars: Record<string, CtxVar>, events?: FiredEvent[]): string {
  const get  = (k: string) => vars[k]?.value?.trim() || "";
  const harga   = get("HARGA");
  const session = get("SESSION");
  const spread  = get("SPREAD");

  // ── TF table rows ──────────────────────────────────────────────────────────
  const tfLines: string[] = [];
  const primeTFs: string[] = [];
  for (const tf of TF_ROWS) {
    const cmp = get(`${tf}_CMP`);
    const vr  = get(`${tf}_VR`);
    const cf  = get(`${tf}_CF`);
    if (!cmp) continue;
    const dir  = cmp === "BULLISH" ? "BUY ▲" : cmp === "BEARISH" ? "SELL ▼" : cmp;
    const fase = (vr === "YA" && cf === "YA") ? "F3⚡PRIME"
               : vr === "YA"                  ? "F2"
               :                                "F1";
    const mark = tf === "H4" ? "★" : " ";
    const sl   = STORYLINE_MAP[tf];
    const vrLabel = vr === "YA" ? `${sl?.vrFrom||"?"}✓` : "BELUM";
    const cfLabel = cf === "YA" ? "CF✓" : `tunggu ${sl?.cfLow||"?"}`;
    tfLines.push(`${tf.padEnd(5)}${mark}| ${dir.padEnd(8)}| VR:${vrLabel.padEnd(7)}| CF:${cfLabel.padEnd(12)}| ${fase}`);
    if (fase === "F3⚡PRIME") primeTFs.push(`${tf} ${dir.trim()}`);
  }

  // ── conflict check ─────────────────────────────────────────────────────────
  const dailyCMP = get("DAILY_CMP");
  const h4CMP    = get("H4_CMP");
  const conflict  = dailyCMP && h4CMP && dailyCMP !== h4CMP;
  const biasNote  = conflict
    ? `⚠ KONFLIK ARAH: Daily=${dailyCMP} vs H4=${h4CMP} → entry searah Daily = SAFER, lawan Daily = Grade C SKIP`
    : dailyCMP
      ? `Daily & H4 searah: ${dailyCMP} → bias aligned`
      : "";

  // ── SNR ───────────────────────────────────────────────────────────────────
  const SNR_KEYS = ["PDH","PDL","DAILY_OPEN","PWH","PWL","WEEKLY_OPEN","PMH","PML",
                    "ASIA_H","ASIA_L","LONDON_H","LONDON_L","ROUND_ABOVE","ROUND_BELOW"];
  const snrLines = SNR_KEYS.filter(k => get(k)).map(k => `  ${k}: ${get(k)}`);
  const tpLines  = ["TP_ABOVE_1","TP_ABOVE_2","TP_BELOW_1","TP_BELOW_2"]
    .filter(k => get(k)).map(k => `  ${k}: ${get(k)}`);

  const lines: string[] = [];

  // ── Event-specific header ─────────────────────────────────────────────────
  const cfEvents = events?.filter(e => e.type === "CF") ?? [];
  const vrEvents = events?.filter(e => e.type === "VR") ?? [];

  if (cfEvents.length > 0) {
    cfEvents.forEach(e =>
      lines.push(`[AUTO-CF] ⚡ CF FIRED — ${e.tf} ${e.dir}`)
    );
    lines.push(`State market terbaru dari TradingView. Baca tabel berikut SECARA LITERAL.`);
  } else if (vrEvents.length > 0) {
    vrEvents.forEach(e =>
      lines.push(`[AUTO-VR] 📡 VR CONFIRMED — ${e.tf} ${e.dir}`)
    );
    lines.push(`State market terbaru dari TradingView. Baca tabel berikut SECARA LITERAL.`);
  } else {
    lines.push(`[AUTO-SYNC] Data market baru dari TradingView. Baca tabel berikut SECARA LITERAL.`);
  }

  lines.push(`Harga sekarang: ${harga || "—"} | Session: ${session || "—"} | Spread: ${spread || "—"}`);
  lines.push("");
  lines.push("═══ STATE PER TF (BACA LITERAL — JANGAN UBAH ATAU ASUMSI) ═══");
  lines.push("TF    ★| CMP     | VR       | CF           | FASE");
  lines.push("-------+--------+----------+--------------+---------");
  lines.push(...tfLines);
  lines.push("");
  if (biasNote)    lines.push(biasNote);
  if (primeTFs.length) lines.push(`PRIME ENTRY AKTIF: ${primeTFs.join(", ")} → siklus CMP→VR→CF SELESAI`);
  if (snrLines.length) {
    lines.push("");
    lines.push("═══ FUNDAMENTAL SNR ═══");
    lines.push(...snrLines);
  }
  if (tpLines.length) {
    lines.push("TP Suggestion:");
    lines.push(...tpLines);
  }
  lines.push("");
  if (cfEvents.length > 0) {
    // CF fired — minta trade plan lengkap langsung
    lines.push("INSTRUKSI: CF baru saja FIRE. LANGSUNG berikan TRADE PLAN lengkap tanpa basa-basi:");
    lines.push("1. KONFIRMASI STATE (tulis ulang H4, M30, Daily dari tabel)");
    lines.push("2. GRADE setup (A+/A/B/C) + alasan singkat");
    lines.push("3. TRADE PLAN: Arah | Entry zone | SL (puncak VR) | TP1 | TP2 | Size");
    lines.push("4. GUARD CHECK cepat: spread / news blackout / barrier");
    lines.push("INGAT: Entry berlawanan Daily = Grade C SKIP. SL = puncak VR, bukan round number.");
  } else if (vrEvents.length > 0) {
    // VR fired — minta watchlist & scenario CF
    lines.push("INSTRUKSI: VR baru saja TERKONFIRMASI. Berikan WATCHLIST & SCENARIO:");
    lines.push("1. KONFIRMASI STATE + VR yang baru fire (TF mana, arah mana)");
    lines.push("2. Entry zone CF berikutnya: area harga berapa, TF entry mana (LowRisk / HighRisk)");
    lines.push("3. Level kritis yang harus DIJAGA: barrier VR, SNR yang tidak boleh ditembus");
    lines.push("4. Perkiraan kekuatan momentum: VR dari TF apa? → berapa kuat gerakan CF expected?");
    lines.push("JANGAN entry sekarang — ini fase nunggu CF. Analisis kapan dan di mana CF akan muncul.");
  } else {
    lines.push("INSTRUKSI: Mulai dengan KONFIRMASI STATE (tulis ulang H4, M30, Daily dari tabel).");
    lines.push("Lalu berikan analisis STORYLINE + GRADE + TRADE PLAN lengkap.");
    lines.push("INGAT: SL = puncak VR (bukan round number). Entry berlawanan Daily = Grade C SKIP.");
  }
  return lines.join("\n");
}

// ── Auto-grade calculator (doctrine: Daily+H4 aligned → M30/M15 F3 → A+/A) ──
type GradeResult = { grade: "A+" | "A" | "B" | "C" | "SKIP" | "—"; reason: string };
function computeAutoGrade(
  tfData: { tf: string; cmp: string; vr: string; cf: string; fase: number }[],
  byName: Record<string, { value: string }>
): GradeResult {
  const get  = (k: string) => byName[k]?.value?.trim() || "";
  const daily = tfData.find(d => d.tf === "DAILY");
  const h4    = tfData.find(d => d.tf === "H4");
  const h1    = tfData.find(d => d.tf === "H1");
  const m30   = tfData.find(d => d.tf === "M30");
  const m15   = tfData.find(d => d.tf === "M15");

  if (!h4?.cmp) return { grade: "—", reason: "H4 belum sync" };

  const h4Dir    = h4.cmp;
  const dailyDir = daily?.cmp || "";

  // Daily vs H4 conflict → C
  if (dailyDir && dailyDir !== h4Dir)
    return { grade: "C", reason: `Daily ${dailyDir} ≠ H4 ${h4Dir} — entry searah Daily saja` };

  const masterDir = h4Dir; // H4 is master TF

  // M30 or M15 F3 SAME direction as master?
  const m30F3 = m30?.fase === 3 && m30.cmp === masterDir;
  const m15F3 = m15?.fase === 3 && m15.cmp === masterDir;

  // SNR proximity check — any fundamental level within 5 pts of current price
  const price = parseFloat(get("HARGA").replace(",", ".")) || 0;
  const SNR_KEYS = ["PDH","PDL","DAILY_OPEN","PWH","PWL","ROUND_ABOVE","ROUND_BELOW","ASIA_H","ASIA_L","LONDON_H","LONDON_L"];
  const snrNear = price > 0 && SNR_KEYS.some(k => {
    const v = parseFloat(get(k));
    return v > 0 && Math.abs(v - price) <= 5;
  });

  if (m30F3 || m15F3) {
    const label = m30F3 ? "M30" : "M15";
    if (snrNear)
      return { grade: "A+", reason: `${label} F3 searah H4 + SNR ≤5 pts` };
    return { grade: "A", reason: `${label} F3 searah H4 — SNR tidak dekat` };
  }

  // H4 or H1 F3 but M30/M15 not F3 same dir → B
  if (h4?.fase === 3 || (h1?.fase === 3 && h1.cmp === masterDir))
    return { grade: "B", reason: `${h4?.fase === 3 ? "H4" : "H1"} F3 — tunggu M30/M15 F3 searah` };

  // Any F3 in opposite direction → SKIP
  if (tfData.some(d => d.fase === 3 && d.cmp && d.cmp !== masterDir))
    return { grade: "SKIP", reason: "Setup berlawanan H4 master — SKIP" };

  return { grade: "C", reason: "Belum ada F3 TF kecil searah master" };
}

// ── Audio alert + browser notification ───────────────────────────────────────

function playBeep(type: "cf" | "vr") {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ctx = new ((window as any).AudioContext || (window as any).webkitAudioContext)();
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    if (type === "cf") {
      // CF — three rising tones (urgent: VR→CF siklus selesai, entry!)
      osc.frequency.setValueAtTime(660,  ctx.currentTime);
      osc.frequency.setValueAtTime(880,  ctx.currentTime + 0.13);
      osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.26);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.55);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.55);
    } else {
      // VR — two medium tones (informational: VR terjadi, tunggu CF)
      osc.frequency.setValueAtTime(440, ctx.currentTime);
      osc.frequency.setValueAtTime(550, ctx.currentTime + 0.18);
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.38);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.38);
    }
  } catch { /* Audio API not available */ }
}

async function tryBrowserNotify(title: string, body: string) {
  try {
    if (!("Notification" in window)) return;
    if (Notification.permission === "denied") return;
    if (Notification.permission === "default") {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") return;
    }
    new Notification(title, { body, icon: "/favicon.ico" });
  } catch { /* ignore */ }
}

async function sendTelegramAlert(message: string) {
  try {
    await fetch("/api/telegram-alert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
  } catch { /* Telegram offline — non-fatal */ }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PanelBox({ title, children, cls = "", extra, scanV = false }: {
  title: React.ReactNode; children: React.ReactNode; cls?: string; extra?: React.ReactNode; scanV?: boolean;
}) {
  return (
    <div className={cn("rounded-xl border bg-zinc-950/90 overflow-hidden relative", cls)}>
      {/* Horizontal scan line sweeper */}
      <div className="absolute top-0 left-0 w-full h-[1px] overflow-hidden pointer-events-none z-10">
        <div className="anim-scan-h h-full w-1/4 bg-gradient-to-r from-transparent via-cyan-400/35 to-transparent" />
      </div>
      {/* Optional vertical scan */}
      {scanV && (
        <div className="absolute top-0 left-0 h-full w-[1px] overflow-hidden pointer-events-none z-10">
          <div className="anim-scan-v w-full h-1/4 bg-gradient-to-b from-transparent via-amber-400/20 to-transparent" />
        </div>
      )}
      <div className="cr-panel-header px-3 py-1 border-b border-zinc-800/80 flex items-center justify-between bg-zinc-900/50">
        {title}
        {extra}
      </div>
      {children}
    </div>
  );
}

function HexTag() {
  const [hex] = useState(() => Math.random().toString(16).slice(2, 8).toUpperCase());
  return <span className="cr-label-xs text-[9px] text-zinc-700 font-mono tabular-nums">{hex}</span>;
}

function PanelTitle({ label, live = false }: { label: string; live?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {live && <span className="anim-pulse-dot w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />}
      <span className="cr-label-sm text-[10px] font-black font-mono text-cyan-400 tracking-widest">[ {label} ]</span>
      <HexTag />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function MarketPanel({ onAutoAnalysis, onPriceUpdate, layout = "panel" }: Props) {
  const isDashboard = layout === "dashboard";

  const [vars,        setVars]        = useState<CtxVar[]>([]);
  const [syncing,      setSyncing]      = useState(false);
  const [syncingSNR,   setSyncingSNR]   = useState(false);
  const [syncingNews,  setSyncingNews]  = useState(false);
  const [lastSync,     setLastSync]     = useState<number | null>(null);
  const [lastSNRSync,  setLastSNRSync]  = useState<number | null>(null);
  const [lastNewsSync, setLastNewsSync] = useState<number | null>(null);
  const [tvStatus,     setTvStatus]     = useState<"unknown" | "connected" | "error">("unknown");
  const [snrStatus,    setSnrStatus]    = useState<"unknown" | "ok" | "error">("unknown");
  const [newsStatus,   setNewsStatus]   = useState<"unknown" | "ok" | "error">("unknown");
  const [tvError,      setTvError]      = useState<string | null>(null);
  const [snrError,     setSnrError]     = useState<string | null>(null);
  const [newsError,    setNewsError]    = useState<string | null>(null);
  const [autoSync,    setAutoSync]    = useState(true);   // ← ON by default

  // ── CF / VR alert state ────────────────────────────────────────────────────
  type Alert = { id: string; text: string; level: "vr" | "cf" };
  const [cfAlerts,        setCfAlerts]    = useState<Alert[]>([]);
  const prevTFStateRef    = useRef<Record<string, string>>({});  // delta detection
  const alertDismissRef   = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const hasMountedRef     = useRef(false);
  const [editing,     setEditing]     = useState<string | null>(null);
  const [editVal,     setEditVal]     = useState("");
  const [livePrice,   setLivePrice]   = useState<string>("");
  const [blink,       setBlink]       = useState(true);
  const [blinkFast,   setBlinkFast]   = useState(true);   // 350ms — for F3 sniper alerts
  const [priceFlash,  setPriceFlash]  = useState<"up"|"dn"|null>(null);

  // ── TICK DELTA STATE ────────────────────────────────────────────────────────
  // tickDeltas[i] = price change for that tick (positive = buy, negative = sell)
  const [tickDeltas, setTickDeltas]   = useState<number[]>([]);
  const prevPriceRef    = useRef<number>(0);
  const autoRef         = useRef<ReturnType<typeof setInterval> | null>(null);
  const onPriceUpdateRef = useRef(onPriceUpdate);
  const [, setTick] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setBlink(p => !p), 800);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setBlinkFast(p => !p), 350);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setTick(p => p + 1), 10_000);
    return () => clearInterval(t);
  }, []);

  // ── Alert timer cleanup on unmount ──────────────────────────────────────────
  useEffect(() => {
    const ref = alertDismissRef.current;
    return () => { ref.forEach(t => clearTimeout(t)); };
  }, []);

  const pushAlert = useCallback((text: string, level: "vr" | "cf") => {
    const id = `${level}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setCfAlerts(prev => [...prev.slice(-3), { id, text, level }]); // max 4 alerts
    const timer = setTimeout(() => {
      setCfAlerts(prev => prev.filter(a => a.id !== id));
      alertDismissRef.current.delete(id);
    }, 10_000);
    alertDismissRef.current.set(id, timer);
  }, []);

  const load = useCallback(async () => {
    const r    = await fetch("/api/context");
    const data: CtxVar[] = await r.json();
    if (data.length === 0) { await seedDefaults(); return; }
    const existingNames = new Set(data.map(v => v.variableName));
    const missing = Object.entries(DEFAULT_MARKET_CONTEXT).filter(([k]) => !existingNames.has(k));
    for (const [variableName, v] of missing) {
      await fetch("/api/context", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variableName, label: v.label, value: "" }) });
    }
    const r2 = await fetch("/api/context");
    setVars(await r2.json());
  }, []);

  async function seedDefaults() {
    for (const [variableName, v] of Object.entries(DEFAULT_MARKET_CONTEXT)) {
      await fetch("/api/context", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variableName, label: v.label, value: "" }) });
    }
    const r = await fetch("/api/context");
    setVars(await r.json());
  }

  const syncTV = useCallback(async () => {
    setSyncing(true); setTvError(null);
    try {
      const r = await fetch("/api/tv-sync", { method: "POST" });
      const json = await r.json();
      if (json.success) {
        const freshVars: CtxVar[] = json.data;
        setVars(freshVars); setLastSync(Date.now()); setTvStatus("connected");

        const byName = Object.fromEntries(freshVars.map(v => [v.variableName, v]));

        // ── Delta detection: compare VR/CF state per TF ────────────────────
        const newState: Record<string, string> = {};
        for (const tf of TF_ROWS) {
          const cmp = byName[`${tf}_CMP`]?.value || "";
          const vr  = byName[`${tf}_VR`]?.value  || "";
          const cf  = byName[`${tf}_CF`]?.value  || "";
          if (cmp) newState[tf] = `${cmp}:${vr}:${cf}`;
        }

        const prev      = prevTFStateRef.current;
        const wasEmpty  = Object.keys(prev).length === 0;
        let hasCFChange = false;
        let hasVRChange = false;
        const firedEvents: FiredEvent[] = [];

        if (!wasEmpty) {
          for (const tf of TF_ROWS) {
            if (!newState[tf] || !prev[tf]) continue;
            const [, prevVR, prevCF]       = prev[tf].split(":");
            const [cmpNow,  newVR,  newCF] = newState[tf].split(":");
            const dir = cmpNow === "BULLISH" ? "BUY" : cmpNow === "BEARISH" ? "SELL" : "";

            if (prevCF !== "YA" && newCF === "YA") {
              // CF just fired — entry signal! (count diambil dari indikator v4)
              hasCFChange = true;
              firedEvents.push({ tf, type: "CF", dir });
              pushAlert(`⚡ CF FIRED — ${tf} ${dir} · PRIME ENTRY`, "cf");
              playBeep("cf");
              void tryBrowserNotify(`⚡ Chain Reaction — ${tf} CF`, `${dir} setup active on ${tf}. Check SL/TP.`);
              {
                const price   = byName["HARGA"]?.value  || "—";
                const h4cmp   = byName["H4_CMP"]?.value || "—";
                const m30cmp  = byName["M30_CMP"]?.value || "—";
                const m30vrNow = byName["M30_VR"]?.value || "";
                const m30cfNow = byName["M30_CF"]?.value || "";
                const sl      = STORYLINE_MAP[tf];
                const tpKey   = dir === "BUY" ? "TP_ABOVE_1" : "TP_BELOW_1";
                const tp1     = byName[tpKey]?.value || "—";

                // Scalp-specific Telegram: M5 CF + M30 F2 (VR done, CF not yet done) same dir
                const isScalpSignal = tf === "M5" && m30vrNow === "YA" && m30cfNow !== "YA" && m30cmp === (dir === "BUY" ? "BULLISH" : "BEARISH");

                const tgMsg = isScalpSignal
                  ? [
                      `⚡ <b>SCALP ENTRY — M5 CF FIRED</b>`,
                      `🎯 M30 F2 AKTIF → Siklus scalp terpenuhi`,
                      ``,
                      `💰 Harga: <b>${price}</b>`,
                      `📊 M30: ${m30cmp} F2 ✓ → M5 CF ✓`,
                      `📊 H4 master: ${h4cmp}`,
                      ``,
                      `▸ Arah: <b>${dir}</b>`,
                      `▸ Entry: SEKARANG di M5 CF`,
                      `▸ SL: swing M5 (~5-10 pts)`,
                      `▸ TP: M15 barrier (scalp cepat)`,
                      `▸ ★ SL kecil → lot lebih besar aman`,
                      ``,
                      `<i>Chain Reaction v4.0 OVERLORD</i>`,
                    ].join("\n")
                  : [
                      `⚡ <b>CF FIRED — ${tf} ${dir}</b>`,
                      `🏆 PRIME ENTRY SIGNAL`,
                      ``,
                      `💰 Harga: <b>${price}</b>`,
                      `📊 H4: ${h4cmp} · M30: ${m30cmp}`,
                      sl ? `🎯 Entry di ${sl.tradeTF} · TP: ${tp1}` : `🎯 TP: ${tp1}`,
                      `⚠️ SL = puncak VR, bukan round number`,
                      ``,
                      `<i>Chain Reaction v4.0 OVERLORD</i>`,
                    ].join("\n");
                void sendTelegramAlert(tgMsg);
              }
            } else if (prevVR !== "YA" && newVR === "YA") {
              // VR just confirmed — waiting for CF
              hasVRChange = true;
              firedEvents.push({ tf, type: "VR", dir });
              pushAlert(`VR CONFIRMED — ${tf} ${dir} · Tunggu CF`, "vr");
              playBeep("vr");
              void tryBrowserNotify(`VR Confirmed — ${tf}`, `${dir} VR done on ${tf}. Waiting CF entry.`);
              {
                const price  = byName["HARGA"]?.value || "—";
                const h4cmp  = byName["H4_CMP"]?.value  || "—";
                const sl     = STORYLINE_MAP[tf];
                const tgMsg  = [
                  `📡 <b>VR CONFIRMED — ${tf} ${dir}</b>`,
                  `⏳ TUNGGU CF ENTRY`,
                  ``,
                  `💰 Harga: <b>${price}</b>`,
                  `📊 H4: ${h4cmp}`,
                  sl ? `⚡ Tunggu CF di ${sl.cfLow}` : `⚡ Tunggu CF`,
                  `🚫 JANGAN entry sekarang — ini fase menunggu`,
                  ``,
                  `<i>Chain Reaction v4.0 OVERLORD</i>`,
                ].join("\n");
                void sendTelegramAlert(tgMsg);
              }
            }
          }
        }

        prevTFStateRef.current = newState;

        // Auto-analysis: fire on first load OR when VR/CF state changes
        if (onAutoAnalysis && (wasEmpty || hasCFChange || hasVRChange)) {
          if (TF_ROWS.some(tf => byName[`${tf}_CMP`]?.value)) {
            // Pass fired events so AI gets event-specific prompt (CF→trade plan, VR→watchlist)
            onAutoAnalysis(buildAutoPrompt(byName, wasEmpty ? [] : firedEvents));
          }
        }
      } else { setTvStatus("error"); setTvError(json.error || "Gagal sync"); }
    } catch (e) { setTvStatus("error"); setTvError(e instanceof Error ? e.message : "Network error"); }
    finally { setSyncing(false); }
  }, [onAutoAnalysis, pushAlert]);

  const syncSNR = useCallback(async () => {
    setSyncingSNR(true); setSnrError(null);
    try {
      const r = await fetch("/api/fundamental-sync", { method: "POST" });
      const json = await r.json();
      if (json.success) { setVars(json.data); setLastSNRSync(Date.now()); setSnrStatus("ok"); }
      else               { setSnrStatus("error"); setSnrError(json.error || "Gagal sync SNR"); }
    } catch (e) { setSnrStatus("error"); setSnrError(e instanceof Error ? e.message : "Network error"); }
    finally { setSyncingSNR(false); }
  }, []);

  const syncNews = useCallback(async () => {
    setSyncingNews(true); setNewsError(null);
    try {
      const r = await fetch("/api/news-sync", { method: "POST" });
      const json = await r.json();
      if (json.success) {
        setVars(json.data); setLastNewsSync(Date.now()); setNewsStatus("ok");
      } else {
        // partial success — some sources failed
        const errors = (json.results as { source: string; status: string; error?: string }[])
          ?.filter(x => x.status === "error").map(x => x.source).join(", ");
        setNewsStatus("error");
        setNewsError(`Gagal: ${errors || json.error || "Unknown"}`);
        if (json.data) { setVars(json.data); setLastNewsSync(Date.now()); }
      }
    } catch (e) { setNewsStatus("error"); setNewsError(e instanceof Error ? e.message : "Network error"); }
    finally { setSyncingNews(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (autoRef.current) { clearInterval(autoRef.current); autoRef.current = null; }
    if (!autoSync) return;

    // First enable: 2s delay so page/load() can settle; subsequent: sync immediately
    let initTimer: ReturnType<typeof setTimeout> | null = null;
    if (!hasMountedRef.current) {
      hasMountedRef.current = true;
      initTimer = setTimeout(syncTV, 2000);
    } else {
      syncTV();
    }
    autoRef.current = setInterval(syncTV, 30_000);

    return () => {
      if (initTimer) clearTimeout(initTimer);
      if (autoRef.current) { clearInterval(autoRef.current); autoRef.current = null; }
    };
  }, [autoSync, syncTV]);

  useEffect(() => { onPriceUpdateRef.current = onPriceUpdate; }, [onPriceUpdate]);

  // ── SSE price stream + tick delta accumulation ───────────────────────────────
  useEffect(() => {
    const es = new EventSource("/api/price-stream");
    es.onmessage = (e) => {
      try {
        const { price } = JSON.parse(e.data) as { price?: string };
        if (!price) return;
        setLivePrice(price);
        onPriceUpdateRef.current?.(price);

        const priceNum = parseFloat(price);
        if (prevPriceRef.current && priceNum) {
          const delta = priceNum - prevPriceRef.current;
          if (Math.abs(delta) > 0.001) {
            // price flash
            setPriceFlash(delta > 0 ? "up" : "dn");
            setTimeout(() => setPriceFlash(null), 550);
            // tick delta log (keep last 40 ticks)
            setTickDeltas(prev => [...prev.slice(-39), delta]);
          }
        }
        if (priceNum) prevPriceRef.current = priceNum;
      } catch { /* ignore */ }
    };
    return () => es.close();
  }, []);

  async function save(variableName: string, label: string, value: string) {
    await fetch("/api/context", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ variableName, label, value }) });
    setVars(prev => prev.map(v => v.variableName === variableName ? { ...v, value } : v));
    setEditing(null);
  }

  const byName       = Object.fromEntries(vars.map(v => [v.variableName, v]));
  const dbHarga      = byName["HARGA"]?.value  || "—";
  const displayPrice = livePrice || dbHarga;
  const spread       = byName["SPREAD"]?.value || "—";
  const sess         = byName["SESSION"]?.value || "—";

  // ── Computed heatmap + chain data ─────────────────────────────────────────
  const tfData = TF_ROWS.map(tf => ({
    tf, cmp: byName[`${tf}_CMP`]?.value || "",
    vr: byName[`${tf}_VR`]?.value  || "",
    cf: byName[`${tf}_CF`]?.value  || "",
    cfCount: parseInt(byName[`${tf}_CF_COUNT`]?.value || "0", 10) || 0,
    cfType:  byName[`${tf}_CF_TYPE`]?.value || "",
    get fase() { return this.cmp ? getFase(this.vr, this.cf) : 0 as 0|1|2|3; },
    sl: STORYLINE_MAP[tf],
  }));
  const hasTFData    = tfData.some(d => !!d.cmp);
  const h4           = tfData.find(d => d.tf === "H4");
  const h4Dir        = h4?.cmp || "";
  const h4Fase       = h4?.fase || 0;
  const hasAnyF3     = tfData.some(d => d.fase === 3);

  // ── Scalp cycle computations ───────────────────────────────────────────────
  const h1d         = tfData.find(d => d.tf === "H1");
  const m30d        = tfData.find(d => d.tf === "M30");
  const m15d        = tfData.find(d => d.tf === "M15");
  const m5d         = tfData.find(d => d.tf === "M5");
  const h1Fase      = h1d?.fase || 0;
  const h4F3        = h4Fase === 3;
  const h1F3        = h1Fase === 3;
  const scalpActive    = h4F3 || h1F3;
  const scalpMasterTF  = h4F3 ? "H4" : "H1";   // hanya untuk label aktivasi panel
  const scalpMasterDir = h4F3 ? h4Dir : (h1d?.cmp || ""); // arah H4/H1 — hanya untuk guard cek m30Aligned
  const scalpIsBull    = scalpMasterDir === "BULLISH"; // H4/H1 direction — untuk header panel & phase 0/-1 label
  const m30cmp      = m30d?.cmp || "";
  const m30vr       = m30d?.vr  || "";
  const m30cf       = m30d?.cf  || "";
  const m15cmp      = m15d?.cmp || "";
  const m5cmp       = m5d?.cmp  || "";
  // Arah entry scalp = M30 CMP (bukan H4/H1)
  const m30IsBull   = m30cmp === "BULLISH";
  // Guard: M30 searah H4/H1 master (kalau tidak → phase -1 warning)
  const m30Aligned  = !!m30cmp && !!scalpMasterDir && m30cmp === scalpMasterDir;
  // scalpPhase: -1=M30 berlawanan H4/H1, 0=no M30 CMP, 1=F1 wait VR, 2=F2 wait CF, 3=F3 entry
  const scalpPhase: -1 | 0 | 1 | 2 | 3 =
    !m30cmp                          ? 0  :
    !m30Aligned                      ? -1 :
    m30vr === "YA" && m30cf === "YA" ? 3  :
    m30vr === "YA"                   ? 2  : 1;

  // CF status — AUTORITATIF dari indikator v4 (bukan tracking sendiri di dashboard)
  // Indikator v4 sudah handle: CF flip → M30_CF jadi BELUM otomatis, CF count naik per siklus
  // m30CfActive cuma cerminan langsung M30_CF dari TV
  const m30CfActive  = m30cf === "YA";
  const m30CfCount   = m30d?.cfCount || 0;
  const m30CfType    = m30d?.cfType  || "";

  const chainNodes = ["DAILY","H4","H1","M30","M15","M5"].map(id => ({
    id, label: id === "H4" ? "H4 ★" : id === "DAILY" ? "D1" : id,
    tf: tfData.find(d => d.tf === id),
    isMaster: id === "H4",
  }));

  // ── Tick delta computations ────────────────────────────────────────────────
  const N_TICKS      = tickDeltas.length;
  const buyTicks     = tickDeltas.filter(d => d > 0).length;
  const sellTicks    = tickDeltas.filter(d => d < 0).length;
  const buyPct       = N_TICKS ? Math.round(buyTicks  / N_TICKS * 100) : 50;
  const sellPct      = N_TICKS ? Math.round(sellTicks / N_TICKS * 100) : 50;
  const cumDelta     = parseFloat(tickDeltas.reduce((a, b) => a + b, 0).toFixed(3));
  const momentum     = N_TICKS < 5 ? "SCANNING" : buyPct >= 65 ? "BULL" : buyPct <= 35 ? "BEAR" : "NEUTRAL";
  const momentumStr  = momentum === "BULL" ? "▲ BULLISH" : momentum === "BEAR" ? "▼ BEARISH" : momentum === "SCANNING" ? "○ SCANNING" : "── NEUTRAL";
  const momentumCol  = momentum === "BULL" ? "text-emerald-400" : momentum === "BEAR" ? "text-red-400" : "text-zinc-500";

  // Group ticks into 8 "candles" of ~5 ticks each for mini chart
  const BARS = 8;
  const barSize = Math.max(1, Math.floor(N_TICKS / BARS));
  const barDeltas: number[] = Array.from({ length: BARS }, (_, i) => {
    const slice = tickDeltas.slice(i * barSize, (i + 1) * barSize);
    return slice.length ? slice.reduce((a, b) => a + b, 0) : 0;
  });
  const maxBarAbs = Math.max(...barDeltas.map(Math.abs), 0.001);

  // divergence: price went one way but delta went opposite
  const recentBuyPct  = tickDeltas.slice(-8).filter(d => d > 0).length / Math.max(Math.min(8, N_TICKS), 1) * 100;
  const earlyBuyPct   = tickDeltas.slice(0, 8).filter(d => d > 0).length  / Math.max(Math.min(8, N_TICKS), 1) * 100;
  const divergence    = N_TICKS >= 16 && Math.abs(recentBuyPct - earlyBuyPct) > 40;

  // ── Auto-grade ────────────────────────────────────────────────────────────
  const autoGrade   = hasTFData ? computeAutoGrade(tfData, byName) : { grade: "—" as const, reason: "" };

  // ── News blackout countdown ────────────────────────────────────────────────
  const nextEpoch         = parseInt(byName["NEXT_EVENT_EPOCH"]?.value || "0");
  const nextEventName     = byName["NEXT_EVENT_NAME"]?.value     || "";
  const nextEventTimeWIB  = byName["NEXT_EVENT_TIME_WIB"]?.value || "";
  const minutesUntilNews  = nextEpoch > 0 ? Math.floor((nextEpoch - Date.now()) / 60_000) : null;
  const newsBlackout      = minutesUntilNews !== null && minutesUntilNews >= 0 && minutesUntilNews <= 30;
  const newsApproaching   = minutesUntilNews !== null && minutesUntilNews > 30 && minutesUntilNews <= 60;

  // ── SITREP computation ─────────────────────────────────────────────────────
  const sitrep = (() => {
    if (!hasTFData) return null;
    const biasDir   = h4Dir || "";
    const biasLabel = biasDir === "BULLISH" ? "▲ BUY" : biasDir === "BEARISH" ? "▼ SELL" : "─";
    const f3List    = tfData.filter(d => d.fase === 3 && d.cmp).map(d => d.tf);
    const primeLabel = f3List.length ? `${f3List[0]}${f3List.length > 1 ? `+${f3List.length - 1}` : ""} F3` : tfData.some(d => d.fase === 2) ? `${tfData.find(d => d.fase === 2)!.tf} F2` : "F1";
    const scalpLabel  = !scalpActive ? "—"
      : scalpPhase === 3 ? "⚡ ENTRY"
      : scalpPhase === 2 ? "WAIT M5 CF"
      : scalpPhase === 1 ? "WAIT M15 VR"
      : scalpPhase === -1 ? "SKIP DIR"
      : "NO M30";
    const newsLabel   = newsBlackout    ? `🚨 ${minutesUntilNews}m`
      : newsApproaching ? `⚠ ${minutesUntilNews}m`
      : minutesUntilNews !== null && minutesUntilNews < 0 ? "PASSED"
      : nextEventName ? "CLEAR" : "NO DATA";
    const gradeLabel  = autoGrade.grade;
    return { biasLabel, primeLabel, scalpLabel, newsLabel, gradeLabel, biasDir };
  })();

  // ── SNR data ─────────────────────────────────────────────────────────────
  const cmpFloat = parseFloat(displayPrice.replace(",", ".")) || 0;
  const allLevels: { key: string; short: string; price: number; stars: number }[] = [];
  for (const group of SNR_AUTO_GROUPS)
    for (const item of group.keys) {
      const price = parseFloat(byName[item.key]?.value || "");
      if (!isNaN(price) && price > 0) allLevels.push({ ...item, price });
    }
  const aboveLevels = allLevels.filter(l => l.price > cmpFloat + 0.5).sort((a, b) => a.price - b.price);
  const belowLevels = allLevels.filter(l => l.price < cmpFloat - 0.5).sort((a, b) => b.price - a.price);
  const atLevel     = allLevels.filter(l => Math.abs(l.price - cmpFloat) <= 0.5);
  const tp1Up = byName["TP_ABOVE_1"]?.value;
  const tp2Up = byName["TP_ABOVE_2"]?.value;
  const tp1Dn = byName["TP_BELOW_1"]?.value;
  const tp2Dn = byName["TP_BELOW_2"]?.value;

  // ── Render helpers ────────────────────────────────────────────────────────
  function CmpBadge({ cmp, pulse = false }: { cmp: string; pulse?: boolean }) {
    if (cmp === "BULLISH") return (
      <span className={cn(
        "cr-cmp-badge inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-black font-mono transition-all duration-100",
        pulse
          ? blinkFast
            ? "bg-emerald-400 border border-emerald-300 text-black shadow-[0_0_14px_rgba(52,211,153,0.7)]"
            : "bg-emerald-950 border border-emerald-600 text-emerald-300"
          : "bg-emerald-950 border border-emerald-700 text-emerald-300"
      )}>
        {pulse && blinkFast ? "◉" : "▣"} BUY
      </span>
    );
    if (cmp === "BEARISH") return (
      <span className={cn(
        "cr-cmp-badge inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-black font-mono transition-all duration-100",
        pulse
          ? blinkFast
            ? "bg-red-400 border border-red-300 text-black shadow-[0_0_14px_rgba(248,113,113,0.7)]"
            : "bg-red-950 border border-red-600 text-red-300"
          : "bg-red-950 border border-red-700 text-red-300"
      )}>
        {pulse && blinkFast ? "◉" : "▣"} SELL
      </span>
    );
    return <span className="cr-label-sm text-[10px] font-mono text-zinc-700">────</span>;
  }

  function FasePill({ fase }: { fase: number }) {
    if (fase === 3) return (
      <span className={cn("cr-fase-pill inline-flex px-2 py-0.5 rounded-full text-[9px] font-black font-mono border",
        blinkFast
          ? "bg-amber-400 border-amber-300 text-black shadow-[0_0_18px_rgba(245,158,11,0.8)]"
          : "bg-amber-600 border-amber-500 text-black shadow-[0_0_6px_rgba(245,158,11,0.3)]"
      )}>
        ⚡F3
      </span>
    );
    if (fase === 2) return (
      <span className="cr-fase-pill inline-flex px-2 py-0.5 rounded-full text-[9px] font-bold font-mono border bg-blue-950 border-blue-700 text-blue-300">
        F2
      </span>
    );
    if (fase === 1) return (
      <span className="cr-fase-pill inline-flex px-2 py-0.5 rounded-full text-[9px] font-mono border bg-zinc-900 border-zinc-700 text-zinc-500">
        F1
      </span>
    );
    return <span className="cr-label-xs text-[9px] text-zinc-800 font-mono">──</span>;
  }

  // ── ALERT TOAST JSX (shared, fixed-position, both modes) ────────────────────
  const alertToasts = cfAlerts.length > 0 ? (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {cfAlerts.map(alert => (
        <div key={alert.id} className={cn(
          "flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl pointer-events-auto",
          alert.level === "cf"
            ? "bg-amber-950/95 border-amber-500/80 shadow-[0_0_32px_rgba(245,158,11,0.45)]"
            : "bg-blue-950/95 border-blue-600/80 shadow-[0_0_24px_rgba(59,130,246,0.3)]"
        )}>
          <span className={cn("text-base shrink-0", alert.level === "cf" ? (blinkFast ? "text-amber-300" : "text-amber-500") : "text-blue-400")}>
            {alert.level === "cf" ? "⚡" : "◉"}
          </span>
          <span className={cn("text-[11px] font-black font-mono tracking-wide",
            alert.level === "cf" ? "text-amber-200" : "text-blue-200"
          )}>{alert.text}</span>
          <button
            onClick={() => {
              const timer = alertDismissRef.current.get(alert.id);
              if (timer) { clearTimeout(timer); alertDismissRef.current.delete(alert.id); }
              setCfAlerts(prev => prev.filter(a => a.id !== alert.id));
            }}
            className="shrink-0 ml-1 text-zinc-600 hover:text-zinc-200 transition-colors"
          >
            <XIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  ) : null;

  // ── PANEL MODE (narrow right sidebar) ─────────────────────────────────────
  if (!isDashboard) {
    return (
      <div className="px-3 py-3 space-y-3">
        <style>{ANIM_CSS}</style>
        {alertToasts}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ZapIcon className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <div>
              <div className="text-[10px] font-black text-amber-400 tracking-tight font-mono">CHAIN REACTION</div>
              <div className="text-[8px] text-zinc-600 font-mono uppercase tracking-widest">Dadang Wahyuono</div>
            </div>
          </div>
          {tvStatus === "connected"
            ? <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" /><span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" /></span>
            : <span className="w-2 h-2 rounded-full bg-zinc-700" />}
        </div>

        <div className={cn("rounded-lg border px-3 py-2 flex items-center justify-between transition-all",
          priceFlash === "up" ? "anim-flash-up border-emerald-700/40" :
          priceFlash === "dn" ? "anim-flash-dn border-red-700/40"     :
          "bg-zinc-900 border-amber-500/20"
        )}>
          <div>
            <div className="text-[9px] text-amber-500 font-mono font-black">XAUUSD · {sess}</div>
            <div className="text-[9px] text-zinc-600 font-mono">SPR:{spread}</div>
          </div>
          <div className="text-right">
            <div className={cn("text-[9px] font-mono", livePrice ? "text-emerald-500" : "text-zinc-700")}>
              {livePrice ? (blink ? "● LIVE" : "○ LIVE") : "○ OFFLINE"}
            </div>
            <div className={cn("text-xl font-black font-mono tabular-nums", livePrice ? "text-amber-400" : "text-zinc-500")}>{displayPrice}</div>
          </div>
        </div>

        <button onClick={syncTV} disabled={syncing} className={cn("w-full py-2 rounded-lg text-[10px] font-black font-mono tracking-wider border transition-all",
          syncing ? "bg-zinc-900 border-zinc-800 text-zinc-600 cursor-not-allowed"
          : tvStatus === "connected" ? "bg-emerald-950/20 border-emerald-700/40 text-emerald-400"
          : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-amber-500/40 hover:text-amber-400"
        )}>
          <RefreshCwIcon className={cn("w-3 h-3 inline mr-1.5", syncing && "animate-spin")} />
          {syncing ? "READING..." : "⚡ SYNC TV"}
        </button>

        {hasTFData && (
          <div className="bg-zinc-900/60 rounded-lg border border-zinc-800 overflow-hidden">
            <div className="px-2 py-1 border-b border-zinc-800 text-[9px] font-black font-mono text-cyan-500 tracking-widest">[ SIGNAL.HEATMAP ]</div>
            {tfData.filter(d => !!d.cmp).map(({ tf, cmp, fase }) => (
              <div key={tf} className={cn("flex items-center gap-1 px-2 py-1 border-b border-zinc-800/50 last:border-0",
                fase === 3 ? "anim-row-fire" : fase === 2 ? "bg-blue-950/20" : ""
              )}>
                <span className={cn("text-[10px] font-black font-mono w-8 shrink-0", tf === "H4" ? "text-amber-400" : "text-cyan-500")}>{tf}{tf === "H4" ? "★" : ""}</span>
                <span className={cn("text-[10px] font-black font-mono flex-1", cmp === "BULLISH" ? "text-emerald-400" : cmp === "BEARISH" ? "text-red-400" : "text-zinc-600")}>
                  {cmp === "BULLISH" ? "BUY" : cmp === "BEARISH" ? "SELL" : "─"}
                </span>
                <FasePill fase={fase} />
              </div>
            ))}
          </div>
        )}

        {/* Compact delta */}
        {N_TICKS >= 5 && (
          <div className="bg-zinc-900/60 rounded-lg border border-zinc-800 overflow-hidden">
            <div className="px-2 py-1 border-b border-zinc-800 text-[9px] font-black font-mono text-cyan-500 tracking-widest">[ DELTA.FLOW ]</div>
            <div className="px-2 py-2 space-y-1">
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-emerald-500 font-mono w-6">BUY</span>
                <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                  <div className={cn("h-full bg-emerald-500 rounded-full anim-delta-fill", momentum === "BULL" && blink && "shadow-[0_0_6px_rgba(52,211,153,0.5)]")} style={{ width: `${buyPct}%` }} />
                </div>
                <span className="text-[9px] text-emerald-400 font-mono w-8 text-right">{buyPct}%</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-red-500 font-mono w-6">SEL</span>
                <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                  <div className="h-full bg-red-500 rounded-full anim-delta-fill" style={{ width: `${sellPct}%` }} />
                </div>
                <span className="text-[9px] text-red-400 font-mono w-8 text-right">{sellPct}%</span>
              </div>
              <div className="flex items-center justify-between pt-0.5">
                <span className={cn("text-[9px] font-black font-mono", momentumCol)}>{momentumStr}</span>
                <span className={cn("text-[9px] font-mono", cumDelta >= 0 ? "text-emerald-600" : "text-red-600")}>Δ{cumDelta >= 0 ? "+" : ""}{cumDelta.toFixed(2)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════════
  // DASHBOARD MODE
  // ══════════════════════════════════════════════════════════════════════════════
  return (
    <div className="px-5 py-1.5 xl:px-8 space-y-1.5 w-full anim-crt">
      <style>{ANIM_CSS}</style>
      {alertToasts}

      {/* ── HEADER ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-1 border-b border-zinc-800/80">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500/20 to-yellow-600/10 border border-amber-500/30 shrink-0">
            <ZapIcon className="w-4 h-4 text-amber-400 animate-pulse" />
            {hasAnyF3 && <div className={cn("absolute inset-0 rounded-xl", blink ? "shadow-[0_0_16px_rgba(245,158,11,0.5)]" : "")} />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="cr-hd-title text-sm xl:text-base font-black font-mono text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-yellow-500 tracking-tight uppercase">CHAIN REACTION</span>
              <span className="cr-label-xs text-[9px] px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono font-bold">CMP ENGINE v6.3</span>
              {hasAnyF3 && <span className={cn("cr-label-xs text-[9px] px-2 py-0.5 rounded-full border font-black font-mono bg-amber-500 border-amber-400 text-black", blink && "shadow-[0_0_10px_rgba(245,158,11,0.7)]")}>⚡ SIGNAL ACTIVE</span>}
            </div>
            <div className="cr-hd-sub text-[9px] text-zinc-600 font-mono tracking-widest uppercase">Dadang Wahyuono · XAUUSD CFD · Daily Deploy System</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {tvStatus === "connected" ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-950/30 border border-emerald-700/40 text-emerald-400">
              <span className="relative flex h-1.5 w-1.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" /><span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" /></span>
              <span className="text-[9px] font-black font-mono tracking-wider">CDP :9222 LIVE</span>
            </div>
          ) : tvStatus === "error" ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-950/30 border border-red-700/40 text-red-400">
              <WifiOffIcon className="w-3 h-3" /><span className="text-[9px] font-black font-mono">CDP OFFLINE</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-500">
              <WifiIcon className="w-3 h-3 opacity-50" /><span className="text-[9px] font-black font-mono">WAITING SYNC</span>
            </div>
          )}
        </div>
      </div>

      {/* ── PRICE BAR ──────────────────────────────────────────────────────── */}
      <div className={cn(
        "rounded-xl border px-5 py-2 transition-all duration-300",
        priceFlash === "up" ? "anim-flash-up border-emerald-600/40 bg-zinc-950" :
        priceFlash === "dn" ? "anim-flash-dn border-red-600/40 bg-zinc-950"     :
        "bg-gradient-to-r from-zinc-900/80 via-zinc-950 to-zinc-900/80 border-amber-500/20"
      )}>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className="text-[10px] text-amber-500 font-black font-mono tracking-widest">XAUUSD CFD</span>
              <span className={cn("text-[9px] px-2 py-0.5 rounded-full border font-black font-mono",
                livePrice ? "bg-emerald-950 border-emerald-700/40 text-emerald-400" : "bg-zinc-900 border-zinc-700 text-zinc-600"
              )}>{livePrice ? (blink ? "● LIVE TICK" : "○ LIVE TICK") : "○ OFFLINE"}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="text-zinc-500">SPREAD <span className="text-zinc-200 font-bold">{spread}</span></span>
              <span className="text-zinc-700">│</span>
              <span className="text-zinc-500">SESSION <span className="text-zinc-200 font-bold">{sess}</span></span>
              {N_TICKS >= 5 && (
                <>
                  <span className="text-zinc-700">│</span>
                  <span className={cn("font-bold", momentumCol)}>{momentumStr}</span>
                </>
              )}
            </div>
          </div>
          <div className="text-right">
            <div className={cn(
              "cr-price-display text-[38px] xl:text-[52px] font-black font-mono tabular-nums tracking-tight transition-all duration-100",
              priceFlash === "up" ? "text-emerald-300 anim-price-glow-up" :
              priceFlash === "dn" ? "text-red-300 anim-price-glow-dn"     :
              livePrice           ? "text-amber-300 anim-price-glow"      : "text-zinc-600"
            )}>{displayPrice}</div>
          </div>
        </div>
      </div>

      {/* ── NEWS BLACKOUT BANNER ──────────────────────────────────────────── */}
      {(newsBlackout || newsApproaching) && (
        <div className={cn(
          "rounded-xl border px-4 py-2.5 flex items-center gap-3 relative overflow-hidden",
          newsBlackout
            ? "bg-red-950/40 border-red-500/70 anim-glow-red"
            : "bg-amber-950/30 border-amber-500/50 anim-amber-border"
        )}>
          <span className={cn("text-lg shrink-0", newsBlackout ? (blinkFast ? "text-red-300" : "text-red-600") : "text-amber-400")}>
            {newsBlackout ? "🚨" : "⚠"}
          </span>
          <div className="flex-1">
            <div className={cn("text-[11px] font-black font-mono tracking-wider", newsBlackout ? "text-red-300" : "text-amber-300")}>
              {newsBlackout
                ? `BLACKOUT — ${nextEventName} dalam ${minutesUntilNews} menit (${nextEventTimeWIB}) · TAHAN SEMUA ENTRY BARU`
                : `NEWS APPROACHING — ${nextEventName} dalam ${minutesUntilNews} menit (${nextEventTimeWIB}) · Pertimbangkan exit posisi`}
            </div>
            {newsBlackout && (
              <div className="text-[9px] font-mono text-red-600 mt-0.5">
                Tunggu sampai berita rilis + 5 menit spread normal sebelum entry baru
              </div>
            )}
          </div>
          {newsBlackout && (
            <span className={cn(
              "shrink-0 text-[13px] font-black font-mono px-2.5 py-1 rounded border tabular-nums",
              blinkFast ? "bg-red-500 border-red-400 text-white" : "bg-red-950 border-red-700 text-red-400"
            )}>
              {minutesUntilNews}m
            </span>
          )}
        </div>
      )}

      {/* ── SITREP BAR ────────────────────────────────────────────────────── */}
      {sitrep && (
        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 px-4 py-2 flex items-center gap-0 overflow-hidden">
          <span className="text-[8px] font-black font-mono text-zinc-600 tracking-[0.2em] uppercase mr-3 shrink-0">SITREP</span>
          {/* BIAS */}
          <div className="flex items-center gap-1.5 pr-3 border-r border-zinc-800 shrink-0">
            <span className="text-[8px] text-zinc-600 font-mono uppercase">BIAS</span>
            <span className={cn("text-[11px] font-black font-mono",
              sitrep.biasDir === "BULLISH" ? "text-emerald-400" :
              sitrep.biasDir === "BEARISH" ? "text-red-400"     : "text-zinc-500"
            )}>{sitrep.biasLabel}</span>
          </div>
          {/* PRIME */}
          <div className="flex items-center gap-1.5 px-3 border-r border-zinc-800 shrink-0">
            <span className="text-[8px] text-zinc-600 font-mono uppercase">PRIME</span>
            <span className={cn("text-[10px] font-black font-mono",
              sitrep.primeLabel.includes("F3") ? (blinkFast ? "text-amber-300" : "text-amber-500") :
              sitrep.primeLabel.includes("F2") ? "text-blue-400" : "text-zinc-500"
            )}>{sitrep.primeLabel}</span>
          </div>
          {/* SCALP */}
          <div className="flex items-center gap-1.5 px-3 border-r border-zinc-800 shrink-0">
            <span className="text-[8px] text-zinc-600 font-mono uppercase">SCALP</span>
            <span className={cn("text-[10px] font-black font-mono",
              sitrep.scalpLabel === "⚡ ENTRY"   ? (blinkFast ? "text-amber-200" : "text-amber-400") :
              sitrep.scalpLabel === "WAIT M5 CF" ? "text-blue-400" :
              sitrep.scalpLabel === "SKIP DIR"   ? "text-red-600"  : "text-zinc-500"
            )}>{sitrep.scalpLabel}</span>
          </div>
          {/* NEWS */}
          <div className="flex items-center gap-1.5 px-3 border-r border-zinc-800 shrink-0">
            <span className="text-[8px] text-zinc-600 font-mono uppercase">NEWS</span>
            <span className={cn("text-[10px] font-black font-mono",
              sitrep.newsLabel.startsWith("🚨") ? (blinkFast ? "text-red-300"   : "text-red-500")   :
              sitrep.newsLabel.startsWith("⚠")  ? "text-amber-400" : "text-emerald-600"
            )}>{sitrep.newsLabel}</span>
          </div>
          {/* GRADE */}
          <div className="flex items-center gap-1.5 pl-3 shrink-0">
            <span className="text-[8px] text-zinc-600 font-mono uppercase">GRADE</span>
            <span className={cn(
              "text-[11px] font-black font-mono px-2 py-0.5 rounded border",
              sitrep.gradeLabel === "A+"   ? (blinkFast ? "bg-amber-500 border-amber-400 text-black" : "bg-amber-950 border-amber-600 text-amber-300")   :
              sitrep.gradeLabel === "A"    ? "bg-emerald-950 border-emerald-700 text-emerald-300" :
              sitrep.gradeLabel === "B"    ? "bg-blue-950 border-blue-700 text-blue-300"          :
              sitrep.gradeLabel === "C"    ? "bg-zinc-900 border-zinc-700 text-zinc-400"          :
              sitrep.gradeLabel === "SKIP" ? "bg-red-950 border-red-800 text-red-500"             :
              "bg-zinc-950 border-zinc-800 text-zinc-600"
            )}>
              {sitrep.gradeLabel}
            </span>
            {sitrep.gradeLabel !== "—" && (
              <span className="text-[8px] font-mono text-zinc-600 max-w-[140px] truncate hidden xl:block">{autoGrade.reason}</span>
            )}
          </div>
        </div>
      )}

      {/* ── SYNC ROW 1: TradingView + SNR ─────────────────────────────────── */}
      <div className="flex gap-2 items-center">
        <button onClick={syncTV} disabled={syncing} className={cn("cr-sync-btn flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-[10px] xl:text-[13px] font-black font-mono tracking-widest uppercase border transition-all",
          syncing ? "bg-zinc-900 border-zinc-800 text-zinc-600 cursor-not-allowed"
          : tvStatus === "connected" ? "bg-emerald-950/20 border-emerald-700/40 text-emerald-400 hover:bg-emerald-950/40"
          : tvStatus === "error" ? "bg-red-950/20 border-red-700/30 text-red-400"
          : "bg-zinc-900/60 border-zinc-800 text-zinc-300 hover:border-amber-500/40 hover:text-amber-400"
        )}>
          <RefreshCwIcon className={cn("w-3.5 h-3.5", syncing && "animate-spin text-amber-500")} />
          {syncing ? "READING CHARTS..." : "⚡ SYNC TRADINGVIEW"}
        </button>
        <button onClick={syncSNR} disabled={syncingSNR} className={cn("cr-sync-btn flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-[10px] xl:text-[13px] font-black font-mono tracking-widest uppercase border transition-all",
          syncingSNR ? "bg-zinc-900 border-zinc-800 text-zinc-600 cursor-not-allowed"
          : snrStatus === "ok" ? "bg-blue-950/20 border-blue-700/40 text-blue-400 hover:bg-blue-950/40"
          : "bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:border-blue-700/40 hover:text-blue-400"
        )}>
          <BarChart2Icon className={cn("w-3.5 h-3.5", syncingSNR && "animate-pulse text-blue-500")} />
          {syncingSNR ? "EXTRACTING SNR..." : "📊 SYNC FUNDAMENTAL SNR"}
        </button>
        <div className="flex items-center gap-2 px-2 text-[9px] font-mono text-zinc-600 shrink-0">
          <ClockIcon className="w-3 h-3 text-zinc-700" />
          <span>{lastSync ? timeAgo(lastSync) : "never"}</span>
        </div>
        <label className="flex items-center gap-2 cursor-pointer shrink-0">
          <span className="text-[9px] font-mono text-zinc-600 uppercase">Auto 30s</span>
          <button onClick={() => setAutoSync(p => !p)} className={cn("relative shrink-0 border rounded-full transition-colors", autoSync ? "bg-amber-500 border-amber-400" : "bg-zinc-800 border-zinc-700")} style={{ width: 32, height: 18 }}>
            <span className={cn("absolute top-[2px] w-3.5 h-3.5 rounded-full bg-white transition-all shadow", autoSync ? "left-[14px]" : "left-[2px]")} />
          </button>
        </label>
      </div>

      {/* ── SYNC ROW 2: News (external) ────────────────────────────────────── */}
      <div className="flex gap-2 items-center">
        <button onClick={syncNews} disabled={syncingNews} className={cn(
          "cr-sync-btn flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-[10px] xl:text-[13px] font-black font-mono tracking-widest uppercase border transition-all",
          syncingNews ? "bg-zinc-900 border-zinc-800 text-zinc-600 cursor-not-allowed"
          : newsStatus === "ok"    ? "bg-violet-950/20 border-violet-700/40 text-violet-400 hover:bg-violet-950/40"
          : newsStatus === "error" ? "bg-red-950/20 border-red-700/30 text-red-400"
          : "bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:border-violet-700/40 hover:text-violet-400"
        )}>
          {syncingNews
            ? <RefreshCwIcon className="w-3.5 h-3.5 animate-spin text-violet-400" />
            : <GlobeIcon className="w-3.5 h-3.5" />}
          {syncingNews ? "FETCHING NEWS..." : "SYNC NEWS + KALENDER"}
        </button>
        <div className="flex items-center gap-2 px-2 text-[9px] font-mono text-zinc-700 shrink-0">
          {newsStatus === "ok" && (
            <span className="text-violet-700">
              {lastNewsSync ? `✓ ${timeAgo(lastNewsSync)}` : "✓ synced"}
            </span>
          )}
          {newsStatus === "error" && (
            <span className="text-red-800">✗ error</span>
          )}
          {newsStatus === "unknown" && (
            <span>ForexFactory · Yahoo Finance</span>
          )}
        </div>
      </div>

      {tvError && (
        <div className="bg-red-950/20 border border-red-700/30 rounded-xl px-4 py-2.5">
          <span className="text-[10px] text-red-400 font-black font-mono">SYNC ERROR · </span>
          <span className="text-[10px] text-red-400/70 font-mono">{tvError.slice(0, 140)}</span>
        </div>
      )}
      {newsError && (
        <div className="bg-red-950/20 border border-red-700/30 rounded-xl px-4 py-2">
          <span className="text-[10px] text-red-400 font-black font-mono">NEWS ERROR · </span>
          <span className="text-[10px] text-red-400/70 font-mono">{newsError.slice(0, 140)}</span>
        </div>
      )}

      {/* ── SNIPER ACTIVE BANNER ───────────────────────────────────────────── */}
      {hasAnyF3 && (
        <div className={cn(
          "cr-sniper-banner relative overflow-hidden rounded-xl border px-4 py-1.5 anim-amber-border",
          "bg-gradient-to-r from-amber-950/30 via-yellow-950/20 to-amber-950/30"
        )}>
          {/* Scanline sweeper */}
          <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
            <div className="anim-scan-h absolute top-0 left-0 h-full w-1/3 bg-gradient-to-r from-transparent via-amber-400/10 to-transparent" />
          </div>
          <div className="flex items-center gap-3">
            <span className={cn("text-base shrink-0", blinkFast ? "text-amber-300" : "text-amber-900")}>⚡</span>
            <div className="overflow-hidden flex-1">
              <div className="anim-marquee whitespace-nowrap text-[10px] font-black font-mono text-amber-400 tracking-widest">
                {tfData.filter(d => d.fase === 3).map(d =>
                  `⚡ SNIPER ACTIVE — ${d.tf} FASE 3 ${d.cmp === "BULLISH" ? "BUY" : "SELL"} PRIME ENTRY · CHAIN REACTION LOCKED IN ·`
                ).join("   ")}
              </div>
            </div>
            <span className={cn(
              "shrink-0 text-[10px] font-black font-mono px-2.5 py-1 rounded border",
              blinkFast
                ? "bg-amber-500 border-amber-400 text-black shadow-[0_0_16px_rgba(245,158,11,0.7)]"
                : "bg-amber-950 border-amber-800 text-amber-600"
            )}>PRIME</span>
          </div>
        </div>
      )}

      {/* ── MAIN GRID ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-[1fr_220px] xl:grid-cols-[1fr_270px] 2xl:grid-cols-[1fr_310px] gap-2">

        {/* ─── LEFT COLUMN ─── */}
        <div className="space-y-2">

          {/* ══ SIGNAL.HEATMAP ══ */}
          <PanelBox
            title={<PanelTitle label="SIGNAL.HEATMAP" />}
            cls={cn("border-fuchsia-900/40 anim-neon-border")}
            scanV={hasAnyF3}
          >
            {hasTFData ? (
              <table className="cr-heatmap-table w-full text-[10px] font-mono">
                <thead>
                  <tr className="border-b border-zinc-800/80 bg-zinc-900/60">
                    {["TF","CMP","FASE","VR","CF","ENTRY AT"].map(h => (
                      <th key={h} className="px-2 py-0.5 text-center text-cyan-500 font-black tracking-widest first:px-3 first:text-left last:text-left last:px-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tfData.filter(d => !!d.cmp).map(({ tf, cmp, vr, cf, cfCount, cfType, fase, sl }) => {
                    const isMaster = tf === "H4";
                    const isBull   = cmp === "BULLISH";
                    const isBear   = cmp === "BEARISH";
                    const f3row    = fase === 3;
                    return (
                      <tr key={tf} className={cn(
                        "border-b border-zinc-800/40 last:border-0 transition-colors",
                        f3row ? "anim-row-fire-fast border-l-2 border-l-amber-400" :
                        fase === 2 ? "bg-blue-950/15 border-l-2 border-l-blue-600" :
                        "border-l-2 border-l-transparent hover:bg-zinc-900/30"
                      )}>
                        <td className="px-3 py-1">
                          {isMaster
                            ? <span className={cn("text-[11px] font-black", blinkFast && f3row ? "text-amber-200" : "text-amber-500")}>H4 ★</span>
                            : <span className={cn("text-[11px] font-black", f3row ? (blinkFast ? "text-amber-200" : "text-amber-500") : "text-cyan-400")}>{tf}</span>}
                        </td>
                        <td className="px-2 py-1 text-center"><CmpBadge cmp={cmp} pulse={f3row} /></td>
                        <td className="px-2 py-1 text-center"><FasePill fase={fase} /></td>
                        <td className="px-2 py-1 text-center">
                          {vr === "YA"
                            ? <span className={cn("font-black text-blue-400", blink && "drop-shadow-[0_0_4px_rgba(96,165,250,0.8)]")}>⚡{sl?.vrFrom}✓</span>
                            : <span className="text-zinc-700">BELUM</span>}
                        </td>
                        <td className="px-2 py-1 text-center">
                          {cf === "YA"
                            ? <span className={cn("font-black text-emerald-400", blink && "drop-shadow-[0_0_4px_rgba(52,211,153,0.8)]")}>{blink ? "◉" : "●"}CF{cfCount > 0 ? ` #${cfCount}` : "✓"}{cfType ? <span className="text-[8px] text-emerald-600 ml-0.5">{cfType}</span> : null}</span>
                            : <span className="text-zinc-600">{cfCount > 0 ? <span className="text-amber-700">flip · tunggu #{cfCount + 1}</span> : <>{sl?.cfLow || "—"}{sl?.cfHigh ? `/${sl.cfHigh}` : ""}</>}</span>}
                        </td>
                        <td className="px-3 py-1">
                          {fase === 3
                            ? <span className={cn("font-black text-[11px] transition-all duration-100",
                                isBull
                                  ? blinkFast ? "text-emerald-200 drop-shadow-[0_0_8px_rgba(52,211,153,0.9)]" : "text-emerald-500"
                                  : blinkFast ? "text-red-200 drop-shadow-[0_0_8px_rgba(248,113,113,0.9)]" : "text-red-500"
                              )}>
                                {blinkFast ? "⚡" : "●"} {isBull ? "BUY" : "SELL"} @{sl?.tradeTF}
                              </span>
                            : fase === 2
                              ? <span className="text-blue-400">Tunggu CF {sl?.cfLow}</span>
                              : <span className="text-zinc-600">Scalp · TP terbatas</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="relative py-8 px-4 overflow-hidden">
                {/* Matrix rain chars */}
                <div className="absolute inset-0 flex gap-4 overflow-hidden opacity-20 pointer-events-none select-none">
                  {["01001011","11000101","00110110","10101010","01110010","11001100"].map((s,i) => (
                    <div key={i} className="flex flex-col gap-1" style={{ animation: `matrix-fall ${2 + i * 0.4}s ease-in-out ${i * 0.3}s infinite` }}>
                      {s.split("").map((c, j) => (
                        <span key={j} className="text-[8px] font-mono text-emerald-500">{c}</span>
                      ))}
                    </div>
                  ))}
                </div>
                <div className="relative text-center space-y-1.5">
                  <div className="text-[10px] text-zinc-600 font-black font-mono animate-pulse tracking-[0.3em]">[ AWAITING SYNC ]</div>
                  <div className="text-[9px] text-zinc-700 font-mono">Klik ⚡ SYNC TRADINGVIEW untuk load data</div>
                  <div className="text-[9px] text-emerald-900 font-mono">› CDP :9222 · CMP Engine v6.3</div>
                </div>
              </div>
            )}
          </PanelBox>

          {/* ══ SCALP.CYCLE ══ */}
          {hasTFData && (
            <PanelBox
              title={
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "w-1.5 h-1.5 rounded-full shrink-0",
                    scalpPhase === 3 ? "anim-pulse-dot-fast bg-amber-400" :
                    scalpActive      ? "anim-pulse-dot bg-emerald-400"    : "bg-zinc-700"
                  )} />
                  <span className="cr-label-sm text-[10px] font-black font-mono text-cyan-400 tracking-widest">[ SCALP.CYCLE ]</span>
                  <span className={cn(
                    "text-[9px] font-black font-mono px-1.5 py-0.5 rounded border",
                    scalpPhase === 3
                      ? blinkFast ? "bg-amber-500 border-amber-400 text-black" : "bg-amber-950 border-amber-700 text-amber-400"
                      : scalpPhase === 2
                        ? "bg-blue-950/40 border-blue-700/50 text-blue-400"
                        : scalpActive
                          ? "bg-emerald-950/30 border-emerald-800/50 text-emerald-600"
                          : "bg-zinc-900 border-zinc-800 text-zinc-600"
                  )}>
                    {scalpPhase === 3 ? "⚡ ENTRY" : scalpPhase === 2 ? "WAIT CF" : scalpActive ? "ACTIVE" : "STANDBY"}
                  </span>
                  <HexTag />
                </div>
              }
              cls={cn(
                // Cuma ENTRY (phase 3) yang "signal" (border amber pulse tajam).
                // Phase lain = kalem/steady (ambient), gak narik perhatian berlebih.
                scalpPhase === 3 ? "border-amber-500/70 anim-amber-border" :
                scalpPhase === 2 ? "border-cyan-800/40"                     :
                scalpActive      ? "border-emerald-800/30"                  :
                "border-zinc-800/50"
              )}
              scanV={scalpPhase === 3}
            >
              <div className="px-4 py-2 space-y-2">

                {/* ── STANDBY: H4 and H1 not F3 ── */}
                {!scalpActive && (
                  <div className="py-2 text-center space-y-1">
                    <div className="text-[10px] font-mono text-zinc-600 tracking-wider">
                      Menunggu H4 atau H1 F3 aktif
                    </div>
                    <div className="text-[9px] font-mono text-zinc-700">
                      Scalp aktif saat setup besar sudah prime entry
                    </div>
                    {m30cmp && (
                      <div className="mt-2 flex items-center justify-center gap-3 text-[9px] font-mono">
                        <span className="text-zinc-600">M30:</span>
                        <span className={m30cmp === "BULLISH" ? "text-emerald-600" : "text-red-600"}>
                          {m30cmp === "BULLISH" ? "▲BUY" : "▼SELL"}
                        </span>
                        <span className="text-zinc-800">·</span>
                        <span className="text-zinc-600">VR:&nbsp;
                          {m30vr === "YA"
                            ? <span className="text-blue-600">✓</span>
                            : <span className="text-zinc-700">—</span>}
                        </span>
                        <span className="text-zinc-800">·</span>
                        <span className="text-zinc-600">CF:&nbsp;
                          {m30cf === "YA"
                            ? <span className="text-emerald-600">✓</span>
                            : <span className="text-zinc-700">—</span>}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* ── ACTIVE: H4 or H1 is F3 ── */}
                {scalpActive && (
                  <>
                    {/* Master direction label */}
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] text-zinc-600 font-mono uppercase tracking-widest shrink-0">MASTER</span>
                      <span className={cn(
                        "text-[10px] font-black font-mono px-2 py-0.5 rounded border",
                        scalpIsBull
                          ? "bg-emerald-950/40 border-emerald-700 text-emerald-300"
                          : "bg-red-950/40 border-red-700 text-red-300"
                      )}>
                        {scalpMasterTF} ★ {scalpIsBull ? "▲ BUY" : "▼ SELL"}
                      </span>
                      <span className="text-[9px] text-zinc-600 font-mono">
                        → scalp {scalpIsBull ? "BUY" : "SELL"} M30
                      </span>
                    </div>

                    {/* ══ PIPELINE STEPPER (REDESIGN) — progress chain yang jelas ══
                        done=hijau ✓ · sekarang=cyan napas · pending=redup · ENTRY=amber SIGNAL */}
                    {(() => {
                      const done1 = m30Aligned;            // M30 CMP searah
                      const done2 = m30vr === "YA";        // M15 VR
                      const entry = m30CfActive;           // M5 CF = ENTRY
                      const waitVR = done1 && !done2;
                      const waitCF = done2 && !entry;
                      const s1 = done1 ? "done" : (m30cmp ? "fail" : "now");
                      const s2 = done2 ? "done" : (waitVR ? "now" : "pending");
                      const s3 = entry ? "signal" : (waitCF ? "now" : "pending");
                      const steps = [
                        { n: 1, tf: "M30", role: "CMP", state: s1, val: m30cmp, txt: done1 ? "searah" : m30cmp ? "lawan" : "—" },
                        { n: 2, tf: "M15", role: "VR",  state: s2, val: m15cmp, txt: done2 ? "VR ✓" : waitVR ? "ditunggu" : "—" },
                        { n: 3, tf: "M5",  role: "CF",  state: s3, val: m5cmp,  txt: entry ? `CF${m30CfCount > 0 ? " #" + m30CfCount : ""}` : waitCF ? "ditunggu" : "—" },
                      ];
                      const doneCount = (done1?1:0) + (done2?1:0) + (entry?1:0);
                      const pct = entry ? 100 : done2 ? 66 : done1 ? 33 : 0;
                      const nowStep = steps.find(s => s.state === "now");
                      const circleCls: Record<string,string> = {
                        done:   "bg-emerald-500 border-emerald-400 text-black",
                        now:    "bg-cyan-950 border-cyan-400 text-cyan-200 anim-ambient-ring",
                        signal: "bg-amber-400 border-amber-200 text-black anim-signal-pulse anim-signal-pop",
                        pending:"bg-zinc-900 border-zinc-700 text-zinc-600",
                        fail:   "bg-red-950 border-red-600 text-red-300",
                      };
                      const labelCls: Record<string,string> = {
                        done:"text-emerald-400", now:"text-cyan-300", signal:"text-amber-300", pending:"text-zinc-600", fail:"text-red-400",
                      };
                      return (
                        <div className="space-y-2 py-1">
                          {/* status line */}
                          <div className="flex items-center gap-2 text-[10px] font-mono">
                            <span className="text-zinc-500 uppercase tracking-widest">PROGRESS</span>
                            <span className="flex gap-1">
                              {[0,1,2].map(i => (
                                <span key={i} className={cn("w-2 h-2 rounded-full transition-all",
                                  i < doneCount ? "bg-emerald-400"
                                  : (i === doneCount && nowStep) ? "bg-cyan-400 anim-ambient-dot"
                                  : "bg-zinc-700")} />
                              ))}
                            </span>
                            <span className="flex-1" />
                            {entry
                              ? <span className={cn("font-black", blinkFast ? "text-amber-200" : "text-amber-400")}>⚡ ENTRY SIAP</span>
                              : nowStep
                                ? <span className="text-cyan-300">← nunggu <b className="text-cyan-200">{nowStep.tf} {nowStep.role}</b></span>
                                : <span className="text-zinc-600">—</span>}
                          </div>

                          {/* stepper: circle + connector */}
                          <div className="flex items-start">
                            {steps.map((s, i) => (
                              <div key={s.n} className="flex items-start" style={{ flex: i < steps.length - 1 ? "1 1 0%" : "0 0 auto" }}>
                                {/* step column */}
                                <div className="flex flex-col items-center w-14 shrink-0">
                                  <div className={cn("w-8 h-8 rounded-full border-2 flex items-center justify-center font-black font-mono text-[13px] transition-all duration-300", circleCls[s.state])}>
                                    {s.state === "done" ? "✓" : s.state === "signal" ? "⚡" : s.state === "fail" ? "✕" : s.n}
                                  </div>
                                  <div className={cn("mt-1 text-[11px] font-black font-mono", labelCls[s.state])}>{s.tf}</div>
                                  <div className="text-[8px] font-mono text-zinc-600 -mt-0.5">{s.role}</div>
                                  <div className={cn("text-[9px] font-mono mt-0.5 text-center leading-tight", labelCls[s.state])}>
                                    {s.val ? (s.val === "BULLISH" ? "▲" : "▼") : ""}{s.txt}
                                  </div>
                                </div>
                                {/* connector */}
                                {i < steps.length - 1 && (
                                  <div className="flex-1 h-0.5 mt-4 bg-zinc-800 rounded overflow-hidden">
                                    <div className={cn("h-full transition-all duration-500",
                                      (steps[i].state === "done" || steps[i].state === "signal") ? "w-full bg-emerald-500" : "w-0")} />
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>

                          {/* progress bar */}
                          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div className={cn("h-full rounded-full transition-all duration-700",
                              entry ? "bg-amber-400 anim-signal-pulse" : "bg-gradient-to-r from-emerald-500 to-cyan-400")}
                              style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })()}

                    {/* Phase recommendation */}
                    <div className={cn(
                      "rounded-lg border px-3 py-2 space-y-1",
                      scalpPhase === 3  ? "bg-amber-950/20 border-amber-700/50"  :
                      scalpPhase === 2  ? "bg-blue-950/20 border-blue-800/50"    :
                      scalpPhase === -1 ? "bg-red-950/20 border-red-900/50"      :
                      "bg-zinc-900/60 border-zinc-800"
                    )}>
                      {scalpPhase === 0 && (
                        <>
                          <div className="text-[9px] font-black font-mono text-zinc-500">M30 belum ada CMP</div>
                          <div className="text-[8px] font-mono text-zinc-700">
                            Tunggu M30 CMP terbentuk searah {scalpIsBull ? "BUY" : "SELL"} (master {scalpMasterTF})
                          </div>
                        </>
                      )}
                      {scalpPhase === -1 && (
                        <>
                          <div className="text-[9px] font-black font-mono text-red-400">M30 BERLAWANAN — SKIP SCALP</div>
                          <div className="text-[8px] font-mono text-red-800">
                            M30 {m30cmp === "BULLISH" ? "BUY" : "SELL"} ≠ master {scalpIsBull ? "BUY" : "SELL"} → tunggu M30 CMP flip
                          </div>
                        </>
                      )}
                      {scalpPhase === 1 && (
                        <>
                          <div className="text-[9px] font-black font-mono text-zinc-300">F1 · Tunggu M15 VR</div>
                          <div className="text-[8px] font-mono text-zinc-600">M15 break berlawanan M30 = VR confirmed</div>
                          <div className="text-[8px] font-mono text-zinc-700">Jangan entry — masih CONTI territory</div>
                        </>
                      )}
                      {scalpPhase === 2 && (
                        <>
                          <div className={cn("text-[10px] font-black font-mono text-blue-300", blink && "drop-shadow-[0_0_6px_rgba(96,165,250,0.5)]")}>
                            {m30CfCount > 0
                              ? `F2 · CF #${m30CfCount} flip — Tunggu CF #${m30CfCount + 1}`
                              : "F2 · VR ✓ — Tunggu M5 CF untuk entry"}
                          </div>
                          <div className="text-[8px] font-mono text-blue-700">
                            {m30CfCount > 0
                              ? `CF #${m30CfCount} sudah selesai/flip — CMP masih valid, tunggu M5 balik searah`
                              : `M5 break ${m30IsBull ? "▲ BULLISH" : "▼ BEARISH"} = CF = MASUK SCALP`}
                          </div>
                          <div className="flex gap-4 pt-1 border-t border-blue-900/40 text-[8px] font-mono text-zinc-600">
                            <span>Entry: M5 CF</span>
                            <span>SL: swing M5 (~5-10 pts)</span>
                            <span>TP: M15 barrier</span>
                          </div>
                        </>
                      )}
                      {scalpPhase === 3 && m30CfActive && (
                        <>
                          <div className={cn("text-[10px] font-black font-mono",
                            blinkFast
                              ? m30IsBull ? "text-emerald-200 drop-shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                                          : "text-red-200 drop-shadow-[0_0_8px_rgba(248,113,113,0.8)]"
                              : m30IsBull ? "text-emerald-400" : "text-red-400"
                          )}>
                            {blinkFast ? "⚡" : "●"} {m30IsBull ? "BUY" : "SELL"} ENTRY
                            {m30CfCount > 0 && <span className="text-[8px] ml-1 opacity-70">CF #{m30CfCount}{m30CfType ? ` ${m30CfType}` : ""}</span>}
                          </div>
                          <div className="grid grid-cols-3 gap-2 pt-1 border-t border-amber-800/40 text-center">
                            <div>
                              <div className="text-[7px] font-mono text-zinc-600 uppercase">Entry</div>
                              <div className="text-[10px] font-black font-mono text-amber-300">M5 CF</div>
                            </div>
                            <div>
                              <div className="text-[7px] font-mono text-zinc-600 uppercase">SL</div>
                              <div className="text-[10px] font-black font-mono text-red-400">Swing M5</div>
                            </div>
                            <div>
                              <div className="text-[7px] font-mono text-zinc-600 uppercase">TP</div>
                              <div className="text-[10px] font-black font-mono text-emerald-400">M15 barrier</div>
                            </div>
                          </div>
                          <div className="text-[8px] font-mono text-amber-800 pt-0.5">
                            ★ SL kecil (M5 swing) → aman pakai lot lebih besar dari setup biasa
                          </div>
                        </>
                      )}
                    </div>

                    {/* Cycle repeat note */}
                    <div className="flex items-center gap-1.5 text-[8px] font-mono text-zinc-700">
                      <span>⟳</span>
                      <span>Repeat cycle selama {scalpMasterTF} F3 aktif · Stop saat {scalpMasterTF} CMP flip</span>
                    </div>
                  </>
                )}
              </div>
            </PanelBox>
          )}

          {/* ══ NEURAL.FLOW ══ */}
          <PanelBox
            title={<PanelTitle label="NEURAL.FLOW — CHAIN SEQUENCE" live={!!livePrice} />}
            cls={cn(
              h4Fase === 3 ? "border-amber-600/60 anim-amber-border" :
              h4Fase === 2 ? "border-blue-700/50 anim-glow-blue"    : "border-zinc-800"
            )}
            scanV={h4Fase === 3}
          >
            <div className="px-4 py-1">
              {hasTFData ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="cr-label-xs text-[9px] text-zinc-600 font-mono uppercase tracking-widest">H4 MASTER BIAS</span>
                    <div className="flex-1 h-px bg-zinc-800" />
                    {h4Dir === "BULLISH"
                      ? <span className={cn("text-[10px] font-black font-mono px-2 py-0.5 rounded bg-emerald-950 border border-emerald-700 text-emerald-300", blink && "shadow-[0_0_10px_rgba(52,211,153,0.35)]")}>▲ BULLISH</span>
                      : h4Dir === "BEARISH"
                        ? <span className={cn("text-[10px] font-black font-mono px-2 py-0.5 rounded bg-red-950 border border-red-700 text-red-300", blink && "shadow-[0_0_10px_rgba(248,113,113,0.35)]")}>▼ BEARISH</span>
                        : <span className="text-[10px] font-mono text-zinc-600">H4 WAIT</span>}
                  </div>

                  {/* Chain nodes */}
                  <div className="flex items-center gap-1 overflow-x-auto pb-1">
                    {chainNodes.map((node, i) => {
                      const tf      = node.tf;
                      const cmp     = tf?.cmp || "";
                      const fase    = tf?.fase || 0;
                      const aligned = h4Dir && cmp === h4Dir;
                      const isBull  = cmp === "BULLISH";

                      let nodeBg = "bg-zinc-900 border-zinc-700 text-zinc-600";
                      let extraCls = "";
                      if (node.isMaster && cmp) {
                        nodeBg   = "bg-amber-950/60 border-amber-500 text-amber-300";
                        extraCls = blinkFast ? "shadow-[0_0_18px_rgba(245,158,11,0.55)]" : "shadow-[0_0_6px_rgba(245,158,11,0.2)]";
                      } else if (fase === 3) {
                        nodeBg   = blinkFast
                          ? "bg-amber-950/50 border-amber-400 text-amber-200 shadow-[0_0_14px_rgba(245,158,11,0.5)]"
                          : "bg-amber-950/25 border-amber-700 text-amber-400";
                        extraCls = "";
                      } else if (fase === 2) {
                        nodeBg   = "bg-blue-950/30 border-blue-700 text-blue-300";
                        extraCls = "anim-glow-blue";
                      } else if (aligned) {
                        nodeBg   = isBull ? "bg-emerald-950/25 border-emerald-800 text-emerald-400" : "bg-red-950/25 border-red-800 text-red-400";
                      } else if (cmp) {
                        nodeBg   = "bg-zinc-900 border-zinc-700 text-zinc-400";
                      }

                      const pipeActive = aligned && i < chainNodes.length - 1 && chainNodes[i+1]?.tf?.cmp === h4Dir;
                      return (
                        <div key={node.id} className="flex items-center gap-1 shrink-0">
                          <div className={cn("cr-neural-node rounded-lg border px-2.5 py-1.5 xl:px-3 xl:py-2.5 text-center min-w-[58px] xl:min-w-[76px] transition-all duration-100", nodeBg, extraCls)}>
                            <div className="cr-label-xs text-[9px] xl:text-[11px] font-black font-mono tracking-widest">{node.label}</div>
                            <div className="cr-label-xs text-[9px] xl:text-[11px] font-mono mt-0.5">
                              {cmp ? (isBull ? "▲BUY" : "▼SELL") : "──"}
                            </div>
                            {tf && cmp && <div className="mt-0.5"><FasePill fase={fase} /></div>}
                          </div>
                          {i < chainNodes.length - 1 && (
                            <span className={cn("font-mono shrink-0 text-sm transition-all duration-100",
                              pipeActive
                                ? (blinkFast ? "text-emerald-300 drop-shadow-[0_0_6px_rgba(52,211,153,0.8)] anim-chain-flow" : "text-emerald-500")
                                : "text-zinc-700"
                            )}>══►</span>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Summary bar */}
                  <div className="border-t border-zinc-800/60 pt-0.5 flex items-center gap-3 flex-wrap">
                    {(() => {
                      const alignCount = tfData.filter(d => d.cmp && d.cmp === h4Dir).length;
                      const total      = tfData.filter(d => !!d.cmp).length;
                      const col        = alignCount >= 5 ? "text-emerald-400" : alignCount >= 3 ? "text-amber-400" : "text-red-400";
                      return (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[9px] text-zinc-600 font-mono uppercase">ALIGN</span>
                          {Array.from({ length: total }).map((_, i) => (
                            <span key={i} className={cn("text-sm leading-none", i < alignCount ? col : "text-zinc-800")}>▰</span>
                          ))}
                          <span className={cn("text-[10px] font-black font-mono", col)}>{alignCount}/{total}</span>
                        </div>
                      );
                    })()}
                    {(() => {
                      const f3 = tfData.filter(d => d.fase === 3);
                      if (f3.length) return (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[9px] text-zinc-600 font-mono uppercase">SETUP</span>
                          {f3.map(d => (
                            <span key={d.tf} className={cn(
                              "text-[10px] font-black font-mono px-1.5 py-0.5 rounded border transition-all duration-100",
                              blinkFast
                                ? "bg-amber-500 border-amber-300 text-black shadow-[0_0_16px_rgba(245,158,11,0.7)]"
                                : "bg-amber-950/40 border-amber-700/60 text-amber-400"
                            )}>
                              {blinkFast ? "⚡" : "◉"} {d.tf} F3 PRIME
                            </span>
                          ))}
                        </div>
                      );
                      const f2 = tfData.filter(d => d.fase === 2);
                      if (f2.length) return (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[9px] text-zinc-600 font-mono uppercase">WATCHING</span>
                          {f2.map(d => <span key={d.tf} className="text-[10px] font-bold font-mono text-blue-400">{d.tf} F2</span>)}
                        </div>
                      );
                      return <span className="text-[9px] font-mono text-zinc-700">F1 · waiting VR phase</span>;
                    })()}
                  </div>
                </div>
              ) : (
                <div className="text-center py-5">
                  <p className="text-[10px] text-zinc-700 font-mono animate-pulse">[ AWAITING SYNC ]</p>
                </div>
              )}
            </div>
          </PanelBox>

          {/* ══ DELTA.FLOW ══ */}
          <PanelBox
            title={<PanelTitle label="DELTA.FLOW — TICK PRESSURE" live={N_TICKS > 0} />}
            cls={cn(
              "border-zinc-800",
              momentum === "BULL" && N_TICKS >= 10 ? "anim-glow-blue" : ""
            )}
            extra={
              <div className="flex items-center gap-2">
                {divergence && (
                  <span className={cn("text-[9px] font-black font-mono px-2 py-0.5 rounded bg-orange-950 border border-orange-700 text-orange-400",
                    blink && "shadow-[0_0_8px_rgba(251,146,60,0.4)]")}>
                    ⚠ DIVERGENCE
                  </span>
                )}
                <span className="text-[9px] text-zinc-700 font-mono">{N_TICKS} ticks</span>
              </div>
            }
          >
            <div className="px-4 py-1 space-y-1">
              {N_TICKS < 3 ? (
                <div className="text-center py-4">
                  <div className="text-[10px] text-zinc-700 font-mono animate-pulse">COLLECTING TICK DATA...</div>
                  <div className="text-[9px] text-zinc-800 font-mono mt-1">Requires live price feed (CDP active)</div>
                </div>
              ) : (
                <>
                  {/* Buy / Sell bars */}
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="cr-label-xs text-[9px] font-black font-mono text-emerald-400 w-6 xl:w-8">BUY</span>
                      <div className="cr-buybar-track flex-1 h-4 xl:h-6 bg-zinc-900 rounded border border-zinc-800 overflow-hidden relative">
                        <div
                          className="h-full rounded anim-delta-fill transition-all duration-500"
                          style={{
                            width: `${buyPct}%`,
                            background: momentum === "BULL"
                              ? `linear-gradient(90deg, #065f46, #34d399)`
                              : `linear-gradient(90deg, #064e3b, #10b981)`,
                            boxShadow: blink && momentum === "BULL" ? "0 0 8px rgba(52,211,153,0.5)" : undefined,
                          }}
                        />
                        <span className="absolute inset-0 flex items-center px-2 text-[9px] xl:text-[11px] font-black font-mono text-emerald-200">{buyPct}%</span>
                      </div>
                      <span className="cr-label-xs text-[9px] font-mono text-emerald-600 w-10 text-right">{buyTicks}t</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="cr-label-xs text-[9px] font-black font-mono text-red-400 w-6 xl:w-8">SEL</span>
                      <div className="cr-sellbar-track flex-1 h-4 xl:h-6 bg-zinc-900 rounded border border-zinc-800 overflow-hidden relative">
                        <div
                          className="h-full rounded anim-delta-fill transition-all duration-500"
                          style={{
                            width: `${sellPct}%`,
                            background: momentum === "BEAR"
                              ? `linear-gradient(90deg, #7f1d1d, #f87171)`
                              : `linear-gradient(90deg, #450a0a, #ef4444)`,
                            boxShadow: blink && momentum === "BEAR" ? "0 0 8px rgba(248,113,113,0.5)" : undefined,
                          }}
                        />
                        <span className="absolute inset-0 flex items-center px-2 text-[9px] xl:text-[11px] font-black font-mono text-red-200">{sellPct}%</span>
                      </div>
                      <span className="cr-label-xs text-[9px] font-mono text-red-600 w-10 text-right">{sellTicks}t</span>
                    </div>
                  </div>

                  {/* Mini bar chart */}
                  <div className="border-t border-zinc-800/60 pt-1 space-y-0.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] text-zinc-600 font-mono uppercase tracking-widest">TICK FLOW CHART (8 bars)</span>
                      <span className={cn("text-[9px] font-black font-mono", momentumCol)}>{momentumStr}</span>
                    </div>
                    <div className="cr-minichart flex items-end gap-0.5 h-8 xl:h-12">
                      {barDeltas.map((delta, i) => {
                        const isUp     = delta >= 0;
                        const heightPct = Math.max(Math.abs(delta) / maxBarAbs * 100, 8);
                        const isLatest  = i === BARS - 1;
                        return (
                          <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                            <div
                              className={cn("w-full rounded-sm transition-all duration-300",
                                isUp
                                  ? (isLatest && blink ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]" : "bg-emerald-600")
                                  : (isLatest && blink ? "bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.7)]" : "bg-red-600")
                              )}
                              style={{ height: `${heightPct}%` }}
                            />
                          </div>
                        );
                      })}
                    </div>
                    {/* Block char sparkline */}
                    <div className="flex items-center gap-1 pt-0.5">
                      <span className="text-[9px] text-zinc-700 font-mono">M1≈</span>
                      <span className="text-[12px] font-mono leading-none tracking-widest">
                        {barDeltas.map((delta, i) => {
                          const isUp  = delta >= 0;
                          const lvl   = Math.min(Math.round(Math.abs(delta) / maxBarAbs * 7), 7);
                          const char  = BLOCKS[lvl];
                          const isLast = i === BARS - 1;
                          return (
                            <span key={i} className={cn(
                              isUp
                                ? (isLast && blink ? "text-emerald-300" : "text-emerald-600")
                                : (isLast && blink ? "text-red-300" : "text-red-600")
                            )}>{char}</span>
                          );
                        })}
                      </span>
                    </div>
                  </div>

                  {/* Summary row */}
                  <div className="border-t border-zinc-800/60 pt-1 flex items-center justify-between">
                    <div className="flex items-center gap-3 text-[9px] font-mono">
                      <span className="text-zinc-600">CUM.DELTA</span>
                      <span className={cn("font-black text-[11px]", cumDelta >= 0 ? "text-emerald-400" : "text-red-400")}>
                        {cumDelta >= 0 ? "+" : ""}{cumDelta.toFixed(3)}
                      </span>
                    </div>
                    <div className="text-[10px] font-black font-mono">
                      {momentum === "BULL" && (
                        <span className={cn("transition-all duration-100",
                          blinkFast
                            ? "text-emerald-300 drop-shadow-[0_0_8px_rgba(52,211,153,0.9)]"
                            : "text-emerald-600"
                        )}>▲ BUYER DOMINANT</span>
                      )}
                      {momentum === "BEAR" && (
                        <span className={cn("transition-all duration-100",
                          blinkFast
                            ? "text-red-300 drop-shadow-[0_0_8px_rgba(248,113,113,0.9)]"
                            : "text-red-600"
                        )}>▼ SELLER DOMINANT</span>
                      )}
                      {momentum === "NEUTRAL" && <span className="text-zinc-500">── BALANCED</span>}
                      {momentum === "SCANNING" && <span className="text-zinc-700 animate-pulse">○ COLLECTING...</span>}
                    </div>
                  </div>
                </>
              )}
            </div>
          </PanelBox>
        </div>

        {/* ─── RIGHT COLUMN: SNR.LADDER ─── */}
        <div>
          <PanelBox title={<PanelTitle label="SNR.LADDER" />} cls="border-zinc-800 sticky top-0">
            <div className="px-3 py-1.5 space-y-1.5">
              {(tp1Up || tp2Up || tp1Dn || tp2Dn) && (
                <div className="bg-zinc-900/60 rounded-lg border border-zinc-800 px-2 py-2 space-y-1">
                  <div className="text-[8px] font-black font-mono text-zinc-600 tracking-widest uppercase pb-0.5 border-b border-zinc-800">TP SUGGESTION</div>
                  {tp1Up && <div className="text-[10px] font-mono text-emerald-400">↑ TP1 {tp1Up}</div>}
                  {tp2Up && <div className="text-[10px] font-mono text-emerald-600/60">↑ TP2 {tp2Up}</div>}
                  {tp1Dn && <div className="text-[10px] font-mono text-red-400">↓ TP1 {tp1Dn}</div>}
                  {tp2Dn && <div className="text-[10px] font-mono text-red-600/60">↓ TP2 {tp2Dn}</div>}
                </div>
              )}

              {allLevels.length > 0 ? (
                <div className="space-y-0.5">
                  {aboveLevels.slice(0, 6).reverse().map(l => {
                    const dist = (l.price - cmpFloat).toFixed(1);
                    const close = parseFloat(dist) < 5;
                    return (
                      <div key={l.key} className={cn("flex items-center gap-1 px-1 py-0.5 rounded text-[10px] font-mono", close && "bg-emerald-950/20")}>
                        <ArrowUpIcon className="w-2.5 h-2.5 text-emerald-700 shrink-0" />
                        <span className={cn("w-11 shrink-0", close ? "text-emerald-500" : "text-zinc-500")}>{l.short}</span>
                        <span className="text-emerald-400 font-bold flex-1 text-right">{l.price.toFixed(2)}</span>
                        <span className="text-zinc-700 w-9 text-right">+{dist}</span>
                      </div>
                    );
                  })}

                  <div className={cn("flex items-center gap-1 px-1 py-1 rounded text-[10px] font-mono border",
                    livePrice ? "bg-amber-950/30 border-amber-800/40" : "bg-zinc-900 border-zinc-800"
                  )}>
                    <span className={cn("w-2.5 text-center", livePrice ? (blink ? "text-amber-300" : "text-amber-600") : "text-zinc-600")}>●</span>
                    <span className={cn("w-11", livePrice ? "text-amber-500" : "text-zinc-600")}>NOW</span>
                    <span className={cn("font-black flex-1 text-right", livePrice ? "text-amber-300" : "text-zinc-400")}>{displayPrice}</span>
                  </div>

                  {atLevel.map(l => (
                    <div key={l.key} className="flex items-center gap-1 px-1 py-0.5 rounded bg-yellow-950/30 text-[10px] font-mono">
                      <span className="text-yellow-500 w-2.5 text-center">⚡</span>
                      <span className="text-yellow-400 w-11">{l.short}</span>
                      <span className="text-yellow-300 font-bold flex-1 text-right">{l.price.toFixed(2)}</span>
                      <span className="text-yellow-800 w-9 text-right">at</span>
                    </div>
                  ))}

                  {belowLevels.slice(0, 6).map(l => {
                    const dist = (cmpFloat - l.price).toFixed(1);
                    const close = parseFloat(dist) < 5;
                    return (
                      <div key={l.key} className={cn("flex items-center gap-1 px-1 py-0.5 rounded text-[10px] font-mono", close && "bg-red-950/20")}>
                        <ArrowDownIcon className="w-2.5 h-2.5 text-red-700 shrink-0" />
                        <span className={cn("w-11 shrink-0", close ? "text-red-500" : "text-zinc-500")}>{l.short}</span>
                        <span className="text-red-400 font-bold flex-1 text-right">{l.price.toFixed(2)}</span>
                        <span className="text-zinc-700 w-9 text-right">-{dist}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-[10px] text-zinc-700 font-mono animate-pulse">[ AWAITING SNR SYNC ]</p>
                </div>
              )}

              {/* Manual round */}
              {(() => {
                const v = byName["ROUND"];
                if (!v) return null;
                return (
                  <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between">
                    <span className="text-[9px] text-zinc-700 font-mono">ROUND (manual)</span>
                    {editing === "ROUND" ? (
                      <div className="flex items-center gap-1">
                        <input autoFocus value={editVal} onChange={e => setEditVal(e.target.value)}
                          onKeyDown={e => { if (e.key === "Enter") save(v.variableName, v.label, editVal); if (e.key === "Escape") setEditing(null); }}
                          placeholder="3320.00"
                          className="w-20 bg-zinc-800 border border-zinc-600 text-white text-[10px] font-mono rounded px-1.5 py-0.5 focus:outline-none focus:border-amber-600 text-right"
                        />
                        <button onClick={() => save(v.variableName, v.label, editVal)} className="text-emerald-500"><CheckIcon className="w-3 h-3" /></button>
                        <button onClick={() => setEditing(null)} className="text-zinc-600"><XIcon className="w-3 h-3" /></button>
                      </div>
                    ) : (
                      <button onClick={() => { setEditing("ROUND"); setEditVal(v.value); }} className="flex items-center gap-1 group">
                        <span className={cn("text-[10px] font-mono", v.value ? "text-yellow-400" : "text-zinc-700")}>{v.value || "—"}</span>
                        <PencilIcon className="w-2.5 h-2.5 text-zinc-700 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                    )}
                  </div>
                );
              })()}
            </div>
          </PanelBox>
        </div>
      </div>

      <div className="flex items-center justify-between pt-0">
        <span className="text-[9px] text-zinc-800 font-mono">CDP :9222 · CMP Engine v6.3 · Daily Deploy · Chain Reaction v4.0 OVERLORD</span>
        <span className="text-[9px] font-black font-mono text-amber-900/60 tracking-widest">© DADANG WAHYUONO — PRIVATE &amp; CONFIDENTIAL</span>
        {lastSNRSync && <span className="text-[9px] text-zinc-800 font-mono">SNR: {timeAgo(lastSNRSync)}</span>}
      </div>
    </div>
  );
}
