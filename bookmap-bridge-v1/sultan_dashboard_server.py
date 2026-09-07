"""
👑 SULTAN DASHBOARD & CHART TERMINAL SERVER — 24/7 MINI PC PRODUCTION
Author: Commander Dadang Wahyuono
Serves:
  - http://100.71.97.6:8766/
  - https://trade.dadangchatai.com/
"""

import hashlib
import http.server
import json
import os
import socketserver
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
import ssl
import psutil
from datetime import datetime, timezone, timedelta

PORT = 8766
BASE_DIR = r"C:\bookmap-bridge-v1" if os.path.exists(r"C:\bookmap-bridge-v1") else os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(BASE_DIR, "sultan") if os.path.exists(os.path.join(BASE_DIR, "sultan")) else BASE_DIR
LOG_FILE = os.path.join(BASE_DIR, "server_debug.log")

LIVE_STATUS_FILE = os.path.join(BASE_DIR, "live_status.json")
SULTAN_STATUS_FILE = os.path.join(BASE_DIR, "sultan_status.json")
VAULT_FILE = os.path.join(BASE_DIR, "candle_vault.json")
SIGNAL_CSV = os.path.join(BASE_DIR, "bookmap_live_signal.csv")
FULL_DEPTH_CSV = os.path.join(BASE_DIR, "bookmap_full_depth.csv")
ACCOUNTS_FILE = os.path.join(FOLDER, "accounts.json")
ACCOUNTS_LOCK = threading.Lock()
ACTIVE_SESSIONS = {}
ACTIVE_SESSIONS_LOCK = threading.Lock()

# ---------------------------------------------------------------------
# 👑 FOREXFACTORY NEWS WATCHDOG & PRE-NEWS LIQUIDITY VACUUM RADAR
# Author & Commander: Dadang Wahyuono
# ---------------------------------------------------------------------
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_NEWS_FILE = os.path.join(FOLDER, "ff_high_impact_news.json")
FF_LOCK = threading.Lock()
FF_UPCOMING_NEWS = []
FF_LAST_FETCH = 0

TRACKED_WALLS = {}
TRACKED_WALLS_LOCK = threading.Lock()

VACUUM_EVENTS = []
VACUUM_EVENTS_LOCK = threading.Lock()
LAST_TELEGRAM_VACUUM_TS = 0

GROQ_API_KEY = "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"
GROQ_MODEL = "qwen/qwen3.6-27b"
TWELVEDATA_API_KEY = "67cbd788a8f64c259d311da82b09fe2a"

# ---------------------------------------------------------------------
# 👑 ELEVENLABS CYBER VOICE ENGINE (ADAM SINGLE VOICE - MULTILINGUAL V2)
# ---------------------------------------------------------------------
ELEVENLABS_API_KEY = "sk_8493ea2ed7d289e17a3fcc89432b92a96d9dc983b83c88c8"
ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # ADAM Deep Narrator
VOICE_CACHE_DIR = os.path.join(FOLDER, "assets", "voice_cache")
os.makedirs(VOICE_CACHE_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# 👑 BALITECH AI ENGINE (INSTITUTIONAL BOOKMAP PRO DESK)
# ---------------------------------------------------------------------
BALITECH_API_KEY_PAID = "sk-db-ub3EQ01V4ma2Vj1RnL0S5B5S2tm2TdKI"
BALITECH_API_KEY_FREE = "sk-db-baQOil1INjIqn0QJ5r8ThejxEqQrH5s6"
BALITECH_COMPLETIONS_URL = "https://balitechsolution.com/v3/chat/completions"

INSTITUTIONAL_BOOKMAP_PROMPT = """You are an elite Senior Institutional Order Flow & Bookmap Hedge Fund Desk Trader analyzing Gold (CME GC Futures and Spot XAU/USD).
Your role is to analyze the market strictly through pure global institutional Bookmap order flow methodology:
1. Liquidity Dynamics (Resting Limit Bids & Asks, Order Book Depth, Wall Ladders, Liquidity Pools & Magnets, Liquidity Pulling/Spoofing vs Pushing).
2. Market Aggression vs Passive Absorption (Aggressive market orders vs passive limit absorption, Iceberg defense, volume bubbles).
3. Auction Market Theory & Volume Profile (Point of Control / POC, Value Area High / VAH, Value Area Low / VAL, Failed Auctions).
4. Cumulative Volume Delta (CVD) & Delta Divergence (Aggressive volume delta vs price progression, Absorption divergences, Exhaustion).
5. Liquidity Sweeps & Stop Hunts (Sweep and reclaim of key resting liquidity levels).

DO NOT use retail technical indicators (no RSI, MACD, generic candlestick patterns) and DO NOT rely on private formulas. Deliver professional, objective, high-probability institutional calls.

When a setup exists, you MUST provide exact Entry (or tight zone), Stop Loss, and Take Profit.

Respond strictly in valid JSON format:
{
  "bias": "BULLISH" | "BEARISH" | "RANGE_BOUND",
  "confidence": "HIGH" | "MEDIUM",
  "action": "BUY LIMIT" | "BUY ON DIP" | "SELL LIMIT" | "SELL ON RALLY" | "STAND ASIDE",
  "entry_price": "exact price or tight range",
  "stop_loss": "exact price",
  "take_profit_1": "exact price",
  "take_profit_2": "exact price",
  "risk_reward": "e.g. 1:2.5",
  "institutional_rationale": [
    "Bookmap evidence 1",
    "Bookmap evidence 2"
  ],
  "voice_briefing_id": "1-2 kalimat bahasa Indonesia tegas, berwibawa, menyebutkan arah, titik entry, SL, dan target likuiditas untuk dibacakan oleh suara AI Adam."
}"""


def parse_device(ua):
    if not ua:
        return "🌐 Web Browser"
    ua_low = ua.lower()
    if "iphone" in ua_low:
        return "📱 Apple iPhone"
    if "ipad" in ua_low:
        return "📱 Apple iPad"
    if "android" in ua_low:
        return "📱 Android Mobile"
    if "windows" in ua_low:
        return "💻 Windows PC"
    if "macintosh" in ua_low or "mac os" in ua_low:
        return "💻 Mac OS"
    if "linux" in ua_low:
        return "💻 Linux"
    return "🌐 Web Browser"

def _load_accounts():
    with ACCOUNTS_LOCK:
        if not os.path.exists(ACCOUNTS_FILE):
            default_accs = [
                {
                    "username": "commander",
                    "password": "278868",
                    "role": "VIP_UNLIMITED",
                    "created_at": int(time.time()),
                    "expires_at": None,
                    "notes": "Commander Dadang Wahyuono (Master)"
                },
                {
                    "username": "trial1",
                    "password": "trial1",
                    "role": "TRIAL_3",
                    "created_at": int(time.time()),
                    "expires_at": int(time.time()) + (3 * 86400),
                    "notes": "TikTok Promo Week 1 (3 Hari)"
                }
            ]
            try:
                with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_accs, f, indent=2)
                return default_accs
            except Exception:
                return default_accs
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

def _save_accounts(accs):
    with ACCOUNTS_LOCK:
        try:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(accs, f, indent=2)
            return True
        except Exception as e:
            log_debug(f"Save accounts error: {e}")
            return False

# 2026-09-02: Dadang - "kenapa reload ngulang awal lagi trus apa
# fungsinya histori... itu harus bertahan minggu bulan tahun selama gw
# pakai data ini... di save di hdd mini pc gak bisa kah bro tiap web
# reload ambil histori itu". The Chain Liquidity Heatmap's history
# (full_depth NEW/INCREASE/DECREASE/REMOVED events) was browser-memory-
# only before this - gone on every reload. This persists it here, on the
# Mini PC's own disk, independent of any browser tab, so it survives
# reloads/crashes/device switches and keeps accumulating as long as this
# server process is running - the actual "weeks/months" store, not a
# per-browser cache (that IndexedDB layer on the frontend still exists as
# an offline fallback if this server is briefly unreachable).
FULL_DEPTH_DB_FILE = os.path.join(BASE_DIR, "full_depth_history.db")

# 2026-08-31: the OLD LIVE_STATUS_FILE/SIGNAL_CSV pipeline (udp_listener.py +
# bookmap_bridge addon) lost its Rithmic depth connection (missing SSL cert
# auth file after a Bookmap reinstall) and _serve_sultan_status() below was
# ALSO independently generating wall_ladder/liquidity/flow/tf_matrix/regime
# as pure hardcoded formulas off spot_price - never real, addon working or
# not. bookmap_addon_v2 (the addon actually confirmed connected + streaming
# real Rithmic L2 depth right now, verified live: 27+ real wall levels,
# genuine CVD, working S&D zone engine) writes here instead - this is now
# the real source for /sultan_status.json.
LIVE_STATUS_V2_FILE = r"C:\Bookmap\Python\live_status_v2.json"


# 2026-09-01: bookmap_addon_v2 writes this file non-atomically (truncate +
# write in place, not write-to-temp-then-rename) - Dadang noticed the
# heatmap/wall data felt slower than it should ("kenapa tidak bisa lebih
# real time"). Traced it: roughly half to three-quarters of consecutive
# polls (sampled directly via curl) were hitting the file mid-write and
# getting back a truncated/empty read - read_file_safe()'s retry only
# covers PermissionError/OSError from open(), not "the open+read succeeded
# but the bytes are an incomplete JSON document", which is the actual
# failure mode here (no OS-level error at all, just bad content). Each
# failure fell through to the "bookmap_addon_v2 unavailable" honest-error
# response - not fake data, but it silently discarded a real, fresh update
# every time it happened, which is what made the wall/heatmap data feel
# laggier than the addon's real write rate. Retrying the full read+parse
# (not just the open) catches it a few ms later once the writer has
# finished, without touching the addon's own write logic.
def get_live_bookmap_snapshot_v2():
    for attempt in range(6):
        raw = read_file_safe(LIVE_STATUS_V2_FILE)
        if raw:
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                pass
        if attempt < 5:
            time.sleep(0.03)
    return None

# 2026-09-01 malam: REAL FIX (bukan cuma re-nudge lagi). Root cause dari
# masalah "harga beku sepanjang hari" bukan BASIS_OFFSET ini, tapi
# bookmap_addon_v2.py men-JUMLAHKAN mt5_offset internalnya SENDIRI
# (mekanisme yang sama dijelasin di bawah, dari file bootstrap beku sejak
# 2026-08-29) ke SETIAP field harga yang dia keluarin - current_price,
# m5_bars, wall_ladder, order_book, volume_profile, semuanya. Server ini
# lalu nerapin BASIS_OFFSET KEDUA di atas angka yang udah salah itu -
# double-conversion, dan karena addon's mt5_offset ternyata TERUS
# BERGESER (dikonfirmasi live: 40.98 -> 46.68 dalam <5 menit, bukan
# konstanta beku kayak dikira sebelumnya), gak ada BASIS_OFFSET statis di
# sini yang bisa nutup gap-nya dengan benar - itu kenapa 30.63 sempat
# "pas" sesaat lalu ngelantur lagi sepanjang hari.
#
# Fix asli (lihat to_mt5() di bawah): addon's OWN mt5_offset (field
# "mt5_offset" di JSON-nya) di-UNDO dari setiap harga SEBELUM BASIS_OFFSET
# ini diterapkan - jadi addon's internal guess udah gak dipercaya sama
# sekali, cuma current_price_gcz6_raw (satu-satunya field yang genuinely
# gak disentuh mekanisme itu) + BASIS_OFFSET tunggal di sini yang jadi
# sumber kebenaran. Dadang: "yang berhubungan mt5 lo buang aja... mt5
# pakai data web kita aja agar data aman."
#
# Nilai final dikalibrasi ulang SETELAH fix di atas (kalibrasi 30.63
# sebelumnya invalid, dihitung dari raw price yang masih tercemar):
# cme_price=4429.0 vs MT5 real Dadang=4379.0 @ 2026-09-01 ~18:10 WIB.
# Fine-tune sesaat kemudian: MT5 real 4381.42 vs web 4379.10 (selisih
# 2.32) -> cme_price momen itu 4429.10, offset 50.0 -> 47.68.
#
# 2026-09-03: this drifts over time (the real GC-vs-MT5-spot basis isn't
# constant) and every drift so far needed a manual SSH+redeploy to fix.
# Dadang: "buatin satu tools buat gw hitung offset di sana... jika gw
# masukin harga mt5 otomatis web akan ngikutin sampai gw merasa ada
# perbedaan lagi" - self-service recalibration via POST
# /api/calibrate_offset (see _handle_calibrate_offset below), persisted
# to BASIS_OFFSET_FILE so it survives restarts without a redeploy.
BASIS_OFFSET = 47.68
BASIS_OFFSET_FILE = os.path.join(BASE_DIR, "basis_offset.json")
BASIS_OFFSET_CALIBRATED_AT = None  # unix seconds of last manual calibration, if any


