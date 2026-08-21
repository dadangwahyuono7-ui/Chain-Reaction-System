document.addEventListener('DOMContentLoaded', () => {
    initWallMemory();
});

const persistentWalls = [
    { price: 4142.4, side: 'SELL', size: 183, age: '3h 28m', status: 'ACTIVE', type: 'STHL', lastSeen: '23:45:21' },
    { price: 4141.1, side: 'BUY',  size: 152, age: '5h 12m', status: 'ACTIVE', type: 'LTHL', lastSeen: '23:45:21' },
    { price: 4140.8, side: 'BUY',  size: 98,  age: '1h 44m', status: 'ACTIVE', type: 'STHL', lastSeen: '23:45:20' },
    { price: 4139.7, side: 'SELL', size: 126, age: '4h 03m', status: 'ACTIVE', type: 'LTHL', lastSeen: '23:45:20' },
    { price: 4138.6, side: 'BUY',  size: 210, age: '6h 21m', status: 'REINFORCED', type: 'LTHL', lastSeen: '23:45:19' },
    { price: 4137.2, side: 'BUY',  size: 75,  age: '2h 11m', status: 'ACTIVE', type: 'STHL', lastSeen: '23:45:19' },
    { price: 4135.0, side: 'SELL', size: 165, age: '7h 09m', status: 'REINFORCED', type: 'STHL', lastSeen: '23:45:18' },
    { price: 4132.8, side: 'SELL', size: 110, age: '1h 36m', status: 'ACTIVE', type: 'STHL', lastSeen: '23:45:18' },
    { price: 4128.6, side: 'BUY',  size: 190, age: '1d 4h',  status: 'ACTIVE', type: 'LTHL', lastSeen: '23:45:17' },
    { price: 4124.3, side: 'BUY',  size: 89,  age: '8h 52m', status: 'ACTIVE', type: 'STHL', lastSeen: '23:45:17' },
    { price: 4118.0, side: 'SELL', size: 144, age: '1d 2h',  status: 'REINFORCED', type: 'LTHL', lastSeen: '23:45:16' },
    { price: 4095.6, side: 'BUY',  size: 76,  age: '3h 42m', status: 'ABSORBING', type: 'STHL', lastSeen: '23:45:15' },
    { price: 4078.2, side: 'BUY',  size: 130, age: '2d 1h',  status: 'ACTIVE', type: 'LTHL', lastSeen: '23:45:15' },
    { price: 4055.4, side: 'SELL', size: 95,  age: '5h 33m', status: 'ACTIVE', type: 'STHL', lastSeen: '23:45:14' }
];

function initWallMemory() {
    const wallmemoryPanel = document.getElementById('wallmemory-panel');

    wallmemoryPanel.innerHTML = `
        <div class="panel-header">
            <span>ZONE MAP - WALL MEMORY</span>
            <div class="flex items-center gap-1">
                <input type="text" id="wall-search-input" placeholder="Search price..." class="terminal-input w-20 text-[8.5px] py-0">
                <button id="filter-tab-all" class="bg-crs-gold/20 text-crs-gold border border-crs-gold/40 px-1.5 py-0 rounded text-[8.5px] font-bold">ALL</button>
                <button id="filter-tab-buy" class="bg-crs-darkbg text-crs-gray border border-crs-border px-1.5 py-0 rounded text-[8.5px] hover:text-white">BUY</button>
                <button id="filter-tab-sell" class="bg-crs-darkbg text-crs-gray border border-crs-border px-1.5 py-0 rounded text-[8.5px] hover:text-white">SELL</button>
            </div>
        </div>

        <!-- Table View -->
        <div class="flex-1 overflow-auto min-h-0">
            <table class="terminal-table">
                <thead>
                    <tr>
                        <th>PRICE</th>
                        <th>SIDE</th>
                        <th>SIZE (LOT)</th>
                        <th>AGE</th>
                        <th>STATUS</th>
                        <th>TYPE</th>
                        <th>LAST SEEN</th>
                    </tr>
                </thead>
                <tbody id="wallmemory-tbody">
                    ${renderTableRows(getFilteredWalls())}
                </tbody>
            </table>
        </div>

        <!-- Legend Footer -->
        <div class="p-1 bg-crs-darkbg border-t border-crs-border flex items-center justify-around text-[8px] text-crs-gray font-semibold uppercase">
            <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-green"></span> ACTIVE</div>
            <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-blue"></span> REINFORCED</div>
            <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-orange"></span> ABSORBING</div>
            <div class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-crs-darkgray"></span> REMOVED</div>
        </div>
    `;

    setupInteractions();

    // Live Update from Bookmap Data
    window.addEventListener('crs-update', (e) => {
        const data = e.detail;
        if (!data || !data.wall_ladder) return;
        
        const asks = data.wall_ladder.asks || [];
        const bids = data.wall_ladder.bids || [];
        
        const newWalls = [];
        const nowStr = new Date().toLocaleTimeString('en-US', { hour12: false });
        
        asks.forEach(ask => {
            newWalls.push({ price: ask[0], side: 'SELL', size: ask[1], age: 'LIVE', status: 'ACTIVE', type: 'ASK WALL', lastSeen: nowStr });
        });
        
        bids.forEach(bid => {
            newWalls.push({ price: bid[0], side: 'BUY', size: bid[1], age: 'LIVE', status: 'ACTIVE', type: 'BID WALL', lastSeen: nowStr });
        });
        
        // Retain current filtering and selected state
        persistentWalls.length = 0;
        persistentWalls.push(...newWalls);
        
        refreshTable();
    });

    window.addEventListener('crs-filter-changed', refreshTable);
}

