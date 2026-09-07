document.addEventListener('DOMContentLoaded', () => {
    initCmpCascade();
});

function initCmpCascade() {
    const cmpPanel = document.getElementById('cmp-panel');
    const { cmp } = window.CRS_CONFIG.state;

    cmpPanel.innerHTML = `
        <div class="panel-header">
            <span>CMP CASCADE</span>
        </div>
        <div class="p-2 flex flex-col justify-between h-full">
            <table class="terminal-table w-full">
                <thead>
                    <tr>
                        <th class="w-1/2">TIMEFRAME</th>
                        <th class="w-1/2 text-right">TREND STATUS</th>
                    </tr>
                </thead>
                <tbody id="cmp-tbody">
                </tbody>
            </table>
            <div class="bg-crs-darkbg p-2 rounded border border-crs-border flex flex-col items-center justify-center gap-1 my-1 shadow-inner">
                <div class="text-[8.5px] text-crs-gray font-semibold tracking-wider">CMP ALIGNMENT</div>
                <div id="cmp-align-box" class="bg-crs-green text-crs-black font-black text-[11px] px-5 py-1 rounded shadow-glow-green uppercase tracking-widest">
                    -
                </div>
                <div id="cmp-cf-box" class="text-[9.5px] text-crs-gold font-bold tracking-wider mt-0.5">
                    -
                </div>
            </div>
        </div>
    `;

    window.addEventListener('crs-update', (e) => {
        const data = e.detail;
        if (!data || !data.tf_matrix) return;
        
        let tbodyHtml = '';
        const order = ['D', 'H4', 'H1', 'M30', 'M15', 'M5', 'M1'];
        let buyCount = 0; let sellCount = 0;
        let cfConfirmed = false;
        
        order.forEach(tf => {
            const row = data.tf_matrix[tf];
            if (!row) return;
            const isBuy = row.cmp === 'BUY';
            const colorClass = isBuy ? 'text-crs-green' : 'text-crs-red';
            const arrow = isBuy ? '▲' : '▼';
            
            if (isBuy) buyCount++; else if (row.cmp === 'SELL') sellCount++;
            if (row.cf && row.cf.includes('BUY') || row.cf.includes('SELL')) cfConfirmed = true;

            // badges
            let badges = '';
            if (row.vr && row.vr !== '-' && row.vr !== '–') {
                badges += `<span class="badge-status bg-crs-amber/20 text-crs-amber border border-crs-amber/40 mr-1">VR</span>`;
            }
            if (row.cf && row.cf !== '-' && row.cf !== '–') {
                badges += `<span class="badge-status bg-crs-gold/20 text-crs-gold border border-crs-gold/40">CF</span>`;
            }

            tbodyHtml += `
                <tr class="border-b border-crs-border/30">
                    <td class="font-mono font-bold text-white py-1">${tf}</td>
                    <td class="text-right py-1">
                        <span class="${colorClass} font-bold mr-2 text-[10px]">${arrow} ${row.cmp}</span>
                        ${badges}
                    </td>
                </tr>
            `;
        });
        
        document.getElementById('cmp-tbody').innerHTML = tbodyHtml;
        
        const alignBox = document.getElementById('cmp-align-box');
        if (buyCount >= 5) {
            alignBox.className = "bg-crs-green text-crs-black font-black text-[11px] px-5 py-1 rounded shadow-glow-green uppercase tracking-widest";
            alignBox.textContent = "STRONG BUY";
        } else if (sellCount >= 5) {
            alignBox.className = "bg-crs-red text-crs-black font-black text-[11px] px-5 py-1 rounded shadow-glow-red uppercase tracking-widest";
            alignBox.textContent = "STRONG SELL";
        } else {
            alignBox.className = "bg-crs-darkbg text-crs-gray font-black text-[11px] px-5 py-1 rounded border border-crs-border uppercase tracking-widest";
            alignBox.textContent = "MIXED";
        }
        
        const cfBox = document.getElementById('cmp-cf-box');
        cfBox.textContent = cfConfirmed ? "CF CONFIRMED" : "WAITING CF";
    });
}