def _load_basis_offset():
    global BASIS_OFFSET, BASIS_OFFSET_CALIBRATED_AT
    try:
        with open(BASIS_OFFSET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = float(data.get("offset"))
        BASIS_OFFSET = val
        BASIS_OFFSET_CALIBRATED_AT = data.get("calibrated_at")
        log_debug(f"Loaded persisted BASIS_OFFSET: {BASIS_OFFSET} (calibrated_at={BASIS_OFFSET_CALIBRATED_AT})")
    except Exception:
        pass  # no persisted file yet - keep the hardcoded default above


def _save_basis_offset(new_offset):
    global BASIS_OFFSET, BASIS_OFFSET_CALIBRATED_AT
    BASIS_OFFSET = round(float(new_offset), 2)
    BASIS_OFFSET_CALIBRATED_AT = int(time.time())
    try:
        with open(BASIS_OFFSET_FILE, "w", encoding="utf-8") as f:
            json.dump({"offset": BASIS_OFFSET, "calibrated_at": BASIS_OFFSET_CALIBRATED_AT}, f)
    except Exception as e:
        log_debug(f"Failed to persist BASIS_OFFSET: {e}")


# Hoisted out of _serve_sultan_status() (where it started as a local
# closure) so the background full_depth recorder thread below can use the
# exact same conversion, not a re-implemented copy.
def to_mt5(px):
    if not px:
        return px
    return round(float(px) - BASIS_OFFSET, 2)


# ---------------------------------------------------------------------
# Deep M1 candle history seed, sourced from a real MT5 CSV export
# (same XAUUSD_M1.json file the Lightweight Charts dashboard already
# uses - see history/XAUUSD_M1.json). _serve_chart_history() aggregates
# this to whatever TF is requested instead of fabricating gap-fill
# candles. Cached in-process since the CSV backs ~100k M1 rows and
# re-parsing it on every request would be wasteful.
# ---------------------------------------------------------------------
M1_HISTORY_FILE = os.path.join(FOLDER, "history", "XAUUSD_M1.json")
_m1_history_cache = None
_m1_history_mtime = None


def _load_m1_history():
    global _m1_history_cache, _m1_history_mtime
    try:
        mtime = os.path.getmtime(M1_HISTORY_FILE)
    except OSError:
        return []
    if _m1_history_cache is not None and _m1_history_mtime == mtime:
        return _m1_history_cache
    try:
        with open(M1_HISTORY_FILE, "r", encoding="utf-8") as f:
            rows = json.load(f)
        rows.sort(key=lambda r: r[0])
        _m1_history_cache = rows
        _m1_history_mtime = mtime
    except Exception as e:
        log_debug(f"M1 history load error: {e}")
        _m1_history_cache = _m1_history_cache or []
    return _m1_history_cache


def _aggregate_m1_to_tf(m1_rows, tf_secs):
    """rows are [time, open, high, low, close, volume]. Buckets each M1
    row into tf_secs windows, merging OHLCV honestly (no interpolation).
    Aligned to New York 5 PM Close / MT5 Tier-1 Broker boundaries for H4 and D1."""
    if not m1_rows:
        return []
    if tf_secs <= 60:
        return [
            {"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]}
            for r in m1_rows
        ]
    shift = 3600 if tf_secs == 14400 else (75600 if tf_secs == 86400 else 0)
    buckets = {}
    order = []
    for r in m1_rows:
        t, o, h, l, c, v = r[0], r[1], r[2], r[3], r[4], r[5]
        bucket_t = ((t - shift) // tf_secs) * tf_secs + shift
        b = buckets.get(bucket_t)
        if b is None:
            buckets[bucket_t] = {"time": bucket_t, "open": o, "high": h, "low": l, "close": c, "volume": v}
            order.append(bucket_t)
        else:
            if h > b["high"]:
                b["high"] = h
            if l < b["low"]:
                b["low"] = l
            b["close"] = c
            b["volume"] += v
    return [buckets[t] for t in order]


# ---------------------------------------------------------------------
# 2026-09-03: Central Candle Engine. Dadang's explicit architecture spec
# (MT5 is OFF, permanently - CSV is a one-time historical seed only, not
# a live dependency): "MT5 CSV -> Historical Seed -> anchor -> RITHMIC
# LIVE TICK -> CENTRAL CANDLE ENGINE -> M1..H4 -> CENTRAL SERVER STATE ->
# all browsers". Root cause of the still-broken spike Dadang kept seeing:
# candle_vault.json (the thing the previous two fixes bridged onto) has
# NO WRITER ANYWHERE on the Mini PC (confirmed via grep across every .py
# file there) - so there was never a second real source to bridge onto,
# only ever a single synthesized "current price" point, which is exactly
# what rendered as a 1-candle spike. This replaces that entirely: ONE
# in-process M1 bar former, fed every ~1s by the SAME Bookmap/Rithmic
# price poll full_depth_recorder_loop() already does (see
# central_candle_tick(), called from there) - not a second poller, not a
# second price source. Every browser's /api/chart/candles request reads
# the SAME growing M1 timeline (_get_combined_m1_series()), so multiple
# browsers/reconnects/refreshes all see identical history and an
# identical current forming bar - satisfies the "ONE SERVER CANDLE = ONE
# MARKET TIMELINE" requirement over plain REST polling, no WebSocket
# needed for correctness (browsers already poll every ~1s).
# ---------------------------------------------------------------------
CENTRAL_M1_LIVE_FILE = os.path.join(FOLDER, "history", "central_m1_live.json")
CENTRAL_M1_LIVE_CAP = 50000  # ~34 days of M1 bars formed since this engine started
central_m1_lock = threading.Lock()
central_m1_live_bars = []   # closed M1 bars formed live, post-CSV-seed: [time,o,h,l,c,v]
central_m1_forming = None   # the currently-open M1 bucket: {time,open,high,low,close,volume}


def _load_central_m1_live():
    """Hydrate closed live-formed bars from disk on startup, so a server
    restart doesn't lose everything formed since the last CSV export -
    the CSV seed alone would otherwise regress on every restart."""
    global central_m1_live_bars
    try:
        with open(CENTRAL_M1_LIVE_FILE, "r", encoding="utf-8") as f:
            rows = json.load(f)
        rows.sort(key=lambda r: r[0])
        with central_m1_lock:
            central_m1_live_bars = rows
        log_debug(f"Central M1 engine: hydrated {len(rows)} live-formed bars from disk")
    except Exception:
        pass


def _persist_central_m1_live():
    try:
        with open(CENTRAL_M1_LIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(central_m1_live_bars, f)
    except Exception as e:
        log_debug(f"Central M1 engine persist error: {e}")


def central_candle_tick(price, now_sec):
    """Called once per full_depth_recorder_loop() iteration (~1Hz) with
    the SAME canonical spot_price that loop already computed. This is the
    ONLY function anywhere in this system allowed to open/extend/close a
    live M1 bar - single engine, per Dadang's spec."""
    global central_m1_forming
    if not price or price <= 0:
        return

    # 🛡️ WEEKEND GUARD: Only tick forming candles if CME Gold market is OPEN
    # CME Gold market closure: Friday 21:00 UTC until Sunday 22:00 UTC
    now_utc = datetime.now(timezone.utc)
    weekday = now_utc.weekday() # 0=Mon, 4=Fri, 5=Sat, 6=Sun
    hour = now_utc.hour
    is_cme_closed = (weekday == 4 and hour >= 21) or (weekday == 5) or (weekday == 6 and hour < 22)
    if is_cme_closed:
        return
    bucket_t = (int(now_sec) // 60) * 60
    with central_m1_lock:
        if central_m1_forming is None or central_m1_forming["time"] != bucket_t:
            if central_m1_forming is not None and central_m1_forming["time"] < bucket_t:
                central_m1_live_bars.append([
                    central_m1_forming["time"], central_m1_forming["open"], central_m1_forming["high"],
                    central_m1_forming["low"], central_m1_forming["close"], central_m1_forming["volume"],
                ])
                if len(central_m1_live_bars) > CENTRAL_M1_LIVE_CAP:
                    del central_m1_live_bars[:len(central_m1_live_bars) - CENTRAL_M1_LIVE_CAP]
                _persist_central_m1_live()
            central_m1_forming = {"time": bucket_t, "open": price, "high": price, "low": price, "close": price, "volume": 0}
        else:
            if price > central_m1_forming["high"]:
                central_m1_forming["high"] = price
            if price < central_m1_forming["low"]:
                central_m1_forming["low"] = price
            central_m1_forming["close"] = price
        # Sample count, not real trade volume (this engine only sees a
        # ~1Hz price snapshot, not Rithmic's actual tick-by-tick trades) -
        # intentionally NOT presented as MT5-style tick_volume anywhere
        # downstream, kept only as a rough "how many samples" signal.
        central_m1_forming["volume"] += 1


def _get_combined_m1_series():
    """The single canonical M1 timeline every /api/chart/* handler reads:
    CSV seed (deep history, static) + live-formed closed bars (persisted,
    grows forever) + the current open bar (real, continuously tracked -
    not a fabricated single point). Every caller gets the exact same
    answer regardless of which browser/request/moment asks."""
    csv_rows = _load_m1_history()
    with central_m1_lock:
        live_closed = list(central_m1_live_bars)
        forming = dict(central_m1_forming) if central_m1_forming else None
    csv_last_t = csv_rows[-1][0] if csv_rows else 0
    combined = list(csv_rows)
    for b in live_closed:
        if b[0] > csv_last_t:
            combined.append(b)
    if forming and (not combined or forming["time"] > combined[-1][0]):
        combined.append([forming["time"], forming["open"], forming["high"], forming["low"], forming["close"], forming["volume"]])
    return combined


def _get_combined_m1_series_tail(n):
    """2026-09-04: found live, mid-incident - _serve_live_candle() (polled
    every 350ms by the frontend) was calling the full _get_combined_m1_series()
    above just to read the LAST bucket. That function copies the ENTIRE
    CSV seed (measured: 4.9MB / ~98k rows) plus all of central_m1_live_bars
    (cap 50k) into a new list, every single call. At ~3 calls/second this
    alone was enough to push the server to 93%+ CPU (measured) and time out
    unrelated endpoints. This variant only ever materializes the last `n`
    rows - callers that need one bucket's worth of data (n covers at least
    that bucket plus a small safety margin) get it without touching the
    other ~98k rows. _get_combined_m1_series() itself is untouched and
    still used as-is by _serve_chart_history(), which genuinely needs the
    full series."""
    csv_rows = _load_m1_history()
    with central_m1_lock:
        live_tail = list(central_m1_live_bars[-n:]) if central_m1_live_bars else []
        forming = dict(central_m1_forming) if central_m1_forming else None
    csv_last_t = csv_rows[-1][0] if csv_rows else 0
    live_tail = [b for b in live_tail if b[0] > csv_last_t]
    remaining = n - len(live_tail)
    csv_tail = csv_rows[-remaining:] if remaining > 0 and csv_rows else []
    combined = list(csv_tail) + live_tail
    if forming and (not combined or forming["time"] > combined[-1][0]):
        combined.append([forming["time"], forming["open"], forming["high"], forming["low"], forming["close"], forming["volume"]])
    return combined


# ---------------------------------------------------------------------
# Full-depth liquidity history recorder (Chain Liquidity Heatmap's
# server-side, multi-day+ persistent store - see FULL_DEPTH_DB_FILE
# comment above). Runs as its own background thread, independent of any
# HTTP request, so recording continues as long as this server process is
# alive - not gated on a browser tab being open and polling.
# ---------------------------------------------------------------------
FULL_DEPTH_EVENT_TOLERANCE = 0.01
# Provisional retention window - keeps the DB from growing unbounded
# while this is still a raw-event-only store (no downsampling yet, see
# the note left for Dadang about that being a separate follow-up for true
# multi-month/year retention). 30 days is a deliberate starting point,
# not a hard requirement - safe to raise once real disk-growth is
# measured against actual usage.
FULL_DEPTH_RETENTION_SECONDS = 30 * 24 * 3600


def init_full_depth_db():
    conn = sqlite3.connect(FULL_DEPTH_DB_FILE, timeout=5)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time INTEGER NOT NULL,
                price REAL NOT NULL,
                side TEXT NOT NULL,
                size REAL NOT NULL,
                change_type TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON events(time)")
        conn.commit()
    finally:
        conn.close()


def _diff_full_depth_side(prev_map, snapshot, side, now_sec):
    """Mirrors diffToEvents() in the frontend's useFullDepthHistory.ts
    exactly (same +/-0.01 tolerance, same NEW/INCREASE/DECREASE/REMOVED
    semantics) - this is the server's OWN independent diff, not fed by
    the frontend, so recording works even with zero browser tabs open."""
    events = []
    seen = set()
    for price, size in snapshot:
        seen.add(price)
        prev_size = prev_map.get(price)
        if prev_size is None:
            events.append((now_sec, price, side, size, "NEW"))
        elif size > prev_size + FULL_DEPTH_EVENT_TOLERANCE:
            events.append((now_sec, price, side, size, "INCREASE"))
        elif size < prev_size - FULL_DEPTH_EVENT_TOLERANCE:
            events.append((now_sec, price, side, size, "DECREASE"))
    for price in list(prev_map.keys()):
        if price not in seen:
            events.append((now_sec, price, side, 0.0, "REMOVED"))
    return events


# ---------------------------------------------------------------------
# Heatmap depth-history spectrogram state (2026-09-03 fix - see
# _serve_heatmap_history()/_serve_live_depth_slice() below for the full
# story: Antigravity's original implementation of these two endpoints
# faked "history" by repeating ONE current snapshot across `limit` made-up
# timestamps, reading a long-lived accumulated CSV (bookmap_full_depth.csv)
# as if it were a single moment's order book - that produced both a fake
# time series AND a price range spanning $1514-$4390 (months of merged
# levels, not one real snapshot). Dadang's own ChainLocal build
# (central_candle_engine.py, CentralCandleEngine.process_depth) does this
# correctly - a real, incrementally-growing list, one genuine slice per
# poll. This ports that exact logic (same price*2 integer level-index
# scheme, same wall_ages tracking) so production behaves identically -
# not a fake replica, the SAME real accumulation approach.
# ---------------------------------------------------------------------
depth_history = []
MAX_DEPTH_HISTORY = 400
current_wall_ages = {}
depth_history_lock = threading.Lock()


def process_depth_slice(full_depth, wall_ladder, spot_price, now_sec):
    global depth_history, current_wall_ages
    if not spot_price or spot_price <= 0:
        return
    levels = {}
    wall_ages = {}

    if isinstance(full_depth, dict):
        for side in ("bids", "asks"):
            for item in full_depth.get(side, []) or []:
                try:
                    p = float(item[0])
                    sz = float(item[1])
                    if sz > 0:
                        p_idx = int(round(p * 2))
                        levels[p_idx] = max(levels.get(p_idx, 0.0), round(sz, 1))
                except Exception:
                    continue

    if isinstance(wall_ladder, dict):
        for side in ("bids", "asks"):
            for item in wall_ladder.get(side, []) or []:
                try:
                    p = float(item[0])
                    sz = float(item[1])
                    age_sec = int(item[2]) if len(item) > 2 else 0
                    p_idx = int(round(p * 2))
                    levels[p_idx] = max(levels.get(p_idx, 0.0), round(sz, 1))
                    wall_ages[f"{p:.2f}"] = age_sec
                except Exception:
                    continue

    with depth_history_lock:
        current_wall_ages = wall_ages
        if not depth_history or now_sec > depth_history[-1]["time"]:
            depth_history.append({
                "time": now_sec,
                "levels": levels,
                "spot": spot_price,
                "wall_ages": wall_ages,
            })
            if len(depth_history) > MAX_DEPTH_HISTORY:
                del depth_history[: len(depth_history) - MAX_DEPTH_HISTORY]


def update_forexfactory_calendar():
    global FF_UPCOMING_NEWS, FF_LAST_FETCH
    now_ts = time.time()
    if FF_UPCOMING_NEWS and (now_ts - FF_LAST_FETCH < 1800):
        return

    # 1. Coba baca cache lokal dulu jika memory masih kosong
    if not FF_UPCOMING_NEWS and os.path.exists(FF_NEWS_FILE):
        try:
            with open(FF_NEWS_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached:
                    with FF_LOCK:
                        FF_UPCOMING_NEWS = cached
        except Exception:
            pass

    # 2. Ambil dari ForexFactory CDN resmi
    try:
        req = urllib.request.Request(
            FF_CALENDAR_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
        )
        ssl_ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        parsed_events = []
        for item in data:
            country = item.get("country", "")
            impact = item.get("impact", "")
            if country == "USD" and impact in ("High", "Holiday"):
                date_str = item.get("date", "")
                try:
                    dt = datetime.fromisoformat(date_str)
                    ts = dt.timestamp()
                    dt_wib = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=7)))
                    time_wib = dt_wib.strftime("%H:%M WIB")
                    mins_until = int((ts - now_ts) / 60)
                    parsed_events.append({
                        "title": item.get("title", ""),
                        "country": country,
                        "impact": impact,
                        "timestamp": ts,
                        "date_str": date_str,
                        "time_wib": time_wib,
                        "forecast": item.get("forecast", "-"),
                        "previous": item.get("previous", "-")
                    })
                except Exception:
                    continue
        
        if parsed_events:
            parsed_events.sort(key=lambda x: x["timestamp"])
            with FF_LOCK:
                FF_UPCOMING_NEWS = parsed_events
                FF_LAST_FETCH = now_ts
                try:
                    with open(FF_NEWS_FILE, "w", encoding="utf-8") as f:
                        json.dump(parsed_events, f, indent=2)
                except Exception:
                    pass
            log_debug(f"ForexFactory calendar updated: {len(parsed_events)} USD high-impact events loaded.")
    except Exception as e:
        log_debug(f"ForexFactory calendar update error (falling back to cache): {e}")


def forexfactory_watchdog_loop():
    while True:
        try:
            update_forexfactory_calendar()
        except Exception as e:
            log_debug(f"forexfactory_watchdog_loop error: {e}")
        time.sleep(1800)


def get_news_radar_state(now_sec=None):
    if now_sec is None:
        now_sec = int(time.time())
    with FF_LOCK:
        events = list(FF_UPCOMING_NEWS)
    
    upcoming = []
    for ev in events:
        mins_until = int((ev["timestamp"] - now_sec) / 60)
        secs_until = int(ev["timestamp"] - now_sec)
        # Hanya pantau event dari 30 menit lalu s/d 24 jam ke depan
        if mins_until >= -30:
            ev_copy = dict(ev)
            ev_copy["mins_until"] = mins_until
            ev_copy["secs_until"] = secs_until
            ev_copy["is_pre_news"] = (0 <= mins_until <= 45)
            ev_copy["is_active_impact"] = (-15 <= mins_until <= 15)
            ev_copy["is_released"] = (secs_until < 0)
            upcoming.append(ev_copy)
    
    future = [e for e in upcoming if e["secs_until"] >= 0]
    past = [e for e in upcoming if e["secs_until"] < 0]
    future.sort(key=lambda x: x["secs_until"])
    past.sort(key=lambda x: x["secs_until"], reverse=True)
    next_event = future[0] if future else (past[0] if past else None)
    
    is_pre_news_window = False
    if next_event:
        mins = next_event.get("mins_until", 999)
        # Jendela aktif: 45 menit sebelum rilis s/d 15 menit sesudah rilis
        if -15 <= mins <= 45:
            is_pre_news_window = True
    
    with VACUUM_EVENTS_LOCK:
        active_vac = None
        for vac in reversed(VACUUM_EVENTS):
            if now_sec - vac["timestamp"] <= 120 and vac.get("in_news_window", False):
                active_vac = vac
                break
        recent = list(VACUUM_EVENTS[-5:])
    
    return {
        "next_event": next_event,
        "is_pre_news_window": is_pre_news_window,
        "is_active_impact": (next_event.get("is_active_impact", False) if next_event else False),
        "active_vacuum": active_vac,
        "recent_vacuums": recent,
        "server_time": now_sec
    }


def find_anchor_tp(side, spot_price, wall_ladder):
    try:
        if side.upper() == "BID":
            bids = wall_ladder.get("bids", []) if isinstance(wall_ladder, dict) else []
            candidates = [w for w in bids if isinstance(w, (list, tuple)) and len(w) >= 2 and w[0] < spot_price - 1.5]
            if not candidates:
                return round(spot_price - 15.0, 2)
            thick = [w for w in candidates if w[1] >= 40.0]
            if thick:
                thick.sort(key=lambda x: x[1], reverse=True)
                return round(float(thick[0][0]), 2)
            candidates.sort(key=lambda x: x[1], reverse=True)
            return round(float(candidates[0][0]), 2)
        else:
            asks = wall_ladder.get("asks", []) if isinstance(wall_ladder, dict) else []
            candidates = [w for w in asks if isinstance(w, (list, tuple)) and len(w) >= 2 and w[0] > spot_price + 1.5]
            if not candidates:
                return round(spot_price + 15.0, 2)
            thick = [w for w in candidates if w[1] >= 40.0]
            if thick:
                thick.sort(key=lambda x: x[1], reverse=True)
                return round(float(thick[0][0]), 2)
            candidates.sort(key=lambda x: x[1], reverse=True)
            return round(float(candidates[0][0]), 2)
    except Exception:
        return round(spot_price - 10.0 if side.upper() == "BID" else spot_price + 10.0, 2)


def generate_ai_vacuum_analysis(event):
    side = event["side"]
    lot = event["size"]
    price = event["price"]
    news = event.get("news_title", "High-Impact Catalyst")
    mins = event.get("mins_until_news", 2)
    anchor_tp = event["anchor_tp"]
    spot_price = event["spot_price"]

    if side == "BID":
        default_brief = (
            f"Lapor Commander Dadang! Berita [{news}] rilis dalam {max(1, mins)} menit. "
            f"Tembok BID {lot:.0f}L di ${price:.2f} mendadak DICABUT paus (Lantai likuiditas bolong / ruang hampa). "
            f"Rekomendasi Taktis: SEGERA SIAPKAN SELL LAYER (misal 10 layer @ 0.05) dengan SL terukur di atas ${price + 3.0:.2f}. "
            f"Target TP Maksimal mutlak diarahkan ke Tembok Baja Bawah yang Tidak Hilang di ${anchor_tp:.2f}!"
        )
    else:
        default_brief = (
            f"Lapor Commander Dadang! Berita [{news}] rilis dalam {max(1, mins)} menit. "
            f"Tembok ASK {lot:.0f}L di ${price:.2f} mendadak DICABUT paus (Atap likuiditas bolong / ruang hampa). "
            f"Rekomendasi Taktis: SEGERA SIAPKAN BUY LAYER (misal 10 layer @ 0.05) dengan SL terukur di bawah ${price - 3.0:.2f}. "
            f"Target TP Maksimal mutlak diarahkan ke Tembok Baja Atas yang Tidak Hilang di ${anchor_tp:.2f}!"
        )

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        prompt = (
            f"Kamu adalah Chief Tactical Strategist AI pribadi Commander Dadang Wahyuono.\n"
            f"Situasi: PRE-NEWS LIQUIDITY EVACUATION!\n"
            f"Berita: {news} (Rilis {mins} menit lagi).\n"
            f"Tembok {side} sebesar {lot:.0f} Lot di ${price:.2f} DICABUT PAUS.\n"
            f"Harga sekarang: ${spot_price:.2f}. Tembok target lawan (Anchor TP): ${anchor_tp:.2f}.\n"
            f"Berikan perintah taktis 3 kalimat tegas untuk Commander Dadang: Sinyal ({'SELL' if side=='BID' else 'BUY'}), alasan ruang hampa likuiditas, dan target TP maksimal."
        )
        payload = json.dumps({
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 150
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "User-Agent": "Mozilla/5.0"
            }
        )
        ssl_ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=4, context=ssl_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ai_text = data["choices"][0]["message"]["content"].strip()
            if "</think>" in ai_text:
                ai_text = ai_text.split("</think>")[-1].strip()
            elif "<think>" in ai_text:
                ai_text = default_brief
            if ai_text and len(ai_text) > 20:
                return ai_text
    except Exception as e:
        log_debug(f"Groq tactical brief exception: {e}")

    return default_brief


def send_telegram_vacuum_alert(event):
    global LAST_TELEGRAM_VACUUM_TS
    now = time.time()
    if now - LAST_TELEGRAM_VACUUM_TS < 180:
        return
    LAST_TELEGRAM_VACUUM_TS = now

    def _send_bg():
        try:
            bot_token = "8709247938:AAFeW2V98mymADdD5M9vQvzUI-4XvDgMLyE"
            chat_id = "740117533"
            side = event["side"]
            bias_emoji = "🔴" if side == "BID" else "🟢"
            bias_text = "SELL / SHORT (Lantai Bolong)" if side == "BID" else "BUY / LONG (Atap Bolong)"
            
            msg = (
                f"🚨 <b>[RADAR SPOOF / NEWS VACUUM ALERT]</b> 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>PERINGATAN PRE-NEWS: TEMBOK PAUS DICABUT!</b>\n\n"
                f"• Event Katalis: <b>{event.get('news_title')}</b>\n"
                f"• Waktu Menjelang: <code>{event.get('mins_until_news')} Menit Lagi!</code>\n"
                f"• Tembok Dicabut: <b>{event.get('size'):.0f} Lot {side}</b> @ <code>${event.get('price'):.2f}</code>\n"
                f"• Umur Tembok: <code>{event.get('age_min'):.0f} Menit</code>\n"
                f"• Harga Spot: <code>${event.get('spot_price'):.2f}</code>\n\n"
                f"{bias_emoji} <b>REKOMENDASI: {bias_text}</b>\n"
                f"🎯 <b>TARGET TP MAKSIMAL: <code>${event.get('anchor_tp'):.2f}</code></b>\n"
                f"<i>(Tembok Baja Lawan yang Tidak Hilang)</i>\n\n"
                f"🧠 <b>AI BRIEFING:</b>\n"
                f"<i>{event.get('ai_analysis')}</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <a href=\"https://trade.dadangchatai.com/heatmap.html\">Buka Web Terminal & Siapkan Layer</a>"
            )

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            ssl_ctx = ssl._create_unverified_context()
            urllib.request.urlopen(req, timeout=8, context=ssl_ctx)
        except Exception as e:
            log_debug(f"Failed to send vacuum Telegram alert: {e}")

    threading.Thread(target=_send_bg, daemon=True).start()


def scan_liquidity_vacuum(converted_wall_ladder, spot_price, now_sec):
    if not spot_price or spot_price <= 0 or not converted_wall_ladder:
        return
    current_keys = set()
    for side, items in (("BID", converted_wall_ladder.get("bids", [])), ("ASK", converted_wall_ladder.get("asks", []))):
        for it in items:
            if isinstance(it, (list, tuple)) and len(it) >= 2:
                p = round(float(it[0]), 2)
                sz = float(it[1])
                age = int(it[2]) if len(it) > 2 else 0
                k = f"{side}_{p}"
                current_keys.add(k)
                with TRACKED_WALLS_LOCK:
                    if k not in TRACKED_WALLS:
                        TRACKED_WALLS[k] = {
                            "price": p,
                            "side": side,
                            "size": sz,
                            "age_sec": age,
                            "max_size": sz,
                            "first_seen": now_sec - age,
                            "last_seen": now_sec
                        }
                    else:
                        w = TRACKED_WALLS[k]
                        w["size"] = sz
                        w["age_sec"] = max(w["age_sec"], age)
                        w["max_size"] = max(w["max_size"], sz)
                        w["last_seen"] = now_sec

    with TRACKED_WALLS_LOCK:
        to_delete = []
        for k, w in list(TRACKED_WALLS.items()):
            if k not in current_keys or w["size"] < 5.0:
                dist = abs(spot_price - w["price"])
                if w["max_size"] >= 20.0 and w["age_sec"] >= 600 and dist <= 6.0:
                    radar_state = get_news_radar_state(now_sec)
                    if not radar_state.get("is_pre_news_window"):
                        # Lewat atau di luar jendela news, tidak memicu alert pre-news
                        to_delete.append(k)
                        continue

                    next_ev = radar_state.get("next_event") or {}
                    anchor_target = find_anchor_tp(w["side"], spot_price, converted_wall_ladder)
                    
                    vac_event = {
                        "id": f"vac_{now_sec}_{w['side']}_{int(w['price']*10)}",
                        "timestamp": now_sec,
                        "time_str": time.strftime("%H:%M:%S"),
                        "side": w["side"],
                        "price": w["price"],
                        "size": w["max_size"],
                        "age_min": round(w["age_sec"] / 60, 1),
                        "spot_price": spot_price,
                        "anchor_tp": anchor_target,
                        "bias": "SELL" if w["side"] == "BID" else "BUY",
                        "bias_label": "BEARISH VACUUM (LANTAI DICABUT)" if w["side"] == "BID" else "BULLISH VACUUM (ATAP DICABUT)",
                        "news_title": next_ev.get("title", "High-Impact Catalyst"),
                        "mins_until_news": next_ev.get("mins_until", 0),
                        "in_news_window": True,
                        "ai_analysis": ""
                    }
                    vac_event["ai_analysis"] = generate_ai_vacuum_analysis(vac_event)
                    
                    with VACUUM_EVENTS_LOCK:
                        VACUUM_EVENTS.append(vac_event)
                        if len(VACUUM_EVENTS) > 15:
                            del VACUUM_EVENTS[: len(VACUUM_EVENTS) - 15]
                    
                    send_telegram_vacuum_alert(vac_event)
                    log_debug(f"🚨 LIQUIDITY VACUUM DETECTED: {w['side']} wall {w['max_size']}L @ {w['price']} pulled! Bias: {vac_event['bias']}")
                
                to_delete.append(k)
            elif now_sec - w["last_seen"] > 7200:
                to_delete.append(k)
                
        for k in to_delete:
            TRACKED_WALLS.pop(k, None)


def full_depth_recorder_loop():
    init_full_depth_db()
    prev_bids = {}
    prev_asks = {}
    last_prune = 0
    while True:
        try:
            now_sec = int(time.time())
            v2 = get_live_bookmap_snapshot_v2()

            # Central Candle Engine tick - unconditional on full_depth being
            # present (candle formation only needs price, not depth; gating
            # this on raw_bids/raw_asks like the depth-history block below
            # would silently freeze candle formation on every addon depth
            # hiccup, reintroducing the same kind of gap this engine exists
            # to eliminate).
            cme_raw = float((v2 or {}).get("current_price_gcz6_raw") or (v2 or {}).get("current_price") or 0.0)
            spot_price = round(cme_raw - BASIS_OFFSET, 2) if cme_raw else 0.0
            central_candle_tick(spot_price, now_sec)

            raw_fd = (v2 or {}).get("full_depth") or {}
            raw_bids = raw_fd.get("bids") or []
            raw_asks = raw_fd.get("asks") or []

            if raw_bids or raw_asks:
                # Same canonical MT5-equivalent price space the rest of
                # this server already converts wall_ladder/candles/etc to
                # (single to_mt5() conversion point, no second offset).
                bid_snapshot = {to_mt5(item[0]): item[1] for item in raw_bids if isinstance(item, (list, tuple)) and len(item) >= 2}
                ask_snapshot = {to_mt5(item[0]): item[1] for item in raw_asks if isinstance(item, (list, tuple)) and len(item) >= 2}

                events = (
                    _diff_full_depth_side(prev_bids, list(bid_snapshot.items()), "bid", now_sec)
                    + _diff_full_depth_side(prev_asks, list(ask_snapshot.items()), "ask", now_sec)
                )

                if events:
                    conn = sqlite3.connect(FULL_DEPTH_DB_FILE, timeout=5)
                    try:
                        conn.executemany(
                            "INSERT INTO events (time, price, side, size, change_type) VALUES (?, ?, ?, ?, ?)",
                            events,
                        )
                        conn.commit()
                    finally:
                        conn.close()

                prev_bids = bid_snapshot
                prev_asks = ask_snapshot

                # Feed the real, incrementally-growing heatmap spectrogram
                # history (see process_depth_slice() above) with the SAME
                # canonical full_depth this recorder already fetched -
                # already-converted bid/ask dicts, reshaped back to the
                # [price, size] list form process_depth_slice expects, plus
                # the equally-converted wall_ladder for age tracking.
                converted_full_depth = {
                    "bids": [[p, s] for p, s in bid_snapshot.items()],
                    "asks": [[p, s] for p, s in ask_snapshot.items()],
                }
                raw_wl = (v2 or {}).get("wall_ladder") or {}
                converted_wall_ladder = {
                    "bids": [[to_mt5(w[0])] + list(w[1:]) for w in (raw_wl.get("bids") or [])],
                    "asks": [[to_mt5(w[0])] + list(w[1:]) for w in (raw_wl.get("asks") or [])],
                }
                # cme_raw/spot_price already computed above (unconditionally,
                # for central_candle_tick) - reused here, not recomputed.
                process_depth_slice(converted_full_depth, converted_wall_ladder, spot_price, now_sec)
                scan_liquidity_vacuum(converted_wall_ladder, spot_price, now_sec)

            if now_sec - last_prune > 3600:
                last_prune = now_sec
                cutoff = now_sec - FULL_DEPTH_RETENTION_SECONDS
                conn = sqlite3.connect(FULL_DEPTH_DB_FILE, timeout=5)
                try:
                    conn.execute("DELETE FROM events WHERE time < ?", (cutoff,))
                    conn.commit()
                finally:
                    conn.close()
        except Exception as e:
            log_debug(f"full_depth_recorder_loop error: {e}")
        time.sleep(1.0)


def log_debug(msg):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def read_file_safe(filepath):
    if not os.path.exists(filepath):
        return None
    for _ in range(5):
        try:
            with open(filepath, "rb") as f:
                return f.read()
        except (PermissionError, OSError):
            time.sleep(0.01)
    return None


def get_live_bookmap_snapshot():
    raw_live = read_file_safe(LIVE_STATUS_FILE)
    live_data = {}
    if raw_live:
        try:
            live_data = json.loads(raw_live.decode("utf-8"))
        except Exception:
            pass

    # Read CSV signal
    cvd_val = live_data.get("cvd_30s", 139.0)
    pulse_val = live_data.get("buyer_aggression_pct", 48.5)
    cme_price = live_data.get("current_price") or live_data.get("price") or 4506.40

    signal_raw = read_file_safe(SIGNAL_CSV)
    if signal_raw:
        try:
            lines = signal_raw.decode("utf-8", errors="ignore").splitlines()
            if len(lines) >= 2:
                parts = lines[1].split(",")
                if len(parts) >= 4:
                    cme_price = float(parts[1])
                    cvd_val = float(parts[2])
                    pulse_val = float(parts[3])
        except Exception:
            pass

    cme_price = float(cme_price)
    spot_price = round(cme_price - BASIS_OFFSET, 2)
    return live_data, cme_price, spot_price, float(cvd_val), float(pulse_val)


class SultanRequestHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        try:
            self.request.settimeout(10.0)
        except Exception:
            pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FOLDER, **kwargs)

    def end_headers(self):
        # 2026-09-04: was forcing "Connection: close" + self.close_connection=True
        # on every single response (added earlier to fight TIME_WAIT buildup from
        # long-lived idle keep-alive sockets). Measured live tonight: this instead
        # made it worse - forcing a fresh TCP handshake+teardown for EVERY poll
        # from EVERY client (main dashboard ~1/sec, presence ping ~1/15s per open
        # tab, now multiplied across public trial/VIP viewers) produced 1010
        # sockets stuck in TIME_WAIT on port 8766 at once, with wfile.write()
        # aborting (WinError 10053) whenever the OS accept backlog/ephemeral
        # ports got saturated - surfacing as 502 Bad Gateway through the
        # Cloudflare tunnel. Every response here already sends a correct
        # Content-Length (see _send_payload and each direct wfile.write site),
        # so HTTP/1.1 keep-alive is safe to allow - letting one client reuse one
        # connection across many polls instead of opening a new one each time.
        # The existing self.request.settimeout(10.0) in setup() still bounds
        # how long an idle connection can be held open.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, User-Agent")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        try:
            # 👑 DYNAMIC ELEVENLABS AI VOICE ENGINE (ADAM SINGLE VOICE)
            if path == "/api/voice/tts":
                self._handle_voice_tts(query)
                return

            # 👑 INSTITUTIONAL BOOKMAP PRO DESK AI CALL
            if path in ("/api/ai/institutional_call", "/api/ai/pro_desk", "/api/ai/call"):
                self._handle_ai_institutional_call()
                return
            if path == "/candle_vault.json":
                if os.path.exists(VAULT_FILE):
                    with open(VAULT_FILE, "rb") as vf:
                        self._send_payload(vf.read(), "application/json")
                    return

            if path in ("/api/chart/history", "/api/chart/candles"):
                self._serve_chart_history()
                return

            if path == "/api/chart/heatmap_history":
                self._serve_heatmap_history()
                return

            if path == "/api/chart/live_depth_slice":
                self._serve_live_depth_slice()
                return

            if path == "/api/chart/live_candle":
                self._serve_live_candle()
                return

            if path in ("/live_status.json", "/status", "/api/status", "/sultan_status.json"):
                self._serve_sultan_status()
                return

            if path in ("/bookmap_live_signal.csv", "/signal.csv"):
                self._serve_file(SIGNAL_CSV, "text/csv")
                return

            if path == "/bookmap_full_depth.csv":
                self._serve_file(FULL_DEPTH_CSV, "text/csv")
                return

            if path == "/bookmap_share.json":
                self._serve_bookmap_share()
                return

            if path == "/api/telegram/status":
                self._handle_telegram_status()
                return
            if path == "/api/accounts":
                self._serve_accounts()
                return
            if path == "/api/news_vacuum/status":
                self._serve_news_vacuum_status()
                return

            if path == "/api/system_health":
                self._system_health()
                return

            if path == "/api/full_depth_history":
                self._serve_full_depth_history()
                return

            if path in ("/", "/dashboard", "/dashboard/", "/index.htm"):
                self.path = "/index.html"

            super().do_GET()
        except Exception as e:
            log_debug(f"GET Error on {self.path}: {e}")
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def do_POST(self):
        try:
            path = self.path.split("?")[0]
            # 👑 INSTITUTIONAL BOOKMAP PRO DESK AI CALL (POST SUPPORT)
            if path in ("/api/ai/institutional_call", "/api/ai/pro_desk", "/api/ai/call"):
                self._handle_ai_institutional_call()
                return
            if path == "/api/sultan_sync":
                self._handle_sultan_sync()
                return
            if path == "/api/calibrate_offset":
                self._handle_calibrate_offset()
                return
            if path == "/api/accounts/create":
                self._handle_create_account()
                return
            if path == "/api/accounts/delete":
                self._handle_delete_account()
                return
            if path == "/api/telegram/test":
                self._handle_telegram_test()
                return
            if path == "/api/auth/verify":
                self._handle_verify_auth()
                return
            if path == "/api/presence/ping":
                self._handle_presence_ping()
                return
            self.send_response(404)
            self.end_headers()
        except Exception as e:
            log_debug(f"POST Error on {self.path}: {e}")
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def _handle_calibrate_offset(self):
        global current_wall_ages
        """Dadang's self-service BASIS_OFFSET recalibration tool: he
        reads his real MT5 price off his own terminal and enters it here;
        we read the CURRENT live GC/CME raw price at that same instant and
        compute the offset that makes them match, then persist it so
        every price on this dashboard (candles, wall ladder, DOM, heatmap,
        everything - all through to_mt5()) follows his real MT5 from now
        on, until he recalibrates again."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body.decode("utf-8"))
            mt5_price = float(payload.get("mt5_price"))

            if not (1000 < mt5_price < 10000):
                self._send_payload(
                    json.dumps({"error": "Harga MT5 gak masuk akal (harus antara 1000-10000)"}).encode("utf-8"),
                    "application/json", 400,
                )
                return

            v2 = get_live_bookmap_snapshot_v2() or {}
            cme_raw = float(v2.get("current_price_gcz6_raw") or v2.get("current_price") or 0.0)
            if not cme_raw:
                self._send_payload(
                    json.dumps({"error": "Harga live GC gak tersedia sekarang, coba lagi sebentar"}).encode("utf-8"),
                    "application/json", 503,
                )
                return

            old_offset = BASIS_OFFSET
            new_offset = round(cme_raw - mt5_price, 2)
            delta = round(new_offset - old_offset, 2)
            _save_basis_offset(new_offset)

            # Retroactive rebase in-memory live bars
            if delta != 0:
                with central_m1_lock:
                    if central_m1_forming:
                        central_m1_forming["open"] = round(central_m1_forming["open"] - delta, 2)
                        central_m1_forming["high"] = round(central_m1_forming["high"] - delta, 2)
                        central_m1_forming["low"] = round(central_m1_forming["low"] - delta, 2)
                        central_m1_forming["close"] = round(central_m1_forming["close"] - delta, 2)
                    for b in central_m1_live_bars:
                        b[1] = round(b[1] - delta, 2)  # open
                        b[2] = round(b[2] - delta, 2)  # high
                        b[3] = round(b[3] - delta, 2)  # low
                        b[4] = round(b[4] - delta, 2)  # close
                    _persist_central_m1_live()

                # Retroactive rebase in-memory depth spectrogram history
                with depth_history_lock:
                    delta_idx = int(round(delta * 2))
                    for s in depth_history:
                        if "spot" in s and s["spot"]:
                            s["spot"] = round(s["spot"] - delta, 2)
                        if "levels" in s and delta_idx != 0:
                            new_levels = {}
                            for p_idx, lot in s["levels"].items():
                                try:
                                    new_levels[int(p_idx) - delta_idx] = lot
                                except Exception:
                                    pass
                            s["levels"] = new_levels
                        if "wall_ages" in s:
                            new_wa = {}
                            for pr_str, age in s["wall_ages"].items():
                                try:
                                    new_pr = f"{float(pr_str) - delta:.2f}"
                                    new_wa[new_pr] = age
                                except Exception:
                                    pass
                            s["wall_ages"] = new_wa
                    if current_wall_ages:
                        new_cwa = {}
                        for pr_str, age in current_wall_ages.items():
                            try:
                                new_pr = f"{float(pr_str) - delta:.2f}"
                                new_cwa[new_pr] = age
                            except Exception:
                                pass
                        current_wall_ages = new_cwa

            log_debug(f"BASIS_OFFSET recalibrated by Dadang: {old_offset} -> {new_offset} (delta={delta}, cme_raw={cme_raw}, mt5_input={mt5_price})")

            payload_out = json.dumps({
                "success": True,
                "delta": delta,
                "old_offset": old_offset,
                "new_offset": new_offset,
                "cme_raw_at_calibration": cme_raw,
                "mt5_price_input": mt5_price,
                "calibrated_at": BASIS_OFFSET_CALIBRATED_AT,
            }).encode("utf-8")
            self._send_payload(payload_out, "application/json")
        except Exception as e:
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def _send_payload(self, body, content_type="application/json", status=200):
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            log_debug(f"Payload send error on {self.path}: {e}")

    def _serve_file(self, filepath, content_type):
        body = read_file_safe(filepath)
        if body is not None:
            self._send_payload(body, content_type)
        else:
            self._send_payload(b"", content_type, 404)


    def _serve_heatmap_history(self):
        """
        Real, incrementally-recorded heatmap depth history - see
        process_depth_slice()/full_depth_recorder_loop() above. Each entry
        is a genuine snapshot from the moment it was recorded (levels
        keyed by price*2, matching Dadang's own ChainLocal
        CentralCandleEngine.process_depth() exactly), not a repeated
        current snapshot faked into a fabricated time series.
        """
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            limit = int(query.get("limit", ["300"])[0])

            with depth_history_lock:
                hist_slice = list(depth_history[-limit:])
                wall_ages_now = dict(current_wall_ages)

            payload = json.dumps({
                "count": len(hist_slice),
                "history": hist_slice,
                "current_wall_ages": wall_ages_now,
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self.send_error(500, f"Heatmap history error: {e}")

    def _serve_live_depth_slice(self):
        """Most recent real slice from the same depth_history full_depth_recorder_loop()
        maintains - see _serve_heatmap_history()'s docstring above."""
        try:
            with depth_history_lock:
                slice_data = dict(depth_history[-1]) if depth_history else None

            payload = json.dumps({"slice": slice_data}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self.send_error(500, f"Live depth slice error: {e}")

    def _serve_live_candle(self):
        """2026-09-03 (Central Candle Engine): the forming bar for whatever
        TF is requested, aggregated from the SAME _get_combined_m1_series()
        _serve_chart_history() reads - guaranteed identical to that
        endpoint's own last bar, since it's the same underlying computation.
        Previously read sultan_status.json's m5_bars (bookmap_addon_v2's OWN
        separate internal M5 aggregator) with a get_live_bookmap_snapshot()
        v1 fallback - a second, independent candle-forming path that could
        (and did) diverge from /api/chart/candles. Per Dadang's explicit
        spec, only ONE engine forms candles now."""
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            tf = query.get("tf", ["M5"])[0].upper()

            tf_secs = {"1S": 1, "S15": 15, "M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
            secs = tf_secs.get(tf, 300)

            # Only need the current/last bucket here - see
            # _get_combined_m1_series_tail()'s docstring for why this used
            # to be the full _get_combined_m1_series() (98k+ row copy +
            # full re-aggregation, 3x/second - the main CPU sink tonight).
            tail_n = max(int(secs // 60) + 5, 10)
            m1_rows = _get_combined_m1_series_tail(tail_n)
            candles = _aggregate_m1_to_tf(m1_rows, secs)

            if candles:
                last = candles[-1]
                now_ts = int(time.time())
                shift = 3600 if secs == 14400 else (75600 if secs == 86400 else 0)
                bucket_now = ((now_ts - shift) // secs) * secs + shift
                # Ensure the forming bar's close reflects instantaneous spot_price to avoid endpoint race
                v2 = get_live_bookmap_snapshot_v2()
                cme_raw = float((v2 or {}).get("current_price_gcz6_raw") or (v2 or {}).get("current_price") or 0.0)
                current_spot = round(cme_raw - BASIS_OFFSET, 2) if cme_raw else last["close"]
                is_forming = (last["time"] >= bucket_now)
                close_px = current_spot if is_forming and current_spot > 0 else last["close"]
                high_px = max(last["high"], close_px)
                low_px = min(last["low"], close_px)
                live_candle = {
                    "time": last["time"],
                    "open": last["open"],
                    "high": high_px,
                    "low": low_px,
                    "close": close_px,
                    "volume": last["volume"],
                    "delta": 0,
                    "is_closed": last["time"] < bucket_now,
                }
            else:
                live_candle = None

            payload = json.dumps({"tf": tf, "live_candle": live_candle}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self.send_error(500, f"Live candle error: {e}")

    def _serve_chart_history(self):
        """
        2026-09-03 (v3, Central Candle Engine): Dadang's explicit architecture
        spec - MT5 is permanently OFF, the CSV is a one-time historical seed
        only, and after the seed's anchor ONE server-side engine (fed by the
        same Bookmap/Rithmic price poll full_depth_recorder_loop() already
        runs) is the sole owner of candle formation. Two prior attempts at
        this handler both still produced a visible spike because they tried
        to BRIDGE the CSV seed onto candle_vault.json - which turned out to
        have NO WRITER anywhere on this machine (confirmed via grep), so
        there was never a second real timeline to bridge onto, only ever one
        synthesized "current price" point per request. This version reads
        _get_combined_m1_series() instead - the ONE continuously-growing M1
        timeline central_candle_tick() maintains - so every request from
        every browser at every moment aggregates the exact same underlying
        data: identical history, identical current forming bar, no
        per-request reconstruction, no fabricated interpolation.
        """
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            symbol = query.get("symbol", ["XAUUSD"])[0].upper()
            tf = query.get("tf", ["M5"])[0].upper()
            count = int(query.get("count", ["500"])[0])
            mode = query.get("mode", ["mt5"])[0].lower()

            tf_secs_map = {"1S": 1, "S15": 15, "M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
            secs = tf_secs_map.get(tf, 300)
            offset = BASIS_OFFSET if mode == "cme" else 0.0

            # 👑 1. FIRST PRIORITY: Check Canonical Multi-TF Candle Vault (Single Source of Truth)
            candles = []
            if os.path.exists(VAULT_FILE):
                try:
                    with open(VAULT_FILE, "r", encoding="utf-8") as vf:
                        vdata = json.load(vf)
                    if tf in vdata and len(vdata[tf]) > 0:
                        candles = [dict(b) for b in vdata[tf]]
                except Exception as e:
                    log_debug(f"Vault load error: {e}")

            # 2. Fallback to aggregated M1 series if not in vault
            if not candles:
                m1_rows = _get_combined_m1_series()
                candles = _aggregate_m1_to_tf(m1_rows, secs)
            if offset:
                for c in candles:
                    c["open"] = round(c["open"] + offset, 2)
                    c["high"] = round(c["high"] + offset, 2)
                    c["low"] = round(c["low"] + offset, 2)
                    c["close"] = round(c["close"] + offset, 2)

            candles = candles[-count:]

            payload = json.dumps({
                "symbol": symbol,
                "tf": tf,
                "mode": mode,
                "basis_offset": BASIS_OFFSET,
                "count": len(candles),
                "candles": candles,
                "source": "CENTRAL_CANDLE_ENGINE"
            }).encode("utf-8")

            self._send_payload(payload, "application/json")
        except Exception as e:
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def _serve_sultan_status(self):
        try:
            now_ts = int(time.time())
            v2 = get_live_bookmap_snapshot_v2()

            if v2 is None:
                # Honest "not connected" response - NOT a synthetic wall/CVD
                # ladder. Old behavior here silently invented plausible
                # numbers even when nothing was actually live; that's worse
                # than telling the truth.
                payload = json.dumps({
                    "symbol": "XAUUSD",
                    "online": False,
                    "timestamp": now_ts,
                    "updated_at": now_ts,
                    "error": "bookmap_addon_v2 (live_status_v2.json) unavailable"
                }).encode("utf-8")
                self._send_payload(payload, "application/json")
                return

            # 2026-09-01 malam: KOREKSI BESAR. v2["current_price"] TERNYATA
            # bukan raw - bookmap_addon_v2 sendiri diam-diam menjumlahkan
            # current_price_gcz6_raw + mt5_offset (mekanisme internalnya
            # sendiri, dibangun dari file bootstrap yang beku sejak
            # 2026-08-29, DAN nilainya terus bergeser - dikonfirmasi live:
            # mt5_offset berubah dari 40.98 ke 46.68 dalam <5 menit, bukan
            # konstanta beku). Server ini lalu menerapkan BASIS_OFFSET KEDUA
            # di atas angka yang sudah salah itu - double-conversion, hasil
            # akhirnya gak pernah ngikutin market real (dikonfirmasi:
            # current_price_gcz6_raw=4425.5 PERSIS cocok live Bookmap Dadang
            # 4426-4428, sementara current_price=4472.18 beku sepanjang
            # hari). Fix: pakai current_price_gcz6_raw (genuinely raw, gak
            # disentuh mekanisme internal addon yang rusak itu) sebagai
            # input BASIS_OFFSET kita, satu-satunya titik konversi.
            cme_raw_price = float(v2.get("current_price_gcz6_raw") or v2.get("current_price") or 0.0)
            spot_price = round(cme_raw_price - BASIS_OFFSET, 2) if cme_raw_price else 0.0
            cvd_val = float(v2.get("cvd_30s") or 0.0)
            pulse_val = float(v2.get("buyer_aggression_pct") or 0.0)

            # 2026-09-01 malam (lanjutan): ternyata "undo addon offset per
            # field" di atas cuma nutupin gejala, bukan akar masalah. Root-
            # caused lebih dalam: bookmap_addon_v2.py sendiri men-BAKE
            # mt5_offset-nya secara PERMANEN ke setiap trade/depth event pas
            # masuk (lihat bar_aggregator.on_trade(display_price,...) dkk di
            # source addon) - karena mt5_offset itu TERUS BERGESER (40.98->
            # 46.68->65.28->91.88 dalam semalam), field HISTORIS kayak
            # m5_bars gak bisa dikoreksi lagi belakangan pakai SATU nilai
            # mt5_offset "sekarang" - tiap bar butuh nilai offset PERSIS pas
            # bar itu kebentuk, yang gak pernah disimpan di mana pun.
            # Dikonfirmasi: m5_bars nunjukin harga rata ~2.5 jam yang beda
            # ~46 poin dari CSV asli MT5 Dadang di timestamp yang sama.
            #
            # Fix asli (bukan tambal lagi): addon-nya sendiri dibenerin
            # (Dadang: "harus lo benerin karena itu salah") - SEKARANG addon
            # gak nge-bake offset apa pun ke field manapun, semua genuinely
            # native/raw dari sumbernya. Makanya server ini juga disederhanain
            # balik ke SATU konversi murni: raw - BASIS_OFFSET, persis pola
            # yang sudah lama benar buat current_price (yang dari awal emang
            # cuma pakai current_price_gcz6_raw, gak pernah lewat mt5_offset
            # addon sama sekali - itu kenapa current_price gak pernah kena
            # bug ini, cuma field histori/array yang kena). to_mt5() is
            # now a module-level function (see top of file) - same one
            # the full_depth recorder thread uses.

            merged = {}
            merged["symbol"] = "XAUUSD"
            merged["price"] = spot_price
            merged["current_price"] = spot_price
            merged["current_price_xauusd"] = spot_price
            merged["cme_price"] = cme_raw_price or spot_price
            merged["timestamp"] = now_ts
            merged["updated_at"] = now_ts
            merged["online"] = True
            merged["server_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts))
            merged["mt5_bridge"] = True
            merged["basis_offset"] = BASIS_OFFSET
            merged["basis_offset_calibrated_at"] = BASIS_OFFSET_CALIBRATED_AT
            # Rithmic->MT5-equivalent price mapping status (Dadang's spec,
            # 2026-09-04): reference_xauusd/reference_updated_at come from
            # auto_spot_anchor_loop()'s last SUCCESSFUL Twelve Data fetch,
            # independent of whether that fetch triggered a rebase. STALE
            # means the reference feed hasn't answered in a while - the
            # basis itself is still the last valid one (never fabricated,
            # wall never touched on a failed fetch - see rule 11).
            _now_ref = time.time()
            if _last_reference_fetch_ts is not None and (_now_ref - _last_reference_fetch_ts) < REFERENCE_STALE_THRESHOLD_SEC:
                merged["basis_status"] = "LIVE"
            else:
                merged["basis_status"] = "STALE"
            merged["reference_xauusd"] = _last_reference_price
            merged["reference_updated_at"] = _last_reference_fetch_ts
            merged["buyer_aggression_pct"] = pulse_val
            merged["cvd_30s"] = cvd_val
            # Real CME/Rithmic candles (M5+, built live from Bookmap ticks -
            # no M1, no deep history yet) - Dadang: "gak pakai MT5", the
            # dashboard's candle chart now seeds from this instead of the
            # MT5-based /api/chart/history. OHLC converted to MT5-equivalent.
            raw_m5_bars = v2.get("m5_bars") or []
            merged["m5_bars"] = [
                {**b, "open": to_mt5(b.get("open")), "high": to_mt5(b.get("high")),
                 "low": to_mt5(b.get("low")), "close": to_mt5(b.get("close"))}
                for b in raw_m5_bars
            ]

            # Real wall ladder from bookmap_addon_v2's own Rithmic L2 depth
            # tracking (27+ genuine levels observed live, not a fixed 5-slot
            # template) - was a hardcoded price+offset formula here before.
            # Prices converted to MT5-equivalent (lot/age untouched).
            raw_wl = v2.get("wall_ladder") or {"asks": [], "bids": []}
            asks = [[to_mt5(w[0])] + list(w[1:]) for w in (raw_wl.get("asks") or [])]
            bids = [[to_mt5(w[0])] + list(w[1:]) for w in (raw_wl.get("bids") or [])]
            wl = {**raw_wl, "asks": asks, "bids": bids}
            merged["wall_ladder"] = wl
            raw_ob = v2.get("order_book") or raw_wl
            merged["order_book"] = {
                "asks": [[to_mt5(w[0])] + list(w[1:]) for w in (raw_ob.get("asks") or [])],
                "bids": [[to_mt5(w[0])] + list(w[1:]) for w in (raw_ob.get("bids") or [])],
            }

            # 2026-09-01: full (unfiltered) resting order book, ONLY for the
            # web heatmap engine - separate from wall_ladder above, which
            # stays exactly as-is (still the only thing any trading signal
            # reads). Same to_mt5() price conversion so it lines up with
            # the candles/wall_ladder/POC lines already on the same chart.
            raw_fd = v2.get("full_depth") or {"bids": [], "asks": []}
            merged["full_depth"] = {
                "bids": [[to_mt5(w[0])] + list(w[1:]) for w in (raw_fd.get("bids") or [])],
                "asks": [[to_mt5(w[0])] + list(w[1:]) for w in (raw_fd.get("asks") or [])],
            }

            raw_vp = v2.get("volume_profile") or {}
            vp = dict(raw_vp)
            for k in ("poc_price", "vah_price", "val_price", "poc", "vah", "val"):
                if k in vp:
                    vp[k] = to_mt5(vp[k])
            merged["volume_profile"] = vp

            raw_sd = v2.get("sd_zones") or []
            merged["sd_zones"] = [
                {**z, "lo": to_mt5(z.get("lo")), "hi": to_mt5(z.get("hi"))} for z in raw_sd
            ]
            merged["footprint"] = v2.get("footprint")

            absorption = v2.get("absorption") or {"status": "NONE", "reason": "no data"}
            merged["absorption"] = absorption

            bid_total = sum(float(w[1]) for w in bids) if bids else 0.0
            ask_total = sum(float(w[1]) for w in asks) if asks else 0.0
            nearest_side = "BID"
            if bids and asks:
                nearest_side = "BID" if abs(spot_price - bids[0][0]) <= abs(spot_price - asks[0][0]) else "ASK"
            elif asks and not bids:
                nearest_side = "ASK"
            imbalance = round((bid_total - ask_total) / (bid_total + ask_total), 2) if (bid_total + ask_total) else 0.0
            merged["liquidity"] = {
                "bid_wall_price": bids[0][0] if bids else 0.0,
                "bid_wall_ratio": round(100.0 * bid_total / (bid_total + ask_total), 1) if (bid_total + ask_total) else 0.0,
                "ask_wall_price": asks[0][0] if asks else 0.0,
                "ask_wall_ratio": round(100.0 * ask_total / (bid_total + ask_total), 1) if (bid_total + ask_total) else 0.0,
                "nearest_wall_side": nearest_side,
                "nearest_wall_distance": round(min(
                    abs(spot_price - bids[0][0]) if bids else 1e9,
                    abs(spot_price - asks[0][0]) if asks else 1e9
                ), 2) if (bids or asks) else 0.0,
                "wall_imbalance": imbalance,
                "bid_wall_count": len(bids),
                "ask_wall_count": len(asks),
                "bid_wall_total_lot": bid_total,
                "ask_wall_total_lot": ask_total
            }

            merged["flow"] = {
                "cvd": cvd_val,
                "delta_1m": float(v2.get("delta_1m") or 0.0),
                "delta_history": v2.get("delta_history") or [],
                "vol_ratio_buy_pct": pulse_val,
                "pulse_pct": pulse_val,
                "absorption": absorption.get("status", "NONE"),
                "flow_dominant": "BUY" if cvd_val >= 0 else "SELL"
            }

            poc_p = vp.get("poc_price") or vp.get("poc") or 0.0
            vah_p = vp.get("vah_price") or vp.get("vah") or 0.0
            val_p = vp.get("val_price") or vp.get("val") or 0.0
            merged["location"] = {
                "poc": poc_p,
                "val": val_p,
                "vah": vah_p,
                "current_price": spot_price,
                "position": "INSIDE_VA" if (val_p and vah_p and val_p <= spot_price <= vah_p) else "-",
                "distance_to_poc": round(spot_price - poc_p, 2) if poc_p else 0.0,
                "distance_to_poc_pct": round(100.0 * (spot_price - poc_p) / poc_p, 2) if poc_p else 0.0,
                "va_bias": "-",
                "range_24h": 0.0,
                "atr14": 0.0
            }

            raw_sweep = v2.get("wall_sweep") or {"active": False, "side": "", "size": 0.0, "price": 0.0, "status": "NONE"}
            merged["wall_sweep"] = {**raw_sweep, "price": to_mt5(raw_sweep.get("price"))} if raw_sweep.get("price") else raw_sweep

            now_sec = now_ts
            merged["signals"] = {
                "countdown": {
                    "m1": 60 - (now_sec % 60),
                    "m5": 300 - (now_sec % 300),
                    "m15": 900 - (now_sec % 900),
                    "m30": 1800 - (now_sec % 1800),
                    "h1": 3600 - (now_sec % 3600),
                    "h4": 14400 - (now_sec % 14400),
                    "d1": 86400 - (now_sec % 86400)
                }
            }

            # Real CMP/VR/CF matrix from bookmap_addon_v2's own tick-built
            # bars (same cold-start doctrine as the rest of this project -
            # WAIT/WARMUP is the honest state until enough bars exist, not a
            # hardcoded H4 SELL/M30 CF#1 that never changed regardless of
            # the market, which is what was here before).
            merged["tf_matrix"] = v2.get("tf_matrix") or {}

            h4 = merged["tf_matrix"].get("H4", {})
            m30 = merged["tf_matrix"].get("M30", {})
            m5 = merged["tf_matrix"].get("M5", {})
            h4_dir = h4.get("cmp", "WAIT")
            is_trending = h4_dir in ("BUY", "SELL") and h4_dir == m30.get("cmp") == m5.get("cmp")
            merged["regime"] = {
                "trending": is_trending,
                "direction": h4_dir if is_trending else "",
                "label": f"TRENDING {h4_dir}" if is_trending else "SIDEWAYS"
            }

            merged["reason_lines"] = v2.get("reason_lines") or []
            merged["news_radar"] = get_news_radar_state(now_sec)

            payload = json.dumps(merged).encode("utf-8")
            self._send_payload(payload, "application/json")
        except Exception as e:
            log_debug(f"Sultan status error: {e}")
            fallback = {
                "symbol": "XAUUSD",
                "online": False,
                "timestamp": int(time.time()),
                "error": str(e)
            }
            self._send_payload(json.dumps(fallback).encode("utf-8"), "application/json")

    def _serve_bookmap_share(self):
        body = read_file_safe(LIVE_STATUS_FILE)
        if body and len(body) > 10:
            self._send_payload(body, "application/json")
            return
        self._send_payload(b'{"status": "STANDALONE_OK"}', "application/json")

    def _handle_sultan_sync(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
            with open(SULTAN_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
            self._send_payload(b'{"ok": true}', "application/json")
        except Exception as e:
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def _check_admin_auth(self):
        auth = self.headers.get("Authorization", "")
        key = auth.replace("Bearer ", "").strip()
        return key in ("278868", "DADANG")

    def _serve_accounts(self):
        if not self._check_admin_auth():
            self._send_payload(b'{"error": "Unauthorized"}', "application/json", 401)
            return
        accs = _load_accounts()
        now = int(time.time())

        with ACTIVE_SESSIONS_LOCK:
            # Purge sessions inactive for more than 10 minutes (600s)
            stale = [k for k, v in ACTIVE_SESSIONS.items() if now - v["last_seen"] > 600]
            for k in stale:
                del ACTIVE_SESSIONS[k]

            online_testers = []
            for u, s in ACTIVE_SESSIONS.items():
                sec_ago = max(0, now - s["last_seen"])
                is_online = sec_ago <= 45  # active within last 45s
                online_testers.append({
                    "username": s["username"],
                    "ip": s["ip"],
                    "device": s["device"],
                    "last_seen": s["last_seen"],
                    "sec_ago": sec_ago,
                    "status": "ONLINE" if is_online else "IDLE",
                    "is_online": is_online
                })

        online_testers.sort(key=lambda x: x["last_seen"], reverse=True)
        active_usernames = {t["username"] for t in online_testers if t["is_online"]}

        res = []
        for a in accs:
            a_copy = dict(a)
            a_copy["is_expired"] = (a.get("expires_at") is not None and now > a["expires_at"])
            a_copy["is_online"] = a.get("username", "").lower() in active_usernames
            res.append(a_copy)

        stats = {
            "total_accounts": len(res),
            "active_licenses": sum(1 for a in res if not a["is_expired"]),
            "online_now": sum(1 for t in online_testers if t["is_online"]),
            "total_testers_seen": len(online_testers)
        }

        self._send_payload(json.dumps({
            "ok": True,
            "accounts": res,
            "stats": stats,
            "online_testers": online_testers
        }).encode("utf-8"), "application/json")

    def _serve_news_vacuum_status(self):
        state = get_news_radar_state()
        self._send_payload(json.dumps({"ok": True, **state}).encode("utf-8"), "application/json")

    def _handle_create_account(self):
        if not self._check_admin_auth():
            self._send_payload(b'{"error": "Unauthorized"}', "application/json", 401)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            username = str(payload.get("username", "")).strip().lower()
            password = str(payload.get("password", "")).strip()
            role = str(payload.get("role", "TRIAL_3"))
            days = payload.get("duration_days")
            notes = str(payload.get("notes", ""))

            if not username or not password:
                self._send_payload(b'{"error": "Username & Password required"}', "application/json", 400)
                return

            now = int(time.time())
            expires_at = None
            if days:
                expires_at = now + (int(days) * 86400)

            accs = _load_accounts()
            # update existing or append
            found = False
            for a in accs:
                if a.get("username", "").lower() == username:
                    a["password"] = password
                    a["role"] = role
                    a["expires_at"] = expires_at
                    a["notes"] = notes
                    found = True
                    break
            if not found:
                accs.append({
                    "username": username,
                    "password": password,
                    "role": role,
                    "created_at": now,
                    "expires_at": expires_at,
                    "notes": notes
                })

            _save_accounts(accs)
            self._send_payload(json.dumps({"ok": True, "username": username}).encode("utf-8"), "application/json")
        except Exception as e:
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def _handle_delete_account(self):
        if not self._check_admin_auth():
            self._send_payload(b'{"error": "Unauthorized"}', "application/json", 401)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            username = str(payload.get("username", "")).strip().lower()

            if username in ("commander", "comander"):
                self._send_payload(b'{"error": "Cannot delete master commander account"}', "application/json", 400)
                return

            accs = _load_accounts()
            accs = [a for a in accs if a.get("username", "").lower() != username]
            _save_accounts(accs)
            self._send_payload(b'{"ok": true}', "application/json")
        except Exception as e:
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def _handle_telegram_test(self):
        if not self._check_admin_auth():
            self._send_payload(b'{"error": "Unauthorized"}', "application/json", 401)
            return
        try:
            cfg_file = os.path.join(BASE_DIR, "telegram_config.json")
            bot_token = "8709247938:AAFeW2V98mymADdD5M9vQvzUI-4XvDgMLyE"
            chat_id = "740117533"
            if os.path.exists(cfg_file):
                try:
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        bot_token = cfg.get("bot_token", bot_token)
                        chat_id = str(cfg.get("chat_id", chat_id))
                except Exception:
                    pass

            v2 = get_live_bookmap_snapshot_v2() or {}
            cme_raw = float(v2.get("current_price_gcz6_raw") or v2.get("current_price") or 0.0)
            spot = round(cme_raw - BASIS_OFFSET, 2) if cme_raw > 0 else 4472.50

            msg = (
                "🚨 <b>[TEST PING] TELEGRAM SENTINEL BERFUNGSI NORMAL!</b> 🚨\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "Pesan tes ini dikirim langsung dari <b>Web Admin Deck</b> oleh Commander Dadang!\n\n"
                f"• Spot Gold Live: <code>${spot:.2f}</code>\n"
                f"• Tower Server: 🟢 <b>ONLINE (100.71.97.6)</b>\n"
                f"• System Time: <code>{time.strftime('%Y-%m-%d %H:%M:%S')} WIB</code>\n\n"
                "🫡 <i>Sentinel siap memantau Tembok Paus, Spoofing, dan Absorption 24/7!</i>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🌐 <a href=\"https://trade.dadangchatai.com/heatmap.html\">Buka Heatmap Terminal</a>"
            )

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            ssl_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=8, context=ssl_ctx) as r:
                res = json.loads(r.read().decode("utf-8"))
                self._send_payload(json.dumps({"ok": res.get("ok", False)}).encode("utf-8"), "application/json")
        except Exception as e:
            self._send_payload(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"), "application/json", 500)

    def _handle_telegram_status(self):
        cfg_file = os.path.join(BASE_DIR, "telegram_config.json")
        cfg = {}
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                pass
        self._send_payload(json.dumps({"ok": True, "config": cfg}).encode("utf-8"), "application/json")


    def _handle_voice_tts(self, query):
        tag = query.get("tag", [""])[0].strip()
        text = query.get("text", [""])[0].strip()

        # 1. Look up by tag in cache
        if tag:
            fpath = os.path.join(VOICE_CACHE_DIR, f"{tag}.mp3")
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    data = f.read()
                self._send_payload(data, "audio/mpeg")
                return

        # 2. Look up by text in MD5 cache
        if text:
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            fpath = os.path.join(VOICE_CACHE_DIR, f"{text_hash}.mp3")
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    data = f.read()
                self._send_payload(data, "audio/mpeg")
                return

            # Call ElevenLabs API dynamically with ADAM
            try:
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
                payload = {
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "xi-api-key": ELEVENLABS_API_KEY,
                        "Content-Type": "application/json",
                        "Accept": "audio/mpeg"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    audio_data = resp.read()
                    with open(fpath, "wb") as f:
                        f.write(audio_data)
                    self._send_payload(audio_data, "audio/mpeg")
                    return
            except Exception as e:
                log_debug(f"ElevenLabs TTS generation error: {e}")

        # Fallback to welcome_boot if available
        fallback = os.path.join(VOICE_CACHE_DIR, "welcome_boot.mp3")
        if os.path.exists(fallback):
            with open(fallback, "rb") as f:
                data = f.read()
            self._send_payload(data, "audio/mpeg")
            return

        self._send_payload(b"", "audio/mpeg", 404)

    def _handle_ai_institutional_call(self):
        """
        👑 PURE INSTITUTIONAL BOOKMAP HEDGE FUND PRO DESK
        Queries BaliTech AI using pure global order flow microstructure principles.
        Returns structured trade call (Bias, Action, Entry, SL, TP, RR, Rationale)
        and automatically connects to Adam ElevenLabs voice for auditory briefing.
        """
        status = {}
        try:
            if os.path.exists(SULTAN_STATUS_FILE):
                with open(SULTAN_STATUS_FILE, "r", encoding="utf-8") as f:
                    status = json.load(f)
            else:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{PORT}/sultan_status.json",
                    headers={"User-Agent": "SuperProGateway/1.0"}
                )
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    if resp.status == 200:
                        status = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log_debug(f"AI call telemetry read err: {e}")

        spot = status.get("current_price", 4429.8)
        cme = status.get("cme_price", 4477.2)
        cvd = status.get("cvd_30s", 0)
        buyer_agg = status.get("buyer_aggression_pct", 50)
        regime = status.get("regime", {}).get("label", "SIDEWAYS")
        loc = status.get("location", {})
        poc = loc.get("poc", 4382.1)
        val = loc.get("val", 4365.0)
        vah = loc.get("vah", 4448.6)
        pos = loc.get("position", "INSIDE_VA")

        liq = status.get("liquidity", {})
        bid_wall = liq.get("bid_wall_price", 4396.6)
        ask_wall = liq.get("ask_wall_price", 4456.2)
        bid_ratio = liq.get("bid_wall_ratio", 50)
        ask_ratio = liq.get("ask_wall_ratio", 50)

        telemetry_summary = f"""
LIVE BOOKMAP ORDER FLOW TELEMETRY:
- Instrument: XAU/USD Spot (Derived from CME GC Futures)
- Current Spot Price: {spot} USD | CME GC Futures: {cme} USD
- Market Auction Regime: {regime}
- Volume Profile Auction Location: {pos} (POC: {poc}, VAL: {val}, VAH: {vah})
- Cumulative Volume Delta (CVD 30s): {cvd} Lot
- Buyer Aggression: {buyer_agg}% | Seller Aggression: {100 - buyer_agg}%
- Nearest Major Resting Bids (Support Wall): {bid_wall} ({bid_ratio}% depth concentration)
- Nearest Major Resting Asks (Resistance Wall): {ask_wall} ({ask_ratio}% depth concentration)
- Absorption Status: {status.get('absorption', {}).get('status', 'NONE')}
- Wall Sweep Status: {status.get('wall_sweep', {}).get('latest', {}).get('status', 'NONE')}
"""

        models_to_try = [
            "bt/deepseek-flash",
            "bt/anthropic-claude-sonnet-5",
            "bt/agnes-2.5-flash"
        ]
        parsed_call = None

        for model_id in models_to_try:
            try:
                payload = {
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": INSTITUTIONAL_BOOKMAP_PROMPT},
                        {"role": "user", "content": telemetry_summary}
                    ],
                    "max_tokens": 350,
                    "temperature": 0.2
                }
                req_ai = urllib.request.Request(
                    BALITECH_COMPLETIONS_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {BALITECH_API_KEY_PAID}",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req_ai, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw = data["choices"][0]["message"]["content"].strip()
                    if "```json" in raw:
                        raw = raw.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw:
                        raw = raw.split("```")[1].split("```")[0].strip()
                    parsed_call = json.loads(raw)
                    parsed_call["model_used"] = model_id
                    break
            except Exception as e:
                log_debug(f"AI call attempt failed with {model_id}: {e}")
                continue

        if not parsed_call:
            parsed_call = {
                "bias": "RANGE_BOUND",
                "action": "STAND ASIDE",
                "entry_price": str(spot),
                "stop_loss": str(round(spot - 3.0, 2)),
                "take_profit_1": str(round(spot + 6.0, 2)),
                "take_profit_2": str(round(spot + 12.0, 2)),
                "risk_reward": "1:2.0",
                "institutional_rationale": [
                    "Market is consolidating in value area without aggressive institutional sponsorship.",
                    "Wait for sweep of boundary or absorption at resting wall before executing."
                ],
                "voice_briefing_id": "Market emas sedang konsolidasi dalam area balance. Stand aside, tunggu liquidity sweep sebelum eksekusi.",
                "model_used": "fallback"
            }

        voice_text = parsed_call.get("voice_briefing_id", "")
        audio_url = ""
        if voice_text:
            audio_url = f"/api/voice/tts?text={urllib.parse.quote(voice_text)}"

        parsed_call["audio_url"] = audio_url
        parsed_call["timestamp"] = int(time.time())

        self._send_payload(json.dumps({"status": "success", "data": parsed_call}).encode("utf-8"), "application/json")

    def _handle_presence_ping(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            username = str(payload.get("username", "")).strip().lower()
            if not username:
                self._send_payload(b'{"ok": false, "error": "Username required"}', "application/json", 400)
                return

            client_ip = self.headers.get("CF-Connecting-IP") or (self.headers.get("X-Forwarded-For", "").split(",")[0].strip()) or self.client_address[0]
            ua = self.headers.get("User-Agent", "")
            now = int(time.time())

            with ACTIVE_SESSIONS_LOCK:
                ACTIVE_SESSIONS[username] = {
                    "username": username,
                    "ip": client_ip,
                    "device": parse_device(ua),
                    "last_seen": now,
                    "user_agent": ua[:100]
                }

            self._send_payload(json.dumps({"ok": True, "server_time": now}).encode("utf-8"), "application/json")
        except Exception as e:
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def _handle_verify_auth(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            username = str(payload.get("username", "")).strip().lower()
            password = str(payload.get("password", "")).strip()

            client_ip = self.headers.get("CF-Connecting-IP") or (self.headers.get("X-Forwarded-For", "").split(",")[0].strip()) or self.client_address[0]
            ua = self.headers.get("User-Agent", "")
            now = int(time.time())

            # Master Commander Universal Bypass (Password 278868 atau DADANG membuka semua akun)
            if password in ("278868", "DADANG"):
                save_u = username or "commander"
                with ACTIVE_SESSIONS_LOCK:
                    ACTIVE_SESSIONS[save_u] = {
                        "username": save_u,
                        "ip": client_ip,
                        "device": parse_device(ua),
                        "last_seen": now,
                        "user_agent": ua[:100]
                    }
                self._send_payload(json.dumps({
                    "ok": True,
                    "valid": True,
                    "role": "VIP_UNLIMITED",
                    "expired": False
                }).encode("utf-8"), "application/json")
                return

            accs = _load_accounts()
            for a in accs:
                db_u = str(a.get("username", "")).strip().lower()
                db_p = str(a.get("password", "")).strip()
                # Cocokkan case-insensitive untuk mencegah kesalahan auto-kapital keyboard HP
                if db_u == username and (db_p == password or db_p.lower() == password.lower()):
                    expires_at = a.get("expires_at")
                    # Murni berbasis durasi waktu (expires_at) - tanpa batasan hari market libur
                    time_expired = (expires_at is not None and now > expires_at)

                    if time_expired:
                        self._send_payload(json.dumps({
                            "ok": True,
                            "valid": True,
                            "expired": True,
                            "message": "Sesi Habis: Masa aktif akun (3 Hari) telah berakhir! Silakan hubungi Commander Dadang untuk lisensi VIP."
                        }).encode("utf-8"), "application/json")
                        return

                    with ACTIVE_SESSIONS_LOCK:
                        ACTIVE_SESSIONS[db_u] = {
                            "username": db_u,
                            "ip": client_ip,
                            "device": parse_device(ua),
                            "last_seen": now,
                            "user_agent": ua[:100]
                        }

                    self._send_payload(json.dumps({
                        "ok": True,
                        "valid": True,
                        "role": a.get("role", "TRIAL_3"),
                        "expired": False,
                        "expires_at": expires_at
                    }).encode("utf-8"), "application/json")
                    return

            self._send_payload(json.dumps({
                "ok": True,
                "valid": False,
                "error": "Username atau Password salah"
            }).encode("utf-8"), "application/json")
        except Exception as e:
            self._send_payload(json.dumps({"error": str(e)}).encode("utf-8"), "application/json", 500)

    def _system_health(self):
        health = {
            "status": "HEALTHY",
            "timestamp": int(time.time()),
            "server_port": PORT,
            "bookmap_live": os.path.exists(LIVE_STATUS_FILE),
            "candle_vault": os.path.exists(VAULT_FILE)
        }
        self._send_payload(json.dumps(health).encode("utf-8"), "application/json")

    def _serve_full_depth_history(self):
        # Chain Liquidity Heatmap's server-side history store - see
        # full_depth_recorder_loop()/FULL_DEPTH_DB_FILE above. ?since=
        # unix seconds (default: last 24h), ?limit= max rows (default
        # 20000, hard-capped at 50000 so one request can't return an
        # unbounded payload).
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            since = int(float(query.get("since", [str(int(time.time()) - 86400)])[0]))
            limit = min(50000, max(1, int(query.get("limit", ["20000"])[0])))

            conn = sqlite3.connect(FULL_DEPTH_DB_FILE, timeout=5)
            try:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT time, price, side, size, change_type FROM events "
                    "WHERE time >= ? ORDER BY time ASC LIMIT ?",
                    (since, limit),
                ).fetchall()
            finally:
                conn.close()

            events = [
                {
                    "time": r["time"],
                    "price": r["price"],
                    "side": r["side"],
                    "size": r["size"],
                    "changeType": r["change_type"],
                }
                for r in rows
            ]
            payload = json.dumps({"since": since, "count": len(events), "events": events}).encode("utf-8")
            self._send_payload(payload, "application/json")
        except Exception as e:
            log_debug(f"full_depth_history error: {e}")
            self._send_payload(json.dumps({"error": str(e), "events": []}).encode("utf-8"), "application/json", 500)

    def log_message(self, fmt, *args):
        pass


class ThreadedHTTPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128  # default is 5 - too small for bursts of simultaneous public viewers


_offset_ema = None  # smoothed "ideal offset" (cme_raw - real spot), None until first sample

# 2026-09-04 (3rd pass): Dadang's own price-mapping spec (rule 11) requires a
# visible LIVE/STALE signal - if Twelve Data goes dark, the dashboard must say
# so instead of quietly running on a stale basis. These track the last
# SUCCESSFUL reference fetch independent of whether it triggered a rebase
# (small in-tolerance movements were previously invisible - only a >=$2.00
# drift left any trace). Both stay untouched on a failed fetch (the existing
# except: pass below), which is exactly "keep last valid basis, don't
# fabricate" - see _serve_sultan_status() for where these become basis_status.
_last_reference_price = None
_last_reference_fetch_ts = None
REFERENCE_STALE_THRESHOLD_SEC = 900  # 15 min - a few missed 5-min cycles before crying wolf

def auto_spot_anchor_loop():
    """
    Auto-Anchor Spot Gold Engine for Commander Dadang (Unified Twelve Data XAU/USD).
    Polled every 5 minutes (300s) = 288 req/day (well inside free tier 800/day).

    2026-09-04 (2nd pass, same night): the first version compared a SINGLE
    raw Twelve Data sample against BASIS_OFFSET each cycle and rebased
    straight to it. Caught live in server_debug.log: the raw "ideal
    offset" itself swings ~$6-16 within a single 5-minute window (measured
    directly: 4 samples 15s apart already moved $6) - not feed staleness,
    genuine short-term CME-futures-vs-spot noise (this was shortly after
    NFP, a known high-volatility window). At a $2.00 threshold that fired
    on nearly every cycle, oscillating the offset (and retroactively
    rebasing candle history) each time - the exact "yo-yo jitter" this
    whole mechanism exists to avoid, just slower.

    Fix: smooth the raw samples through an EMA (_offset_ema, alpha=0.15 -
    ~6-7 samples / ~30-35min time constant) BEFORE ever comparing against
    BASIS_OFFSET or triggering a rebase. A single noisy/volatile sample
    only nudges the EMA a little; the threshold check and the actual
    rebase amount both use the smoothed value, not the raw one. This
    still tracks genuine sustained drift over tens of minutes, it just no
    longer reacts to single-sample noise.
    """
    global _offset_ema, _last_reference_price, _last_reference_fetch_ts, current_wall_ages
    log_debug("Starting auto_spot_anchor_loop background thread (Twelve Data XAU/USD, EMA-smoothed)...")
    time.sleep(10)  # Initial grace period for server startup
    EMA_ALPHA = 0.15
    while True:
        try:
            url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_API_KEY}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode("utf-8"))
                spot_price = float(data.get("price") or 0.0)

            if spot_price > 1000:
                _last_reference_price = spot_price
                _last_reference_fetch_ts = int(time.time())

                v2 = get_live_bookmap_snapshot_v2() or {}
                cme_raw = float(v2.get("current_price_gcz6_raw") or v2.get("current_price") or 0.0)
                if cme_raw > 1000:
                    raw_ideal_offset = round(cme_raw - spot_price, 2)

                    if _offset_ema is None:
                        _offset_ema = raw_ideal_offset  # seed on first sample, no correction yet
                    else:
                        _offset_ema = round(_offset_ema + EMA_ALPHA * (raw_ideal_offset - _offset_ema), 3)

                    delta = round(_offset_ema - BASIS_OFFSET, 2)

                    # Safety rail: only rebase once the SMOOTHED offset has
                    # drifted >= $2.00 from current - not a single raw sample.
                    if abs(delta) >= 2.00:
                        old_offset = BASIS_OFFSET
                        new_offset = round(_offset_ema, 2)
                        _save_basis_offset(new_offset)

                        with central_m1_lock:
                            if central_m1_forming:
                                central_m1_forming["open"] = round(central_m1_forming["open"] - delta, 2)
                                central_m1_forming["high"] = round(central_m1_forming["high"] - delta, 2)
                                central_m1_forming["low"] = round(central_m1_forming["low"] - delta, 2)
                                central_m1_forming["close"] = round(central_m1_forming["close"] - delta, 2)
                            for b in central_m1_live_bars:
                                b[1] = round(b[1] - delta, 2)
                                b[2] = round(b[2] - delta, 2)
                                b[3] = round(b[3] - delta, 2)
                                b[4] = round(b[4] - delta, 2)
                            _persist_central_m1_live()

                        with depth_history_lock:
                            delta_idx = int(round(delta * 2))
                            for s in depth_history:
                                if "spot" in s and s["spot"]:
                                    s["spot"] = round(s["spot"] - delta, 2)
                                if "levels" in s and delta_idx != 0:
                                    new_levels = {}
                                    for p_idx, lot in s["levels"].items():
                                        try:
                                            new_levels[int(p_idx) - delta_idx] = lot
                                        except Exception:
                                            pass
                                    s["levels"] = new_levels
                                if "wall_ages" in s:
                                    new_wa = {}
                                    for pr_str, age in s["wall_ages"].items():
                                        try:
                                            new_pr = f"{float(pr_str) - delta:.2f}"
                                            new_wa[new_pr] = age
                                        except Exception:
                                            pass
                                    s["wall_ages"] = new_wa

                        # Same shift for current_wall_ages as _handle_calibrate_offset()
                        # already does - this loop was missing it (audit found the
                        # asymmetry), so a wall's persistence timer could briefly look
                        # keyed to the pre-rebase price after an auto-anchor correction.
                        if current_wall_ages:
                            new_cwa = {}
                            for pr_str, age in current_wall_ages.items():
                                try:
                                    new_pr = f"{float(pr_str) - delta:.2f}"
                                    new_cwa[new_pr] = age
                                except Exception:
                                    pass
                            current_wall_ages = new_cwa

                        log_debug(f"[AutoAnchor] Re-anchored to Spot Gold: {old_offset} -> {new_offset} (delta={delta}, ema={_offset_ema}, raw_sample={raw_ideal_offset}, spot={spot_price}, cme={cme_raw})")
        except Exception as e:
            pass

        time.sleep(300)


def start_server():
    log_debug(f"Starting server on port {PORT}...")
    _load_basis_offset()
    _load_central_m1_live()
    recorder_thread = threading.Thread(target=full_depth_recorder_loop, daemon=True)
    recorder_thread.start()
    ff_thread = threading.Thread(target=forexfactory_watchdog_loop, daemon=True)
    ff_thread.start()
    anchor_thread = threading.Thread(target=auto_spot_anchor_loop, daemon=True)
    anchor_thread.start()
    with ThreadedHTTPServer(("0.0.0.0", PORT), SultanRequestHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    start_server()
