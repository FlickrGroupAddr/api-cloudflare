"""Bounded HTTP runner for the disposable synthetic Worker; never follows redirects."""

import argparse
import hashlib
import http.client
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

TOKEN = "-".join(["0000"] * 13)
THUMBNAIL = "/api/v001/existing-public-photos/photo/thumbnail"
QUERY = "?page=1&page_size=1&linked_flickr_revision=1"
CASES = {
    "ok": (200, None, 1, 1),
    "jpeg": (200, None, 1, 1),
    "discovery": (200, None, 1, 0),
    "missing-auth": (401, "missing_token", 0, 0),
    "bad-auth": (401, "invalid_token", 0, 0),
    "bad-query": (400, "invalid_request", 0, 0),
    "wrong-revision": (409, "flickr_link_changed", 0, 0),
    "foreign-owner": (503, "photo_thumbnail_unavailable", 1, 0),
    "private-photo": (503, "photo_thumbnail_unavailable", 1, 0),
    "missing-photo": (503, "photo_thumbnail_unavailable", 1, 0),
    "bad-destination": (503, "photo_thumbnail_unavailable", 1, 0),
    "redirect": (503, "photo_thumbnail_unavailable", 1, 1),
    "error-large": (503, "photo_thumbnail_unavailable", 1, 1),
    "declared-large": (503, "photo_thumbnail_unavailable", 1, 1),
    "stream-large": (503, "photo_thumbnail_unavailable", 1, 1),
    "truncated": (503, "photo_thumbnail_unavailable", 1, 1),
    "bad-mime": (503, "photo_thumbnail_unavailable", 1, 1),
    "bad-signature": (503, "photo_thumbnail_unavailable", 1, 1),
    "timeout": (503, "photo_thumbnail_unavailable", 1, 1),
    "link-change": (409, "flickr_link_changed", 1, 1),
    "generation-change": (409, "flickr_link_changed", 1, 1),
    "revoke": (401, "invalid_token", 1, 1),  # Permanent; always last, fresh database per run.
}


def target(origin: str, allow_loopback: bool = False) -> tuple[str, str, int | None]:
    parsed = urlsplit(origin)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        parsed.scheme != "https"
        and not (allow_loopback and local and parsed.scheme == "http")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use an HTTPS origin with no path, credentials, query or fragment")
    return parsed.scheme, parsed.hostname, parsed.port


def exchange(origin: str, path: str, headers: dict[str, str], allow_loopback: bool = False):
    scheme, host, port = target(origin, allow_loopback)
    factory = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
    connection = factory(host, port, timeout=25)
    start = time.monotonic()
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        values = {name.lower(): value for name, value in response.getheaders()}
        # Never allocate an unbounded server body, including error/provider-edge replies.
        body = response.read(262145)
        if len(body) > 262144:
            raise ValueError("response_byte_limit")
        return response.status, values, body, round((time.monotonic() - start) * 1000)
    finally:
        connection.close()


def case_request(case: str) -> tuple[str, dict[str, str]]:
    path = THUMBNAIL + QUERY
    headers = {"Authorization": "Bearer " + TOKEN, "X-Probe-Case": case}
    if case == "discovery":
        path = "/api/v001/existing-public-photos?page=1&page_size=1"
    elif case == "missing-auth":
        del headers["Authorization"]
    elif case == "bad-auth":
        headers["Authorization"] = "Bearer " + TOKEN[:-1] + "G"
    elif case == "bad-query":
        path += "&url=https://example.invalid/"
    elif case in {"wrong-revision", "generation-change", "revoke"}:
        path = path.replace("revision=1", "revision=2")
    return path, headers


