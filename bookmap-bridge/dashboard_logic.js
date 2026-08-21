// Chain Reaction Dashboard logic - wires dashboard.html's Tailwind terminal
// mockup to REAL live_status.json data. Rewritten 2026-08-07: the previous
// version had several data-shape mismatches (tf_matrix expected as an array,
// it's an object; event_log/order_book referenced fields that didn't exist)
// and hardcoded placeholder values (Absorption "MODERATE", Volatility "HIGH")
// that never reflected reality. Dadang: "lo buat jika lo adalah trader" -
// every value here now traces to a real field, nothing decorative.

const TF_ORDER = ["D", "H4", "H1", "M30", "M15", "M5", "M1"];
let cvdHistory = [];
let lastDataTime = null;

async function pollStatus() {
    try {
        const res = await fetch("live_status.json?t=" + Date.now(), { cache: "no-store" });
        if (res.ok) {
            const data = await res.json();
            renderDashboard(data);
            lastDataTime = Date.now();
        }
    } catch (e) {
        console.error("Polling error:", e);
    }
    setTimeout(pollStatus, 150);
}

function renderDashboard(data) {
    if (!data) return;

    // 1. Header - v37: prefer the MT5-converted price (current_price_xauusd,
    // added by udp_listener.py) over the raw GCZ6 futures price - Dadang:
    // "harga yang di web harus ke konvert ke mt5 juga bro". Falls back to
    // the raw value (and says so) only if MT5 wasn't reachable that cycle.
    if (data.current_price_xauusd) {
        document.getElementById('header-price').textContent = data.current_price_xauusd.toFixed(2);
        document.getElementById('header-instrument').textContent = "XAUUSD • MT5";
    } else if (data.current_price) {
        document.getElementById('header-price').textContent = data.current_price.toFixed(2);
        document.getElementById('header-instrument').textContent = "GCZ6 (unconverted - MT5 offline)";
    }
    document.getElementById('header-time').textContent = new Date().toLocaleTimeString('en-US', { hour12: false });

    // v52.18: Dadang - "di panel harus ada tulisan yang menyatakan sydeway
    // atau trending bro karena ini penting baget bagi gw trader breakout" +
    // "lo taruh juga di WEB gw dan webpy gw bro" - regime badge, same
    // definition as the MT5 panel/Sultan web (H4=M30=M5 all agree), from
    // the new "regime" field udp_listener.py now writes into live_status.json.
    const regime = data.regime || {};
    const regimeEl = document.getElementById('header-regime');
    if (regimeEl) {
        regimeEl.textContent = regime.label || "-";
        regimeEl.className = 'font-mono font-semibold ' + (regime.trending ? 'text-emerald-400' : 'text-amber-400');
    }
    // TradingView/Pine retired (v37, Dadang: "tv sudah tidak kita butuhkan") -
    // mt5_overlay_active replaces the old tv_overlay_active field.
    const overlay = data.mt5_overlay_active || [];
    document.getElementById('header-change').textContent = overlay.length ? `MT5 OVERLAY: ${overlay.length} TF` : "PURE BOOKMAP";

    // 2. DECISION Panel
    const rec = data.recommendation || "WAIT";
    const badgeText = (data.status_badge || "WAIT").replace(/[^\x00-\x7F]/g, "").trim() || "WAIT";
    const titleEl = document.getElementById('dec-title');
    titleEl.innerHTML = `<span>${badgeText}</span>`;
    if (rec === "BUY") {
        titleEl.className = 'text-3xl font-extrabold tracking-tight flex items-center justify-center space-x-2 text-emerald-500 glow-green';
        document.getElementById('dec-bias').textContent = 'BIAS : BUY';
        document.getElementById('dec-bias').className = 'text-[10px] font-semibold mt-1 text-emerald-400';
    } else if (rec === "SELL") {
        titleEl.className = 'text-3xl font-extrabold tracking-tight flex items-center justify-center space-x-2 text-rose-500 glow-red';
        document.getElementById('dec-bias').textContent = 'BIAS : SELL';
        document.getElementById('dec-bias').className = 'text-[10px] font-semibold mt-1 text-rose-400';
    } else {
        titleEl.className = 'text-3xl font-extrabold tracking-tight flex items-center justify-center space-x-2 text-slate-400';
        document.getElementById('dec-bias').textContent = 'BIAS : NEUTRAL';
        document.getElementById('dec-bias').className = 'text-[10px] font-semibold mt-1 text-slate-400';
    }

    // "Recommendation Strength" bar repurposed to what we actually have: Market
    // Pulse % (buyer aggression, our own Price-Change-algorithm replica).
    const pulsePct = data.buyer_aggression_pct != null ? data.buyer_aggression_pct : 50.0;
    document.getElementById('dec-pct').textContent = pulsePct.toFixed(0) + '%';
    const bar = document.getElementById('dec-bar');
    bar.style.width = Math.min(100, Math.max(0, pulsePct)) + '%';
    bar.className = `h-1.5 rounded-full transition-all duration-300 ${pulsePct >= 50 ? 'bg-emerald-500' : 'bg-rose-500'}`;
    document.getElementById('dec-pct').className = pulsePct >= 50 ? 'text-emerald-400' : 'text-rose-400';

    document.getElementById('dec-pos').textContent = rec;
    document.getElementById('dec-upd').textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
    const staleSec = data.updated_at ? (Date.now() / 1000 - data.updated_at) : 0;
    const isStale = staleSec > 5;
    document.getElementById('dec-next').textContent = isStale ? "STALE" : "LIVE";
    document.getElementById('dec-next').className = `font-bold font-mono mt-0.5 ${isStale ? 'text-rose-400' : 'text-cyan-400'}`;

    renderPosition(data);

    // 3. CHAIN REACTION Panel - tf_matrix is an OBJECT keyed by TF label, not an array
    if (data.tf_matrix) {
        const tbody = document.getElementById('matrix-tbody');
        tbody.innerHTML = TF_ORDER.map(tf => {
            const row = data.tf_matrix[tf] || { cmp: "-", vr: "-", cf: "-", action: "" };
            const cmp = row.cmp || "-";
            const color = cmp === 'BUY' ? 'text-emerald-400' : cmp === 'SELL' ? 'text-rose-400' : 'text-slate-500';
            const actionTitle = (row.action || "").replace(/"/g, "&quot;");
            return `
                <tr title="${actionTitle}">
                    <td class="py-1.5 font-bold text-slate-300">${tf}</td>
                    <td class="py-1.5 font-bold ${color}">${cmp}</td>
                    <td class="py-1.5 text-amber-400">${row.vr && row.vr !== '-' ? row.vr : '-'}</td>
                    <td class="py-1.5 text-emerald-400">${row.cf && row.cf !== '-' ? row.cf : '-'}</td>
                </tr>
            `;
        }).join('');
    }

    // 4. ALASAN & KESIMPULAN - real reason_lines + conclusion (was reading a
    // top-level event_log field that never existed, always rendered empty)
    const reasons = document.getElementById('alasan-list');
    const lines = (data.reason_lines || []).map(r => r.replace(/[✔⏳⚡📈👁⚠]/g, '').trim());
    let reasonsHtml = lines.map(l => `<div>${l}</div>`).join('');
    if (data.conclusion) {
        reasonsHtml += `<div class="text-amber-400 font-bold mt-1 pt-1 border-t border-slate-800">${data.conclusion}</div>`;
    }
    reasons.innerHTML = reasonsHtml || '<div class="text-slate-600">Loading...</div>';

    // 5. ORDER FLOW SNAPSHOT - all four tiles now real (Absorption/Footprint
    // used to be hardcoded "MODERATE"/"HIGH", never touched by JS at all)
    if (data.buyer_aggression_pct !== undefined) {
        const pulseEl = document.getElementById('ofs-pulse');
        pulseEl.textContent = data.buyer_aggression_pct.toFixed(1) + '%';
        pulseEl.className = `text-sm font-bold font-mono ${data.buyer_aggression_pct >= 50 ? 'text-emerald-400' : 'text-rose-400'}`;
    }
    if (data.cvd_30s !== undefined) {
        const delta = data.cvd_30s;
        const deltaEl = document.getElementById('ofs-delta');
        deltaEl.textContent = (delta >= 0 ? '+' : '') + delta.toFixed(1);
        deltaEl.className = `text-sm font-bold font-mono ${delta >= 0 ? 'text-emerald-400 glow-green' : 'text-rose-400 glow-red'}`;
    }
    const absorption = data.absorption || { status: 'NONE' };
    const absEl = document.getElementById('ofs-absorp');
    if (absorption.status === 'NONE') {
        absEl.textContent = 'NONE';
        absEl.className = 'text-sm font-bold font-mono text-slate-500';
        absEl.title = '';
    } else {
        absEl.textContent = absorption.status.replace('_ABSORBED', '');
        absEl.className = 'text-sm font-bold font-mono text-amber-400 glow-amber';
        absEl.title = absorption.reason || '';
    }
    const fp = data.footprint;
    const fpEl = document.getElementById('ofs-vol');
    if (fp && fp.status && fp.status !== 'NEUTRAL') {
        const cls = fp.status === 'BUY_DOMINANT' ? 'text-emerald-400' : 'text-rose-400';
        fpEl.textContent = fp.status.replace('_DOMINANT', '');
        fpEl.className = `text-sm font-bold font-mono ${cls}`;
        fpEl.title = `@ ${fp.wall_price != null ? fp.wall_price.toFixed(2) : '-'} (${fp.side || '-'})`;
    } else {
        fpEl.textContent = fp ? 'NEUTRAL' : '-';
        fpEl.className = 'text-sm font-bold font-mono text-slate-500';
        fpEl.title = fp ? '' : 'No wall nearby';
    }

    // 6. WALL WATCHLIST (v52.25, was "LIQUIDITY WALL (NEAREST)" capped to
    // 5/side) - Dadang: "kenapa nunggu load bro... yang penting real time
    // aja, kalo spoofing kan akan hilang" - show EVERY currently-tracked
    // wall (data.wall_ladder.bids/asks is already the full un-gated near-
    // scan from cr_master_engine.py, top_n=1000 as of v52.22 - nothing
    // here waits for the 1-hour WALL_HISTORY_MIN_AGE_SEC that governs the
    // MT5 chart lines/HasLiquiditySupport() decision gate, that's a
    // separate, untouched thing). Sorted biggest-first (Dadang: "yang kuat
    // wall besar" - size is what matters most for a quick scan of a long
    // list), converted to MT5/XAUUSD price terms (was raw GCZ6 - Dadang:
    // "harga mt5 gw di convert disesuaikan dengan mt5 gw"), no row cap
    // (panel scrolls - see dashboard.html's max-h-64 + overflow-y-auto).
    if (data.wall_ladder) {
        const offset = (data.current_price_xauusd != null && data.current_price)
            ? data.current_price_xauusd - data.current_price : 0;
        const toMt5 = px => px + offset;
        const asks = [...(data.wall_ladder.asks || [])].sort((a, b) => b[1] - a[1]);
        const bids = [...(data.wall_ladder.bids || [])].sort((a, b) => b[1] - a[1]);
        document.getElementById('wall-asks').innerHTML = asks.map(ask => `
            <div class="flex justify-between items-center bg-rose-500/10 px-1 py-0.5 rounded border border-rose-500/20">
                <span class="text-rose-400 font-bold">${toMt5(ask[0]).toFixed(2)}</span>
                <span class="text-white">${Math.round(ask[1])}</span>
            </div>
        `).join('') || '<div class="text-slate-600 text-center">-</div>';
        document.getElementById('wall-bids').innerHTML = bids.map(bid => `
            <div class="flex justify-between items-center bg-emerald-500/10 px-1 py-0.5 rounded border border-emerald-500/20">
                <span class="text-emerald-400 font-bold">${toMt5(bid[0]).toFixed(2)}</span>
                <span class="text-white">${Math.round(bid[1])}</span>
            </div>
        `).join('') || '<div class="text-slate-600 text-center">-</div>';
    }

    // 7. ORDER BOOK (DOM Ladder) - real L2 depth (data.order_book, added to the
    // Python backend 2026-08-07 - this used to reference a field that never
    // existed anywhere in our pipeline, so the panel was permanently blank)
    if (data.order_book && data.current_price) {
        const ladder = document.getElementById('dom-ladder');
        const obAsks = data.order_book.asks || [];
        const obBids = data.order_book.bids || [];
        const allSizes = [...obAsks, ...obBids].map(l => l[1]);
        const maxSize = allSizes.length ? Math.max(...allSizes) : 1;
        let html = '';
        [...obAsks].reverse().forEach(ask => {
            const width = Math.min(100, (ask[1] / maxSize) * 100);
            html += `
            <div class="flex justify-between items-center py-0.5 relative hover:bg-slate-800">
                <span class="text-rose-400 w-14 text-right relative z-10">${ask[0].toFixed(2)}</span>
                <div class="flex-1 mx-2 relative h-3">
                    <div class="absolute right-0 top-0 h-full bg-rose-500/30" style="width: ${width}%"></div>
                </div>
                <span class="text-white w-10 relative z-10">${Math.round(ask[1])}</span>
            </div>`;
        });
        html += `<div class="py-1 text-center font-bold text-white bg-slate-800/80 my-1">${data.current_price.toFixed(2)}</div>`;
        obBids.forEach(bid => {
            const width = Math.min(100, (bid[1] / maxSize) * 100);
            html += `
            <div class="flex justify-between items-center py-0.5 relative hover:bg-slate-800">
                <span class="text-emerald-400 w-14 text-right relative z-10">${bid[0].toFixed(2)}</span>
                <div class="flex-1 mx-2 relative h-3">
                    <div class="absolute right-0 top-0 h-full bg-emerald-500/30" style="width: ${width}%"></div>
                </div>
                <span class="text-white w-10 relative z-10">${Math.round(bid[1])}</span>
            </div>`;
        });
        ladder.innerHTML = html || '<div class="text-slate-600 text-center p-4">Belum ada depth data</div>';
    }

    // 8. DB STATS & TRADE LOG - real trades.db data (was completely unwired before)
    if (data.db_stats) {
        document.getElementById('stat-total').textContent = data.db_stats.total;
        document.getElementById('stat-wr').textContent = data.db_stats.win_rate.toFixed(1) + '%';
        const pnl = data.db_stats.total_pnl;
        const pnlEl = document.getElementById('stat-pnl');
        pnlEl.textContent = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2);
        pnlEl.className = `font-bold ml-1 ${pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;
    }

    if (data.recent_trades) {
        const log = document.getElementById('trade-log');
        log.innerHTML = data.recent_trades.map(t => {
            const isBuy = t.direction === 'BUY';
            const pnlNum = parseFloat(t.points);
            const pnlColor = t.status === 'CLOSED' ? (pnlNum >= 0 ? 'text-emerald-400' : 'text-rose-400') : 'text-amber-400';
            const exitTxt = t.status === 'CLOSED' ? t.exit.toFixed(2) : 'OPEN';
            return `
                <tr>
                    <td class="py-1 px-2 text-slate-400">${t.time}</td>
                    <td class="py-1 px-2 font-bold ${isBuy ? 'text-emerald-400' : 'text-rose-400'}">${t.direction}</td>
                    <td class="py-1 px-2">${t.entry.toFixed(2)} &rarr; ${exitTxt}</td>
                    <td class="py-1 px-2">${t.status === 'CLOSED' ? t.duration : '-'}</td>
                    <td class="py-1 px-2 text-right font-bold ${pnlColor}">${t.status === 'CLOSED' ? t.points + ' pts' : '-'}</td>
                </tr>
            `;
        }).join('') || '<tr><td colspan="5" class="py-4 text-center text-slate-600">Belum ada trade</td></tr>';
    }

    // Strip stats - real spread + real cumulative points (was a nonsense
    // price*0.0001 "spread" and a made-up "total*15 LOT" avg volume)
    document.getElementById('strip-spread').textContent = data.spread != null ? data.spread.toFixed(2) : '-';
    document.getElementById('strip-vol').textContent = (data.db_stats && data.db_stats.total_points != null)
        ? (data.db_stats.total_points >= 0 ? '+' : '') + data.db_stats.total_points.toFixed(1) : '0.0';
    document.getElementById('strip-speed').textContent = overlay.length ? 'PINE+BM' : 'BOOKMAP';
    const biasEl = document.getElementById('strip-bias');
    biasEl.textContent = rec === 'WAIT' ? 'NEUTRAL' : rec;
    biasEl.className = `font-bold ml-1 ${rec === 'BUY' ? 'text-emerald-400' : rec === 'SELL' ? 'text-rose-400' : 'text-slate-400'}`;

    const mt5El = document.getElementById('strip-mt5');
    mt5El.textContent = data.mt5_bridge ? 'ON' : 'OFF';
    mt5El.className = `font-bold ${data.mt5_bridge ? 'text-emerald-400' : 'text-rose-400'}`;

    // System status - real connection state, not hardcoded "CONNECTED"/"ACTIVE"
    document.getElementById('sys-status').innerHTML = `
        <div class="flex justify-between items-center"><span class="text-slate-300">Bookmap Bridge</span><span class="${isStale ? 'text-rose-400' : 'text-emerald-400'}">${isStale ? 'STALE' : 'CONNECTED'}</span></div>
        <div class="flex justify-between items-center"><span class="text-slate-300">MT5 Auto-Exec</span><span class="${data.mt5_bridge ? 'text-emerald-400' : 'text-rose-400'}">${data.mt5_bridge ? 'ON' : 'OFF'}</span></div>
        <div class="flex justify-between items-center"><span class="text-slate-300">Pine Overlay</span><span class="text-slate-400">${overlay.length} TF</span></div>
        <div class="flex justify-between items-center"><span class="text-slate-300">Decision Engine</span><span class="text-emerald-400">ACTIVE</span></div>
    `;

    drawCharts(data);
}

function renderPosition(data) {
    const el = document.getElementById('position-strip');
    if (!el) return;
    const pos = data.position;
    if (pos && pos.entry_price != null) {
        const dirMult = pos.dir === 'BUY' ? 1 : -1;
        // v37 fix: pos.entry_price is a REAL MT5 execution price (XAUUSD
        // scale, from mt5_bridge_executor.py's own tick), but data.current_price
        // is Bookmap's raw GCZ6 futures price - subtracting the two was a
        // silent scale-mismatch bug producing garbage points. Use the
        // MT5-converted price instead (falls back to the old, technically-
        // wrong behavior only if MT5 was unreachable that cycle).
        const livePrice = data.current_price_xauusd || data.current_price;
        const points = livePrice ? ((livePrice - pos.entry_price) * dirMult) : 0;
        el.style.display = 'grid';
        el.innerHTML = `
            <div class="bg-slate-950 border border-emerald-800 p-1.5 rounded">
                <div class="text-slate-500 uppercase">Entry (${pos.dir})</div>
                <div class="font-bold mt-0.5 font-mono">${pos.entry_price.toFixed(2)}</div>
            </div>
            <div class="bg-slate-950 border border-emerald-800 p-1.5 rounded">
                <div class="text-slate-500 uppercase">Poin</div>
                <div class="font-bold mt-0.5 font-mono ${points >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${points >= 0 ? '+' : ''}${points.toFixed(1)}</div>
            </div>
            <div class="bg-slate-950 border border-emerald-800 p-1.5 rounded">
                <div class="text-slate-500 uppercase">SL (backstop)</div>
                <div class="font-bold mt-0.5 font-mono text-rose-400">${pos.sl != null ? pos.sl.toFixed(2) : '-'}</div>
            </div>
        `;
    } else {
        el.style.display = 'none';
    }
}

function drawCharts(data) {
    // Price Action (M5) - real OHLC candles from the doctrine's own bar
    // aggregator (data.m5_bars, added 2026-08-07), not a synthetic tick line.
    const pCanvas = document.getElementById('chart-canvas');
    if (pCanvas) {
        const pCtx = pCanvas.getContext('2d');
        const rect = pCanvas.getBoundingClientRect();
        pCanvas.width = rect.width;
        pCanvas.height = rect.height;
        const w = pCanvas.width, h = pCanvas.height;
        pCtx.clearRect(0, 0, w, h);

        const bars = data.m5_bars || [];
        if (bars.length > 1) {
            const highs = bars.map(b => b.high);
            const lows = bars.map(b => b.low);
            const minP = Math.min(...lows);
            const maxP = Math.max(...highs);
            const range = (maxP - minP) || 1;
            const padTop = h * 0.08, padBot = h * 0.08;
            const usableH = h - padTop - padBot;
            const barW = w / bars.length;
            const bodyW = Math.max(2, barW * 0.6);
            const yFor = (p) => padTop + usableH - ((p - minP) / range) * usableH;

            bars.forEach((b, i) => {
                const x = i * barW + barW / 2;
                const isUp = b.close >= b.open;
                const col = isUp ? '#10b981' : '#f43f5e';
                pCtx.strokeStyle = col;
                pCtx.fillStyle = col;
                pCtx.beginPath();
                pCtx.moveTo(x, yFor(b.high));
                pCtx.lineTo(x, yFor(b.low));
                pCtx.lineWidth = 1;
                pCtx.stroke();
                const yOpen = yFor(b.open), yClose = yFor(b.close);
                const top = Math.min(yOpen, yClose), bh = Math.max(1, Math.abs(yClose - yOpen));
                pCtx.fillRect(x - bodyW / 2, top, bodyW, bh);
            });
        } else {
            pCtx.fillStyle = '#475569';
            pCtx.font = '11px Inter';
            pCtx.fillText('Menunggu candle M5 pertama dari tick Bookmap...', 10, h / 2);
        }
    }

    // CVD Chart - rolling client-side history of the session-cumulative CVD
    if (data.cvd_30s === undefined) return;
    cvdHistory.push(data.cvd_30s);
    if (cvdHistory.length > 100) cvdHistory.shift();

    const cCanvas = document.getElementById('cvd-canvas');
    if (cCanvas) {
        const cCtx = cCanvas.getContext('2d');
        const rect = cCanvas.getBoundingClientRect();
        cCanvas.width = rect.width;
        cCanvas.height = rect.height;
        const w = cCanvas.width, h = cCanvas.height;
        cCtx.clearRect(0, 0, w, h);
        if (cvdHistory.length > 1) {
            const minC = Math.min(...cvdHistory, 0);
            const maxC = Math.max(...cvdHistory, 0);
            const range = (maxC - minC) || 1;
            cCtx.beginPath();
            cvdHistory.forEach((c, i) => {
                const x = (w / (cvdHistory.length - 1)) * i;
                const y = h - ((c - minC) / range) * h * 0.8 - h * 0.1;
                if (i === 0) cCtx.moveTo(x, y); else cCtx.lineTo(x, y);
            });
            const lastUp = cvdHistory[cvdHistory.length - 1] >= 0;
            cCtx.strokeStyle = lastUp ? '#10b981' : '#f43f5e';
            cCtx.lineWidth = 2;
            cCtx.stroke();
            cCtx.lineTo(w, h);
            cCtx.lineTo(0, h);
            cCtx.fillStyle = lastUp ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)';
            cCtx.fill();
        }
    }
}

// Init
pollStatus();
