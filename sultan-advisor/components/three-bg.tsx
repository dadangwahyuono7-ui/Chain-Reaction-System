"use client";

/**
 * ThreeBg — background grid synthwave CSS MURNI (bukan WebGL).
 * Alasan: WebGL bisa render putih / gagal di GPU yang sibuk (RX580 + llama.cpp).
 * CSS-only = dark dijamin, GPU ringan, gak pernah putih. Tetap ada kesan 3D + gerak.
 */

export function ThreeBg({ color = "rgba(99,102,241,0.16)", bg = "#020617" }: { color?: string; bg?: string }) {
  return (
    <div className="fixed inset-0 -z-10 pointer-events-none overflow-hidden" style={{ backgroundColor: bg }}>
      <style>{`
        @keyframes cr-grid-move { from { background-position: 0 0, 0 0; } to { background-position: 0 44px, 44px 0; } }
      `}</style>
      {/* lantai grid perspektif (synthwave) */}
      <div
        className="absolute left-1/2 bottom-0 h-[65%] w-[260%] -translate-x-1/2"
        style={{
          backgroundImage: `linear-gradient(${color} 1px, transparent 1px), linear-gradient(90deg, ${color} 1px, transparent 1px)`,
          backgroundSize: "44px 44px",
          transform: "perspective(340px) rotateX(62deg)",
          transformOrigin: "bottom center",
          animation: "cr-grid-move 7s linear infinite",
          WebkitMaskImage: "linear-gradient(transparent 0%, #000 55%)",
          maskImage: "linear-gradient(transparent 0%, #000 55%)",
        }}
      />
      {/* vignette halus biar konten tetap fokus */}
      <div
        className="absolute inset-0"
        style={{ background: "radial-gradient(120% 80% at 50% 0%, transparent 50%, rgba(2,6,23,0.6) 100%)" }}
      />
    </div>
  );
}
