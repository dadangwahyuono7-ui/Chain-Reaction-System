import { NextResponse } from "next/server";

async function checkPort(url: string, timeoutMs = 2000): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(url, { signal: ctrl.signal });
    clearTimeout(timer);
    return res.ok || res.status < 500;
  } catch {
    return false;
  }
}

export async function GET() {
  const [qwen, tv] = await Promise.all([
    checkPort("http://localhost:8080/v1/models"),
    checkPort("http://localhost:9222/json/version"),
  ]);

  return NextResponse.json({
    qwen: qwen,
    tv:   tv,
    ts:   Date.now(),
  });
}
