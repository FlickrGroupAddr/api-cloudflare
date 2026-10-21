"""Synthetic retained-evidence boundary tests; no native or provider actions."""

import copy
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts import hosted_publisher_execution as execution
from scripts import post_screenshot_admission as admission
from scripts.hosted_publisher_operator import OperatorRefused

NOW = datetime(2026, 10, 21, 16, tzinfo=UTC).timestamp()
PIN = "a" * 64
TOKEN = b"synthetic_child_token_123456789"
PARENT_TOKEN = b"synthetic_parent_token_123456789"


def timestamp(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


def envelope(value):
    return {"success": True, "errors": [], "messages": [], "result": value}


def review(subjects):
    return {
        "schemaVersion": 1,
        "author": "author",
        "reviewer": "independent",
        "verdict": "pass",
        "subjects": subjects,
    }


class Fixture:
    def __init__(self, root):
        self.root = root
        self.private = root / "private"
        self.private.mkdir()
        self.config = {
            "schemaVersion": 1,
            "runId": "1" * 24,
            "runRoot": str(root),
            "coordinationRoot": str(root / "handshake"),
            "outputRoot": str(root / "output"),
            "nativeRoot": str(root / "native"),
            "tokenFile": str(self.private / "operator-token.txt"),
            "parentTokenFile": str(self.private / "parent-token.txt"),
            "evidencePath": str(self.private / "action-evidence.json"),
            "accountId": "2" * 32,
            "subdomain": "test-account",
            "actionDeadlineUnix": NOW + 1500,
            "windowId": 7,
            "scopeSha2_256": PIN,
            "credentialExpiryUnix": NOW + 1500,
            "credentialSha2_256": admission._digest(TOKEN),
            "parserProfile": "bounded-stateless-cookie-discard-v1",
        }
        self.bound = {
            k: v
            for k, v in self.config.items()
            if k
            in {
                "schemaVersion",
                "runId",
                "runRoot",
                "coordinationRoot",
                "outputRoot",
                "nativeRoot",
                "tokenFile",
                "evidencePath",
            }
        }
        self.documents = {}
        self.references = {}
        self.put("cells", b"synthetic reviewed cell source")
        self.config["runtimeCellsSha2_256"] = self.references["cells"]["sha2_256"]
        self.put(
            "native",
            {
                "schemaVersion": 1,
                "runId": self.config["runId"],
                "ownerPid": os.getpid(),
                "windowId": 7,
                "hostVersion": "15.6",
                "sdkVersion": "15.3",
                "hostBuild": "synthetic-build",
                "fixtureVersion": "0.0.1.1",
                "toolkitIdentifier": "com.sixbuckssolutions.fga.grouppost.v1.lrc15",
                "observedAtUnix": NOW - 1,
                "expiresAtUnix": NOW + 1500,
                "manifestSha2_256": PIN,
                "runtimeCellsSha2_256": self.config["runtimeCellsSha2_256"],
                "witness": "Bot Root",
                "authorityOwner": "Terry",
                "witnessReference": "synthetic actual UI inspection evidence",
                "observations": [
                    "current_source_equal",
                    "loaded_enabled",
                    "sole_operator",
                    "supported_full_window_inspected",
                    "fresh_native_paths",
                    "fresh_run_paths",
                    "runtime_cells_reviewed",
                ],
            },
        )
        self.config["nativePreflightSha2_256"] = self.references["native"]["sha2_256"]
        self.put(
            "custody",
            {
                "schemaVersion": 1,
                "runId": self.config["runId"],
                "owner": "Terry",
                "tokenFile": self.config["tokenFile"],
                "credentialSha2_256": self.config["credentialSha2_256"],
                "reviewReference": "synthetic-review",
                "observedAtUnix": NOW - 1,
                "expiresAtUnix": NOW + 1500,
                "delivery": "issuer_exclusive_new_private_file",
            },
        )
        self.config["custodyReviewSha2_256"] = self.references["custody"]["sha2_256"]
        self.put(
            "accountProvenance",
            {
                "schemaVersion": 1,
                "runId": self.config["runId"],
                "accountId": self.config["accountId"],
                "subdomain": self.config["subdomain"],
                "observedAtUnix": NOW - 1,
                "expiresAtUnix": NOW + 1500,
                "owner": "Terry",
                "sourceReference": "synthetic source",
            },
        )
        self.plan = {
            "schema_version": 1,
            "purpose": "work_plan_local_token_admin",
            "owner": "Terry",
            "operation": "issue",
            "profile": admission.issuer.PROFILE,
            "account_id": self.config["accountId"],
            "source_commit": "3" * 40,
            "source_sha2_256": {name: PIN for name in admission.issuer.SOURCE_FILES},
            "starts_at": timestamp(NOW - 120),
            "expires_at": timestamp(NOW - 10),
            "cleanup_at": timestamp(NOW + 1500),
            "child_expires_at": timestamp(NOW + 1500),
            "child_name": "synthetic child",
            "child_condition": {},
            "parent_condition": {},
            "parent_id": "4" * 32,
            "parent_sha2_256": admission._digest(PARENT_TOKEN),
            "api_address": "1.1.1.1",
            "parent_credential": self.config["parentTokenFile"],
            "child_credential": self.config["tokenFile"],
            "claim": str(root / "issuer.claim"),
            "journal": str(root / "issuer.sqlite"),
            "evidence": str(root / "issuer.jsonl"),
            "retention_until": timestamp(NOW + 1500),
            "revoker": "Terry",
            "issuance": None,
            "request_limit": 5,
            "request_byte_limit": admission.issuer.MAX_REQUEST_BYTES,
            "response_byte_limit": admission.issuer.MAX_TOTAL_RESPONSE_BYTES,
        }
        self.put("issuerPlan", self.plan)
        self.put("issuerAuthority", b"synthetic human direction, authenticated outside JSON")
        self.put(
            "issuerApproval",
            {
                "schema_version": 1,
                "decision_id": admission.issuer.DECISION,
                "plan_digest": self.references["issuerPlan"]["sha2_256"],
                "source_commit": self.plan["source_commit"],
                "owner": "Terry",
                "provisioning": "authorized_automated_local_issuance",
                "bootstrap_role": "user_wide_token_management_write_local_only",
                "human_evidence_sha2_256": self.references["issuerAuthority"]["sha2_256"],
                "recorded_at": timestamp(NOW - 119),
                "expires_at": timestamp(NOW - 10),
            },
        )
        ids = {
            "API Tokens Write": "6" * 32,
            "D1 Write": "7" * 32,
            "Workers Scripts Write": "8" * 32,
        }
        parent = {
            "id": "4" * 32,
            "name": "synthetic parent",
            "status": "active",
            "issued_on": timestamp(NOW - 86400),
            "expires_on": "2026-10-26T12:00:00Z",
            "not_before": timestamp(NOW - 86400),
            "policies": admission.issuer._policies(self.plan, ids, parent=True),
        }
        child = {
            "id": "9" * 32,
            "name": self.plan["child_name"],
            "status": "active",
            "issued_on": timestamp(NOW - 100),
            "expires_on": timestamp(NOW + 1500),
            "not_before": self.plan["starts_at"],
            "policies": admission.issuer._policies(self.plan, ids),
        }
        self.ownership = {
            "childId": child["id"],
            "parentId": parent["id"],
            "parentFingerprint": self.plan["parent_sha2_256"],
            "accountId": self.config["accountId"],
            "profile": self.plan["profile"],
            "childExpiry": self.plan["child_expires_at"],
            "childName": self.plan["child_name"],
            "childCondition": {},
        }

        def verify(details):
            return {k: details[k] for k in ("id", "status", "expires_on", "not_before")}

        self.events = [
            {
                "plan_digest": self.references["issuerPlan"]["sha2_256"],
                "approval_digest": self.references["issuerApproval"]["sha2_256"],
                "decision_id": admission.issuer.DECISION,
                "source_commit": self.plan["source_commit"],
                "provisioning": "authorized_automated_local_issuance",
                "retention_until": self.plan["retention_until"],
            },
            {"phase": "parent_verify", "response": envelope(verify(parent))},
            {
                "phase": "permission_catalog",
                "response": envelope(
                    [
                        {"id": ids[name], "name": name, "scopes": [scope]}
                        for name, scope in admission.issuer.GROUP_SCOPES.items()
                    ]
                ),
            },
            {"phase": "parent_details", "response": envelope(parent)},
            {
                "phase": "create_acknowledged",
                "response": envelope({"id": child["id"]}),
                "ownership": self.ownership,
                "child_sha2_256": self.config["credentialSha2_256"],
            },
            {"phase": "child_details", "response": envelope(child)},
            {"phase": "delivery", "status": "exclusive_new_private_file_written"},
        ]
        self.put("issuerEvidence", b"\n".join(json.dumps(v).encode() for v in self.events) + b"\n")
        Path(self.config["parentTokenFile"]).write_bytes(PARENT_TOKEN)
        self.journal(populate_evidence=True)
        self.put(
            "issuerReview",
            review(
                {
                    k: self.references[k]["sha2_256"]
                    for k in (
                        "issuerPlan",
                        "issuerEvidence",
                        "issuerJournal",
                        "issuerApproval",
                        "issuerAuthority",
                    )
                }
            ),
        )
        self.put(
            "grant",
            {
                "schemaVersion": 1,
                "runId": self.config["runId"],
                "observedAtUnix": NOW - 1,
                "childSha2_256": self.config["credentialSha2_256"],
                "parentSha2_256": self.plan["parent_sha2_256"],
                "childVerify": verify(child),
                "parentVerify": verify(parent),
                "childDetails": child,
            },
        )
        self.config["credentialGrantSha2_256"] = self.references["grant"]["sha2_256"]
        self.put(
            "grantPlan",
            {
                "schema_version": 1,
                "purpose": "publisher_grant_metadata_evidence",
                "owner": "Terry",
                "source_commit": "3" * 40,
                "source_sha2_256": {name: PIN for name in admission.metadata.SOURCE_FILES},
                "starts_at": timestamp(NOW - 10),
                "expires_at": timestamp(NOW + 10),
                "api_address": "1.1.1.1",
                "test_credential": self.config["tokenFile"],
                "reader_credential": self.plan["parent_credential"],
                "evidence": str(self.private / "grantCollection.evidence"),
                "journal": str(root / "grant.sqlite"),
                "claim": str(root / "grant.claim"),
                "discovery": "test_verify_id_only",
                "actions": list(admission.metadata.ACTIONS),
            },
        )
        self.put(
            "grantCollection",
            {
                "schema_version": 1,
                "purpose": "provider_metadata_evidence_only",
                "plan_digest": self.references["grantPlan"]["sha2_256"],
                "approval_digest": "a" * 64,
                "source_commit": "3" * 40,
                "responses": dict(
                    zip(
                        admission.metadata.ACTIONS,
                        (envelope(verify(child)), envelope(verify(parent)), envelope(child)),
                        strict=True,
                    )
                ),
                "credential_sha2_256": {
                    "test": self.config["credentialSha2_256"],
                    "reader": self.plan["parent_sha2_256"],
                },
                "limitations": [
                    "reader_full_policy_not_observed",
                    "not_execution_authority",
                    "human_provenance_external",
                    "manual_revocation_required",
                ],
            },
        )
        self.put("sourceReview", review({"manifest": PIN}))
        self.put(
            "spentHistory",
            {
                "schemaVersion": 1,
                "observedAtUnix": NOW - 1,
                "owner": "Terry",
                "spentRunIds": ["b" * 24],
                "sourceReference": "synthetic complete history",
            },
        )
        self.config["spentRunIds"] = ["b" * 24]
        self.config["spentHistorySha2_256"] = self.references["spentHistory"]["sha2_256"]
        self.packet = self.private / "approved-packet.json"
        self.rebind()
        Path(self.config["tokenFile"]).write_bytes(TOKEN)

    def journal(self, *, state="complete", populate_evidence=False):
        """Use the actual issuer writer with fake source/ACL/transport boundaries."""
        for path in (
            self.plan["claim"],
            self.plan["journal"],
            self.plan["journal"] + ".owner",
            self.plan["evidence"],
            self.plan["child_credential"],
        ):
            Path(path).unlink(missing_ok=True)
        responses = [event["response"] for event in self.events[1:6]]
        responses[3] = envelope({"id": self.ownership["childId"], "value": TOKEN.decode()})
        pending = iter(responses)

        def transport(_request):
            raw = json.dumps(next(pending)).encode()
            return admission.Response(
                200, {"content-type": "application/json"}, raw, len(raw) + 100
            )

        inputs = admission.issuer.RuntimeInputs(
            Path(self.references["issuerPlan"]["path"]),
            self.references["issuerPlan"]["sha2_256"],
            Path(self.references["issuerApproval"]["path"]),
            self.references["issuerApproval"]["sha2_256"],
            Path(self.references["issuerAuthority"]["path"]),
            admission.prepared.ROOT,
        )
        with (
            patch.object(admission.issuer, "_validate_source"),
            patch.object(execution, "_windows_private"),
        ):
            result = admission.issuer.run(
                inputs, wall_clock=lambda: NOW - 100, monotonic=lambda: 100.0, transport=transport
            )
        if result["status"] != "finished":
            raise AssertionError("actual synthetic issuer did not finish")
        raw_journal = Path(self.plan["journal"]).read_bytes()
        if state != "complete":
            with closing(sqlite3.connect(":memory:")) as db:
                db.deserialize(raw_journal)
                db.execute("UPDATE intents SET state=? WHERE key='issuer:mutation'", (state,))
                db.commit()
                raw_journal = db.serialize()
        self.put("issuerJournal", raw_journal)
        if populate_evidence:
            raw = Path(self.plan["evidence"]).read_bytes()
            self.events = [json.loads(line) for line in raw.splitlines()]
            self.put("issuerEvidence", raw)

    def put(self, name, value):
        self.documents[name] = copy.deepcopy(value)
        raw = value if type(value) is bytes else json.dumps(value).encode()
        path = self.private / (name + ".evidence")
        path.write_bytes(raw)
        self.references[name] = {"path": str(path), "sha2_256": admission._digest(raw)}

    def rebind_issuer_evidence(self):
        """Rebind deliberate retained-copy mutations without rerunning a producer."""
        self.put("issuerPlan", self.plan)
        approval = self.documents["issuerApproval"]
        approval["plan_digest"] = self.references["issuerPlan"]["sha2_256"]
        self.put("issuerApproval", approval)
        self.events[0]["plan_digest"] = self.references["issuerPlan"]["sha2_256"]
        self.events[0]["approval_digest"] = self.references["issuerApproval"]["sha2_256"]
        self.put("issuerEvidence", b"\n".join(json.dumps(v).encode() for v in self.events) + b"\n")
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(self.documents["issuerJournal"])
            db.execute("UPDATE meta SET digest=?", (self.references["issuerPlan"]["sha2_256"],))
            db.commit()
            self.put("issuerJournal", db.serialize())
        self.put(
            "issuerReview",
            review(
                {
                    k: self.references[k]["sha2_256"]
                    for k in (
                        "issuerPlan",
                        "issuerEvidence",
                        "issuerJournal",
                        "issuerApproval",
                        "issuerAuthority",
                    )
                }
            ),
        )
        self.rebind()

    def rebind(self):
        intent = admission.config_intent_sha2_256(self.config)
        self.put(
            "authority",
            {
                "schemaVersion": 1,
                "runId": self.config["runId"],
                "owner": "Terry",
                "decisionReference": "synthetic-owner-direction",
                "scopeSha2_256": PIN,
                "manifestSha2_256": PIN,
                "configIntentSha2_256": intent,
                "recordedAtUnix": NOW - 1,
                "expiresAtUnix": NOW + 1500,
                "nativeAction": "authorized_under_recorded_owner_direction",
                "cancelCase": "authorized_under_recorded_owner_direction",
                "localCleanup": "authorized_under_recorded_owner_direction",
            },
        )
        self.put(
            "packetReview",
            review(
                {
                    "configIntent": intent,
                    "manifest": PIN,
                    **{
                        k: self.references[k]["sha2_256"]
                        for k in admission.REFERENCES - {"packetReview"}
                    },
                }
            ),
        )
        evidence = {
            "schemaVersion": 1,
            "kind": "post_screenshot_action_evidence",
            "runId": self.config["runId"],
            "manifestSha2_256": PIN,
            "managementAddress": "1.1.1.1",
            "references": self.references,
            "cleanup": {
                "owner": "Terry",
                "revocationOwner": "Terry",
                "revocationByUnix": NOW + 1500,
                "actionDeadlineUnix": self.config["actionDeadlineUnix"],
                "resourceLifetimeSeconds": 1200,
                "cleanupReserveSeconds": 240,
                "providerCallsMaximum": 120,
                "cleanupRequestsReserved": 10,
                "stopNewWorkUnix": NOW + 960,
            },
        }
        raw = json.dumps(evidence).encode()
        Path(self.config["evidencePath"]).write_bytes(raw)
        self.config["evidenceSha2_256"] = admission._digest(raw)
        config_raw = json.dumps(self.config).encode()
        (self.private / "config.json").write_bytes(config_raw)
        approval = {
            "schemaVersion": 1,
            "runId": self.config["runId"],
            "manifestSha2_256": PIN,
            "configSha2_256": admission._digest(config_raw),
            "ownerConsent": True,
            "nativeConsent": True,
            "caseCancelConsent": True,
        }
        raw = json.dumps(approval).encode()
        self.packet.write_bytes(raw)
        self.approved = admission._digest(raw)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture(Path(self.temp.name))
        self.reads = []

        def read(path, maximum=262144):
            self.reads.append(Path(path))
            raw = Path(path).read_bytes()
            if len(raw) > maximum:
                raise OperatorRefused("test_read_bound")
            return raw

        # Fake OS and source boundaries only. Real evidence/policy validators run.
        self.enterContext(patch.object(admission, "_assert_private"))
        self.enterContext(patch.object(admission, "_private_bytes", side_effect=read))
        self.enterContext(
            patch.object(admission, "_document", side_effect=lambda p, d: self.document(p, d, read))
        )
        self.enterContext(
            patch.object(admission.prepared, "binding", return_value=self.fixture.bound)
        )
        self.enterContext(patch.object(admission.prepared, "validate_manifest", return_value=PIN))
        self.enterContext(patch.object(admission.prepared, "digest", return_value=PIN))
        self.enterContext(patch.object(admission.time, "time", return_value=NOW))
        self.enterContext(patch.object(admission.time, "monotonic", return_value=100.0))

    @staticmethod
    def document(path, digest, reader):
        raw = reader(path)
        if admission._digest(raw) != digest:
            raise OperatorRefused("private_input_digest_mismatch")
        return json.loads(raw)

    def admit(self):
        return admission.admit(
            self.fixture.packet, self.fixture.approved, config=self.fixture.config
        )

    def test_valid_facts_admit_without_read_then_exactly_one_claimed_token_read(self):
        permit = self.admit()
        token_path = Path(self.fixture.config["tokenFile"])
        self.assertNotIn(token_path, self.reads)
        self.assertEqual(permit.read_token_once(), TOKEN.decode())
        self.assertEqual(self.reads.count(token_path), 1)
        self.assertTrue((self.fixture.private / "token-read.claim").exists())
        with self.assertRaises(OperatorRefused):
            permit.read_token_once()
        with self.assertRaises(FileExistsError):
            self.admit().read_token_once()

    def test_immutable_grant_drift_is_refused_before_token_read(self):
        permit = self.admit()
        Path(self.fixture.references["grant"]["path"]).write_text("{}")
        with self.assertRaises(OperatorRefused):
            permit.read_token_once()
        self.assertNotIn(Path(self.fixture.config["tokenFile"]), self.reads)

    def test_unknown_issuance_and_missing_delivery_are_not_authority(self):
        self.fixture.journal(state="unknown")
        self.fixture.rebind()
        with self.assertRaises(OperatorRefused):
            self.admit()
        self.fixture.journal()
        self.fixture.events.pop()
        self.fixture.put(
            "issuerEvidence", b"\n".join(json.dumps(v).encode() for v in self.fixture.events)
        )
        self.fixture.rebind()
        with self.assertRaises(OperatorRefused):
            self.admit()

    def test_current_grant_account_or_full_policy_widening_refused(self):
        value = self.fixture.documents["grant"]
        value["childDetails"]["policies"][0]["resources"] = {"com.cloudflare.api.account.*": "*"}
        self.fixture.put("grant", value)
        self.fixture.config["credentialGrantSha2_256"] = self.fixture.references["grant"][
            "sha2_256"
        ]
        self.fixture.rebind()
        with self.assertRaises(OperatorRefused):
            self.admit()

    def test_stop_allows_only_irreversible_cleanup_with_original_deadline(self):
        permit = self.admit()
        stopped = Path(self.fixture.config["coordinationRoot"])
        stopped.mkdir()
        (stopped / "operator-stop.json").write_text("{}")
        with self.assertRaises(OperatorRefused):
            permit.authorize()
        permit.begin_cleanup()
        permit.authorize()
        with self.assertRaises(OperatorRefused):
            permit.read_token_once()
        with patch.object(admission.time, "time", return_value=NOW + 1501):
            with self.assertRaises(OperatorRefused):
                permit.authorize()

    def test_independent_review_and_actual_owner_pid_required(self):
        native = self.fixture.documents["native"]
        native["ownerPid"] += 1
        self.fixture.put("native", native)
        self.fixture.config["nativePreflightSha2_256"] = self.fixture.references["native"][
            "sha2_256"
        ]
        self.fixture.rebind()
        with self.assertRaises(OperatorRefused):
            self.admit()

    def test_stale_or_missing_current_facts_do_not_read_token(self):
        value = self.fixture.documents["grant"]
        value["observedAtUnix"] = NOW - 301
        self.fixture.put("grant", value)
        self.fixture.config["credentialGrantSha2_256"] = self.fixture.references["grant"][
            "sha2_256"
        ]
        self.fixture.rebind()
        with self.assertRaises(OperatorRefused):
            self.admit()
        self.assertNotIn(Path(self.fixture.config["tokenFile"]), self.reads)

    def test_close_and_monotonic_expiry_cannot_renew(self):
        permit = self.admit()
        with patch.object(admission.time, "monotonic", return_value=1601.0):
            with self.assertRaises(OperatorRefused):
                permit.authorize()
        permit.close()
        with self.assertRaises(OperatorRefused):
            permit.authorize()

    def test_consumed_private_identity_is_rejected(self):
        value = self.fixture.documents["spentHistory"]
        value["spentRunIds"].append(self.fixture.config["runId"])
        self.fixture.put("spentHistory", value)
        self.fixture.config["spentRunIds"] = value["spentRunIds"]
        self.fixture.config["spentHistorySha2_256"] = self.fixture.references["spentHistory"][
            "sha2_256"
        ]
        self.fixture.rebind()
        with self.assertRaises(OperatorRefused):
            self.admit()

    def test_source_review_author_cannot_review_itself(self):
        value = self.fixture.documents["sourceReview"]
        value["reviewer"] = value["author"]
        self.fixture.put("sourceReview", value)
        self.fixture.rebind()
        with self.assertRaises(OperatorRefused):
            self.admit()

    def test_failed_claim_persistence_leaves_token_unread_and_attempt_spent(self):
        permit = self.admit()
        with patch.object(admission.os, "fsync", side_effect=OSError("synthetic fsync failure")):
            with self.assertRaises(OSError):
                permit.read_token_once()
        self.assertNotIn(Path(self.fixture.config["tokenFile"]), self.reads)
        self.assertTrue((self.fixture.private / "token-read.claim").exists())
        with self.assertRaises(OperatorRefused):
            permit.read_token_once()

    def test_boolean_schema_version_does_not_alias_integer_one(self):
        value = self.fixture.documents["grant"]
        value["schemaVersion"] = True
        self.fixture.put("grant", value)
        self.fixture.config["credentialGrantSha2_256"] = self.fixture.references["grant"][
            "sha2_256"
        ]
        self.fixture.rebind()
        with self.assertRaises(OperatorRefused):
            self.admit()

    def test_real_producer_journal_missing_or_mutated_intent_refused(self):
        original = self.fixture.documents["issuerJournal"]
        mutations = [
            "DELETE FROM intents WHERE key='issuer:read:1'",
            "UPDATE intents SET payload='{}' WHERE key='issuer:read:1'",
            "UPDATE intents SET payload='{}' WHERE key='issuer:mutation'",
            "UPDATE intents SET receipt='{}' WHERE key='issuer:read:5'",
            "INSERT INTO intents VALUES ('extra','complete','{}','{}')",
        ]
        for sql in mutations:
            with self.subTest(sql=sql), closing(sqlite3.connect(":memory:")) as db:
                db.deserialize(original)
                db.execute(sql)
                db.commit()
                self.fixture.put("issuerJournal", db.serialize())
                self.fixture.rebind_issuer_evidence()
                with self.assertRaises(OperatorRefused):
                    self.admit()

    def test_complete_current_producer_source_maps_required(self):
        self.fixture.plan["source_sha2_256"] = {}
        self.fixture.rebind_issuer_evidence()
        with self.assertRaises(OperatorRefused):
            self.admit()

    def test_actual_header_retention_and_parent_verify_must_match(self):
        self.fixture.events[0]["retention_until"] = "2099-01-01T00:00:00Z"
        self.fixture.rebind_issuer_evidence()
        with self.assertRaises(OperatorRefused):
            self.admit()
        self.fixture.events[0]["retention_until"] = self.fixture.plan["retention_until"]
        self.fixture.events[1]["response"]["result"]["status"] = "revoked"
        self.fixture.rebind_issuer_evidence()
        with self.assertRaises(OperatorRefused):
            self.admit()

    def test_observed_stop_remains_sticky_after_file_removed(self):
        permit = self.admit()
        directory = Path(self.fixture.config["coordinationRoot"])
        directory.mkdir()
        stop = directory / "operator-stop.json"
        stop.write_text("{}")
        with self.assertRaises(OperatorRefused):
            permit.authorize()
        stop.unlink()
        with self.assertRaises(OperatorRefused):
            permit.authorize()
        permit.begin_cleanup()
        permit.authorize()

    def test_all_reference_aliases_to_credentials_refused_before_any_secret_read(self):
        token_path = Path(self.fixture.config["tokenFile"])
        parent_path = Path(self.fixture.config["parentTokenFile"])
        for alias in (
            str(self.fixture.private / ".." / "private" / token_path.name),
            str(parent_path),
        ):
            with self.subTest(alias=alias):
                self.fixture.references["issuerAuthority"] = {"path": alias, "sha2_256": PIN}
                self.fixture.rebind()
                with self.assertRaises(OperatorRefused):
                    self.admit()
                self.assertFalse(
                    any(
                        p.resolve() in {token_path.resolve(), parent_path.resolve()}
                        for p in self.reads
                    )
                )

    def test_validation_io_cannot_return_authority_after_monotonic_expiry(self):
        permit = self.admit()
        tick = [100.0]

        def slow_validate(*_args, **_kwargs):
            tick[0] = 1601.0
            return permit._evidence, permit._end

        with (
            patch.object(admission, "_validate", side_effect=slow_validate),
            patch.object(admission.time, "monotonic", side_effect=lambda: tick[0]),
        ):
            with self.assertRaises(OperatorRefused):
                permit.authorize()


if __name__ == "__main__":
    unittest.main()
