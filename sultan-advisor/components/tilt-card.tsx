"use client";

/**
 * TiltCard — glassmorphism card dengan efek tilt 3D mengikuti kursor.
 * Pure CSS transform (GPU-accelerated), nol library. Bungkus panel apa pun.
 */

import { useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function TiltCard({
  children,
  className,
  intensity = 7,
  glow = "rgba(99,102,241,0.18)",
}: {
  children: React.ReactNode;
  className?: string;
  intensity?: number;
  glow?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState("");
  const [active, setActive] = useState(false);

  function onMove(e: React.MouseEvent) {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    setTransform(
      `perspective(900px) rotateX(${-py * intensity}deg) rotateY(${px * intensity}deg) scale(1.01)`
    );
  }

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseEnter={() => setActive(true)}
      onMouseLeave={() => {
        setActive(false);
        setTransform("");
      }}
      style={{
        transform,
        transition: active ? "none" : "transform .45s cubic-bezier(.2,.8,.2,1)",
        boxShadow: active
          ? `0 18px 50px ${glow}, 0 0 0 1px rgba(99,102,241,0.35)`
          : `0 6px 24px rgba(0,0,0,0.35)`,
      }}
      className={cn(
        "rounded-2xl border border-indigo-500/20 bg-slate-900/45 backdrop-blur-xl will-change-transform",
        className
      )}
    >
      {children}
    </div>
  );
}
