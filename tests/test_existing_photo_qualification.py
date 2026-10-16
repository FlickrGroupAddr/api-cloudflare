"""Local adapter/runner checks; never claim these qualify a hosted edge."""

import base64
import http.server
import json
import subprocess
import threading
import unittest
from pathlib import Path

from scripts.existing_photo_qualification import CASES, case_request, exchange, target, validate

ROOT = Path(__file__).resolve().parents[1]


class QualificationTests(unittest.TestCase):
    def test_actual_production_handler_matrix(self):
        result = subprocess.run(
            ["node", "probes/existing-photo-qualification/local_matrix.mjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=45,
            check=True,
        )
        snapshots = json.loads(result.stdout)
        self.assertEqual([row["scenario"] for row in snapshots], list(CASES))
        for row in snapshots:
            with self.subTest(case=row["scenario"]):
                validate(
                    row["scenario"], row["status"], row["headers"], base64.b64decode(row["body"])
                )
                if row["scenario"] == "timeout":
                    self.assertGreaterEqual(row["elapsedMs"], 14500)
                    self.assertLess(row["elapsedMs"], 25000)

    def test_origin_boundary(self):
        for origin in [
            "http://example.com",
            "https://u:p@example.com",
            "https://example.com/path",
            "https://example.com?x=1",
            "https://example.com#fragment",
        ]:
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                target(origin)
        self.assertEqual(target("https://example.com"), ("https", "example.com", None))
        self.assertEqual(target("http://127.0.0.1:8000", True), ("http", "127.0.0.1", 8000))

    def test_request_cases_are_fixed(self):
        self.assertEqual(list(CASES)[-1], "revoke")
        for case in CASES:
            path, headers = case_request(case)
            self.assertTrue(path.startswith("/api/v001/existing-public-photos"))
            self.assertEqual(headers["X-Probe-Case"], case)

    def test_http_reader_does_not_follow_redirect_and_caps_errors(self):
        seen = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                seen.append(self.path)
                self.send_response(302 if self.path == "/redirect" else 500)
                if self.path == "/redirect":
                    self.send_header("Location", "/target")
                self.end_headers()
                if self.path != "/redirect":
                    self.wfile.write(b"x" * 262145)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            origin = f"http://127.0.0.1:{server.server_port}"
            self.assertEqual(exchange(origin, "/redirect", {}, True)[0], 302)
            self.assertEqual(seen, ["/redirect"])
            with self.assertRaisesRegex(ValueError, "response_byte_limit"):
                exchange(origin, "/large", {}, True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
