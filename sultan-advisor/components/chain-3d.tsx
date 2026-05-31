"use client";

/**
 * Chain3D — visualisasi 3D siklus CMP → VR → CF.
 * 3 orb bercahaya di ruang 3D + pulsa energi yang ngalir antar node,
 * nyala sesuai fase: F1 (CMP only) → F2 (+VR) → F3 PRIME (+CF, full flow).
 * GPU-light: basic material (no lights), <1K verts.
 */

import { Canvas, useFrame } from "@react-three/fiber";
import { useRef, useState, useEffect } from "react";
import * as THREE from "three";

const NODE_X = [-2.4, 0, 2.4] as const;

function Orb({ x, color, active }: { x: number; color: string; active: boolean }) {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.getElapsedTime();
    ref.current.scale.setScalar(active ? 1 + Math.sin(t * 3 + x) * 0.07 : 0.65);
    ref.current.position.y = Math.sin(t * 1.4 + x) * 0.13;
  });
  return (
    <group ref={ref} position={[x, 0, 0]}>
      <mesh>
        <sphereGeometry args={[0.42, 32, 32]} />
        <meshBasicMaterial color={color} transparent opacity={active ? 1 : 0.22} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.66, 24, 24]} />
        <meshBasicMaterial color={color} transparent opacity={active ? 0.16 : 0.04} />
      </mesh>
    </group>
  );
}

function Link({ from, to, color, lit }: { from: number; to: number; color: string; lit: boolean }) {
  const len = Math.abs(to - from);
  const mid = (from + to) / 2;
  return (
    <mesh position={[mid, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
      <cylinderGeometry args={[0.03, 0.03, len, 12]} />
      <meshBasicMaterial color={color} transparent opacity={lit ? 0.55 : 0.1} />
    </mesh>
  );
}

function Pulse({ phase, color }: { phase: number; color: string }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.getElapsedTime();
    const p = (t % 2.4) / 2.4;
    let x: number;
    if (phase >= 3) x = THREE.MathUtils.lerp(NODE_X[0], NODE_X[2], p);
    else if (phase === 2) x = THREE.MathUtils.lerp(NODE_X[0], NODE_X[1], p);
    else x = NODE_X[0] + Math.sin(t * 3) * 0.28;
    ref.current.position.x = x;
    ref.current.position.y = Math.sin(t * 1.4) * 0.13;
    ref.current.visible = phase >= 1;
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.14, 16, 16]} />
      <meshBasicMaterial color="#ffffff" />
    </mesh>
  );
}

function Scene({ phase, color }: { phase: number; color: string }) {
  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (group.current) group.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.3) * 0.28;
  });
  return (
    <group ref={group}>
      <Link from={NODE_X[0]} to={NODE_X[1]} color={color} lit={phase >= 2} />
      <Link from={NODE_X[1]} to={NODE_X[2]} color={color} lit={phase >= 3} />
      <Orb x={NODE_X[0]} color={color} active={phase >= 1} />
      <Orb x={NODE_X[1]} color={color} active={phase >= 2} />
      <Orb x={NODE_X[2]} color={color} active={phase >= 3} />
      <Pulse phase={phase} color={color} />
    </group>
  );
}

function phaseColor(dir: string): string {
  const d = dir.toUpperCase();
  if (d.includes("BULL") || d === "BUY") return "#34d399"; // emerald
  if (d.includes("BEAR") || d === "SELL") return "#f87171"; // red
  return "#818cf8"; // indigo
}

export function Chain3D({
  tf = "H4",
  cmp = "",
  vr = "",
  cf = "",
}: {
  tf?: string;
  cmp?: string;
  vr?: string;
  cf?: string;
}) {
  const hasCmp = !!cmp;
  const isVR = vr === "YA";
  const isCF = cf === "YA";
  const phase = !hasCmp ? 0 : isVR && isCF ? 3 : isVR ? 2 : 1;
  const color = phaseColor(cmp);
  const faseLabel = phase === 3 ? "F3 ⚡ PRIME" : phase === 2 ? "F2 — tunggu CF" : phase === 1 ? "F1 — tunggu VR" : "no CMP";
  const dirLabel = cmp ? (phaseColor(cmp) === "#34d399" ? "BUY ▲" : phaseColor(cmp) === "#f87171" ? "SELL ▼" : cmp) : "—";

  return (
    <div className="relative w-full">
      <div className="flex items-center justify-between px-1 mb-1">
        <span className="text-[11px] font-mono tracking-widest text-slate-400">
          CHAIN 3D · <span className="text-slate-200">{tf}</span>
        </span>
        <span className="text-[11px] font-mono font-bold" style={{ color }}>
          {dirLabel} · {faseLabel}
        </span>
      </div>

      <div className="h-[180px] w-full">
        <Canvas camera={{ position: [0, 0.5, 6.2], fov: 55 }} gl={{ antialias: true, alpha: true }} dpr={[1, 1.5]}>
          <Scene phase={phase} color={color} />
        </Canvas>
      </div>

      {/* Label node di bawah canvas */}
      <div className="flex justify-between px-6 -mt-3">
        {[
          { k: "CMP", on: phase >= 1 },
          { k: "VR", on: phase >= 2 },
          { k: "CF", on: phase >= 3 },
        ].map((n) => (
          <span
            key={n.k}
            className="text-[10px] font-mono font-bold tracking-wider transition-colors"
            style={{ color: n.on ? color : "#475569" }}
          >
            {n.k}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Versi live — fetch /api/context, tampilkan chain 3D untuk TF tertentu (default H4). */
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
