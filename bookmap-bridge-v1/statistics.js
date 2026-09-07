document.addEventListener('DOMContentLoaded', () => {
    initStatistics();
});

function initStatistics() {
    const bottomPanel = document.getElementById('bottom-panel');
    const { stats, author, systemName } = window.CRS_CONFIG.state;

    bottomPanel.innerHTML = `
        <div class="w-full flex items-center justify-between font-mono text-[9px] overflow-hidden whitespace-nowrap">
            <!-- Left Stats Bar matching reference -->
            <div class="flex items-center gap-3">
                <div class="flex items-center gap-1 text-crs-gray border-r border-crs-border pr-2">
                    <span>⚙</span>
                    <span>⇥</span>
                    <span class="font-bold text-white font-sans text-[8.5px] uppercase tracking-wider">SYSTEM STATISTICS</span>
                </div>

                <!-- Total Trades -->
                <div class="flex items-center gap-1">
                    <span class="text-crs-gray">TOTAL TRADES</span>
                    <span class="text-white font-bold" id="stat-total">-</span>
                </div>

                <div class="w-px h-3 bg-crs-border"></div>

                <!-- Wins / Losses -->
                <div class="flex items-center gap-1">
                    <span class="text-crs-gray">W / L</span>
                    <span class="text-white font-bold" id="stat-wl">- / -</span>
                </div>

                <div class="w-px h-3 bg-crs-border"></div>

                <!-- Win Rate -->
                <div class="flex items-center gap-1">
                    <span class="text-crs-gray">WIN RATE</span>
                    <span class="text-white font-bold" id="stat-wr">-%</span>
                </div>

                <div class="w-px h-3 bg-crs-border"></div>

                <!-- Total PNL -->
                <div class="flex items-center gap-1">
                    <span class="text-crs-gray">TOTAL PNL</span>
                    <span class="text-white font-bold" id="stat-pnl">-</span>
                </div>

                <div class="w-px h-3 bg-crs-border"></div>

                <!-- Order Flow Bias -->
                <div class="flex items-center gap-1">
                    <span class="text-crs-gray">ORDER FLOW BIAS</span>
                    <span class="text-crs-green font-bold glow-green uppercase" id="stat-bias">${stats.orderFlowBias}</span>
                </div>

                <div class="w-px h-3 bg-crs-border"></div>

                <!-- Liquidity State -->
                <div class="flex items-center gap-1">
                    <span class="text-crs-gray">DATA QUALITY</span>
                    <span class="text-crs-green font-bold">100%</span>
                    <div class="w-8 h-1 bg-crs-darkbg rounded-full border border-crs-border overflow-hidden inline-block">
                        <div class="h-full bg-crs-green rounded-full w-full"></div>
                    </div>
                </div>
            </div>

            <!-- Right Signature Branding matching reference -->
            <div class="flex items-center gap-2 text-right shrink-0">
                <div>
                    <div class="text-[8.5px] font-bold text-white uppercase tracking-widest">${systemName}</div>
                    <div class="text-[7.5px] text-crs-gray tracking-wider uppercase">by ${author}</div>
                </div>
                <div class="w-7 h-5 flex items-center justify-center font-serif text-crs-gold italic font-bold text-xs border-l border-crs-border pl-1">
                    Dadang
                </div>
            </div>
        </div>
    `;

    // Live Data Connection
    window.addEventListener('crs-update', (e) => {
        const data = e.detail;
        if (!data) return;

        if (data.db_stats) {
            document.getElementById('stat-total').textContent = data.db_stats.total;
            document.getElementById('stat-wl').textContent = data.db_stats.wins + ' / ' + data.db_stats.losses;
            document.getElementById('stat-wr').textContent = data.db_stats.win_rate.toFixed(1) + '%';
            
            const pnl = data.db_stats.total_pnl;
            const pnlEl = document.getElementById('stat-pnl');
            pnlEl.textContent = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + ' USD';
            pnlEl.className = pnl >= 0 ? 'text-crs-green font-bold' : 'text-crs-red font-bold';
        }

        if (data.recommendation) {
            const biasEl = document.getElementById('stat-bias');
            if (data.recommendation.includes('BUY')) {
                biasEl.textContent = 'BULLISH';
                biasEl.className = 'text-crs-green font-bold glow-green uppercase';
            } else if (data.recommendation.includes('SELL')) {
                biasEl.textContent = 'BEARISH';
                biasEl.className = 'text-crs-red font-bold glow-red uppercase';
            } else {
                biasEl.textContent = 'NEUTRAL';
                biasEl.className = 'text-crs-gray font-bold uppercase';
            }
        }
    });
}
