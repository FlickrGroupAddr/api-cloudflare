"""Synthetic issuer invariants; no real credential, ACL, DNS or provider access."""

from __future__ import annotations

import copy
import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import hosted_publisher_execution as execution
from scripts import provision_work_plan_token as issuer
from scripts.hosted_publisher_finite_client import Response
from scripts.hosted_publisher_operator import DurableJournal, OperatorRefused

PARENT = b"synthetic-bootstrap-credential-A123456789"
CHILD = b"synthetic-execution-credential-B123456789"
PARENT_ID = "a" * 32
CHILD_ID = "b" * 32
ACCOUNT = "c" * 32
START = "2026-10-19T12:00:00Z"
END = "2026-10-19T12:10:00Z"
CHILD_END = "2026-10-19T13:00:00Z"
NOW = datetime(2026, 10, 19, 12, 1, tzinfo=UTC).timestamp()
IDS = {name: str(index) * 32 for index, name in enumerate(issuer.GROUP_SCOPES, 1)}
REAL_SOURCE_CHECK = issuer._validate_source


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode()


def envelope(value, **extra):
    return {"success": True, "errors": [], "messages": [], "result": value, **extra}


def response(value):
    raw = encoded(value)
    return Response(200, {"content-type": "application/json"}, raw, len(raw) + 100)


class IssuerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-issuer-synthetic-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(socket, "socket", side_effect=AssertionError("network forbidden")).start()
        patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")).start()
        # Windows ACL calls are intentionally replaced for synthetic temporary fixtures.
        patch.object(execution, "_windows_private").start()
        patch.object(issuer, "_validate_source").start()
        self.now = NOW
        self.tick = 100.0
        self.calls = []
        self.plan = {
            "schema_version": 1,
            "purpose": "work_plan_local_token_admin",
            "owner": "Terry",
            "operation": "issue",
            "profile": issuer.PROFILE,
            "account_id": ACCOUNT,
            "source_commit": "d" * 40,
            "source_sha2_256": {name: "e" * 64 for name in issuer.SOURCE_FILES},
            "starts_at": START,
            "expires_at": END,
            "cleanup_at": CHILD_END,
            "child_expires_at": CHILD_END,
            "child_name": "synthetic-execution",
            "child_condition": {},
            "parent_condition": {},
            "parent_id": None,
            "parent_sha2_256": issuer.boundary.sha2_256(PARENT),
            "api_address": "1.1.1.1",
            "parent_credential": str(self.root / "parent.txt"),
            "child_credential": str(self.root / "child.txt"),
            "claim": str(self.root / "claim"),
            "journal": str(self.root / "journal.sqlite"),
            "evidence": str(self.root / "evidence.jsonl"),
            "retention_until": "2026-10-26T12:00:00Z",
            "revoker": "Terry",
            "issuance": None,
            "request_limit": issuer.MAX_REQUESTS,
            "request_byte_limit": issuer.MAX_REQUEST_BYTES,
            "response_byte_limit": issuer.MAX_TOTAL_RESPONSE_BYTES,
        }
        self.write("parent.txt", PARENT)
        self.human = self.root / "human.txt"
        self.human.write_bytes(b"SYNTHETIC independently retained owner decision")
        self.approval = {
            "schema_version": 1,
            "decision_id": issuer.DECISION,
            "owner": "Terry",
            "plan_digest": "",
            "source_commit": self.plan["source_commit"],
            "provisioning": "authorized_automated_local_issuance",
            "bootstrap_role": "user_wide_token_management_write_local_only",
            "human_evidence_sha2_256": issuer.boundary.sha2_256(self.human.read_bytes()),
            "recorded_at": START,
            "expires_at": END,
        }
        self.refresh()
        self.parent_verify = {
            "id": PARENT_ID,
            "status": "active",
            "not_before": START,
            "expires_on": "2026-10-26T12:00:00Z",
        }
        self.parent_details = {
            **self.parent_verify,
            "name": "synthetic-bootstrap",
            "issued_on": START,
            "policies": issuer._policies(self.plan, IDS, parent=True),
        }
        self.child_details = {
            "id": CHILD_ID,
            "status": "active",
            "name": self.plan["child_name"],
            "issued_on": "2026-10-19T12:00:30.123456789Z",
            "not_before": START,
            "expires_on": CHILD_END,
            "policies": issuer._policies(self.plan, IDS),
        }
        self.catalog = envelope(
            [
                {
                    "id": value,
                    "name": name,
                    "scopes": [issuer.GROUP_SCOPES[name]],
                    "category": "Account" if "account" in issuer.GROUP_SCOPES[name] else "User",
                    "is_selectable": True,
                    "description": "Synthetic documented optional field",
                }
                for name, value in IDS.items()
            ],
            result_info={"count": 3, "page": 1, "per_page": 50, "total_count": 3, "total_pages": 1},
        )
        self.create = envelope({"id": CHILD_ID, "value": CHILD.decode()})
        self.responses: list[Any] = [
            envelope(self.parent_verify),
            self.catalog,
            envelope(self.parent_details),
            self.create,
            envelope(self.child_details),
        ]

    def write(self, name, value):
        path = self.root / name
        path.write_bytes(value if isinstance(value, bytes) else encoded(value))
        return path

    def refresh(self):
        path = self.write("plan.json", self.plan)
        digest = issuer.boundary.sha2_256(path.read_bytes())
        self.approval["plan_digest"] = digest
        approval = self.write("approval.json", self.approval)
        self.inputs = issuer.RuntimeInputs(
            path,
            digest,
            approval,
            issuer.boundary.sha2_256(approval.read_bytes()),
            self.human,
            self.source,
        )

    def transport(self, request):
        self.calls.append(request)
        value = self.responses[len(self.calls) - 1]
        if isinstance(value, BaseException):
            raise value
        if callable(value):
            value = value(request)
        return value if isinstance(value, Response) else response(value)

    def run_issuer(self):
        return issuer.run(
            self.inputs,
            wall_clock=lambda: self.now,
            monotonic=lambda: self.tick,
            transport=self.transport,
        )

    def stopped(self, count=None):
        with self.assertRaises(issuer.ProvisioningRefused) as caught:
            self.run_issuer()
        if count is not None:
            self.assertEqual(len(self.calls), count)
        self.assertIsNone(caught.exception.__context__)
        return caught.exception

    def journal(self, path=None, digest=None):
        with DurableJournal(
            Path(path or self.plan["journal"]), digest or self.inputs.plan_digest
        ) as ledger:
            return ledger.snapshot()

    def prepare_revoke(self):
        original_path = self.plan["journal"]
        original_digest = self.inputs.plan_digest
        self.plan.update(
            operation="revoke",
            parent_id=PARENT_ID,
            issuance={
                "journal": original_path,
                "plan_digest": original_digest,
                "child_id": CHILD_ID,
            },
            journal=str(self.root / "revoke.sqlite"),
            claim=str(self.root / "revoke.claim"),
            evidence=str(self.root / "revoke.jsonl"),
        )
        self.refresh()
        self.calls.clear()
        self.responses = [
            envelope(self.parent_verify),
            self.catalog,
            envelope(self.parent_details),
            envelope(self.child_details),
            envelope({"id": CHILD_ID}),
        ]
        return original_path, original_digest

    def test_issue_exact_profile_authenticated_self_identity_and_private_delivery(self):
        result = self.run_issuer()
        self.assertEqual(result["requests"], 5)
        self.assertEqual(Path(self.plan["child_credential"]).read_bytes(), CHILD)
        methods = [request.wire.split(b" ", 1)[0] for request in self.calls]
        self.assertEqual(methods, [b"GET", b"GET", b"GET", b"POST", b"GET"])
        self.assertTrue(self.calls[2].url.endswith(PARENT_ID))
        body = json.loads(self.calls[3].wire.split(b"\r\n\r\n")[1])
        self.assertEqual(body["policies"], issuer._policies(self.plan, IDS))
        self.assertEqual(body["expires_on"], CHILD_END)
        self.assertEqual(self.journal()["issuer:mutation"]["receipt"]["childId"], CHILD_ID)
        evidence = Path(self.plan["evidence"]).read_bytes()
        self.assertNotIn(PARENT, evidence)
        self.assertNotIn(CHILD, evidence)
        self.assertIn(b"authorized_automated_local_issuance", evidence)
        self.assertNotIn(b"owner_provisioned", evidence)

    def test_no_replay_after_success(self):
        self.run_issuer()
        self.calls.clear()
        self.stopped(0)

    def test_unknown_post_retains_durable_intent_and_never_delivers_or_retries(self):
        def lost(_):
            raise RuntimeError(PARENT.decode() + CHILD.decode())

        self.responses[3] = lost
        caught = self.stopped(4)
        self.assertNotIn(PARENT.decode(), str(caught))
        self.assertEqual(self.journal()["issuer:mutation"]["state"], "unknown")
        self.assertFalse(Path(self.plan["child_credential"]).exists())
        self.calls.clear()
        self.stopped(0)

    def test_intent_precedes_actual_post_dispatch(self):
        seen = []
        original = DurableJournal.reserve

        def reserve(journal, key, payload):
            result = original(journal, key, payload)
            if key == "issuer:mutation":
                seen.append((result, journal.snapshot()[key]["state"]))
            return result

        def created(_):
            self.assertEqual(seen, [(True, "intent")])
            return self.create

        self.responses[3] = created
        with patch.object(DurableJournal, "reserve", reserve):
            self.run_issuer()

    def test_closed_plan_and_decision_and_fingerprint_fail_before_mutation(self):
        for key, value in (
            ("profile", "arbitrary"),
            ("account_id", "*"),
            ("request_limit", True),
            ("request_limit", 6),
            ("child_expires_at", "2026-10-27T12:00:00Z"),
            ("child_condition", {"request_ip": {"in": ["0.0.0.0/0"]}}),
        ):
            with self.subTest(key=key, value=value):
                before = copy.deepcopy(self.plan)
                self.plan[key] = value
                self.refresh()
                self.stopped(0)
                self.plan = before
        self.approval["decision_id"] = "invented"
        self.refresh()
        self.stopped(0)
        self.approval["decision_id"] = issuer.DECISION
        self.plan["parent_sha2_256"] = "f" * 64
        self.refresh()
        self.stopped(0)

    def test_authentic_parent_policy_identity_and_actual_lifetime_required(self):
        variants = [
            ("expires_on", "2026-10-26T12:00:00.000000001Z"),
            ("issued_on", "2026-10-19T11:59:59.999999999Z"),
            ("id", "f" * 32),
            ("policies", issuer._policies(self.plan, IDS)),
            ("condition", {"request_ip": {"in": ["1.1.1.1/32"]}}),
        ]
        for key, value in variants:
            with self.subTest(key=key):
                altered = copy.deepcopy(self.parent_details)
                altered[key] = value
                self.responses[2] = envelope(altered)
                # Each case needs fresh sinks; preflight is consumed even on refusal.
                self.plan.update(
                    journal=str(self.root / f"j-{key}"),
                    evidence=str(self.root / f"e-{key}"),
                    claim=str(self.root / f"c-{key}"),
                )
                self.refresh()
                self.calls.clear()
                self.stopped(3)

    def test_catalog_ambiguity_scope_selectability_missing_or_unknown_fields_refuse(self):
        variants = []
        duplicate = copy.deepcopy(self.catalog)
        duplicate["result"].append(copy.deepcopy(duplicate["result"][0]))
        variants.append(duplicate)
        for key, value in (
            ("scopes", ["com.cloudflare.api.zone"]),
            ("is_selectable", False),
            ("unknown", "extra"),
        ):
            altered = copy.deepcopy(self.catalog)
            altered["result"][1][key] = value
            variants.append(altered)
        missing = copy.deepcopy(self.catalog)
        missing["result"].pop()
        variants.append(missing)
        for value in variants:
            with self.subTest(value=value["result"][0].keys()):
                with self.assertRaises(OperatorRefused):
                    issuer.permission_ids(response(value))

    def test_catalog_nullable_category_and_lf_description_keep_exact_profile(self):
        self.catalog["result"].insert(
            0,
            {
                "id": "f" * 32,
                "name": "Synthetic Unrelated Read",
                "scopes": ["com.cloudflare.api.account.zone"],
                "category": None,
                "is_selectable": True,
                "description": "Synthetic first line\nsecond line\n",
            },
        )
        self.catalog["result_info"]["count"] = 4
        self.catalog["result_info"]["total_count"] = 4
        self.assertEqual(issuer.permission_ids(response(self.catalog)), IDS)
        self.run_issuer()
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(
            json.loads(self.calls[3].wire.split(b"\r\n\r\n")[1])["policies"],
            issuer._policies(self.plan, IDS),
        )

    def test_catalog_prose_compatibility_keeps_types_controls_and_byte_bounds(self):
        for key, value in (
            ("category", []),
            ("category", 1),
            ("category", "Synthetic\ncategory"),
            ("description", None),
            ("description", []),
            ("description", "Synthetic\r\nline"),
            ("description", "Synthetic\tline"),
            ("description", "Synthetic\x00line"),
            ("description", "Synthetic\x1bline"),
            ("description", "Synthetic\x7fline"),
            ("description", "\n" * 4097),
            ("description", "é" * 2048 + "\n"),
        ):
            with self.subTest(key=key, kind=type(value).__name__):
                altered = copy.deepcopy(self.catalog)
                altered["result"][1][key] = value
                with self.assertRaises(OperatorRefused):
                    issuer.permission_ids(response(altered))

    def test_catalog_prose_compatibility_does_not_alias_names_or_scopes(self):
        for key, value in (
            ("name", "D1 Edit"),
            ("name", "D1 Write\n"),
            ("scopes", ["com.cloudflare.api.account.zone"]),
        ):
            with self.subTest(key=key):
                altered = copy.deepcopy(self.catalog)
                altered["result"][1].update(category=None, description="Synthetic\nprose")
                altered["result"][1][key] = value
                with self.assertRaises(OperatorRefused):
                    issuer.permission_ids(response(altered))

    def test_child_wrong_actual_policy_expiry_or_identity_never_delivers(self):
        for key, value in (
            ("expires_on", "2026-10-19T13:00:00.000000001Z"),
            ("id", "f" * 32),
            ("policies", issuer._policies(self.plan, IDS, parent=True)),
            ("issued_on", "2026-10-19T11:59:59Z"),
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.child_details)
                changed[key] = value
                self.responses[4] = envelope(changed)
                self.plan.update(
                    journal=str(self.root / f"j-{key}"),
                    evidence=str(self.root / f"e-{key}"),
                    claim=str(self.root / f"c-{key}"),
                )
                self.refresh()
                self.calls.clear()
                self.stopped(5)
                self.assertEqual(self.journal()["issuer:mutation"]["state"], "complete")
                self.assertFalse(Path(self.plan["child_credential"]).exists())

    def test_secret_delivery_race_is_exclusive_and_known_id_survives(self):
        def replaced(_):
            Path(self.plan["child_credential"]).write_bytes(b"synthetic-existing-do-not-overwrite")
            return envelope(self.child_details)

        self.responses[4] = replaced
        self.stopped(5)
        self.assertEqual(
            Path(self.plan["child_credential"]).read_bytes(), b"synthetic-existing-do-not-overwrite"
        )
        self.assertEqual(self.journal()["issuer:mutation"]["receipt"]["childId"], CHILD_ID)

    def test_bad_secret_still_preserves_acknowledged_id_for_separate_revoke(self):
        self.responses[3] = envelope({"id": CHILD_ID, "value": "malformed"})
        self.stopped(4)
        self.assertEqual(self.journal()["issuer:mutation"]["receipt"]["childId"], CHILD_ID)

    def test_exact_id_revoke_and_no_inferred_parent_cascade(self):
        self.run_issuer()
        original, digest = self.prepare_revoke()
        self.run_issuer()
        self.assertEqual(self.calls[-1].wire.split(b" ", 1)[0], b"DELETE")
        self.assertTrue(self.calls[-1].url.endswith(CHILD_ID))
        self.assertEqual(self.journal(original, digest)["issuer:retire"]["state"], "complete")
        self.assertEqual(Path(self.plan["parent_credential"]).read_bytes(), PARENT)

    def test_revoke_ownership_tampering_never_dispatches_child_read_or_delete(self):
        self.run_issuer()
        self.prepare_revoke()
        self.plan["issuance"]["child_id"] = "f" * 32
        self.refresh()
        self.stopped(3)

    def test_unknown_delete_spends_original_child_retirement_across_fresh_packets(self):
        self.run_issuer()
        original, digest = self.prepare_revoke()
        self.responses[4] = RuntimeError("synthetic lost delete")
        self.stopped(5)
        self.assertEqual(self.journal(original, digest)["issuer:retire"]["state"], "intent")
        self.plan.update(
            journal=str(self.root / "another.sqlite"),
            claim=str(self.root / "another.claim"),
            evidence=str(self.root / "another.jsonl"),
        )
        self.refresh()
        self.calls.clear()
        self.stopped(3)

    def test_unsafe_alias_and_changed_authority_block_dispatch(self):
        self.plan["evidence"] = self.plan["parent_credential"]
        self.refresh()
        self.stopped(0)
        self.plan["evidence"] = str(self.root / "evidence.jsonl")
        self.refresh()

        def changed(_):
            self.inputs.approval.write_bytes(b"SYNTHETIC changed authority")
            return envelope(self.parent_verify)

        self.responses[0] = changed
        self.stopped(1)

    def test_late_or_excess_response_and_time_jump_block_mutation(self):
        def late(_):
            self.tick += 21
            return envelope(self.parent_verify)

        self.responses[0] = late
        self.stopped(1)

    def test_response_wire_budget_refuses_before_mutation(self):
        raw = response(envelope(self.parent_verify))
        self.responses[0] = Response(
            raw.status, raw.headers, raw.body, issuer.MAX_RESPONSE_BYTES + 1
        )
        self.stopped(1)

    def test_duplicate_create_fields_are_unresolved_and_not_replayed(self):
        raw = (
            b'{"success":true,"errors":[],"messages":[],"result":'
            b'{"id":"'
            + CHILD_ID.encode()
            + b'","id":"'
            + b"f" * 32
            + b'","value":"'
            + CHILD
            + b'"}}'
        )
        self.responses[3] = Response(200, {"content-type": "application/json"}, raw, len(raw))
        self.stopped(4)
        self.assertEqual(self.journal()["issuer:mutation"]["state"], "intent")
        self.assertFalse(Path(self.plan["child_credential"]).exists())

    def test_existing_secret_delivery_refuses_before_parent_use(self):
        Path(self.plan["child_credential"]).write_bytes(b"synthetic-existing-secret")
        self.stopped(0)

    def test_child_cannot_outlive_actual_parent(self):
        self.parent_verify["expires_on"] = "2026-10-19T12:30:00Z"
        self.parent_details["expires_on"] = self.parent_verify["expires_on"]
        self.stopped(3)

    def test_source_or_private_qualification_failure_prevents_secret_load(self):
        with patch.object(
            issuer, "_validate_source", side_effect=OperatorRefused("source_changed")
        ):
            self.stopped(0)
        with patch.object(issuer, "_assert_private", side_effect=OperatorRefused("unsafe_file")):
            self.stopped(0)

    def test_existing_parent_group_need_not_be_selectable_for_child_issuance(self):
        self.catalog["result"][0]["is_selectable"] = False
        self.run_issuer()

    def test_source_commit_and_digest_mismatch_refuse(self):
        plan = copy.deepcopy(self.plan)
        name = "scripts/provision_work_plan_token.py"
        raw = b"synthetic source closure"
        with (
            patch.object(issuer.metadata, "_validate_source"),
            patch.object(issuer.packet, "bounded_read", return_value=raw),
            patch.object(issuer.offline, "_git", return_value=""),
        ):
            with self.assertRaises(OperatorRefused):
                REAL_SOURCE_CHECK(self.source, plan)
        identity = issuer.hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        with (
            patch.object(issuer.metadata, "_validate_source"),
            patch.object(issuer.packet, "bounded_read", return_value=raw),
            patch.object(issuer.offline, "_git", return_value=f"100644 blob {identity}\t{name}"),
        ):
            with self.assertRaises(OperatorRefused):
                REAL_SOURCE_CHECK(self.source, plan)
            plan["source_sha2_256"][name] = issuer.boundary.sha2_256(raw)
            REAL_SOURCE_CHECK(self.source, plan)

    def test_no_secret_in_stdout_stderr_or_exception(self):
        self.responses[3] = RuntimeError(PARENT.decode() + CHILD.decode())
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            failure = self.stopped(4)
        for raw in (out.getvalue(), err.getvalue(), str(failure)):
            self.assertNotIn(PARENT.decode(), raw)
            self.assertNotIn(CHILD.decode(), raw)


if __name__ == "__main__":
    unittest.main()
