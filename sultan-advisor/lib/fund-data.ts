/**
 * lib/fund-data — komputasi "Jejak Fund" dari Yahoo Finance.
 * Dipakai oleh /api/fund-data (panel) DAN tool get_fund_data (AI).
 */

export type Candle = { t: number; o: number; h: number; l: number; c: number; v: number };

export async function yfChart(symbol: string, interval: string, range: string): Promise<Candle[]> {
  const url = `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=${interval}&range=${range}&includePrePost=false`;
  const res = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0 SultanAdvisor/1.0", Accept: "application/json" },
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`YF ${symbol} HTTP ${res.status}`);
  const data = await res.json();
  const r = data?.chart?.result?.[0];
  if (!r) throw new Error(`no data ${symbol}`);
  const ts: number[] = r.timestamp ?? [];
  const q = r.indicators?.quote?.[0] ?? {};
  const out: Candle[] = [];
  for (let i = 0; i < ts.length; i++) {
    if (q.close?.[i] == null || q.open?.[i] == null) continue;
    out.push({ t: ts[i], o: q.open[i], h: q.high[i], l: q.low[i], c: q.close[i], v: q.volume?.[i] ?? 0 });
  }
  return out;
}

async function lastPrice(symbol: string): Promise<number | null> {
  try { const c = await yfChart(symbol, "5m", "1d"); return c.length ? c[c.length - 1].c : null; }
  catch { return null; }
}

function volumeProfile(candles: Candle[], bins = 40) {
  if (candles.length === 0) return null;
  const hi = Math.max(...candles.map(c => c.h));
  const lo = Math.min(...candles.map(c => c.l));
  const span = hi - lo || 1;
  const step = span / bins;
  const vol = new Array(bins).fill(0);
  for (const c of candles) {
    const loB = Math.floor((c.l - lo) / step);
    const hiB = Math.min(bins - 1, Math.floor((c.h - lo) / step));
    const n = Math.max(1, hiB - loB + 1);
    const per = c.v / n;
    for (let b = Math.max(0, loB); b <= hiB; b++) vol[b] += per;
  }
  const priceOf = (b: number) => lo + (b + 0.5) * step;
  const totalVol = vol.reduce((s, v) => s + v, 0) || 1;
  let pocB = 0; for (let b = 1; b < bins; b++) if (vol[b] > vol[pocB]) pocB = b;
  let included = vol[pocB], loVA = pocB, hiVA = pocB;
  while (included < totalVol * 0.7 && (loVA > 0 || hiVA < bins - 1)) {
    const below = loVA > 0 ? vol[loVA - 1] : -1;
    const above = hiVA < bins - 1 ? vol[hiVA + 1] : -1;
    if (above >= below) { hiVA++; included += vol[hiVA]; } else { loVA--; included += vol[loVA]; }
  }
  const idx = vol.map((v, b) => ({ v, b })).filter(x => x.v > 0);
  const hvn = [...idx].sort((a, b) => b.v - a.v).slice(0, 3).map(x => +priceOf(x.b).toFixed(2));
  const lvn = [...idx].sort((a, b) => a.v - b.v).slice(0, 2).map(x => +priceOf(x.b).toFixed(2));
  return { poc: +priceOf(pocB).toFixed(2), valueAreaHigh: +priceOf(hiVA).toFixed(2), valueAreaLow: +priceOf(loVA).toFixed(2), hvn, lvn, hi: +hi.toFixed(2), lo: +lo.toFixed(2) };
}

