document.addEventListener('DOMContentLoaded', () => {
    initWallMap();
});

function initWallMap() {
    const wallmapPanel = document.getElementById('wallmap-panel');

    wallmapPanel.innerHTML = `
        <div class="panel-header">
            <span>WALL MAP OVERVIEW</span>
            <div class="flex items-center gap-1 font-mono text-[9px]">
                <button class="bg-crs-darkbg border border-crs-border px-2 py-0.5 rounded text-crs-gray hover:text-white transition">Zoom Out</button>
                <button class="bg-crs-darkbg border border-crs-border px-2 py-0.5 rounded text-crs-gray hover:text-white transition">Zoom In</button>
                <button class="bg-crs-darkbg border border-crs-border px-2 py-0.5 rounded text-crs-gray hover:text-white transition">Center</button>
            </div>
        </div>

        <div class="flex-1 flex flex-col p-1.5 min-h-0 bg-[#05070a] justify-between">
            <!-- Bubble Scatter Canvas -->
            <div class="flex-1 relative w-full min-h-0">
                <canvas id="wallmap-canvas" class="absolute inset-0 w-full h-full"></canvas>
            </div>

            <!-- 7 Summary Stat Cards matching reference -->
            <div class="grid grid-cols-7 gap-1 mt-1 text-center text-xs font-mono">
                <!-- 1. Total Wall (Buy) -->
                <div class="bg-crs-darkbg p-1 rounded border border-crs-green/30">
                    <div class="text-[8px] text-crs-gray font-sans font-semibold">TOTAL WALL (BUY)</div>
                    <div class="text-xs font-black text-crs-green glow-green">28</div>
                    <div class="text-[8px] text-crs-green font-semibold">1,742 LOT</div>
                </div>

                <!-- 2. Total Wall (Sell) -->
                <div class="bg-crs-darkbg p-1 rounded border border-crs-red/30">
                    <div class="text-[8px] text-crs-gray font-sans font-semibold">TOTAL WALL (SELL)</div>
                    <div class="text-xs font-black text-crs-red glow-red">24</div>
                    <div class="text-[8px] text-crs-red font-semibold">1,586 LOT</div>
                </div>

                <!-- 3. LTHL (Buy) -->
                <div class="bg-crs-darkbg p-1 rounded border border-crs-border">
                    <div class="text-[8px] text-crs-gray font-sans font-semibold">LTHL (BUY)</div>
                    <div class="text-xs font-black text-crs-green">14</div>
                    <div class="text-[8px] text-crs-green font-semibold">1,128 LOT</div>
                </div>

                <!-- 4. LTHL (Sell) -->
                <div class="bg-crs-darkbg p-1 rounded border border-crs-border">
                    <div class="text-[8px] text-crs-gray font-sans font-semibold">LTHL (SELL)</div>
                    <div class="text-xs font-black text-crs-red">11</div>
                    <div class="text-[8px] text-crs-red font-semibold">1,032 LOT</div>
                </div>

                <!-- 5. Reinforced -->
                <div class="bg-crs-darkbg p-1 rounded border border-crs-blue/30">
                    <div class="text-[8px] text-crs-gray font-sans font-semibold">REINFORCED</div>
                    <div class="text-xs font-black text-crs-blue glow-blue">8</div>
                    <div class="text-[8px] text-crs-blue font-semibold">942 LOT</div>
                </div>

                <!-- 6. Absorbing -->
                <div class="bg-crs-darkbg p-1 rounded border border-crs-orange/30">
                    <div class="text-[8px] text-crs-gray font-sans font-semibold">ABSORBING</div>
                    <div class="text-xs font-black text-crs-orange">3</div>
                    <div class="text-[8px] text-crs-orange font-semibold">256 LOT</div>
                </div>

                <!-- 7. Removed -->
                <div class="bg-crs-darkbg p-1 rounded border border-crs-border">
                    <div class="text-[8px] text-crs-gray font-sans font-semibold">REMOVED</div>
                    <div class="text-xs font-black text-crs-darkgray">12</div>
                    <div class="text-[8px] text-crs-gray">-</div>
                </div>
            </div>

            <!-- Legend Bar -->
            <div class="flex items-center justify-center gap-5 mt-1 text-[8.5px] text-crs-gray uppercase font-semibold">
                <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-green"></span> BUY WALL</div>
                <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-red"></span> SELL WALL</div>
                <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-blue"></span> REINFORCED</div>
                <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-orange"></span> ABSORBING</div>
                <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-darkgray"></span> REMOVED</div>
            </div>
        </div>
    `;

    const canvas = document.getElementById('wallmap-canvas');
    if (!canvas) return;

    let livePrice = 4090.15;
    let bubbles = [];

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

        const axisY = h * 0.52;
        ctx.strokeStyle = '#182030';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, axisY);
        ctx.lineTo(w, axisY);
        ctx.stroke();

        // Dynamic Price Bounds
        const minP = livePrice - 50;
        const maxP = livePrice + 50;
        const prices = [];
        for (let i = 0; i <= 8; i++) {
            prices.push(minP + (maxP - minP) * (i / 8));
        }

        ctx.font = '9px "JetBrains Mono"';
        ctx.fillStyle = '#8292b0';
        prices.forEach((p, idx) => {
            const px = (w / (prices.length - 1)) * idx;
            ctx.fillText(p.toFixed(1), px > w - 28 ? w - 28 : px, h - 3);
        });

        // Scatter Bubbles
        bubbles.forEach(b => {
            const bx = w * b.xPct;
            const by = h * b.yPct;
            ctx.beginPath();
            ctx.arc(bx, by, b.size, 0, Math.PI * 2);
            ctx.fillStyle = b.color + '66';
            ctx.strokeStyle = b.color;
            ctx.lineWidth = 1.5;
            ctx.shadowColor = b.color;
            ctx.shadowBlur = 8;
            ctx.fill();
            ctx.stroke();
            ctx.shadowBlur = 0;
        });

        // Current Price Marker Badge
        const priceX = w * ((livePrice - minP) / (maxP - minP));
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(priceX - 25, 4, 50, 15);
        ctx.fillStyle = '#05070a';
        ctx.font = 'bold 9px "JetBrains Mono"';
        ctx.fillText(livePrice.toFixed(2), priceX - 20, 15);

        ctx.strokeStyle = '#ffffff';
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(priceX, 19);
        ctx.lineTo(priceX, axisY);
        ctx.stroke();
        ctx.setLineDash([]);
    }

    window.addEventListener('resize', renderCanvas);
    setTimeout(renderCanvas, 50);

    window.addEventListener('crs-update', (e) => {
        const data = e.detail;
        if (!data) return;
        
        if (data.current_price) livePrice = data.current_price;
        
        if (data.wall_ladder) {
            const minP = livePrice - 50;
            const maxP = livePrice + 50;
            
            bubbles = [];
            const asks = data.wall_ladder.asks || [];
            const bids = data.wall_ladder.bids || [];
            
            // Map asks
            asks.forEach(ask => {
                const p = ask[0]; const s = ask[1];
                if (p >= minP && p <= maxP) {
                    const xPct = (p - minP) / (maxP - minP);
                    const size = Math.min(25, Math.max(5, s / 10)); // Scale size by lot volume
                    // Place randomly on y-axis for scatter effect
                    const yPct = 0.2 + (Math.random() * 0.6);
                    bubbles.push({ xPct, yPct, size, color: '#ff0055' });
                }
            });
            // Map bids
            bids.forEach(bid => {
                const p = bid[0]; const s = bid[1];
                if (p >= minP && p <= maxP) {
                    const xPct = (p - minP) / (maxP - minP);
                    const size = Math.min(25, Math.max(5, s / 10)); // Scale size by lot volume
                    const yPct = 0.2 + (Math.random() * 0.6);
                    bubbles.push({ xPct, yPct, size, color: '#00ff88' });
                }
            });
        }
        renderCanvas();
    });
}
