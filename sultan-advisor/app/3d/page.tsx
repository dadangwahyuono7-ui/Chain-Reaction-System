"use client";

import dynamic from "next/dynamic";

const ThreeBg = dynamic(() => import("@/components/three-bg").then((m) => m.ThreeBg), { ssr: false });
const Chain3D = dynamic(() => import("@/components/chain-3d").then((m) => m.Chain3D), { ssr: false });
import { TiltCard } from "@/components/tilt-card";
import { CursorGlow } from "@/components/cursor-glow";

export default function Demo3D() {
  const cases = [
    { tf: "M15", cmp: "BULLISH", vr: "", cf: "", note: "F1 — baru CMP, tunggu VR" },
    { tf: "M30", cmp: "BEARISH", vr: "YA", cf: "", note: "F2 — VR udah, tunggu CF" },
    { tf: "H4", cmp: "BULLISH", vr: "YA", cf: "YA", note: "F3 ⚡ PRIME — siklus lengkap" },
  ];
  return (
    <div className="min-h-screen bg-transparent text-slate-100 p-8">
      <ThreeBg />
      <CursorGlow />
      <h1 className="text-center text-lg font-mono tracking-widest text-slate-300 mb-1">
        CHAIN REACTION · 3D PREVIEW
      </h1>
      <p className="text-center text-[12px] text-slate-500 mb-8">CMP → VR → CF dalam 3 fase</p>
      <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
        {cases.map((c) => (
          <TiltCard key={c.tf} className="p-4">
            <Chain3D tf={c.tf} cmp={c.cmp} vr={c.vr} cf={c.cf} />
            <p className="text-center text-[11px] text-slate-400 mt-2">{c.note}</p>
          </TiltCard>
        ))}
      </div>
    </div>
  );
}