def validate(case: str, status: int, headers: dict[str, str], body: bytes) -> None:
    expected, code, pages, images = CASES[case]
    if status != expected or "location" in headers:
        raise ValueError("status_or_redirect")
    if "no-store" not in headers.get("cache-control", ""):
        raise ValueError("cache_policy")
    if headers.get("x-content-type-options") != "nosniff":
        raise ValueError("content_policy")
    if headers.get("x-probe-pages") != str(pages) or headers.get("x-probe-images") != str(images):
        raise ValueError("upstream_contract")
    if case in {"timeout", "stream-large"} and headers.get("x-probe-cancelled") != "true":
        raise ValueError("stream_not_cancelled")
    if case == "missing-auth":
        if body or headers.get("www-authenticate") != 'Bearer realm="fga-api"':
            raise ValueError("missing_auth_challenge")
    elif code is not None:
        if len(body) > 4096 or not headers.get("content-type", "").startswith("application/json"):
            raise ValueError("error_body_bound")
        value = json.loads(body)
        if value["error"]["code"] != code or body.startswith((b"\x89PNG", b"\xff\xd8")):
            raise ValueError("error_envelope")
        if any(fragment in body for fragment in (b"https://", TOKEN.encode(), b"synthetic-owner")):
            raise ValueError("error_disclosure")
    elif case == "discovery":
        value = json.loads(body)
        if len(value["photos"]) != 1 or value["photos"][0]["flickrPhotoId"] != "photo":
            raise ValueError("discovery_shape")
    else:
        mime = "image/jpeg" if case == "jpeg" else "image/png"
        if headers.get("content-type") != mime or headers.get("content-length") != str(len(body)):
            raise ValueError("image_headers")
        valid = (
            body.startswith(b"\xff\xd8\xff") and body.endswith(b"\xff\xd9")
            if case == "jpeg"
            else body.startswith(b"\x89PNG\r\n\x1a\n")
            and body.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")
        )
        if not valid or headers.get("cross-origin-resource-policy") != "same-origin":
            raise ValueError("image_signature_or_origin")


def provenance(root: Path) -> dict[str, str]:
    paths = [
        "src/worker.ts",
        "src/photo_thumbnails.ts",
        "src/existing_photo_discovery.ts",
        "probes/existing-photo-qualification/worker.ts",
        "probes/existing-photo-qualification/wrangler.jsonc",
        "package-lock.json",
    ]
    return {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--seed", action="store_true", help="Seed a fresh disposable migrated DB once"
    )
    parser.add_argument("--allow-loopback", action="store_true")
    args = parser.parse_args()
    target(args.origin, args.allow_loopback)
    access = os.environ.get("FGA_PHOTO_PROBE_ACCESS", "")
    if len(access) < 32:
        parser.error("Set FGA_PHOTO_PROBE_ACCESS to the reviewed disposable access secret")
    results = []
    try:
        status, _, body, _ = exchange(args.origin, THUMBNAIL + QUERY, {}, args.allow_loopback)
        if status != 404 or body:
            raise ValueError("probe_gate")
        if args.seed:
            status, _, _, _ = exchange(
                args.origin, "/__probe/seed", {"X-Probe-Access": access}, args.allow_loopback
            )
            if status != 204:
                raise ValueError("fresh_fixture_seed")
        for case in CASES:
            path, headers = case_request(case)
            headers["X-Probe-Access"] = access
            status, received, body, elapsed = exchange(
                args.origin, path, headers, args.allow_loopback
            )
            validate(case, status, received, body)
            results.append(
                {
                    "case": case,
                    "status": status,
                    "bytes": len(body),
                    "elapsedMs": elapsed,
                    "passed": True,
                }
            )
    except Exception:
        # No raw exception, URLs, headers, credentials or payloads in public evidence.
        results.append(
            {
                "case": list(CASES)[len(results)] if len(results) < len(CASES) else "gate",
                "passed": False,
            }
        )
    passed = len(results) == len(CASES) and all(row["passed"] for row in results)
    report = {
        "schemaVersion": 1,
        "scope": "synthetic disposable edge; no native host or real Flickr qualification",
        "passed": passed,
        "sourceSha2_256": provenance(Path(__file__).resolve().parents[1]),
        "cases": results,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Synthetic edge matrix: {'passed' if passed else 'failed'}; {len(results)} cases recorded"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
