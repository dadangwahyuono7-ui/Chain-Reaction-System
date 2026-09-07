document.addEventListener('DOMContentLoaded', () => {
    initHeader();
    startRealtimeEngine();
});

function initHeader() {
    const headerPanel = document.getElementById('header-panel');
    const { systemName, author, instrument, instrumentDesc, state } = window.CRS_CONFIG;

    headerPanel.innerHTML = `
        <!-- Left: Logo & System Title -->
        <div class="flex items-center gap-2 border-r border-crs-border pr-3 shrink-0">
            <!-- Hexagon Emblem Logo -->
            <div class="w-6 h-6 rounded flex items-center justify-center font-black text-crs-black text-[10px] bg-crs-gold shadow-glow-gold" style="clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);">
                CR
            </div>
            <div>
                <div class="text-[11px] font-black tracking-wider text-crs-gold leading-none">
                    ${systemName}
                </div>
                <div class="text-[8px] text-crs-gray tracking-wider uppercase font-semibold leading-tight mt-0.5">
                    by ${author}
                </div>
            </div>
        </div>

        <!-- Center Metadata Widgets matching reference image -->
        <div class="flex items-center gap-5 text-xs font-mono overflow-hidden">
            <!-- Instrument -->
            <div class="shrink-0">
                <div class="text-[8px] text-crs-gray font-sans font-semibold uppercase tracking-wider leading-none">INSTRUMENT</div>
                <div class="font-bold text-white flex items-center gap-1.5 leading-tight mt-0.5">
                    <span class="text-[11px] font-bold text-white">${instrument}</span>
                    <span class="text-[8px] text-crs-gray font-normal">${instrumentDesc}</span>
                </div>
            </div>

            <!-- Price -->
            <div class="border-l border-crs-border pl-3 shrink-0">
                <div class="text-[8px] text-crs-gray font-sans font-semibold uppercase tracking-wider leading-none">PRICE</div>
                <div class="font-bold text-crs-green flex items-center gap-1.5 leading-tight mt-0.5">
                    <span class="text-[12px] font-black font-mono text-crs-green" id="header-price">${state.price.toFixed(2)}</span>
                    <span class="text-[9px] font-semibold text-crs-green">+13.48 (+0.33%)</span>
                </div>
            </div>

            <!-- Time -->
            <div class="border-l border-crs-border pl-3 shrink-0">
                <div class="text-[8px] text-crs-gray font-sans font-semibold uppercase tracking-wider leading-none">TIME</div>
                <div class="text-white font-medium text-[10px] leading-tight mt-0.5" id="header-time">${state.timeStr}</div>
            </div>

            <!-- Session -->
            <div class="border-l border-crs-border pl-3 shrink-0">
                <div class="text-[8px] text-crs-gray font-sans font-semibold uppercase tracking-wider leading-none">SESSION</div>
                <div class="text-white font-medium text-[10px] flex items-center gap-1 leading-tight mt-0.5">
                    <span class="text-crs-blue font-bold">${state.session}</span>
                    <span class="text-white text-[9px]">${state.sessionStatus}</span>
                </div>
            </div>

            <!-- Status -->
            <div class="border-l border-crs-border pl-3 shrink-0">
                <div class="text-[8px] text-crs-gray font-sans font-semibold uppercase tracking-wider leading-none">STATUS</div>
                <div class="text-crs-green font-bold flex items-center gap-1 text-[10px] leading-tight mt-0.5">
                    <span class="w-1.5 h-1.5 rounded-full bg-crs-green animate-pulse-neon"></span>
                    ${state.status}
                </div>
            </div>
        </div>

        <!-- Right Controls matching reference -->
        <div class="flex items-center gap-2 text-xs font-mono shrink-0">
            <!-- Data Feed -->
            <div class="bg-crs-darkbg border border-crs-border px-2 py-0.5 rounded flex items-center gap-1.5 text-[9px]">
                <span class="text-crs-gray font-sans text-[8px]">DATA FEED</span>
                <span class="w-1.5 h-1.5 rounded-full bg-crs-green"></span>
                <span class="text-white font-bold">${state.feed}</span>
            </div>

            <!-- Refresh Rate Select -->
            <div class="bg-crs-darkbg border border-crs-border px-1.5 py-0.5 rounded flex items-center gap-1 text-[9px]">
                <span class="text-crs-gray font-sans text-[8px]">REFRESH ⓘ</span>
                <span class="text-crs-gold font-bold">${state.refreshRate} ˅</span>
            </div>

            <!-- Action Buttons -->
            <div class="flex items-center gap-1 text-crs-gray ml-1">
                <button class="p-1 hover:text-white hover:bg-crs-border rounded transition text-[11px]">⚙</button>
                <button class="p-1 hover:text-white hover:bg-crs-border rounded transition text-[11px]">⤢</button>
                <button class="w-5 h-5 rounded-full bg-crs-red text-white flex items-center justify-center text-[10px] hover:bg-crs-red/80 transition">⏻</button>
            </div>
        </div>
    `;
}

async function pollStatus() {
    try {
        const res = await fetch("live_status.json?t=" + Date.now(), {cache: "no-store"});
        if (res.ok) {
            const data = await res.json();
            // Update global config with latest state
            if (data.status) {
                const now = new Date();
                const timeEl = document.getElementById('header-time');
                if (timeEl) {
                    const timeStr = now.toLocaleTimeString('en-US', { hour12: false }) + " WIB";
                    timeEl.textContent = `${now.getDate()} Aug ${now.getFullYear()} ${timeStr}`;
                }
                
                // Update Price in Header
                const priceEl = document.getElementById('header-price');
                if (priceEl && data.dom && data.dom.current_price) {
                    priceEl.textContent = data.dom.current_price.toFixed(2);
                }
            }
            // Dispatch real data to all modules
            window.dispatchEvent(new CustomEvent('crs-update', { detail: data }));
        }
    } catch (e) {
        console.warn("Connection lost to Bridge:", e);
    }
}

function startRealtimeEngine() {
    setInterval(pollStatus, 200);
}

