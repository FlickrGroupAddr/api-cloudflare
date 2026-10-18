"""Finite, separately consented configuration-metadata GET collection.

The CLI loads only an explicitly named private token file after plan/consent
validation. ``collect`` also supports a callable credential delivery mechanism
for synthetic tests. Construction/plan validation never requests a token.
All returned projections are partial metadata; they are never a complete baseline.
Transport injection is trusted synthetic test code, not an authority boundary.

Plan exact fields: schemaVersion=1, kind="temporary_composition_metadata_plan",
runId (32 lowercase hex), sourceSha256=source_sha256(), endpointAddress (public
numeric IP), startsAt/expiresAt (UTC Z, at most one hour), timeoutSeconds (1..60),
maxResponseBytes (1..262144), credentialBinding (SHA256 of delivered token ASCII),
grantEvidenceSha256 (independently reviewed effective-policy evidence digest),
outputPath/journalPath (exact absolute resolved private sink paths),
requests=[{"scope": safe scope, "target": exact target dict}]. Max 18 requests.
Consent exact fields: approved=True, decisionRef (nonempty text), planSha256,
sourceSha256, credentialBinding, grantEvidenceSha256. Bindings must match the plan.
The entire response scope must be authorized, including every zone route.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.hosted_publisher_execution_provider import _address, _pinned_https
from scripts.hosted_publisher_finite_client import Request, Response
from scripts.temporary_composition_metadata_projection import endpoint_for, project_metadata

MAX_REQUESTS = 18
SOURCE_FILES = (
    "temporary_composition_metadata_collector.py",
    "temporary_composition_metadata_projection.py",
    "hosted_publisher_execution_provider.py",
    "hosted_publisher_finite_client.py",
    "hosted_publisher_provider.py",
    "hosted_publisher_worker_deployment.py",
    "hosted_publisher_worker_identity.py",
)


class CollectionError(ValueError):
    """Sanitized refusal or failed collection; never replay its output paths."""


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n"
    ).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def source_sha256() -> dict[str, str]:
    """Local source manifest; the caller must retain/review its independent copy."""
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise CollectionError(code)


def _keys(value: Any, keys: set[str], code: str) -> None:
    _require(type(value) is dict and set(value) == keys, code)


def _utc(value: Any) -> datetime:
    _require(type(value) is str and value.endswith("Z"), "collection_timestamp")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise CollectionError("collection_timestamp") from None
    return result


def _now() -> datetime:
    return datetime.now(UTC)


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, "collection_duplicate_json_key")
        result[key] = value
    return result


def _json(body: bytes) -> Any:
    try:
        return json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(CollectionError("collection_json")),
        )
    except ValueError, UnicodeError, RecursionError:
        raise CollectionError("collection_json") from None


def _prepare(plan, expected_plan_sha256, consent, now):
    # Bound operator input before canonicalizing it. No raw plan/target appears in errors.
    try:
        encoded = canonical(plan)
    except ValueError, TypeError, RecursionError:
        raise CollectionError("collection_plan_invalid") from None
    _require(len(encoded) <= 65_536, "collection_plan_limit")
    _require(
        type(expected_plan_sha256) is str
        and re.fullmatch(r"[a-f0-9]{64}", expected_plan_sha256) is not None
        and hashlib.sha256(encoded).hexdigest() == expected_plan_sha256,
        "collection_independent_plan_pin",
    )
    _keys(
        plan,
        {
            "schemaVersion",
            "kind",
            "runId",
            "sourceSha256",
            "endpointAddress",
            "startsAt",
            "expiresAt",
            "timeoutSeconds",
            "maxResponseBytes",
            "credentialBinding",
            "grantEvidenceSha256",
            "outputPath",
            "journalPath",
            "requests",
        },
        "collection_plan_fields",
    )
    _require(
        type(plan["schemaVersion"]) is int
        and plan["schemaVersion"] == 1
        and plan["kind"] == "temporary_composition_metadata_plan",
        "collection_plan_schema",
    )
    _require(
        type(plan["runId"]) is str and re.fullmatch(r"[a-f0-9]{32}", plan["runId"]) is not None,
        "collection_run_id",
    )
    _require(
        type(plan["credentialBinding"]) is str
        and re.fullmatch(r"[a-f0-9]{64}", plan["credentialBinding"]) is not None,
        "collection_credential_binding",
    )
    _require(plan["sourceSha256"] == source_sha256(), "collection_source_pin")
    _require(
        type(plan["grantEvidenceSha256"]) is str
        and re.fullmatch(r"[a-f0-9]{64}", plan["grantEvidenceSha256"]) is not None,
        "collection_grant_evidence_pin",
    )
    _keys(
        consent,
        {
            "approved",
            "decisionRef",
            "planSha256",
            "sourceSha256",
            "credentialBinding",
            "grantEvidenceSha256",
        },
        "collection_consent_fields",
    )
    _require(
        consent["approved"] is True
        and consent["planSha256"] == expected_plan_sha256
        and consent["sourceSha256"] == plan["sourceSha256"]
        and consent["credentialBinding"] == plan["credentialBinding"]
        and consent["grantEvidenceSha256"] == plan["grantEvidenceSha256"],
        "collection_consent",
    )
    ref = consent["decisionRef"]
    _require(
        type(ref) is str and 0 < len(ref) <= 512 and all(ord(c) >= 32 for c in ref),
        "collection_decision_ref",
    )
    start, end = _utc(plan["startsAt"]), _utc(plan["expiresAt"])
    _require(type(now) is datetime and now.tzinfo is not None, "collection_aware_now")
    _require(
        start <= now < end and timedelta(0) < end - start <= timedelta(hours=1), "collection_window"
    )
    for key, maximum in (("timeoutSeconds", 60), ("maxResponseBytes", 262_144)):
        _require(type(plan[key]) is int and 1 <= plan[key] <= maximum, "collection_limits")
    try:
        address = _address(plan["endpointAddress"])
    except Exception:
        raise CollectionError("collection_public_numeric_address") from None
    requests = plan["requests"]
    _require(
        type(requests) is list and 1 <= len(requests) <= MAX_REQUESTS, "collection_request_budget"
    )
    paths = []
    for item in requests:
        item: Any = item
        _keys(item, {"scope", "target"}, "collection_request_fields")
        try:
            path = endpoint_for(item["scope"], item["target"])
        except Exception:
            raise CollectionError("collection_safe_scope_unavailable") from None
        _require(
            type(path) is str
            and path.startswith("/client/v4/")
            and re.fullmatch(r"[A-Za-z0-9_/?=&.,-]+", path) is not None
            and ".." not in path
            and path not in paths,
            "collection_exact_target",
        )
        paths.append(path)
    return address, end, paths


def collect(
    plan,
    expected_plan_sha256,
    consent,
    credential,
    output_path,
    journal_path,
    *,
    now=_now,
    clock=time.monotonic,
    transport=None,
) -> dict[str, Any]:
    """Execute each reviewed safe GET once, retaining only closed projections.

    Existing output OR journal refuses before credential delivery. Exclusive empty
    output and durable intent journal remain on failure as no-replay tombstones.
    Separate consent is supplied by the operator; a truthy JSON value by itself is
    no authentication or permission. No function in this module grants access.
    """
    # Freeze untrusted mutable input before validation/callbacks.
    try:
        plan, consent = _json(canonical(plan)), _json(canonical(consent))
    except Exception:
        raise CollectionError("collection_inputs_invalid") from None
    address, end, paths = _prepare(plan, expected_plan_sha256, consent, now())
    _require(callable(credential), "collection_credential_delivery_required")
    output, journal = Path(output_path), Path(journal_path)
    _require(
        type(plan["outputPath"]) is str
        and type(plan["journalPath"]) is str
        and Path(plan["outputPath"]).is_absolute()
        and Path(plan["journalPath"]).is_absolute()
        and str(output.resolve()) == plan["outputPath"]
        and str(journal.resolve()) == plan["journalPath"],
        "collection_sink_binding",
    )
    _require(output.resolve() != journal.resolve(), "collection_distinct_sinks")
    _require(not output.exists() and not journal.exists(), "collection_sink_exists")
    started = clock()
    _require(type(started) in (int, float) and math.isfinite(started), "collection_clock")
    deadline = started + (end - now()).total_seconds()
    captured_start = now().astimezone(UTC).isoformat().replace("+00:00", "Z")
    collected = []

    def guard():
        current = clock()
        _require(
            type(current) in (int, float)
            and math.isfinite(current)
            and started <= current < deadline
            and now() < end,
            "collection_deadline",
        )
        _require(plan["sourceSha256"] == source_sha256(), "collection_source_changed")

    try:
        with output.open("xb") as out, journal.open("xb") as log:

            def record(state, ordinal):
                log.write(
                    canonical(
                        {
                            "runId": plan["runId"],
                            "planSha256": expected_plan_sha256,
                            "state": state,
                            "ordinal": ordinal,
                        }
                    )
                )
                log.flush()
                os.fsync(log.fileno())

            record("opened", 0)
            try:
                guard()
                token = credential()
                _require(
                    type(token) is str
                    and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) is not None,
                    "collection_credential_invalid",
                )
                _require(
                    hashlib.sha256(token.encode("ascii")).hexdigest() == plan["credentialBinding"],
                    "collection_credential_mismatch",
                )
                for ordinal, (item, path) in enumerate(
                    zip(plan["requests"], paths, strict=True), 1
                ):
                    guard()
                    headers = {
                        "Host": "api.cloudflare.com",
                        "Connection": "close",
                        "Content-Length": "0",
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                        "Authorization": "Bearer " + token,
                    }
                    wire = (
                        f"GET {path} HTTP/1.1\r\n"
                        + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                        + "\r\n"
                    ).encode("ascii")
                    request = Request(
                        "https://api.cloudflare.com" + path,
                        headers,
                        min(plan["timeoutSeconds"], deadline - clock()),
                        plan["maxResponseBytes"] + 65_536,
                        min(deadline, clock() + plan["timeoutSeconds"]),
                        wire,
                    )
                    record("intent", ordinal)
                    guard()
                    response = (
                        _pinned_https(request, address, clock, guard)
                        if transport is None
                        else transport(request)
                    )
                    guard()
                    _require(isinstance(response, Response), "collection_response_type")
                    _require(
                        response.status == 200
                        and type(response.body) is bytes
                        and len(response.body) <= plan["maxResponseBytes"],
                        "collection_response_refused",
                    )
                    response_headers = response.headers
                    _require(
                        type(response_headers) is dict
                        and all(
                            type(k) is str and type(v) is str for k, v in response_headers.items()
                        ),
                        "collection_headers",
                    )
                    normalized = {k.lower(): v for k, v in response_headers.items()}
                    _require(
                        len(normalized) == len(response_headers)
                        and "location" not in normalized
                        and normalized.get("content-encoding", "identity").lower() == "identity"
                        and normalized.get("content-type", "").split(";", 1)[0].strip().lower()
                        == "application/json",
                        "collection_response_metadata",
                    )
                    payload = _json(response.body)
                    projected = project_metadata(item["scope"], payload, item["target"])
                    # Raw body is never retained or included in diagnostic output.
                    del payload, response
                    collected.append(
                        {
                            "scope": item["scope"],
                            "target": item["target"],
                            "capturedAt": now().astimezone(UTC).isoformat().replace("+00:00", "Z"),
                            "projectionSha256": digest(projected),
                            "metadata": projected,
                        }
                    )
                    record("projected", ordinal)
                guard()
                result = {
                    "schemaVersion": 1,
                    "kind": "temporary_composition_metadata_result",
                    "runId": plan["runId"],
                    "planSha256": expected_plan_sha256,
                    "sourceSha256": plan["sourceSha256"],
                    "collectionStartedAt": captured_start,
                    "collectionFinishedAt": now()
                    .astimezone(UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "completeBaseline": False,
                    "requests": len(paths),
                    "projections": collected,
                }
                out.write(canonical(result))
                out.flush()
                os.fsync(out.fileno())
                record("complete", len(paths))
                return result
            except Exception:
                record("aborted_no_replay", len(collected))
                raise CollectionError("collection_aborted_no_replay") from None
    except CollectionError:
        raise
    except Exception:
        raise CollectionError("collection_sink_failure_no_replay") from None


def _read_private_json(path):
    with Path(path).open("rb") as handle:
        data = handle.read(65_537)
    _require(len(data) <= 65_536, "collection_input_limit")
    return _json(data)


def main(argv=None) -> int:
    """Explicit operator entry point; never prints paths, targets or credentials.

    Token-file custody, ACLs, effective grants and genuine human consent require
    independent operator verification before invoking this command. A plan or
    consent file created by this program would not establish any of those facts.
    No token verification request, discovery, refresh or revocation is performed.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--consent", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--journal", required=True)
    args = parser.parse_args(argv)
    try:
        plan = _read_private_json(args.plan)
        consent = _read_private_json(args.consent)

        # Do not resolve/stat/open the token file during pre-credential checks.
        def credential():
            with Path(args.token_file).open("rb") as handle:
                raw = handle.read(4_097)
            _require(len(raw) <= 4_096, "collection_credential_limit")
            try:
                return raw.decode("ascii")
            except UnicodeError:
                raise CollectionError("collection_credential_invalid") from None

        collect(plan, args.expected_plan_sha256, consent, credential, args.output, args.journal)
    except Exception:
        print("collection_refused_or_aborted_no_replay")
        return 1
    print("collection_complete_partial_metadata_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
