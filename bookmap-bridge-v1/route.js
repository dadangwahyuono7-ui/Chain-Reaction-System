document.addEventListener('DOMContentLoaded', () => {
    initRoutePrediction();
});

function initRoutePrediction() {
    const routePanel = document.getElementById('route-panel');
    
    // Header
    const header = document.createElement('div');
    header.className = 'flex items-center justify-between mb-2';
    header.innerHTML = `
        <h2 class="text-xs font-bold text-crs-gray tracking-widest">ROUTE PREDICTION</h2>
        <span class="badge bg-white/10 text-white border border-white/20">CONFIDENCE 85%</span>
    `;
    routePanel.appendChild(header);

    // Path Container
    const pathContainer = document.createElement('div');
    pathContainer.className = 'flex items-center justify-between px-2 py-4 relative';

    const targets = [
        { price: 4068, type: 'start', current: false },
        { price: 4056, type: 'node', current: true },
        { price: 4043, type: 'node', current: false },
        { price: 4030, type: 'node', current: false },
        { price: 3995, type: 'end', current: false }
    ];

    // Background Line
    const bgLine = document.createElement('div');
    bgLine.className = 'absolute top-1/2 left-[10%] right-[10%] h-0.5 bg-crs-border -translate-y-1/2 z-0';
    pathContainer.appendChild(bgLine);

    // Active Line
    const activeLine = document.createElement('div');
    activeLine.className = 'absolute top-1/2 left-[10%] w-[20%] h-0.5 bg-crs-gold shadow-glow -translate-y-1/2 z-0';
    pathContainer.appendChild(activeLine);

    targets.forEach((target, index) => {
        const node = document.createElement('div');
        node.className = 'flex flex-col items-center gap-2 z-10';

        let dotColor = 'bg-crs-darkgray border-crs-gray/50';
        let priceColor = 'text-crs-gray';
        let glow = '';

        if (target.current) {
            dotColor = 'bg-crs-gold border-crs-gold';
            priceColor = 'text-crs-gold font-bold';
            glow = 'shadow-glow';
        } else if (index === 0) { // Past
            dotColor = 'bg-crs-green border-crs-green';
            priceColor = 'text-crs-green/50 line-through';
        } else if (index === targets.length - 1) { // Final Target
            dotColor = 'bg-crs-red border-crs-red';
            priceColor = 'text-crs-red font-bold';
        }

        node.innerHTML = `
            <div class="text-[10px] font-mono ${priceColor}">${target.price}</div>
            <div class="w-3 h-3 rounded-full border-2 ${dotColor} ${glow} bg-crs-panel"></div>
        `;

        pathContainer.appendChild(node);
    });

    routePanel.appendChild(pathContainer);

    // Subtext
    const subtext = document.createElement('div');
    subtext.className = 'text-[10px] text-crs-gray text-center mt-2 italic';
    subtext.innerHTML = "Jalur market memprioritaskan penyerapan liquidity area bawah.";
    routePanel.appendChild(subtext);
}
