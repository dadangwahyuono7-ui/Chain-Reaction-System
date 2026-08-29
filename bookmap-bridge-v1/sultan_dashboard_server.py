"""
SULTAN SNIPER ENGINE - Web Dashboard Server (v34)
Location: bookmap-bridge/sultan_dashboard_server.py

Dadang: "gak usah baca pine langsung mt5 aja supaya bagus tv nya kita close
dan tidak dipakai" + "untuk web dhasboard untuk mt5 lo buat semaximal
mungkin tapi focus web dhaboard dulu" + "ini buat dari phiton seperti
sebelumya bro agar bisa terbuka langsung" - this serves a NEW dashboard whose
data comes directly from MT5 (DD_ChainReaction_MultiTF_EA.mq5's
WriteSultanStatus(), v34+), not from Bookmap's own Python pipeline
(dashboard_web.py/live_status.json) and not from TradingView. Same launch
pattern as dashboard_web.py: this one script starts the HTTP server AND
opens a native always-on-top pywebview window - no manual browser/URL typing
needed, matches how the existing Chain Reaction dashboard already opens.

Serves:
  - sultan/*.html, *.js, *.css  (static frontend, this folder)
  - /sultan_status.json         (proxied straight from MT5's Common\Files -
                                  MQL5 can only write to its own sandbox, it
                                  cannot write directly into this project
                                  folder, so this endpoint bridges the two)

Runs on port 8766 (separate from dashboard_web.py's 8765, so both dashboards
can run side by side) - plain http.server, no external dependencies for the
server itself; pywebview for the native window (already a dependency of
dashboard_web.py, same venv).
"""

import hashlib
import http.cookies
import http.server
import json
import os
import sys
import secrets
import socketserver
import threading
import time
import urllib.error
import urllib.request

import psutil
try:
    import webview
except ImportError:
    webview = None

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sultan")
PORT = 8766

MT5_COMMON_FILES_DIR = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
SULTAN_STATUS_FILE = os.path.join(MT5_COMMON_FILES_DIR, "sultan_status.json")
# 2026-08-23 - "News & Catalyst" tab: today's high-impact calendar events,
# written by the EA's ExportTodayCalendar() (v52.86) - same
# MQL5-can-only-write-to-its-own-sandbox reason SULTAN_STATUS_FILE needs
# proxying.
TODAY_CALENDAR_FILE = os.path.join(MT5_COMMON_FILES_DIR, "today_calendar.json")

# 2026-08-23 - lets news.html's settings form update news_engine.py's
# translation API key/base/model without touching a file by hand - Dadang:
# "nanti di web kasih tempat gw pasang api key nya karena nanti kedepan gw
# akan pasang yang premium juga bro". Same bookmap-bridge/.env news_engine.py
# already reads every fetch cycle, so a save here takes effect on its next
# cycle with no restart needed.
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _read_env_file():
    env = {}
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def _write_env_updates(updates: dict):
    """Rewrites only the matching KEY= lines in-place, preserving every
    other line (comments, ADMIN_TOKEN, blank lines) exactly as-is - never
    a full-file regenerate, so nothing about the file's own documentation
    or unrelated settings gets lost."""
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    seen = set()
    out = []
    for line in lines:
        stripped = line.strip()
        matched_key = None
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                matched_key = k
        if matched_key:
            out.append(f"{matched_key}={updates[matched_key]}\n")
            seen.add(matched_key)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}\n")

    tmp = ENV_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(out)
    os.replace(tmp, ENV_FILE)


# 2026-08-23 - Dadang: "kenapa gwk lo buat... untuk ganti api kai lo beri
# admin panel aja lo bro nanti gw isi email dan pasword gw" - replaces the
# copy-pasted ADMIN_TOKEN with a real email+password login (his own
# credentials, set up once through the panel itself, never typed by
# Claude). Password is salted+hashed with PBKDF2 (stdlib hashlib, no new
# dependency) - never stored or logged in plain text. Sessions are an
# in-memory dict (token -> expiry) since this is one process serving one
# person; a restart just means logging in again, no persistence needed.
SESSION_TTL_SEC = 7 * 24 * 3600   # 7 days
PBKDF2_ITERATIONS = 200_000
_sessions = {}   # token -> expiry unix ts


def _hash_password(password: str, salt: str):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return digest.hex()


def _create_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + SESSION_TTL_SEC
    return token


def _session_valid(token: str) -> bool:
    if not token:
        return False
    exp = _sessions.get(token)
    if exp is None:
        return False
    if exp < time.time():
        del _sessions[token]
        return False
    return True


# 2026-08-19: Dadang wants a friend in Semarang to test the EA on HIS OWN
# MT5/broker/account ("dia berdiri sendiri bro baca mt5 dia sendiri, hanya
# data bookmap ikut data gw") - the friend's EA should stay fully independent
# except for mirroring Dadang's live Bookmap read over the network. Sharing
# the raw /sultan_status.json would leak balance/equity/CMP-signals too, so
# this is a SEPARATE, sanitized endpoint: only fields actually sourced from
# Bookmap (flow/liquidity/location/wall_sweep/bookmap_read) - no account
# data, no trading signals, nothing proprietary to Dadang's own edge.
BOOKMAP_SHARE_FIELDS = ("flow", "liquidity", "location", "wall_sweep", "bookmap_read")


class SultanRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FOLDER, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    # 2026-08-14: the retired sultan-advisor app lived at /dashboard and that
    # is the URL Dadang has bookmarked ("alamatnya ini bro
    # https://trade.dadangchatai.com/dashboard"). This server serves the page
    # at /, so those paths are mapped onto index.html rather than 404-ing.
    _INDEX_ALIASES = ("/", "/dashboard", "/dashboard/", "/index.htm")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/chart/history":
            self._serve_chart_history()
            return
        if path == "/api/chart/status":
            self._serve_chart_status()
            return
        if path.startswith("/api/chart/"):
            self._proxy_to_chart_engine()
            return
        if path == "/bookmap_full_depth.csv":
            self._serve_full_depth_csv()
            return
        if path in ("/bookmap_live_signal.csv", "/signal.csv"):
            self._serve_signal_csv()
            return
        if path in ("/live_status.json", "/status", "/api/status"):
            self._serve_live_status_json()
            return
        if path == "/sultan_status.json":
            self._serve_sultan_status()
            return
        if path == "/bookmap_share.json":
            self._serve_bookmap_share()
            return
        if path == "/today_calendar.json":
            self._serve_json_passthrough(TODAY_CALENDAR_FILE, b"[]")
            return
        if path == "/api/admin/status":
            self._admin_status()
            return
        if path == "/api/admin/settings":
            self._admin_get_settings()
            return
        if path == "/api/admin/models":
            self._admin_list_models()
            return
        if path == "/api/system_health":
            self._system_health()
            return
        if path in self._INDEX_ALIASES:
            self.path = "/index.html"
        super().do_GET()

    def _serve_chart_history(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            symbol = query.get("symbol", ["XAUUSD"])[0].upper()
            tf = query.get("tf", ["M5"])[0].upper()
            count = int(query.get("count", ["500"])[0])
            mode = query.get("mode", ["mt5"])[0].lower()
            
            vault_file = os.path.join(FOLDER, "candle_vault.json")
            if not os.path.exists(vault_file):
                vault_file = os.path.join(os.path.dirname(FOLDER), "candle_vault.json")
            
            candles = []
            basis_offset = 51.82
            
            # Read real bookmap basis offset if available
            status_path = os.path.join(FOLDER, "live_status.json")
            if not os.path.exists(status_path):
                status_path = os.path.join(os.path.dirname(FOLDER), "live_status.json")
            if os.path.exists(status_path):
                try:
                    with open(status_path, "r", encoding="utf-8") as sf:
                        st = json.load(sf)
                        p_gc = float(st.get("current_price") or st.get("price") or 4506.10)
                        basis_offset = round(p_gc - 4454.28, 2)
                except Exception:
                    pass

            if os.path.exists(vault_file):
                try:
                    with open(vault_file, "r", encoding="utf-8") as f:
                        vault = json.load(f)
                    bars = vault.get(tf, [])
                    if bars and len(bars) > 0:
                        if mode == "cme":
                            # Raw CME GC scale (+basis_offset)
                            for b in bars[-count:]:
                                candles.append({
                                    "time": b["time"],
                                    "open": round(b["open"] + basis_offset, 2),
                                    "high": round(b["high"] + basis_offset, 2),
                                    "low": round(b["low"] + basis_offset, 2),
                                    "close": round(b["close"] + basis_offset, 2),
                                    "volume": b.get("volume", 100)
                                })
                        else:
                            # MT5 Spot scale (default)
                            candles = bars[-count:]
                except Exception:
                    pass

            payload = json.dumps({
                "symbol": symbol,
                "tf": tf,
                "mode": mode,
                "basis_offset": basis_offset,
                "count": len(candles),
                "candles": candles,
                "source": "RAW_CME_FUTURES" if mode == "cme" else "REAL_MT5_SPOT_ALIGNED"
            }).encode("utf-8")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self.send_error(500, f"Chart history error: {e}")


def log_message(self, fmt, *args):
        pass  # keep the console/log quiet - same JSON polled ~1x/sec


class ThreadedHTTPServer(socketserver.ThreadingTCPServer):
    """2026-08-14: was a plain TCPServer, which serves ONE connection at a
    time. Fine while the only client was the local pywebview window, but
    cloudflared holds persistent connections open - so the single handler
    thread stayed occupied and every other request (including the window's
    own 800ms poll) timed out, surfacing publicly as HTTP 502.

    daemon_threads so a hung client connection can't keep the process alive
    after the window is closed; allow_reuse_address so a restart doesn't hit
    TIME_WAIT on 8766."""
    daemon_threads = True
    allow_reuse_address = True


def start_server():
    psutil.cpu_percent(interval=None)
    print(f"[Sultan Dashboard] Server listening on http://0.0.0.0:{PORT}", flush=True)
    print(f"[Sultan Dashboard] Local:   http://127.0.0.1:{PORT}/chart.html", flush=True)
    print(f"[Sultan Dashboard] Status source: {SULTAN_STATUS_FILE}", flush=True)
    while True:
        try:
            with ThreadedHTTPServer(("0.0.0.0", PORT), SultanRequestHandler) as httpd:
                httpd.serve_forever()
        except Exception as e:
            print(f"[Sultan Dashboard] Server restart on error: {e}", flush=True)
            time.sleep(1)


def main():
    is_headless = "--headless" in sys.argv or os.environ.get("HEADLESS") == "1"

    if is_headless or webview is None:
        # Dedicated headless server mode (Runs forever in background!)
        start_server()
        return

    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    try:
        window = webview.create_window(
            "Sultan Sniper Engine",
            url=f"http://127.0.0.1:{PORT}/index.html?t={int(time.time())}",
            width=1220,
            height=760,
            x=650,
            y=60,
            on_top=True,
            frameless=False,
            resizable=True,
            maximized=True,
            background_color="#020617",
        )
        webview.start(debug=False)
    except Exception as e:
        print(f"[Sultan Dashboard] pywebview window closed/bypassed: {e}", flush=True)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
