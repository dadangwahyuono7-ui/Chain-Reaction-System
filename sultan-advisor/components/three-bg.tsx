"use client";

/**
 * ThreeBg — wireframe terrain synthwave di 2D CANVAS (BUKAN WebGL).
 * WebGL gagal/blank di GPU sibuk (RX580 + llama.cpp) → ini software render, SELALU muncul.
 * Floor grid perspektif yang bergelombang + reaktif mouse (ripple). Gak pernah putih.
 */

import { useRef, useEffect } from "react";

export function ThreeBg({ color = "99,102,241", bg = "#020617" }: { color?: string; bg?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const mouse = useRef({ x: 0.5, y: 0.5 });

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let raf = 0;
    const COLS = 30, ROWS = 16;

    const onMove = (e: MouseEvent) => {
      mouse.current = { x: e.clientX / window.innerWidth, y: e.clientY / window.innerHeight };
    };
    window.addEventListener("mousemove", onMove);

    const draw = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) { canvas.width = w * dpr; canvas.height = h * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const t = performance.now() / 1000;
      const horizon = h * 0.40;
      const mxCol = mouse.current.x;          // 0..1 lebar
      const myNear = 1 - mouse.current.y;     // 0 jauh .. 1 dekat

      const pts: { x: number; y: number; a: number }[][] = [];
      for (let r = 0; r < ROWS; r++) {
        const dT = r / (ROWS - 1);            // 0 = jauh (horizon), 1 = dekat (bawah)
        const persp = Math.pow(dT, 1.7);
        const rowY = horizon + persp * (h - horizon);
        const halfW = w * 0.04 + persp * (w * 0.72);
        const amp = 26 * persp + 6;
        const row: { x: number; y: number; a: number }[] = [];
        for (let c = 0; c < COLS; c++) {
          const fx = c / (COLS - 1);          // 0..1
          const sx = w / 2 + (fx - 0.5) * 2 * halfW;
          let wave = Math.sin(fx * 8 + t * 1.5 + dT * 4) * 0.5 + Math.cos(dT * 6 - t) * 0.5;
          const dx = fx - mxCol, dy = dT - myNear;
          wave += Math.exp(-(dx * dx * 9 + dy * dy * 9)) * Math.sin(t * 5) * 1.7;
          const sy = rowY - wave * amp;
          const a = 0.22 + dT * 0.55;
          row.push({ x: sx, y: sy, a });
        }
        pts.push(row);
      }

      ctx.lineWidth = 1.3;
      ctx.shadowColor = `rgba(${color},0.9)`;
      ctx.shadowBlur = 6;
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
