"""Finite fresh synthetic D1 qualification; default invocation has no authority.

Private owner approval is required for the exact packet, effective D1 Write grant,
credential, numeric endpoint and caller window. Provider token expiry is recorded
separately and is never shortened by this caller's twenty-minute deadline.
No Workers, existing database IDs, resource lookup, retries or resumed cleanup.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import subprocess
import time
from contextlib import ExitStack
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

EVIDENCE_SOURCE_FILES = ("hosted_publisher_execution.py", "hosted_publisher_operator_plan.py")
MAX_REQUESTS = 26
MAX_EVIDENCE_BODY_BYTES = 262144
MAX_EVIDENCE_RAW_BYTES = 7536640
MAX_EVIDENCE_FILE_BYTES = 11 * 1024 * 1024
SEED_SQL = (
    "CREATE TABLE probe AS SELECT column1 AS v FROM (VALUES(NULL),"
    "(-9223372036854775808),(9223372036854775807),(''),"
    "(CAST(X'610062F09F8C8A' AS TEXT)),(X'0001FF'))"
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
    for name in EVIDENCE_SOURCE_FILES:
        result[name] = hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    return result


def runtime_commit(root=None):
    """Bind the actual checkout revision, independently of source byte pins."""
    root = (root if root is not None else Path(__file__).resolve().parents[1]).resolve(strict=True)
    try:
        lines = subprocess.run(
            ["git", "rev-parse", "--show-toplevel", "HEAD"],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        ).stdout.splitlines()
    except OSError, subprocess.SubprocessError:
        raise QualificationError("qualification_runtime_commit") from None
    require(
        len(lines) == 2
        and Path(lines[0]).resolve(strict=True) == root
        and re.fullmatch(r"[a-f0-9]{40}", lines[1]) is not None,
        "qualification_runtime_commit",
    )
    return lines[1]


def profile_context(packet):
    """Selection is explicit; reviewed input is never inferred from a census."""
    if "profile" not in packet:
        return {}
    from scripts.private_d1_snapshot_profile import PROFILE, validate_manifest

    require(packet["profile"] == PROFILE, "qualification_profile")
    manifest = packet.get("profileManifest")
    require(type(manifest) is dict, "qualification_profile_manifest")
    validate_manifest(manifest, manifest.get("schema"), manifest.get("tableList"))
    require(packet.get("runtimeCommit") == runtime_commit(), "qualification_runtime_commit")
    return {key: packet[key] for key in ("profile", "profileManifest", "runtimeCommit")}


class _ResponseEvidence:
    """Explicit private diagnostic sink; no headers, request bodies or exception text."""

    def __init__(self, path, packet, stack):
        from scripts.hosted_publisher_execution import _assert_private
        from scripts.hosted_publisher_operator_plan import _refuse_links

        self.path = Path(path)
        require(
            self.path.is_absolute()
            and str(self.path.resolve()) == str(self.path)
            and self.path
            not in {
                Path(packet[key]) for key in ("journalPath", "outputPath", "readerJournalPath")
            },
            "qualification_evidence_path",
        )
        _refuse_links(self.path)
        _assert_private(self.path.parent, directory=True)
        self.handle = stack.enter_context(self.path.open("xb"))
        _assert_private(self.path)
        self.identity = os.fstat(self.handle.fileno())
        current = self.path.stat()
        require(
            (current.st_dev, current.st_ino) == (self.identity.st_dev, self.identity.st_ino)
            and self.identity.st_size == 0,
            "qualification_evidence_changed",
        )
        self.records = self.raw_bytes = self.file_bytes = 0

    def capture(self, response, *, ordinal, phase, token, packet_sha256):
        from scripts.hosted_publisher_execution import _assert_private

        _assert_private(self.path)
        current = self.path.stat()
        opened = os.fstat(self.handle.fileno())
        require(
            (current.st_dev, current.st_ino)
            == (opened.st_dev, opened.st_ino)
            == (self.identity.st_dev, self.identity.st_ino)
            and opened.st_size == self.file_bytes,
            "qualification_evidence_changed",
        )
        require(
            isinstance(response, Response)
            and type(response.status) is int
            and 100 <= response.status <= 599
            and type(response.body) is bytes
            and len(response.body) <= MAX_EVIDENCE_BODY_BYTES,
            "qualification_evidence_response_bound",
        )
        body = response.body
        # Normalize JSON solely for echo refusal, before semantic acceptance.
        # Non-JSON errors remain capturable unless Unicode escape spelling is
        # ambiguous. Residual nested escapes refuse rather than add a new codec.
        normalized = b""
        try:
            normalized = canonical(_json(body))
        except Exception:
            require(b"\\u" not in body.lower(), "qualification_evidence_secret_echo")
        require(
            len(normalized) <= 6 * MAX_EVIDENCE_BODY_BYTES + 2
            and b"\\\\u" not in normalized.lower()
            and all(
                token.encode("ascii") not in candidate
                and not any(
                    marker in candidate.lower()
                    for marker in (b"authorization", b"set-cookie", b"cookie", b"bearer")
                )
                for candidate in (body, normalized)
            ),
            "qualification_evidence_secret_echo",
        )
        record = canonical(
            {
                "schemaVersion": 1,
                "packetSha256": packet_sha256,
                "ordinal": ordinal,
                "phase": phase,
                "status": response.status,
                "bodyBytes": len(body),
                "bodyBase64": base64.b64encode(body).decode("ascii"),
            }
        )
        require(
            self.records < MAX_REQUESTS
            and self.raw_bytes + len(body) <= MAX_EVIDENCE_RAW_BYTES
            and self.file_bytes + len(record) <= MAX_EVIDENCE_FILE_BYTES,
            "qualification_evidence_aggregate_bound",
        )
        self.handle.write(record)
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.records += 1
        self.raw_bytes += len(body)
        self.file_bytes += len(record)


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
    context = profile_context(packet) if type(packet) is dict else {}
    require(
        type(packet) is dict and set(packet) == keys | context.keys(), "qualification_packet_fields"
    )
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
        and set(consent) == {"approved", "decisionRef", "packetSha256", *context}
        and consent["approved"] is True
        and consent["packetSha256"] == expected
        and type(consent["decisionRef"]) is str
        and 0 < len(consent["decisionRef"]) <= 512
        and all(ord(c) >= 32 for c in consent["decisionRef"]),
        "qualification_owner_approval",
    )
    require(
        all(consent[key] == value for key, value in context.items()),
        "qualification_profile_consent",
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
    evidence_path=None,
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
        context = profile_context(packet)
        reader_context = (
            {key: context[key] for key in ("profile", "profileManifest")} if context else {}
        )
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
            if context:
                require(profile_context(packet) == context, "qualification_profile_changed")

        with ExitStack() as stack:
            # Create/prove the optional exclusive private sink before reading credentials.
            guard()
            evidence = (
                _ResponseEvidence(evidence_path, packet, stack)
                if evidence_path is not None
                else None
            )
            log = stack.enter_context(Path(journal_path).open("xb"))

            def record(state, receipt_sha256=None):
                log.write(
                    canonical(
                        {
                            "state": state,
                            "packetSha256": expected_packet_sha256,
                            "databaseId": database,
                            "ordinal": count,
                            **(
                                {
                                    "profile": context["profile"],
                                    "profileManifestSha256": digest(context["profileManifest"]),
                                    "runtimeCommit": context["runtimeCommit"],
                                }
                                if context
                                else {}
                            ),
                            **(
                                {"qualificationReceiptSha256": receipt_sha256}
                                if receipt_sha256 is not None
                                else {}
                            ),
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
                        else _pinned_https(
                            request, address, clock, dispatch_guard=guard, discard_set_cookie=True
                        )
                    )
                    guard()
                    if evidence is not None:
                        evidence.capture(
                            response,
                            ordinal=count,
                            phase=(
                                "absence"
                                if absence
                                else "sql"
                                if path.endswith("/query")
                                else method.lower()
                            ),
                            token=token,
                            packet_sha256=expected_packet_sha256,
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

                expected_snapshot = codec.collect_snapshot(
                    query, page_size=256, profile_manifest=packet.get("profileManifest")
                )
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
                        **context,
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
                    **reader_context,
                }
                reader_consent = {
                    "approved": True,
                    "decisionRef": consent["decisionRef"],
                    "planSha256": digest(plan),
                    "sourceSha256": plan["sourceSha256"],
                    **{key: plan[key] for key in reader.PINS},
                    **reader_context,
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
                require(
                    actual["plan"] == plan and actual["snapshot"] == expected_snapshot,
                    "qualification_snapshot_mismatch",
                )
                # This is an unsupported typed cell decoder check, never a production claim.
                try:
                    codec._decode_cell("real", None)
                except codec.Refused:
                    pass
                else:
                    raise QualificationError("qualification_negative_failed")
                uncertain = False
                permit.active = False
                record("reader_terminal_equal", receipt if context else None)
                deleted = True
                dispatch("DELETE", base + "/" + database, None)
                record("deleted_known_fresh_database")
                dispatch("GET", base + "/" + database, None, absence=True)
                record("exact_database_not_found_response")
                record("cleanup_unconfirmed_provider_not_found")
                result = {
                    "complete": True,
                    "cleanupVerified": False,
                    "providerNotFoundObserved": True,
                    "productionQualified": False,
                    "syntheticTransport": transport is not None,
                    "requests": count,
                }
                if context:
                    result.update(
                        profileBinding=expected_snapshot["profileBinding"],
                        runtimeCommit=context["runtimeCommit"],
                        applicationStateEqualityVerified=True,
                        wholeProviderContentsEqualityVerified=False,
                        qualificationReceiptSha256=receipt,
                    )
                return result
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
