/**
 * fundamental-snapshot.mjs
 * Reads TradingView via CDP, switches to Daily/Weekly TF to get bar data,
 * calculates PDH/PDL/PWH/PWL/Round Numbers/Session H-L, then restores TF.
 *
 * Output JSON:
 * { success: true, snr: { PDH, PDL, PWH, PWL, DAILY_OPEN, WEEKLY_OPEN, PMH, PML,
 *   ROUND_ABOVE, ROUND_BELOW, TP_ABOVE_1, TP_ABOVE_2, TP_BELOW_1, TP_BELOW_2,
 *   ASIA_H, ASIA_L, LONDON_H, LONDON_L, HARGA }, levels: [...sorted] }
 */

import CDP from 'chrome-remote-interface';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  let client;
  try {
    const list = await CDP.List({ port: 9222 });
    const tab  = list.find(t => t.url?.includes('tradingview.com/chart'));
    if (!tab) throw new Error('TradingView chart tab tidak ditemukan di port 9222');

    client = await CDP({ target: tab.id, port: 9222 });
    await client.Runtime.enable();

    const ev = async (expr) => {
      const r = await client.Runtime.evaluate({ expression: expr, returnByValue: true, timeout: 8000 });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval error');
      return r.result?.value;
    };

    const API   = `window.TradingViewApi._activeChartWidgetWV.value()`;
    const CHART = `${API}._chartWidget`;

    // Save current resolution
    const origTF = await ev(`${API}.resolution()`) || '15';

    async function switchTF(tf) {
      await ev(`${API}.setResolution('${tf}', {})`);
      const deadline = Date.now() + 8000;
      while (Date.now() < deadline) {
        await sleep(350);
        const cur = await ev(`${API}.resolution()`);
        if (cur === tf) { await sleep(800); return true; }
      }
      return false;
    }

    async function getBars(n) {
      return await ev(`(function(){
        var bars=${CHART}.model().mainSeries().bars();
        var end=bars.lastIndex(), out=[];
        for(var i=Math.max(bars.firstIndex(),end-${n}+1);i<=end;i++){
          var v=bars.valueAt(i);
          if(v) out.push([v[0],+v[1].toFixed(2),+v[2].toFixed(2),+v[3].toFixed(2),+v[4].toFixed(2)]);
        }
        return out;
      })()`);
    }

    // Current price (on original TF)
    const cmp = parseFloat(await ev(`(function(){
      var q=${CHART}.model().mainSeries();
      var last=q.data().bars().last();
      return last?last.value[4].toFixed(2):'0';
    })()`) || '0');

    // Switch to Daily
    await switchTF('1D');
    const dailyBars = await getBars(35) || []; // [ts, o, h, l, c]

    // Switch to Weekly
    await switchTF('W');
    const weeklyBars = await getBars(8) || [];

    // Switch to H1 (for session data)
    await switchTF('60');
    const h1Bars = await getBars(50) || [];

    // Restore original TF
    await switchTF(origTF);
    await client.close();

    // ── Parse bars ──────────────────────────────────────────────────────────
    if (dailyBars.length < 2) throw new Error('Daily bars data tidak cukup');

    const today    = dailyBars[dailyBars.length - 1]; // [ts,o,h,l,c]
    const prevDay  = dailyBars[dailyBars.length - 2];
    const pdh      = prevDay[2]; // high
    const pdl      = prevDay[3]; // low
    const dailyOpen = today[1];  // open

    const prevWeek   = weeklyBars.length >= 2 ? weeklyBars[weeklyBars.length - 2] : null;
    const thisWeek   = weeklyBars.length >= 1 ? weeklyBars[weeklyBars.length - 1] : null;
    const pwh        = prevWeek ? prevWeek[2] : null;
    const pwl        = prevWeek ? prevWeek[3] : null;
    const weeklyOpen = thisWeek ? thisWeek[1] : null;

    // Previous Month
    const todayDate = new Date(today[0] * 1000);
    const thisMonth = todayDate.getUTCMonth();
    const thisYear  = todayDate.getUTCFullYear();
    const prevMo    = thisMonth === 0 ? { m: 11, y: thisYear - 1 } : { m: thisMonth - 1, y: thisYear };
    const prevMoBars = dailyBars.filter(b => {
      const d = new Date(b[0] * 1000);
      return d.getUTCMonth() === prevMo.m && d.getUTCFullYear() === prevMo.y;
    });
    const pmh = prevMoBars.length ? Math.max(...prevMoBars.map(b => b[2])) : null;
    const pml = prevMoBars.length ? Math.min(...prevMoBars.map(b => b[3])) : null;

    // Session H/L from H1 bars today
    const todayStr = new Date(today[0] * 1000).toISOString().slice(0, 10);
    const todayH1  = h1Bars.filter(b => new Date(b[0] * 1000).toISOString().startsWith(todayStr));
    function sessionHL(bars, startH, endH) {
      const s = bars.filter(b => { const h = new Date(b[0]*1000).getUTCHours(); return h >= startH && h < endH; });
      if (!s.length) return null;
      return { h: Math.max(...s.map(b => b[2])), l: Math.min(...s.map(b => b[3])) };
    }
    const asia   = sessionHL(todayH1, 0, 7);
    const london = sessionHL(todayH1, 7, 16);

    // Round numbers (50-pt and 25-pt)
    const STEP_BIG   = 50;
    const STEP_SMALL = 25;
    const RANGE      = 200;
    function roundLevels(step) {
      const base   = Math.floor(cmp / step) * step;
      const levels = [];
      for (let l = base - RANGE; l <= base + RANGE; l += step) levels.push(parseFloat(l.toFixed(2)));
      return levels;
    }
    const bigRounds   = roundLevels(STEP_BIG);
    const smallRounds = roundLevels(STEP_SMALL);

    // Build sorted level list
    const rawLevels = [
      { price: pdh,        label: 'PDH',         rating: 5 },
      { price: pdl,        label: 'PDL',          rating: 5 },
      { price: dailyOpen,  label: 'Daily Open',   rating: 4 },
      ...(pwh  ? [{ price: pwh,        label: 'PWH',         rating: 5 }] : []),
      ...(pwl  ? [{ price: pwl,        label: 'PWL',         rating: 5 }] : []),
      ...(weeklyOpen ? [{ price: weeklyOpen, label: 'Weekly Open', rating: 4 }] : []),
      ...(pmh  ? [{ price: pmh, label: 'PMH', rating: 4 }] : []),
      ...(pml  ? [{ price: pml, label: 'PML', rating: 4 }] : []),
      ...(asia   ? [{ price: asia.h,   label: 'Asia High',   rating: 3 },
                    { price: asia.l,   label: 'Asia Low',    rating: 3 }] : []),
      ...(london ? [{ price: london.h, label: 'London High', rating: 3 },
                    { price: london.l, label: 'London Low',  rating: 3 }] : []),
      ...bigRounds.map(r => ({ price: r, label: `Round ${r}`, rating: 4 })),
    ].filter(l => l.price > 0);

    // Deduplicate and sort
    const seen = new Set();
    const levels = rawLevels
      .filter(l => { const k = l.price.toFixed(2); if (seen.has(k)) return false; seen.add(k); return true; })
      .sort((a, b) => b.price - a.price); // high → low

    // Find nearest TP levels above and below CMP (skip round numbers first, prefer named)
    const above = levels.filter(l => l.price > cmp + 2).sort((a, b) => a.price - b.price);
    const below = levels.filter(l => l.price < cmp - 2).sort((a, b) => b.price - a.price);

    const nearestRoundAbove = smallRounds.filter(r => r > cmp).sort((a,b) => a - b)[0];
    const nearestRoundBelow = smallRounds.filter(r => r < cmp).sort((a,b) => b - a)[0];

    // Snap to string helper
    const fmt = (v) => v != null ? parseFloat(v).toFixed(2) : '';

    const snr = {
      HARGA:        fmt(cmp),
      PDH:          fmt(pdh),
      PDL:          fmt(pdl),
      DAILY_OPEN:   fmt(dailyOpen),
      PWH:          fmt(pwh),
      PWL:          fmt(pwl),
      WEEKLY_OPEN:  fmt(weeklyOpen),
      PMH:          fmt(pmh),
      PML:          fmt(pml),
      ASIA_H:       fmt(asia?.h),
      ASIA_L:       fmt(asia?.l),
      LONDON_H:     fmt(london?.h),
      LONDON_L:     fmt(london?.l),
      ROUND_ABOVE:  fmt(nearestRoundAbove),
      ROUND_BELOW:  fmt(nearestRoundBelow),
      TP_ABOVE_1:   above[0] ? `${fmt(above[0].price)} (${above[0].label})` : '',
      TP_ABOVE_2:   above[1] ? `${fmt(above[1].price)} (${above[1].label})` : '',
      TP_BELOW_1:   below[0] ? `${fmt(below[0].price)} (${below[0].label})` : '',
      TP_BELOW_2:   below[1] ? `${fmt(below[1].price)} (${below[1].label})` : '',
    };

    process.stdout.write(JSON.stringify({ success: true, snr, levels }));
    process.exit(0);

  } catch (err) {
    if (client) { try { await client.close(); } catch {} }
    process.stdout.write(JSON.stringify({ success: false, error: err.message }));
    process.exit(1);
  }
}

main();
