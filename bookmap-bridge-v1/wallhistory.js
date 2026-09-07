document.addEventListener('DOMContentLoaded', () => {
    initWallHistory();
});

function initWallHistory() {
    const wallhistoryPanel = document.getElementById('wallhistory-panel');

    function renderPanel() {
        const wall = window.CRS_CONFIG.state.selectedWall;
        const isBuy = wall.side === 'BUY';
        const priceColor = isBuy ? 'text-crs-green glow-green' : 'text-crs-red glow-red';

        wallhistoryPanel.innerHTML = `
            <div class="panel-header">
                <span>WALL HISTORY - <span class="${priceColor}">${wall.price.toFixed(1)} (${wall.side} LIMIT)</span></span>
                <div class="flex items-center gap-1 text-[9px] font-mono" id="tf-btn-group">
                    ${['1H', '6H', '1D', '3D', '1W', 'ALL'].map(tf => `
                        <button data-tf="${tf}" class="${tf === wall.timeframe ? 'bg-crs-gold/20 text-crs-gold border border-crs-gold/40 px-1.5 py-0.5 rounded font-bold shadow-glow-gold' : 'bg-crs-darkbg border border-crs-border px-1.5 py-0.5 rounded text-crs-gray hover:text-white transition'}">${tf}</button>
                    `).join('')}
                </div>
            </div>

            <div class="p-2 flex-1 flex flex-col justify-between min-h-0 bg-[#05070a]">
                <!-- Top Stat Counters -->
                <div class="grid grid-cols-5 gap-1 text-[9px] font-mono border-b border-crs-border/60 pb-1.5">
                    <div>
                        <div class="text-[8px] text-crs-gray font-sans font-semibold">FIRST SEEN</div>
                        <div class="text-white font-bold">${wall.firstSeen}</div>
                    </div>
                    <div>
                        <div class="text-[8px] text-crs-gray font-sans font-semibold">HIGHEST SIZE</div>
                        <div class="text-crs-gold font-bold glow-gold">${wall.highestSize} LOT</div>
                    </div>
                    <div>
                        <div class="text-[8px] text-crs-gray font-sans font-semibold">LOWEST SIZE</div>
                        <div class="text-white font-bold">${wall.lowestSize} LOT</div>
                    </div>
                    <div>
                        <div class="text-[8px] text-crs-gray font-sans font-semibold">MAX AGE</div>
                        <div class="text-crs-gold font-bold glow-gold">${wall.maxAge}</div>
                    </div>
                    <div>
                        <div class="text-[8px] text-crs-gray font-sans font-semibold">TYPE</div>
                        <div class="${wall.type === 'STHL' ? 'text-crs-red font-bold' : 'text-crs-blue font-bold'}">${wall.type}</div>
                    </div>
                </div>

                <!-- Canvas Area Chart -->
                <div class="flex-1 relative w-full min-h-0 mt-1">
                    <canvas id="wallhistory-canvas" class="absolute inset-0 w-full h-full"></canvas>
                </div>

                <!-- Legend Bar -->
                <div class="flex items-center justify-center gap-6 mt-1 text-[8.5px] text-crs-gray font-semibold">
                    <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-red"></span> Size (Lot)</div>
                    <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-blue"></span> Reinforcement</div>
                </div>
            </div>
        `;

        setupCanvasChart();
        setupTimeframeListeners();
    }

    function setupTimeframeListeners() {
        const group = document.getElementById('tf-btn-group');
        if (!group) return;
        group.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', () => {
                window.CRS_CONFIG.state.selectedWall.timeframe = btn.dataset.tf;
                renderPanel();
            });
        });
    }

    function setupCanvasChart() {
        const canvas = document.getElementById('wallhistory-canvas');
        if (!canvas) return;

        function drawWallHistory() {
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

            const chartBottom = h - 14;
            const chartW = w - 24;
            const wall = window.CRS_CONFIG.state.selectedWall;
            const isBuy = wall.side === 'BUY';
            const themeColor = isBuy ? '#00ff88' : '#ff0055';

            // Grid Lines
            const yTicks = [200, 150, 100, 50, 0];
            ctx.font = '8.5px "JetBrains Mono"';
            ctx.fillStyle = '#8292b0';
            yTicks.forEach((tick, idx) => {
                const y = (chartBottom / (yTicks.length - 1)) * idx + 4;
                ctx.fillText(tick.toString(), w - 20, y + 3);

                ctx.strokeStyle = '#182030';
                ctx.lineWidth = 0.5;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(chartW, y);
                ctx.stroke();
            });

            // Dynamic Area Plot
            const points = [];
            const numPts = 32;
            const seed = wall.price * 10;
            for (let i = 0; i < numPts; i++) {
                const px = (chartW / (numPts - 1)) * i;
                const py = chartBottom - (Math.sin(i * 0.4 + seed) * 28 + Math.cos(i * 0.2) * 16 + 35);
                points.push({ x: px, y: py });
            }

            const areaGrad = ctx.createLinearGradient(0, 0, 0, chartBottom);
            areaGrad.addColorStop(0, isBuy ? 'rgba(0, 255, 136, 0.45)' : 'rgba(255, 0, 85, 0.45)');
            areaGrad.addColorStop(1, 'rgba(0, 0, 0, 0.02)');

            ctx.beginPath();
            ctx.moveTo(0, chartBottom);
            points.forEach(p => ctx.lineTo(p.x, p.y));
            ctx.lineTo(chartW, chartBottom);
            ctx.closePath();
            ctx.fillStyle = areaGrad;
            ctx.fill();

            ctx.beginPath();
            points.forEach((p, idx) => {
                if (idx === 0) ctx.moveTo(p.x, p.y);
                else ctx.lineTo(p.x, p.y);
            });
            ctx.strokeStyle = themeColor;
            ctx.lineWidth = 1.5;
            ctx.shadowColor = themeColor;
            ctx.shadowBlur = 6;
            ctx.stroke();
            ctx.shadowBlur = 0;

            // Reinforcement Line
            ctx.beginPath();
            points.forEach((p, idx) => {
                const ry = p.y + 8;
                if (idx === 0) ctx.moveTo(p.x, ry);
                else ctx.lineTo(p.x, ry);
            });
            ctx.strokeStyle = '#00d9ff';
            ctx.lineWidth = 1;
            ctx.stroke();

            // Timestamps
            const times = ['20:00', '20:30', '21:00', '21:30', '22:00', '22:30', '23:00', '23:30', '00:00'];
            ctx.fillStyle = '#8292b0';
            times.forEach((t, idx) => {
                const tx = (chartW / (times.length - 1)) * idx;
                ctx.fillText(t, tx, h - 2);
            });
        }

        window.addEventListener('resize', drawWallHistory);
        setTimeout(drawWallHistory, 50);

        window.addEventListener('crs-update', drawWallHistory);
    }

    renderPanel();

    window.addEventListener('crs-wall-selected', () => {
        renderPanel();
    });
}
