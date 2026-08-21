document.addEventListener('DOMContentLoaded', () => {
    initWallFilter();
});

function initWallFilter() {
    const wallfilterPanel = document.getElementById('wallfilter-panel');

    wallfilterPanel.innerHTML = `
        <div class="panel-header">
            <span>WALL FILTER & SETTINGS</span>
        </div>

        <div class="p-1.5 flex-1 flex gap-2 text-[9px] bg-[#06090e] overflow-y-auto">
            <!-- Left Controls: Range & Checkboxes -->
            <div class="w-1/2 flex flex-col gap-1 border-r border-crs-border/60 pr-2">
                <div class="flex justify-between items-center">
                    <span class="text-crs-gray font-semibold">SCAN RANGE</span>
                    <select class="terminal-input text-[8.5px] py-0 font-mono">
                        <option>Unlimited (Full Depth) ˅</option>
                        <option>100 Pips</option>
                    </select>
                </div>

                <div class="flex justify-between items-center">
                    <span class="text-crs-gray font-semibold">DISPLAY RANGE</span>
                    <select class="terminal-input text-[8.5px] py-0 font-mono">
                        <option>±5000 Pips ˅</option>
                        <option>±1000 Pips</option>
                    </select>
                </div>

                <div class="flex justify-between items-center">
                    <span class="text-crs-gray font-semibold">MIN LOT SIZE</span>
                    <div class="flex items-center gap-1">
                        <input type="number" id="min-lot-input" value="10" class="terminal-input w-8 text-center text-[8.5px] py-0">
                        <span class="text-crs-gray text-[8.5px] font-mono">LOT</span>
                    </div>
                </div>

                <!-- Interactive Checkboxes Grid matching reference -->
                <div class="grid grid-cols-2 gap-0.5 mt-0.5 border-t border-crs-border/40 pt-1 text-[8.5px]">
                    <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" id="chk-buy" checked class="accent-crs-green"> <span class="text-crs-green font-semibold">BUY WALL</span></label>
                    <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" id="chk-sell" checked class="accent-crs-red"> <span class="text-crs-red font-semibold">SELL WALL</span></label>
                    <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" id="chk-active" checked class="accent-crs-green"> <span class="text-crs-green font-semibold">ACTIVE</span></label>
                    <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" id="chk-reinforced" checked class="accent-crs-blue"> <span class="text-crs-blue font-semibold">REINFORCED</span></label>
                    <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" id="chk-absorbing" checked class="accent-crs-orange"> <span class="text-crs-orange font-semibold">ABSORBING</span></label>
                    <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" id="chk-removed" checked class="accent-crs-gray"> <span class="text-crs-gray font-semibold">REMOVED</span></label>
                </div>
            </div>

            <!-- Right Controls: Auto Settings matching reference -->
            <div class="w-1/2 flex flex-col gap-1 font-mono">
                <div class="text-[8.5px] text-crs-gray font-sans font-semibold tracking-wider uppercase border-b border-crs-border/40 pb-0.5">AUTO SETTINGS</div>
                
                <div class="flex justify-between items-center">
                    <span class="text-crs-gray font-semibold font-sans text-[8.5px]">AUTO SCAN</span>
                    <span class="switch-toggle-green">ON</span>
                </div>

                <div class="flex justify-between items-center">
                    <span class="text-crs-gray font-semibold font-sans text-[8.5px]">AUTO SAVE</span>
                    <span class="switch-toggle-green">ON</span>
                </div>

                <div class="flex justify-between items-center">
                    <span class="text-crs-gray font-semibold font-sans text-[8.5px]">GRACE PERIOD</span>
                    <span class="text-white text-[8.5px]">5 Minutes</span>
                </div>

                <div class="flex justify-between items-center">
                    <span class="text-crs-gray font-semibold font-sans text-[8.5px]">REFRESH INTERVAL</span>
                    <span class="text-crs-gold text-[8.5px] font-bold">250 ms</span>
                </div>
            </div>
        </div>
    `;

    setupCheckboxListeners();
}

function setupCheckboxListeners() {
    const f = window.CRS_CONFIG.state.filter;
    const map = [
        { id: 'chk-buy', prop: 'showBuy' },
        { id: 'chk-sell', prop: 'showSell' },
        { id: 'chk-active', prop: 'showActive' },
        { id: 'chk-reinforced', prop: 'showReinforced' },
        { id: 'chk-absorbing', prop: 'showAbsorbing' },
        { id: 'chk-removed', prop: 'showRemoved' }
    ];

    map.forEach(item => {
        const el = document.getElementById(item.id);
        if (el) {
            el.addEventListener('change', (e) => {
                f[item.prop] = e.target.checked;
                window.dispatchEvent(new CustomEvent('crs-filter-changed'));
            });
        }
    });

    const minLotEl = document.getElementById('min-lot-input');
    if (minLotEl) {
        minLotEl.addEventListener('input', (e) => {
            f.minLot = parseInt(e.target.value) || 0;
            window.dispatchEvent(new CustomEvent('crs-filter-changed'));
        });
    }
}
