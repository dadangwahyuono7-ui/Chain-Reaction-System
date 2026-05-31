// components/dashboard/dashboard-components/JournalTab.tsx

"use client";

import { useState, useEffect } from "react";

interface JournalEntry {
  id: number;
  pair: string;
  direction: "BUY" | "SELL";
  entry_price: number;
  sl_price: number;
  tp1_price: number;
  tp2_price: number | null;
  entry_date: string;
  exit_date?: string;
  exit_price?: number;
  result?: "WIN" | "LOSS" | "BE" | "PENDING";
  pips_gained?: number;
  notes?: string;
  grade?: string;
}

interface Balance {
  initial: number;
  current: number;
  change: number;
  changePercent: number;
}

interface Stats {
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  bestTrade: number;
  worstTrade: number;
  totalPips: number;
  rrRatio: number;
}

export default function JournalTab() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState({
    pair: "BTCUSD",
    direction: "BUY" as "BUY" | "SELL",
    entry_price: "",
    sl_price: "",
    tp1_price: "",
    tp2_price: "",
    notes: "",
  });

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [journalRes, balanceRes, statsRes] = await Promise.all([
        fetch("/api/journal"),
        fetch("/api/balance"),
        fetch("/api/stats"),
      ]);
      const journalData = await journalRes.json();
      const balanceData = await balanceRes.json();
      const statsData = await statsRes.json();
      setEntries(journalData.entries || []);
      setBalance(balanceData);
      setStats(statsData);
    } catch (error) {
      console.error("Fetch error:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetch("/api/journal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          entry_price: parseFloat(form.entry_price),
          sl_price: parseFloat(form.sl_price),
          tp1_price: parseFloat(form.tp1_price),
          tp2_price: form.tp2_price ? parseFloat(form.tp2_price) : null,
        }),
      });
      setShowAddForm(false);
      setForm({ pair: "BTCUSD", direction: "BUY", entry_price: "", sl_price: "", tp1_price: "", tp2_price: "", notes: "" });
      fetchAll();
    } catch (error) {
      console.error("Submit error:", error);
    }
  };

  const updateResult = async (id: number, result: string, exitPrice?: number) => {
    try {
      await fetch(`/api/journal/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ result, exit_price: exitPrice }),
      });
      fetchAll();
    } catch (error) {
      console.error("Update error:", error);
    }
  };

  const resetBalance = async () => {
    if (!confirm("Reset balance ke Rp 10.000.000?")) return;
    try {
      await fetch("/api/balance/reset", { method: "POST" });
      fetchAll();
    } catch (error) {
      console.error("Reset error:", error);
    }
  };

  const formatCurrency = (num: number) =>
    new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 }).format(num);

  const getResultColor = (r?: string) => {
    if (r === "WIN") return "text-green-400";
    if (r === "LOSS") return "text-red-400";
    if (r === "BE") return "text-yellow-400";
    return "text-gray-400";
  };

  if (loading) {
    return (
      <div className="p-6 text-gray-400 animate-pulse">
        Loading journal...
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* ===== PAPER BALANCE ===== */}
      <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-xl p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-white">💰 Paper Balance</h2>
          <button onClick={resetBalance} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-400">
            🔄 Reset
          </button>
        </div>
        {balance && (
          <>
            <div className="text-3xl font-bold text-white mb-2">
              {formatCurrency(balance.current)}
            </div>
            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full ${balance.change >= 0 ? "bg-green-900/30" : "bg-red-900/30"}`}>
              <span className={balance.change >= 0 ? "text-green-400" : "text-red-400"}>
                {balance.change >= 0 ? "📈" : "📉"} {formatCurrency(balance.change)} ({balance.change >= 0 ? "+" : ""}{balance.changePercent.toFixed(2)}%)
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div className="bg-gray-800 rounded-lg p-3">
                <div className="text-gray-400 text-xs">Modal Awal</div>
                <div className="text-lg font-bold text-white">{formatCurrency(balance.initial)}</div>
              </div>
              <div className="bg-gray-800 rounded-lg p-3">
                <div className="text-gray-400 text-xs">Profit/Loss</div>
                <div className={`text-lg font-bold ${balance.change >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {balance.change >= 0 ? "+" : ""}{formatCurrency(balance.change)}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ===== PERFORMANCE STATS ===== */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-xs mb-1">Win Rate</div>
            <div className="text-2xl font-bold text-green-400">{stats.winRate.toFixed(1)}%</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-xs mb-1">R:R Ratio</div>
            <div className="text-2xl font-bold text-blue-400">{stats.rrRatio.toFixed(2)}:1</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-xs mb-1">Best Trade</div>
            <div className="text-2xl font-bold text-green-400">+{stats.bestTrade} pips</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-gray-400 text-xs mb-1">Total Pips</div>
            <div className={`text-2xl font-bold ${stats.totalPips >= 0 ? "text-green-400" : "text-red-400"}`}>
              {stats.totalPips >= 0 ? "+" : ""}{stats.totalPips}
            </div>
          </div>
        </div>
      )}

      {/* ===== JOURNAL ENTRIES ===== */}
      <div className="bg-gray-900 rounded-xl p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-white">📝 Trading Journal</h2>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm font-medium"
          >
            {showAddForm ? "Tutup" : "+ Tambah Manual"}
          </button>
        </div>

        {/* Add Form */}
        {showAddForm && (
          <form onSubmit={handleSubmit} className="bg-gray-800 rounded-lg p-4 mb-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              <div>
                <label className="text-gray-400 text-xs">Pair</label>
                <select value={form.pair} onChange={e => setForm({...form, pair: e.target.value})} className="w-full bg-gray-700 text-white rounded px-3 py-2">
                  <option value="BTCUSD">BTCUSD</option>
                  <option value="XAUUSD">XAUUSD</option>
                </select>
              </div>
              <div>
                <label className="text-gray-400 text-xs">Direction</label>
                <select value={form.direction} onChange={e => setForm({...form, direction: e.target.value as "BUY" | "SELL"})} className="w-full bg-gray-700 text-white rounded px-3 py-2">
                  <option value="BUY">BUY</option>
                  <option value="SELL">SELL</option>
                </select>
              </div>
              <div>
                <label className="text-gray-400 text-xs">Entry</label>
                <input type="number" value={form.entry_price} onChange={e => setForm({...form, entry_price: e.target.value})} className="w-full bg-gray-700 text-white rounded px-3 py-2" required />
              </div>
              <div>
                <label className="text-gray-400 text-xs">SL</label>
                <input type="number" value={form.sl_price} onChange={e => setForm({...form, sl_price: e.target.value})} className="w-full bg-gray-700 text-white rounded px-3 py-2" required />
              </div>
              <div>
                <label className="text-gray-400 text-xs">TP1</label>
                <input type="number" value={form.tp1_price} onChange={e => setForm({...form, tp1_price: e.target.value})} className="w-full bg-gray-700 text-white rounded px-3 py-2" required />
              </div>
              <div>
                <label className="text-gray-400 text-xs">TP2</label>
                <input type="number" value={form.tp2_price} onChange={e => setForm({...form, tp2_price: e.target.value})} className="w-full bg-gray-700 text-white rounded px-3 py-2" />
              </div>
              <div className="md:col-span-2">
                <label className="text-gray-400 text-xs">Notes</label>
                <input type="text" value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} placeholder="Setup info..." className="w-full bg-gray-700 text-white rounded px-3 py-2" />
              </div>
            </div>
            <button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded font-medium">
              💾 Save Entry
            </button>
          </form>
        )}

        {/* Entries List */}
        <div className="space-y-3">
          {entries.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <div className="text-4xl mb-2">📋</div>
              <div>Belum ada entries</div>
              <div className="text-sm">AI akan auto-create draft saat kasih plan</div>
            </div>
          ) : (
            entries.map((entry) => (
              <div key={entry.id} className="bg-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <div className="flex items-center gap-3">
                    <span className={`font-bold ${entry.pair === "BTCUSD" ? "text-orange-400" : "text-yellow-400"}`}>
                      {entry.pair}
                    </span>
                    <span className={`font-bold ${entry.direction === "BUY" ? "text-green-400" : "text-red-400"}`}>
                      {entry.direction}
                    </span>
                    {entry.grade && <span className="px-2 py-1 bg-purple-900 text-purple-300 rounded text-xs">{entry.grade}</span>}
                  </div>
                  <span className={`font-bold ${getResultColor(entry.result)}`}>
                    {entry.result || "⏳ PENDING"}
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-2 text-sm">
                  <div><div className="text-gray-500">Entry</div><div className="text-white font-mono">{entry.entry_price.toLocaleString()}</div></div>
                  <div><div className="text-gray-500">SL</div><div className="text-red-400 font-mono">{entry.sl_price.toLocaleString()}</div></div>
                  <div><div className="text-gray-500">TP1</div><div className="text-green-400 font-mono">{entry.tp1_price.toLocaleString()}</div></div>
                  <div><div className="text-gray-500">TP2</div><div className="text-green-400 font-mono">{(entry.tp2_price || "-").toLocaleString()}</div></div>
                </div>
                <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-700">
                  <div className="text-xs text-gray-500">{new Date(entry.entry_date).toLocaleString("id-ID")}</div>
                  {entry.pips_gained !== undefined && (
                    <div className={`font-bold ${entry.pips_gained >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {entry.pips_gained >= 0 ? "+" : ""}{entry.pips_gained} pips
                    </div>
                  )}
                  {entry.result === "PENDING" && (
                    <div className="flex gap-2">
                      <button onClick={() => { const exit = prompt("Exit price:"); if (exit) updateResult(entry.id, "WIN", parseFloat(exit)); }} className="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-xs text-white">WIN</button>
                      <button onClick={() => updateResult(entry.id, "LOSS")} className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-xs text-white">LOSS</button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}