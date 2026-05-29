"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { DEFAULT_MARKET_CONTEXT } from "@/lib/system-prompt";
import { cn } from "@/lib/utils";
import { DashboardPro } from "@/components/dashboard-pro";
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

const TF_ROWS = ["DAILY", "H4", "H1", "M30", "M15", "M5", "M1"];

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
    <div className={cn("rounded-xl border border-slate-800/70 bg-slate-900/40 overflow-hidden relative", cls)}>
      {/* Accent atas tipis (statis) — cuma saat panel ditandai aktif */}
      {scanV && <div className="absolute top-0 left-0 w-full h-[2px] bg-indigo-500/70 pointer-events-none" />}
      <div className="cr-panel-header px-3.5 py-2 border-b border-slate-800/60 flex items-center justify-between">
        {title}
        {extra}
      </div>
      {children}
    </div>
  );
}

function HexTag() { return null; }

function PanelTitle({ label, live = false }: { label: string; live?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {live && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0 anim-ambient-dot" />}
      <span className="text-[11px] font-semibold text-slate-300 tracking-wide uppercase">{label}</span>
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
    // REDESIGN: dipelanin biar kalem institusi (dulu 800ms) — gerakan ambient
    const t = setInterval(() => setBlink(p => !p), 1400);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    // REDESIGN: dulu 350ms (frantic). Dipelanin ke 700ms — tetap "hidup" tapi gak bikin capek.
    const t = setInterval(() => setBlinkFast(p => !p), 700);
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
  // DASHBOARD MODE — PRO (Clean Institutional, port 3003)
  // Visual baru total. Logika & data tetap dari atas (tidak diubah).
  // ══════════════════════════════════════════════════════════════════════════════
  return (
    <>
      <style>{ANIM_CSS}</style>
      {alertToasts}
      <DashboardPro
        displayPrice={displayPrice}
        livePrice={livePrice}
        priceFlash={priceFlash}
        spread={spread}
        sess={sess}
        tfData={tfData}
        h4Dir={h4Dir}
        hasTFData={hasTFData}
        autoGrade={autoGrade}
        buyPct={buyPct}
        sellPct={sellPct}
        cumDelta={cumDelta}
        momentum={momentum}
        momentumStr={momentumStr}
        barDeltas={barDeltas}
        maxBarAbs={maxBarAbs}
        divergence={divergence}
        nTicks={N_TICKS}
        aboveLevels={aboveLevels}
        belowLevels={belowLevels}
        atLevel={atLevel}
        cmpFloat={cmpFloat}
        tp1Up={tp1Up}
        tp2Up={tp2Up}
        tp1Dn={tp1Dn}
        tp2Dn={tp2Dn}
        minutesUntilNews={minutesUntilNews}
        newsBlackout={newsBlackout}
        newsApproaching={newsApproaching}
        nextEventName={nextEventName}
        nextEventTimeWIB={nextEventTimeWIB}
        syncTV={syncTV}
        syncing={syncing}
        tvStatus={tvStatus}
        lastSync={lastSync}
        syncSNR={syncSNR}
        syncingSNR={syncingSNR}
        syncNews={syncNews}
        syncingNews={syncingNews}
        autoSync={autoSync}
        setAutoSync={setAutoSync}
        blink={blink}
        blinkFast={blinkFast}
      />
    </>
  );

}
