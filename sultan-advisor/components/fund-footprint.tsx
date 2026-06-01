"use client";

/**
 * FundFootprint — panel "Jejak Fund": Volume Profile (HVN/LVN/POC),
 * Liquidity zones (stop pool), Basis, DXY/Yield macro gate.
 * Data dari /api/fund-data (Yahoo Finance). Konteks akumulasi/distribusi buat AI & mata.
 */

import { useEffect, useState } from "react";

type FundData = {
  ok: boolean;
  volumeProfile: { poc: number; valueAreaHigh: number; valueAreaLow: number; hvn: number[]; lvn: number[]; hi: number; lo: number } | null;
  liquidity: { liquidityAbove: { price: number; touches: number } | null; liquidityBelow: { price: number; touches: number } | null };
  basis: { gc: number | null; spot: number | null; basis: number | null };
  macro: { dxy: number | null; dxyTrend: string; us10y: number | null; tnxTrend: string; macroBias: string };
  summary: string;
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-slate-800/40 last:border-0">
      <span className="text-[11px] text-slate-500 tracking-wide">{label}</span>
      <span className="text-[12px] font-mono text-slate-200">{children}</span>
    </div>
  );
}

export function FundFootprint() {
  const [d, setD] = useState<FundData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    try {
      const r = await fetch("/api/fund-data");
      const j = await r.json();
      if (j.ok) { setD(j); setErr(null); } else setErr(j.error || "gagal");
    } catch (e) { setErr(e instanceof Error ? e.message : "error"); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 120000); // refresh 2 menit (data delay, gak perlu sering)
    return () => clearInterval(t);
  }, []);

  const biasColor = d?.macro.macroBias?.includes("BEARISH") ? "text-rose-400"
    : d?.macro.macroBias?.includes("BULLISH") ? "text-emerald-400" : "text-slate-400";

  return (
    <div className="dp-card dp-glass rounded-2xl border border-slate-700/30 overflow-hidden">
      <div className="flex items-center justify-between px-5 pt-4 pb-2.5">
        <div className="flex items-center gap-2.5 text-slate-400">
          <span className="text-[15px]">🏦</span>
          <span className="dp-label font-bold uppercase tracking-[0.15em]">Jejak Fund · Institutional</span>
        </div>
        <button onClick={load} className="text-[10px] text-slate-600 hover:text-slate-400">↻ refresh</button>
      </div>

      <div className="px-5 pb-4">
        {loading && <div className="text-[12px] text-slate-500 py-3">Narik data Yahoo…</div>}
        {err && <div className="text-[12px] text-rose-400 py-3">⚠ {err}</div>}
        {d && (
          <div className="grid md:grid-cols-2 gap-x-6">
            {/* Volume Profile */}
            <div>
              <div className="text-[10px] text-indigo-300/80 font-bold tracking-widest mb-1">VOLUME PROFILE (GC=F)</div>
              {d.volumeProfile ? (
                <>
                  <Row label="POC (magnet)"><span className="text-amber-300">{d.volumeProfile.poc}</span></Row>
                  <Row label="Value Area">{d.volumeProfile.valueAreaLow} – {d.volumeProfile.valueAreaHigh}</Row>
                  <Row label="HVN (akumulasi)"><span className="text-emerald-300">{d.volumeProfile.hvn.join(" · ")}</span></Row>
                  <Row label="LVN (rejection)"><span className="text-rose-300/80">{d.volumeProfile.lvn.join(" · ")}</span></Row>
                </>
              ) : <div className="text-[11px] text-slate-600 py-2">no data</div>}
            </div>

            {/* Liquidity + Macro */}
            <div>
              <div className="text-[10px] text-indigo-300/80 font-bold tracking-widest mb-1 mt-3 md:mt-0">LIQUIDITY & MAKRO</div>
              <Row label="Liq ATAS (stop pool)">
                {d.liquidity.liquidityAbove ? <span className="text-rose-300">{d.liquidity.liquidityAbove.price} ({d.liquidity.liquidityAbove.touches}×)</span> : "—"}
              </Row>
              <Row label="Liq BAWAH (stop pool)">
                {d.liquidity.liquidityBelow ? <span className="text-emerald-300">{d.liquidity.liquidityBelow.price} ({d.liquidity.liquidityBelow.touches}×)</span> : "—"}
              </Row>
              <Row label="Basis COMEX-Spot">
                {d.basis.basis != null ? <span className={d.basis.basis >= 0 ? "text-emerald-300" : "text-rose-300"}>{d.basis.basis >= 0 ? "+" : ""}{d.basis.basis}</span> : "—"}
              </Row>
              <Row label="DXY">{d.macro.dxy ?? "—"} <span className="text-slate-500">({d.macro.dxyTrend})</span></Row>
              <Row label="US10Y">{d.macro.us10y ?? "—"}% <span className="text-slate-500">({d.macro.tnxTrend})</span></Row>
              <Row label="Macro Bias"><span className={biasColor + " font-bold"}>{d.macro.macroBias}</span></Row>
            </div>
          </div>
        )}
        <p className="text-[10px] text-slate-600 mt-3 leading-relaxed">
          Proxy akumulasi fund dari volume & price action (Yahoo, delay). Bukan order book real-time — tapi area HVN/POC & stop pool = tempat smart money sering main.
        </p>
      </div>
    </div>
  );
}
