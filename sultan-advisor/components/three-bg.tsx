"use client";

/**
 * ThreeBg — background synthwave CSS MURNI (no WebGL → gak pernah putih, GPU ringan).
 * Grid lantai perspektif yang scroll + horizon glow + sun. Kesan 3D tanpa risiko WebGL.
 */

export function ThreeBg({
  grid = "rgba(99,102,241,0.28)",
  glow = "rgba(99,102,241,0.5)",
  bg = "#020617",
}: { grid?: string; glow?: string; bg?: string }) {
  return (
    <div className="fixed inset-0 -z-10 pointer-events-none overflow-hidden" style={{ backgroundColor: bg }}>
      <style>{`
        @keyframes cr-grid-move { from { background-position: 0 0, 0 0; } to { background-position: 0 50px, 50px 0; } }
        @keyframes cr-glow-pulse { 0%,100% { opacity:.55; } 50% { opacity:.9; } }
      `}</style>

      {/* sun / horizon glow */}
      <div
        className="absolute left-1/2 -translate-x-1/2"
        style={{
          top: "33%", width: "70%", height: "42%",
          background: `radial-gradient(ellipse at center, ${glow} 0%, transparent 65%)`,
          filter: "blur(40px)",
          animation: "cr-glow-pulse 5s ease-in-out infinite",
        }}
      />
      {/* garis horizon tajam */}
      <div
        className="absolute left-0 right-0"
        style={{ top: "38%", height: "2px", background: `linear-gradient(90deg, transparent, ${glow}, transparent)` }}
      />

      {/* lantai grid perspektif (synthwave) */}
      <div
        className="absolute left-1/2 bottom-0 h-[62%] w-[300%] -translate-x-1/2"
        style={{
          backgroundImage: `linear-gradient(${grid} 1.5px, transparent 1.5px), linear-gradient(90deg, ${grid} 1.5px, transparent 1.5px)`,
          backgroundSize: "50px 50px",
          transform: "perspective(360px) rotateX(64deg)",
          transformOrigin: "bottom center",
          animation: "cr-grid-move 6s linear infinite",
          WebkitMaskImage: "linear-gradient(transparent 0%, #000 45%)",
          maskImage: "linear-gradient(transparent 0%, #000 45%)",
        }}
      />

      {/* vignette atas biar konten fokus */}
      <div
        className="absolute inset-0"
        style={{ background: "radial-gradient(130% 90% at 50% 8%, transparent 42%, rgba(2,6,23,0.72) 100%)" }}
      />
    </div>
  );
}
