"""Stdlib HTTP server: serves static dashboard files + proxies /api/* to engine."""

import http.server
import json
import mimetypes
import threading
import urllib.request
import webbrowser
from pathlib import Path

STATIC = Path(__file__).parent / "static"


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    engine_url: str = ""
    api_key: str = ""

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy("GET", b"")
        elif self.path == "/" or "." not in self.path.split("/")[-1]:
            self._serve_index()
        else:
            self._serve_static()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if self.path.startswith("/api/"):
            self._proxy("POST", body)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy("DELETE", b"")

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if self.path.startswith("/api/"):
            self._proxy("PATCH", body)

    def _proxy(self, method: str, body: bytes):
        engine_path = self.path[4:]  # strip /api prefix
        target_url = f"{self.engine_url}{engine_path}"
        req = urllib.request.Request(
            target_url,
            data=body or None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": self.headers.get("Content-Type", "application/json"),
                "Accept": self.headers.get("Accept", "*/*"),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.end_headers()
                while chunk := resp.read(4096):
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _serve_index(self):
        index_path = STATIC / "index.html"
        if not index_path.exists():
            self._serve_no_build()
            return
        html = index_path.read_text()
        config = json.dumps({"url": self.engine_url, "key": self.api_key})
        inject = f"<script>window.__CORTEXA__={config}</script>"
        html = html.replace("</head>", f"{inject}</head>")
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self):
        path = STATIC / self.path.lstrip("/")
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_no_build(self):
        body = b"""<!DOCTYPE html>
<html>
<head><title>CortexOS Dashboard</title>
<style>
  body { background: #0D0D0D; color: #fff; font-family: monospace;
         display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
  .box { text-align: center; }
  h1 { color: #00FF88; font-size: 2rem; margin-bottom: 0.5rem; }
  p { color: #888; }
  code { background: #141414; padding: 0.25rem 0.5rem; border-radius: 4px; color: #00DDFF; }
</style>
</head>
<body>
<div class="box">
  <h1>CortexOS Dashboard</h1>
  <p>Static files not found. Build the UI first:</p>
  <br>
  <code>cd cortexos-sdk/dashboard-ui && npm install && npm run build</code>
</div>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence request logs
        pass


def serve(engine_url: str, api_key: str, port: int, open_browser: bool) -> None:
    """Start the local dashboard server."""
    handler = type(
        "Handler",
        (DashboardHandler,),
        {"engine_url": engine_url, "api_key": api_key},
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://localhost:{port}"
    print(f"\n  CortexOS Dashboard → {url}\n")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=[url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Dashboard stopped.")
        server.shutdown()
