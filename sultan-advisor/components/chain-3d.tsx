"use client";

/**
 * Chain3D — siklus CMP → VR → CF sebagai GARIS DETAK JANTUNG (ECG) full-width.
 * Garis scroll kiri→kanan, 3 node glow (CMP/VR/CF) nyala per fase.
 * Detak makin KENCENG seiring fase: F1 pelan → F2 sedang → F3/CF cepat.
 * 2D canvas (ringan, look monitor jantung), glow neon.
 */

import { useRef, useEffect, useState } from "react";

function phaseColor(dir: string): { hex: string; rgb: string } {
  const d = (dir || "").toUpperCase();
  if (d.includes("BULL") || d === "BUY") return { hex: "#34d399", rgb: "52,211,153" };
  if (d.includes("BEAR") || d === "SELL") return { hex: "#f87171", rgb: "248,113,113" };
  return { hex: "#818cf8", rgb: "129,140,248" };
}

// bentuk gelombang ECG dalam 1 siklus detak (t = 0..1)
function ecg(t: number): number {
  // P wave
  if (t > 0.12 && t < 0.20) return Math.sin((t - 0.12) / 0.08 * Math.PI) * 0.18;
  // QRS complex (dip - spike tajam - dip)
  if (t > 0.30 && t < 0.34) return -(t - 0.30) / 0.04 * 0.22;          // Q dip
  if (t > 0.34 && t < 0.38) return -0.22 + (t - 0.34) / 0.04 * 1.22;  // R naik tajam
  if (t > 0.38 && t < 0.42) return 1.0 - (t - 0.38) / 0.04 * 1.30;    // S turun
  if (t > 0.42 && t < 0.46) return -0.30 + (t - 0.42) / 0.04 * 0.30;  // balik baseline
  // T wave
  if (t > 0.55 && t < 0.70) return Math.sin((t - 0.55) / 0.15 * Math.PI) * 0.30;
  return 0;
}

function HeartbeatCanvas({ phase, color }: { phase: number; color: { hex: string; rgb: string } }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    let offset = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    // detak makin kenceng per fase
    const speed = phase >= 3 ? 1.5 : phase === 2 ? 0.85 : phase === 1 ? 0.45 : 0.2;
    const beats = phase >= 3 ? 4.2 : phase === 2 ? 3.0 : 2.2; // jumlah detak melintang layar

    const nodes = [
      { x: 0.16, on: phase >= 1, label: "CMP" },
      { x: 0.5, on: phase >= 2, label: "VR" },
      { x: 0.84, on: phase >= 3, label: "CF" },
    ];

    const draw = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr; canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const midY = h * 0.52;
      const amp = h * 0.30;
      offset += speed * 0.006;

      // garis dasar redup
      ctx.strokeStyle = `rgba(${color.rgb},0.12)`;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(0, midY); ctx.lineTo(w, midY); ctx.stroke();

      // ECG line dengan glow
      ctx.shadowColor = color.hex;
      ctx.shadowBlur = 12;
      ctx.strokeStyle = color.hex;
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let px = 0; px <= w; px += 2) {
        const t = ((px / w) * beats - offset) % 1;
        const tt = t < 0 ? t + 1 : t;
        const y = midY - ecg(tt) * amp;
        if (px === 0) ctx.moveTo(px, y); else ctx.lineTo(px, y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // node glow CMP/VR/CF
      const beatPulse = 1 + Math.sin(offset * Math.PI * 2 * beats) * 0.12;
      nodes.forEach(n => {
        const cx = n.x * w;
        const r = (n.on ? 9 : 5) * (n.on ? beatPulse : 1);
        // halo
        const grad = ctx.createRadialGradient(cx, midY, 0, cx, midY, r * 2.6);
        grad.addColorStop(0, `rgba(${color.rgb},${n.on ? 0.5 : 0.12})`);
        grad.addColorStop(1, "transparent");
        ctx.fillStyle = grad;
        ctx.beginPath(); ctx.arc(cx, midY, r * 2.6, 0, Math.PI * 2); ctx.fill();
        // inti
        ctx.fillStyle = n.on ? color.hex : `rgba(${color.rgb},0.3)`;
        ctx.beginPath(); ctx.arc(cx, midY, r, 0, Math.PI * 2); ctx.fill();
      });

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [phase, color]);

  return <canvas ref={ref} className="w-full h-[110px] block" />;
}

export function Chain3D({ tf = "H4", cmp = "", vr = "", cf = "" }: { tf?: string; cmp?: string; vr?: string; cf?: string }) {
  const isVR = vr === "YA", isCF = cf === "YA", hasCmp = !!cmp;
  const phase = !hasCmp ? 0 : isVR && isCF ? 3 : isVR ? 2 : 1;
  const color = phaseColor(cmp);
  const faseLabel = phase === 3 ? "F3 ⚡ PRIME" : phase === 2 ? "F2 — tunggu CF" : phase === 1 ? "F1 — tunggu VR" : "no CMP";
  const dirLabel = !cmp ? "—" : color.hex === "#34d399" ? "BUY ▲" : color.hex === "#f87171" ? "SELL ▼" : cmp;
  const bpm = phase >= 3 ? "FAST" : phase === 2 ? "MED" : phase === 1 ? "SLOW" : "—";

  return (
    <div className="relative w-full">
      <div className="flex items-center justify-between px-1 mb-0.5">
        <span className="text-[11px] font-mono tracking-widest text-slate-400">
          CHAIN PULSE · <span className="text-slate-200">{tf}</span>
        </span>
        <span className="text-[11px] font-mono font-bold" style={{ color: color.hex }}>
          {dirLabel} · {faseLabel} · ♥ {bpm}
        </span>
      </div>

      <HeartbeatCanvas phase={phase} color={color} />

      <div className="flex justify-between px-[14%] -mt-2">
        {[
          { k: "CMP", on: phase >= 1 },
          { k: "VR", on: phase >= 2 },
          { k: "CF", on: phase >= 3 },
        ].map((n) => (
          <span key={n.k} className="text-[10px] font-mono font-bold tracking-wider"
            style={{ color: n.on ? color.hex : "#475569" }}>{n.k}</span>
        ))}
      </div>
    </div>
  );
}

/** Versi live — fetch /api/context untuk TF tertentu (default H4). */
export function Chain3DLive({ tf = "H4" }: { tf?: string }) {
  const [s, setS] = useState({ cmp: "", vr: "", cf: "" });
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fetch("/api/context");
        if (!r.ok) return;
        const rows: Array<{ variableName: string; value: string }> = await r.json();
        const m: Record<string, string> = {};
        for (const row of rows) m[row.variableName] = row.value;
        if (alive) setS({ cmp: m[`${tf}_CMP`] || "", vr: m[`${tf}_VR`] || "", cf: m[`${tf}_CF`] || "" });
      } catch { /* ignore */ }
    };
    load();
    const id = setInterval(load, 6000);
    return () => { alive = false; clearInterval(id); };
  }, [tf]);
  return <Chain3D tf={tf} cmp={s.cmp} vr={s.vr} cf={s.cf} />;
}
