import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

const DATA_FILE = path.join(process.cwd(), "data", "journal.json");

async function ensureDataDir() {
  const dir = path.dirname(DATA_FILE);
  try {
    await fs.mkdir(dir, { recursive: true });
  } catch {}
}

async function readData() {
  await ensureDataDir();
  try {
    const raw = await fs.readFile(DATA_FILE, "utf-8");
    return JSON.parse(raw);
  } catch {
    return { entries: [], balance: { initial: 10000000, current: 10000000 } };
  }
}

async function writeData(data: any) {
  await ensureDataDir();
  await fs.writeFile(DATA_FILE, JSON.stringify(data, null, 2));
}

export async function GET() {
  try {
    const data = await readData();
    return NextResponse.json({ entries: data.entries || [] });
  } catch (error) {
    return NextResponse.json({ error: "Failed to read" }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const data = await readData();
    
    const entry = {
      id: Date.now(),
      pair: body.pair || "BTCUSD",
      direction: body.direction || "BUY",
      entry_price: body.entry_price,
      sl_price: body.sl_price,
      tp1_price: body.tp1_price,
      tp2_price: body.tp2_price || null,
      entry_date: new Date().toISOString(),
      exit_date: null,
      exit_price: null,
      result: "PENDING",
      pips_gained: null,
      notes: body.notes || "",
      grade: body.grade || null,
      created_at: new Date().toISOString()
    };
    
    data.entries = [entry, ...(data.entries || [])];
    await writeData(data);
    
    return NextResponse.json({ success: true, entry });
  } catch (error) {
    return NextResponse.json({ error: "Failed to create entry" }, { status: 500 });
  }
}