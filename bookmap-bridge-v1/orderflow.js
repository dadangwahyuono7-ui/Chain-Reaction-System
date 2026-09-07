document.addEventListener('DOMContentLoaded', () => {
    initOrderFlow();
});

function initOrderFlow() {
    const orderflowPanel = document.getElementById('orderflow-panel');

    orderflowPanel.innerHTML = `
        <div class="panel-header">
            <span>GC - ORDER FLOW (BOOKMAP STYLE)</span>
            <div class="flex items-center gap-1.5 text-xs">
                <select class="terminal-input text-[9px] py-0 font-sans font-semibold">
                    <option>BOOKMAP VIEW ˅</option>
                    <option>CANDLESTICK VIEW</option>
                </select>
                <div class="flex items-center gap-1 text-crs-gray font-mono text-[10px]">
                    <button class="px-1 hover:text-white hover:bg-crs-border rounded transition">+</button>
                    <button class="px-1 hover:text-white hover:bg-crs-border rounded transition">-</button>
                    <button class="px-1 hover:text-white hover:bg-crs-border rounded transition">🔍</button>
                    <button class="px-1 hover:text-white hover:bg-crs-border rounded transition">📷</button>
                    <button class="px-1 hover:text-white hover:bg-crs-border rounded transition">⤢</button>
                </div>
            </div>
        </div>

        <div class="flex-1 relative w-full h-full min-h-0 bg-[#06090e] overflow-hidden">
            <canvas id="bookmap-canvas" class="absolute inset-0 w-full h-full"></canvas>
        </div>
    `;

    const canvas = document.getElementById('bookmap-canvas');
    if (!canvas) return;

    let livePrice = 4090.15;
    let cvdVal = 4128;
    let deltaVal = 14;
    let vwapVal = 4110.6;
    let tickCount = 0;

    const maxCandles = 35;
    const candleList = [];
    let basePrice = 4090.00;

    for (let i = 0; i < maxCandles; i++) {
        const change = (Math.random() - 0.48) * 1.5;
        const open = basePrice;
        const close = basePrice + change;
        const high = Math.max(open, close) + Math.random() * 0.8;
        const low = Math.min(open, close) - Math.random() * 0.8;
        candleList.push({ open, close, high, low, isBull: close >= open, bubble: i % 3 === 0 });
        basePrice = close;
    }

    let obAsks = [];
    let obBids = [];

    function renderCanvas() {
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;

        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;

        ctx.clearRect(0, 0, w, h);

        const chartRightMargin = 60;
        const subChartH = 28;
        const mainH = h - (subChartH * 3) - 16;
        const chartW = w - chartRightMargin;

        // 1. Draw Glowing Heatmap Bands
        const heatGrad = ctx.createLinearGradient(0, 0, 0, mainH);
        heatGrad.addColorStop(0, '#06090e');
        heatGrad.addColorStop(0.15, 'rgba(255, 23, 68, 0.35)');
        heatGrad.addColorStop(0.32, 'rgba(255, 107, 0, 0.55)');
        heatGrad.addColorStop(0.48, 'rgba(255, 215, 0, 0.7)');
        heatGrad.addColorStop(0.65, 'rgba(41, 182, 246, 0.35)');
        heatGrad.addColorStop(0.85, 'rgba(0, 230, 118, 0.35)');
        heatGrad.addColorStop(1, '#06090e');

        ctx.fillStyle = heatGrad;
        ctx.fillRect(0, 0, chartW, mainH);

        // Heat Lines
        const heatLines = [
            { y: mainH * 0.22, color: '#ff1744', blur: 10 },
            { y: mainH * 0.42, color: '#ffd700', blur: 14 },
            { y: mainH * 0.72, color: '#00e676', blur: 10 }
        ];

        heatLines.forEach(hl => {
            ctx.fillStyle = hl.color;
            ctx.shadowColor = hl.color;
            ctx.shadowBlur = hl.blur;
            ctx.fillRect(0, hl.y, chartW, 2);
            ctx.shadowBlur = 0;
        });

        // 2. Draw Candlesticks & Bubbles
        const candleStep = chartW / maxCandles;
        const candleW = candleStep * 0.55;
        const minP = livePrice - 20;
        const maxP = livePrice + 20;

        function pToY(price) {
            return mainH - ((price - minP) / (maxP - minP)) * mainH;
        }

        // 3. Right Y-Axis Price Scale & Depth Profile Histogram (ASKS / BIDS)
        ctx.fillStyle = '#0b0e14';
        ctx.fillRect(chartW, 0, chartRightMargin, h);
        ctx.strokeStyle = '#1a2333';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(chartW, 0);
        ctx.lineTo(chartW, h);
        ctx.stroke();

        ctx.font = '9px "Space Grotesk"';
        ctx.fillStyle = '#8a99b5';
        
        // Header labels ASKS / BIDS
        ctx.fillStyle = '#ff1744';
        ctx.font = 'bold 8px sans-serif';
        ctx.fillText('ASKS', chartW + 36, 10);
        ctx.fillStyle = '#00e676';
        ctx.fillText('BIDS', chartW + 36, mainH - 5);

        ctx.font = '9px "Space Grotesk"';
        ctx.fillStyle = '#8a99b5';

        // Render Asks
        obAsks.slice(0, 4).forEach((ask, idx) => {
            const p = ask[0]; const s = ask[1];
            const py = pToY(p);
            ctx.fillText(p.toFixed(1), chartW + 2, py);
            const barW = Math.min(24, (s/200)*24);
            ctx.fillStyle = 'rgba(255, 23, 68, 0.65)';
            ctx.fillRect(chartW + 36 - barW, py - 6, barW, 5);
        });

        // Render Bids
        obBids.slice(0, 4).forEach((bid, idx) => {
            const p = bid[0]; const s = bid[1];
            const py = pToY(p);
            ctx.fillText(p.toFixed(1), chartW + 2, py);
            const barW = Math.min(24, (s/200)*24);
            ctx.fillStyle = 'rgba(0, 230, 118, 0.65)';
            ctx.fillRect(chartW + 36 - barW, py - 6, barW, 5);
        });

        // Live Current Price Badge
        const liveY = pToY(livePrice);
        ctx.fillStyle = '#ffd700';
        ctx.fillRect(chartW, Math.max(0, Math.min(mainH - 14, liveY - 7)), chartRightMargin, 14);
        ctx.fillStyle = '#06090e';
        ctx.font = 'bold 9px "Space Grotesk"';
        ctx.fillText(livePrice.toFixed(2), chartW + 6, Math.max(10, Math.min(mainH - 3, liveY + 3)));

        // 4. Sub-Charts (Delta, CVD, VWAP)
        const subY1 = mainH + 2;
        const subY2 = subY1 + subChartH;
        const subY3 = subY2 + subChartH;

        [subY1, subY2, subY3].forEach(y => {
            ctx.strokeStyle = '#1a2333';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(chartW, y);
            ctx.stroke();
        });

        // SUB-CHART 1: DELTA
        ctx.font = '8.5px "Inter", sans-serif';
        ctx.fillStyle = '#8a99b5';
        ctx.fillText('DELTA', 6, subY1 + 11);

        ctx.fillStyle = 'rgba(0, 230, 118, 0.15)';
        ctx.fillRect(46, subY1 + 2, 22, 11);
        ctx.fillStyle = deltaVal >= 0 ? '#00e676' : '#ff1744';
        ctx.font = 'bold 8.5px "Space Grotesk"';
        ctx.fillText(deltaVal.toString(), 50, subY1 + 10);

        // SUB-CHART 2: CVD
        ctx.font = '8.5px "Inter", sans-serif';
        ctx.fillStyle = '#8a99b5';
        ctx.fillText('CVD', 6, subY2 + 11);

        ctx.fillStyle = 'rgba(0, 230, 118, 0.15)';
        ctx.fillRect(46, subY2 + 2, 40, 11);
        ctx.fillStyle = cvdVal >= 0 ? '#00e676' : '#ff1744';
        ctx.font = 'bold 8.5px "Space Grotesk"';
        ctx.fillText((cvdVal>=0?'+':'') + cvdVal.toFixed(1), 49, subY2 + 10);

        // SUB-CHART 3: VWAP
        ctx.font = '8.5px "Inter", sans-serif';
        ctx.fillStyle = '#8a99b5';
        ctx.fillText('VWAP', 6, subY3 + 11);

        ctx.fillStyle = 'rgba(41, 182, 246, 0.15)';
        ctx.fillRect(46, subY3 + 2, 40, 11);
        ctx.fillStyle = '#29b6f6';
        ctx.font = 'bold 8.5px "Space Grotesk"';
        ctx.fillText(vwapVal.toFixed(1), 49, subY3 + 10);

        // X-Axis Timestamps
        const timestamps = ['21:30', '21:45', '22:00', '22:15', '22:30', '22:45', '23:00', '23:15', '23:30', '23:45'];
        ctx.fillStyle = '#8a99b5';
        ctx.font = '8.5px "Space Grotesk"';
        timestamps.forEach((t, i) => {
            const tx = (chartW / (timestamps.length - 1)) * i;
            ctx.fillText(t, tx, h - 2);
        });
    }

    window.addEventListener('resize', renderCanvas);
    setTimeout(renderCanvas, 50);

    window.addEventListener('crs-update', (e) => {
        const data = e.detail;
        if (!data) return;
        
        if (data.current_price) livePrice = data.current_price;
        if (data.cvd_30s != null) cvdVal = data.cvd_30s;
        if (data.buyer_aggression_pct != null) deltaVal = Math.round(data.buyer_aggression_pct);
        
        if (data.wall_ladder) {
            obAsks = data.wall_ladder.asks || [];
            obBids = data.wall_ladder.bids || [];
        }

        renderCanvas();
    });
}
