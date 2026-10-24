"""Invented issuance/temp IO and fake ACL/TLS only; no genuine private inputs.

The fake native library supplies invented private metadata. No native DLL is
loaded, socket created, DNS queried, source_entry booted or actual session run.
"""

from __future__ import annotations

import copy
import ctypes
import dataclasses
import hashlib
import io
import json
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts import historical_child_recovery_nullable_v2 as recovery
from scripts import historical_child_recovery_operator_nullable_v2 as operator
from scripts import provision_work_plan_token as issuer
from tests import test_historical_child_recovery as synthetic
from tests import test_provision_work_plan_token as base

ROOT = Path(issuer.__file__).resolve().parents[1]
NOW = datetime(2026, 10, 23, 12, 0, 1, tzinfo=UTC)
SyntheticEvidence = synthetic.SyntheticEvidence
SyntheticWriter = synthetic.SyntheticWriter


class FakeFunction:
    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


class FakeNativeLibrary:
    """Zero ACEs, invented matching owner/current SID; never calls Windows."""

    def __init__(self):
        self.sid = ctypes.create_unicode_buffer("INVENTED-owner")
        self.acl = ctypes.create_string_buffer(8)
        self.GetCurrentProcess = FakeFunction(lambda: 1)
        self.LocalFree = FakeFunction(lambda *args: 0)
        self.CloseHandle = FakeFunction(lambda *args: 1)
        self.GetAce = FakeFunction(lambda *args: 0)
        self.OpenProcessToken = FakeFunction(self.token)
        self.GetTokenInformation = FakeFunction(self.token_info)
        self.ConvertSidToStringSidW = FakeFunction(self.sid_text)
        self.GetNamedSecurityInfoW = FakeFunction(self.security)

    def token(self, process, access, output):
        output._obj.value = 1
        return 1

    def token_info(self, token, kind, output, length, needed):
        needed._obj.value = ctypes.sizeof(ctypes.c_void_p)
        if output is None:
            return 0
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = 1
        return 1

    def sid_text(self, sid, output):
        output._obj.value = ctypes.addressof(self.sid)
        return 1

    def security(self, path, kind, flags, owner, group, dacl, sacl, descriptor):
        owner._obj.value = 1
        dacl._obj.value = ctypes.addressof(self.acl)
        descriptor._obj.value = 1
        return 0


