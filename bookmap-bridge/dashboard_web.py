"""
Chain Reaction Dashboard - Web Edition
Location: bookmap-bridge/dashboard_web.py

Same live_status.json data as cr_dashboard_app.py (Tkinter), but rendered as
real HTML/CSS (dashboard.html) inside a native always-on-top webview window -
pixel-accurate to the approved mockup (rounded cards, pulsing badge glow,
smooth live ticker), which Tkinter cannot reproduce natively.

Serves bookmap-bridge/ over a local HTTP server (so dashboard.html can
fetch('live_status.json') without file:// CORS issues), then opens it in a
pywebview window.
"""

import http.server
import os
import socket
import socketserver
import threading

import webview

FOLDER = os.path.dirname(os.path.abspath(__file__))
PORT = 8765


def _lan_ip() -> str:
    """Best-effort LAN IP so Dadang can open the dashboard from phone/tablet
    on the same network - doesn't actually send anything, just asks the OS
    which local interface would be used to reach an external address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def start_server():
    os.chdir(FOLDER)
    class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            super().end_headers()

    with socketserver.TCPServer(("0.0.0.0", PORT), NoCacheHTTPRequestHandler) as httpd:
        httpd.serve_forever()


def main():
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    lan_ip = _lan_ip()
    print(f"[Dashboard] Local:   http://127.0.0.1:{PORT}/dashboard.html", flush=True)
    print(f"[Dashboard] Network: http://{lan_ip}:{PORT}/dashboard.html  (buka ini dari HP/tablet di WiFi yang sama)", flush=True)

    try:
        import time
        window = webview.create_window(
            "Chain Reaction — Decision Recommendation Engine",
            url=f"http://127.0.0.1:{PORT}/dashboard.html?t={int(time.time())}",
            width=1280,
            height=880,
            x=20,
            y=40,
            on_top=True,
            frameless=False,
            resizable=True,
            background_color="#0b0e14",
        )
        webview.start(debug=True)
    except Exception as e:
        print(f"[Dashboard] pywebview window closed/bypassed: {e}", flush=True)

    # Keep HTTP server thread alive infinitely so browser access (127.0.0.1:8765) never fails with ERR_CONNECTION_REFUSED
    import time
    while True:
        time.sleep(1)



if __name__ == "__main__":
    main()
