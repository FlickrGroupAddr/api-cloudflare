"""Behavioral checks for public-only preparation; no provider or private inputs."""

import copy
import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from scripts import prepare_private_snapshot_qualification as p
from scripts import qualify_private_d1_snapshot as q
from scripts.temporary_composition_metadata_collector import canonical, digest


class PrivateSnapshotPreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-offline-snapshot-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.stage = self.base / "stage"

    def prepare(self):
        return p.prepare(self.stage)

    def document(self, name):
        return json.loads((self.stage / name).read_bytes())

    def synthetic_root(self):
        root = self.base / "source"
        (root / "scripts").mkdir(parents=True)
        for name in (*p.QUALIFIER_SOURCE_FILES, "prepare_private_snapshot_qualification.py"):
            (root / "scripts" / name).write_bytes((p.ROOT / "scripts" / name).read_bytes())
        return root

    def test_source_pins_bind_actual_bytes_and_qualifier_template_is_compatible(self):
        result = self.prepare()
        pins = self.document("source-pins.json")
        self.assertEqual(
            set(pins), {*p.QUALIFIER_SOURCE_FILES, "prepare_private_snapshot_qualification.py"}
        )
        for name, value in pins.items():
            self.assertEqual(
                value, hashlib.sha256((p.ROOT / "scripts" / name).read_bytes()).hexdigest()
            )
        self.assertEqual(self.document("packet-template.json")["sourceSha256"], q.source_sha256())
        self.assertEqual(p.verify(self.stage, digest(result)), result)
        self.assertEqual(p.prepare(self.base / "second"), result)

    def test_independent_pin_is_required_to_match(self):
        self.prepare()
        for wrong in ("0" * 64, "", "not-a-digest"):
            with self.subTest(pin=wrong), self.assertRaises(ValueError):
                p.verify(self.stage, wrong)

    def test_source_change_invalidates_existing_stage_and_new_identity(self):
        root = self.synthetic_root()
        before = p.prepare(self.stage, root=root)
        source = root / "scripts" / "private_d1_snapshot_codec.py"
        source.write_bytes(source.read_bytes() + b"\n# synthetic source drift\n")
        with self.assertRaises(ValueError):
            p.verify(self.stage, digest(before), root=root)
        after = p.prepare(self.base / "changed", root=root)
        self.assertNotEqual(digest(before), digest(after))

    def test_preparation_reads_only_public_sources_and_its_own_stage(self):
        root = self.synthetic_root()
        (root / "private-account.json").write_text("synthetic-account-decoy", encoding="utf-8")
        allowed = {
            root / "scripts" / name for name in (*p.QUALIFIER_SOURCE_FILES, Path(p.__file__).name)
        }
        original_open = Path.open
        reads = []

        def guarded_open(path, mode="r", *args, **kwargs):
            if "r" in mode or "+" in mode:
                resolved = path.resolve()
                self.assertTrue(resolved in allowed or resolved.parent == self.stage)
                reads.append(resolved)
            return original_open(path, mode, *args, **kwargs)

        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, "open", guarded_open))
            for target in (
                "socket.socket",
                "socket.getaddrinfo",
                "subprocess.run",
                "subprocess.Popen",
                "os.getenv",
                "pathlib.Path.home",
                "builtins.input",
            ):
                stack.enter_context(patch(target, side_effect=AssertionError("offline boundary")))
            self.prepare_with_root(root)
        self.assertTrue(reads)
        self.assertEqual({path.name for path in self.stage.iterdir()}, set(p.FILES))
        self.assertFalse((self.stage / "private-account.json").exists())

    def prepare_with_root(self, root):
        return p.prepare(self.stage, root=root)

    def test_request_budget_and_new_database_ownership_are_fixed(self):
        recipe = cast(dict[str, Any], self.prepare())
        phases = recipe["orderedRequestBounds"]
        self.assertEqual([phase["maximum"] for phase in phases], [1, 1, 11, 11, 1, 1])
        self.assertEqual(sum(phase["maximum"] for phase in phases), 26)
        self.assertEqual(recipe["maximumRequests"], q.MAX_REQUESTS)
        self.assertEqual(recipe["maximumCallerSeconds"], 1200)
        self.assertEqual(recipe["maximumRequestSeconds"], 30)
        self.assertEqual(recipe["maximumTablesIncludingProviderTables"], 2)
        self.assertEqual(recipe["maximumRowsPerTable"], 256)
        self.assertEqual(recipe["maximumAggregateResponseWireBytes"], 7536640)
        for key in ("existingDatabaseIdAccepted", "automaticRetries", "resumeOrReconcile"):
            self.assertIs(recipe[key], False)
        self.assertEqual(phases[0]["operation"], "fresh_create")
        self.assertEqual(phases[-2]["operation"], "same_acknowledged_uuid_delete")
        self.assertEqual(phases[-1]["operation"], "same_uuid_get_observation")

    def test_preparation_does_not_manufacture_authority_or_cleanup_evidence(self):
        recipe = self.prepare()
        for key in (
            "liveExecutionGranted",
            "effectiveGrantsVerified",
            "privateCustodyVerified",
            "sqlSettlementQualified",
            "cleanupVerified",
            "productionQualified",
            "realExtractionQualified",
            "publisherDisposalExceptionApplicable",
        ):
            self.assertIs(recipe[key], False)
        self.assertEqual(recipe["providerNotFoundMeaning"], "exact_response_observation_only")
        consent = self.document("consent-template.json")
        self.assertEqual(consent, {"approved": False, "decisionRef": None, "packetSha256": None})
        packet = self.document("packet-template.json")
        for key in set(packet) - {"kind", "schemaVersion", "sourceSha256"}:
            self.assertIsNone(packet[key])
        self.assertNotIn("databaseId", packet)

    def test_unfilled_template_refuses_before_credentials_or_transport(self):
        self.prepare()
        packet, consent = (
            self.document("packet-template.json"),
            self.document("consent-template.json"),
        )
        with (
            patch.object(q, "_pinned_https", side_effect=AssertionError("no transport")) as network,
            self.assertRaises(q.QualificationError),
        ):
            q.qualify(packet, digest(packet), consent, self.fail, self.base / "journal")
        network.assert_not_called()
        self.assertFalse((self.base / "journal").exists())

    def test_filled_but_unapproved_template_and_existing_id_refuse_before_credentials(self):
        self.prepare()
        packet = self.document("packet-template.json")
        now = datetime(2026, 10, 18, tzinfo=UTC)
        packet.update(
            {
                "runId": "a" * 32,
                "accountId": "b" * 32,
                "endpointAddress": "1.1.1.1",
                "startsAt": now.isoformat().replace("+00:00", "Z"),
                "expiresAt": (now + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
                "providerTokenExpiresAt": (now + timedelta(hours=1))
                .isoformat()
                .replace("+00:00", "Z"),
                "credentialBinding": "c" * 64,
                "grantEvidenceSha256": "d" * 64,
                "privateCustodySha256": "e" * 64,
                "journalPath": str(self.base / "journal"),
                "outputPath": str(self.base / "output"),
                "readerJournalPath": str(self.base / "reader"),
            }
        )
        with self.assertRaisesRegex(q.QualificationError, "qualification_owner_approval"):
            q.qualify(
                packet,
                digest(packet),
                self.document("consent-template.json"),
                self.fail,
                packet["journalPath"],
                now=lambda: now,
            )
        for key in ("databaseId", "existingDatabaseId"):
            candidate = {**packet, key: "11111111-2222-3333-4444-555555555555"}
            consent = {
                "approved": True,
                "decisionRef": "synthetic",
                "packetSha256": digest(candidate),
            }
            with (
                self.subTest(field=key),
                self.assertRaisesRegex(q.QualificationError, "packet_fields"),
            ):
                q.qualify(
                    candidate,
                    digest(candidate),
                    consent,
                    self.fail,
                    packet["journalPath"],
                    now=lambda: now,
                )
        self.assertFalse((self.base / "journal").exists())

    def test_every_artifact_byte_and_semantic_tamper_is_refused(self):
        self.prepare()
        for name in p.FILES:
            path = self.stage / name
            original = path.read_bytes()
            for altered in (original + b"\n", canonical({"approved": True})):
                with self.subTest(file=name):
                    path.write_bytes(altered)
                    with self.assertRaises(ValueError):
                        p.verify(self.stage)
            path.write_bytes(original)

    def test_invented_retention_and_evidence_claims_cannot_verify(self):
        self.prepare()
        path = self.stage / "recipe.json"
        original = self.document("recipe.json")
        for key, value in (
            ("cleanupVerified", True),
            ("providerNotFoundMeaning", "erasure_proved"),
            ("retentionHours", 0),
            ("effectiveGrantsVerified", True),
        ):
            altered = copy.deepcopy(original)
            altered[key] = value
            path.write_bytes(canonical(altered))
            with self.subTest(field=key), self.assertRaises(ValueError):
                p.verify(self.stage, digest(altered))

    def test_extra_missing_and_directory_stage_members_are_refused(self):
        self.prepare()
        extra = self.stage / "unexpected.json"
        extra.write_bytes(b"{}")
        with self.assertRaises(ValueError):
            p.verify(self.stage)
        extra.unlink()
        extra.mkdir()
        with self.assertRaises(ValueError):
            p.verify(self.stage)
        extra.rmdir()
        (self.stage / "source-pins.json").unlink()
        with self.assertRaises(ValueError):
            p.verify(self.stage)

    def test_existing_and_inside_source_destinations_refuse_without_writes(self):
        self.stage.mkdir()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(list(self.stage.iterdir()), [])
        root = self.synthetic_root()
        with self.assertRaises(ValueError):
            p.prepare(root / "stage", root=root)
        self.assertFalse((root / "stage").exists())

    def test_missing_public_source_refuses_before_stage_creation(self):
        root = self.synthetic_root()
        (root / "scripts" / "private_d1_snapshot_codec.py").unlink()
        with self.assertRaises(ValueError):
            p.prepare(self.stage, root=root)
        self.assertFalse(self.stage.exists())

    def test_fresh_staged_packet_admits_current_qualifier_and_rejects_helper_drift(self):
        self.prepare()
        packet = self.document("packet-template.json")
        now = datetime(2026, 10, 19, tzinfo=UTC)
        packet.update(
            {
                "runId": "a" * 32,
                "accountId": "b" * 32,
                "endpointAddress": "1.1.1.1",
                "startsAt": now.isoformat().replace("+00:00", "Z"),
                "expiresAt": (now + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
                "providerTokenExpiresAt": (now + timedelta(hours=1))
                .isoformat()
                .replace("+00:00", "Z"),
                "credentialBinding": "c" * 64,
                "grantEvidenceSha256": "d" * 64,
                "privateCustodySha256": "e" * 64,
                "journalPath": str(self.base / "journal"),
                "outputPath": str(self.base / "output"),
                "readerJournalPath": str(self.base / "reader"),
            }
        )
        consent = {
            "approved": True,
            "decisionRef": "synthetic admission only",
            "packetSha256": digest(packet),
        }
        self.assertEqual(len(self.document("source-pins.json")), 15)
        self.assertEqual(len(packet["sourceSha256"]), 14)
        address, end = q._prepare(packet, digest(packet), consent, now)
        self.assertEqual(str(address), "1.1.1.1")
        self.assertEqual(end, now + timedelta(minutes=20))
        for name in q.EVIDENCE_SOURCE_FILES:
            changed = copy.deepcopy(packet)
            changed["sourceSha256"][name] = "0" * 64
            changed_consent = {**consent, "packetSha256": digest(changed)}
            with (
                self.subTest(source=name),
                self.assertRaisesRegex(q.QualificationError, "^qualification_source_pin$"),
            ):
                q._prepare(changed, digest(changed), changed_consent, now)
        self.assertFalse((self.base / "journal").exists())


if __name__ == "__main__":
    unittest.main()
