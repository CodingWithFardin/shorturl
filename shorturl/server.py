"""HTTP layer: one request in, one response out, no framework."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .store import resolve_path


def handle(shortener, method, raw_path, body=b""):
    """Return (status, headers, body_bytes). Kept pure so it can be tested."""
    parsed = urlparse(raw_path)
    kind, value = resolve_path(parsed.path)

    if method == "GET" and kind == "health":
        return 200, {"Content-Type": "application/json"}, b'{"ok":true}'

    if method == "GET" and kind == "redirect":
        url = shortener.hit(value)
        if not url:
            return 404, {"Content-Type": "text/plain"}, b"not found"
        return 302, {"Location": url, "Content-Type": "text/plain"}, b""

    if method == "POST" and kind == "api":
        try:
            payload = json.loads(body or b"{}")
            code = shortener.shorten(payload.get("url", ""))
        except (ValueError, json.JSONDecodeError) as exc:
            return 400, {"Content-Type": "application/json"}, json.dumps({"error": str(exc)}).encode()
        return 201, {"Content-Type": "application/json"}, json.dumps({"code": code}).encode()

    if method == "GET" and kind == "api":
        params = parse_qs(parsed.query)
        code = (params.get("code") or [""])[0]
        if code:
            stats = shortener.stats(code)
            if not stats:
                return 404, {"Content-Type": "application/json"}, b'{"error":"unknown code"}'
            return 200, {"Content-Type": "application/json"}, json.dumps(stats).encode()
        return 200, {"Content-Type": "application/json"}, json.dumps(shortener.top()).encode()

    if method == "GET" and kind == "home":
        return 200, {"Content-Type": "text/plain"}, b"POST /api/links with a json url\n"

    return 404, {"Content-Type": "text/plain"}, b"not found"


def make_server(shortener, host="127.0.0.1", port=8080):
    class Handler(BaseHTTPRequestHandler):
        def _dispatch(self, method):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            status, headers, payload = handle(shortener, method, self.path, body)
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def log_message(self, fmt, *args):
            return

    return ThreadingHTTPServer((host, port), Handler)
