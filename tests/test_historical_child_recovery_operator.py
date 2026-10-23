"""Invented evidence, temp files and blocked sockets; no actual readiness claims."""

from __future__ import annotations

import contextlib
import copy
import dataclasses
import sqlite3
import stat
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import historical_child_recovery as recovery
from scripts import historical_child_recovery_operator as operator
from scripts import provision_work_plan_token as issuer
from tests import test_historical_child_recovery as synthetic
from tests import test_provision_work_plan_token as base

ROOT = Path(__file__).resolve().parents[1]


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = synthetic.RecoveryTests(
            "test_inert_default_and_prepare_have_no_dispatch_or_credential_reads"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.req = copy.deepcopy(f.req)
        self.req["sourceRoot"] = ROOT.as_posix()
        self.pins = {
            name: recovery.digest((ROOT / name).read_bytes()) for name in issuer.SOURCE_FILES
        }
        self.req["sourcePins"] = {(ROOT / name).as_posix(): pin for name, pin in self.pins.items()}
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
        )
        self.op = operator.Operator(self.raw, facts=self.facts)
        # Production ACL implementation is loaded from exact bytes; temporary
        # fixture ACL truth is deliberately not a claim about protected inputs.
        self.addCleanup(patch.stopall)
        patch.object(
            self.op,
            "_private",
            side_effect=lambda path, **kw: operator._regular(
                Path(path), directory=kw.get("directory", False)
            ),
        ).start()
        patch.object(
            self.op, "_read", side_effect=lambda path, limit: Path(path).read_bytes()
        ).start()

    def test_prepare_real_role_inventory_source_and_sqlite_latch(self):
        packet = recovery.prepare(
            self.raw, expected_digest=self.facts.request_digest, verifier=self.op, now=synthetic.NOW
        )
        self.assertEqual(recovery.document(packet.plan)["operation"], "revoke_expired")
        self.assertEqual(
            Path(self.req["roles"]["terminal"]).read_bytes(), self.fixture.records["terminal"]
        )
        self.assertEqual(self.fixture.fixture.calls, [])

    def test_source_loader_ignores_ambient_forged_producer(self):
        producer = self.op.producer()
        self.assertIsNot(producer, issuer)
        self.assertIsNot(producer.metadata, issuer.metadata)
        self.assertEqual(
            producer.__file__, (ROOT / "scripts/provision_work_plan_token.py").as_posix()
        )
        self.assertEqual(producer.MAX_REQUESTS, 5)
        self.assertEqual(producer.SOURCE_FILES, issuer.SOURCE_FILES)
        self.op.sources.recheck()

    def test_loaded_code_mutation_is_refused(self):
        producer = self.op.producer()
        producer.run.__code__ = (lambda *args, **kwargs: "forged").__code__
        with self.assertRaisesRegex(recovery.Refused, "loaded_code_not_pinned"):
            self.op.sources.recheck()

    def test_source_global_replacement_refused(self):
        producer = self.op.producer()
        producer.__dict__["MAX_REQUESTS"] = 6
        with self.assertRaisesRegex(recovery.Refused, "loaded_module_changed"):
            self.op.sources.recheck()

    def test_source_bytes_mutation_before_import_refuses(self):
        self.op.sources.raw["scripts.provision_work_plan_token"] = (
            b"raise RuntimeError('must not execute')"
        )
        with self.assertRaisesRegex(recovery.Refused, "import_bytes_changed"):
            self.op.producer()

    def test_missing_own_source_and_missing_producer_closure_refuse(self):
        for path in (
            Path(operator.__file__).as_posix(),
            (ROOT / issuer.SOURCE_FILES[0]).as_posix(),
        ):
            req = copy.deepcopy(self.req)
            req["sourcePins"].pop(path)
            raw = recovery.encoded(req)
            facts = dataclasses.replace(self.facts, request_digest=recovery.digest(raw))
            with self.assertRaises(recovery.Refused):
                operator.Operator(raw, facts=facts)

    def test_case_alias_and_ancestor_fact_roles_refuse_before_read(self):
        for value in (
            self.req["roles"]["parentCredential"].upper().replace("C:", "C:"),
            self.req["namespace"] + "/fact",
            ROOT.as_posix() + "/fact",
        ):
            refs = dict(self.facts.fact_evidence)
            refs["identityCustody"] = operator.EvidenceRef(value, "0" * 64)
            with self.assertRaises(recovery.Refused):
                operator.Operator(
                    self.raw, facts=dataclasses.replace(self.facts, fact_evidence=refs)
                )

    def test_missing_fact_refuses_inventory_and_changed_fact_refuses_authentication(self):
        ref = self.facts.fact_evidence["consumerTermination"]
        Path(ref.path).unlink()
        with self.assertRaises(recovery.Refused):
            self.op.inventory(self.req["roles"], self.req["namespace"])

    def test_fact_byte_drift_and_missing_current_binding_refuse(self):
        self.op.inventory(self.req["roles"], self.req["namespace"])
        Path(self.facts.fact_evidence["parentLifetime"].path).write_bytes(b"changed")
        with self.assertRaisesRegex(recovery.Refused, "fact_evidence_changed"):
            self.op.authenticate(
                "current",
                self.raw,
                {
                    role: Path(self.req["roles"][role]).read_bytes()
                    for role in recovery.HISTORY | recovery.CURRENT
                },
            )
        with self.assertRaises(recovery.Refused):
            operator.Operator(self.raw, facts=dataclasses.replace(self.facts, current_pins={}))

    def test_metadata_adapter_never_reads_parent_or_child(self):
        for role in ("parentCredential", "childCredential", "issuerJournal", "other"):
            with self.assertRaises(recovery.Refused):
                self.op.read_metadata(role, self.req["roles"].get(role, "C:/other"), 2048)

    def test_original_latch_read_is_byte_preserving_and_used_states_refuse(self):
        path = Path(self.req["roles"]["issuerJournal"])
        original = path.read_bytes()
        for state in ("intent", "unknown", "complete", "unused", "", "malformed"):
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                db.execute("DELETE FROM intents WHERE key='issuer:retire'")
                db.execute("INSERT INTO intents VALUES ('issuer:retire', ?, '{}', '{}')", (state,))
            before = path.read_bytes()
            with self.assertRaisesRegex(recovery.Refused, "latch_not_unused"):
                recovery.prepare(
                    self.raw,
                    expected_digest=self.facts.request_digest,
                    verifier=self.op,
                    now=synthetic.NOW,
                )
            self.assertEqual(path.read_bytes(), before)
        path.write_bytes(original)
        self.op.original_latch(path.as_posix(), self.req["pins"]["issuerPlan"], self.req["childId"])
        self.assertEqual(path.read_bytes(), original)

    def test_existing_namespace_and_issuer_sidecar_refuse(self):
        namespace = Path(self.req["namespace"])
        namespace.mkdir()
        with self.assertRaises(recovery.Refused):
            recovery.prepare(
                self.raw,
                expected_digest=self.facts.request_digest,
                verifier=self.op,
                now=synthetic.NOW,
            )
        namespace.rmdir()
        Path(self.req["roles"]["issuerWal"]).write_bytes(b"occupied")
        with self.assertRaises(recovery.Refused):
            self.op.original_latch(
                self.req["roles"]["issuerJournal"],
                self.req["pins"]["issuerPlan"],
                self.req["childId"],
            )

    def test_writer_exclusive_partial_failure_has_no_retry_or_cleanup(self):
        self.op.reserve_exclusive(self.req["namespace"])
        with self.assertRaises(recovery.Refused):
            self.op.reserve_exclusive(self.req["namespace"])
        with patch.object(self.op.sources, "load", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.op.create_exclusive(self.req["roles"]["plan"], b"partial")
        with self.assertRaises(recovery.Refused):
            self.op.create_exclusive(self.req["roles"]["plan"], b"retry")
        self.assertTrue(Path(self.req["namespace"]).exists())

    def test_dispatch_default_and_unbound_packet_review_refuse(self):
        with self.assertRaisesRegex(recovery.Refused, "inert_default"):
            self.op.dispatch(
                None, packet_review=b"", clock=lambda: synthetic.NOW, monotonic=lambda: 0
            )
        with self.assertRaisesRegex(recovery.Refused, "authenticated_packet_review_required"):
            self.op.authenticate(
                "dispatch",
                self.raw,
                {role: Path(self.req["roles"][role]).read_bytes() for role in recovery.CURRENT}
                | {"packetReview": b"synthetic unbound review"},
            )

    def test_support_reference_commitment_and_mutable_source_constants_refuse_drift(self):
        self.op.inventory(self.req["roles"], self.req["namespace"])
        records = {
            role: Path(self.req["roles"][role]).read_bytes()
            for role in recovery.HISTORY | recovery.CURRENT
        }
        self.op.facts.fact_evidence["identityCustody"] = self.facts.fact_evidence["parentLifetime"]
        with self.assertRaisesRegex(recovery.Refused, "fact_reference_not_bound"):
            self.op.authenticate("current", self.raw, records)
        producer = self.op.producer()
        producer.GROUP_SCOPES["API Tokens Write"] = "forged"
        with self.assertRaisesRegex(recovery.Refused, "loaded_constants_changed"):
            self.op.sources.recheck()

    def test_same_exact_support_record_can_prove_multiple_fact_meanings(self):
        ref = self.facts.fact_evidence["consumerTermination"]
        refs = {role: ref for role in operator.FACTS}
        op = operator.Operator(self.raw, facts=dataclasses.replace(self.facts, fact_evidence=refs))
        with patch.object(
            op,
            "_private",
            side_effect=lambda path, **kw: operator._regular(
                Path(path), directory=kw.get("directory", False)
            ),
        ):
            op.inventory(self.req["roles"], self.req["namespace"])
        self.assertEqual(set(op._fact_inventory), {ref.path})

    def test_actual_exclusive_metadata_writer_and_existing_bytes_preserved(self):
        self.op.reserve_exclusive(self.req["namespace"])
        helpers = self.op._helpers()
        with patch.object(helpers, "_windows_private"):
            self.assertEqual(
                self.op.create_exclusive(self.req["roles"]["plan"], b"exact bytes"), 11
            )
        with self.assertRaises(recovery.Refused):
            self.op.create_exclusive(self.req["roles"]["plan"], b"overwrite")
        self.assertEqual(Path(self.req["roles"]["plan"]).read_bytes(), b"exact bytes")

    def test_private_reader_refuses_replaced_inventory_identity(self):
        self.op.inventory(self.req["roles"], self.req["namespace"])
        path = self.req["roles"]["terminal"]
        target = Path(path)
        replacement = target.with_name("replacement")
        replacement.write_bytes(target.read_bytes())
        replacement.replace(target)
        with self.assertRaisesRegex(recovery.Refused, "inventory_identity_changed"):
            operator.Operator._read(self.op, path, 16777216)

    def test_pinned_import_refuses_missing_application_and_nonstdlib_modules(self):
        with self.assertRaises(recovery.Refused):
            self.op.sources.load("scripts.unreviewed")
        with self.assertRaises(recovery.Refused):
            self.op.sources._import("requests")

    def test_foreign_controller_function_operator_class_and_method_refuse(self):
        for owner, name, value in (
            (recovery, "_window", lambda *args, **kwargs: None),
            (operator, "EvidenceRef", type("Foreign", (), {})),
            (operator.Operator, "_private", lambda *args, **kwargs: None),
        ):
            with self.subTest(name=name), patch.object(owner, name, value):
                with self.assertRaisesRegex(recovery.Refused, "source_binding_changed"):
                    self.op.source_closure(self.req["sourcePins"])

    def test_controller_constants_and_bootstrap_import_replacement_refuse(self):
        for owner, name, value in (
            (recovery, "MAX_REQUESTS", 6),
            (operator, "uuid", object()),
        ):
            with self.subTest(name=name), patch.object(owner, name, value):
                with self.assertRaisesRegex(recovery.Refused, "ambient_.*changed"):
                    self.op.source_closure(self.req["sourcePins"])

    def test_stable_reader_replacement_gap_refuses_original_inventory_identity(self):
        self.op.inventory(self.req["roles"], self.req["namespace"])
        path = self.req["roles"]["terminal"]
        helpers = self.op._helpers()

        def replacing_reader(target, maximum):
            raw = target.read_bytes()
            replacement = target.with_name("race-replacement")
            replacement.write_bytes(raw)
            replacement.replace(target)
            return raw

        with patch.object(helpers, "_private_bytes", side_effect=replacing_reader):
            with self.assertRaisesRegex(recovery.Refused, "inventory_identity_changed"):
                operator.Operator._read(self.op, path, 16777216)

    def test_unknown_ancestor_reparse_tag_refuses(self):
        path = Path(self.req["roles"]["terminal"])
        original = Path.stat

        def reparse_ancestor(target, *args, **kwargs):
            info = original(target, *args, **kwargs)
            if target == path.parent:
                return types.SimpleNamespace(
                    st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT, st_mode=info.st_mode
                )
            return info

        with patch.object(Path, "stat", new=reparse_ancestor):
            with self.assertRaisesRegex(recovery.Refused, "reparse_refused"):
                operator._regular(path)

    def test_original_default_transport_parses_address_and_fences_connect_tls_send(self):
        packet = recovery.prepare(
            self.raw, expected_digest=self.facts.request_digest, verifier=self.op, now=synthetic.NOW
        )
        producer = self.op.producer()
        provider = self.op.sources.load("scripts.hosted_publisher_execution_provider")
        helpers = self.op._helpers()
        plan = recovery.document(packet.plan)
        root = self.fixture.root / "synthetic-default-tls"
        root.mkdir()
        for key in ("claim", "journal", "evidence"):
            plan[key] = (root / key).as_posix()
        approval = self.fixture.fixture.approval
        events = []

        def validate(*args, **kwargs):
            events.append("fence")
            return plan, approval

        class FakeSocket:
            def settimeout(self, timeout):
                self.timeout = timeout

            def connect(self, address):
                self.address = address
                events.append("connect")

            def sendall(self, wire):
                events.append("send")
                raise RuntimeError("synthetic stop before any actual send")

            def close(self):
                pass

        raw, tls = FakeSocket(), FakeSocket()

        class FakeContext:
            def wrap_socket(self, sock, server_hostname):
                self.hostname = server_hostname
                events.append("tls")
                return tls

        inputs = producer.RuntimeInputs(
            Path(self.req["roles"]["plan"]),
            recovery.digest(packet.plan),
            Path(self.req["roles"]["approval"]),
            recovery.digest(packet.approval),
            Path(self.req["roles"]["authority"]),
            ROOT,
        )
        with (
            patch.object(producer, "validate_inputs", side_effect=validate),
            patch.object(helpers, "_windows_private"),
            patch.object(provider.socket, "socket", return_value=raw) as socket_factory,
            patch.object(provider.ssl, "create_default_context", return_value=FakeContext()),
        ):
            with self.assertRaises(producer.ProvisioningRefused):
                producer.run(
                    inputs,
                    wall_clock=lambda: synthetic.NOW.timestamp(),
                    monotonic=lambda: 100.0,
                    transport=None,
                    credential_loader=lambda path, maximum: base.PARENT,
                )
        self.assertEqual(raw.address, (plan["api_address"], 443))
        self.assertEqual(
            socket_factory.call_args.args, (provider.socket.AF_INET, provider.socket.SOCK_STREAM)
        )
        for stage in ("connect", "tls", "send"):
            self.assertEqual(events[events.index(stage) - 1], "fence")


if __name__ == "__main__":
    unittest.main()
