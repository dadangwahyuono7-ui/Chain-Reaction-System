"use client";

/**
 * CursorGlow — cahaya radial lembut yang ngikutin kursor ke seluruh layar.
 * Duduk di antara background 3D dan konten (-z-5) → nyinari backdrop near cursor.
 */

import { useEffect, useRef } from "react";

export function CursorGlow({ color = "rgba(99,102,241,0.14)" }: { color?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const el = ref.current;
      if (!el) return;
      el.style.setProperty("--x", `${e.clientX}px`);
      el.style.setProperty("--y", `${e.clientY}px`);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  return (
    <div
      ref={ref}
      aria-hidden
      className="fixed inset-0 pointer-events-none"
      style={{
        zIndex: -5,
        background: `radial-gradient(460px circle at var(--x,50%) var(--y,50%), ${color}, transparent 72%)`,
        transition: "background .08s linear",
      }}
    />
  );
}