function liquidityZones(candles: Candle[], lookback = 3) {
  const highs: number[] = [], lows: number[] = [];
  for (let i = lookback; i < candles.length - lookback; i++) {
    const win = candles.slice(i - lookback, i + lookback + 1);
    if (candles[i].h >= Math.max(...win.map(c => c.h))) highs.push(candles[i].h);
    if (candles[i].l <= Math.min(...win.map(c => c.l))) lows.push(candles[i].l);
  }
  const price = candles.length ? candles[candles.length - 1].c : 0;
  const tol = price * 0.0012;
  const cluster = (arr: number[]) => {
    const used = new Array(arr.length).fill(false);
    const zones: { price: number; touches: number }[] = [];
    for (let i = 0; i < arr.length; i++) {
      if (used[i]) continue;
      const group = [arr[i]];
      for (let j = i + 1; j < arr.length; j++) if (!used[j] && Math.abs(arr[j] - arr[i]) <= tol) { group.push(arr[j]); used[j] = true; }
      if (group.length >= 2) zones.push({ price: +(group.reduce((s, x) => s + x, 0) / group.length).toFixed(2), touches: group.length });
    }
    return zones;
  };
  const eqHighs = cluster(highs).filter(z => z.price > price).sort((a, b) => a.price - b.price);
  const eqLows = cluster(lows).filter(z => z.price < price).sort((a, b) => b.price - a.price);
  return { liquidityAbove: eqHighs[0] ?? null, liquidityBelow: eqLows[0] ?? null, allAbove: eqHighs.slice(0, 3), allBelow: eqLows.slice(0, 3) };
}

function trendOf(candles: Candle[], n = 12): "naik" | "turun" | "flat" {
  if (candles.length < n + 1) return "flat";
  const now = candles[candles.length - 1].c, prev = candles[candles.length - 1 - n].c;
  const d = (now - prev) / prev;
  return d > 0.001 ? "naik" : d < -0.001 ? "turun" : "flat";
}

export async function computeFundData() {
  const [gc, dxy, tnx] = await Promise.all([
    yfChart("GC=F", "30m", "5d").catch(() => [] as Candle[]),
    yfChart("DX-Y.NYB", "1h", "5d").catch(() => [] as Candle[]),
    yfChart("^TNX", "1h", "5d").catch(() => [] as Candle[]),
  ]);
  const spot = await lastPrice("XAUUSD=X");
  const vp = volumeProfile(gc);
  const liq = liquidityZones(gc);
  const gcLast = gc.length ? gc[gc.length - 1].c : null;
  const basis = gcLast != null && spot != null ? +(gcLast - spot).toFixed(2) : null;
  const dxyLast = dxy.length ? +dxy[dxy.length - 1].c.toFixed(2) : null;
  const dxyTrend = trendOf(dxy);
  const tnxLast = tnx.length ? +tnx[tnx.length - 1].c.toFixed(2) : null;
  const tnxTrend = trendOf(tnx);
  const macroBias = (dxyTrend === "naik" || tnxTrend === "naik") ? "BEARISH-gold"
    : (dxyTrend === "turun" || tnxTrend === "turun") ? "BULLISH-gold" : "netral";
  const summary = [
    vp ? `VOLUME PROFILE GC=F: POC(magnet) ${vp.poc} | Value Area ${vp.valueAreaLow}-${vp.valueAreaHigh} | HVN(akumulasi) ${vp.hvn.join(", ")} | LVN(rejection) ${vp.lvn.join(", ")}` : "",
    liq.liquidityAbove ? `LIQUIDITY ATAS (stop pool): ${liq.liquidityAbove.price} (${liq.liquidityAbove.touches}x sentuh)` : "",
    liq.liquidityBelow ? `LIQUIDITY BAWAH (stop pool): ${liq.liquidityBelow.price} (${liq.liquidityBelow.touches}x sentuh)` : "",
    basis != null ? `BASIS COMEX-Spot: ${basis > 0 ? "+" : ""}${basis} (${basis > 0 ? "futures premium" : "discount"})` : "",
    dxyLast != null ? `DXY: ${dxyLast} (${dxyTrend})` : "",
    tnxLast != null ? `US10Y: ${tnxLast}% (${tnxTrend})` : "",
    `MACRO BIAS gold: ${macroBias}`,
  ].filter(Boolean).join("\n");
  return { ok: true, updatedAt: Date.now(), volumeProfile: vp, liquidity: liq, basis: { gc: gcLast, spot, basis }, macro: { dxy: dxyLast, dxyTrend, us10y: tnxLast, tnxTrend, macroBias }, summary };
}
