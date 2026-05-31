"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

type Health = { qwen: boolean; tv: boolean; ts: number } | null;

function Dot({ ok, pulse }: { ok: boolean; pulse?: boolean }) {
  return (
    <span
      className={cn(
        "inline-block w-1.5 h-1.5 rounded-full",
        ok ? "bg-emerald-500" : "bg-red-600",
        ok && pulse && "animate-pulse"
      )}
    />
  );
}

export function StatusBar({ price }: { price?: string }) {
  const [health, setHealth] = useState<Health>(null);
  const [checking, setChecking] = useState(false);

  async function check() {
    setChecking(true);
    try {
      const r = await fetch("/api/health");
      if (r.ok) setHealth(await r.json());
    } catch { /* silent */ }
    setChecking(false);
  }

  useEffect(() => {
    check();
    const t = setInterval(check, 30_000);
    return () => clearInterval(t);
  }, []);

  if (!health && checking) return null; // first load, show nothing

  return (
    <div className="flex items-center gap-3">
      {/* Price */}
      {price && price !== "—" && (
        <span className="text-xs font-mono font-bold text-amber-400 tabular-nums">
          {price}
        </span>
      )}

      {/* Service dots */}
      {health && (
        <div className="flex items-center gap-2">
          <div
            className="flex items-center gap-1 cursor-pointer group"
            onClick={check}
            title={health.qwen ? "Qwen3-8B: online" : "Qwen3-8B: offline"}
          >
            <Dot ok={health.qwen} pulse={health.qwen} />
            <span className={cn("text-[10px]", health.qwen ? "text-zinc-600" : "text-red-600/80")}>
              AI
            </span>
          </div>

          <div
            className="flex items-center gap-1 cursor-pointer"
            title={health.tv ? "TradingView CDP: connected" : "TradingView CDP: not detected"}
          >
            <Dot ok={health.tv} />
            <span className={cn("text-[10px]", health.tv ? "text-zinc-600" : "text-red-600/80")}>
              TV
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
