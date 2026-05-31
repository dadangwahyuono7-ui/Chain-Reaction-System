"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";

type ModelDef = {
  id: string; label: string; desc: string;
  size: string; stars: number; bat: string; fast: boolean;
};

export function LocalModelSwitcher() {
  const [models,   setModels]   = useState<ModelDef[]>([]);
  const [running,  setRunning]  = useState(false);
  const [current,  setCurrent]  = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [switching, setSwitching] = useState<string | null>(null);
  const [msg,      setMsg]      = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch("/api/local-model");
      const j = await r.json();
      setRunning(j.running);
      setCurrent(j.model);
      if (j.models) setModels(j.models);
    } catch { setRunning(false); }
  }, []);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 10_000);
    return () => clearInterval(t);
  }, [fetchStatus]);

  async function switchModel(id: string) {
    setSwitching(id);
    setLoading(true);
    setMsg(null);
    try {
      const r = await fetch("/api/local-model", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modelId: id }),
      });
      const j = await r.json();
      setMsg(j.message || j.error || "Done");
      await fetchStatus();
    } catch {
      setMsg("Gagal switch model");
    } finally {
      setLoading(false);
      setSwitching(null);
    }
  }

  return (
    <div className="space-y-3">
      {/* Status bar */}
      <div className="flex items-center gap-2 px-1">
        <span className={cn(
          "w-2 h-2 rounded-full shrink-0",
          running ? "bg-emerald-400 animate-pulse" : "bg-zinc-600"
        )} />
        <span className="text-[12px] font-mono text-zinc-400">
          {running ? `llama.cpp RUNNING${current && current !== "unknown" ? ` · ${current}` : ""}` : "llama.cpp OFFLINE"}
        </span>
        <button onClick={fetchStatus} className="ml-auto text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors">
          ↻ refresh
        </button>
      </div>

      {/* Model cards */}
      <div className="space-y-2">
        {models.map(m => {
          const isActive   = running && current?.toLowerCase().includes(m.id.split("-")[0]);
          const isSwitching = switching === m.id;

          return (
            <div key={m.id} className={cn(
              "rounded-xl border px-4 py-3 transition-all",
              isActive
                ? "bg-emerald-500/8 border-emerald-500/30"
                : "bg-slate-900/40 border-slate-700/40 hover:border-slate-600/60"
            )}>
              <div className="flex items-center justify-between gap-3">
                {/* Info */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={cn(
                      "text-[13px] font-bold",
                      isActive ? "text-emerald-300" : "text-slate-200"
                    )}>{m.label}</span>
                    <span className="text-[11px] text-amber-400/80 font-mono">{m.size}</span>
                    <span className="text-[11px] text-amber-400">{"★".repeat(m.stars)}</span>
                    {isActive && (
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        AKTIF
                      </span>
                    )}
                  </div>
                  <div className="text-[12px] text-slate-500 mt-0.5">{m.desc}</div>
                </div>

                {/* Button */}
                <button
                  onClick={() => switchModel(m.id)}
                  disabled={loading || isActive}
                  className={cn(
                    "shrink-0 px-3 py-1.5 rounded-lg text-[12px] font-bold border transition-all",
                    isActive
                      ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400 cursor-default"
                      : loading && switching === m.id
                        ? "bg-amber-500/10 border-amber-500/30 text-amber-400 cursor-wait animate-pulse"
                        : loading
                          ? "bg-slate-800/40 border-slate-700/40 text-slate-600 cursor-not-allowed"
                          : "bg-indigo-500/10 border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/20"
                  )}
                >
                  {isActive ? "✓ Running" : isSwitching ? "Loading..." : "Switch"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Message */}
      {msg && (
        <div className={cn(
          "text-[12px] px-3 py-2 rounded-lg border",
          msg.includes("siap") || msg.includes("Ready")
            ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
            : msg.includes("Gagal") || msg.includes("error")
              ? "bg-rose-500/10 border-rose-500/20 text-rose-300"
              : "bg-amber-500/10 border-amber-500/20 text-amber-300"
        )}>
          {msg}
        </div>
      )}

      {/* Tip */}
      <div className="text-[11px] text-slate-600 px-1 leading-relaxed">
        Switch model = stop llama.cpp lama → start model baru. Model besar butuh 1-3 menit loading.
      </div>
    </div>
  );
}
