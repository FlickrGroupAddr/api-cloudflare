"""Serve only the local, synthetic lifecycle review prototype on loopback."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1] / "prototypes/native-flickr-admin"
FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.mjs": "app.mjs",
    "/model.mjs": "model.mjs",
    "/styles.css": "styles.css",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, status, body=b"", content_type="application/json", location=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; form-action 'none'; base-uri 'none'",
        )
        if location:
            self.send_header("Location", location)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            self.respond(200, b'{"service":"fga-native-review","synthetic":true}')
            return
        filename = FILES.get(path)
        if not filename:
            self.respond(404)
            return
        mime = (
            "text/css"
            if filename.endswith(".css")
            else "text/javascript"
            if filename.endswith(".mjs")
            else "text/html; charset=utf-8"
        )
        self.respond(200, (ROOT / filename).read_bytes(), mime)

    def do_POST(self):
        if (
            self.headers.get("X-CSRF-Token") != "synthetic-review"
            or self.headers.get("Content-Type") != "application/json"
        ):
            self.respond(403)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.respond(400)
            return
        if size < 1 or size > 1024:
            self.respond(400)
            return
        self.rfile.read(size)
        path = urlsplit(self.path).path
        if path == "/preview/legacy-start":
            port = cast(ThreadingHTTPServer, self.server).server_port
            self.respond(303, location=f"http://127.0.0.1:{port}/preview/consent")
        elif path == "/preview/json-start":
            self.respond(
                201,
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "authorizationTransactionId": "synthetic-review-only",
                        "authorizationUrl": "https://www.flickr.com/services/oauth/authorize?oauth_token=synthetic-review-only",
                        "expiresAt": (datetime.now(UTC) + timedelta(minutes=5))
                        .isoformat(timespec="microseconds")
                        .replace("+00:00", "Z"),
                    }
                ).encode(),
            )
        else:
            self.respond(404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    status = ROOT.parents[1] / ".coordination-runs/native-ui-preview-status.json"
    status.write_text(
        json.dumps({"service": "fga-native-review", "url": url, "pid": os.getpid()}),
        encoding="utf-8",
    )
    print("Synthetic review preview: " + url, flush=True)
    server.serve_forever()
