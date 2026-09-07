document.addEventListener('DOMContentLoaded', () => {
    initDecisionEngine();
});

function initDecisionEngine() {
    const decisionPanel = document.getElementById('decision-panel');
    const { confidence, wallAcuan, wallUjian, triggerEntry, validasi, deltaVal } = window.CRS_CONFIG.state;

    decisionPanel.innerHTML = `
        <div class="panel-header">
            <span>DECISION ENGINE</span>
            <span class="text-[10px] text-crs-gray cursor-pointer hover:text-white">ⓘ</span>
        </div>

        <div class="p-2.5 flex-1 flex flex-col justify-between overflow-y-auto text-xs">
            <!-- Confidence Flip Bar -->
            <div>
                <div class="flex justify-between items-center text-[10px] font-semibold text-crs-gray mb-1">
                    <span>CONFIDENCE FLIP</span>
                    <span class="font-mono font-bold text-crs-gold"><span id="dec-conf-val">${confidence}</span> <span class="text-crs-gray font-normal">/100</span></span>
                </div>
                <div class="w-full h-2 bg-crs-darkbg rounded-full overflow-hidden border border-crs-border">
                    <div id="dec-conf-bar" class="h-full bg-gradient-to-r from-crs-orange via-crs-gold to-crs-green rounded-full shadow-glow-gold transition-all duration-500" style="width: ${confidence}%"></div>
                </div>
            </div>

            <!-- Wall Acuan (VR) -->
            <div class="border-t border-crs-border/60 pt-1.5">
                <div class="text-[9px] text-crs-gray font-semibold">WALL ACUAN (VR)</div>
                <div class="text-sm font-mono font-bold text-crs-green" id="dec-wall-acuan">-</div>
                <div class="text-[10px] text-crs-gray font-mono" id="dec-acuan-type">-</div>
            </div>

            <!-- Wall Ujian (CF) -->
            <div class="border-t border-crs-border/60 pt-1.5">
                <div class="text-[9px] text-crs-gray font-semibold">WALL UJIAN (CF)</div>
                <div class="text-sm font-mono font-bold text-crs-red" id="dec-wall-ujian">-</div>
                <div class="text-[10px] text-crs-gray font-mono" id="dec-ujian-type">-</div>
            </div>

            <!-- Validasi Saat Ini -->
            <div class="border-t border-crs-border/60 pt-1.5 bg-crs-darkbg/50 p-1.5 rounded border border-crs-border mt-2">
                <div class="text-[9px] text-crs-gray font-semibold">VALIDASI SAAT INI</div>
                <div id="dec-validasi" class="text-[11px] text-crs-gold font-bold tracking-wider uppercase animate-pulse-fast">WAITING DATA</div>
                <div class="text-[10px] font-mono text-crs-green font-bold">DELTA: <span id="dec-delta-val">-</span></div>
            </div>
        </div>
    `;

    window.addEventListener('crs-update', (e) => {
        const data = e.detail;
        if (!data) return;
        
        if (data.buyer_aggression_pct != null) {
            const confVal = document.getElementById('dec-conf-val');
            const confBar = document.getElementById('dec-conf-bar');
            if (confVal) confVal.textContent = data.buyer_aggression_pct.toFixed(1);
            if (confBar) confBar.style.width = `${Math.min(100, Math.max(0, data.buyer_aggression_pct))}%`;
        }

        if (data.cvd_30s != null) {
            const deltaValEl = document.getElementById('dec-delta-val');
            if (deltaValEl) {
                deltaValEl.textContent = (data.cvd_30s >= 0 ? "+" : "") + data.cvd_30s.toFixed(1);
                deltaValEl.className = data.cvd_30s >= 0 ? 'text-crs-green' : 'text-crs-red';
            }
        }

        if (data.recommendation) {
            const valEl = document.getElementById('dec-validasi');
            if (valEl) {
                valEl.textContent = data.recommendation;
                if (data.recommendation.includes('BUY')) valEl.className = 'text-[11px] font-bold tracking-wider uppercase animate-pulse-fast text-crs-green';
                else if (data.recommendation.includes('SELL')) valEl.className = 'text-[11px] font-bold tracking-wider uppercase animate-pulse-fast text-crs-red';
                else valEl.className = 'text-[11px] font-bold tracking-wider uppercase animate-pulse-fast text-crs-gold';
            }
        }

        if (data.wall_ladder) {
            const asks = data.wall_ladder.asks || [];
            const bids = data.wall_ladder.bids || [];
            
            if (asks.length > 0) {
                document.getElementById('dec-wall-ujian').textContent = asks[0][0].toFixed(1);
                document.getElementById('dec-ujian-type').textContent = "ASK WALL (" + asks[0][1] + "ct)";
            }
            if (bids.length > 0) {
                document.getElementById('dec-wall-acuan').textContent = bids[0][0].toFixed(1);
                document.getElementById('dec-acuan-type').textContent = "BID WALL (" + bids[0][1] + "ct)";
            }
        }
    });
}
