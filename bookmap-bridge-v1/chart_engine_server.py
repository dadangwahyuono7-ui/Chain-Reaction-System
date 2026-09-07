"""
═══════════════════════════════════════════════════════════════════════════
  SULTAN CHART ENGINE — CANDLE/TICK DATA API (port 8800)
  Adapted from Antigravity's standalone custom-chart-engine (2026-08-27).
  Serves ONLY real MT5 OHLC history + live tick stream for the "Chart"
  tab in the Sultan web dashboard (sultan/chart.html, port 8766).

  What changed from the original standalone version:
  - Dropped /api/storyline/analysis - it ran its OWN CMP/storyline calc
    (CMPLogic.js, storyline_calc.py) separate from EA V3, and its
    "liquidity ladder" was literally random.randint() dummy data. The
    Cockpit HUD on the chart tab now reads /sultan_status.json instead
    (same real data the rest of the dashboard uses) - see
    sultan/chart-assets/charts/WindowManager.js mapSultanStatusToCockpit().
  - Dropped the app.mount("/", StaticFiles(...)) at the bottom - this
    server no longer hosts its own frontend. The page itself is served
    by sultan_dashboard_server.py (port 8766) alongside the rest of the
    dashboard, so it shares that same origin for /sultan_status.json.
  - Everything below (MT5DataAdapter, DemoDataAdapter, MarketDataStore,
    the /api/chart/* endpoints, the tick websocket) is UNCHANGED - it was
    already reading genuine MT5 data via the MetaTrader5 Python API, with
    an honestly-labeled DEMO_DATA fallback (is_demo_data flag) when MT5
    isn't reachable, not fake data pretending to be real.
═══════════════════════════════════════════════════════════════════════════
"""

import asyncio
import glob
import json
import math
import os
import random
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Sultan Chart Engine — Candle/Tick Data API",
    description="Real MT5 OHLC history + live tick stream for the Sultan dashboard Chart tab",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. 21 SUPPORTED CHART TIMEFRAMES & SECONDS MAPPING
# ─────────────────────────────────────────────────────────────────────────────
TF_SECONDS = {
    "M1": 60,
    "M2": 120,
    "M3": 180,
    "M4": 240,
    "M5": 300,
    "M6": 360,
    "M10": 600,
    "M12": 720,
    "M15": 900,
    "M20": 1200,
    "M30": 1800,
    "H1": 3600,
    "H2": 7200,
    "H3": 10800,
    "H4": 14400,
    "H6": 21600,
    "H8": 28800,
    "H12": 43200,
    "D1": 86400,
    "W1": 604800,
    "MN1": 2592000,
}

SUPPORTED_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "US30", "NAS100"]

