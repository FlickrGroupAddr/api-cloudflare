"""Independent contract checks for the routing collector's failure detection."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("route_conformance", SCRIPTS / "route_conformance.py")
assert spec and spec.loader
routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes)


class Response:
    def __init__(self, status: int, body: bytes, headers: list[tuple[str, str]]) -> None:
        self.status, self.body, self.headers = status, body, headers

    def read(self, _limit: int) -> bytes:
        return self.body

    def getheaders(self) -> list[tuple[str, str]]:
        return self.headers


class Connection:
    def __init__(self, response: Response) -> None:
        self.response = response

    def request(self, *_args: object, **_kwargs: object) -> None:
        pass

    def getresponse(self) -> Response:
        return self.response

    def close(self) -> None:
        pass


class CollectorTests(unittest.TestCase):
    def collect(self, response: Response, case: dict[str, object]) -> dict[str, Any]:
        with patch.object(routes.http.client, "HTTPConnection", return_value=Connection(response)):
            return routes.probe("http://127.0.0.1:8799", [case])[0]

    def test_html_error_cannot_pass_as_backend_404(self) -> None:
        result = self.collect(
            Response(404, b"<!doctype html>Wrong owner", [("Content-Type", "text/html")]),
            {"id": "unknown", "method": "GET", "path": "/api/missing", "status": 404},
        )
        self.assertFalse(result["passed"])
        self.assertIn("json_type", result["errors"])

    def test_health_rejects_identifying_fields_and_cookies(self) -> None:
        result = self.collect(
            Response(
                200,
                b'{"schemaVersion":1,"status":"ok","build":"synthetic"}',
                [
                    ("Content-Type", "application/json"),
                    ("Cache-Control", "no-store"),
                    ("Set-Cookie", "synthetic=1"),
                ],
            ),
            {
                "id": "health",
                "method": "GET",
                "path": "/healthz/live",
                "status": 200,
                "boundary": "health",
            },
        )
        self.assertFalse(result["passed"])
        self.assertIn("health_schema", result["errors"])
        self.assertIn("cookie", result["errors"])

    def test_fixed_health_response_passes(self) -> None:
        result = self.collect(
            Response(
                200,
                b'{"schemaVersion":1,"status":"ok"}',
                [("Content-Type", "application/json"), ("Cache-Control", "no-store")],
            ),
            {
                "id": "health",
                "method": "GET",
                "path": "/healthz/live",
                "status": 200,
                "boundary": "health",
            },
        )
        self.assertTrue(result["passed"])

    def test_contract_boundaries_are_in_matrix(self) -> None:
        cases = routes.matrix(
            {"routes": []}, {"path": "/admin/assets/proof.js", "sha2_256": "synthetic"}
        )
        paths = {(case["method"], case["path"]) for case in cases}
        for pair in [
            ("GET", "/api"),
            ("GET", "/api/v001"),
            ("GET", "/admin\\"),
            ("GET", "/api/%00"),
            ("POST", "/api/v001/group-submission"),
            ("POST", "/api/v001/installations/current"),
            ("POST", "/admin/"),
        ]:
            self.assertIn(pair, paths)
        self.assertEqual(len(cases), len({case["id"] for case in cases}))


if __name__ == "__main__":
    unittest.main()
