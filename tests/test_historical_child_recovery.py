"""Synthetic recovery adapter integration; no host custody/provider assertions."""

from __future__ import annotations

import copy
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts import historical_child_recovery as recovery
from scripts import provision_work_plan_token as issuer
from tests import test_provision_work_plan_token as base

NOW = datetime(2026, 10, 23, 12, 0, 1, tzinfo=UTC)


class SyntheticEvidence:
    """In-memory evidence seam; invented statements are explicitly synthetic."""

    def __init__(self, fixture, req, records):
        self.fixture, self.req, self.records = fixture, req, records
        self.calls = []
        self.overrides = {}
        self.reject: str | None = None

    def inventory(self, roles, namespace):
        self.calls.append("inventory")
        states = {}
        for role in recovery.ROLES | {"namespace"}:
            is_output = role in recovery.OUTPUTS or role == "namespace"
            path = namespace if role == "namespace" else roles[role]
            exists = (
                Path(path).exists()
                if is_output
                else role
                not in {
                    "issuerRollback",
                    "issuerWal",
                    "issuerShm",
                }
            )
            states[role] = recovery.RoleState(
                exists,
                "identity-" + role if exists else None,
                role != "sourceManifest",
                True,
                1,
                False,
            )
        return states | self.overrides

    def source_closure(self, pins):
        self.calls.append("source")
        if self.reject == "source":
            raise recovery.Refused("synthetic_source_drift")
        assert pins == self.req["sourcePins"]

    def original_latch(self, journal, plan_digest, child_id):
        self.calls.append("latch")
        value = self.fixture.journal(journal, plan_digest).get("issuer:retire", {})
        return {
            "key": "issuer:retire",
            "planDigest": plan_digest,
            "childId": child_id,
            "state": value.get("state", "unused"),
        }

    def read_metadata(self, role, path, limit):
        self.calls.append("read:" + role)
        assert role not in {"parentCredential", "childCredential"}
        if role in recovery.OUTPUTS:
            return Path(path).read_bytes()
        if role not in self.records:
            raise recovery.Refused("synthetic_missing_evidence")
        return self.records[role]

    def authenticate(self, kind, context, records):
        self.calls.append("authenticate:" + kind)
        if self.reject == kind:
            raise recovery.Refused("synthetic_unverified_evidence")


