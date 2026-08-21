"""
Auth gate for the public (Cloudflare Tunnel) path into the Chain Reaction
dashboard.

WHY A SEPARATE PORT INSTEAD OF AUTH ON THE DASHBOARD ITSELF:
    cloudflared connects to 127.0.0.1 - exactly like the pywebview desktop
    window does. From sultan_dashboard_server.py's point of view the two are
    indistinguishable, so putting a password there would demand a login on
    Dadang's own desktop window every time he opens it.

    Splitting by PORT separates them cleanly:
        127.0.0.1:8766  <- desktop window, no auth, untouched
        127.0.0.1:8767  <- this gate, requires login, forwards to 8766
    cloudflared points at 8767, so only traffic arriving from the internet
    ever sees the password prompt.

WHY THIS MATTERS AT ALL: the dashboard shows account balance, equity, open
positions and live signals. trade.dadangchatai.com was verified (2026-08-14,
HTTP 530 straight from the tunnel layer) to have NO Cloudflare Access policy
in front of it - the old app's login belonged to the retired app, not to the
hostname. Without this gate the tunnel would publish all of that to anyone
who knows the URL.

The password lives in tunnel_password.txt next to this file - never in the
source, never in git. It is generated on first run if missing.
"""

import base64
import http.server
import os
import secrets
import socketserver
import urllib.error
import urllib.request

GATE_PORT = 8767                     # what cloudflared connects to
UPSTREAM = "http://127.0.0.1:8766"   # the real dashboard, left unauthenticated for localhost
PASSWORD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_password.txt")
USERNAME = "dadang"

# Browsers only send credentials after a 401 challenge, and they cache them
# per realm - so the realm string is what keeps a saved login working.
REALM = "Chain Reaction System"


def load_or_create_password() -> str:
    if os.path.exists(PASSWORD_FILE):
        pw = open(PASSWORD_FILE, "r", encoding="utf-8").read().strip()
        if pw:
            return pw
    # token_urlsafe(9) -> 12 chars, easy enough to type on a phone but far
    # beyond guessing range for a URL nobody has published.
    pw = secrets.token_urlsafe(9)
    with open(PASSWORD_FILE, "w", encoding="utf-8") as f:
        f.write(pw)
    print(f"[Gate] password baru dibuat -> {PASSWORD_FILE}", flush=True)
    return pw


PASSWORD = load_or_create_password()
EXPECTED = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()

# 2026-08-19: Dadang - "wkwkwk lupa gw bro buang aja deh gak usah password
# password an" - a friend's EA (DD_ChainReaction_Friend.mq5) needs to fetch
# this ONE path with no login (MQL5 WebRequest, no interactive auth prompt to
# type a password into). Only this specific path skips the gate - the rest
# of the dashboard (balance/equity/positions via /sultan_status.json and /)
# stays password-protected exactly as before. Keep this set to EXACT paths
# only, never a prefix/wildcard - it's a public-access allowlist.
PUBLIC_PATHS = {"/bookmap_share.json"}


class GateHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _challenge(self):
        body = b"Unauthorized"
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path_only = self.path.split("?")[0]
        if path_only not in PUBLIC_PATHS:
            auth = self.headers.get("Authorization", "")
            # compare_digest keeps the check constant-time; a plain == would
            # leak the password one character at a time to anyone measuring
            # latency.
            if not auth or not secrets.compare_digest(auth, EXPECTED):
                self._challenge()
                return

        try:
            with urllib.request.urlopen(UPSTREAM + self.path, timeout=10) as up:
                body = up.read()
                ctype = up.headers.get("Content-Type", "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            # Dashboard not up yet (started before it, or it crashed) - say so
            # plainly instead of a blank page.
            body = f"Dashboard belum jalan di {UPSTREAM} ({e})".encode()
            self.send_response(502)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # the page polls ~1x/sec; logging every hit is pure noise


class ThreadedServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    print(f"[Gate] listening 127.0.0.1:{GATE_PORT} -> {UPSTREAM}", flush=True)
    print(f"[Gate] user={USERNAME}  password ada di {PASSWORD_FILE}", flush=True)
    with ThreadedServer(("127.0.0.1", GATE_PORT), GateHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
