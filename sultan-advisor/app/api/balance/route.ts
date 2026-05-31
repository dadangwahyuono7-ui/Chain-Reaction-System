import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

const DATA_FILE = path.join(process.cwd(), "data", "journal.json");

async function readData() {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf-8");
    return JSON.parse(raw);
  } catch {
    return { entries: [], balance: { initial: 10000000, current: 10000000 } };
  }
}

async function writeData(data: any) {
  const dir = path.dirname(DATA_FILE);
  try { await fs.mkdir(dir, { recursive: true }); } catch {}
  await fs.writeFile(DATA_FILE, JSON.stringify(data, null, 2));
}

export async function GET() {
  try {
    const data = await readData();
    const balance = data.balance || { initial: 10000000, current: 10000000 };
    const change = balance.current - balance.initial;
    const changePercent = (change / balance.initial) * 100;
    
    return NextResponse.json({
      initial: balance.initial,
      current: balance.current,
      change,
      changePercent
    });
  } catch (error) {
    return NextResponse.json({ error: "Failed" }, { status: 500 });
  }
}

export async function POST() {
  try {
    const data = await readData();
    data.balance = { initial: 10000000, current: 10000000 };
    await writeData(data);
    
    return NextResponse.json({ success: true, balance: data.balance });
  } catch (error) {
    return NextResponse.json({ error: "Failed" }, { status: 500 });
  }
}