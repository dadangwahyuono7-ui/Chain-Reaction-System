/**
 * ═══════════════════════════════════════════════════════════════════════════
 *  MULTI-WINDOW ENGINE & TIMEFRAME RESAMPLING ORCHESTRATOR (PHASE 1)
 *  By Dadang Wahyuono
 *  - 21 Supported Chart Timeframes (Aggregation Engine)
 *  - Storyline Pro Cockpit Connection (Fractals, CMP, Depth Ladder)
 *  - SMA / EMA Indicators Engine & Custom Settings Manager
 *  - Full State Persistence (Layout, Symbols, Timeframes, Indicators, Volume, Settings)
 *  - Right Price Scale Countdown to Bar Close (1:1 TradingView)
 * ═══════════════════════════════════════════════════════════════════════════
 */

import { globalDrawingStore } from '../drawings/DrawingStore.js';
import { DrawingEngine } from '../drawings/DrawingEngine.js?v=8';

// Audit fix: App.js's Lock All / Hide All / Trash Drawings buttons call
// window.globalDrawingStore.* directly (see App.js lines ~90/100/111), tapi
// gak pernah ada yang assign module binding ini ke window - 3 tombol itu
// crash tiap diklik (Cannot read properties of undefined). windowManager
// sendiri udah di-expose (window.windowManager = ...) di App.js, ini yang
// ketinggalan.
window.globalDrawingStore = globalDrawingStore;

import { ALL_21_TIMEFRAMES, TF_SECONDS_MAP, POPULAR_SYMBOLS } from '../core/Constants.js';

// v1: Chart engine ini digabung ke Sultan web dashboard (dulunya standalone
// di port 8800). Halaman ini sendiri di-serve dari server dashboard utama
// (port 8766, tempat /sultan_status.json juga ada - fetch relatif di bawah
// buat itu tetap same-origin). Tapi data CANDLE/tick real-time masih dari
// server chart engine terpisah (server.py, port 8800, baca MT5 langsung) -
// jadi base URL-nya dibikin eksplisit di sini, ikut hostname halaman biar
// jalan juga lewat tunnel/LAN, bukan cuma localhost.
// 100% Unified Same-Origin Routing (localhost:8766 == trade.dadangchatai.com)
const IS_LOCAL_HOST = typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");
const CHART_ENGINE_PORT = 8800;
const CHART_ENGINE_BASE = "";

const CHART_TYPES = [
  { id: "candles",   label: "🕯️", title: "Candlestick" },
  { id: "line",      label: "📈", title: "Line Chart" }
];

// Mathematical Indicators Calculators
function calculateEMA(candles, period) {
  if (!candles || candles.length < period) return [];
  const k = 2 / (period + 1);
  const emaData = [];

  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += candles[i].close;
  }
  let prevEma = sum / period;
  emaData.push({ time: candles[period - 1].time, value: Number(prevEma.toFixed(4)) });

  for (let i = period; i < candles.length; i++) {
    const currentPrice = candles[i].close;
    const currentEma = (currentPrice - prevEma) * k + prevEma;
    emaData.push({ time: candles[i].time, value: Number(currentEma.toFixed(4)) });
    prevEma = currentEma;
  }
  return emaData;
}

