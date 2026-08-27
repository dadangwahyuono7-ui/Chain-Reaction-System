/**
 * ═══════════════════════════════════════════════════════════════════════════
 *  DRAWING OBJECT MODEL & GLOBAL STORE (COMMANDER DADANG PHASE 1)
 *  Generic DrawingObject architecture with Source Timeframe & Cross-Window Sync
 * ═══════════════════════════════════════════════════════════════════════════
 */

export class DrawingObject {
  constructor(data) {
    this.id = data.id || "draw_" + Date.now() + "_" + Math.random().toString(36).substr(2, 5);
    this.symbol = (data.symbol || "XAUUSD").toUpperCase();
    this.sourceTimeframe = (data.sourceTimeframe || "H4").toUpperCase();
    this.type = data.type || "trendline"; // hline, vline, trendline, ray, rectangle, arrow, text, price_label, measure
    this.points = data.points || []; // [{ time: timestamp (seconds), price: float }]
    this.style = {
      color: data.style?.color || "#00f0ff",
      lineWidth: data.style?.lineWidth || 2,
      lineStyle: data.style?.lineStyle || "solid", // solid, dashed, dotted
      fillColor: data.style?.fillColor || "rgba(0, 240, 255, 0.15)",
      opacity: data.style?.opacity !== undefined ? data.style.opacity : 1.0,
      fontSize: data.style?.fontSize || 12,
      ...data.style
    };
    this.text = data.text || "";
    this.isLocked = data.isLocked || false;
    this.visibility = {
      isHidden: data.visibility?.isHidden || false,
      allTimeframes: data.visibility?.allTimeframes !== false
    };
    this.metadata = {
      author: "Commander Dadang",
      createdAt: data.metadata?.createdAt || Date.now(),
      updatedAt: Date.now()
    };
  }

  toJSON() {
    return {
      id: this.id,
      symbol: this.symbol,
      sourceTimeframe: this.sourceTimeframe,
      type: this.type,
      points: this.points,
      style: this.style,
      text: this.text,
      isLocked: this.isLocked,
      visibility: this.visibility,
      metadata: this.metadata
    };
  }
}


export class DrawingStore {
  constructor() {
    this.drawings = [];
    this.listeners = [];
    this.isLocked = false;
    this.isGlobalHidden = false;
    this.loadFromStorage();
  }

  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  notify() {
    this.saveToStorage();
    this.listeners.forEach(fn => fn(this.drawings));
  }

  getDrawingsForSymbol(symbol) {
    const sym = (symbol || "").toUpperCase();
    return this.drawings.filter(d => d.symbol === sym && (!this.isGlobalHidden && !d.visibility.isHidden));
  }

  getDrawingById(id) {
    return this.drawings.find(d => d.id === id);
  }

  add(drawingData) {
    const obj = new DrawingObject(drawingData);
    this.drawings.push(obj);
    this.notify();
    return obj;
  }

  update(id, partial) {
    const d = this.getDrawingById(id);
    if (d) {
      if (partial.points) d.points = partial.points;
      if (partial.style) d.style = { ...d.style, ...partial.style };
      if (partial.text !== undefined) d.text = partial.text;
      if (partial.isLocked !== undefined) d.isLocked = partial.isLocked;
      if (partial.visibility) d.visibility = { ...d.visibility, ...partial.visibility };
      d.metadata.updatedAt = Date.now();
      this.notify();
    }
  }


  remove(id) {
    this.drawings = this.drawings.filter(d => d.id !== id);
    this.notify();
  }

  clearSymbol(symbol) {
    const sym = (symbol || "").toUpperCase();
    this.drawings = this.drawings.filter(d => d.symbol !== sym);
    this.notify();
  }

  clearAll() {
    this.drawings = [];
    this.notify();
  }

  toggleLockAll() {
    this.isLocked = !this.isLocked;
    this.notify();
    return this.isLocked;
  }

  toggleHideAll() {
    this.isGlobalHidden = !this.isGlobalHidden;
    this.notify();
    return this.isGlobalHidden;
  }

  saveToStorage() {
    try {
      localStorage.setItem("cd_drawing_store_v1", JSON.stringify(this.drawings.map(d => d.toJSON())));
    } catch (e) {
      console.warn("Failed to persist drawings to localStorage:", e);
    }
  }

  loadFromStorage() {
    try {
      const raw = localStorage.getItem("cd_drawing_store_v1");
      if (raw) {
        const parsed = JSON.parse(raw);
        this.drawings = parsed.map(item => new DrawingObject(item));
      }
    } catch (e) {
      console.warn("Failed to load drawings from localStorage:", e);
    }
  }
}

// Export a singleton instance if needed, or instantiate elsewhere.
export const globalDrawingStore = new DrawingStore();