class SyntheticWriter:
    def __init__(self):
        self.partial = False
        self.writes = 0

    def reserve_exclusive(self, path):
        Path(path).mkdir()

    def create_exclusive(self, path, raw):
        self.writes += 1
        data = raw[: len(raw) // 2] if self.partial else raw
        with Path(path).open("xb") as stream:
            written = stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return written


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = base.IssuerTests(
            "test_issue_exact_profile_authenticated_self_identity_and_private_delivery"
        )
        with patch.object(tempfile, "tempdir", str(Path(tempfile.gettempdir()).resolve())):
            self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        fixture = self.fixture
        fixture.plan["parent_id"] = base.PARENT_ID
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

    def prepare(self):
        return recovery.prepare(
            self.raw, expected_digest=self.expected, verifier=self.verifier, now=NOW
        )

    def write_packet(self):
        packet = self.prepare()
        recovery.write_preparation(
            packet,
            verifier=self.verifier,
            writer=self.writer,
            expected_digest=self.expected,
            now=NOW,
        )
        Path(self.req["roles"]["authority"]).write_bytes(self.records["authority"])
        review = recovery.encoded(
            {
                "author": "synthetic packet author",
                "reviewer": "synthetic packet reviewer",
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
        Path(self.req["roles"]["packetReview"]).write_bytes(review)
        return packet, review

    def dispatch(self, packet, review, *, execute=True, clock=lambda: NOW):
        def credential(path, limit):
            self.loaded.append(path)
            self.assertEqual(path, Path(self.req["roles"]["parentCredential"]))
            return base.PARENT

        origin = self.req["sourceRoot"] + "/scripts/provision_work_plan_token.py"
        with patch.object(issuer, "__file__", origin):
            return recovery.dispatch(
                packet,
                expected_digest=self.expected,
                verifier=self.verifier,
                producer=issuer,
                packet_review=review,
                clock=clock,
                monotonic=lambda: self.fixture.tick,
                transport=self.fixture.transport,
                credential_loader=credential,
                execute=execute,
            )

    def test_inert_default_and_prepare_have_no_dispatch_or_credential_reads(self):
        with self.assertRaises(recovery.Refused):
            recovery.prepare(self.raw, expected_digest=self.expected, now=NOW)
        packet, review = self.write_packet()
        with self.assertRaisesRegex(recovery.Refused, "inert_default"):
            self.dispatch(packet, review, execute=False)
        self.assertEqual(self.loaded, [])
        self.assertEqual(self.fixture.calls, [])
        self.assertNotIn("read:parentCredential", self.verifier.calls)
        self.assertLess(self.verifier.calls.index("inventory"), self.verifier.calls.index("source"))
        self.assertLess(
            self.verifier.calls.index("latch"), self.verifier.calls.index("read:authority")
        )

    def test_generated_packet_reuses_real_producer_and_retains_immutable_history(self):
        terminal = self.records["terminal"]
        packet, review = self.write_packet()
        result = self.dispatch(packet, review)
        self.assertEqual(result["requests"], 5)
        self.assertEqual(
            [call.wire.split(b" ")[0] for call in self.fixture.calls],
            [b"GET", b"GET", b"GET", b"GET", b"DELETE"],
        )
        self.assertTrue(all(call.timeout <= 20 for call in self.fixture.calls))
        self.assertEqual(len(self.loaded), 1)
        self.assertEqual(self.records["terminal"], terminal)
        plan = recovery.document(packet.plan)
        original = recovery.document(self.records["issuerPlan"])
        changed = {key for key in plan if plan[key] != original[key]}
        self.assertEqual(
            changed,
            {"operation", "starts_at", "expires_at", "claim", "journal", "evidence", "issuance"},
        )
        self.assertEqual(plan["issuance"]["plan_digest"], self.original_digest)
        self.assertEqual(
            self.fixture.journal(plan["issuance"]["journal"], self.original_digest)[
                "issuer:retire"
            ]["state"],
            "complete",
        )

    def test_missing_current_witness_and_missing_authority_refuse(self):
        for role in ("witness", "authority"):
            original = self.records.pop(role)
            with self.assertRaises(recovery.Refused):
                self.prepare()
            self.records[role] = original
        self.assertEqual(self.loaded, [])
        self.assertEqual(self.fixture.calls, [])

    def test_stale_future_or_end_boundary_evidence_refuses(self):
        for role, field in (("witness", "observedAt"), ("authority", "recordedAt")):
            original = self.records[role]
            for value in ("2026-10-22T12:00:00Z", "2026-10-23T12:00:02Z", "2026-10-23T12:10:00Z"):
                self.records[role] = recovery.encoded(recovery.document(original) | {field: value})
                self.refresh()
                with self.assertRaises(recovery.Refused):
                    self.prepare()
            self.records[role] = original

    def test_window_limits_deadline_and_dispatch_clock(self):
        for end in ("2026-10-23T12:00:00Z", "2026-10-23T12:10:01Z", "2026-10-26T12:00:01Z"):
            self.req["endsAt"] = end
            self.refresh()
            with self.assertRaises(recovery.Refused):
                self.prepare()
        self.req["endsAt"] = "2026-10-23T12:10:00Z"
        self.refresh()
        packet, review = self.write_packet()
        with self.assertRaises(recovery.Refused):
            self.dispatch(packet, review, clock=lambda: recovery.stamp(self.req["endsAt"]))
        self.assertEqual(self.loaded, [])

    def test_existing_namespace_outputs_sidecars_links_and_identity_alias_refuse(self):
        for role in ("namespace", "plan", "claim", "issuerWal", "issuerShm", "issuerRollback"):
            self.verifier.overrides = {
                role: recovery.RoleState(True, "occupied", True, True, 1, False)
            }
            with self.assertRaises(recovery.Refused):
                self.prepare()
        for state in (
            recovery.RoleState(True, "x", True, True, 2, False),
            recovery.RoleState(True, "x", True, True, 1, True),
            recovery.RoleState(True, "x", False, True, 1, False),
            recovery.RoleState(True, "identity-terminal", True, True, 1, False),
        ):
            self.verifier.overrides = {"authority": state}
            with self.assertRaises(recovery.Refused):
                self.prepare()
        self.assertNotIn("source", self.verifier.calls)

    def test_lexical_role_alias_source_alias_and_unknown_fields_refuse_early(self):
        original = copy.deepcopy(self.req)
        changes = [
            lambda: self.req["roles"].update(authority=self.req["roles"]["terminal"]),
            lambda: self.req["roles"].update(authority=self.req["sourceRoot"] + "/file"),
            lambda: self.req.update(extra="unknown"),
            lambda: self.req["roles"].update(extra="unknown"),
            lambda: self.req["roles"].update(authority="C:/bad/../alias"),
            lambda: self.req["roles"].update(authority="C:/bad/FILE~1"),
        ]
        for change in changes:
            self.req.clear()
            self.req.update(copy.deepcopy(original))
            change()
            self.refresh()
            with self.assertRaises(recovery.Refused):
                self.prepare()
        self.assertEqual(self.verifier.calls, [])

    def test_source_or_metadata_drift_and_unauthenticated_facts_refuse(self):
        self.verifier.reject = "source"
        with self.assertRaises(recovery.Refused):
            self.prepare()
        self.assertFalse(any(call.startswith("read:") for call in self.verifier.calls))
        self.verifier.reject = None
        self.records["terminal"] += b" "
        with self.assertRaises(recovery.Refused):
            self.prepare()
        self.records["terminal"] = self.records["terminal"][:-1]
        self.verifier.reject = "current"
        with self.assertRaises(recovery.Refused):
            self.prepare()

    def test_used_or_unknown_original_latch_refuses_before_metadata_and_provider(self):
        with patch.object(self.verifier, "original_latch") as latch:
            for state in ("intent", "unknown", "complete", "partial"):
                latch.return_value = {
                    "key": "issuer:retire",
                    "planDigest": self.original_digest,
                    "childId": base.CHILD_ID,
                    "state": state,
                }
                with self.assertRaises(recovery.Refused):
                    self.prepare()
        self.assertFalse(any(call.startswith("read:") for call in self.verifier.calls))
        self.assertEqual(self.loaded, [])

    def test_partial_write_retains_namespace_and_refuses_repreparation(self):
        packet = self.prepare()
        self.writer.partial = True
        with self.assertRaisesRegex(recovery.Refused, "partial_preparation"):
            recovery.write_preparation(
                packet,
                verifier=self.verifier,
                writer=self.writer,
                expected_digest=self.expected,
                now=NOW,
            )
        self.assertEqual(self.writer.writes, 1)
        self.assertTrue(Path(self.req["roles"]["plan"]).exists())
        with self.assertRaises(recovery.Refused):
            self.prepare()

    def test_child_identity_mismatch_is_refused_by_unchanged_producer(self):
        packet, review = self.write_packet()
        self.fixture.responses[3]["result"]["id"] = "f" * 32
        with self.assertRaises(issuer.ProvisioningRefused):
            self.dispatch(packet, review)
        self.assertEqual(len(self.fixture.calls), 4)

    def test_active_child_status_is_refused_by_unchanged_producer(self):
        packet, review = self.write_packet()
        self.fixture.responses[3]["result"]["status"] = "active"
        with self.assertRaises(issuer.ProvisioningRefused):
            self.dispatch(packet, review)
        self.assertEqual(len(self.fixture.calls), 4)

    def test_disabled_child_status_is_refused_by_unchanged_producer(self):
        packet, review = self.write_packet()
        self.fixture.responses[3]["result"]["status"] = "disabled"
        with self.assertRaises(issuer.ProvisioningRefused):
            self.dispatch(packet, review)
        self.assertEqual(len(self.fixture.calls), 4)

    def test_unknown_child_status_is_refused_by_unchanged_producer(self):
        packet, review = self.write_packet()
        self.fixture.responses[3]["result"]["status"] = "unknown"
        with self.assertRaises(issuer.ProvisioningRefused):
            self.dispatch(packet, review)
        self.assertEqual(len(self.fixture.calls), 4)

    def test_expired_parent_is_refused_by_unchanged_producer(self):
        packet, review = self.write_packet()
        self.fixture.responses[0]["result"].update(
            status="expired", expires_on="2026-10-23T11:00:00Z"
        )
        with self.assertRaises(issuer.ProvisioningRefused):
            self.dispatch(packet, review)
        self.assertEqual(len(self.fixture.calls), 1)

    def test_independent_current_judgment_is_required(self):
        judgment = recovery.document(self.records["judgment"])
        judgment["reviewer"] = judgment["author"].upper()
        self.records["judgment"] = recovery.encoded(judgment)
        self.req["pins"]["judgment"] = recovery.digest(self.records["judgment"])
        self.raw = recovery.encoded(self.req)
        self.expected = recovery.digest(self.raw)
        with self.assertRaises(recovery.Refused):
            self.prepare()

    def test_dispatch_clock_expiring_during_review_refuses_before_bearer(self):
        packet, review = self.write_packet()
        times = iter([NOW, recovery.stamp(self.req["endsAt"])])
        with self.assertRaises(recovery.Refused):
            self.dispatch(packet, review, clock=lambda: next(times))
        self.assertEqual(self.loaded, [])

    def test_unknown_delete_spends_original_latch_and_no_second_parent_read(self):
        packet, review = self.write_packet()
        self.fixture.responses[-1] = TimeoutError("SYNTHETIC unknown result")
        with self.assertRaises(issuer.ProvisioningRefused):
            self.dispatch(packet, review)
        self.assertEqual(len(self.fixture.calls), 5)
        self.assertEqual(len(self.loaded), 1)
        self.req["recoveryId"] = "5" * 24
        self.req["namespace"] = (self.root / ("recovery-" + "5" * 24)).as_posix()
        for role, name in recovery.OUTPUTS.items():
            self.req["roles"][role] = self.req["namespace"] + "/" + name
        self.refresh()
        self.verifier.calls.clear()
        with self.assertRaisesRegex(recovery.Refused, "original_retirement_latch_not_unused"):
            self.prepare()
        self.assertFalse(any(call.startswith("read:") for call in self.verifier.calls))
        self.assertEqual(len(self.loaded), 1)
        with self.assertRaises(recovery.Refused):
            self.dispatch(packet, review)
        self.assertEqual(len(self.fixture.calls), 5)
        self.assertEqual(len(self.loaded), 1)

    def test_packet_drift_or_independent_review_failure_refuses_before_bearer(self):
        packet, review = self.write_packet()
        Path(self.req["roles"]["plan"]).write_bytes(packet.plan + b" ")
        with self.assertRaises(recovery.Refused):
            self.dispatch(packet, review)
        self.assertEqual(self.loaded, [])

    def test_packet_reviewer_cannot_be_its_author(self):
        packet, review = self.write_packet()
        value = recovery.document(review)
        value["reviewer"] = value["author"]
        review = recovery.encoded(value)
        Path(self.req["roles"]["packetReview"]).write_bytes(review)
        with self.assertRaisesRegex(recovery.Refused, "independent_actual_packet_review_required"):
            self.dispatch(packet, review)
        self.assertEqual(self.loaded, [])

    def test_public_manifest_inventory_cannot_claim_private_or_share_identity(self):
        for state in (
            recovery.RoleState(True, "manifest", True, True, 1, False),
            recovery.RoleState(True, "identity-terminal", False, True, 1, False),
            recovery.RoleState(True, "manifest", False, True, 2, False),
            recovery.RoleState(True, "manifest", False, True, 1, True),
        ):
            self.verifier.overrides = {"sourceManifest": state}
            with self.subTest(state=state), self.assertRaises(recovery.Refused):
                self.prepare()
        self.assertNotIn("source", self.verifier.calls)

    def test_only_exact_public_manifest_role_and_equal_optional_source_pin_allowed(self):
        original = copy.deepcopy(self.req)
        for path in (
            self.req["roles"]["sourceManifest"].upper(),
            self.req["sourceRoot"] + "/copied-manifest.json",
            (self.root / "copied-manifest.json").as_posix(),
        ):
            self.req.clear()
            self.req.update(copy.deepcopy(original))
            self.req["roles"]["sourceManifest"] = path
            self.refresh()
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(recovery.Refused, "source_manifest_required"),
            ):
                self.prepare()
        self.req.clear()
        self.req.update(copy.deepcopy(original))
        path = self.req["roles"]["sourceManifest"]
        self.req["sourcePins"][path] = self.req["pins"]["sourceManifest"]
        self.refresh()
        self.prepare()
        self.req["sourcePins"][path] = "0" * 64
        self.refresh()
        with self.assertRaisesRegex(recovery.Refused, "dual_pin_mismatch"):
            self.prepare()

    def test_manifest_schema_map_and_other_private_roles_remain_closed(self):
        original_manifest = recovery.document(self.records["sourceManifest"])
        for change in (
            lambda value: value.update(kind="other"),
            lambda value: value.update(productionQualified=True),
            lambda value: value.update(schemaVersion=True),
            lambda value: value["sources"].pop("scripts/provision_work_plan_token.py"),
            lambda value: value["sources"].update({"../escape.py": "a" * 64}),
            lambda value: value["sources"].update({"SCRIPT.py": "a" * 64, "script.py": "a" * 64}),
        ):
            manifest = copy.deepcopy(original_manifest)
            change(manifest)
            self.records["sourceManifest"] = recovery.encoded(manifest)
            self.refresh()
            with self.assertRaises(recovery.Refused):
                self.prepare()
        self.records["sourceManifest"] = recovery.encoded(original_manifest)
        for role in ("terminal", "witness", "parentCredential", "issuerJournal", "plan"):
            original_path = self.req["roles"][role]
            self.req["roles"][role] = self.req["sourceRoot"] + "/" + role
            self.refresh()
            with self.subTest(role=role), self.assertRaises(recovery.Refused):
                self.prepare()
            self.req["roles"][role] = original_path


if __name__ == "__main__":
    unittest.main()