function getFilteredWalls() {
    const f = window.CRS_CONFIG.state.filter;
    return persistentWalls.filter(w => {
        if (f.side !== 'ALL' && w.side !== f.side) return false;
        if (f.searchPrice && !w.price.toString().includes(f.searchPrice)) return false;
        if (w.side === 'BUY' && !f.showBuy) return false;
        if (w.side === 'SELL' && !f.showSell) return false;
        if (w.status === 'ACTIVE' && !f.showActive) return false;
        if (w.status === 'REINFORCED' && !f.showReinforced) return false;
        if (w.status === 'ABSORBING' && !f.showAbsorbing) return false;
        if (w.status === 'REMOVED' && !f.showRemoved) return false;
        if (w.size < f.minLot) return false;
        return true;
    });
}

function refreshTable() {
    const tbody = document.getElementById('wallmemory-tbody');
    if (tbody) {
        tbody.innerHTML = renderTableRows(getFilteredWalls());
        attachRowClickListeners();
    }
}

function setupInteractions() {
    const btnAll = document.getElementById('filter-tab-all');
    const btnBuy = document.getElementById('filter-tab-buy');
    const btnSell = document.getElementById('filter-tab-sell');
    const searchInput = document.getElementById('wall-search-input');

    function setActiveTab(activeBtn) {
        [btnAll, btnBuy, btnSell].forEach(b => {
            if (b) {
                b.className = 'bg-crs-darkbg text-crs-gray border border-crs-border px-1.5 py-0 rounded text-[8.5px] hover:text-white';
            }
        });
        if (activeBtn) {
            activeBtn.className = 'bg-crs-gold/20 text-crs-gold border border-crs-gold/40 px-1.5 py-0 rounded text-[8.5px] font-bold shadow-glow-gold';
        }
    }

    if (btnAll) btnAll.addEventListener('click', () => { window.CRS_CONFIG.state.filter.side = 'ALL'; setActiveTab(btnAll); refreshTable(); });
    if (btnBuy) btnBuy.addEventListener('click', () => { window.CRS_CONFIG.state.filter.side = 'BUY'; setActiveTab(btnBuy); refreshTable(); });
    if (btnSell) btnSell.addEventListener('click', () => { window.CRS_CONFIG.state.filter.side = 'SELL'; setActiveTab(btnSell); refreshTable(); });

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            window.CRS_CONFIG.state.filter.searchPrice = e.target.value.trim();
            refreshTable();
        });
    }

    attachRowClickListeners();
}

function attachRowClickListeners() {
    const tbody = document.getElementById('wallmemory-tbody');
    if (!tbody) return;

    Array.from(tbody.children).forEach(tr => {
        tr.addEventListener('click', () => {
            const price = parseFloat(tr.children[0].textContent);
            const wall = persistentWalls.find(w => w.price === price);
            if (wall) {
                window.CRS_CONFIG.state.selectedWall = {
                    price: wall.price,
                    side: wall.side,
                    type: wall.type,
                    highestSize: wall.size + 40,
                    lowestSize: Math.max(10, wall.size - 50),
                    maxAge: wall.age,
                    firstSeen: '03 Aug 2026 20:17:43',
                    timeframe: '6H'
                };
                window.dispatchEvent(new CustomEvent('crs-wall-selected'));
            }
        });
    });
}

function renderTableRows(walls) {
    const selectedP = window.CRS_CONFIG.state.selectedWall.price;

    return walls.map(w => {
        const isBuy = w.side === 'BUY';
        const priceColor = isBuy ? 'text-crs-green font-bold' : 'text-crs-red font-bold';
        const sideColor = isBuy ? 'text-crs-green font-bold' : 'text-crs-red font-bold';
        
        let badgeClass = 'badge-active';
        if (w.status === 'REINFORCED') badgeClass = 'badge-reinforced';
        else if (w.status === 'ABSORBING') badgeClass = 'badge-absorbing';
        else if (w.status === 'REMOVED') badgeClass = 'badge-removed';

        const typeColor = w.type === 'STHL' ? 'text-crs-red' : 'text-crs-blue';
        const isSelected = w.price === selectedP ? 'bg-crs-gold/10 border-l-2 border-crs-gold' : '';

        return `
            <tr class="cursor-pointer hover:bg-white/5 transition-colors ${isSelected}">
                <td class="font-mono ${priceColor}">${w.price.toFixed(1)}</td>
                <td class="${sideColor}">${w.side}</td>
                <td class="font-mono text-white font-bold">${w.size}</td>
                <td class="text-crs-gray">${w.age}</td>
                <td><span class="badge-status ${badgeClass}">${w.status}</span></td>
                <td class="font-bold ${typeColor}">${w.type}</td>
                <td class="text-crs-gray font-mono text-[9px]">${w.lastSeen}</td>
            </tr>
        `;
    }).join('');
}
