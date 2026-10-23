"""Private complete-state D1 reader preparation; production dispatch is unavailable.

Trusted synthetic transports and newly created isolated synthetic databases execute.
Neither JSON
consent nor evidence hashes qualify the exact restored artifact's all-writer
barrier, coherent snapshot or lossless codec. A later reviewed independent gate
and genuine later owner approval are mandatory before enabling provider dispatch.
Rows and query text go only to the explicitly approved private sink, never returns.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from scripts.hosted_publisher_finite_client import Request, Response
from scripts.temporary_composition_metadata_collector import (
    _address,
    _json,
    _utc,
    canonical,
    digest,
)

MAX_QUERIES = 2048
MAX_TOTAL_BYTES = 16 * 1024 * 1024
# Local source admission bounds, not actual run/transport/campaign allowances.
# Only an explicit subsequently validated ADR0065 context selects the larger
# finite source domain. Historical/default profiles keep their prior bounds.
MAX_INPUT_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
NO_REAL_MAX_INPUT_BYTES = 2 * 1024 * 1024
NO_REAL_MAX_RESPONSE_BYTES = 512 * 1024
SOURCE_FILES = (
    "private_d1_snapshot_reader.py",
    "private_d1_snapshot_codec.py",
    "private_d1_snapshot_profile.py",
    "private_no_real_guards.py",
    "fixed_origin_preservation.py",
    "fixed_origin_restore.py",
    "qualify_private_d1_snapshot.py",
    "temporary_composition_metadata_collector.py",
    "temporary_composition_metadata_projection.py",
    "hosted_publisher_execution_provider.py",
    "hosted_publisher_finite_client.py",
    "hosted_publisher_provider.py",
    "hosted_publisher_worker_deployment.py",
    "hosted_publisher_worker_identity.py",
)
PINS = (
    "artifactSha256",
    "barrierReceiptSha256",
    "grantEvidenceSha256",
    "qualificationEvidenceSha256",
    "credentialBinding",
)


class SnapshotError(ValueError):
    """Static refusal category; never includes private data or provider errors."""


def require(ok, category):
    if not ok:
        raise SnapshotError(category)


def source_sha256():
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def _keys(value, keys):
    require(type(value) is dict and set(value) == set(keys), "snapshot_fields")


def _now():
    return datetime.now(UTC)


def _hash(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _input_bound(value):
    from scripts.private_d1_snapshot_profile import NO_REAL_PROFILE

    return (
        NO_REAL_MAX_INPUT_BYTES
        if type(value) is dict and value.get("profile") == NO_REAL_PROFILE
        else MAX_INPUT_BYTES
    )


def _bounded_inputs(plan, consent):
    bound = _input_bound(plan)
    encoded_plan, encoded_consent = canonical(plan), canonical(consent)
    require(max(len(encoded_plan), len(encoded_consent)) <= bound, "snapshot_input_limit")
    return _json(encoded_plan), _json(encoded_consent)


def _prepare(plan, expected, consent, now):
    require(_hash(expected) and digest(plan) == expected, "snapshot_plan_pin")
    profile = plan.get("profile") if type(plan) is dict else None
    profile_keys = {"profile", "profileManifest"} if profile is not None else set()
    if profile is not None:
        from scripts.private_d1_snapshot_profile import NO_REAL_PROFILE, PROFILE, validate_manifest

        require(
            profile in (PROFILE, NO_REAL_PROFILE) and "profileManifest" in plan, "snapshot_profile"
        )
        manifest = plan["profileManifest"]
        require(type(manifest) is dict and manifest.get("profile") == profile, "snapshot_profile")
        validate_manifest(manifest, manifest.get("schema"), manifest.get("tableList"))
    _keys(
        plan,
        {
            "schemaVersion",
            "kind",
            "runId",
            "sourceSha256",
            "accountId",
            "databaseId",
            "endpointAddress",
            "startsAt",
            "expiresAt",
            "timeoutSeconds",
            "maxResponseBytes",
            "maxTotalBytes",
            "pageSize",
            "queries",
            "outputPath",
            "journalPath",
            *PINS,
            *profile_keys,
        },
    )
    require(
        type(plan["schemaVersion"]) is int
        and plan["schemaVersion"] == 1
        and plan["kind"] == "private_d1_snapshot_plan",
        "snapshot_schema",
    )
    require(
        type(plan["runId"]) is str and re.fullmatch(r"[a-f0-9]{32}", plan["runId"]) is not None,
        "snapshot_run",
    )
    require(plan["sourceSha256"] == source_sha256(), "snapshot_source_pin")
    require(all(_hash(plan[key]) for key in PINS), "snapshot_evidence_pins")
    require(
        type(plan["accountId"]) is str
        and re.fullmatch(r"[a-f0-9]{32}", plan["accountId"]) is not None,
        "snapshot_account",
    )
    require(
        type(plan["databaseId"]) is str
        and re.fullmatch(
            r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", plan["databaseId"]
        )
        is not None,
        "snapshot_database",
    )
    _keys(consent, {"approved", "decisionRef", "planSha256", "sourceSha256", *PINS, *profile_keys})
    require(
        consent["approved"] is True
        and consent["planSha256"] == expected
        and consent["sourceSha256"] == plan["sourceSha256"]
        and all(consent[key] == plan[key] for key in PINS),
        "snapshot_consent",
    )
    if profile is not None:
        require(all(consent[key] == plan[key] for key in profile_keys), "snapshot_profile_consent")
    ref = consent["decisionRef"]
    require(
        type(ref) is str and 0 < len(ref) <= 512 and all(ord(c) >= 32 for c in ref),
        "snapshot_decision",
    )
    start, end = _utc(plan["startsAt"]), _utc(plan["expiresAt"])
    require(
        type(now) is datetime
        and now.tzinfo is not None
        and start <= now < end
        and timedelta(0) < end - start <= timedelta(minutes=20),
        "snapshot_window",
    )
    from scripts.private_d1_snapshot_profile import NO_REAL_PROFILE

    response_bound = (
        NO_REAL_MAX_RESPONSE_BYTES if profile == NO_REAL_PROFILE else MAX_RESPONSE_BYTES
    )
    for key, cap in (
        ("timeoutSeconds", 60),
        ("maxResponseBytes", response_bound),
        ("maxTotalBytes", MAX_TOTAL_BYTES),
        ("pageSize", 256),
    ):
        require(type(plan[key]) is int and 1 <= plan[key] <= cap, "snapshot_limits")
    queries = plan["queries"]
    require(
        type(queries) is list
        and 1 <= len(queries) <= MAX_QUERIES
        and all(type(q) is str and 0 < len(q.encode()) <= 32768 for q in queries),
        "snapshot_query_plan",
    )
    from scripts.private_d1_snapshot_codec import ENCODING_SQL, SCHEMA_SQL, TABLE_LIST_SQL

    require(
        len(queries) >= 3 and queries[:3] == [SCHEMA_SQL, TABLE_LIST_SQL, ENCODING_SQL],
        "snapshot_query_prefix",
    )
    address = _address(plan["endpointAddress"])
    return address, end


def _rows(response, limit):
    require(
        isinstance(response, Response)
        and response.status == 200
        and type(response.body) is bytes
        and len(response.body) <= limit,
        "snapshot_response",
    )
    headers = response.headers
    require(
        type(headers) is dict
        and all(type(k) is str and type(v) is str for k, v in headers.items()),
        "snapshot_headers",
    )
    normalized: dict[str, str] = {k.lower(): v for k, v in cast(dict[str, str], headers).items()}
    require(
        len(normalized) == len(headers)
        and "location" not in normalized
        and normalized.get("content-encoding", "identity").lower() == "identity"
        and normalized.get("content-type", "").split(";", 1)[0].strip().lower()
        == "application/json",
        "snapshot_response_metadata",
    )
    payload = _json(response.body)
    _keys(payload, {"success", "errors", "messages", "result"})
    require(
        payload["success"] is True
        and payload["errors"] == []
        and payload["messages"] == []
        and type(payload["result"]) is list
        and len(payload["result"]) == 1,
        "snapshot_provider_result",
    )
    result = payload["result"][0]
    _keys(result, {"success", "results", "meta"})
    require(
        result["success"] is True
        and type(result["results"]) is list
        and all(type(row) is dict for row in result["results"])
        and type(result["meta"]) is dict,
        "snapshot_query_result",
    )
    # Unknown completion/pagination signals cannot silently become completeness.
    require(
        not any(
            key in result["meta"]
            for key in ("next", "next_page", "cursor", "truncated", "has_more")
        ),
        "snapshot_incomplete_response",
    )
    return result["results"]


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
):
    """Finite orchestration; returns a closed summary containing no rows.

    maxResponseBytes and maxTotalBytes are per-response and aggregate decrypted
    HTTP wire allowances, including
    response headers, body and framing. Every request ceiling shrinks to its
    remaining allowance; missing/invalid transport accounting refuses.
    Exclusive files are no-replay tombstones even after an uncertain dispatch.
    Private directory ACLs/custody require independent operator qualification.
    Injected transport and clocks are trusted test code, never security evidence.
    """
    try:
        plan, consent = _bounded_inputs(plan, consent)
        _address_value, end = _prepare(plan, expected_plan_sha256, consent, now())
        # No arbitrary boolean or self-authored evidence file can enable networking.
        require(callable(transport), "snapshot_external_qualification_unavailable")
        require(callable(credential), "snapshot_credential_delivery")
        output, journal = Path(output_path), Path(journal_path)
        require(
            all(
                type(plan[key]) is str and Path(plan[key]).is_absolute()
                for key in ("outputPath", "journalPath")
            ),
            "snapshot_sink_binding",
        )
        require(
            str(output.resolve()) == plan["outputPath"]
            and str(journal.resolve()) == plan["journalPath"]
            and output.resolve() != journal.resolve(),
            "snapshot_sink_binding",
        )
        require(not output.exists() and not journal.exists(), "snapshot_sink_exists")
        started = clock()
        require(type(started) in (float, int) and math.isfinite(started), "snapshot_clock")
        deadline = started + (end - now()).total_seconds()
        ordinal, total_bytes = 0, 0

        def guard():
            current = clock()
            require(
                type(current) in (float, int)
                and math.isfinite(current)
                and started <= current < deadline
                and _utc(plan["startsAt"]) <= now() < end,
                "snapshot_deadline",
            )
            require(source_sha256() == plan["sourceSha256"], "snapshot_source_changed")
            if isinstance(transport, _IsolatedTransport):
                transport.authorize()

        with output.open("xb") as out, journal.open("xb") as log:

            def record(state):
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

            record("opened")
            try:
                guard()
                token = credential()
                require(
                    type(token) is str
                    and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) is not None
                    and hashlib.sha256(token.encode("ascii")).hexdigest()
                    == plan["credentialBinding"],
                    "snapshot_credential",
                )
                path = (
                    "/client/v4/accounts/"
                    + plan["accountId"]
                    + "/d1/database/"
                    + plan["databaseId"]
                    + "/query"
                )

                def query(sql):
                    nonlocal ordinal, total_bytes
                    guard()
                    require(
                        ordinal < len(plan["queries"]) and sql == plan["queries"][ordinal],
                        "snapshot_query_plan_mismatch",
                    )
                    remaining_bytes = plan["maxTotalBytes"] - total_bytes
                    require(remaining_bytes > 0, "snapshot_total_bytes")
                    response_cap = min(plan["maxResponseBytes"], remaining_bytes)
                    body = canonical({"sql": sql, "params": []})
                    headers = {
                        "Host": "api.cloudflare.com",
                        "Connection": "close",
                        "Content-Length": str(len(body)),
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                        "Authorization": "Bearer " + token,
                    }
                    wire = (
                        f"POST {path} HTTP/1.1\r\n"
                        + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                        + "\r\n"
                    ).encode("ascii") + body
                    ordinal += 1
                    record("intent")
                    guard()
                    request = Request(
                        "https://api.cloudflare.com" + path,
                        headers,
                        min(plan["timeoutSeconds"], deadline - clock()),
                        response_cap,
                        min(deadline, clock() + plan["timeoutSeconds"]),
                        wire,
                    )
                    response = cast(Any, transport)(request)
                    guard()
                    rows = _rows(response, min(plan["maxResponseBytes"], remaining_bytes))
                    require(
                        type(response.wire_bytes) is int
                        and len(response.body) <= response.wire_bytes <= response_cap,
                        "snapshot_wire_accounting",
                    )
                    total_bytes += response.wire_bytes
                    record("received")
                    return rows

                from scripts.private_d1_snapshot_codec import collect_snapshot

                snapshot = collect_snapshot(
                    query,
                    page_size=plan["pageSize"],
                    profile_manifest=plan.get("profileManifest"),
                )
                require(ordinal == len(plan["queries"]), "snapshot_unused_queries")
                guard()
                encoded = canonical(
                    {
                        "kind": "private_d1_snapshot_result",
                        "mode": (
                            "isolated-new-synthetic-d1"
                            if isinstance(transport, _IsolatedTransport)
                            else "synthetic-transport-only"
                        ),
                        "runId": plan["runId"],
                        "planSha256": expected_plan_sha256,
                        "plan": plan,
                        "observedAt": now().astimezone(UTC).isoformat(),
                        "snapshot": snapshot,
                    }
                )
                require(len(encoded) <= MAX_TOTAL_BYTES, "snapshot_output_limit")
                out.write(encoded)
                out.flush()
                os.fsync(out.fileno())
                guard()
                record("complete")
                summary = {"complete": True, "productionQualified": False, "queries": ordinal}
                if "profile" in plan:
                    summary.update(
                        profileBinding=snapshot["profileBinding"],
                        wholeProviderContentsEqualityVerified=False,
                    )
                return summary
            except Exception:
                record("aborted_no_replay")
                raise SnapshotError("snapshot_aborted_no_replay") from None
    except SnapshotError:
        raise
    except Exception:
        raise SnapshotError("snapshot_refused_or_aborted_no_replay") from None


class _IsolatedTransport:
    """Only a same-process new synthetic database permit selects real HTTPS."""

    def __init__(self, plan, permit, clock):
        from scripts.qualify_private_d1_snapshot import _FreshDatabasePermit

        require(type(permit) is _FreshDatabasePermit, "snapshot_fresh_database_permit")
        self.plan = _json(canonical(plan))
        self.permit, self.clock = permit, clock
        self.address = _address(self.plan["endpointAddress"])
        self.authorize()

    def authorize(self):
        self.permit.authorize(self.plan)

    def __call__(self, request):
        from scripts.hosted_publisher_execution_provider import _pinned_https

        self.authorize()
        # Accepted management-only policy; all permit, wire and deadline gates
        # remain in force. The generic primitive and probe client stay strict.
        return _pinned_https(
            request, self.address, self.clock, self.authorize, discard_set_cookie=True
        )


def collect_isolated(
    plan,
    expected_plan_sha256,
    consent,
    credential,
    output_path,
    journal_path,
    *,
    permit,
    now=_now,
    clock=time.monotonic,
):
    """Use a newly created synthetic database only; never an existing production ID.

    The qualification source owns creation acknowledgement, same-process permit
    lifecycle, fixture SQL and cleanup. No serialized permit or plan flag works.
    Completion qualifies neither production barriers nor production snapshots.
    """
    try:
        frozen, consent = _bounded_inputs(plan, consent)
        _prepare(frozen, expected_plan_sha256, consent, now())
        transport = _IsolatedTransport(frozen, permit, clock)
        return collect(
            frozen,
            expected_plan_sha256,
            consent,
            credential,
            output_path,
            journal_path,
            now=now,
            clock=clock,
            transport=transport,
        )
    except Exception:
        raise SnapshotError("snapshot_isolated_refused_or_aborted_no_replay") from None


def _read_json(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(NO_REAL_MAX_INPUT_BYTES + 1)
    require(len(raw) <= NO_REAL_MAX_INPUT_BYTES, "snapshot_input_limit")
    value = _json(raw)
    require(len(raw) <= _input_bound(value), "snapshot_input_limit")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "expected-plan-sha256", "consent", "token-file", "output", "journal"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        plan, consent = _read_json(args.plan), _read_json(args.consent)

        def credential():
            with Path(args.token_file).open("rb") as handle:
                raw = handle.read(4097)
            require(len(raw) <= 4096, "snapshot_credential_limit")
            return raw.decode("ascii")

        collect(plan, args.expected_plan_sha256, consent, credential, args.output, args.journal)
    except Exception:
        print("snapshot_refused_or_aborted_no_replay")
        return 1
    print("snapshot_private_file_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
