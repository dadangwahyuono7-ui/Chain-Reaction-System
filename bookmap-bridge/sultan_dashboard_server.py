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
import secrets
import socketserver
import threading
import time
import urllib.error
import urllib.request

import psutil
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

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/settings/translate":
            self._save_translate_settings()
            return
        if path == "/api/admin/setup":
            self._admin_setup()
            return
        if path == "/api/admin/login":
            self._admin_login()
            return
        if path == "/api/admin/logout":
            self._admin_logout()
            return
        self.send_error(404, "Not found")

    def _json_response(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def _get_session_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = http.cookies.SimpleCookie()
        jar.load(raw)
        return jar["session"].value if "session" in jar else None

    def _is_logged_in(self):
        return _session_valid(self._get_session_token())

    def _system_health(self):
        # 2026-08-25 - Dadang's Android app design mockup has a "System
        # Status" screen with CPU/Memory/Disk Usage (monitoring whatever
        # PC/mini-PC actually runs this backend) - didn't exist anywhere
        # in this project before. psutil.cpu_percent(interval=None) reads
        # against the LAST call (primed once at import time below, see
        # _PSUTIL_CPU_PRIMED) - non-blocking, unlike passing an interval
        # here which would stall this request for that many seconds.
        disk = psutil.disk_usage(os.path.abspath(__file__)[:3] or "C:\\")
        self._json_response(200, {
            "cpu_pct": round(psutil.cpu_percent(interval=None), 1),
            "memory_pct": round(psutil.virtual_memory().percent, 1),
            "disk_pct": round(disk.percent, 1),
        })

    def _admin_status(self):
        env = _read_env_file()
        self._json_response(200, {
            "setup_done": bool(env.get("ADMIN_PASSWORD_HASH")),
            "logged_in": self._is_logged_in(),
            "email": env.get("ADMIN_EMAIL", "") if self._is_logged_in() else "",
        })

    def _admin_get_settings(self):
        """Current translate/analysis config, for the admin panel to show
        what's actually active (and pre-select in the model dropdowns)
        instead of always presenting blank fields. The API key itself is
        never sent back in full - only a masked tail - so it's not
        re-exposed to the browser just for viewing the settings page."""
        if not self._is_logged_in():
            self._json_response(401, {"ok": False, "error": "Belum login"})
            return
        env = _read_env_file()
        key = env.get("TRANSLATE_API_KEY", "")
        masked = f"...{key[-4:]}" if len(key) > 4 else ("(belum diisi)" if not key else "***")
        self._json_response(200, {
            "ok": True,
            "api_key_masked": masked,
            "api_base": env.get("TRANSLATE_API_BASE", ""),
            "translate_model": env.get("TRANSLATE_MODEL", ""),
            "analysis_model": env.get("ANALYSIS_MODEL", ""),
        })

    def _admin_list_models(self):
        """Dadang: 'model translate ini sebaiknya detect model yang ready
        jadi dropdown deh bro supaya gw gak nebak2 jika ganti api' - fetches
        the live model list from whichever gateway is currently saved
        (same GET {base}/models call already confirmed working tonight),
        so the dropdown always reflects what THIS key can actually use -
        switching to a different key/provider later just works, no need
        to know exact model id strings."""
        if not self._is_logged_in():
            self._json_response(401, {"ok": False, "error": "Belum login"})
            return
        env = _read_env_file()
        api_base = env.get("TRANSLATE_API_BASE", "").rstrip("/")
        api_key = env.get("TRANSLATE_API_KEY", "")
        if not api_base or not api_key:
            self._json_response(400, {"ok": False, "error": "API key/base URL belum di-set - isi dulu terus Simpan"})
            return
        try:
            req = urllib.request.Request(f"{api_base}/models", headers={"Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))
            self._json_response(200, {"ok": True, "models": models})
        except Exception as e:
            self._json_response(502, {"ok": False, "error": f"Gagal ambil daftar model: {e}"})

    def _admin_setup(self):
        env = _read_env_file()
        if env.get("ADMIN_PASSWORD_HASH"):
            self._json_response(409, {"ok": False, "error": "Akun admin udah pernah di-setup. Pakai login, bukan setup lagi."})
            return
        try:
            body = self._read_json_body()
        except Exception:
            self._json_response(400, {"ok": False, "error": "Body bukan JSON valid"})
            return
        email = (body.get("email") or "").strip()
        password = body.get("password") or ""
        if not email or len(password) < 6:
            self._json_response(400, {"ok": False, "error": "Email wajib diisi, password minimal 6 karakter"})
            return
        salt = secrets.token_hex(16)
        pw_hash = _hash_password(password, salt)
        _write_env_updates({"ADMIN_EMAIL": email, "ADMIN_PASSWORD_SALT": salt, "ADMIN_PASSWORD_HASH": pw_hash})
        token = _create_session()
        self.send_response(200)
        self.send_header("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_SEC}")
        self.send_header("Content-Type", "application/json")
        body_out = json.dumps({"ok": True}).encode("utf-8")
        self.send_header("Content-Length", str(len(body_out)))
        self.end_headers()
        self.wfile.write(body_out)

    def _admin_login(self):
        env = _read_env_file()
        stored_email = env.get("ADMIN_EMAIL", "")
        stored_salt = env.get("ADMIN_PASSWORD_SALT", "")
        stored_hash = env.get("ADMIN_PASSWORD_HASH", "")
        if not stored_hash:
            self._json_response(409, {"ok": False, "error": "Belum ada akun admin - setup dulu."})
            return
        try:
            body = self._read_json_body()
        except Exception:
            self._json_response(400, {"ok": False, "error": "Body bukan JSON valid"})
            return
        email = (body.get("email") or "").strip()
        password = body.get("password") or ""
        candidate_hash = _hash_password(password, stored_salt) if stored_salt else ""
        if email != stored_email or not secrets.compare_digest(candidate_hash, stored_hash):
            self._json_response(401, {"ok": False, "error": "Email atau password salah"})
            return
        token = _create_session()
        self.send_response(200)
        self.send_header("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_SEC}")
        self.send_header("Content-Type", "application/json")
        body_out = json.dumps({"ok": True}).encode("utf-8")
        self.send_header("Content-Length", str(len(body_out)))
        self.end_headers()
        self.wfile.write(body_out)

    def _admin_logout(self):
        token = self._get_session_token()
        if token and token in _sessions:
            del _sessions[token]
        self.send_response(200)
        self.send_header("Set-Cookie", "session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")
        self.send_header("Content-Type", "application/json")
        body_out = json.dumps({"ok": True}).encode("utf-8")
        self.send_header("Content-Length", str(len(body_out)))
        self.end_headers()
        self.wfile.write(body_out)

    def _save_translate_settings(self):
        if not self._is_logged_in():
            self._json_response(401, {"ok": False, "error": "Belum login - buka /admin.html dulu"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json_response(400, {"ok": False, "error": "Body bukan JSON valid"})
            return

        field_to_env_key = {
            "api_key": "TRANSLATE_API_KEY",
            "api_base": "TRANSLATE_API_BASE",
            "model": "TRANSLATE_MODEL",
            "analysis_model": "ANALYSIS_MODEL",
        }
        updates = {}
        for key, env_key in field_to_env_key.items():
            val = (body.get(key) or "").strip()
            if val:
                updates[env_key] = val
        if not updates:
            self._json_response(400, {"ok": False, "error": "Gak ada field yang diisi"})
            return

        _write_env_updates(updates)
        self._json_response(200, {"ok": True, "saved": list(updates.keys())})

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
    # priming call for _system_health()'s psutil.cpu_percent(interval=None) -
    # the first-ever call always returns a meaningless 0.0, subsequent calls
    # measure against the previous call's timestamp instead.
    psutil.cpu_percent(interval=None)
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
