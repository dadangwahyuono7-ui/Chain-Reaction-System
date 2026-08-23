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

import http.server
import json
import os
import socketserver
import threading
import time

import webview

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sultan")
PORT = 8766

MT5_COMMON_FILES_DIR = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
SULTAN_STATUS_FILE = os.path.join(MT5_COMMON_FILES_DIR, "sultan_status.json")
# 2026-08-23 - "News & Catalyst" tab: today's high-impact calendar events,
# written by the EA's ExportTodayCalendar() (v52.86) - same
# MQL5-can-only-write-to-its-own-sandbox reason SULTAN_STATUS_FILE needs
# proxying.
TODAY_CALENDAR_FILE = os.path.join(MT5_COMMON_FILES_DIR, "today_calendar.json")

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
        if path == "/sultan_status.json":
            self._serve_sultan_status()
            return
        if path == "/bookmap_share.json":
            self._serve_bookmap_share()
            return
        if path == "/today_calendar.json":
            self._serve_json_passthrough(TODAY_CALENDAR_FILE, b"[]")
            return
        if path in self._INDEX_ALIASES:
            self.path = "/index.html"
        super().do_GET()

    def _serve_sultan_status(self):
        try:
            with open(SULTAN_STATUS_FILE, "r", encoding="ascii") as f:
                body = f.read().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            body = b'{"online": false, "error": "sultan_status.json not written yet - is the EA (v34+) attached and running?"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(500, str(e))

    def _serve_bookmap_share(self):
        # Sanitized mirror for a friend's independent EA (see
        # BOOKMAP_SHARE_FIELDS comment above) - strips balance/equity/regime/
        # conviction/signals, keeps only what actually came from Bookmap.
        try:
            with open(SULTAN_STATUS_FILE, "r", encoding="ascii") as f:
                full = json.load(f)
            shared = {k: full[k] for k in BOOKMAP_SHARE_FIELDS if k in full}
            shared["timestamp"] = full.get("timestamp")
            shared["symbol"] = full.get("symbol")
            shared["price"] = full.get("price")
            shared["online"] = bool(full.get("data_status", {}).get("bookmap_online", False))
            shared["bridge_latency_ms"] = full.get("data_status", {}).get("bridge_latency_ms")
            body = json.dumps(shared).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            body = b'{"online": false, "error": "sultan_status.json not written yet"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(500, str(e))

    def _serve_json_passthrough(self, filepath, fallback_body):
        """Generic version of _serve_sultan_status's file->HTTP proxy, used
        for today_calendar.json (and any future MQL5-sandbox file) so each
        new source doesn't need its own copy-pasted try/except block."""
        try:
            with open(filepath, "r", encoding="ascii") as f:
                body = f.read().encode("utf-8")
        except FileNotFoundError:
            body = fallback_body
        except Exception as e:
            self.send_error(500, str(e))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
    with ThreadedHTTPServer(("0.0.0.0", PORT), SultanRequestHandler) as httpd:
        httpd.serve_forever()


def main():
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    print(f"[Sultan Dashboard] Local:   http://127.0.0.1:{PORT}/index.html", flush=True)
    print(f"[Sultan Dashboard] Status source: {SULTAN_STATUS_FILE}", flush=True)

    try:
        # v52.72 (2026-08-20): was a fixed width=1220/height=760 box - Dadang:
        # "kurang proporsional yang bawah ketutup gak bisa keliatan full
        # layar" - page content (6 sections + wall ladder) is taller than
        # 760px, so the bottom was silently clipped with no visible way to
        # scroll. maximized=True opens at the real screen size instead of a
        # guessed fixed box (still resizable/restorable - Dadang can un-
        # maximize if he wants the small floating window back).
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

    # Keep the HTTP server thread alive even if the window is closed, same
    # as dashboard_web.py - so http://127.0.0.1:8766 stays reachable from a
    # browser too, not just the native window.
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
