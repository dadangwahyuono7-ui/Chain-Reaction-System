"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";

type Account = {
  id: string; label: string;
  initialBalance: number; balance: number; riskPerTrade: number;
};
type Trade = {
  id: string; accountId: string; instrument: string; direction: string;
  setupTf: string | null; grade: string | null; status: string;
  entryPrice: number; slPrice: number; tp1Price: number | null;
  exitPrice: number | null; rMultiple: number | null; pnl: number | null;
  openReason: string | null; closeReason: string | null;
  openedAt: number; closedAt: number | null;
};
type Stat = {
  open: number; wins: number; losses: number; be: number;
  totalR: number; winRate: number; avgR: number; expectancy: number;
};

const fmtRp = (n: number) =>
  "Rp " + Math.round(n).toLocaleString("id-ID");

export function PaperPerformance({ expanded = false }: { expanded?: boolean }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [trades,   setTrades]   = useState<Trade[]>([]);
  const [stats,    setStats]    = useState<Record<string, Stat>>({});
  const [tab,      setTab]      = useState<"engine" | "ai">("engine");
  const [loading,  setLoading]  = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/paper");
      const j = await r.json();
      setAccounts(j.accounts || []);
      setTrades(j.trades || []);
      setStats(j.stats || {});
    } catch { /* offline */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15_000);
    return () => clearInterval(t);
  }, [load]);

  const acc  = accounts.find(a => a.id === tab);
  const st   = stats[tab];
  const list = trades.filter(t => t.accountId === tab).slice(0, expanded ? 50 : 12);

  const reset = async () => {
    if (!confirm(`Reset akun ${tab}? Semua trade dihapus & saldo balik ke awal.`)) return;
    await fetch("/api/paper", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "reset", accountId: tab }),
    });
    load();
  };

  const pnl = acc ? acc.balance - acc.initialBalance : 0;
  const pnlPct = acc && acc.initialBalance ? (pnl / acc.initialBalance) * 100 : 0;

  return (
    <div className="bg-zinc-900/60 rounded-lg border border-zinc-800 overflow-hidden">
      <div className="px-2 py-1 border-b border-zinc-800 flex items-center justify-between">
        <span className="text-[9px] font-black font-mono text-emerald-500 tracking-widest">[ PAPER.PERFORMANCE ]</span>
        <button onClick={reset} className="text-[8px] font-mono text-zinc-600 hover:text-red-400 transition-colors">RESET</button>
      </div>

      {/* Tab switch: Engine vs AI */}
      <div className="flex border-b border-zinc-800">
        {(["engine", "ai"] as const).map(id => {
          const a = accounts.find(x => x.id === id);
          const active = tab === id;
          return (
            <button key={id} onClick={() => setTab(id)}
              className={cn("flex-1 px-2 py-1.5 text-[9px] font-black font-mono tracking-wide transition-all",
                active ? "bg-zinc-800/80 text-emerald-300" : "text-zinc-600 hover:text-zinc-400")}>
              {id === "engine" ? "⚙ ENGINE" : "🧠 AI"}
              <div className={cn("text-[8px] mt-0.5", (a && a.balance >= a.initialBalance) ? "text-emerald-500" : "text-red-400")}>
                {a ? fmtRp(a.balance) : "—"}
              </div>
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="px-3 py-4 text-center text-[9px] font-mono text-zinc-600">memuat…</div>
      ) : (
        <>
          {/* Saldo + P&L */}
          <div className="px-2.5 py-2 border-b border-zinc-800/60">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-[8px] font-mono text-zinc-600 uppercase">Saldo</div>
                <div className="text-sm font-black font-mono tabular-nums text-zinc-100">{acc ? fmtRp(acc.balance) : "—"}</div>
              </div>
              <div className={cn("text-right font-mono tabular-nums", pnl >= 0 ? "text-emerald-400" : "text-red-400")}>
                <div className="text-[10px] font-black">{pnl >= 0 ? "▲" : "▼"} {fmtRp(Math.abs(pnl))}</div>
                <div className="text-[8px]">{pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%</div>
              </div>
            </div>
          </div>

          {/* Stat grid */}
          {st && (
            <div className="grid grid-cols-4 gap-px bg-zinc-800/40">
              <Stat label="WIN%" value={`${st.winRate}`} accent={st.winRate >= 50 ? "good" : "bad"} />
              <Stat label="TOT R" value={(st.totalR >= 0 ? "+" : "") + st.totalR} accent={st.totalR >= 0 ? "good" : "bad"} />
              <Stat label="AVG R" value={(st.avgR >= 0 ? "+" : "") + st.avgR} accent={st.avgR >= 0 ? "good" : "bad"} />
              <Stat label="OPEN" value={`${st.open}`} accent="neutral" />
            </div>
          )}
          {st && (
            <div className="px-2.5 py-1 border-t border-zinc-800/60 flex justify-between text-[8px] font-mono text-zinc-600">
              <span>W:{st.wins} L:{st.losses} BE:{st.be}</span>
              <span>risk/trade: {acc ? fmtRp(acc.riskPerTrade) : "—"} = 1R</span>
            </div>
          )}

          {/* Trade list */}
          <div className={expanded ? "" : "max-h-44 overflow-y-auto"}>
            {list.length === 0 ? (
              <div className="px-3 py-3 text-center text-[9px] font-mono text-zinc-600">
                Belum ada trade. {tab === "engine" ? "Nyalakan AUTOPILOT biar engine entry otomatis." : "AI belum buka posisi."}
              </div>
            ) : list.map(t => {
              const open = t.status === "OPEN";
              const col = t.status === "WIN" ? "text-emerald-400"
                : t.status === "LOSS" ? "text-red-400"
                : t.status === "BE" ? "text-zinc-400" : "text-amber-400";
              return (
                <div key={t.id} className="px-2.5 py-1 border-b border-zinc-800/40 last:border-0 flex items-center gap-2">
                  <span className={cn("text-[9px] font-black font-mono w-9 shrink-0",
                    t.direction === "BUY" ? "text-emerald-500" : "text-red-500")}>{t.direction}</span>
                  <span className="text-[9px] font-mono text-zinc-400 flex-1 truncate">
                    {t.instrument}{t.setupTf ? `·${t.setupTf}` : ""} @ {t.entryPrice.toFixed(2)}
                  </span>
                  <span className={cn("text-[9px] font-black font-mono shrink-0", col)}>
                    {open ? "OPEN" : `${t.rMultiple != null ? (t.rMultiple >= 0 ? "+" : "") + t.rMultiple.toFixed(2) + "R" : t.status}`}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent: "good" | "bad" | "neutral" }) {
  const col = accent === "good" ? "text-emerald-400" : accent === "bad" ? "text-red-400" : "text-zinc-300";
  return (
    <div className="bg-zinc-900 px-1 py-1.5 text-center">
      <div className="text-[7px] font-mono text-zinc-600 uppercase tracking-wide">{label}</div>
      <div className={cn("text-[11px] font-black font-mono tabular-nums", col)}>{value}</div>
    </div>
  );
}
