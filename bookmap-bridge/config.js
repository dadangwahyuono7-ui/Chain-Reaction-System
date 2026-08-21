const Config = {
    systemName: "CHAIN REACTION SYSTEM",
    author: "DADANG WAHYUONO",
    version: "v3.0 MAXIMAL PRO",
    
    instrument: "XAUUSD",
    instrumentDesc: "Gold Spot / US Dollar",
    
    // Global Interactive State
    state: {
        price: 4090.15,
        change: +13.48,
        changePct: +0.33,
        session: "LONDON",
        sessionStatus: "Active",
        status: "MARKET OPEN",
        feed: "Rithmic - Live",
        refreshRate: "Auto (200ms)",
        timeStr: "03 Aug 2026 23:45:51 WIB",
        
        // Active Selection State
        selectedWall: {
            price: 4142.4,
            side: 'SELL',
            type: 'STHL',
            highestSize: 195,
            lowestSize: 78,
            maxAge: '3h 28m',
            firstSeen: '03 Aug 2026 20:17:43',
            timeframe: '6H'
        },

        // Filters State
        filter: {
            side: 'ALL',
            searchPrice: '',
            showBuy: true,
            showSell: true,
            showActive: true,
            showReinforced: true,
            showAbsorbing: true,
            showRemoved: true,
            minLot: 10
        },

        orderflowViewMode: 'BOOKMAP VIEW',
        
        // CMP Cascade
        cmp: [
            { tf: 'D1', status: 'BUY', trend: 'CF' },
            { tf: 'H4', status: 'BUY', trend: 'CF' },
            { tf: 'H1', status: 'BUY', trend: 'CF' },
            { tf: 'M30', status: 'BUY', trend: 'CF' },
            { tf: 'M15', status: 'BUY', trend: 'CF' },
            { tf: 'M5', status: 'BUY', trend: 'CF' }
        ],
        
        // Decision Engine
        confidence: 70,
        wallAcuan: { price: 4141.1, type: "Buy Limit - Size 12", validation: "PENDING VALIDATION", xau: "4088.40 XAU", mode: "VR" },
        wallUjian: { price: 4142.4, type: "Sell Limit - STHL - ACTIVE", xau: "4090.70 XAU", mode: "CF" },
        triggerEntry: { entry: 4092.60, tp: "4102.60 / 4112.60", sl: 4082.60 },
        validasi: "PENDING VALIDATION",
        deltaVal: 14,
        
        // Statistics
        stats: {
            spread: "0.28",
            dayRange: "4062.35 - 4118.70",
            avgVolume: "125,430 LOT",
            tickSpeed: "12 / sec",
            orderFlowBias: "BUY DOMINANT",
            liquidityState: "HIGH",
            volatility: "MODERATE",
            dataQuality: "100%"
        }
    },

    Colors: {
        bg: '#05070a',
        panel: '#0d111a',
        border: '#182030',
        green: '#00ff88',
        red: '#ff0055',
        blue: '#00d9ff',
        gold: '#ffd700',
        orange: '#ff6600',
        gray: '#8292b0',
        darkgray: '#3a465e'
    },

    randomInt: (min, max) => Math.floor(Math.random() * (max - min + 1)) + min,
    randomFloat: (min, max) => Math.random() * (max - min) + min
};

window.CRS_CONFIG = Config;
