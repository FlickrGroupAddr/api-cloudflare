"""Finite fresh synthetic D1 qualification; default invocation has no authority.

Private owner approval is required for the exact packet, effective D1 Write grant,
credential, numeric endpoint and caller window. Provider token expiry is recorded
separately and is never shortened by this caller's twenty-minute deadline.
No Workers, existing database IDs, resource lookup, retries or resumed cleanup.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.hosted_publisher_execution_provider import _pinned_https
from scripts.hosted_publisher_finite_client import Request, Response
from scripts.temporary_composition_metadata_collector import (
    _address,
    _json,
    _utc,
    canonical,
    digest,
)

MAX_REQUESTS = 26
SEED_SQL = (
    "CREATE TABLE probe AS SELECT NULL AS v UNION ALL SELECT -9223372036854775808 "
    "UNION ALL SELECT 9223372036854775807 UNION ALL SELECT '' "
    "UNION ALL SELECT CAST(X'610062F09F8C8A' AS TEXT) UNION ALL SELECT X'0001FF'"
)
_PROCESS = object()


class QualificationError(ValueError):
    """Closed failure category; provider diagnostics never escape."""


def require(ok, code):
    if not ok:
        raise QualificationError(code)


def source_sha256():
    from scripts.private_d1_snapshot_reader import source_sha256 as reader_sources

    result = reader_sources()
    result[Path(__file__).name] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


class _FreshDatabasePermit:
    """Ephemeral exact-plan capability. No serialized receipt can reconstruct it."""

    def __init__(self, seal, plan, guard):
        require(seal is _PROCESS, "qualification_permit")
        self._process = os.getpid()
        self._digest = digest(plan)
        self._guard = guard
        self.active = True

    def authorize(self, plan):
        require(
            self.active and self._process == os.getpid() and digest(plan) == self._digest,
            "qualification_permit",
        )
        self._guard()


def _prepare(packet: dict[str, Any], expected, consent, now):
    keys = {
        "schemaVersion",
        "kind",
        "runId",
        "sourceSha256",
        "accountId",
        "endpointAddress",
        "startsAt",
        "expiresAt",
        "providerTokenExpiresAt",
        "credentialBinding",
        "grantEvidenceSha256",
        "privateCustodySha256",
        "journalPath",
        "outputPath",
        "readerJournalPath",
    }
    require(type(packet) is dict and set(packet) == keys, "qualification_packet_fields")
    require(
        type(packet["schemaVersion"]) is int
        and packet["schemaVersion"] == 1
        and packet["kind"] == "fresh_synthetic_d1_qualification",
        "qualification_packet_kind",
    )
    require(
        digest(packet) == expected and re.fullmatch(r"[a-f0-9]{64}", expected) is not None,
        "qualification_packet_pin",
    )
    require(packet["sourceSha256"] == source_sha256(), "qualification_source_pin")
    for key, pattern in (
        ("accountId", r"[a-f0-9]{32}"),
        ("runId", r"[a-f0-9]{32}"),
        ("credentialBinding", r"[a-f0-9]{64}"),
        ("grantEvidenceSha256", r"[a-f0-9]{64}"),
        ("privateCustodySha256", r"[a-f0-9]{64}"),
    ):
        require(
            type(packet[key]) is str and re.fullmatch(pattern, packet[key]) is not None,
            "qualification_binding",
        )
    require(
        type(consent) is dict
        and set(consent) == {"approved", "decisionRef", "packetSha256"}
        and consent["approved"] is True
        and consent["packetSha256"] == expected
        and type(consent["decisionRef"]) is str
        and 0 < len(consent["decisionRef"]) <= 512
        and all(ord(c) >= 32 for c in consent["decisionRef"]),
        "qualification_owner_approval",
    )
    start, end = _utc(packet["startsAt"]), _utc(packet["expiresAt"])
    require(
        start <= now < end and timedelta(0) < end - start <= timedelta(minutes=20),
        "qualification_window",
    )
    require(_utc(packet["providerTokenExpiresAt"]) >= end, "qualification_provider_expiry")
    paths = [Path(packet[key]) for key in ("journalPath", "outputPath", "readerJournalPath")]
    require(
        all(p.is_absolute() and str(p.resolve()) == str(p) and not p.exists() for p in paths)
        and len(set(paths)) == 3,
        "qualification_private_sinks",
    )
    return _address(packet["endpointAddress"]), end


def qualify(
    packet,
    expected_packet_sha256,
    consent,
    credential,
    journal_path,
    *,
    now=lambda: datetime.now(UTC),
    clock=time.monotonic,
    transport=None,
):
    """Run once. Injected transport is synthetic test code, never qualification.

    At most 26 requests: create, seed, <=11 census/capture SQL, <=11 exact
    reader SQL, delete, exact-ID absence GET. Two tables and 256 rows/table maximum. Any uncertainty
    retains the acknowledged UUID in the private journal and prevents deletion.
    """
    from scripts import private_d1_snapshot_codec as codec
    from scripts import private_d1_snapshot_reader as reader

    try:
        require(len(canonical(packet)) <= 65536, "qualification_packet_limit")
        packet, consent = _json(canonical(packet)), _json(canonical(consent))
        address, end = _prepare(packet, expected_packet_sha256, consent, now())
        require(
            str(Path(journal_path).resolve()) == packet["journalPath"] and callable(credential),
            "qualification_inputs",
        )
        started = clock()
        deadline = started + (end - now()).total_seconds()
        count, database, uncertain, permit = 0, None, False, None
        deleted = False

        def guard():
            require(
                started <= clock() < deadline
                and now() < end
                and source_sha256() == packet["sourceSha256"],
                "qualification_fence",
            )

        with Path(journal_path).open("xb") as log:

            def record(state):
                log.write(
                    canonical(
                        {
                            "state": state,
                            "packetSha256": expected_packet_sha256,
                            "databaseId": database,
                            "ordinal": count,
                        }
                    )
                )
                log.flush()
                os.fsync(log.fileno())

            record("opened_no_replay")
            try:
                guard()
                token: Any = credential()
                require(
                    type(token) is str
                    and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) is not None
                    and hashlib.sha256(token.encode("ascii")).hexdigest()
                    == packet["credentialBinding"],
                    "qualification_credential",
                )
                base = "/client/v4/accounts/" + packet["accountId"] + "/d1/database"

                def dispatch(method, path, body, *, absence=False):
                    nonlocal count, uncertain
                    guard()
                    require(not uncertain and count < MAX_REQUESTS, "qualification_budget")
                    raw = canonical(body) if body is not None else b""
                    headers = {
                        "Host": "api.cloudflare.com",
                        "Connection": "close",
                        "Content-Length": str(len(raw)),
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                        "Authorization": "Bearer " + token,
                    }
                    wire = (
                        f"{method} {path} HTTP/1.1\r\n"
                        + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                        + "\r\n"
                    ).encode() + raw
                    count += 1
                    uncertain = True
                    record("dispatch_intent")
                    request = Request(
                        "https://api.cloudflare.com" + path,
                        headers,
                        min(30, deadline - clock()),
                        327680,
                        min(deadline, clock() + 30),
                        wire,
                    )
                    response = (
                        transport(request)
                        if transport is not None
                        else _pinned_https(request, address, clock, dispatch_guard=guard)
                    )
                    guard()
                    require(
                        isinstance(response, Response)
                        and response.status == (404 if absence else 200)
                        and len(response.body) <= 262144,
                        "qualification_response",
                    )
                    headers_lower = {k.lower(): v for k, v in response.headers.items()}
                    require(
                        len(headers_lower) == len(response.headers)
                        and "location" not in headers_lower
                        and headers_lower.get("content-encoding", "identity") == "identity"
                        and headers_lower.get("content-type", "").split(";")[0]
                        == "application/json",
                        "qualification_response_metadata",
                    )
                    payload = _json(response.body)
                    require(
                        type(payload) is dict
                        and set(payload) == {"success", "errors", "messages", "result"}
                        and payload["messages"] == [],
                        "qualification_terminal_result",
                    )
                    if absence:
                        # A provider not-found response is evidence about this exact
                        # request, never a claim of physical erasure or token revocation.
                        require(
                            payload["success"] is False
                            and payload["result"] is None
                            and type(payload["errors"]) is list
                            and len(payload["errors"]) == 1
                            and type(payload["errors"][0]) is dict
                            and payload["errors"][0].get("code") == 7404,
                            "qualification_absence_unconfirmed",
                        )
                    else:
                        require(
                            payload["success"] is True and payload["errors"] == [],
                            "qualification_terminal_result",
                        )
                    # SQL must also be positively terminal before uncertainty clears.
                    if path.endswith("/query"):
                        reader._rows(response, 262144)
                    uncertain = False
                    record("dispatch_terminal")
                    return response, payload["result"]

                name = "fga-snapshot-qualification-" + packet["runId"]
                _, created = dispatch(
                    "POST", base, {"name": name, "read_replication": {"mode": "disabled"}}
                )
                require(
                    type(created) is dict
                    and created.get("name") == name
                    and type(created.get("uuid")) is str
                    and re.fullmatch(
                        r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", created["uuid"]
                    )
                    is not None
                    and created["uuid"] != "00000000-0000-0000-0000-000000000000",
                    "qualification_create_ack",
                )
                database = created["uuid"]
                record("fresh_database_acknowledged")
                query_path = base + "/" + database + "/query"
                dispatch("POST", query_path, {"sql": SEED_SQL, "params": []})
                queries = []

                def query(sql):
                    require(len(queries) < 11, "qualification_census_budget")
                    response, _ = dispatch("POST", query_path, {"sql": sql, "params": []})
                    rows = reader._rows(response, 262144)
                    if sql == codec.SCHEMA_SQL:
                        require(
                            sum(row.get("type") == "table" for row in rows) <= 2,
                            "qualification_table_bound",
                        )
                    if " AS row_count " in sql:
                        require(codec.decode_count(rows) <= 256, "qualification_row_bound")
                    queries.append(sql)
                    return rows

                expected_snapshot = codec.collect_snapshot(query, page_size=256)
                expected_cells = [
                    ["null", None],
                    ["integer", -(2**63)],
                    ["integer", 2**63 - 1],
                    ["text", ""],
                    ["text", "a\x00b\U0001f30a"],
                    ["blob", "0001ff"],
                ]
                require(
                    sorted(expected_snapshot["tables"]["probe"]["rows"], key=canonical)
                    == sorted([[cell] for cell in expected_cells], key=canonical),
                    "qualification_fixture_roundtrip",
                )
                receipt = digest(
                    {
                        "freshDatabase": database,
                        "seed": SEED_SQL,
                        "snapshot": expected_snapshot,
                        "packet": expected_packet_sha256,
                    }
                )
                plan = {
                    "schemaVersion": 1,
                    "kind": "private_d1_snapshot_plan",
                    "runId": packet["runId"],
                    "sourceSha256": reader.source_sha256(),
                    "accountId": packet["accountId"],
                    "databaseId": database,
                    "endpointAddress": packet["endpointAddress"],
                    "startsAt": packet["startsAt"],
                    "expiresAt": packet["expiresAt"],
                    "timeoutSeconds": 30,
                    "maxResponseBytes": 262144,
                    "maxTotalBytes": 2621440,
                    "pageSize": 256,
                    "queries": queries,
                    "outputPath": packet["outputPath"],
                    "journalPath": packet["readerJournalPath"],
                    "artifactSha256": digest(packet["sourceSha256"]),
                    "barrierReceiptSha256": receipt,
                    "qualificationEvidenceSha256": receipt,
                    "grantEvidenceSha256": packet["grantEvidenceSha256"],
                    "credentialBinding": packet["credentialBinding"],
                }
                reader_consent = {
                    "approved": True,
                    "decisionRef": consent["decisionRef"],
                    "planSha256": digest(plan),
                    "sourceSha256": plan["sourceSha256"],
                    **{key: plan[key] for key in reader.PINS},
                }
                permit = _FreshDatabasePermit(_PROCESS, plan, guard)
                uncertain = True  # Reader failure might have dispatched SQL: retain, never delete.
                record("reader_entered")
                if transport is None:
                    reader.collect_isolated(
                        plan,
                        digest(plan),
                        reader_consent,
                        lambda: token,
                        plan["outputPath"],
                        plan["journalPath"],
                        permit=permit,
                        now=now,
                        clock=clock,
                    )
                else:
                    reader.collect(
                        plan,
                        digest(plan),
                        reader_consent,
                        lambda: token,
                        plan["outputPath"],
                        plan["journalPath"],
                        now=now,
                        clock=clock,
                        transport=transport,
                    )
                count += len(queries)
                actual = _json(Path(plan["outputPath"]).read_bytes())
                require(actual["snapshot"] == expected_snapshot, "qualification_snapshot_mismatch")
                # This is an unsupported typed cell decoder check, never a production claim.
                try:
                    codec._decode_cell("real", None)
                except codec.Refused:
                    pass
                else:
                    raise QualificationError("qualification_negative_failed")
                uncertain = False
                permit.active = False
                record("reader_terminal_equal")
                deleted = True
                dispatch("DELETE", base + "/" + database, None)
                record("deleted_known_fresh_database")
                dispatch("GET", base + "/" + database, None, absence=True)
                record("exact_database_not_found_response")
                record("cleanup_unconfirmed_provider_not_found")
                return {
                    "complete": True,
                    "cleanupVerified": False,
                    "providerNotFoundObserved": True,
                    "productionQualified": False,
                    "syntheticTransport": transport is not None,
                    "requests": count,
                }
            except Exception:
                if permit is not None:
                    permit.active = False
                record("cleanup_unconfirmed_no_replay" if deleted else "retained_no_replay")
                raise QualificationError("qualification_retained_no_replay") from None
    except QualificationError:
        raise
    except Exception:
        raise QualificationError("qualification_refused_or_retained_no_replay") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packet", "expected-packet-sha256", "consent", "token-file", "journal"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:

        def read(path, limit):
            with Path(path).open("rb") as handle:
                raw = handle.read(limit + 1)
            require(len(raw) <= limit, "qualification_input_limit")
            return raw

        packet, consent = _json(read(args.packet, 65536)), _json(read(args.consent, 65536))
        qualify(
            packet,
            args.expected_packet_sha256,
            consent,
            lambda: read(args.token_file, 4096).decode("ascii"),
            args.journal,
        )
    except Exception:
        print("qualification_refused_or_retained_no_replay")
        return 1
    print("qualification_recipe_complete_cleanup_unconfirmed_production_unqualified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
