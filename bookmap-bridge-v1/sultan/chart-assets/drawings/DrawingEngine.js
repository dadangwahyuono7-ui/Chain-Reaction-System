/**
 * ═══════════════════════════════════════════════════════════════════════════
 *  COMMANDER DADANG — BUTTERY-SMOOTH TRADINGVIEW DRAWING ENGINE (PHASE 1)
 *  By Dadang Wahyuono
 *  - 60/120 FPS requestAnimationFrame rendering
 *  - RIGID CANDLE-LOCKED ANCHORING (Zero Drift / Floating)
 *  - Object Lock Mode (🔒 Lock individual drawings to freeze handles)
 *  - Deselection on empty click & instant re-draw capabilities
 *  - Dual Click-Drag-Release & Click-Move-Click workflows
 * ═══════════════════════════════════════════════════════════════════════════
 */

import { globalDrawingStore } from './DrawingStore.js';
import { TF_SECONDS_MAP } from '../core/Constants.js';

export class DrawingEngine {
  constructor(chartWindowInstance) {
    this.win = chartWindowInstance;
    this.chart = chartWindowInstance.chart;
    this.series = chartWindowInstance.candleSeries;
    this.container = chartWindowInstance.chartContainer;
    this.store = globalDrawingStore;

    // High-DPI Overlay Canvas
    this.canvas = document.createElement("canvas");
    this.canvas.className = "drawing-canvas-overlay";
    this.ctx = this.canvas.getContext("2d");
    this.container.appendChild(this.canvas);

    // Floating Property Bar
    this.propertyBar = null;
    this.createPropertyBar();

    // State
    this.currentTool = "cursor";
    this.isDrawing = false;
    this.magnetEnabled = false;
    this.stayInDrawMode = false;

    this.selectedDrawingId = null;
    this.dragHandle = null; // { drawingId, handleIndex }
    this.dragOffset = null; // { drawingId, startPoints, startMouse }
    this.tempDrawing = null;
    this.brushPoints = [];

    this.mouseDownPos = null;
    this.hasMovedSignificantly = false;
    this.animFrameId = null;
    this.hoverPos = null;

    // Active Style Defaults
    this.activeColor = "#00f0ff";
    this.activeLineWidth = 2;
    this.activeLineStyle = "solid"; // solid, dashed, dotted
    this.activeFillColor = "rgba(0, 240, 255, 0.15)";
    this.activeFontSize = 12;

    // Synchronize with Global Drawing Store
    this.unsubscribeStore = this.store.subscribe(() => {
      this.requestRender();
    });

    this.initEvents();
    this.resizeCanvas();
  }

  get symbol() {
    return this.win.symbol;
  }

  get timeframe() {
    return this.win.timeframe;
  }

  get drawings() {
    return this.store.getDrawingsForSymbol(this.symbol);
  }

  get selectedDrawing() {
    if (!this.selectedDrawingId) return null;
    return this.store.getDrawingById(this.selectedDrawingId);
  }

  resizeCanvas() {
    const rect = this.container.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = rect.height * window.devicePixelRatio;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    this.requestRender();
  }

  setTool(tool) {
    this.currentTool = tool;
    this.selectedDrawingId = null;
    this.tempDrawing = null;
    this.isDrawing = false;
    this.dragHandle = null;
    this.dragOffset = null;
    this.brushPoints = [];
    this.mouseDownPos = null;
    this.hidePropertyBar();

    const isCursorMode = ["cursor", "dot", "arrow_cursor"].includes(tool);
    this.canvas.style.pointerEvents = isCursorMode ? "none" : "auto";

    if (tool === "cursor") this.canvas.style.cursor = "default";
    else if (tool === "dot") this.canvas.style.cursor = "crosshair";
    else if (tool === "arrow_cursor") this.canvas.style.cursor = "default";
    else if (tool === "eraser") this.canvas.style.cursor = "cell";
    else this.canvas.style.cursor = "crosshair";

    this.requestRender();
  }

  toggleMagnet() {
    this.magnetEnabled = !this.magnetEnabled;
    return this.magnetEnabled;
  }

  toggleStayInDrawMode() {
    this.stayInDrawMode = !this.stayInDrawMode;
    return this.stayInDrawMode;
  }

  deleteSelected() {
    if (this.selectedDrawingId) {
      // Allow delete even if locked
      this.store.remove(this.selectedDrawingId);
      this.selectedDrawingId = null;
      this.hidePropertyBar();
      this.requestRender();
    }
  }

  toggleLockSelected() {
    if (!this.selectedDrawingId) return;
    const d = this.store.getDrawingById(this.selectedDrawingId);
    if (!d) return;

    const newLockState = !d.isLocked;
    this.store.update(this.selectedDrawingId, { isLocked: newLockState });

    if (window.showToast) {
      window.showToast(newLockState ? "🔒 Dikunci — Klik lagi untuk unlock" : "🔓 Dibuka (Unlocked)");
    }

    // Keep selected so user can unlock/delete from property bar
    const lockBtn = this.propertyBar?.querySelector(".prop-lock-btn");
    if (lockBtn) lockBtn.textContent = newLockState ? "🔓" : "🔒";

    this.requestRender();
  }

