import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

const DATA_FILE = path.join(process.cwd(), "data", "journal.json");

interface JournalEntry {
  id: number;
  pair: string;
  direction: string;
  entry_price: number;
  sl_price: number;
  tp1_price: number;
  tp2_price: number | null;
  entry_date: string;
  exit_date?: string;
  exit_price?: number;
  result?: string;
  pips_gained?: number;
  notes?: string;
  grade?: string;
}

async function readData() {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf-8");
    return JSON.parse(raw);
  } catch {
    return { entries: [], balance: { initial: 10000000, current: 10000000 } };
  }
}

export async function GET() {
  try {
    const data = await readData();
    const entries: JournalEntry[] = data.entries || [];
    
    const completed = entries.filter((e: JournalEntry) => e.result && e.result !== "PENDING");
    const wins = completed.filter((e: JournalEntry) => e.result === "WIN").length;
    const losses = completed.filter((e: JournalEntry) => e.result === "LOSS").length;
    const breakeven = completed.filter((e: JournalEntry) => e.result === "BE").length;
    const pending = entries.filter((e: JournalEntry) => e.result === "PENDING").length;
    
    const winRate = completed.length > 0 ? (wins / completed.length) * 100 : 0;
    
    const winsWithPips = completed.filter((e: JournalEntry) => e.result === "WIN" && e.pips_gained !== undefined);
    const lossesWithPips = completed.filter((e: JournalEntry) => e.result === "LOSS" && e.pips_gained !== undefined);
    
    const avgWin = winsWithPips.length > 0
      ? winsWithPips.reduce((sum, e) => sum + (e.pips_gained || 0), 0) / winsWithPips.length
      : 0;
    const avgLoss = lossesWithPips.length > 0
      ? Math.abs(lossesWithPips.reduce((sum, e) => sum + (e.pips_gained || 0), 0) / lossesWithPips.length)
      : 0;
    
    const allPips = completed.filter((e: JournalEntry) => e.pips_gained !== undefined).map((e: JournalEntry) => e.pips_gained || 0);
    const bestTrade = allPips.length > 0 ? Math.max(...allPips) : 0;
    const worstTrade = allPips.length > 0 ? Math.min(...allPips) : 0;
    const totalPips = allPips.reduce((sum, p) => sum + p, 0);
    
    const rrRatio = avgLoss > 0 ? avgWin / avgLoss : 0;
    
    return NextResponse.json({
      totalTrades: entries.length,
      wins,
      losses,
      breakeven,
      pending,
      winRate,
      avgWin: Math.round(avgWin),
      avgLoss: Math.round(avgLoss),
      bestTrade,
      worstTrade,
      totalPips,
      rrRatio
    });
  } catch (error) {
    return NextResponse.json({ error: "Failed" }, { status: 500 });
  }
}