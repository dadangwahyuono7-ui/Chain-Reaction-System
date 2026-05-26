/**
 * tv-snapshot.mjs
 * Connects to TradingView via CDP (port 9222), reads CMP Engine dashboard,
 * and outputs clean JSON to stdout.
 *
 * Output: { success: true, ctx: {H4_CMP, H4_VR, ...}, price: "3342.15", session: "..." }
 *      or { success: false, error: "..." }
 */

import CDP from 'chrome-remote-interface';

function normalizeTF(raw) {
  const s = (raw || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (s.startsWith('DAILY') || s === 'D1' || s === 'D') return 'DAILY';
  if (s.startsWith('H4'))  return 'H4';
  if (s.startsWith('H1'))  return 'H1';
  if (s.startsWith('M30')) return 'M30';
  if (s.startsWith('M15')) return 'M15';
  if (s.startsWith('M5'))  return 'M5';
  if (s.startsWith('M1'))  return 'M1';
  return null;
}

function cmpToValue(raw) {
  const s = (raw || '').toUpperCase();
  if (s.includes('BUY'))  return 'BULLISH';
  if (s.includes('SELL')) return 'BEARISH';
  return '';
}

function actionToVRCF(raw) {
  const s = (raw || '').toUpperCase();
  if (s.includes('ENTRI'))        return { vr: 'YA',    cf: 'YA'    };
  if (s.includes('MENUNGGU CF'))  return { vr: 'YA',    cf: 'BELUM' };
  if (s.includes('MENUNGGU VR'))  return { vr: 'BELUM', cf: 'BELUM' };
  if (s.includes('MONITOR'))      return { vr: 'BELUM', cf: 'BELUM' };
  return { vr: '', cf: '' };
}

function detectSession() {
  const h = new Date().getUTCHours();
  // UTC offsets: Asia=01-08, London=07-16, NY=12-21
  if (h >= 12 && h < 16) return 'London-NY Overlap';
  if (h >= 12 && h < 21) return 'New York';
  if (h >= 7  && h < 16) return 'London';
  return 'Asia';
}

const READ_EXPR = `(function(){
  try {
    var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
    var sources = chart.model().model().dataSources();
    var results = [];
    for (var i = 0; i < sources.length; i++) {
      var s = sources[i];
      if (!s.metaInfo || !s._graphics) continue;
      try {
        var name = (s.metaInfo().description || s.metaInfo().shortDescription || '').toLowerCase();
        if (!name.includes('cmp')) continue;
        var pc = s._graphics._primitivesCollection;
        if (!pc) continue;
        var tables = {};
        try {
          var outer = pc.dwgtablecells;
          if (outer) {
            ['tableCells','cells'].forEach(function(key) {
              try {
                var inner = outer.get(key);
                if (inner) {
                  var coll = inner.get ? inner.get(false) : inner;
                  if (coll && coll._primitivesDataById) {
                    coll._primitivesDataById.forEach(function(v) {
                      var tid = v.tid || 0;
                      if (!tables[tid]) tables[tid] = {};
                      if (!tables[tid][v.row]) tables[tid][v.row] = {};
                      tables[tid][v.row][v.col] = v.t || '';
                    });
                  }
                }
              } catch(e) {}
            });
          }
        } catch(e) {}
        var rows = [];
        Object.values(tables).forEach(function(t) {
          Object.keys(t).sort(function(a,b){ return +a - +b; }).forEach(function(r) {
            var cols = t[r];
            var line = Object.keys(cols).sort(function(a,b){ return +a - +b; }).map(function(c){ return cols[c]; }).filter(Boolean).join('|');
            if (line.trim()) rows.push(line);
          });
        });
        if (rows.length) results.push({ name: s.metaInfo().description || '', rows: rows });
      } catch(e) {}
    }
    return results;
  } catch(e) { return []; }
})()`;

const PRICE_EXPR = `(function(){
  try {
    var q = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries();
    var last = q.data().bars().last();
    return last ? last.value[4].toFixed(2) : 'N/A';
  } catch(e) { return 'N/A'; }
})()`;

async function main() {
  let client;
  try {
    // Connect
    const list = await CDP.List({ port: 9222 });
    const tab  = list.find(t => t.url && t.url.includes('tradingview.com/chart'));
    if (!tab) throw new Error('TradingView chart tab tidak ditemukan. Pastikan TradingView sudah jalan dengan --remote-debugging-port=9222');

    client = await CDP({ target: tab.id, port: 9222 });
    await client.Runtime.enable();

    const ev = async (expr) => {
      const r = await client.Runtime.evaluate({ expression: expr, returnByValue: true, timeout: 5000 });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'CDP eval error');
      return r.result?.value;
    };

    const [tables, price] = await Promise.all([ev(READ_EXPR), ev(PRICE_EXPR)]);

    // Parse rows → raw state per TF
    const rawState = {};
    for (const t of (tables || [])) {
      for (const row of (t.rows || [])) {
        const cols = row.split('|').map(s => s.trim());
        if (cols.length < 4) continue;
        const tf = normalizeTF(cols[0]);
        if (!tf) continue;
        rawState[tf] = {
          cmp:    cols[1] || '',
          action: cols[cols.length - 1] || '',
        };
      }
    }

    // Build context vars
    const TF_KEYS = ['DAILY', 'H4', 'H1', 'M30', 'M15', 'M5', 'M1'];
    const ctx = {};

    for (const tf of TF_KEYS) {
      const s = rawState[tf];
      if (!s || !s.cmp) {
        ctx[`${tf}_CMP`] = '';
        ctx[`${tf}_VR`]  = '';
        ctx[`${tf}_CF`]  = '';
      } else {
        const { vr, cf } = actionToVRCF(s.action);
        ctx[`${tf}_CMP`] = cmpToValue(s.cmp);
        ctx[`${tf}_VR`]  = vr;
        ctx[`${tf}_CF`]  = cf;
      }
    }

    ctx['HARGA']   = price || 'N/A';
    ctx['SESSION'] = detectSession();

    await client.close();
    process.stdout.write(JSON.stringify({ success: true, ctx, rawState }));
    process.exit(0);

  } catch (err) {
    if (client) { try { await client.close(); } catch {} }
    process.stdout.write(JSON.stringify({ success: false, error: err.message }));
    process.exit(1);
  }
}

main();
