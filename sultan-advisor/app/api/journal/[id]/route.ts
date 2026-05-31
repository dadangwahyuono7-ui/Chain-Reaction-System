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

interface DataStore {
  entries: JournalEntry[];
  balance: { initial: number; current: number };
}

async function readData(): Promise<DataStore> {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf-8");
    return JSON.parse(raw);
  } catch {
    return { entries: [], balance: { initial: 10000000, current: 10000000 } };
  }
}

async function writeData(data: DataStore): Promise<void> {
  const dir = path.dirname(DATA_FILE);
  try { await fs.mkdir(dir, { recursive: true }); } catch {}
  await fs.writeFile(DATA_FILE, JSON.stringify(data, null, 2));
}

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const data = await readData();
    const entry = data.entries.find((e: JournalEntry) => e.id === parseInt(id));
    if (!entry) return NextResponse.json({ error: "Not found" }, { status: 404 });
    return NextResponse.json(entry);
  } catch (error) {
    return NextResponse.json({ error: "Failed" }, { status: 500 });
  }
}

export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await req.json();
    const data = await readData();
    
    const idx = data.entries.findIndex((e: JournalEntry) => e.id === parseInt(id));
    if (idx === -1) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }
    
    const entry = data.entries[idx];
    entry.result = body.result || entry.result;
    entry.exit_price = body.exit_price || entry.exit_price;
    entry.exit_date = new Date().toISOString();
    
    // Calculate pips
    if (entry.exit_price && entry.entry_price) {
      const direction = entry.direction === "BUY" ? 1 : -1;
      entry.pips_gained = Math.round((entry.exit_price - entry.entry_price) * direction);
      
      // Update balance
      if (entry.result === "WIN") {
        const pipsValue = Math.abs(entry.pips_gained) * 100000;
        data.balance.current += pipsValue;
      } else if (entry.result === "LOSS") {
        const pipsValue = Math.abs(entry.pips_gained) * 100000;
        data.balance.current -= pipsValue;
      }
    }
    
    data.entries[idx] = entry;
    await writeData(data);
    
    return NextResponse.json({ success: true, entry });
  } catch (error) {
    return NextResponse.json({ error: "Failed to update" }, { status: 500 });
  }
}