# ─────────────────────────────────────────────────────────────────────────────
# 2. MT5 DATA ADAPTER WITH NATIVE QUERY & BASE TF AGGREGATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class MT5DataAdapter:
    def __init__(self):
        self.available = False
        self.mt5 = None
        self.tf_map = {}
        self._init_mt5()

    def _init_mt5(self):
        try:
            import MetaTrader5 as mt5_lib
            if mt5_lib.initialize():
                self.available = True
                self.mt5 = mt5_lib
                self._setup_tf_map()
                print("[MT5DataAdapter] [OK] Connected to MetaTrader 5 Terminal successfully.")
            else:
                err = mt5_lib.last_error()
                print(f"[MT5DataAdapter] [WARN] MT5 Init failed ({err}). Operating in DEMO DATA mode.")
        except ImportError:
            print("[MT5DataAdapter] [INFO] MetaTrader5 python library not installed. Operating in DEMO DATA mode.")

    def _setup_tf_map(self):
        m = self.mt5
        self.tf_map = {
            "M1": getattr(m, "TIMEFRAME_M1", 1),
            "M2": getattr(m, "TIMEFRAME_M2", 2),
            "M3": getattr(m, "TIMEFRAME_M3", 3),
            "M4": getattr(m, "TIMEFRAME_M4", 4),
            "M5": getattr(m, "TIMEFRAME_M5", 5),
            "M6": getattr(m, "TIMEFRAME_M6", 6),
            "M10": getattr(m, "TIMEFRAME_M10", 10),
            "M12": getattr(m, "TIMEFRAME_M12", 12),
            "M15": getattr(m, "TIMEFRAME_M15", 15),
            "M20": getattr(m, "TIMEFRAME_M20", 20),
            "M30": getattr(m, "TIMEFRAME_M30", 30),
            "H1": getattr(m, "TIMEFRAME_H1", 16385),
            "H2": getattr(m, "TIMEFRAME_H2", 16386),
            "H3": getattr(m, "TIMEFRAME_H3", 16387),
            "H4": getattr(m, "TIMEFRAME_H4", 16388),
            "H6": getattr(m, "TIMEFRAME_H6", 16390),
            "H8": getattr(m, "TIMEFRAME_H8", 16392),
            "H12": getattr(m, "TIMEFRAME_H12", 16396),
            "D1": getattr(m, "TIMEFRAME_D1", 16408),
            "W1": getattr(m, "TIMEFRAME_W1", 32769),
            "MN1": getattr(m, "TIMEFRAME_MN1", 49153),
        }

    def get_rates(self, symbol: str, tf: str, count: int = 500) -> Optional[List[Dict[str, Any]]]:
        if not self.available or not self.mt5:
            return None
        
        # Ensure symbol is selected in MarketWatch
        if not self.mt5.symbol_select(symbol, True):
            return None
            
        mt5_tf = self.tf_map.get(tf)
        
        # 1. Attempt Native MT5 query
        if mt5_tf is not None:
            rates = self.mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
            if rates is not None and len(rates) > 0:
                candles = []
                for r in rates:
                    candles.append({
                        "time": int(r["time"]),
                        "open": float(r["open"]),
                        "high": float(r["high"]),
                        "low": float(r["low"]),
                        "close": float(r["close"]),
                        "volume": int(r["tick_volume"])
                    })
                return candles

        # 2. Aggregation Engine: Resample from M1 base data if native rates are unavailable
        return self._aggregate_from_m1(symbol, tf, count)

    def get_rates_range(self, symbol: str, tf: str, date_from: int, date_to: int) -> Optional[List[Dict[str, Any]]]:
        """Buat Replay/Backtest - candle di RENTANG WAKTU TERTENTU (bukan
        'N bar terakhir dari sekarang' kayak get_rates()). date_from/date_to
        Unix timestamp UTC detik. MT5 copy_rates_range butuh naive datetime
        (diperlakukan sebagai UTC oleh API-nya)."""
        if not self.available or not self.mt5:
            return None
        if not self.mt5.symbol_select(symbol, True):
            return None
        mt5_tf = self.tf_map.get(tf)
        if mt5_tf is None:
            return None
        # BUKAN datetime.utcfromtimestamp() - empirically dites (2026-08-27):
        # MT5 Python API di mesin ini nafsirin naive datetime pakai jam LOKAL
        # sistem (WIB/UTC+7), bukan UTC, meskipun dokumentasinya bilang UTC.
        # utcfromtimestamp() geser query 7 jam ke belakang dari yang diminta
        # (dibuktikan: minta 10:55-16:00 UTC, MT5 balikin candle 04:00-09:00).
        # fromtimestamp() (lokal) yang cocok sama epoch-like `time` field yang
        # udah dipakai konsisten di seluruh sistem ini (field `timestamp` EA,
        # `.time` tiap candle) - round-trip-nya jadi selaras.
        rates = self.mt5.copy_rates_range(
            symbol, mt5_tf,
            datetime.fromtimestamp(date_from),
            datetime.fromtimestamp(date_to)
        )
        if rates is None or len(rates) == 0:
            return None
        candles = []
        for r in rates:
            candles.append({
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": int(r["tick_volume"])
            })
        return candles

    def _aggregate_from_m1(self, symbol: str, tf: str, count: int) -> Optional[List[Dict[str, Any]]]:
        tf_sec = TF_SECONDS.get(tf, 300)
        needed_m1_bars = count * (tf_sec // 60) + 100
        # Clamp to reasonable limit
        needed_m1_bars = min(needed_m1_bars, 20000)
        
        m1_tf = self.mt5.TIMEFRAME_M1
        m1_rates = self.mt5.copy_rates_from_pos(symbol, m1_tf, 0, needed_m1_bars)
        if m1_rates is None or len(m1_rates) == 0:
            return None

        # Group by target timeframe bucket
        buckets: Dict[int, List[Any]] = {}
        for r in m1_rates:
            t = int(r["time"])
            bucket_time = (t // tf_sec) * tf_sec
            if bucket_time not in buckets:
                buckets[bucket_time] = []
            buckets[bucket_time].append(r)

        aggregated = []
        for bucket_time in sorted(buckets.keys()):
            bars = buckets[bucket_time]
            open_p = float(bars[0]["open"])
            close_p = float(bars[-1]["close"])
            high_p = max(float(b["high"]) for b in bars)
            low_p = min(float(b["low"]) for b in bars)
            vol = sum(int(b["tick_volume"]) for b in bars)
            aggregated.append({
                "time": bucket_time,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol
            })
            
        return aggregated[-count:] if len(aggregated) > count else aggregated

    def get_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.available or not self.mt5:
            return None
        t = self.mt5.symbol_info_tick(symbol)
        if not t:
            return None
        bid = float(t.bid)
        ask = float(t.ask)
        last = float(t.last) if t.last != 0 else bid
        return {
            "time": int(t.time),
            "bid": bid,
            "ask": ask,
            "last": last,
            "spread": round((ask - bid) * 100, 1)
        }

# ─────────────────────────────────────────────────────────────────────────────
# 3. SYNTHETIC DEMO DATA ADAPTER (Explicit Simulation for Offline/Dev Mode)
# ─────────────────────────────────────────────────────────────────────────────
class DemoDataAdapter:
    def __init__(self):
        self.base_prices = {
            "XAUUSD": 2888.50,
            "EURUSD": 1.08500,
            "GBPUSD": 1.29500,
            "USDJPY": 154.200,
            "BTCUSD": 67500.0,
            "US30": 39500.0,
            "NAS100": 19800.0
        }
        self.current_prices = dict(self.base_prices)

    def generate_candles(self, symbol: str, tf: str, count: int = 500) -> List[Dict[str, Any]]:
        sec_step = TF_SECONDS.get(tf, 300)
        now = int(time.time())
        # Align start time to timeframe bucket
        start_time = ((now - (count * sec_step)) // sec_step) * sec_step
        base_p = self.base_prices.get(symbol, 100.0)
        
        # Volatility factor based on instrument
        volat = base_p * 0.0008
        candles = []
        curr_price = base_p * 0.985
        
        for i in range(count):
            t = start_time + (i * sec_step)
            macro_wave = math.sin(i / 40.0) * (volat * 5)
            micro_wave = math.cos(i / 12.0) * (volat * 2)
            noise = random.gauss(0, volat)
            delta = (macro_wave * 0.05) + (micro_wave * 0.05) + noise
            
            open_p = curr_price
            close_p = open_p + delta
            high_p = max(open_p, close_p) + abs(random.gauss(0, volat * 0.7))
            low_p = min(open_p, close_p) - abs(random.gauss(0, volat * 0.7))
            vol = int(random.randint(50, 800) + abs(delta / (volat or 1) * 150))
            
            precision = 4 if ("USD" in symbol and "XAU" not in symbol and "BTC" not in symbol) else 2
            candles.append({
                "time": t,
                "open": round(open_p, precision),
                "high": round(high_p, precision),
                "low": round(low_p, precision),
                "close": round(close_p, precision),
                "volume": vol
            })
            curr_price = close_p
            
        self.current_prices[symbol] = curr_price
        return candles

    def get_simulated_tick(self, symbol: str) -> Dict[str, Any]:
        curr = self.current_prices.get(symbol, 100.0)
        volat = curr * 0.0001
        drift = random.gauss(0, volat)
        precision = 4 if ("USD" in symbol and "XAU" not in symbol and "BTC" not in symbol) else 2
        new_price = round(curr + drift, precision)
        self.current_prices[symbol] = new_price
        
        spread_val = round(volat * 0.5, precision)
        return {
            "time": int(time.time()),
            "bid": round(new_price - (spread_val / 2), precision),
            "ask": round(new_price + (spread_val / 2), precision),
            "last": new_price,
            "spread": 12.0
        }

# ─────────────────────────────────────────────────────────────────────────────
# 4. MARKET DATA STORE (Unified Orchestrator)
# ─────────────────────────────────────────────────────────────────────────────
class MarketDataStore:
    def __init__(self):
        self.mt5_adapter = MT5DataAdapter()
        self.demo_adapter = DemoDataAdapter()
        self.cache: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def is_live(self) -> bool:
        return self.mt5_adapter.available

    def get_history(self, symbol: str, tf: str, count: int = 500) -> Dict[str, Any]:
        if self.mt5_adapter.available:
            candles = self.mt5_adapter.get_rates(symbol, tf, count)
            if candles and len(candles) > 0:
                return {
                    "source": "MT5_LIVE",
                    "is_demo_data": False,
                    "symbol": symbol,
                    "timeframe": tf,
                    "count": len(candles),
                    "candles": candles
                }
                
        # Fallback to Demo Adapter with explicit flag
        candles = self.demo_adapter.generate_candles(symbol, tf, count)
        return {
            "source": "DEMO_DATA",
            "is_demo_data": True,
            "symbol": symbol,
            "timeframe": tf,
            "count": len(candles),
            "candles": candles
        }

    def get_history_range(self, symbol: str, tf: str, date_from: int, date_to: int) -> Dict[str, Any]:
        """Replay/Backtest - TIDAK fallback ke DemoDataAdapter kalau MT5 gak
        punya datanya (DemoDataAdapter cuma generate 'N bar terakhir dari
        sekarang', gak ada artinya buat tanggal spesifik di masa lalu -
        lebih jujur balikin kosong daripada nyodorin candle karangan buat
        backtest beneran)."""
        if self.mt5_adapter.available:
            candles = self.mt5_adapter.get_rates_range(symbol, tf, date_from, date_to)
            if candles and len(candles) > 0:
                return {
                    "source": "MT5_LIVE",
                    "is_demo_data": False,
                    "symbol": symbol,
                    "timeframe": tf,
                    "count": len(candles),
                    "candles": candles
                }
        return {
            "source": "UNAVAILABLE",
            "is_demo_data": False,
            "symbol": symbol,
            "timeframe": tf,
            "count": 0,
            "candles": [],
            "error": "MT5 gak punya history buat rentang ini (mungkin di luar retensi terminal, atau MT5 lagi offline)"
        }

    def get_current_tick(self, symbol: str) -> Dict[str, Any]:
        if self.mt5_adapter.available:
            tick = self.mt5_adapter.get_tick(symbol)
            if tick:
                tick["source"] = "MT5_LIVE"
                tick["is_demo_data"] = False
                return tick
        tick = self.demo_adapter.get_simulated_tick(symbol)
        tick["source"] = "DEMO_DATA"
        tick["is_demo_data"] = True
        return tick

data_store = MarketDataStore()

# Sama persis path yang dipakai sultan_dashboard_server.py buat baca
# sultan_status.json - dna_vault_YYYY-MM-DD.jsonl ada di folder yang sama,
# ditulis EA (WriteSultanStatus() di DD_ChainReaction_MultiTF_EA_v3.mq5,
# 1 baris/menit selama EA nyala, sejak v52.85/2026-08-23).
MT5_COMMON_FILES_DIR = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files"

# ─────────────────────────────────────────────────────────────────────────────
# 5. REST API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/chart/status")
def get_chart_engine_status():
    return {
        "engine": "Sultan Chart Engine — Candle/Tick Data API",
        "is_demo_data": not data_store.is_live,
        "source": "MT5_LIVE" if data_store.is_live else "DEMO_DATA",
        "supported_timeframes": list(TF_SECONDS.keys()),
        "supported_symbols": SUPPORTED_SYMBOLS,
        "server_time": int(time.time()),
        "timestamp_iso": datetime.utcnow().isoformat()
    }

@app.get("/api/chart/history")
def get_historical_candles(
    symbol: str = Query("XAUUSD", description="Instrument Symbol"),
    tf: str = Query("M5", description="21 Supported Timeframes (M1..MN1)"),
    count: int = Query(500, description="Bar Count")
):
    symbol = symbol.upper()
    tf = tf.upper()
    if tf not in TF_SECONDS:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe {tf}. Supported: {list(TF_SECONDS.keys())}")
    return data_store.get_history(symbol, tf, count)

@app.get("/api/chart/history-range")
def get_historical_candles_range(
    symbol: str = Query("XAUUSD", description="Instrument Symbol"),
    tf: str = Query("M5", description="21 Supported Timeframes (M1..MN1)"),
    date_from: int = Query(..., description="Unix timestamp UTC (detik) - awal rentang"),
    date_to: int = Query(..., description="Unix timestamp UTC (detik) - akhir rentang"),
):
    """Buat Replay/Backtest - candle di rentang waktu tertentu, bukan 'N bar
    terakhir'. Dipasangkan sama /api/replay/snapshots (timestamp yang sama)
    di sisi web buat merekonstruksi kondisi chart+HUD persis kayak waktu itu."""
    symbol = symbol.upper()
    tf = tf.upper()
    if tf not in TF_SECONDS:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe {tf}. Supported: {list(TF_SECONDS.keys())}")
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="date_to harus lebih besar dari date_from")
    return data_store.get_history_range(symbol, tf, date_from, date_to)

# v1 (Replay): endpoint di bawah ini SENGAJA dikasih prefix /api/chart/
# (bukan /api/replay/) - sultan_dashboard_server.py (port 8766) cuma
# reverse-proxy request yang path-nya diawali "/api/chart/" ke port 8800
# ini (lihat _proxy_to_chart_engine() di sana). Kalau dikasih prefix lain,
# request dari web (yang fetch relatif, bukan localhost:8800 eksplisit -
# biar jalan juga lewat tunnel/cloud) bakal 404 di sultan_dashboard_server
# duluan, gak pernah nyampe sini.
@app.get("/api/chart/replay-dates")
def get_replay_dates():
    """Daftar tanggal yang punya histori DNA Vault (S&D zones, Sierra Chart,
    confluence radar, wall, flow, dll - snapshot penuh EA, 1 per menit)."""
    pattern = os.path.join(MT5_COMMON_FILES_DIR, "dna_vault_*.jsonl")
    dates = []
    for path in glob.glob(pattern):
        name = os.path.basename(path)
        date_str = name.replace("dna_vault_", "").replace(".jsonl", "")
        try:
            with open(path, "r", encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())
        except Exception:
            count = 0
        if count > 0:
            dates.append({"date": date_str, "snapshot_count": count})
    dates.sort(key=lambda d: d["date"])
    return {"dates": dates}

@app.get("/api/chart/replay-snapshots")
def get_replay_snapshots(date: str = Query(..., description="YYYY-MM-DD")):
    """Full snapshot EA (sama persis shape sultan_status.json - regime,
    conviction, sd_zones, sierra_chart, confluence_radar, dll) buat 1 hari,
    1 per menit. Web nyocokin timestamp-nya sama candle dari
    /api/chart/history-range buat mode Replay - fungsi render yang SAMA
    yang dipakai live (renderCockpitData, updateSDZones, updateSierraChart,
    dst) dipakai ulang, cuma sumber datanya array historis, bukan poll live."""
    # Validasi format tanggal sederhana - cegah path traversal lewat query param
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD")

    path = os.path.join(MT5_COMMON_FILES_DIR, f"dna_vault_{date}.jsonl")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Gak ada histori DNA Vault buat tanggal {date}")

    snapshots = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                snapshots.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # Urutan baris di file harusnya kronologis (EA append 1x/menit), TAPI
    # jangan diasumsikan - kalau MT5 Strategy Tester (backtest historis)
    # pernah jalan di hari yang sama, WriteSultanStatus() bisa nyelipin
    # timestamp lama ke tengah file yang isinya live. Sort eksplisit di sini
    # sekali, biar Replay di web selalu maju kronologis apa pun kondisi filenya.
    snapshots.sort(key=lambda s: s.get("timestamp", 0))
    return {"date": date, "count": len(snapshots), "snapshots": snapshots}

@app.get("/api/chart/symbols")
def get_supported_symbols():
    return {
        "symbols": SUPPORTED_SYMBOLS
    }

@app.get("/api/chart/timeframes")
def get_supported_timeframes():
    return {
        "timeframes": list(TF_SECONDS.keys()),
        "categories": {
            "Minutes": ["M1", "M2", "M3", "M4", "M5", "M6", "M10", "M12", "M15", "M20", "M30"],
            "Hours": ["H1", "H2", "H3", "H4", "H6", "H8", "H12"],
            "Days": ["D1", "W1", "MN1"]
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. WEBSOCKET REALTIME STREAMING
# ─────────────────────────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for conn in list(self.active_connections):
            try:
                await conn.send_json(message)
            except Exception:
                self.disconnect(conn)

ws_manager = ConnectionManager()

@app.websocket("/ws/chart-stream")
async def websocket_chart_stream(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

@app.on_event("startup")
async def start_tick_broadcaster():
    asyncio.create_task(stream_loop())

async def stream_loop():
    """Broadcasts real-time ticks for all monitored symbols every 250ms"""
    while True:
        await asyncio.sleep(0.25)
        if not ws_manager.active_connections:
            continue
            
        ticks = {}
        for sym in SUPPORTED_SYMBOLS:
            ticks[sym] = data_store.get_current_tick(sym)
            
        payload = {
            "type": "MARKET_DATA_STREAM",
            "timestamp": int(time.time()),
            "is_demo_data": not data_store.is_live,
            "source": "MT5_LIVE" if data_store.is_live else "DEMO_DATA",
            "ticks": ticks
        }
        await ws_manager.broadcast(payload)

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 70)
    print(" [ENGINE] SULTAN CHART ENGINE - CANDLE/TICK DATA API")
    print(" [PORT]   Running on: http://localhost:8800 (data only, no page here)")
    print(" [PAGE]   Frontend served separately at sultan_dashboard_server.py -> /chart.html")
    print(" [SPECS]  21 Supported Chart Timeframes | MT5 Live + honest DEMO_DATA fallback")
    print("=" * 70 + "\n")
    uvicorn.run("chart_engine_server:app", host="0.0.0.0", port=8800, reload=False)