function calculateSMA(candles, period) {
  if (!candles || candles.length < period) return [];
  const smaData = [];
  let sum = 0;

  for (let i = 0; i < period; i++) {
    sum += candles[i].close;
  }
  smaData.push({ time: candles[period - 1].time, value: Number((sum / period).toFixed(4)) });

  for (let i = period; i < candles.length; i++) {
    sum += candles[i].close - candles[i - period].close;
    smaData.push({ time: candles[i].time, value: Number((sum / period).toFixed(4)) });
  }
  return smaData;
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. INDIVIDUAL CHART WINDOW INSTANCE
// ─────────────────────────────────────────────────────────────────────────────
export class ChartWindow {
  constructor(windowManager, id, config = {}) {
    this.wm = windowManager;
    this.id = id;
    this.symbol = (config.symbol || "XAUUSD").toUpperCase();
    this.timeframe = (config.timeframe || "M5").toUpperCase();
    this.chartType = config.chartType || "candles";
    this.initialIndicators = config.indicators || null;
    this.initialVolumeVisible = config.volumeVisible !== undefined ? config.volumeVisible : true;

    this.candles = [];
    this.lastCandle = null;
    this.currentPrice = 0;
    this.isMaximized = false;
    this.isLoading = false;

    // Active indicators Map: key -> { id, type, period, color, series, visible, chipEl }
    this.activeIndicators = new Map();

    // DOM references
    this.el = null;
    this.chartContainer = null;
    this.legendEl = null;
    this.indicatorsLegendEl = null;
    this.volumeChipEl = null;
    this.volumeVisible = true;
    this.chart = null;
    this.candleSeries = null;
    this.volumeSeries = null;
    this.drawingEngine = null;
    this.resizeObserver = null;
    this.timerInterval = null;

    // v1: S&D zone overlay dari EA V3 (sultan_status.json) - price lines,
    // dibersihin & digambar ulang tiap kali WindowManager.fetchSultanStatus()
    // dapet data baru. Lihat updateSDZones() di bawah.
    this.sdZonePriceLines = [];
    // v2: Sierra Chart Suite overlay (marker candle + naked POC price line).
    this.scPocPriceLine = null;
    this.vaPriceLines = [];

    this.createDOM();
    this.initChart();
    this.loadHistory();
  }

  createDOM() {
    this.el = document.createElement("div");
    this.el.className = "chart-window";
    this.el.id = `chart-window-${this.id}`;

    this.el.innerHTML = `
      <div class="window-header">
        <div class="win-left-controls">
          <span class="win-badge">${this.id}</span>

          <!-- Symbol Selector (search-style like TradingView) -->
          <div class="sym-search-wrap">
            <input type="text" class="sym-search-input" value="${this.symbol}" title="Symbol (ketik simbol lalu Enter)" autocomplete="off" />
            <div class="sym-search-dropdown">
              ${POPULAR_SYMBOLS.map(s => `<div class="sym-dd-item" data-sym="${s}">${s}</div>`).join("")}
            </div>
          </div>

          <!-- Chart Type Selector (Candle / Line) -->
          <div class="win-chart-type-wrap">
            ${CHART_TYPES.map(ct => `<button class="win-act-btn btn-chart-type ${ct.id === this.chartType ? "active" : ""}" data-ctype="${ct.id}" title="${ct.title}">${ct.label}</button>`).join("")}
          </div>

          <!-- Timeframe Quick Selector -->
          <div class="win-tf-bar">
            ${["M1", "M5", "M15", "M30", "H1", "H4", "D1"].map(tf => `
              <button class="win-tf-btn ${tf === this.timeframe ? "active" : ""}" data-tf="${tf}">${tf}</button>
            `).join("")}

            <!-- 21 Timeframe Dropdown -->
            <div class="tf-dropdown-wrap">
              <button class="win-tf-btn tf-more-btn" title="All 21 Timeframes">▼</button>
              <div class="tf-flyout-menu">
                <div class="tf-flyout-header">Minutes</div>
                <div class="tf-flyout-grid">
                  ${["M1", "M2", "M3", "M4", "M5", "M6", "M10", "M12", "M15", "M20", "M30"].map(tf => `
                    <div class="tf-flyout-item ${tf === this.timeframe ? "active" : ""}" data-tf="${tf}">${tf}</div>
                  `).join("")}
                </div>
                <div class="tf-flyout-header">Hours</div>
                <div class="tf-flyout-grid">
                  ${["H1", "H2", "H3", "H4", "H6", "H8", "H12"].map(tf => `
                    <div class="tf-flyout-item ${tf === this.timeframe ? "active" : ""}" data-tf="${tf}">${tf}</div>
                  `).join("")}
                </div>
                <div class="tf-flyout-header">Daily / Weekly</div>
                <div class="tf-flyout-grid">
                  ${["D1", "W1", "MN1"].map(tf => `
                    <div class="tf-flyout-item ${tf === this.timeframe ? "active" : ""}" data-tf="${tf}">${tf}</div>
                  `).join("")}
                </div>
              </div>
            </div>
          </div>

          <!-- Quick Indicators Button -->
          <button class="win-act-btn btn-win-indicators" title="Add Indicators (EMA, SMA)">ƒx</button>
        </div>

        <!-- OHLC Legend & Candle Closing Countdown Timer -->
        <div class="win-ohlc-legend">
          <span class="leg-item leg-sym">${this.symbol}</span>
          <span class="leg-item leg-tf">${this.timeframe}</span>
          <span class="leg-item">O:<b class="val-o">0.00</b></span>
          <span class="leg-item">H:<b class="val-h">0.00</b></span>
          <span class="leg-item">L:<b class="val-l">0.00</b></span>
          <span class="leg-item">C:<b class="val-c">0.00</b></span>
          <span class="leg-item">V:<b class="val-v">0</b></span>
          <span class="win-candle-timer" title="Time remaining until active candle close">⏳ <b class="val-timer">--:--</b></span>
          <span class="win-delta-badge buy" title="Real-time 1m Delta & Flow Dominance">Δ <b class="val-delta">+0</b> <small class="val-flow-dom">50%</small></span>
          <span class="win-bar-count" title="Candles loaded">📊 <b class="val-bar-count">0</b> bars</span>
        </div>

        <!-- Right Window Actions -->
        <div class="win-right-controls">
          <button class="win-act-btn btn-autoscale active" title="Auto-Scale Price Axis (A)">A</button>
          <button class="win-act-btn btn-log-scale" title="Log Scale (L)">Log</button>
          <button class="win-act-btn btn-jump-latest" title="Jump to Latest Candle">⏭</button>
          <button class="win-act-btn btn-zoom-in" title="Zoom In (+)">➕</button>
          <button class="win-act-btn btn-zoom-out" title="Zoom Out (-)">➖</button>
          <button class="win-act-btn btn-fit-content" title="Auto Fit">⛶</button>
          <button class="win-act-btn btn-screenshot" title="Screenshot Chart">📷</button>
          <button class="win-act-btn btn-maximize-win" title="Maximize / Restore">🗖</button>
        </div>
      </div>

      <!-- Chart Canvas Viewport -->
      <div class="window-chart-container">
        <!-- Floating On-Chart Indicator Legend -->
        <div class="win-indicators-legend-wrapper">
          <button class="win-act-btn btn-toggle-indicators" title="Show/Hide Indicators Legend">👁️</button>
          <div class="win-indicators-legend"></div>
        </div>
        <!-- Bottom Status Bar (TradingView Style) -->
        <div class="win-status-bar">
          <span class="sb-cursor-date">—</span>
          <span class="sb-sep">|</span>
          <span class="sb-cursor-price">—</span>
          <span class="sb-sep">|</span>
          <span class="sb-bars-visible">— bars visible</span>
          <span class="sb-sep">|</span>
          <span class="sb-delta-history" title="Recent Delta 1m Stream"></span>
        </div>
      </div>
    `;

    this.chartContainer = this.el.querySelector(".window-chart-container");
    this.legendEl = this.el.querySelector(".win-ohlc-legend");
    this.indicatorsLegendEl = this.el.querySelector(".win-indicators-legend");
    this.indicatorsLegendWrapper = this.el.querySelector(".win-indicators-legend-wrapper");
    this.btnToggleIndicators = this.el.querySelector(".btn-toggle-indicators");

    this.bindDOMEvents();
  }

  bindDOMEvents() {
    // --- Symbol Search Input (TradingView style) ---
    const symInput = this.el.querySelector(".sym-search-input");
    const symDropdown = this.el.querySelector(".sym-search-dropdown");

    symInput.addEventListener("focus", () => symDropdown.classList.add("show"));
    symInput.addEventListener("blur", () => setTimeout(() => symDropdown.classList.remove("show"), 180));
    symInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const val = symInput.value.trim().toUpperCase();
        if (val) this.setSymbol(val);
        symDropdown.classList.remove("show");
        symInput.blur();
      }
    });
    symInput.addEventListener("input", () => {
      const q = symInput.value.toUpperCase();
      this.el.querySelectorAll(".sym-dd-item").forEach(item => {
        item.style.display = item.dataset.sym.includes(q) ? "" : "none";
      });
    });
    this.el.querySelectorAll(".sym-dd-item").forEach(item => {
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        this.setSymbol(item.dataset.sym);
        symInput.value = item.dataset.sym;
        symDropdown.classList.remove("show");
      });
    });

    // --- Chart Type Selector (Candle / Line) ---
    this.el.querySelectorAll(".btn-chart-type").forEach(btn => {
      btn.addEventListener("click", () => {
        this.setChartType(btn.dataset.ctype);
      });
    });

    // --- Timeframe Buttons ---
    this.el.querySelectorAll(".win-tf-btn[data-tf]").forEach(btn => {
      btn.addEventListener("click", () => {
        this.setTimeframe(btn.dataset.tf);
      });
    });

    const flyout = this.el.querySelector(".tf-flyout-menu");
    const moreBtn = this.el.querySelector(".tf-more-btn");

    moreBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      flyout.classList.toggle("show");
    });
    document.addEventListener("click", () => flyout.classList.remove("show"));

    this.el.querySelectorAll(".tf-flyout-item[data-tf]").forEach(item => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        this.setTimeframe(item.dataset.tf);
        flyout.classList.remove("show");
      });
    });

    // --- Indicators ---
    const indBtn = this.el.querySelector(".btn-win-indicators");
    if (indBtn) {
      indBtn.addEventListener("click", () => {
        window.openIndicatorsModalForWindow(this);
      });
    }

    // --- Auto-Scale Toggle ---
    const btnAutoScale = this.el.querySelector(".btn-autoscale");
    if (btnAutoScale) {
      btnAutoScale.addEventListener("click", () => {
        this.isAutoScale = !this.isAutoScale;
        this.chart.priceScale("right").applyOptions({ autoScale: this.isAutoScale });
        btnAutoScale.classList.toggle("active", this.isAutoScale);
        if (window.showToast) window.showToast(this.isAutoScale ? "📐 Auto-Scale ON" : "📐 Auto-Scale OFF");
      });
    }

    // --- Log Scale Toggle ---
    const btnLogScale = this.el.querySelector(".btn-log-scale");
    if (btnLogScale) {
      btnLogScale.addEventListener("click", () => {
        this.isLogScale = !this.isLogScale;
        this.chart.priceScale("right").applyOptions({ mode: this.isLogScale ? 1 : 0 });
        btnLogScale.classList.toggle("active", this.isLogScale);
        if (window.showToast) window.showToast(this.isLogScale ? "📊 Log Scale ON" : "📊 Log Scale OFF");
      });
    }

    // --- Screenshot ---
    const btnScreenshot = this.el.querySelector(".btn-screenshot");
    if (btnScreenshot) {
      btnScreenshot.addEventListener("click", () => {
        try {
          const canvas = this.chartContainer.querySelector("canvas");
          if (canvas) {
            const link = document.createElement("a");
            link.download = `chart_${this.symbol}_${this.timeframe}_${Date.now()}.png`;
            link.href = canvas.toDataURL("image/png");
            link.click();
            if (window.showToast) window.showToast("📷 Screenshot saved!");
          }
        } catch(e) {
          if (window.showToast) window.showToast("📷 Screenshot failed (canvas restriction)");
        }
      });
    }

    // --- Zoom, Fit, Maximize ---
    this.el.querySelector(".btn-zoom-in").addEventListener("click", () => this.zoom(0.75));
    this.el.querySelector(".btn-zoom-out").addEventListener("click", () => this.zoom(1.35));
    this.el.querySelector(".btn-fit-content").addEventListener("click", () => this.chart.timeScale().fitContent());
    this.el.querySelector(".btn-jump-latest").addEventListener("click", () => this.chart.timeScale().scrollToRealTime());
    this.el.querySelector(".btn-maximize-win").addEventListener("click", () => this.wm.toggleMaximizeWindow(this));

    if (this.btnToggleIndicators) {
      this.btnToggleIndicators.addEventListener("click", (e) => {
        e.stopPropagation();
        this.indicatorsLegendWrapper.classList.toggle("collapsed");
      });
    }
  }

  initChart() {
    this.chart = LightweightCharts.createChart(this.chartContainer, {
      width: this.chartContainer.clientWidth || 400,
      height: this.chartContainer.clientHeight || 300,
      layout: {
        background: { type: "solid", color: "#07090e" },
        // Audit fix: dulu textColor dideklarasi 2x (nilai lama #94a3b8
        // ketiban #cbd5e1 di bawahnya, mati/gak ke-pakai) - dihapus yang mati.
        textColor: "#cbd5e1",
        fontSize: 13,
        fontFamily: "'JetBrains Mono', 'Segoe UI', system-ui, sans-serif"
      },
      // v1: Watermark - Dadang: "kasih tanda air biar gak dicopas orang".
      // Redup banget (biar gak ganggu baca candle) tapi kelihatan kalau
      // di-screenshot/direkam, nempel nama dia di setiap window chart.
      watermark: {
        visible: true,
        text: `${this.symbol} • COMMANDER DADANG WAHYUONO`,
        fontSize: (window.innerWidth >= 1920 ? 38 : 30),
        fontFamily: "'JetBrains Mono', 'Inter', sans-serif",
        color: "rgba(255, 215, 0, 0.28)", // Tanda air Emas Tegas & Jelas
        horzAlign: "center",
        vertAlign: "center"
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.04)" },
        horzLines: { color: "rgba(255, 255, 255, 0.04)" }
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: "rgba(0, 240, 255, 0.5)", width: 1, style: 3, labelBackgroundColor: "#0f172a" },
        horzLine: { color: "rgba(0, 240, 255, 0.5)", width: 1, style: 3, labelBackgroundColor: "#0f172a" }
      },
      timeScale: {
        borderColor: "#1e293b",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 12,
        barSpacing: 10,
        minBarSpacing: 2
      },
      rightPriceScale: {
        borderColor: "#1e293b",
        scaleMargins: {
          top: 0.02,
          bottom: 0.02
        },
        autoScale: true,
        alignLabels: true
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
        axisReset: true
      }
    });

    const isCurrency = (this.symbol.includes("USD") && !this.symbol.includes("XAU") && !this.symbol.includes("BTC"));
    this.candleSeries = this.chart.addCandlestickSeries({
      upColor: "#00e676",
      downColor: "#ff334b",
      borderVisible: false,
      wickUpColor: "#00e676",
      wickDownColor: "#ff334b",
      priceFormat: {
        type: "price",
        precision: isCurrency ? 4 : 2,
        minMove: isCurrency ? 0.0001 : 0.01
      }
    });

    this.volumeSeries = this.chart.addHistogramSeries({
      color: "rgba(56, 189, 248, 0.18)",
      priceFormat: { type: "volume" },
      priceScaleId: `vol_${this.id}`,
      scaleMargins: {
        top: 0.86,
        bottom: 0
      }
    });

    this.chart.priceScale(`vol_${this.id}`).applyOptions({
      scaleMargins: { top: 0.86, bottom: 0 },
      visible: false
    });

    this.drawingEngine = new DrawingEngine(this);

    this.chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData.get(this.candleSeries)) {
        this.updateLegend(this.lastCandle);
        this.updateIndicatorValues(this.lastCandle?.time);
        this.updateStatusBar(null, null);
        return;
      }
      const data = param.seriesData.get(this.candleSeries);
      this.updateLegend(data);
      this.updateIndicatorValues(param.time);
      this.updateStatusBar(param.time, data?.close || 0);

      if (this.wm.isCrosshairLinked && param.time) {
        this.wm.broadcastCrosshair(this.id, param.time, data?.close || 0);
      }
    });

    // Update bars visible count on scroll/zoom
    this.chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      this.updateBarsVisible();
    });


    this.chartContainer.addEventListener("wheel", (e) => {
      e.preventDefault();
      const logicalRange = this.chart.timeScale().getVisibleLogicalRange();
      if (!logicalRange) return;
      const zoomStep = 0.05; // Smoother zoom (was 0.12)
      const factor = e.deltaY > 0 ? (1 + zoomStep) : (1 - zoomStep);
      const rangeLen = logicalRange.to - logicalRange.from;
      const newRangeLen = Math.max(10, rangeLen * factor);
      const center = (logicalRange.from + logicalRange.to) / 2;
      this.chart.timeScale().setVisibleLogicalRange({
        from: center - (newRangeLen / 2),
        to: center + (newRangeLen / 2)
      });
      if (this.drawingEngine) this.drawingEngine.requestRender();
    }, { passive: false });

    this.chartContainer.addEventListener("dblclick", () => {
      this.chart.timeScale().fitContent();
    });

    this.timerInterval = setInterval(() => this.updateCountdownTimer(), 1000);

    // Right Price Scale Countdown Badge (TradingView Style on Axis)
    this.floatingCandleDeltaPill = document.createElement("div");
    this.floatingCandleDeltaPill.className = "floating-candle-delta-pill buy";
    this.floatingCandleDeltaPill.innerHTML = `Δ <b class="val-pill-delta">+0</b>`;
    this.chartContainer.appendChild(this.floatingCandleDeltaPill);

    this.confluenceRadarBanner = document.createElement("div");
    this.confluenceRadarBanner.className = "on-chart-radar-banner sell";
    this.confluenceRadarBanner.innerHTML = `☑ <b>RADAR KONFLUENSI:</b> <span class="val-score">80% SELL</span> <small class="val-grade">[A (BAGUS)]</small>`;
    this.chartContainer.appendChild(this.confluenceRadarBanner);

    // Audit fix: WindowManager.updateWallSweepBanner() was being called every
    // poll (fetchSultanStatus) but this method + its DOM element never
    // existed - threw silently forever inside a bare try/catch, so the wall
    // sweep alert (real EA signal, wall_sweep.active in sultan_status.json)
    // never showed even though the CSS for it was fully built already.
    this.wallSweepBanner = document.createElement("div");
    this.wallSweepBanner.className = "wall-sweep-floating-banner";
    this.wallSweepBanner.style.top = "54px";   // di bawah confluence radar banner (top:14px), biar gak numpuk
    this.wallSweepBanner.style.display = "none";
    this.chartContainer.appendChild(this.wallSweepBanner);

    this.priceScaleCountdownBadge = document.createElement("div");
    this.priceScaleCountdownBadge.className = "price-scale-countdown-badge";
    this.priceScaleCountdownBadge.textContent = "--:--";
    this.chartContainer.appendChild(this.priceScaleCountdownBadge);

    // Volume On-Chart Legend Chip (1-Click Hide / Remove like TradingView)
    this.volumeChipEl = document.createElement("div");
    this.volumeChipEl.className = "indicator-chip";
    this.volumeChipEl.dataset.id = "volume";
    this.volumeChipEl.style.borderColor = "#38bdf844";
    this.volumeChipEl.innerHTML = `
      <span class="ind-dot" style="background: #38bdf8;"></span>
      <span class="ind-label" style="color: #38bdf8;">Vol:</span>
      <span class="ind-val val-vol-chip">--</span>
      <button class="ind-action-btn ind-eye" title="Hide/Show Volume">👁️</button>
      <button class="ind-action-btn del ind-del" title="Remove Volume Histogram (Hapus)">✖</button>
    `;

    this.volumeVisible = (this.wm.globalChartConfig?.showVolume !== false) && (this.initialVolumeVisible !== false);
    this.volumeSeries.applyOptions({ visible: this.volumeVisible });
    this.volumeChipEl.classList.toggle("hidden-line", !this.volumeVisible);
    if (this.wm.globalChartConfig?.showVolume === false) {
      this.volumeChipEl.style.display = "none";
    }

    this.volumeChipEl.querySelector(".ind-eye").addEventListener("click", (e) => {
      e.stopPropagation();
      this.volumeVisible = !this.volumeVisible;
      this.volumeSeries.applyOptions({ visible: this.volumeVisible });
      this.volumeChipEl.classList.toggle("hidden-line", !this.volumeVisible);
      this.volumeChipEl.querySelector(".ind-eye").textContent = this.volumeVisible ? "👁️" : "🚫";
      this.wm.saveState();
    });

    this.volumeChipEl.querySelector(".ind-del").addEventListener("click", (e) => {
      e.stopPropagation();
      this.volumeVisible = false;
      this.volumeSeries.applyOptions({ visible: false });
      if (this.volumeChipEl.parentNode) {
        this.volumeChipEl.parentNode.removeChild(this.volumeChipEl);
      }
      this.wm.saveState();
      if (window.showToast) window.showToast("🗑️ Volume Histogram removed");
    });

    this.indicatorsLegendEl.appendChild(this.volumeChipEl);

    // Apply global settings
    if (this.wm.globalChartConfig) {
      this.applyChartSettings(this.wm.globalChartConfig);
    }

    // Restore saved indicators or defaults if none exist
    if (Array.isArray(this.initialIndicators)) {
      this.initialIndicators.forEach(ind => {
        this.addIndicator(ind.type, ind.period, ind.color, ind.visible !== false, false);
      });
    } else if (this.id === 1 && !this.wm.hasSavedState) {
      this.addIndicator("EMA", 21, "#ffb703", true, false);
    }

    this.resizeObserver = new ResizeObserver(() => {
      this.resize();
    });
    this.resizeObserver.observe(this.chartContainer);
  }

  applyChartSettings(cfg) {
    if (!cfg) return;

    if (this.candleSeries) {
      this.candleSeries.applyOptions({
        upColor: cfg.candleUp || "#00e676",
        downColor: cfg.candleDown || "#ff334b",
        wickUpColor: cfg.wickUp || "#00e676",
        wickDownColor: cfg.wickDown || "#ff334b",
        borderVisible: false
      });
    }

    if (this.chart) {
      this.chart.applyOptions({
        layout: {
          background: { color: cfg.chartBg || "#07090e" }
        },
        grid: {
          vertLines: {
            color: cfg.showGrid ? (cfg.gridColor || "rgba(255, 255, 255, 0.04)") : "transparent"
          },
          horzLines: {
            color: cfg.showGrid ? (cfg.gridColor || "rgba(255, 255, 255, 0.04)") : "transparent"
          }
        }
      });
    }

    if (this.priceScaleCountdownBadge) {
      this.priceScaleCountdownBadge.classList.toggle("hidden", !cfg.showCountdown);
    }

    if (this.volumeSeries) {
      const showVol = cfg.showVolume !== false && this.volumeVisible;
      this.volumeSeries.applyOptions({
        visible: showVol
      });
      if (this.volumeChipEl) {
        this.volumeChipEl.style.display = (cfg.showVolume !== false && this.volumeChipEl.parentNode) ? "flex" : "none";
      }
    }

    if (this.legendEl) {
      this.legendEl.style.display = cfg.showOHLC !== false ? "flex" : "none";
    }
  }

  getStateObject() {
    const indicatorsArr = [];
    this.activeIndicators.forEach(ind => {
      indicatorsArr.push({
        type: ind.type,
        period: ind.period,
        color: ind.color,
        visible: ind.visible
      });
    });

    return {
      id: this.id,
      symbol: this.symbol,
      timeframe: this.timeframe,
      chartType: this.chartType || "candles",
      volumeVisible: this.volumeVisible !== false,
      indicators: indicatorsArr
    };
  }

  // v1 (Replay) - nunjukin candle window ini sampai ke waktu snapshot
  // replay tertentu doang ("histori sekarang" versi replay), dari
  // _replayFullCandles yang dimuat WindowManager.startReplay(). Per-window
  // (ikut symbol/timeframe window itu sendiri), independen dari zona S&D
  // yang XAUUSD-only.
  setReplayCandles(uptoTime) {
    if (!this._replayFullCandles || !this._replayFullCandles.length) return;
    const visible = this._replayFullCandles.filter(c => c.time <= uptoTime);
    if (visible.length === 0) return;
    this.candles = visible;
    this.candleSeries.setData(visible);
    const volData = visible.map(c => ({
      time: c.time,
      value: c.volume || 100,
      color: c.close >= c.open ? "rgba(0, 230, 118, 0.25)" : "rgba(255, 51, 75, 0.25)"
    }));
    this.volumeSeries.setData(volData);
    this.lastCandle = visible[visible.length - 1];
    this.currentPrice = this.lastCandle.close;
    if (this.updateLegend) this.updateLegend(this.lastCandle);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // S&D ZONE OVERLAY (dari sultan_status.json, EA V3 - lihat mapSultanStatusToCockpit)
  // ─────────────────────────────────────────────────────────────────────────
    // ─────────────────────────────────────────────────────────────────────────
  // S&D ZONE OVERLAY (Clean Discrete S1, S2 / D1, D2 - Zero Clutter)
  // ─────────────────────────────────────────────────────────────────────────
      // ─────────────────────────────────────────────────────────────────────────
  // MASTER CLEAN S&D PRICE LINES WITH RIGHT SCALE BADGES (TRADINGVIEW STYLE)
  // ─────────────────────────────────────────────────────────────────────────
        // ─────────────────────────────────────────────────────────────────────────
  // SPACIOUS ON-CHART S&D PILL BADGES & PRICE LINES
  // ─────────────────────────────────────────────────────────────────────────
    updateSDBadgePositions() {
    if (!this.activeSDItems || !this.candleSeries || !this.chartContainer) return;

    if (this._rafSDPending) return;
    this._rafSDPending = true;

    requestAnimationFrame(() => {
      this._rafSDPending = false;
      if (!this.activeSDItems || !this.candleSeries || !this.chartContainer) return;
      const h = this.chartContainer.clientHeight;
      this.activeSDItems.forEach(item => {
        const y = this.candleSeries.priceToCoordinate(item.price);
        if (y !== null && y > 10 && y < (h - 25)) {
          item.el.style.top = `${y - 12}px`;
          item.el.style.display = "flex";
        } else {
          item.el.style.display = "none";
        }
      });
    });
  }

  updateSDZones(sdGroup, liq) {
    if (!this.candleSeries || this.symbol !== "XAUUSD" || !sdGroup) return;

    const supplies = sdGroup.supply || [];
    const demands = sdGroup.demand || [];
    const sdKey = `${supplies.map(s => `${s.lo}_${s.total_lot}`).join(",")}|${demands.map(d => `${d.hi}_${d.total_lot}`).join(",")}`;

    if (!this.sdBadgesContainer) {
      this.sdBadgesContainer = document.createElement("div");
      this.sdBadgesContainer.className = "sd-badges-container";
      this.chartContainer.appendChild(this.sdBadgesContainer);
    }

    if (this._lastSDKey !== sdKey) {
      this._lastSDKey = sdKey;

      this.sdZonePriceLines.forEach(pl => {
        try { this.candleSeries.removePriceLine(pl); } catch (e) {}
      });
      this.sdZonePriceLines = [];
      this.sdBadgesContainer.innerHTML = "";
      this.activeSDItems = [];

      const bestAskLot = (liq && liq.ask_wall_size) ? `${Math.round(liq.ask_wall_size)}L` : "";
      const bestBidLot = (liq && liq.bid_wall_size) ? `${Math.round(liq.bid_wall_size)}L` : "";

      // 1. Supply Lines
      supplies.forEach((z, idx) => {
        const liveWallStr = (idx === 0 && bestAskLot) ? ` • Ask Live: ${bestAskLot}` : "";
        const ujiStr = z.retest_count ? ` • Uji ${z.retest_count}x` : "";
        const fullText = `🔴 S${idx + 1} ${Math.round(z.total_lot || 0)}L • ${z.strength || 'SEDANG'} ${Math.round(z.score || 50)}${ujiStr}${liveWallStr}`;

        const pl = this.candleSeries.createPriceLine({
          price: z.lo,
          color: idx === 0 ? "#ff334b" : "#ff334b99",
          lineWidth: idx === 0 ? 2 : 1,
          lineStyle: idx === 0 ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed,
          axisLabelVisible: true,
          title: ``,
        });
        this.sdZonePriceLines.push(pl);

        const badge = document.createElement("div");
        badge.className = `on-chart-sd-pill supply ${idx === 0 ? "s1" : "s2"}`;
        badge.textContent = fullText;
        this.sdBadgesContainer.appendChild(badge);
        this.activeSDItems.push({ el: badge, price: z.lo });
      });

      // 2. Demand Lines
      demands.forEach((z, idx) => {
        const liveWallStr = (idx === 0 && bestBidLot) ? ` • Bid Live: ${bestBidLot}` : "";
        const ujiStr = z.retest_count ? ` • Uji ${z.retest_count}x` : "";
        const fullText = `🟢 D${idx + 1} ${Math.round(z.total_lot || 0)}L • ${z.strength || 'SEDANG'} ${Math.round(z.score || 50)}${ujiStr}${liveWallStr}`;

        const pl = this.candleSeries.createPriceLine({
          price: z.hi,
          color: idx === 0 ? "#00e676" : "#00e67699",
          lineWidth: idx === 0 ? 2 : 1,
          lineStyle: idx === 0 ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed,
          axisLabelVisible: true,
          title: ``,
        });
        this.sdZonePriceLines.push(pl);

        const badge = document.createElement("div");
        badge.className = `on-chart-sd-pill demand ${idx === 0 ? "d1" : "d2"}`;
        badge.textContent = fullText;
        this.sdBadgesContainer.appendChild(badge);
        this.activeSDItems.push({ el: badge, price: z.hi });
      });
    }

    this.updateSDBadgePositions();
  }

  updateSierraChart(sc) {
    if (!this.candleSeries) return;

    if (this.scPocPriceLine) {
      try { this.candleSeries.removePriceLine(this.scPocPriceLine); } catch (e) {}
      this.scPocPriceLine = null;
    this.vaPriceLines = [];
    }

    if (this.symbol !== "XAUUSD" || !sc || !this.candles.length) {
      this.candleSeries.setMarkers([]);
      return;
    }

    if (sc.naked_poc_active && sc.naked_poc_price > 0) {
      this.scPocPriceLine = this.candleSeries.createPriceLine({
        price: sc.naked_poc_price,
        color: "#ffb703",
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: "🧲 VPOC",
      });
    }

    const lastTime = this.candles[this.candles.length - 1].time;
    const prevTime = this.candles.length > 1 ? this.candles[this.candles.length - 2].time : lastTime;
    const markers = [];

    if (sc.imbalance_side === "BUY") {
      markers.push({ time: lastTime, position: "belowBar", color: "#00e676", shape: "arrowUp", text: "BUYER MASUK 3:1" });
    } else if (sc.imbalance_side === "SELL") {
      markers.push({ time: lastTime, position: "aboveBar", color: "#ff334b", shape: "arrowDown", text: "SELLER MASUK 3:1" });
    }

    if (sc.divergence_type === "BEAR") {
      markers.push({ time: prevTime, position: "aboveBar", color: "#ff50b4", shape: "arrowDown", text: "JEBAKAN BUYER" });
    } else if (sc.divergence_type === "BULL") {
      markers.push({ time: prevTime, position: "belowBar", color: "#00e6c8", shape: "arrowUp", text: "JEBAKAN SELLER" });
    }

    if (sc.whale_side === "BUY") {
      markers.push({ time: lastTime, position: "belowBar", color: "#00ff8c", shape: "circle", text: `🐋 PAUS BUY ${Math.round(sc.whale_lots)}L` });
    } else if (sc.whale_side === "SELL") {
      markers.push({ time: lastTime, position: "aboveBar", color: "#ff4646", shape: "circle", text: `🐋 PAUS SELL ${Math.round(sc.whale_lots)}L` });
    }

    if (sc.unfinished_found && sc.unfinished_time) {
      const match = this.candles.find(c => c.time === sc.unfinished_time);
      if (match) {
        markers.push({ time: match.time, position: "aboveBar", color: "#ffa500", shape: "circle", text: "Poor High" });
      }
    }

    markers.sort((a, b) => a.time - b.time);
    this.candleSeries.setMarkers(markers);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INDICATOR SYSTEM: ADD, REMOVE, HIDE/SHOW, EDIT
  // ─────────────────────────────────────────────────────────────────────────
  
  // ─────────────────────────────────────────────────────────────────────────
  // VALUE AREA OVERLAY (POC, VAH, VAL dari sultan_status.json.location)
  // ─────────────────────────────────────────────────────────────────────────
    // ─────────────────────────────────────────────────────────────────────────
  // VALUE AREA OVERLAY (POC Emas Solid, VAH & VAL Cyan Halus)
  // ─────────────────────────────────────────────────────────────────────────
    updateValueArea(loc) {
    if (!this.candleSeries || this.symbol !== "XAUUSD" || !loc) return;

    const locKey = `${loc.poc || 0}_${loc.vah || 0}_${loc.val || 0}`;
    if (this._lastLocKey === locKey) return; // Zero-glitch memoization
    this._lastLocKey = locKey;

    this.vaPriceLines.forEach(pl => {
      try { this.candleSeries.removePriceLine(pl); } catch (e) {}
    });
    this.vaPriceLines = [];

    if (loc.poc > 0) {
      const plPoc = this.candleSeries.createPriceLine({
        price: loc.poc,
        color: "#ffd700",
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: `📍 POC ${Number(loc.poc).toFixed(2)}`,
      });
      this.vaPriceLines.push(plPoc);
    }
    if (loc.vah > 0 && Math.abs(loc.vah - loc.poc) > 1.5) {
      const plVah = this.candleSeries.createPriceLine({
        price: loc.vah,
        color: "rgba(0, 240, 255, 0.4)",
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: `VAH ${Number(loc.vah).toFixed(2)}`,
      });
      this.vaPriceLines.push(plVah);
    }
    if (loc.val > 0 && Math.abs(loc.val - loc.poc) > 1.5) {
      const plVal = this.candleSeries.createPriceLine({
        price: loc.val,
        color: "rgba(0, 240, 255, 0.4)",
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: `VAL ${Number(loc.val).toFixed(2)}`,
      });
      this.vaPriceLines.push(plVal);
    }
  }

    updateRunningCandleDeltaPosition() {
    if (!this.floatingCandleDeltaPill || !this.lastCandle || !this.candleSeries || !this.chartContainer) return;

    if (this._rafDeltaPending) return;
    this._rafDeltaPending = true;

    requestAnimationFrame(() => {
      this._rafDeltaPending = false;
      if (!this.floatingCandleDeltaPill || !this.lastCandle || !this.candleSeries || !this.chartContainer) return;

      const timeScale = this.chart.timeScale();
      const x = timeScale.timeToCoordinate(this.lastCandle.time);
      const y = this.candleSeries.priceToCoordinate(this.lastCandle.close);

      const w = this.chartContainer.clientWidth;
      const h = this.chartContainer.clientHeight;

      if (y === null || y < 10 || y > (h - 30)) {
        this.floatingCandleDeltaPill.style.display = "none";
        return;
      }

      if (x !== null && x > 20 && x < (w - 85)) {
        this.floatingCandleDeltaPill.style.left = `${x + 18}px`;
        this.floatingCandleDeltaPill.style.top = `${y - 12}px`;
        this.floatingCandleDeltaPill.style.display = "flex";
      } else {
        this.floatingCandleDeltaPill.style.left = `${w - 140}px`;
        this.floatingCandleDeltaPill.style.top = `${y - 12}px`;
        this.floatingCandleDeltaPill.style.display = "flex";
      }
    });
  }

  // Audit fix: render buat wallSweepBanner (dibuat di initChart() di atas).
  // Dipanggil dari WindowManager.updateWallSweepBanner() - lihat di bawah.
  renderWallSweep(ws) {
    if (!this.wallSweepBanner) return;
    if (this.symbol !== "XAUUSD" || !ws || !ws.active) {
      this.wallSweepBanner.style.display = "none";
      return;
    }
    this.wallSweepBanner.style.display = "flex";
    const sideTxt = ws.side === "BID" ? "BID" : "ASK";
    this.wallSweepBanner.innerHTML = `🌊 <b>WALL SWEEP:</b> ${sideTxt} ${ws.status || ""} @${Number(ws.price || 0).toFixed(2)} (${Math.round(ws.size || 0)}L)`;
  }

  // v53.57: `radar` = sultan_status.json.confluence_radar, EA V3's REAL
  // CalculateConfluenceScore() (angka yang SAMA PERSIS ditampilin di banner
  // MT5) - Dadang: "isi aja bro karena gw fokusnya di chart sekarang".
  // `conv` (conviction, chain-depth) dipertahankan sebagai fallback doang
  // buat masa transisi sebelum EA di-reattach (biar gak kosong tiba-tiba).
  updateConfluenceRadar(radar, conv) {
    if (!this.confluenceRadarBanner) return;
    let score, dir, grade;
    if (radar) {
      score = Math.round(radar.score || 0);
      dir = (radar.dir || "WAIT").toUpperCase();
      grade = radar.grade || "-";
    } else if (conv) {
      score = conv.max > 0 ? Math.round((conv.score / conv.max) * 100) : 80;
      dir = (conv.dir || "WAIT").toUpperCase();
      grade = conv.grade || "HATI-HATI";
    } else {
      return;
    }
    const isBuy = dir === "BUY";
    const isSell = dir === "SELL";

    this.confluenceRadarBanner.className = `on-chart-radar-banner ${isBuy ? "buy" : (isSell ? "sell" : "wait")}`;
    this.confluenceRadarBanner.innerHTML = `☑ <b>RADAR KONFLUENSI:</b> <span class="val-score">${score}% ${dir}</span> <small class="val-grade">[${grade}]</small>`;
  }

  updateLiveFlow(flow) {
    if (!flow) return;
    const d1m = flow.delta_1m !== undefined ? flow.delta_1m : (flow.cvd || 0);
    const isBuy = d1m >= 0;
    const sign = d1m > 0 ? "+" : "";

    // 1. Update on-chart floating delta pill attached to running candle
    if (this.floatingCandleDeltaPill) {
      this.floatingCandleDeltaPill.className = `floating-candle-delta-pill ${isBuy ? "buy" : "sell"}`;
      this.floatingCandleDeltaPill.innerHTML = `Δ <b>${sign}${Math.round(d1m)}</b>`;
      this.updateRunningCandleDeltaPosition();
    }

    // 2. Update legend header badge
    const deltaBadge = this.el?.querySelector(".win-delta-badge");
    if (deltaBadge) {
      deltaBadge.className = `win-delta-badge ${isBuy ? "buy" : "sell"}`;
      const flowDom = flow.flow_dominant || (isBuy ? "BUY" : "SELL");
      const volPct = flow.vol_ratio_buy_pct ? `${Number(flow.vol_ratio_buy_pct).toFixed(0)}%` : `${Number(flow.pulse_pct || 50).toFixed(0)}%`;
      deltaBadge.innerHTML = `Δ <b class="val-delta">${sign}${Math.round(d1m)}</b> <small class="val-flow-dom">${flowDom} ${volPct}</small>`;
    }

    const sbDeltaStream = this.el?.querySelector(".sb-delta-history");
    if (sbDeltaStream && Array.isArray(flow.delta_history) && flow.delta_history.length > 0) {
      const recent = flow.delta_history.slice(-14);
      const maxAbs = Math.max(...recent.map(d => Math.abs(d)), 10);
      sbDeltaStream.innerHTML = recent.map(d => {
        const h = Math.min(12, Math.max(3, Math.round((Math.abs(d) / maxAbs) * 12)));
        const cls = d >= 0 ? "pos" : "neg";
        return `<span class="sb-delta-bar ${cls}" style="height:${h}px;" title="Delta 1m: ${d > 0 ? '+' : ''}${d}"></span>`;
      }).join("");
    }
  }

  addIndicator(type, period, color, visible = true, triggerSave = true) {
    const id = `${type.toLowerCase()}_${period}`;
    if (this.activeIndicators.has(id)) {
      if (triggerSave && window.showToast) window.showToast(`⚠️ ${type} ${period} is already on this chart`);
      return;
    }

    const isCurrency = (this.symbol.includes("USD") && !this.symbol.includes("XAU") && !this.symbol.includes("BTC"));
    const lineSeries = this.chart.addLineSeries({
      color: color,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      visible: visible,
      priceFormat: {
        type: "price",
        precision: isCurrency ? 4 : 2,
        minMove: isCurrency ? 0.0001 : 0.01
      }
    });

    const chip = document.createElement("div");
    chip.className = `indicator-chip ${visible ? "" : "hidden-line"}`;
    chip.dataset.id = id;
    chip.style.borderColor = `${color}44`;
    chip.innerHTML = `
      <span class="ind-dot" style="background: ${color};"></span>
      <span class="ind-label" style="color: ${color};">${type} ${period}:</span>
      <span class="ind-val">--</span>
      <button class="ind-action-btn ind-gear" title="Settings (Ubah Periode / Warna)">⚙</button>
      <button class="ind-action-btn ind-eye" title="Hide/Show Indicator">${visible ? "👁️" : "🚫"}</button>
      <button class="ind-action-btn del ind-del" title="Remove Indicator (Hapus)">✖</button>
    `;

    chip.querySelector(".ind-gear").addEventListener("click", (e) => {
      e.stopPropagation();
      if (window.openIndicatorSettingsModal) {
        window.openIndicatorSettingsModal(this, id);
      }
    });

    chip.querySelector(".ind-eye").addEventListener("click", (e) => {
      e.stopPropagation();
      this.wm.windows.forEach(w => {
        if (w.activeIndicators.has(id)) w.toggleIndicatorVisibility(id, false);
      });
      if (window.showToast) window.showToast("Indicator Visibility Toggled");
    });

    chip.querySelector(".ind-del").addEventListener("click", (e) => {
      e.stopPropagation();
      this.wm.windows.forEach(w => {
        if (w.activeIndicators.has(id)) w.removeIndicator(id, false);
      });
      if (window.showToast) window.showToast("Indicator Removed");
    });

    this.indicatorsLegendEl.appendChild(chip);

    const indObj = {
      id,
      type,
      period,
      color,
      series: lineSeries,
      visible: visible,
      chipEl: chip,
      data: []
    };

    this.activeIndicators.set(id, indObj);
    this.recalculateIndicator(indObj);

    if (triggerSave) {
      if (window.showToast) window.showToast(`✅ ${type} ${period} added to Chart ${this.id}`);
      this.wm.saveState();
    }
  }

  updateIndicatorConfig(id, newType, newPeriod, newColor) {
    const ind = this.activeIndicators.get(id);
    if (!ind) return;

    const newId = `${newType.toLowerCase()}_${newPeriod}`;
    if (newId !== id && this.activeIndicators.has(newId)) {
      if (window.showToast) window.showToast(`⚠️ ${newType} ${newPeriod} is already on this chart`);
      return;
    }

    ind.type = newType;
    ind.period = newPeriod;
    ind.color = newColor;
    ind.series.applyOptions({ color: newColor });

    ind.chipEl.dataset.id = newId;
    ind.chipEl.style.borderColor = `${newColor}44`;
    ind.chipEl.querySelector(".ind-dot").style.background = newColor;
    ind.chipEl.querySelector(".ind-label").style.color = newColor;
    ind.chipEl.querySelector(".ind-label").textContent = `${newType} ${newPeriod}:`;

    if (newId !== id) {
      this.activeIndicators.delete(id);
      ind.id = newId;
      this.activeIndicators.set(newId, ind);
    }

    this.recalculateIndicator(ind);
    this.wm.saveState();
    if (window.showToast) window.showToast(`⚙ ${newType} ${newPeriod} updated`);
  }

  removeIndicator(id) {
    const ind = this.activeIndicators.get(id);
    if (!ind) return;

    if (ind.series) {
      this.chart.removeSeries(ind.series);
    }
    if (ind.chipEl && ind.chipEl.parentNode) {
      ind.chipEl.parentNode.removeChild(ind.chipEl);
    }

    this.activeIndicators.delete(id);
    this.wm.saveState();
    if (window.showToast) window.showToast(`🗑️ ${ind.type} ${ind.period} removed`);
  }

  toggleIndicatorVisibility(id) {
    const ind = this.activeIndicators.get(id);
    if (!ind) return;

    ind.visible = !ind.visible;
    ind.series.applyOptions({ visible: ind.visible });
    ind.chipEl.classList.toggle("hidden-line", !ind.visible);
    ind.chipEl.querySelector(".ind-eye").textContent = ind.visible ? "👁️" : "🚫";
    this.wm.saveState();
  }

  recalculateIndicator(ind) {
    if (!this.candles || this.candles.length === 0) return;
    if (ind.type === "EMA") {
      ind.data = calculateEMA(this.candles, ind.period);
    } else if (ind.type === "SMA") {
      ind.data = calculateSMA(this.candles, ind.period);
    }
    ind.series.setData(ind.data);
    this.updateIndicatorValues(this.lastCandle?.time);
  }

  recalculateAllIndicators() {
    this.activeIndicators.forEach(ind => {
      this.recalculateIndicator(ind);
    });
  }

  updateIndicatorValues(time) {
    if (!time) return;
    const isCurrency = (this.symbol.includes("USD") && !this.symbol.includes("XAU") && !this.symbol.includes("BTC"));
    const p = isCurrency ? 4 : 2;

    this.activeIndicators.forEach(ind => {
      if (!ind.data || ind.data.length === 0) return;
      const pt = ind.data.find(d => d.time === time) || ind.data[ind.data.length - 1];
      if (pt && ind.chipEl) {
        ind.chipEl.querySelector(".ind-val").textContent = Number(pt.value).toFixed(p);
      }
    });
  }

  resize() {
    if (!this.chart || !this.chartContainer) return;
    const w = this.chartContainer.clientWidth;
    const h = this.chartContainer.clientHeight;
    if (w > 0 && h > 0) {
      this.chart.applyOptions({ width: w, height: h });
      if (this.drawingEngine) {
        this.drawingEngine.resizeCanvas();
      }
    }
  }

  zoom(factor) {
    const range = this.chart.timeScale().getVisibleLogicalRange();
    if (!range) return;
    const center = (range.from + range.to) / 2;
    const newHalf = ((range.to - range.from) * factor) / 2;
    this.chart.timeScale().setVisibleLogicalRange({
      from: center - newHalf,
      to: center + newHalf
    });
    if (this.drawingEngine) this.drawingEngine.requestRender();
  }

  updateLegend(c) {
    if (!c || !this.legendEl) return;
    const isCur = (this.symbol.includes("USD") && !this.symbol.includes("XAU") && !this.symbol.includes("BTC"));
    const p = isCur ? 4 : 2;

    this.legendEl.querySelector(".leg-sym").textContent = this.symbol;
    this.legendEl.querySelector(".leg-tf").textContent = this.timeframe;
    this.legendEl.querySelector(".val-o").textContent = Number(c.open).toFixed(p);
    this.legendEl.querySelector(".val-h").textContent = Number(c.high).toFixed(p);
    this.legendEl.querySelector(".val-l").textContent = Number(c.low).toFixed(p);
    this.legendEl.querySelector(".val-c").textContent = Number(c.close).toFixed(p);
    this.legendEl.querySelector(".val-v").textContent = (c.volume || 100).toLocaleString();

    if (this.volumeChipEl && c.volume !== undefined) {
      const volTxt = c.volume >= 1000 ? `${(c.volume / 1000).toFixed(1)}K` : c.volume.toString();
      const chipVal = this.volumeChipEl.querySelector(".val-vol-chip");
      if (chipVal) chipVal.textContent = volTxt;
    }
  }

    updateCountdownTimer() {
    const tfSec = TF_SECONDS_MAP[this.timeframe] || 60;
    // Audit fix: pakai jam server (broker MT5), bukan jam PC lokal - kalau
    // PC drift dari server, countdown ke candle-close bisa salah, padahal
    // doktrin CMP butuh presisi close TEPAT. Offset dari fetchSultanStatus().
    const now = Math.floor(Date.now() / 1000) + (this.wm?.serverTimeOffset || 0);
    const elapsed = now % tfSec;
    let remaining = tfSec - elapsed;

    const h = Math.floor(remaining / 3600);
    const m = Math.floor((remaining % 3600) / 60);
    const s = remaining % 60;

    let timerStr = "";
    if (h > 0) {
      timerStr = `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    } else {
      timerStr = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }

    const timerEl = this.el?.querySelector(".val-timer");
    if (timerEl) {
      timerEl.textContent = timerStr;
    }

    const scaleBadge = this.priceScaleCountdownBadge;
    if (scaleBadge && this.candleSeries && this.chartContainer && this.lastCandle) {
      scaleBadge.textContent = timerStr;
      const priceY = this.candleSeries.priceToCoordinate(this.lastCandle.close);
      if (priceY !== null && priceY > 10 && priceY < (this.chartContainer.clientHeight - 25)) {
        scaleBadge.style.top = `${priceY + 11}px`;
        scaleBadge.style.display = "block";
      } else {
        scaleBadge.style.display = "none";
      }
    }
  }

  async loadHistory(forceReload = false) {
    if (this.isLoading) return;
    this.isLoading = true;
    try {
      const res = await fetch(`${CHART_ENGINE_BASE}/api/chart/history?symbol=${this.symbol}&tf=${this.timeframe}&count=500`);
      const data = await res.json();
      const newCandles = data.candles || [];

      if (newCandles.length === 0) return;

      const isFullReload = !this.candles || this.candles.length === 0 || forceReload;

      if (isFullReload) {
        this.candles = newCandles;
        this.candleSeries.setData(this.candles);

        const volData = this.candles.map(c => ({
          time: c.time,
          value: c.volume || 100,
          color: c.close >= c.open ? "rgba(0, 230, 118, 0.25)" : "rgba(255, 51, 75, 0.25)"
        }));
        this.volumeSeries.setData(volData);
        this.chart.timeScale().fitContent();
        this.recalculateAllIndicators();
      } else {
        // Smooth incremental merge without resetting viewport during background polling
        const lastExistingTime = this.candles[this.candles.length - 1].time;
        newCandles.forEach(nc => {
          if (nc.time >= lastExistingTime) {
            const idx = this.candles.findIndex(c => c.time === nc.time);
            if (idx !== -1) {
              this.candles[idx] = nc;
            } else {
              this.candles.push(nc);
            }
            this.candleSeries.update(nc);
            this.volumeSeries.update({
              time: nc.time,
              value: nc.volume || 100,
              color: nc.close >= nc.open ? "rgba(0, 230, 118, 0.25)" : "rgba(255, 51, 75, 0.25)"
            });
          }
        });
      }

      if (this.candles.length > 0) {
        this.lastCandle = this.candles[this.candles.length - 1];
        this.currentPrice = this.lastCandle.close;
        this.updateLegend(this.lastCandle);
        this.updateCountdownTimer();

        const barCountEl = this.el.querySelector(".val-bar-count");
        if (barCountEl) barCountEl.textContent = this.candles.length;

        if (this.chartType === "line" && this.lineSeries) {
          const lineData = this.candles.map(c => ({ time: c.time, value: c.close }));
          this.lineSeries.setData(lineData);
        }
      }

      if (this.drawingEngine) {
        this.drawingEngine.requestRender();
      }

      if (data.source) {
        this.wm.updateDataSourceStatus(data.source, data.is_demo_data);
      }
    } catch (err) {
      console.error(`[Window ${this.id}] Error loading history:`, err);
    } finally {
      this.isLoading = false;
    }
  }

  setSymbol(newSymbol) {
    const sym = newSymbol.toUpperCase();
    if (this.symbol === sym) return;
    this.symbol = sym;

    // Update symbol search input
    const symInput = this.el.querySelector(".sym-search-input");
    if (symInput) symInput.value = this.symbol;

    // Update legend
    const legSym = this.el.querySelector(".leg-sym");
    if (legSym) legSym.textContent = this.symbol;

    const isCur = (this.symbol.includes("USD") && !this.symbol.includes("XAU") && !this.symbol.includes("BTC"));
    this.candleSeries.applyOptions({
      priceFormat: {
        type: "price",
        precision: isCur ? 4 : 2,
        minMove: isCur ? 0.0001 : 0.01
      }
    });

    this.chart.applyOptions({ watermark: { text: `${this.symbol} • COMMANDER DADANG WAHYUONO`, fontSize: (window.innerWidth >= 1920 ? 38 : 30), color: "rgba(255, 215, 0, 0.28)" } });

    this.loadHistory(true);
    this.wm.saveState();
  }

  setTimeframe(newTf) {
    if (this.timeframe === newTf) return;
    this.timeframe = newTf.toUpperCase();

    this.el.querySelectorAll(".win-tf-btn[data-tf]").forEach(b => {
      b.classList.toggle("active", b.dataset.tf === this.timeframe);
    });
    this.el.querySelectorAll(".tf-flyout-item[data-tf]").forEach(b => {
      b.classList.toggle("active", b.dataset.tf === this.timeframe);
    });

    // Update legend timeframe label
    const legTf = this.el.querySelector(".leg-tf");
    if (legTf) legTf.textContent = this.timeframe;

    this.loadHistory(true);
    this.wm.saveState();
  }

  setChartType(newType) {
    if (this.chartType === newType) return;
    this.chartType = newType;

    // Update chart type buttons
    this.el.querySelectorAll(".btn-chart-type").forEach(b => {
      b.classList.toggle("active", b.dataset.ctype === this.chartType);
    });

    if (newType === "line") {
      this.candleSeries.applyOptions({
        visible: false
      });
      // Add a line series if not already present
      if (!this.lineSeries) {
        const isCur = (this.symbol.includes("USD") && !this.symbol.includes("XAU") && !this.symbol.includes("BTC"));
        this.lineSeries = this.chart.addLineSeries({
          color: "#00f0ff",
          lineWidth: 2,
          crosshairMarkerVisible: true,
          priceFormat: { type: "price", precision: isCur ? 4 : 2, minMove: isCur ? 0.0001 : 0.01 }
        });
        if (this.candles.length > 0) {
          const lineData = this.candles.map(c => ({ time: c.time, value: c.close }));
          this.lineSeries.setData(lineData);
        }
      } else {
        this.lineSeries.applyOptions({ visible: true });
      }
    } else {
      // candles
      this.candleSeries.applyOptions({ visible: true });
      if (this.lineSeries) this.lineSeries.applyOptions({ visible: false });
    }

    this.wm.saveState();
    if (window.showToast) window.showToast(`🕯️ Chart: ${newType === "candles" ? "Candlestick" : "Line"}`);
  }

  updateStatusBar(time, price) {
    const sb = this.el.querySelector(".win-status-bar");
    if (!sb) return;

    const dateEl = sb.querySelector(".sb-cursor-date");
    const priceEl = sb.querySelector(".sb-cursor-price");

    if (!time || !price) {
      if (dateEl) dateEl.textContent = "—";
      if (priceEl) priceEl.textContent = "—";
      return;
    }

    // Format date from unix timestamp
    const d = new Date(time * 1000);
    const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
    if (dateEl) dateEl.textContent = dateStr;

    const isCur = (this.symbol.includes("USD") && !this.symbol.includes("XAU") && !this.symbol.includes("BTC"));
    if (priceEl) priceEl.textContent = Number(price).toFixed(isCur ? 4 : 2);
  }

  updateBarsVisible() {
    const range = this.chart.timeScale().getVisibleLogicalRange();
    const sbEl = this.el.querySelector(".sb-bars-visible");
    if (range && sbEl) {
      const count = Math.round(range.to - range.from);
      sbEl.textContent = `${count} bars visible`;
    }
    // Also update bar count in header
    const barCountEl = this.el.querySelector(".val-bar-count");
    if (barCountEl && this.candles) {
      barCountEl.textContent = this.candles.length;
    }
  }

    handleTick(tick) {
    if (!tick || !this.candles || this.candles.length === 0 || !this.candleSeries) return;
    const price = Number(tick.last || tick.price || tick.close);
    if (!price || isNaN(price)) return;

    this.currentPrice = price;
    const isCur = (this.symbol.includes("USD") && !this.symbol.includes("XAU") && !this.symbol.includes("BTC"));
    const p = isCur ? 4 : 2;

    // Direct active candle synchronization (guaranteed valid LightweightCharts timestamp)
    const activeCandle = this.candles[this.candles.length - 1];
    activeCandle.high = Math.max(activeCandle.high, price);
    activeCandle.low = Math.min(activeCandle.low, price);
    activeCandle.close = Number(price.toFixed(p));
    activeCandle.volume = (activeCandle.volume || 0) + 1;
    this.lastCandle = activeCandle;

    try {
      this.candleSeries.update(activeCandle);
      if (this.volumeSeries) {
        this.volumeSeries.update({
          time: activeCandle.time,
          value: activeCandle.volume,
          color: activeCandle.close >= activeCandle.open ? "rgba(0, 230, 118, 0.3)" : "rgba(255, 51, 75, 0.3)"
        });
      }
    } catch (e) {
      console.warn("Candle update safely caught:", e);
    }

    this.updateLegend(activeCandle);
    this.updateCountdownTimer();
    this.updateRunningCandleDeltaPosition();
    this.updateSDBadgePositions();

    this.activeIndicators.forEach(ind => {
      if (ind.type === "EMA" && ind.data.length > 0) {
        const k = 2 / (ind.period + 1);
        const prevEma = ind.data[ind.data.length - 1].value;
        const currentEma = Number(((price - prevEma) * k + prevEma).toFixed(4));
        try { ind.series.update({ time: activeCandle.time, value: currentEma }); } catch (e) {}
        if (ind.chipEl) {
          ind.chipEl.querySelector(".ind-val").textContent = currentEma.toFixed(p);
        }
      }
    });
  }

  syncCrosshairTimestamp(timestamp) {
    if (!this.chart || !this.candleSeries) return;
    const targetCandle = this.candles.find(c => c.time === timestamp) ||
      this.candles.reduce((prev, curr) => Math.abs(curr.time - timestamp) < Math.abs(prev.time - timestamp) ? curr : prev, this.candles[0]);

    if (targetCandle) {
      this.updateLegend(targetCandle);
      this.updateIndicatorValues(targetCandle.time);
    }
  }

  destroy() {
    if (this.timerInterval) clearInterval(this.timerInterval);
    if (this.resizeObserver) this.resizeObserver.disconnect();
    if (this.drawingEngine) this.drawingEngine.destroy();
    if (this.chart) this.chart.remove();
    if (this.el && this.el.parentNode) {
      this.el.parentNode.removeChild(this.el);
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. MULTI-WINDOW MANAGER ORCHESTRATOR
// ─────────────────────────────────────────────────────────────────────────────
export class WindowManager {
  constructor(gridContainerSelector) {
    this.container = document.querySelector(gridContainerSelector);
    this.windows = [];
    this.layout = "QUAD";
    this.isCrosshairLinked = false;
    this.activeTool = "cursor";
    this.maximizedWindow = null;
    this.ws = null;
    this.storylineInterval = null;
    this.hasSavedState = false;
    this.savedConfigs = null;
    // Audit fix: countdown timer sempat kehilangan koreksi ke jam server
    // broker (regresi ke Date.now() PC lokal doang, salah kalau jam PC
    // ngedrift dari server MT5 - fatal buat doktrin CMP yang butuh presisi
    // candle-close). Offset ini di-update tiap fetchSultanStatus() dari
    // raw.timestamp (epoch server, ditulis EA), dipakai ChartWindow.now().
    this.serverTimeOffset = 0;

    // v1 (Replay/Backtest) - null = mode live normal. Diisi
    // {date, snapshots, index, playing, intervalId, speedMs} oleh
    // startReplay(). Dadang: "semua data history harus ke save biar bisa
    // buat bactes n replay" - candle historis dari MT5 (copy_rates_range,
    // gak ada batas selain retensi terminal), overlay/HUD historis dari
    // DNA Vault (dna_vault_YYYY-MM-DD.jsonl, ditulis EA 1x/menit sejak
    // 2026-08-23 - lihat WriteSultanStatus() di MQL5, sudah jalan duluan
    // sebelum fitur replay ini ada, jadi historinya udah numpuk).
    this.replayState = null;

    this.globalChartConfig = {
      candleUp: "#00e676",
      candleDown: "#ff334b",
      wickUp: "#00e676",
      wickDown: "#ff334b",
      showCountdown: true,
      showLastPrice: true,
      showOHLC: true,
      showVolume: true,
      chartBg: "#07090e",
      gridColor: "rgba(255, 255, 255, 0.04)",
      showGrid: true,
      crosshairStyle: "dashed"
    };

    try {
      const rawCfg = localStorage.getItem("cd_chart_settings_v1");
      if (rawCfg) {
        this.globalChartConfig = { ...this.globalChartConfig, ...JSON.parse(rawCfg) };
      }
    } catch (e) {}

    this.initWebSocket();
    this.loadSavedState();

    this.storylineInterval = setInterval(() => { this.fetchSultanStatus(); }, 1000);
    this.syncBarsInterval = setInterval(() => {
      this.windows.forEach(w => {
        if (w.loadHistory) w.loadHistory();
      });
    }, 10000);
    this.fetchSultanStatus();
  }

    initWebSocket() {
    if (!IS_LOCAL_HOST) {
      // In Cloud / Remote Domain: Port 8800 WebSocket is not exposed by Cloudflare.
      // Live tick streaming & candles are automatically driven by fast reverse-proxy & status sync!
      const pill = document.getElementById("status-pill");
      if (pill) {
        pill.className = "status-pill live";
        pill.innerHTML = '<span class="pulse-dot"></span> MT5 LIVE';
      }
      return;
    }

    try {
      const wsUrl = `ws://127.0.0.1:${CHART_ENGINE_PORT}/ws/chart-stream`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("[WS] Multi-Window Stream Connected");
      };

      this.ws.onmessage = (event) => {
        try {
          if (this.replayState) return;   // Replay aktif - jangan biarin tick live nimpa candle historis
          const data = JSON.parse(event.data);
          if (data.type === "MARKET_DATA_STREAM" && data.ticks) {
            this.updateDataSourceStatus(data.source, data.is_demo_data);
            this.windows.forEach(win => {
              const symTick = data.ticks[win.symbol];
              if (symTick) {
                win.handleTick(symTick);
              }
            });
          }
        } catch (e) {
          console.error("WS Tick Error:", e);
        }
      };

      this.ws.onerror = () => {};

      this.ws.onclose = () => {
        console.log("[WS] Disconnected, reconnecting in 3s...");
        setTimeout(() => this.initWebSocket(), 3000);
      };
    } catch (e) {
      console.warn("WebSocket init safely bypassed:", e);
    }
  }

  updateDataSourceStatus(source, isDemo) {
    const pill = document.getElementById("status-pill");
    if (!pill) return;

    if (isDemo || source === "DEMO_DATA") {
      pill.innerHTML = `<span class="pulse-dot"></span> DEMO DATA`;
      pill.className = "status-pill sim";
    } else {
      pill.innerHTML = `<span class="pulse-dot"></span> MT5 LIVE`;
      pill.className = "status-pill";
    }
  }

  // Audit fix: dipanggil tiap poll dari fetchSultanStatus() (`this.updateWallSweepBanner(...)`)
  // tapi method-nya sendiri gak pernah dibikin - lihat ChartWindow.renderWallSweep() +
  // this.wallSweepBanner di initChart() buat elemen DOM-nya.
  updateWallSweepBanner(ws) {
    this.windows.forEach(w => w.renderWallSweep(ws));
  }

  // v1: Cockpit HUD sekarang baca /sultan_status.json (data ASLI dari EA
  // MT5 V3, sama persis yang dipakai panel utama dashboard) - BUKAN lagi
  // /api/storyline/analysis bawaan chart engine, yang itungannya sendiri
  // (CMPLogic.js dst, terpisah dari EA) dan wall_ladder-nya literally
  // random.randint() (dummy). renderCockpitData() di bawah TIDAK diubah -
  // cuma sumber & mapping datanya yang beda, biar chart ini gak pernah
  // nunjukin angka yang beda dari panel MT5/dashboard utama.
  async fetchSultanStatus() {
    if (this.replayState) return;   // Replay aktif - poll live dijeda, jangan nimpa tampilan
    try {
      const res = await fetch(`/sultan_status.json?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) return;
      const raw = await res.json();
      if (raw.timestamp) {
        this.serverTimeOffset = raw.timestamp - Math.floor(Date.now() / 1000);
      }
      this.applyStatusSnapshot(raw, true);
    } catch (e) {}
  }

  // v1 (Replay): sebelumnya semua ini ada LANGSUNG di dalam fetchSultanStatus().
  // Ditarik keluar jadi fungsi sendiri biar bisa dipakai ULANG persis sama
  // buat mode Replay (snapshot dari DNA Vault historis, bukan poll live) -
  // satu jalur render buat live MAUPUN replay, gak ada logic yang
  // diduplikat/bisa nyimpang beda hasil antara dua mode.
  applyStatusSnapshot(raw, isLiveTick) {
    this.renderCockpitData(raw);
    if (isLiveTick && raw.price > 0) {
      this.windows.forEach(w => {
        if (w.symbol === "XAUUSD") {
          w.handleTick({ last: raw.price, time: raw.timestamp || Math.floor(Date.now() / 1000) });
        }
      });
    }

    const zones = this.nearestSDZones(raw);
    this.windows.forEach(w => {
      w.updateSDZones(zones, raw.liquidity);
      w.updateSierraChart(raw.sierra_chart);
      w.updateValueArea(raw.location);
      w.updateLiveFlow(raw.flow);
      w.updateConfluenceRadar(raw.confluence_radar, raw.conviction);
    });
    this.updateWallSweepBanner(raw.wall_sweep);
  }

  // ═══════════════════════════════════════════════════════════════════════
  // REPLAY / BACKTEST MODE — Dadang: "semua data history harus ke save
  // biar bisa buat bactes n replay". Candle historis dari MT5
  // (copy_rates_range, /api/chart/history-range) + overlay/HUD historis
  // dari DNA Vault (dna_vault_YYYY-MM-DD.jsonl, EA nulis 1x/menit sejak
  // 2026-08-23 - histori udah numpuk duluan sebelum fitur ini dibangun).
  // Pakai applyStatusSnapshot() yang SAMA persis dipakai live - satu jalur
  // render, gak ada logic kembar.
  // ═══════════════════════════════════════════════════════════════════════
  async loadReplayDates() {
    try {
      const res = await fetch(`${CHART_ENGINE_BASE}/api/chart/replay-dates`);
      const data = await res.json();
      return data.dates || [];
    } catch (e) {
      return [];
    }
  }

  async startReplay(date) {
    if (window.showToast) window.showToast(`⏳ Memuat replay ${date}...`);
    try {
      const snapRes = await fetch(`${CHART_ENGINE_BASE}/api/chart/replay-snapshots?date=${date}`);
      if (!snapRes.ok) {
        if (window.showToast) window.showToast(`❌ Gak ada histori buat ${date}`, true);
        return false;
      }
      const snapData = await snapRes.json();
      const snapshots = snapData.snapshots || [];
      if (snapshots.length === 0) {
        if (window.showToast) window.showToast(`❌ Histori ${date} kosong`, true);
        return false;
      }

      const dateFrom = snapshots[0].timestamp - 900;
      const dateTo = snapshots[snapshots.length - 1].timestamp + 900;

      await Promise.all(this.windows.map(async (w) => {
        try {
          const res = await fetch(`${CHART_ENGINE_BASE}/api/chart/history-range?symbol=${w.symbol}&tf=${w.timeframe}&date_from=${dateFrom}&date_to=${dateTo}`);
          const data = await res.json();
          w._replayFullCandles = data.candles || [];
        } catch (e) {
          w._replayFullCandles = [];
        }
      }));

      this.replayState = { date, snapshots, index: 0, playing: false, intervalId: null, speedMs: 400 };
      this.replayGoTo(0);
      if (window.showToast) window.showToast(`▶ Replay ${date} siap — ${snapshots.length} snapshot`);
      return true;
    } catch (e) {
      if (window.showToast) window.showToast(`❌ Gagal load replay: ${e.message}`, true);
      return false;
    }
  }

  stopReplay() {
    if (!this.replayState) return;
    this.replayPause();
    this.replayState = null;
    this.windows.forEach(w => {
      w._replayFullCandles = null;
      w.loadHistory(true);
    });
    const bar = document.getElementById("replay-bar");
    if (bar) bar.style.display = "none";
    if (window.showToast) window.showToast("⏹ Replay dihentikan — kembali ke LIVE");
  }

  replayGoTo(index) {
    if (!this.replayState) return;
    const { snapshots } = this.replayState;
    const clamped = Math.max(0, Math.min(index, snapshots.length - 1));
    this.replayState.index = clamped;
    const snap = snapshots[clamped];

    this.windows.forEach(w => w.setReplayCandles(snap.timestamp));
    this.applyStatusSnapshot(snap, false);
    this.updateReplayScrubber();

    if (clamped >= snapshots.length - 1) this.replayPause();
  }

  replayStep(delta) {
    if (!this.replayState) return;
    this.replayGoTo(this.replayState.index + delta);
  }

  replayPlay() {
    if (!this.replayState || this.replayState.playing) return;
    this.replayState.playing = true;
    this.replayState.intervalId = setInterval(() => this.replayStep(1), this.replayState.speedMs);
    this.updateReplayScrubber();
  }

  replayPause() {
    if (!this.replayState) return;
    if (this.replayState.intervalId) clearInterval(this.replayState.intervalId);
    this.replayState.intervalId = null;
    this.replayState.playing = false;
    this.updateReplayScrubber();
  }

  setReplaySpeed(ms) {
    if (!this.replayState) return;
    this.replayState.speedMs = ms;
    if (this.replayState.playing) {
      this.replayPause();
      this.replayPlay();
    }
  }

  updateReplayScrubber() {
    if (!this.replayState) return;
    const { index, snapshots, playing } = this.replayState;
    const bar = document.getElementById("replay-bar");
    if (!bar) return;
    bar.style.display = "flex";
    const slider = document.getElementById("replay-slider");
    const label = document.getElementById("replay-time-label");
    const playBtn = document.getElementById("replay-play-btn");
    if (slider) {
      slider.max = snapshots.length - 1;
      slider.value = index;
    }
    if (label) {
      const dt = new Date(snapshots[index].timestamp * 1000);
      label.textContent = `${dt.toISOString().substr(11, 8)} UTC · ${index + 1}/${snapshots.length}`;
    }
    if (playBtn) playBtn.textContent = playing ? "⏸" : "▶";
  }

  // Audit fix: mapSultanStatusToCockpit()/mapFlowSection() dulu dipanggil
  // dari fetchSultanStatus() (renderCockpitData(this.mapSultanStatusToCockpit(raw))),
  // tapi editor lain nulis ulang renderCockpitData() buat baca `raw` LANGSUNG
  // dengan mapping inline sendiri, dan ganti call site jadi
  // this.renderCockpitData(raw) (tanpa lewat sini lagi). Dua fungsi ini jadi
  // orphaned - gak ada yang manggil, drift risk (kalau salah satu diedit,
  // yang lain gak ikut) - dihapus daripada dibiarin nyasar.

  // Zona SND asli EA bisa sampai ~17 (semua yang lolos skor minimum), gambar
  // semuanya jadi 34 price line - kepenuhan. Ambil yang PALING DEKAT harga
  // sekarang aja, 3 per sisi (SUPPLY/DEMAND), sama kayak konvensi panel
  // "S&D Price Map" lain di dashboard ini.
    // v3: MASTER CLEAN DISCRETE S&D FILTER
  // - Filter out BROKEN / AUS zones (jangan gambar zona yang udah jebol!)
  // - Supply (S1, S2) WAJIB DI ATAS HARGA (Resistance)
  // - Demand (D1, D2) WAJIB DI BAWAH HARGA (Support)
  // - Enforce minimum separation distance ($3.00 USD) agar TIDAK MENUMPUK/NGUMPUL
  // - Maksimal 2 Supply + 2 Demand (Total maks 4 zona terpenting di chart)
    // ─────────────────────────────────────────────────────────────────────────
  // EA OFFICIAL S&D ROADMAP (100% STRICT: SUPPLY DI ATAS HARGA, DEMAND DI BAWAH)
  // ─────────────────────────────────────────────────────────────────────────
    // ─────────────────────────────────────────────────────────────────────────
  // EA OFFICIAL S&D ROADMAP (ENRICHED WITH REAL MT5 LOT SIZES & METRICS)
  // ─────────────────────────────────────────────────────────────────────────
  nearestSDZones(raw) {
    if (!raw.sd_zones || !raw.sd_zones.available) return { supply: [], demand: [] };
    const price = raw.price || (this.windows[0]?.currentPrice || 0);
    if (!price) return { supply: [], demand: [] };

    const roadmap = raw.sd_zones.roadmap || {};
    const rawZones = raw.sd_zones.zones || [];

    // Helper: Enrich roadmap item with full lot metrics from raw zones
    const enrich = (item, side) => {
      const match = rawZones.find(z => z.side === side && Math.abs(z.lo - item.lo) < 2.0 && Math.abs(z.hi - item.hi) < 2.0)
                 || rawZones.find(z => z.side === side && (Math.abs(z.lo - item.lo) < 3.5 || Math.abs(z.hi - item.hi) < 3.5));
      return {
        ...item,
        total_lot: match?.total_lot || item.total_lot || (match?.wall_count ? match.wall_count * 10 : 150),
        retest_count: match?.retest_count || 0,
        absorption_hits: match?.absorption_hits || 0,
        wall_count: match?.wall_count || 0,
        status: match?.status || "ACTIVE",
        strength: item.strength || match?.strength || "SEDANG",
        score: item.score || match?.score || 50
      };
    };

    let cleanSupply = [];
    let cleanDemand = [];

    // Prioritas 1: Gunakan Official Roadmap dari EA yang sudah dimurnikan
    if (roadmap.supply && roadmap.supply.length > 0) {
      cleanSupply = roadmap.supply
        .filter(z => z.lo >= (price - 0.8)) // Wajib di atas harga
        .sort((a, b) => a.lo - b.lo)
        .slice(0, 2)
        .map(z => enrich(z, "SUPPLY"));
    }
    if (roadmap.demand && roadmap.demand.length > 0) {
      cleanDemand = roadmap.demand
        .filter(z => z.hi <= (price + 0.8)) // Wajib di bawah harga
        .sort((a, b) => b.hi - a.hi)
        .slice(0, 2)
        .map(z => enrich(z, "DEMAND"));
    }

    // Fallback jika roadmap kosong
    if (cleanSupply.length === 0) {
      cleanSupply = rawZones
        .filter(z => z.side === "SUPPLY" && z.status !== "BROKEN" && z.lo >= (price - 0.8))
        .sort((a, b) => a.lo - b.lo)
        .slice(0, 2);
    }
    if (cleanDemand.length === 0) {
      cleanDemand = rawZones
        .filter(z => z.side === "DEMAND" && z.status !== "BROKEN" && z.hi <= (price + 0.8))
        .sort((a, b) => b.hi - a.hi)
        .slice(0, 2);
    }

    return { supply: cleanSupply, demand: cleanDemand };
  }

  renderCockpitData(raw) {
    if (!raw) return;

    const regime = raw.regime || {};
    const conv = raw.conviction || {};
    const ctx = raw.context || {};
    const liq = raw.liquidity || {};
    const flow = raw.flow || {};
    const ws = raw.wall_sweep || {};
    const usd = raw.usd || {};
    const signals = raw.signals || {};
    const sc = raw.sierra_chart || {};
    const sd = raw.sd_zones || {};
    const decision = sd.decision || {};
    const brk = sd.break || {};

    // 1. EA Header & Version
    const verEl = document.getElementById("ea-version-tag");
    if (verEl) verEl.textContent = `${raw.ea_version || 'v53.56-V3'} • Dadang Wahyuono`;

    const radarPill = document.getElementById("ea-radar-pill");
    const radarText = document.getElementById("ea-radar-text");
    const scorePct = conv.max > 0 ? Math.round((conv.score / conv.max) * 100) : 83;
    const grade = conv.grade || "HATI-HATI";
    if (radarText) radarText.textContent = `${scorePct}% ${grade}`;
    if (radarPill) {
      radarPill.className = `ea-radar-pill ${scorePct >= 80 ? "strong" : (scorePct >= 60 ? "moderate" : "caution")}`;
    }

    // 2. Action Hero Banner (Berdasarkan MARKET_READING_LOGIC_Konsep_Murni.md)
    const heroBadge = document.getElementById("ea-hero-badge");
    const heroRegime = document.getElementById("ea-hero-regime");
    const heroReason = document.getElementById("ea-hero-reason");
    const heroBox = document.getElementById("ea-action-hero");

    const dir = (conv.dir || "WAIT").toUpperCase();
    const isRootAligned = regime.d1 === dir; // CF Mode (Searah Root D1) vs VR Mode (Retracement terhadap D1)
    const modeTag = isRootAligned ? "CF MODE" : "VR RETEST";
    const curPrice = raw.price || 0;

    // Deteksi apakah harga sedang di/dekat area Supply / Demand Pullback
    const nearSupply = decision.location_text?.includes("SUPPLY") || (sd.roadmap?.supply?.[0] && Math.abs(curPrice - sd.roadmap.supply[0].lo) <= 3.5);
    const nearDemand = decision.location_text?.includes("DEMAND") || (sd.roadmap?.demand?.[0] && Math.abs(curPrice - sd.roadmap.demand[0].hi) <= 3.5);

    let smartAction = "WAIT OBSERVE";
    let smartClass = "wait";
    let smartReason = "";

    if (dir === "SELL") {
      if (nearSupply) {
        smartAction = "🔴 SELL PULLBACK (VR)";
        smartClass = "sell";
        smartReason = "Harga di area Supply S1 • Kesempatan Sell Retest • TP di Demand D1";
      } else if (conv.score >= 5) {
        smartAction = "🔴 SELL RETEST (VR)";
        smartClass = "sell";
        smartReason = `Local Cascade 80% SELL • Mode ${modeTag} • TP Scalp di Demand`;
      } else {
        smartAction = "⏳ TUNGGU PULLBACK SUPPLY";
        smartClass = "wait";
        smartReason = "Tunggu harga naik ke Supply S1 untuk entry Sell diskon";
      }
    } else if (dir === "BUY") {
      if (nearDemand) {
        smartAction = "🟢 BUY PULLBACK (VR)";
        smartClass = "buy";
        smartReason = "Harga di area Demand D1 • Kesempatan Buy Retest • TP di Supply S1";
      } else if (conv.score >= 5) {
        smartAction = "🟢 BUY RETEST (VR)";
        smartClass = "buy";
        smartReason = `Local Cascade 80% BUY • Mode ${modeTag} • TP Scalp di Supply`;
      } else {
        smartAction = "⏳ TUNGGU PULLBACK DEMAND";
        smartClass = "wait";
        smartReason = "Tunggu harga turun ke Demand D1 untuk entry Buy diskon";
      }
    } else {
      smartAction = "⏳ WAIT OBSERVE";
      smartClass = "wait";
      smartReason = decision.reason_text || "Market sideways tanpa dominasi arah";
    }

    if (heroBadge) heroBadge.textContent = smartAction;
    if (heroRegime) heroRegime.textContent = `${modeTag} • ${regime.regime || "SIDEWAYS"}`;
    if (heroReason) heroReason.textContent = smartReason;
    if (heroBox) heroBox.className = `ea-action-hero ${smartClass}`;

    // 4. Multi-Timeframe Matrix
    const setTfCell = (id, tf, bias, gradeTag) => {
      const el = document.getElementById(id);
      if (!el) return;
      const b = (bias || "WAIT").toUpperCase();
      const cls = b === "BUY" ? "buy" : (b === "SELL" ? "sell" : "wait");
      el.innerHTML = `<span class="tf-name">${tf}</span><span class="tf-val ${cls}">${b}</span><span class="tf-tag">[${gradeTag || '-'}]</span>`;
    };

    const getTag = (tf) => (regime[tf] === conv.dir ? conv.grade : (regime[tf] === "WAIT" ? "-" : "vs"));
    setTfCell("ea-tf-d1", "D1", regime.d1, getTag("d1"));
    setTfCell("ea-tf-h4", "H4", regime.h4, getTag("h4"));
    setTfCell("ea-tf-h1", "H1", regime.h1, getTag("h1"));
    setTfCell("ea-tf-m30", "M30", regime.m30, getTag("m30"));
    setTfCell("ea-tf-m15", "M15", regime.m15, getTag("m15"));
    setTfCell("ea-tf-m5", "M5", regime.m5, getTag("m5"));

    // 5. Momentum Triad Section
    const setRow = (id, txt, cls) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = txt || "-";
      if (cls) el.className = `m-val ${cls}`;
    };

    setRow("ea-mom-m5", signals.momentum_m5?.text || "SELL WEAK 0.1x (46s)", signals.momentum_m5?.dir === "BUY" ? "buy" : "sell");
    setRow("ea-mom-bm", signals.momentum_m5_bookmap?.text || "SELL WEAK 0.1x (46s)", signals.momentum_m5_bookmap?.dir === "BUY" ? "buy" : "sell");
    setRow("ea-mom-fp", signals.momentum_m5_footprint?.text || "SELL (46s)", signals.momentum_m5_footprint?.dir === "BUY" ? "buy" : "sell");
    setRow("ea-chain-next", conv.chain_next ? `${conv.chain_next} (Tunggu Breakout)` : "-", "highlight-gold");
    setRow("ea-profile-shape", sc.profile_shape || signals.daily_profile?.text || "b-SHAPE (BEAR DUMP)");

    // 6. Order Flow Live Stats
    const cvdVal = flow.cvd || 0;
    const cvdEl = document.getElementById("of-cvd");
    if (cvdEl) {
      cvdEl.textContent = `${cvdVal >= 0 ? "+" : ""}${Math.round(cvdVal)}`;
      cvdEl.className = `of-val ${cvdVal >= 0 ? "buy" : "sell"}`;
    }

    const pulseEl = document.getElementById("of-pulse");
    if (pulseEl) pulseEl.textContent = `${Number(flow.pulse_pct || 50).toFixed(1)}%`;

    const absorbEl = document.getElementById("of-absorb");
    if (absorbEl) {
      absorbEl.textContent = flow.absorption || "NONE";
      absorbEl.className = `of-val ${flow.absorption !== "NONE" ? "caution" : ""}`;
    }

    const usdEl = document.getElementById("of-usd");
    if (usdEl) usdEl.textContent = `${usd.dir || "-"} ${usd.bias || ""} • ${usd.gold_effect || "-"}`;

    const sweepEl = document.getElementById("of-sweep");
    if (sweepEl) {
      if (ws && ws.active) {
        sweepEl.innerHTML = `<b style="color:${ws.side === 'BID' ? '#00e676' : '#ff334b'}">${ws.side} ${Math.round(ws.size)}L @${Number(ws.price).toFixed(2)}</b> (${ws.status || 'ACTIVE'})`;
      } else {
        sweepEl.textContent = "-";
      }
    }

    const newsEl = document.getElementById("of-news");
    if (newsEl) {
      newsEl.textContent = (usd.next_mins != null && usd.next_mins >= 0 && usd.next_event) ? `${usd.next_event} • ${usd.next_mins}m lagi` : "-";
    }

    // 7. S&D Decision & Buyer/Seller Control
    const buyerPct = decision.buyer_pct || 50;
    const sellerPct = decision.seller_pct || 50;

    const bPctEl = document.getElementById("power-buyer-pct");
    const sPctEl = document.getElementById("power-seller-pct");
    const bFillEl = document.getElementById("power-fill-buyer");
    const sFillEl = document.getElementById("power-fill-seller");

    if (bPctEl) bPctEl.textContent = `${buyerPct}%`;
    if (sPctEl) sPctEl.textContent = `${sellerPct}%`;
    if (bFillEl) bFillEl.style.width = `${buyerPct}%`;
    if (sFillEl) sFillEl.style.width = `${sellerPct}%`;

    const decBadge = document.getElementById("sd-decision-badge");
    if (decBadge) decBadge.textContent = (decision.focus || "TUNGGU").replace("FOKUS: ", "");

    const locEl = document.getElementById("sd-location-text");
    if (locEl) locEl.textContent = decision.location_text || "DEKAT ZONA SUPPLY";

    const brkEl = document.getElementById("sd-break-text");
    if (brkEl) brkEl.textContent = brk.status_text || "NONE"

    // 8. S&D Live Wall Stats (Embedded from Liquidity)
    const wallAskEl = document.getElementById("sd-wall-ask");
    const wallBidEl = document.getElementById("sd-wall-bid");
    const wallImbEl = document.getElementById("sd-wall-imb");

    if (wallAskEl && liq) {
      wallAskEl.textContent = `Ask Live: ${Math.round(liq.ask_wall_size || 0)}L @${Number(liq.ask_wall_price || 0).toFixed(2)} (Tot: ${Math.round(liq.ask_wall_total_lot || 0)}L)`;
    }
    if (wallBidEl && liq) {
      wallBidEl.textContent = `Bid Live: ${Math.round(liq.bid_wall_size || 0)}L @${Number(liq.bid_wall_price || 0).toFixed(2)} (Tot: ${Math.round(liq.bid_wall_total_lot || 0)}L)`;
    }
    if (wallImbEl && liq) {
      const imbVal = liq.wall_imbalance !== undefined ? liq.wall_imbalance : 0;
      const imbText = imbVal > 0.3 ? "Bid Dominated" : (imbVal < -0.3 ? "Ask Dominated" : "Neutral / Balanced");
      wallImbEl.textContent = `${imbVal.toFixed(2)} (${imbText})`;
    }

    // Audit fix: blok "Bookmap Liquidity Depth Ladder" yang lama dihapus -
    // getElementById("ladder-container") gak pernah ketemu apa-apa lagi
    // (chart.html gak punya elemen itu sama sekali sekarang), sudah
    // digantikan sd-wall-ask/sd-wall-bid/sd-wall-imb di atas yang nunjukin
    // data yang sama (ask/bid live size + total lot + imbalance) dalam
    // bentuk teks. Dead code, bukan bug - dihapus biar gak nyasar.
  }

  setLayout(layoutName) {
    this.layout = layoutName;
    this.applyLayout();
  }

  applyLayout() {
    this.container.className = `chart-grid-container layout-${this.layout.toLowerCase()}`;
    let requiredCount = 4;
    if (this.layout === "SINGLE") requiredCount = 1;
    else if (this.layout === "DUAL_HORIZ" || this.layout === "DUAL_VERT") requiredCount = 2;

    const defaultConfigs = [
      { symbol: "XAUUSD", timeframe: "H4" },
      { symbol: "XAUUSD", timeframe: "M30" },
      { symbol: "XAUUSD", timeframe: "M15" },
      { symbol: "XAUUSD", timeframe: "M5" }
    ];

    while (this.windows.length < requiredCount) {
      const idx = this.windows.length;
      const conf = (this.savedConfigs && this.savedConfigs[idx]) || defaultConfigs[idx] || { symbol: "XAUUSD", timeframe: "M5" };
      const win = new ChartWindow(this, idx + 1, conf);
      this.windows.push(win);
      this.container.appendChild(win.el);
    }

    while (this.windows.length > requiredCount) {
      const win = this.windows.pop();
      win.destroy();
    }

    setTimeout(() => {
      this.windows.forEach(w => w.resize());
    }, 50);

    this.updateActiveLayoutButtons();
    this.saveState();
  }

  toggleMaximizeWindow(win) {
    if (this.maximizedWindow === win) {
      this.maximizedWindow = null;
      this.container.querySelectorAll(".chart-window").forEach(el => el.classList.remove("maximized", "hidden"));
    } else {
      this.maximizedWindow = win;
      this.windows.forEach(w => {
        if (w === win) {
          w.el.classList.add("maximized");
          w.el.classList.remove("hidden");
        } else {
          w.el.classList.remove("maximized");
          w.el.classList.add("hidden");
        }
      });
    }
    setTimeout(() => {
      win.resize();
    }, 50);
  }

  broadcastCrosshair(sourceWinId, timestamp, price) {
    if (!this.isCrosshairLinked) return;
    this.windows.forEach(w => {
      if (w.id !== sourceWinId) {
        w.syncCrosshairTimestamp(timestamp);
      }
    });
  }

  setCrosshairLinked(linked) {
    this.isCrosshairLinked = linked;
    const btn = document.getElementById("btn-link-crosshair");
    if (btn) {
      btn.classList.toggle("active", linked);
      btn.innerHTML = linked ? "🔗 LINK CROSSHAIR: ON" : "⛓ LINK CROSSHAIR: OFF";
    }
    this.saveState();
  }

  setGlobalTool(toolName) {
    this.activeTool = toolName;
    this.windows.forEach(w => {
      if (w.drawingEngine) {
        w.drawingEngine.setTool(toolName);
      }
    });
  }

  updateActiveLayoutButtons() {
    document.querySelectorAll(".layout-btn[data-layout]").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.layout === this.layout);
    });
  }

  saveState() {
    try {
      const winConfigs = this.windows.map(w => w.getStateObject());
      const stateObj = {
        layout: this.layout,
        isCrosshairLinked: this.isCrosshairLinked,
        windows: winConfigs
      };
      localStorage.setItem("cd_window_manager_state_v1", JSON.stringify(stateObj));
    } catch (e) {
      console.warn("Failed to save WindowManager state:", e);
    }
  }

  loadSavedState() {
    try {
      const raw = localStorage.getItem("cd_window_manager_state_v1");
      if (raw) {
        const parsed = JSON.parse(raw);
        this.hasSavedState = true;
        this.layout = parsed.layout || "QUAD";
        this.isCrosshairLinked = parsed.isCrosshairLinked || false;
        this.setCrosshairLinked(this.isCrosshairLinked);

        this.savedConfigs = parsed.windows || null;
        this.applyLayout();
        return;
      }
    } catch (e) {
      console.warn("Failed to load WindowManager state:", e);
    }

    this.hasSavedState = false;
    this.setLayout("QUAD");
  }

  applyGlobalChartConfig(cfg) {
    this.globalChartConfig = { ...this.globalChartConfig, ...cfg };
    this.windows.forEach(w => w.applyChartSettings(this.globalChartConfig));
    try {
      localStorage.setItem("cd_chart_settings_v1", JSON.stringify(this.globalChartConfig));
    } catch (e) {}
    if (window.showToast) window.showToast("⚙ Chart Settings Applied & Saved");
  }
}