  requestRender() {
    if (this.animFrameId) return;
    this.animFrameId = requestAnimationFrame(() => {
      this.animFrameId = null;
      this.render();
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // RIGID CANDLE ANCHORED COORDINATE CONVERSIONS
  // ─────────────────────────────────────────────────────────────────────────
  toScreen(time, price) {
    if (!this.chart || !this.series) return { x: null, y: null };
    const timeScale = this.chart.timeScale();
    let x = timeScale.timeToCoordinate(time);
    const y = this.series.priceToCoordinate(price);

    const candles = this.win.candles || [];
    if (x === null && candles.length > 0) {
      const tfSec = TF_SECONDS_MAP[this.timeframe] || 300;
      const lastCandle = candles[candles.length - 1];
      const firstCandle = candles[0];
      const lastX = timeScale.timeToCoordinate(lastCandle.time);
      const firstX = timeScale.timeToCoordinate(firstCandle.time);
      const barSpacing = (candles.length > 1 && lastX !== null && firstX !== null)
        ? Math.max(2, (lastX - firstX) / (candles.length - 1))
        : 10;

      if (time > lastCandle.time && lastX !== null) {
        const offset = (time - lastCandle.time) / tfSec;
        x = lastX + (offset * barSpacing);
      } else if (time < firstCandle.time && firstX !== null) {
        const offset = (firstCandle.time - time) / tfSec;
        x = firstX - (offset * barSpacing);
      } else {
        for (let i = 0; i < candles.length; i++) {
          if (candles[i].time === time) {
            x = timeScale.timeToCoordinate(candles[i].time);
            break;
          }
        }
      }
    }

    return { x, y };
  }

  toData(x, y) {
    if (!this.chart || !this.series) return { time: null, price: null };
    const timeScale = this.chart.timeScale();
    let time = timeScale.coordinateToTime(x);
    let price = this.series.coordinateToPrice(y);

    const candles = this.win.candles || [];
    if (candles.length > 0) {
      const tfSec = TF_SECONDS_MAP[this.timeframe] || 300;
      const lastCandle = candles[candles.length - 1];
      const firstCandle = candles[0];
      const lastX = timeScale.timeToCoordinate(lastCandle.time);
      const firstX = timeScale.timeToCoordinate(firstCandle.time);
      const barSpacing = (candles.length > 1 && lastX !== null && firstX !== null)
        ? Math.max(2, (lastX - firstX) / (candles.length - 1))
        : 10;

      if (time === null) {
        if (lastX !== null && x > lastX) {
          const offset = Math.round((x - lastX) / barSpacing);
          time = lastCandle.time + (offset * tfSec);
        } else if (firstX !== null && x < firstX) {
          const offset = Math.round((firstX - x) / barSpacing);
          time = firstCandle.time - (offset * tfSec);
        } else {
          // Snap firmly to nearest visible candle
          let bestDist = Infinity;
          let bestTime = lastCandle.time;
          for (let i = 0; i < candles.length; i++) {
            const cx = timeScale.timeToCoordinate(candles[i].time);
            if (cx !== null) {
              const d = Math.abs(cx - x);
              if (d < bestDist) {
                bestDist = d;
                bestTime = candles[i].time;
              }
            }
          }
          time = bestTime;
        }
      }
    }

    if (price === null && candles.length > 0) {
      price = candles[candles.length - 1].close;
    }

    // Magnet snap
    if (this.magnetEnabled && candles.length > 0) {
      const snap = this.getMagnetSnap(x, y);
      if (snap) {
        time = snap.time;
        price = snap.price;
      }
    }

    return { time, price };
  }

  getMagnetSnap(x, y) {
    const timeScale = this.chart.timeScale();
    const candles = this.win.candles || [];
    let closest = null;
    let minDist = 30;

    candles.forEach(c => {
      const cx = timeScale.timeToCoordinate(c.time);
      if (cx !== null && Math.abs(cx - x) < minDist) {
        [c.open, c.high, c.low, c.close].forEach(p => {
          const cy = this.series.priceToCoordinate(p);
          if (cy !== null) {
            const dist = Math.hypot(cx - x, cy - y);
            if (dist < minDist) {
              minDist = dist;
              closest = { time: c.time, price: p };
            }
          }
        });
      }
    });
    return closest;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // EVENT LISTENERS (Seamless 60/120 FPS Interaction)
  // ─────────────────────────────────────────────────────────────────────────
  initEvents() {
    this.chart.timeScale().subscribeVisibleTimeRangeChange(() => this.requestRender());
    this.chart.timeScale().subscribeVisibleLogicalRangeChange(() => this.requestRender());

    this.container.addEventListener("mousemove", (e) => {
      if (e.buttons > 0) this.requestRender();

      if (["cursor", "dot", "arrow_cursor"].includes(this.currentTool)) {
        const { x, y } = this.getCanvasCoords(e);
        const hoveredDrawing = this.getDrawingAt(x, y);
        const hoveredHandle = (this.selectedDrawing && !this.selectedDrawing.isLocked) ? this.getHoveredHandle(x, y, this.selectedDrawing) : -1;
        this.canvas.style.pointerEvents = (hoveredDrawing !== null || hoveredHandle !== -1 || this.isDrawing) ? "auto" : "none";
      }
    });

    // Forward wheel events for chart zoom
    this.canvas.addEventListener("wheel", (e) => {
      const chartCanvas = this.container.querySelector("canvas");
      if (chartCanvas && chartCanvas !== this.canvas) {
        chartCanvas.dispatchEvent(new WheelEvent("wheel", e));
      }
    }, { passive: true });

    this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
    this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));
    this.canvas.addEventListener("mouseup", (e) => this.onMouseUp(e));

    // Right-Click Context Deletion (Klik Kanan Langsung Hapus)
    this.canvas.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      const { x, y } = this.getCanvasCoords(e);
      const clicked = this.getDrawingAt(x, y);
      if (clicked) {
        this.store.remove(clicked.id);
        this.selectedDrawingId = null;
        this.hidePropertyBar();
        this.requestRender();
        if (window.showToast) window.showToast("🗑 Gambar berhasil dihapus");
      }
    });

    window.addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
      if (e.key === "Delete" || e.key === "Backspace") {
        this.deleteSelected();
      }
      if (e.key === "Escape") {
        this.selectedDrawingId = null;
        this.hidePropertyBar();
        this.setTool("cursor");
      }
      if (e.key === "l" || e.key === "L") {
        this.toggleLockSelected();
      }
    });
  }

  getCanvasCoords(e) {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  onMouseDown(e) {
    if (this.store.isGlobalHidden) return;
    const { x, y } = this.getCanvasCoords(e);
    const dataCoord = this.toData(x, y);
    if (dataCoord.time === null || dataCoord.price === null) return;

    this.mouseDownPos = { x, y };
    this.hasMovedSignificantly = false;

    // ERASER TOOL
    if (this.currentTool === "eraser") {
      const clicked = this.getDrawingAt(x, y);
      if (clicked) {
        this.store.remove(clicked.id);
        this.requestRender();
      }
      return;
    }

    // CURSOR MODE: Selection & Dragging
    if (["cursor", "dot", "arrow_cursor"].includes(this.currentTool)) {
      if (this.selectedDrawing && !this.selectedDrawing.isLocked) {
        const handleIndex = this.getHoveredHandle(x, y, this.selectedDrawing);
        if (handleIndex !== -1) {
          this.dragHandle = { drawingId: this.selectedDrawingId, handleIndex };
          return;
        }
      }

      const clicked = this.getDrawingAt(x, y);
      if (clicked) {
        this.selectedDrawingId = clicked.id;
        if (!clicked.isLocked) {
          this.dragOffset = {
            drawingId: clicked.id,
            startPoints: JSON.parse(JSON.stringify(clicked.points)),
            startMouse: { time: dataCoord.time, price: dataCoord.price }
          };
        }
        this.showPropertyBar(clicked, x, y);
      } else {
        // Deselect when clicking empty space
        this.selectedDrawingId = null;
        this.dragOffset = null;
        this.hidePropertyBar();
      }
      this.requestRender();
      return;
    }

    // FREEHAND BRUSH / HIGHLIGHTER
    if (this.currentTool === "brush" || this.currentTool === "highlighter") {
      this.isDrawing = true;
      this.brushPoints = [{ time: dataCoord.time, price: dataCoord.price }];
      this.tempDrawing = {
        symbol: this.symbol,
        sourceTimeframe: this.timeframe,
        type: this.currentTool,
        color: this.currentTool === "highlighter" ? "#ffb703" : this.activeColor,
        lineWidth: this.currentTool === "highlighter" ? 14 : 3,
        opacity: this.currentTool === "highlighter" ? 0.35 : 1.0,
        points: this.brushPoints,
        createdAt: Date.now()
      };
      return;
    }

    // SINGLE-CLICK TOOLS
    const singleClickTools = [
      "hline", "hray", "vline", "crossline", "text", "anchored_text",
      "note", "callout", "price_label", "arrow_up", "arrow_down",
      "icon_bull", "icon_bear", "icon_target", "icon_fire", "icon_warning"
    ];

    if (singleClickTools.includes(this.currentTool)) {
      let promptText = "";
      if (this.currentTool === "text" || this.currentTool === "anchored_text") {
        promptText = prompt("Enter text annotation:", "Key Zone") || "Text";
      } else if (this.currentTool === "note" || this.currentTool === "callout") {
        promptText = prompt("Enter note:", "Breakout Confirmation") || "Note";
      } else if (this.currentTool === "price_label") {
        promptText = Number(dataCoord.price).toFixed(2);
      }

      const newObj = this.store.add({
        symbol: this.symbol,
        sourceTimeframe: this.timeframe,
        type: this.currentTool,
        points: [{ time: dataCoord.time, price: dataCoord.price }],
        style: {
          color: this.activeColor,
          lineWidth: this.activeLineWidth,
          lineStyle: this.activeLineStyle,
          fillColor: this.activeFillColor,
          fontSize: this.activeFontSize
        },
        text: promptText
      });

      if (!this.stayInDrawMode) {
        this.selectedDrawingId = newObj.id;
        this.showPropertyBar(newObj, x, y);
        this.setTool("cursor");
      } else {
        this.selectedDrawingId = null;
        this.requestRender();
      }
      return;
    }

    // MULTI-POINT TOOLS (Trendline, Ray, Rectangle, Channel, Fib, Measure, Long/Short Pos)
    if (!this.isDrawing) {
      this.isDrawing = true;
      this.tempDrawing = {
        symbol: this.symbol,
        sourceTimeframe: this.timeframe,
        type: this.currentTool,
        points: [
          { time: dataCoord.time, price: dataCoord.price },
          { time: dataCoord.time, price: dataCoord.price }
        ],
        style: {
          color: this.activeColor,
          lineWidth: this.activeLineWidth,
          lineStyle: this.activeLineStyle,
          fillColor: this.activeFillColor,
          fontSize: this.activeFontSize
        },
        text: ""
      };
      this.requestRender();
    } else {
      this.completeDrawing(dataCoord);
    }
  }

  onMouseMove(e) {
    if (this.store.isGlobalHidden) return;
    const { x, y } = this.getCanvasCoords(e);
    const dataCoord = this.toData(x, y);
    this.hoverPos = { x, y, data: dataCoord };

    if (this.mouseDownPos && Math.hypot(x - this.mouseDownPos.x, y - this.mouseDownPos.y) > 6) {
      this.hasMovedSignificantly = true;
    }

    // Freehand Brush
    if (this.isDrawing && (this.currentTool === "brush" || this.currentTool === "highlighter") && dataCoord.time && dataCoord.price) {
      this.brushPoints.push({ time: dataCoord.time, price: dataCoord.price });
      this.requestRender();
      return;
    }

    // Multi-point live preview
    if (this.isDrawing && this.tempDrawing && dataCoord.time && dataCoord.price) {
      this.tempDrawing.points[1] = { time: dataCoord.time, price: dataCoord.price };
      this.requestRender();
      return;
    }

    // Drag handle
    if (this.dragHandle && dataCoord.time && dataCoord.price && !this.store.isLocked) {
      const d = this.store.getDrawingById(this.dragHandle.drawingId);
      if (d && !d.isLocked && d.points[this.dragHandle.handleIndex]) {
        d.points[this.dragHandle.handleIndex] = { time: dataCoord.time, price: dataCoord.price };
        this.store.update(d.id, { points: d.points });
      }
      return;
    }

    // Drag whole shape
    if (this.dragOffset && dataCoord.time && dataCoord.price && !this.store.isLocked) {
      const d = this.store.getDrawingById(this.dragOffset.drawingId);
      if (d && !d.isLocked) {
        const timeDiff = dataCoord.time - this.dragOffset.startMouse.time;
        const priceDiff = dataCoord.price - this.dragOffset.startMouse.price;
        const newPoints = this.dragOffset.startPoints.map(pt => ({
          time: pt.time + timeDiff,
          price: pt.price + priceDiff
        }));
        this.store.update(d.id, { points: newPoints });
      }
      return;
    }

    // Cursor Styling in Cursor Mode
    if (["cursor", "dot", "arrow_cursor"].includes(this.currentTool)) {
      if (this.selectedDrawing && !this.selectedDrawing.isLocked && this.getHoveredHandle(x, y, this.selectedDrawing) !== -1) {
        this.canvas.style.cursor = "pointer";
      } else if (this.getDrawingAt(x, y)) {
        this.canvas.style.cursor = "move";
      } else {
        this.canvas.style.cursor = "default";
      }
    }
  }

  onMouseUp(e) {
    const { x, y } = this.getCanvasCoords(e);
    const dataCoord = this.toData(x, y);

    // Finish freehand brush
    if (this.isDrawing && (this.currentTool === "brush" || this.currentTool === "highlighter")) {
      const newObj = this.store.add(this.tempDrawing);
      this.tempDrawing = null;
      this.isDrawing = false;
      this.brushPoints = [];

      if (!this.stayInDrawMode) {
        this.selectedDrawingId = newObj.id;
        this.setTool("cursor");
      } else {
        this.selectedDrawingId = null;
        this.requestRender();
      }
      return;
    }

    // Click-and-Drag Mode completion
    if (this.isDrawing && this.hasMovedSignificantly && dataCoord.time && dataCoord.price) {
      this.completeDrawing(dataCoord);
    }

    if (this.dragHandle) this.dragHandle = null;
    if (this.dragOffset) this.dragOffset = null;
    this.mouseDownPos = null;
  }

  completeDrawing(dataCoord) {
    if (!this.tempDrawing) return;
    this.tempDrawing.points[1] = { time: dataCoord.time, price: dataCoord.price };
    const newObj = this.store.add(this.tempDrawing);
    
    this.tempDrawing = null;
    this.isDrawing = false;

    if (!this.stayInDrawMode) {
      this.selectedDrawingId = newObj.id;
      const p2Screen = this.toScreen(dataCoord.time, dataCoord.price);
      this.showPropertyBar(newObj, p2Screen.x || 100, p2Screen.y || 100);
      this.setTool("cursor");
    } else {
      // Stay ready for the next drawing without selecting previous handles
      this.selectedDrawingId = null;
      this.hidePropertyBar();
      this.requestRender();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HIT TESTING
  // ─────────────────────────────────────────────────────────────────────────
  getDrawingAt(x, y) {
    const list = this.drawings;
    for (let i = list.length - 1; i >= 0; i--) {
      const d = list[i];
      if (this.isPointNearDrawing(x, y, d)) return d;
    }
    return null;
  }

  getHoveredHandle(x, y, drawing) {
    if (!drawing || !drawing.points || drawing.isLocked) return -1;
    const pts = drawing.points.map(p => this.toScreen(p.time, p.price));
    for (let i = 0; i < pts.length; i++) {
      const pt = pts[i];
      if (pt.x !== null && pt.y !== null && Math.hypot(pt.x - x, pt.y - y) <= 10) {
        return i;
      }
    }
    return -1;
  }

  isPointNearDrawing(x, y, drawing) {
    const threshold = 12;
    const pts = drawing.points.map(p => this.toScreen(p.time, p.price));

    if (drawing.type === "hline") {
      return pts[0]?.y !== null && Math.abs(pts[0].y - y) <= threshold;
    }
    if (drawing.type === "vline") {
      return pts[0]?.x !== null && Math.abs(pts[0].x - x) <= threshold;
    }
    if (drawing.type === "crossline") {
      const isNearH = pts[0]?.y !== null && Math.abs(pts[0].y - y) <= threshold;
      const isNearV = pts[0]?.x !== null && Math.abs(pts[0].x - x) <= threshold;
      return isNearH || isNearV;
    }
    if (drawing.type === "hray") {
      return pts[0]?.y !== null && pts[0]?.x !== null && Math.abs(pts[0].y - y) <= threshold && x >= pts[0].x - 5;
    }
    if (drawing.type === "ray") {
      if (pts.length < 2 || pts[0].x === null || pts[0].y === null || pts[1].x === null || pts[1].y === null) return false;
      return this.distanceToRay(x, y, pts[0].x, pts[0].y, pts[1].x, pts[1].y) <= threshold;
    }
    if (drawing.type === "extended_line") {
      if (pts.length < 2 || pts[0].x === null || pts[0].y === null || pts[1].x === null || pts[1].y === null) return false;
      return this.distanceToInfiniteLine(x, y, pts[0].x, pts[0].y, pts[1].x, pts[1].y) <= threshold;
    }
    if (["trendline", "infoline", "trend_angle", "ruler", "measure", "arrow_line"].includes(drawing.type)) {
      if (pts.length < 2 || pts[0].x === null || pts[0].y === null || pts[1].x === null || pts[1].y === null) return false;
      return this.distanceToSegment(x, y, pts[0].x, pts[0].y, pts[1].x, pts[1].y) <= threshold;
    }
    if (drawing.type === "fib_retrace") {
      if (pts.length < 2 || pts[0].x === null || pts[0].y === null || pts[1].x === null || pts[1].y === null) return false;
      const minY = Math.min(pts[0].y, pts[1].y);
      const maxY = Math.max(pts[0].y, pts[1].y);
      const minX = Math.min(pts[0].x, pts[1].x);
      return y >= minY - 10 && y <= maxY + 10 && x >= minX - 10;
    }
    if (drawing.type === "long_pos" || drawing.type === "short_pos") {
      if (pts.length < 2 || pts[0].x === null || pts[0].y === null || pts[1].x === null || pts[1].y === null) return false;
      const p1 = pts[0];
      const p2 = pts[1];
      const isLong = drawing.type === "long_pos";
      const entryY = p1.y;
      const targetY = p2.y;
      const slY = isLong ? entryY + Math.abs(entryY - targetY) * 0.5 : entryY - Math.abs(entryY - targetY) * 0.5;
      const minX = Math.min(p1.x, p2.x);
      const maxX = Math.max(p1.x, p2.x);
      const minY = Math.min(entryY, targetY, slY);
      const maxY = Math.max(entryY, targetY, slY);
      const isInsideBox = x >= minX - 12 && x <= maxX + 12 && y >= minY - 12 && y <= maxY + 12;
      const isNearBadge = x >= minX - 10 && x <= minX + 95 && y >= entryY - 18 && y <= entryY + 18;
      return isInsideBox || isNearBadge;
    }
    if (["rectangle", "gann_box", "circle", "triangle", "channel"].includes(drawing.type)) {
      if (pts.length < 2 || pts[0].x === null || pts[0].y === null || pts[1].x === null || pts[1].y === null) return false;
      const minX = Math.min(pts[0].x, pts[1].x);
      const maxX = Math.max(pts[0].x, pts[1].x);
      const minY = Math.min(pts[0].y, pts[1].y);
      const maxY = Math.max(pts[0].y, pts[1].y);
      return x >= minX - 10 && x <= maxX + 10 && y >= minY - 10 && y <= maxY + 10;
    }
    if (["text", "anchored_text", "note", "callout", "price_label", "arrow_up", "arrow_down", "icon_bull", "icon_bear", "icon_target", "icon_fire", "icon_warning"].includes(drawing.type)) {
      const pt = pts[0];
      return pt?.x !== null && pt?.y !== null && Math.hypot(pt.x - x, pt.y - y) <= 32;
    }
    if (drawing.type === "brush" || drawing.type === "highlighter") {
      return pts.some(pt => pt.x !== null && pt.y !== null && Math.hypot(pt.x - x, pt.y - y) <= 16);
    }
    return false;
  }

  distanceToSegment(px, py, x1, y1, x2, y2) {
    const l2 = (x2 - x1) ** 2 + (y2 - y1) ** 2;
    if (l2 === 0) return Math.hypot(px - x1, py - y1);
    let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (x1 + t * (x2 - x1)), py - (y1 + t * (y2 - y1)));
  }

  distanceToRay(px, py, x1, y1, x2, y2) {
    const l2 = (x2 - x1) ** 2 + (y2 - y1) ** 2;
    if (l2 === 0) return Math.hypot(px - x1, py - y1);
    let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
    if (t < 0) t = 0;
    return Math.hypot(px - (x1 + t * (x2 - x1)), py - (y1 + t * (y2 - y1)));
  }

  distanceToInfiniteLine(px, py, x1, y1, x2, y2) {
    const l2 = (x2 - x1) ** 2 + (y2 - y1) ** 2;
    if (l2 === 0) return Math.hypot(px - x1, py - y1);
    const t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
    return Math.hypot(px - (x1 + t * (x2 - x1)), py - (y1 + t * (y2 - y1)));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUTTERY-SMOOTH RENDERING ENGINE
  // ─────────────────────────────────────────────────────────────────────────
  render() {
    const width = this.canvas.width / window.devicePixelRatio;
    const height = this.canvas.height / window.devicePixelRatio;
    this.ctx.clearRect(0, 0, width, height);

    if (this.store.isGlobalHidden) return;

    this.ctx.lineCap = "round";
    this.ctx.lineJoin = "round";
    this.ctx.imageSmoothingEnabled = true;

    // 0. Render Live MT5 S&D Shaded Rectangle Boxes
    // renderLiveSDBoxes disabled in favor of clean price line badges

    // 1. Saved drawings
    const list = this.drawings;
    list.forEach(d => {
      this.drawShape(d, d.id === this.selectedDrawingId);
    });

    // 2. Active temporary drawing
    if (this.tempDrawing) {
      this.drawShape(this.tempDrawing, true);
    }
  }

  
  // ─────────────────────────────────────────────────────────────────────────
  // MASTER MT5 REPLICA: LIVE SHADED S&D RECTANGLE BOXES WITH TEXT INSIDE
  // ─────────────────────────────────────────────────────────────────────────
  renderLiveSDBoxes(ctx, screenW, screenH) {
    if (!this.win.latestSDGroup || this.win.symbol !== "XAUUSD") return;
    const { supply = [], demand = [] } = this.win.latestSDGroup;
    if (!this.win.lastCandle || !this.series) return;

    const timeScale = this.chart.timeScale();
    const lastX = timeScale.timeToCoordinate(this.win.lastCandle.time) || (screenW - 140);
    const boxX1 = Math.max(10, lastX - 260);
    const boxX2 = screenW - 65; // Align cleanly before right price scale

    // 1. Render Supply Boxes (Red / Crimson)
    supply.forEach((z, idx) => {
      const yHi = this.series.priceToCoordinate(z.hi);
      const yLo = this.series.priceToCoordinate(z.lo);
      if (yHi === null || yLo === null) return;
      const topY = Math.min(yHi, yLo);
      const h = Math.max(22, Math.abs(yLo - yHi));
      const w = Math.max(140, boxX2 - boxX1);

      ctx.save();
      // Shaded Background
      ctx.fillStyle = idx === 0 ? "rgba(245, 60, 60, 0.18)" : "rgba(245, 60, 60, 0.08)";
      ctx.fillRect(boxX1, topY, w, h);

      // Border Box
      ctx.strokeStyle = idx === 0 ? "#f53c3c" : "rgba(245, 60, 60, 0.65)";
      ctx.lineWidth = idx === 0 ? 1.5 : 1;
      if (idx > 0) ctx.setLineDash([5, 4]);
      ctx.strokeRect(boxX1, topY, w, h);
      ctx.setLineDash([]);

      // Label Text Inside Box (MT5 1:1 format)
      const liveAskStr = z.live_lot ? ` | Ask Live: ${Math.round(z.live_lot)}L` : "";
      const tag = `S${idx + 1} ${Math.round(z.total_lot || 0)}L | ${z.strength || 'SEDANG'} ${Math.round(z.score || 50)} | Uji ${z.retest_count || 0}x, Serap ${z.absorption_hits || 0}x${liveAskStr}`;
      
      // Text Background Tag Pill
      ctx.fillStyle = "rgba(10, 15, 26, 0.85)";
      ctx.fillRect(boxX1 + 6, topY + 3, Math.min(w - 12, ctx.measureText(tag).width + 12), 16);

      ctx.fillStyle = "#ffb4b4";
      ctx.font = "bold 10px 'JetBrains Mono', 'Segoe UI', monospace";
      ctx.fillText(tag, boxX1 + 10, topY + 15);
      ctx.restore();
    });

    // 2. Render Demand Boxes (Green / Emerald)
    demand.forEach((z, idx) => {
      const yHi = this.series.priceToCoordinate(z.hi);
      const yLo = this.series.priceToCoordinate(z.lo);
      if (yHi === null || yLo === null) return;
      const topY = Math.min(yHi, yLo);
      const h = Math.max(22, Math.abs(yLo - yHi));
      const w = Math.max(140, boxX2 - boxX1);

      ctx.save();
      // Shaded Background
      ctx.fillStyle = idx === 0 ? "rgba(0, 225, 120, 0.18)" : "rgba(0, 225, 120, 0.08)";
      ctx.fillRect(boxX1, topY, w, h);

      // Border Box
      ctx.strokeStyle = idx === 0 ? "#00e178" : "rgba(0, 225, 120, 0.65)";
      ctx.lineWidth = idx === 0 ? 1.5 : 1;
      if (idx > 0) ctx.setLineDash([5, 4]);
      ctx.strokeRect(boxX1, topY, w, h);
      ctx.setLineDash([]);

      // Label Text Inside Box (MT5 1:1 format)
      const liveBidStr = z.live_lot ? ` | Bid Live: ${Math.round(z.live_lot)}L` : "";
      const tag = `D${idx + 1} ${Math.round(z.total_lot || 0)}L | ${z.strength || 'SEDANG'} ${Math.round(z.score || 50)} | Uji ${z.retest_count || 0}x, Serap ${z.absorption_hits || 0}x${liveBidStr}`;

      // Text Background Tag Pill
      ctx.fillStyle = "rgba(10, 15, 26, 0.85)";
      ctx.fillRect(boxX1 + 6, topY + 3, Math.min(w - 12, ctx.measureText(tag).width + 12), 16);

      ctx.fillStyle = "#b4ffd7";
      ctx.font = "bold 10px 'JetBrains Mono', 'Segoe UI', monospace";
      ctx.fillText(tag, boxX1 + 10, topY + 15);
      ctx.restore();
    });
  }

  drawShape(d, isSelected) {
    const ctx = this.ctx;
    ctx.save();

    const pts = d.points.map(p => this.toScreen(p.time, p.price));
    const color = d.style?.color || d.color || "#00f0ff";
    const lineWidth = d.style?.lineWidth || d.lineWidth || 2;
    const lineStyle = d.style?.lineStyle || "solid";
    const fillColor = d.style?.fillColor || d.fillColor || "rgba(0, 240, 255, 0.15)";
    const fontSize = d.style?.fontSize || 12;

    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.fillStyle = color;

    if (lineStyle === "dashed") ctx.setLineDash([6, 4]);
    else if (lineStyle === "dotted") ctx.setLineDash([2, 3]);
    else ctx.setLineDash([]);

    const screenW = this.canvas.width / window.devicePixelRatio;
    const screenH = this.canvas.height / window.devicePixelRatio;

    switch (d.type) {
      case "trendline":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          ctx.beginPath();
          ctx.moveTo(pts[0].x, pts[0].y);
          ctx.lineTo(pts[1].x, pts[1].y);
          ctx.stroke();

          ctx.strokeStyle = color + "44";
          ctx.lineWidth = lineWidth + 3;
          ctx.stroke();
        }
        break;

      case "ray":
      case "extended_line":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          const dx = pts[1].x - pts[0].x;
          const dy = pts[1].y - pts[0].y;
          const len = Math.hypot(dx, dy) || 1;
          const extX1 = d.type === "extended_line" ? pts[0].x - (dx / len) * 4000 : pts[0].x;
          const extY1 = d.type === "extended_line" ? pts[0].y - (dy / len) * 4000 : pts[0].y;
          const extX2 = pts[0].x + (dx / len) * 4000;
          const extY2 = pts[0].y + (dy / len) * 4000;

          ctx.beginPath();
          ctx.moveTo(extX1, extY1);
          ctx.lineTo(extX2, extY2);
          ctx.stroke();
        }
        break;

      case "infoline":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          ctx.beginPath();
          ctx.moveTo(pts[0].x, pts[0].y);
          ctx.lineTo(pts[1].x, pts[1].y);
          ctx.stroke();

          const diffP = Math.abs(d.points[1].price - d.points[0].price);
          const pips = (diffP * 10).toFixed(1);
          const midX = (pts[0].x + pts[1].x) / 2;
          const midY = (pts[0].y + pts[1].y) / 2;

          ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
          ctx.fillRect(midX - 45, midY - 14, 90, 22);
          ctx.fillStyle = color;
          ctx.font = "bold 10px 'JetBrains Mono', monospace";
          ctx.fillText(`Δ ${pips}p`, midX - 35, midY + 1);
        }
        break;

      case "hline":
        if (pts.length >= 1 && pts[0].y !== null) {
          const y = pts[0].y;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(screenW, y);
          ctx.stroke();

          ctx.setLineDash([]);
          ctx.fillStyle = color;
          ctx.fillRect(screenW - 75, y - 11, 70, 22);
          ctx.fillStyle = "#000";
          ctx.font = "bold 11px 'JetBrains Mono', monospace";
          ctx.fillText(Number(d.points[0].price).toFixed(2), screenW - 70, y + 4);

          if (d.sourceTimeframe) {
            ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
            ctx.fillRect(8, y - 10, 36, 18);
            ctx.fillStyle = color;
            ctx.font = "bold 10px 'JetBrains Mono', monospace";
            ctx.fillText(d.sourceTimeframe, 12, y + 3);
          }
        }
        break;

      case "hray":
        if (pts.length >= 1 && pts[0].x !== null && pts[0].y !== null) {
          const y = pts[0].y;
          ctx.beginPath();
          ctx.moveTo(pts[0].x, y);
          ctx.lineTo(screenW, y);
          ctx.stroke();
        }
        break;

      case "vline":
        if (pts.length >= 1 && pts[0].x !== null) {
          const x = pts[0].x;
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, screenH);
          ctx.stroke();

          if (d.sourceTimeframe) {
            ctx.setLineDash([]);
            ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
            ctx.fillRect(x - 18, 8, 36, 18);
            ctx.fillStyle = color;
            ctx.font = "bold 10px 'JetBrains Mono', monospace";
            ctx.fillText(d.sourceTimeframe, x - 12, 21);
          }
        }
        break;

      case "crossline":
        if (pts.length >= 1 && pts[0].x !== null && pts[0].y !== null) {
          ctx.beginPath();
          ctx.moveTo(0, pts[0].y);
          ctx.lineTo(screenW, pts[0].y);
          ctx.moveTo(pts[0].x, 0);
          ctx.lineTo(pts[0].x, screenH);
          ctx.stroke();
        }
        break;

      case "channel":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          const [p1, p2] = pts;
          const offset = 35;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y - offset);
          ctx.lineTo(p2.x, p2.y - offset);
          ctx.moveTo(p1.x, p1.y + offset);
          ctx.lineTo(p2.x, p2.y + offset);
          ctx.stroke();

          ctx.fillStyle = fillColor;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y - offset);
          ctx.lineTo(p2.x, p2.y - offset);
          ctx.lineTo(p2.x, p2.y + offset);
          ctx.lineTo(p1.x, p1.y + offset);
          ctx.closePath();
          ctx.fill();
        }
        break;

      case "fib_retrace":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          const p1 = d.points[0];
          const p2 = d.points[1];
          const minX = Math.min(pts[0].x, pts[1].x);
          const maxX = Math.max(pts[0].x, pts[1].x);
          const priceDiff = p2.price - p1.price;

          const fibLevels = [
            { lvl: 0.0, color: "#787b86" },
            { lvl: 0.236, color: "#f23645" },
            { lvl: 0.382, color: "#ff9800" },
            { lvl: 0.5, color: "#4caf50" },
            { lvl: 0.618, color: "#089981" },
            { lvl: 0.786, color: "#00bcd4" },
            { lvl: 1.0, color: "#787b86" }
          ];

          fibLevels.forEach(fib => {
            const curP = p1.price + (priceDiff * fib.lvl);
            const sy = this.series.priceToCoordinate(curP);
            if (sy !== null) {
              ctx.strokeStyle = fib.color;
              ctx.lineWidth = 1;
              ctx.beginPath();
              ctx.moveTo(minX, sy);
              ctx.lineTo(maxX, sy);
              ctx.stroke();

              ctx.fillStyle = fib.color;
              ctx.font = "bold 9.5px 'JetBrains Mono', monospace";
              ctx.fillText(`${fib.lvl} (${curP.toFixed(2)})`, minX + 4, sy - 3);
            }
          });
        }
        break;

      case "rectangle":
        if (pts.length >= 2) {
          // Resolve screen coords — clamp to chart edges when time is off-screen (other TF / scrolled)
          let rx0 = pts[0].x, ry0 = pts[0].y;
          let rx1 = pts[1].x, ry1 = pts[1].y;

          // If price coords are null, skip (price level truly off-screen)
          if (ry0 === null || ry1 === null) break;

          // Clamp time coords to chart edges if null
          if (rx0 === null && rx1 === null) {
            // Both off-screen: try to determine if box is in the past (left) or future (right)
            const tfSec = TF_SECONDS_MAP?.[this.timeframe] || 300;
            const candles = this.win.candles || [];
            if (candles.length > 0) {
              const firstCandle = candles[0];
              const lastCandle = candles[candles.length - 1];
              if (d.points[0].time < firstCandle.time && d.points[1].time < firstCandle.time) break; // fully before history
              if (d.points[0].time > lastCandle.time && d.points[1].time > lastCandle.time) break; // fully future
            }
            rx0 = 0;
            rx1 = screenW;
          } else if (rx0 === null) {
            rx0 = 0; // clamp left edge
          } else if (rx1 === null) {
            rx1 = screenW; // clamp right edge
          }

          const rxx = Math.min(rx0, rx1);
          const ryy = Math.min(ry0, ry1);
          const rw = Math.abs(rx1 - rx0);
          const rh = Math.abs(ry1 - ry0);

          if (rw < 1 || rh < 1) break;

          ctx.fillStyle = fillColor;
          ctx.fillRect(rxx, ryy, rw, rh);
          ctx.strokeRect(rxx, ryy, rw, rh);

          // Source TF label badge
          if (d.sourceTimeframe) {
            ctx.setLineDash([]);
            ctx.fillStyle = "rgba(15, 23, 42, 0.82)";
            ctx.fillRect(rxx + 4, ryy + 4, 32, 16);
            ctx.fillStyle = color;
            ctx.font = "bold 9.5px 'JetBrains Mono', monospace";
            ctx.fillText(d.sourceTimeframe, rxx + 8, ryy + 15);
          }
        }
        break;


      case "circle":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          const [p1, p2] = pts;
          const rx = Math.abs(p2.x - p1.x) / 2;
          const ry = Math.abs(p2.y - p1.y) / 2;
          const cx = Math.min(p1.x, p2.x) + rx;
          const cy = Math.min(p1.y, p2.y) + ry;

          ctx.fillStyle = fillColor;
          ctx.beginPath();
          ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        }
        break;

      case "triangle":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          const [p1, p2] = pts;
          const topX = (p1.x + p2.x) / 2;
          const topY = Math.min(p1.y, p2.y);
          const botY = Math.max(p1.y, p2.y);

          ctx.fillStyle = fillColor;
          ctx.beginPath();
          ctx.moveTo(topX, topY);
          ctx.lineTo(p2.x, botY);
          ctx.lineTo(p1.x, botY);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        }
        break;

      case "brush":
      case "highlighter":
        if (pts.length >= 2) {
          ctx.globalAlpha = d.opacity || 1.0;
          ctx.beginPath();
          let started = false;
          pts.forEach(pt => {
            if (pt.x !== null && pt.y !== null) {
              if (!started) {
                ctx.moveTo(pt.x, pt.y);
                started = true;
              } else {
                ctx.lineTo(pt.x, pt.y);
              }
            }
          });
          ctx.stroke();
          ctx.globalAlpha = 1.0;
        }
        break;

      case "long_pos":
      case "short_pos":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          const isLong = d.type === "long_pos";
          const [p1, p2] = pts;
          const minX = Math.min(p1.x, p2.x);
          const maxX = Math.max(p1.x, p2.x);
          const entryY = p1.y;
          const targetY = p2.y;
          const slY = isLong ? entryY + Math.abs(entryY - targetY) * 0.5 : entryY - Math.abs(entryY - targetY) * 0.5;

          ctx.fillStyle = "rgba(0, 230, 118, 0.2)";
          ctx.fillRect(minX, Math.min(entryY, targetY), maxX - minX, Math.abs(entryY - targetY));
          ctx.strokeStyle = "#00e676";
          ctx.strokeRect(minX, Math.min(entryY, targetY), maxX - minX, Math.abs(entryY - targetY));

          ctx.fillStyle = "rgba(255, 51, 75, 0.2)";
          ctx.fillRect(minX, Math.min(entryY, slY), maxX - minX, Math.abs(entryY - slY));
          ctx.strokeStyle = "#ff334b";
          ctx.strokeRect(minX, Math.min(entryY, slY), maxX - minX, Math.abs(entryY - slY));

          ctx.fillStyle = "rgba(10, 15, 26, 0.9)";
          ctx.fillRect(minX + 4, entryY - 10, 75, 20);
          ctx.fillStyle = "#fff";
          ctx.font = "bold 10px 'JetBrains Mono', monospace";
          ctx.fillText("R:R 1:2.0", minX + 8, entryY + 4);
        }
        break;

      case "arrow_up":
      case "arrow_down":
        if (pts.length >= 1 && pts[0].x !== null && pts[0].y !== null) {
          const x = pts[0].x;
          const y = pts[0].y;
          const isUp = d.type === "arrow_up";
          const arrowColor = isUp ? "#00e676" : "#ff334b";

          ctx.fillStyle = arrowColor;
          ctx.beginPath();
          if (isUp) {
            ctx.moveTo(x, y - 18);
            ctx.lineTo(x + 10, y);
            ctx.lineTo(x + 4, y);
            ctx.lineTo(x + 4, y + 12);
            ctx.lineTo(x - 4, y + 12);
            ctx.lineTo(x - 4, y);
            ctx.lineTo(x - 10, y);
          } else {
            ctx.moveTo(x, y + 18);
            ctx.lineTo(x + 10, y);
            ctx.lineTo(x + 4, y);
            ctx.lineTo(x + 4, y - 12);
            ctx.lineTo(x - 4, y - 12);
            ctx.lineTo(x - 4, y);
            ctx.lineTo(x - 10, y);
          }
          ctx.closePath();
          ctx.fill();
        }
        break;

      case "arrow_line":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          ctx.beginPath();
          ctx.moveTo(pts[0].x, pts[0].y);
          ctx.lineTo(pts[1].x, pts[1].y);
          ctx.stroke();

          const angle = Math.atan2(pts[1].y - pts[0].y, pts[1].x - pts[0].x);
          const headLen = 14;
          ctx.setLineDash([]);
          ctx.beginPath();
          ctx.moveTo(pts[1].x, pts[1].y);
          ctx.lineTo(pts[1].x - headLen * Math.cos(angle - Math.PI / 6), pts[1].y - headLen * Math.sin(angle - Math.PI / 6));
          ctx.lineTo(pts[1].x - headLen * Math.cos(angle + Math.PI / 6), pts[1].y - headLen * Math.sin(angle + Math.PI / 6));
          ctx.closePath();
          ctx.fill();
        }
        break;

      case "text":
      case "anchored_text":
      case "note":
      case "callout":
        if (pts.length >= 1 && pts[0].x !== null && pts[0].y !== null) {
          const x = pts[0].x;
          const y = pts[0].y;
          const text = d.text || "Note";

          ctx.font = `bold ${fontSize}px 'Inter', sans-serif`;
          const textMetrics = ctx.measureText(text);
          const textWidth = textMetrics.width;

          ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
          ctx.fillRect(x - 6, y - fontSize - 4, textWidth + 12, fontSize + 8);
          ctx.strokeStyle = color;
          ctx.lineWidth = 1;
          ctx.strokeRect(x - 6, y - fontSize - 4, textWidth + 12, fontSize + 8);

          ctx.fillStyle = color;
          ctx.fillText(text, x, y);
        }
        break;

      case "price_label":
        if (pts.length >= 1 && pts[0].x !== null && pts[0].y !== null) {
          const x = pts[0].x;
          const y = pts[0].y;
          const priceText = Number(d.points[0].price).toFixed(2);

          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + 10, y - 10);
          ctx.lineTo(x + 85, y - 10);
          ctx.lineTo(x + 85, y + 10);
          ctx.lineTo(x + 10, y + 10);
          ctx.closePath();
          ctx.fill();

          ctx.fillStyle = "#000";
          ctx.font = "bold 11px 'JetBrains Mono', monospace";
          ctx.fillText(priceText, x + 16, y + 4);
        }
        break;

      case "measure":
      case "ruler":
        if (pts.length >= 2 && pts[0].x !== null && pts[1].x !== null) {
          const [p1, p2] = pts;
          const rx = Math.min(p1.x, p2.x);
          const ry = Math.min(p1.y, p2.y);
          const rw = Math.abs(p2.x - p1.x);
          const rh = Math.abs(p2.y - p1.y);

          const priceDiff = d.points[1].price - d.points[0].price;
          const timeDiff = Math.abs(d.points[1].time - d.points[0].time);
          const isGain = priceDiff >= 0;
          const measureColor = isGain ? "#00e676" : "#ff334b";

          ctx.fillStyle = isGain ? "rgba(0, 230, 118, 0.12)" : "rgba(255, 51, 75, 0.12)";
          ctx.fillRect(rx, ry, rw, rh);
          ctx.strokeStyle = measureColor;
          ctx.strokeRect(rx, ry, rw, rh);

          ctx.setLineDash([4, 3]);
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
          ctx.setLineDash([]);

          const pips = (Math.abs(priceDiff) * 10).toFixed(1);
          const hours = Math.floor(timeDiff / 3600);
          const mins = Math.floor((timeDiff % 3600) / 60);
          const timeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
          const signStr = isGain ? "+" : "-";

          const midX = (p1.x + p2.x) / 2;
          const midY = (p1.y + p2.y) / 2;

          ctx.fillStyle = "rgba(10, 15, 26, 0.95)";
          ctx.fillRect(midX - 60, midY - 22, 120, 44);
          ctx.strokeStyle = measureColor;
          ctx.lineWidth = 1.5;
          ctx.strokeRect(midX - 60, midY - 22, 120, 44);

          ctx.fillStyle = measureColor;
          ctx.font = "bold 11px 'JetBrains Mono', monospace";
          ctx.fillText(`${signStr}${Math.abs(priceDiff).toFixed(2)} (${signStr}${pips} p)`, midX - 52, midY - 6);

          ctx.fillStyle = "#94a3b8";
          ctx.font = "10px 'Inter', sans-serif";
          ctx.fillText(`Time: ${timeStr}`, midX - 52, midY + 12);
        }
        break;

      case "icon_bull":
      case "icon_bear":
      case "icon_target":
      case "icon_fire":
      case "icon_warning":
        if (pts.length >= 1 && pts[0].x !== null && pts[0].y !== null) {
          const x = pts[0].x;
          const y = pts[0].y;
          const iconMap = {
            icon_bull: "🚀",
            icon_bear: "🔻",
            icon_target: "🎯",
            icon_fire: "🔥",
            icon_warning: "⚠️"
          };
          ctx.font = "20px sans-serif";
          ctx.fillText(iconMap[d.type] || "📍", x - 10, y + 10);
        }
        break;
    }

    // Anchor Handles when selected (Only if not locked)
    if (isSelected && !this.store.isLocked && !d.isLocked) {
      ctx.setLineDash([]);
      pts.forEach(pt => {
        if (pt.x !== null && pt.y !== null) {
          ctx.fillStyle = color + "33";
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 9, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = "#ffffff";
          ctx.strokeStyle = color;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        }
      });
    }

    ctx.restore();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PROPERTY TOOLBAR (Floating UI for Selected Drawing)
  // ─────────────────────────────────────────────────────────────────────────
  createPropertyBar() {
    this.propertyBar = document.createElement("div");
    this.propertyBar.className = "drawing-property-bar";
    this.propertyBar.style.display = "none";
    // Audit fix: dulu id="prop-*" - karena ada 1 DrawingEngine per window
    // (4x di layout QUAD), id yang sama muncul berkali-kali di 1 dokumen
    // (HTML gak valid). Semua lookup di bawah udah scoped ke
    // this.propertyBar.querySelector(...) jadi gak pernah nyampur beneran,
    // tapi tetep jebakan buat kode masa depan yang mungkin pakai
    // document.getElementById(). Diganti ke class (masih tetep scoped sama
    // cara yang sama, cuma gak duplikat id lagi).
    this.propertyBar.innerHTML = `
      <div class="prop-group">
        <input type="color" class="prop-color prop-color-picker" value="#00f0ff" title="Color">
      </div>
      <div class="prop-group">
        <select class="prop-select prop-width" title="Line Width">
          <option value="1">1px</option>
          <option value="2" selected>2px</option>
          <option value="3">3px</option>
          <option value="4">4px</option>
          <option value="6">6px</option>
        </select>
      </div>
      <div class="prop-group">
        <select class="prop-select prop-style" title="Line Style">
          <option value="solid" selected>Solid</option>
          <option value="dashed">Dashed</option>
          <option value="dotted">Dotted</option>
        </select>
      </div>
      <button class="prop-btn prop-lock-btn" title="Lock Object in Place (Kunci Gambar)">🔒</button>
      <button class="prop-btn danger prop-del-btn" title="Delete Drawing (Del)">🗑</button>
    `;
    this.container.appendChild(this.propertyBar);

    const colorPicker = this.propertyBar.querySelector(".prop-color-picker");
    colorPicker.addEventListener("input", (e) => {
      const col = e.target.value;
      this.activeColor = col;
      if (this.selectedDrawingId) {
        this.store.update(this.selectedDrawingId, {
          style: { color: col, fillColor: col + "26" }
        });
      }
    });

    const widthSelect = this.propertyBar.querySelector(".prop-width");
    widthSelect.addEventListener("change", (e) => {
      const w = parseInt(e.target.value, 10);
      this.activeLineWidth = w;
      if (this.selectedDrawingId) {
        this.store.update(this.selectedDrawingId, { style: { lineWidth: w } });
      }
    });

    const styleSelect = this.propertyBar.querySelector(".prop-style");
    styleSelect.addEventListener("change", (e) => {
      const st = e.target.value;
      this.activeLineStyle = st;
      if (this.selectedDrawingId) {
        this.store.update(this.selectedDrawingId, { style: { lineStyle: st } });
      }
    });

    const lockBtn = this.propertyBar.querySelector(".prop-lock-btn");
    lockBtn.addEventListener("click", () => {
      this.toggleLockSelected();
    });

    const delBtn = this.propertyBar.querySelector(".prop-del-btn");
    delBtn.addEventListener("click", () => {
      this.deleteSelected();
    });
  }

  showPropertyBar(drawing, x, y) {
    if (!this.propertyBar || !drawing) return;
    const colorPicker = this.propertyBar.querySelector(".prop-color-picker");
    const widthSelect = this.propertyBar.querySelector(".prop-width");
    const styleSelect = this.propertyBar.querySelector(".prop-style");
    const lockBtn = this.propertyBar.querySelector(".prop-lock-btn");
    const delBtn = this.propertyBar.querySelector(".prop-del-btn");

    if (colorPicker && (drawing.style?.color || drawing.color)) colorPicker.value = drawing.style?.color || drawing.color;
    if (widthSelect && (drawing.style?.lineWidth || drawing.lineWidth)) widthSelect.value = drawing.style?.lineWidth || drawing.lineWidth;
    if (styleSelect && (drawing.style?.lineStyle || drawing.lineStyle)) styleSelect.value = drawing.style?.lineStyle || drawing.lineStyle;

    // If locked: disable edit controls, show unlock button
    const isLocked = drawing.isLocked;
    if (colorPicker) colorPicker.disabled = isLocked;
    if (widthSelect) widthSelect.disabled = isLocked;
    if (styleSelect) styleSelect.disabled = isLocked;
    if (lockBtn) lockBtn.textContent = isLocked ? "🔓 Unlock" : "🔒 Lock";
    if (lockBtn) lockBtn.title = isLocked ? "Unlock Drawing" : "Lock Drawing";
    if (delBtn) delBtn.title = isLocked ? "Delete (meski dikunci)" : "Delete Drawing";

    this.propertyBar.style.display = "flex";
    const barX = Math.max(10, Math.min(x - 60, this.container.clientWidth - 260));
    const barY = Math.max(45, Math.min(y - 50, this.container.clientHeight - 60));
    this.propertyBar.style.left = `${barX}px`;
    this.propertyBar.style.top = `${barY}px`;
  }

  hidePropertyBar() {
    if (this.propertyBar) {
      this.propertyBar.style.display = "none";
    }
  }

  destroy() {
    if (this.unsubscribeStore) this.unsubscribeStore();
    if (this.canvas && this.canvas.parentNode) {
      this.canvas.parentNode.removeChild(this.canvas);
    }
    if (this.propertyBar && this.propertyBar.parentNode) {
      this.propertyBar.parentNode.removeChild(this.propertyBar);
    }
  }
}