class NullableFixture(unittest.TestCase):
    def setUp(self):
        self.fixture = base.IssuerTests(
            "test_issue_exact_profile_authenticated_self_identity_and_private_delivery"
        )
        with patch.object(tempfile, "tempdir", str(Path(tempfile.gettempdir()).resolve())):
            self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        fixture = self.fixture
        fixture.plan["parent_id"] = None
        for key in ("parent_credential", "child_credential", "journal", "claim", "evidence"):
            fixture.plan[key] = fixture.plan[key].replace("\\", "/")
        source_root = Path(issuer.__file__).resolve().parents[1]
        fixture.plan["source_sha2_256"] = {
            name: recovery.digest((source_root / name).read_bytes()) for name in issuer.SOURCE_FILES
        }
        fixture.refresh()
        original_plan = fixture.inputs.plan.read_bytes()
        fixture.run_issuer()
        original_evidence = Path(fixture.plan["evidence"]).read_bytes()
        self.root = fixture.root
        namespace = (self.root / ("recovery-" + "4" * 24)).as_posix()
        roles = {
            role: (self.root / ("metadata-" + role)).as_posix()
            for role in recovery.HISTORY | recovery.CURRENT
        }
        roles.update({role: namespace + "/" + name for role, name in recovery.OUTPUTS.items()})
        roles.update(
            parentCredential=fixture.plan["parent_credential"].replace("\\", "/"),
            childCredential=fixture.plan["child_credential"].replace("\\", "/"),
            issuerJournal=fixture.plan["journal"].replace("\\", "/"),
        )
        roles["sourceManifest"] = (fixture.source / recovery.SOURCE_MANIFEST).as_posix()
        # Exact path strings are producer fields, so original source uses canonical
        # slash spelling too; this changes only synthetic fixture bytes.
        original = recovery.document(original_plan)
        for old_key, role in (
            ("parent_credential", "parentCredential"),
            ("child_credential", "childCredential"),
            ("journal", "issuerJournal"),
        ):
            original[old_key] = roles[role]
        self.assertEqual(original, recovery.document(original_plan))
        # The synthetic original journal is bound to the original plan's exact
        # byte digest. Rebuild it from issuance receipts under that spelling.
        old_digest = fixture.inputs.plan_digest
        self.original_digest = recovery.digest(original_plan)
        if self.original_digest != old_digest:
            raise AssertionError("fixture must create canonical issuer paths before issuance")
        for role, suffix in (
            ("issuerOwner", ".owner"),
            ("issuerRollback", "-journal"),
            ("issuerWal", "-wal"),
            ("issuerShm", "-shm"),
        ):
            roles[role] = roles["issuerJournal"] + suffix
        self.records = {
            role: recovery.encoded({"syntheticRole": role}) for role in recovery.HISTORY
        }
        self.records.update(
            issuerPlan=original_plan,
            issuerEvidence=original_evidence,
            terminal=b'{"recordedAt":"2026-10-21T12:00:00Z","synthetic":true}',
        )
        self.records["sourceManifest"] = recovery.encoded(
            {
                "schemaVersion": 1,
                "kind": "ungranted_screenshot_post_successor",
                "sources": dict(original["source_sha2_256"]),
                "productionQualified": False,
            }
        )
        self.records["witness"] = recovery.encoded(
            {
                "observedAt": "2026-10-23T12:00:00Z",
                "observer": "synthetic root",
                "evidenceReference": "synthetic-current-evidence",
                "parentExpiresAt": recovery.PARENT_CUTOFF,
                "providerStatus": "UNKNOWN",
            }
        )
        self.records["authority"] = recovery.encoded(
            {
                "recordedAt": "2026-10-23T12:00:00Z",
                "owner": "Terry",
                "decisionReference": "synthetic-authority",
                "scopeReference": "synthetic-scope",
            }
        )
        self.req = {
            "schemaVersion": 1,
            "contract": recovery.CONTRACT,
            "recoveryId": "4" * 24,
            "originalRunId": "9" * 24,
            "childId": base.CHILD_ID,
            "parentId": base.PARENT_ID,
            "startsAt": "2026-10-23T12:00:00Z",
            "endsAt": "2026-10-23T12:10:00Z",
            "namespace": namespace,
            "oldNamespace": (self.root / "old-retirement").as_posix(),
            "sourceRoot": fixture.source.as_posix(),
            "controllerSource": Path(recovery.__file__).as_posix(),
            "roles": roles,
            "pins": {k: recovery.digest(v) for k, v in self.records.items()},
            "sourcePins": {
                (fixture.source / k).as_posix(): v for k, v in original["source_sha2_256"].items()
            },
        }
        self.req["sourcePins"][self.req["controllerSource"]] = "7" * 64
        self.refresh()
        self.verifier = SyntheticEvidence(fixture, self.req, self.records)
        self.writer = SyntheticWriter()
        fixture.calls.clear()
        fixture.now = NOW.timestamp()
        fixture.responses = [
            base.envelope(fixture.parent_verify),
            fixture.catalog,
            base.envelope(fixture.parent_details),
            base.envelope(fixture.child_details | {"status": "expired"}),
            base.envelope({"id": base.CHILD_ID}),
        ]
        self.loaded = []

    def refresh(self):
        self.req["pins"] = {
            k: recovery.digest(v) for k, v in self.records.items() if k != "judgment"
        }
        subjects = {key: value for key, value in self.req.items() if key != "pins"}
        subjects["pins"] = dict(self.req["pins"])
        self.records["judgment"] = recovery.encoded(
            {
                "recordedAt": "2026-10-23T12:00:01Z",
                "author": "synthetic author",
                "reviewer": "synthetic independent reviewer",
                "verdict": "pass",
                "subjects": subjects,
            }
        )
        self.req["pins"]["judgment"] = recovery.digest(self.records["judgment"])
        self.raw = recovery.encoded(self.req)
        self.expected = recovery.digest(self.raw)


class NullableOperatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = NullableFixture("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.req = copy.deepcopy(f.req)
        self.source = f.fixture.source
        for name in issuer.SOURCE_FILES:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        self.req["sourceRoot"] = self.source.as_posix()
        self.pins = {
            name: recovery.digest((ROOT / name).read_bytes()) for name in issuer.SOURCE_FILES
        }
        self.req["sourcePins"] = {
            (self.source / name).as_posix(): pin for name, pin in self.pins.items()
        }
        self.req["roles"]["sourceManifest"] = (self.source / recovery.SOURCE_MANIFEST).as_posix()
        self.manifest_raw = recovery.encoded(
            {
                "schemaVersion": 1,
                "kind": "ungranted_screenshot_post_successor",
                "sources": self.pins,
                "productionQualified": False,
            }
        )
        f.records["sourceManifest"] = self.manifest_raw
        self.req["pins"]["sourceManifest"] = recovery.digest(self.manifest_raw)
        manifest_path = Path(self.req["roles"]["sourceManifest"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        for source in (recovery, operator):
            path = Path(str(source.__file__)).as_posix()
            self.req["sourcePins"][path] = recovery.digest(Path(path).read_bytes())
        for role, raw in f.records.items():
            if role != "judgment":
                Path(self.req["roles"][role]).write_bytes(raw)
        subjects = {key: value for key, value in self.req.items() if key != "pins"}
        subjects["pins"] = {
            key: value for key, value in self.req["pins"].items() if key != "judgment"
        }
        judgment = recovery.encoded(
            {
                "recordedAt": "2026-10-23T12:00:01Z",
                "author": "synthetic author",
                "reviewer": "synthetic reviewer",
                "verdict": "pass",
                "subjects": subjects,
            }
        )
        self.req["pins"]["judgment"] = recovery.digest(judgment)
        Path(self.req["roles"]["judgment"]).write_bytes(judgment)
        self.raw = recovery.encoded(self.req)
        provenance_path = f.root / "synthetic-original-manifest-provenance.txt"
        provenance_path.write_bytes(b"INVENTED original root, manifest and commit provenance")
        refs = {}
        for role in operator.FACTS:
            path = f.root / ("synthetic-fact-" + role)
            raw = ("INVENTED fixture evidence for " + role).encode()
            path.write_bytes(raw)
            refs[role] = operator.EvidenceRef(path.as_posix(), recovery.digest(raw))
        witness_path = Path(self.req["roles"]["witness"])
        witness = recovery.document(witness_path.read_bytes())
        witness["evidenceReference"] = operator.fact_reference(refs)
        witness_path.write_bytes(recovery.encoded(witness))
        self.req["pins"]["witness"] = recovery.digest(witness_path.read_bytes())
        subjects["pins"] = {
            key: value for key, value in self.req["pins"].items() if key != "judgment"
        }
        judgment = recovery.encoded(
            {
                "recordedAt": "2026-10-23T12:00:01Z",
                "author": "synthetic author",
                "reviewer": "synthetic reviewer",
                "verdict": "pass",
                "subjects": subjects,
            }
        )
        self.req["pins"]["judgment"] = recovery.digest(judgment)
        Path(self.req["roles"]["judgment"]).write_bytes(judgment)
        self.raw = recovery.encoded(self.req)
        self.facts = operator.ReviewedFacts(
            recovery.digest(self.raw),
            self.pins,
            {role: self.req["pins"][role] for role in recovery.HISTORY},
            {role: self.req["pins"][role] for role in recovery.CURRENT},
            refs,
            None,
            operator.OriginalManifestBinding(
                self.source.as_posix(),
                recovery.document(f.records["issuerPlan"])["source_commit"],
                recovery.digest(self.manifest_raw),
                self.pins,
                operator.EvidenceRef(
                    provenance_path.as_posix(), recovery.digest(provenance_path.read_bytes())
                ),
            ),
        )
        self.op = operator.Operator(self.raw, facts=self.facts)
        self.addCleanup(patch.stopall)
        patch.object(ctypes, "WinDLL", side_effect=lambda *a, **k: FakeNativeLibrary()).start()
        patch.object(
            subprocess, "check_output", side_effect=AssertionError("process forbidden")
        ).start()

    def rebind(self, role, raw):
        """Change invented bytes and every fixture binding; never genuine evidence."""
        Path(self.req["roles"][role]).write_bytes(raw)
        self.req["pins"][role] = recovery.digest(raw)
        subjects = {key: value for key, value in self.req.items() if key != "pins"}
        subjects["pins"] = {k: v for k, v in self.req["pins"].items() if k != "judgment"}
        judgment = recovery.encoded(
            {
                "recordedAt": "2026-10-23T12:00:01Z",
                "author": "INVENTED author",
                "reviewer": "INVENTED reviewer",
                "verdict": "pass",
                "subjects": subjects,
            }
        )
        Path(self.req["roles"]["judgment"]).write_bytes(judgment)
        self.req["pins"]["judgment"] = recovery.digest(judgment)
        self.raw = recovery.encoded(self.req)
        self.facts = dataclasses.replace(
            self.facts,
            request_digest=recovery.digest(self.raw),
            original_pins={k: self.req["pins"][k] for k in recovery.HISTORY},
            current_pins={k: self.req["pins"][k] for k in recovery.CURRENT},
        )
        self.op = operator.Operator(self.raw, facts=self.facts)

    def evidence_rows(self):
        return [
            recovery.document(row)
            for row in Path(self.req["roles"]["issuerEvidence"]).read_bytes().splitlines()
        ]

    def rebind_rows(self, rows):
        self.rebind("issuerEvidence", b"\n".join(recovery.encoded(r) for r in rows) + b"\n")

    def packet_review(self, packet):
        raw = recovery.encoded(
            {
                "author": "INVENTED packet author",
                "reviewer": "INVENTED independent reviewer",
                "recordedAt": "2026-10-23T12:00:01Z",
                "verdict": "pass",
                "subjects": {
                    "request": recovery.digest(packet.request),
                    "plan": recovery.digest(packet.plan),
                    "approval": recovery.digest(packet.approval),
                    "binding": recovery.digest(packet.binding),
                },
            }
        )
        path = Path(self.req["roles"]["packetReview"])
        path.write_bytes(raw)
        self.op.facts = dataclasses.replace(
            self.op.facts, packet_review=operator.EvidenceRef(path.as_posix(), recovery.digest(raw))
        )
        return raw

    def test_full_concrete_prepare_reprepare_write_preserves_immutable_history(self):
        before = {r: Path(self.req["roles"][r]).read_bytes() for r in recovery.HISTORY}
        original_journal = Path(self.req["roles"]["issuerJournal"]).read_bytes()
        outcome = self.op.prepare_metadata(now=NOW, execute=True)
        self.assertEqual(outcome.report["status"], "PREPARED_METADATA_ONLY", outcome.report)
        self.assertIsNotNone(outcome.packet)
        packet = outcome.packet
        assert packet is not None
        plan = recovery.document(packet.plan)
        old = recovery.document(before["issuerPlan"])
        self.assertIsNone(old["parent_id"])
        self.assertEqual(plan["parent_id"], self.req["parentId"])
        self.assertEqual(
            {k for k in plan if plan[k] != old[k]},
            {
                "operation",
                "parent_id",
                "starts_at",
                "expires_at",
                "claim",
                "journal",
                "evidence",
                "issuance",
            },
        )
        self.assertEqual(
            before, {r: Path(self.req["roles"][r]).read_bytes() for r in recovery.HISTORY}
        )
        self.assertEqual(Path(self.req["roles"]["issuerJournal"]).read_bytes(), original_journal)
        counts = outcome.report["counters"]
        self.assertGreater(
            counts["privateReadCallsCompleted"], len(recovery.HISTORY | recovery.CURRENT) * 2
        )
        self.assertEqual(counts["namespaceReserveCallsCompleted"], 1)
        self.assertEqual(counts["metadataCreateCallsCompleted"], 3)
        self.assertEqual(self.fixture.fixture.calls, [])
        with self.assertRaisesRegex(recovery.Refused, "spent_no_retry"):
            self.op.prepare_metadata(now=NOW, execute=True)

    def test_full_concrete_dispatch_unchanged_producer_fake_tls_only(self):
        outcome = self.op.prepare_metadata(now=NOW, execute=True)
        self.assertEqual(outcome.report["status"], "PREPARED_METADATA_ONLY", outcome.report)
        packet = outcome.packet
        assert packet is not None
        review = self.packet_review(packet)
        producer = self.op.producer()
        provider = self.op.sources.load("scripts.hosted_publisher_execution_provider")
        replies = iter(self.fixture.fixture.responses)
        wires = []

        class FakeSocket:
            def __init__(self):
                value = next(replies)
                body = json.dumps(value).encode()
                self.buffer = io.BytesIO(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                    + str(len(body)).encode()
                    + b"\r\nConnection: close\r\n\r\n"
                    + body
                )

            def settimeout(self, value):
                pass

            def connect(self, address):
                if address != ("1.1.1.1", 443):
                    raise AssertionError("invented exact address required")

            def sendall(self, raw):
                wires.append(raw)

            def recv(self, maximum):
                return self.buffer.read(maximum)

            def close(self):
                pass

        class FakeTLS:
            def wrap_socket(self, raw, server_hostname):
                return raw

        def invented_git(arguments, **kwargs):
            # Preserve producer source validation while inventing Git receipts.
            # No Git process or real repository/history query is performed.
            command = arguments[arguments.index("-C") + 2 :]
            if command == ["rev-parse", "HEAD"]:
                return "d" * 40
            if command[0] != "ls-tree":
                raise AssertionError("unexpected invented Git command")
            names = command[command.index("--") + 1 :]
            return "\n".join(
                "100644 blob "
                + hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                + "\t"
                + name
                for name in names
                for raw in [(self.source / name).read_bytes()]
            )

        with (
            patch.object(provider.socket, "socket", side_effect=lambda *a: FakeSocket()),
            patch.object(provider.ssl, "create_default_context", return_value=FakeTLS()),
            patch.object(subprocess, "check_output", side_effect=invented_git),
        ):
            result = self.op.dispatch(
                packet,
                packet_review=review,
                clock=lambda: NOW,
                monotonic=lambda: 100.0,
                execute=True,
            )
        self.assertEqual(result["requests"], 5)
        self.assertEqual([w.split(b" ")[0] for w in wires], [b"GET"] * 4 + [b"DELETE"])
        self.assertEqual(producer.MAX_REQUESTS, 5)
        self.assertEqual(
            self.fixture.fixture.journal(
                self.req["roles"]["issuerJournal"], self.req["pins"]["issuerPlan"]
            )["issuer:retire"]["state"],
            "complete",
        )

    def test_acknowledged_parent_mismatch_refuses_without_reservation(self):
        original_rows = self.evidence_rows()
        for index, branch, field in (
            (1, "result", "id"),
            (3, "result", "id"),
            (4, "ownership", "parentId"),
        ):
            rows = copy.deepcopy(original_rows)
            if branch == "ownership":
                rows[index][branch][field] = "e" * 32
            else:
                rows[index]["response"][branch][field] = "e" * 32
            self.rebind_rows(rows)
            outcome = self.op.prepare_metadata(now=NOW, execute=True)
            self.assertEqual(
                outcome.report["failureCategory"], "acknowledged_parent_lineage_mismatch"
            )
            self.assertFalse(Path(self.req["namespace"]).exists())

    def test_nonnull_original_mismatch_refuses(self):
        plan = recovery.document(Path(self.req["roles"]["issuerPlan"]).read_bytes())
        plan["parent_id"] = "e" * 32
        self.rebind("issuerPlan", recovery.encoded(plan))
        # Retie the invented journal so this isolates the parent gate rather than
        # stopping at the earlier digest check. This changes synthetic data only.
        with sqlite3.connect(self.req["roles"]["issuerJournal"]) as db:
            db.execute("UPDATE meta SET digest=?", (self.req["pins"]["issuerPlan"],))
        outcome = self.op.prepare_metadata(now=NOW, execute=True)
        self.assertEqual(outcome.report["failureCategory"], "exact_original_issue_binding_required")

    def test_nonnull_matching_original_still_prepares(self):
        plan = recovery.document(Path(self.req["roles"]["issuerPlan"]).read_bytes())
        plan["parent_id"] = self.req["parentId"]
        self.rebind("issuerPlan", recovery.encoded(plan))
        with sqlite3.connect(self.req["roles"]["issuerJournal"]) as db:
            db.execute("UPDATE meta SET digest=?", (self.req["pins"]["issuerPlan"],))
        outcome = self.op.prepare_metadata(now=NOW, execute=True)
        self.assertEqual(outcome.report["status"], "PREPARED_METADATA_ONLY", outcome.report)

    def test_missing_duplicate_or_reordered_lineage_refuses(self):
        rows = self.evidence_rows()
        for changed in (rows[1:], rows + [rows[1]], [rows[0], rows[2], rows[1], *rows[3:]]):
            self.rebind_rows(changed)
            outcome = self.op.prepare_metadata(now=NOW, execute=True)
            self.assertEqual(
                outcome.report["failureCategory"], "acknowledged_parent_lineage_required"
            )

    def test_acknowledged_security_fields_cannot_change_parent_binding(self):
        rows = self.evidence_rows()
        for field, value in (
            ("parentFingerprint", "e" * 64),
            ("accountId", "e" * 32),
            ("childId", "e" * 32),
        ):
            changed = copy.deepcopy(rows)
            changed[4]["ownership"][field] = value
            self.rebind_rows(changed)
            outcome = self.op.prepare_metadata(now=NOW, execute=True)
            self.assertEqual(
                outcome.report["failureCategory"], "acknowledged_parent_lineage_mismatch"
            )

    def test_private_provenance_failure_has_closed_category_and_unknown_effects(self):
        original = self.facts.original_manifest
        assert original is not None
        original_private = self.op._private

        def private(path, **kwargs):
            if path == original.provenance.path:
                raise self.op._helpers().OperatorRefused("private_file_broad_access_refused")
            return original_private(path, **kwargs)

        with patch.object(self.op, "_private", side_effect=private):
            outcome = self.op.prepare_metadata(now=NOW, execute=True)
        self.assertEqual(outcome.report["phase"], "inventory")
        self.assertEqual(outcome.report["failureCategory"], "private_file_broad_access_refused")
        self.assertEqual(outcome.report["failedCallEffects"], "UNKNOWN")
        self.assertEqual(outcome.report["counters"]["privateReadCallsAttempted"], 0)

    def test_provenance_role_and_private_parent_contract(self):
        original = self.facts.original_manifest
        assert original is not None
        with self.assertRaisesRegex(recovery.Refused, "provenance_required"):
            operator.Operator(
                self.raw,
                facts=dataclasses.replace(
                    self.facts,
                    original_manifest=dataclasses.replace(
                        original, provenance_role="public_source_manifest"
                    ),
                ),
            )
        # Exercise exact _private calls with invented ACL results, no native DLL.
        checks = []
        helpers = self.op._helpers()

        def acl(path, *, directory=False):
            checks.append((path, directory))
            if directory:
                raise recovery.Refused("operator_private_parent_test_refusal")

        with patch.object(helpers, "_assert_private", side_effect=acl):
            with self.assertRaisesRegex(recovery.Refused, "private_parent_test"):
                self.op._private(original.provenance.path)
        self.assertEqual(
            checks,
            [
                (Path(original.provenance.path), False),
                (Path(original.provenance.path).parent, True),
            ],
        )

    def test_safe_unexpected_error_contains_no_exception_data(self):
        marker = "SECRET C:/private/identity fingerprint-123"
        with patch.object(self.op, "inventory", side_effect=RuntimeError(marker)):
            outcome = self.op.prepare_metadata(now=NOW, execute=True)
        self.assertIsNone(outcome.packet)
        self.assertEqual(outcome.report["failureCategory"], "UNEXPECTED_EXCEPTION")
        self.assertEqual(outcome.report["failedCallEffects"], "UNKNOWN")
        self.assertNotIn(marker, json.dumps(outcome.report))

    def test_forged_refusal_text_is_closed_and_partial_write_preserved(self):
        def fail_create(path, raw):
            with Path(path).open("xb") as stream:
                stream.write(raw[:8])
            raise recovery.Refused("SECRET C:/sensitive/path")

        metadata = self.op.sources.load("scripts.collect_publisher_grant_metadata")
        # Patch only during the exclusive write, after source rechecks finish.
        reserve = self.op.reserve_exclusive

        def reserve_and_inject(path):
            reserve(path)
            metadata.__dict__["_create_private"] = fail_create

        with patch.object(self.op, "reserve_exclusive", side_effect=reserve_and_inject):
            outcome = self.op.prepare_metadata(now=NOW, execute=True)
        self.assertEqual(outcome.report["failureCategory"], "UNEXPECTED_EXCEPTION")
        self.assertEqual(outcome.report["phase"], "write")
        self.assertEqual(outcome.report["counters"]["metadataCreateCallsAttempted"], 1)
        self.assertEqual(outcome.report["counters"]["metadataCreateCallsCompleted"], 0)
        self.assertEqual(len(Path(self.req["roles"]["plan"]).read_bytes()), 8)
        with self.assertRaisesRegex(recovery.Refused, "spent_no_retry"):
            self.op.prepare_metadata(now=NOW, execute=True)

    def test_final_recheck_refuses_drift_before_any_socket(self):
        outcome = self.op.prepare_metadata(now=NOW, execute=True)
        packet = outcome.packet
        assert packet is not None
        review = self.packet_review(packet)
        Path(self.req["roles"]["witness"]).write_bytes(b"invented drift")
        with self.assertRaisesRegex(recovery.Refused, "metadata_pin_mismatch"):
            self.op.dispatch(
                packet,
                packet_review=review,
                clock=lambda: NOW,
                monotonic=lambda: 100.0,
                execute=True,
            )

    def test_inert_defaults_and_source_guards_remain(self):
        with self.assertRaisesRegex(recovery.Refused, "inert_default"):
            self.op.prepare_metadata(now=NOW)
        with self.assertRaisesRegex(recovery.Refused, "inert_default"):
            self.op.dispatch(None, packet_review=b"", clock=lambda: NOW, monotonic=lambda: 0)
        with patch.object(recovery, "MAX_REQUESTS", 6):
            with self.assertRaisesRegex(recovery.Refused, "ambient_constants_changed"):
                self.op.source_closure(self.req["sourcePins"])


if __name__ == "__main__":
    unittest.main()
