"use client";

/**
 * ThreeBg — ocean wireframe FULL-SCREEN di 2D canvas (BUKAN WebGL → selalu render, gak putih).
 * Grid penuh satu layar + swell ombak + ripple "batu jatuh ke air" ngikutin kursor.
 */

import { useRef, useEffect } from "react";

export function ThreeBg({ color = "99,102,241", bg = "#020617" }: { color?: string; bg?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const mouse = useRef({ x: -9999, y: -9999 });

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let raf = 0;
    const COLS = 34, ROWS = 24;

    const onMove = (e: MouseEvent) => { mouse.current = { x: e.clientX, y: e.clientY }; };
    window.addEventListener("mousemove", onMove);

    const draw = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) { canvas.width = w * dpr; canvas.height = h * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const t = performance.now() / 1000;
      const mxP = mouse.current.x, myP = mouse.current.y;

      const pts: { x: number; y: number; a: number }[][] = [];
      for (let r = 0; r < ROWS; r++) {
        const dT = r / (ROWS - 1);                 // 0 = atas (jauh), 1 = bawah (dekat)
        const baseY = dT * h;
        const spread = 0.55 + dT * 0.6;            // perspektif: sempit di atas, lebar di bawah
        const ampA = 7 + dT * 22;                  // swell makin besar ke depan
        const row: { x: number; y: number; a: number }[] = [];
        for (let c = 0; c < COLS; c++) {
          const fx = c / (COLS - 1);
          const sx = w / 2 + (fx - 0.5) * w * spread;
          // swell ombak (multi-arah)
          let wave =
            Math.sin(fx * 6 + t * 1.1) * 0.5 +
            Math.sin(dT * 5 - t * 0.8) * 0.5 +
            Math.sin((fx * 3 + dT * 4) + t * 0.6) * 0.4;
          let sy = baseY - wave * ampA;
          // ripple kursor (ombak melingkar dari titik mouse)
          const dx = sx - mxP, dy = sy - myP;
          const dist = Math.sqrt(dx * dx + dy * dy);
          sy -= Math.sin(dist * 0.03 - t * 5) * Math.exp(-dist / 280) * 30;
          row.push({ x: sx, y: sy, a: 0.13 + dT * 0.45 });
        }
        pts.push(row);
      }

      ctx.lineWidth = 1.2;
      ctx.shadowColor = `rgba(${color},0.85)`;
      ctx.shadowBlur = 5;
      for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
          const p = pts[r][c];
          if (c < COLS - 1) {
            const q = pts[r][c + 1];
            ctx.strokeStyle = `rgba(${color},${Math.min(p.a, q.a).toFixed(3)})`;
            ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke();
          }
          if (r < ROWS - 1) {
            const q = pts[r + 1][c];
            ctx.strokeStyle = `rgba(${color},${Math.min(p.a, q.a).toFixed(3)})`;
            ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke();
          }
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("mousemove", onMove); };
  }, [color]);

  return (
    <div className="fixed inset-0 -z-10 pointer-events-none" style={{ backgroundColor: bg }}>
      <canvas ref={ref} className="w-full h-full block" />
    </div>
  );
}
