"""Protected POST action admission; imported modules and default CLI are inert.

The trusted primary authenticates human direction and native UI observations.
These bindings preserve those observations; JSON is not human authentication.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from scripts import collect_publisher_grant_metadata as metadata
from scripts import prepare_post_screenshot_successor as prepared
from scripts import provision_work_plan_token as issuer
from scripts.hosted_publisher_execution import _assert_private, _document, _private_bytes
from scripts.hosted_publisher_execution_provider import _address
from scripts.hosted_publisher_finite_client import Response
from scripts.hosted_publisher_operator import OperatorRefused

HASH = r"[a-f0-9]{64}"
ID = r"[a-f0-9]{32}"
TOKEN_OBSERVATIONS = {"modified_on", "last_used_on"}
REFERENCES = {
    "authority",
    "native",
    "cells",
    "custody",
    "accountProvenance",
    "issuerPlan",
    "issuerEvidence",
    "issuerJournal",
    "issuerReview",
    "issuerApproval",
    "issuerAuthority",
    "grant",
    "sourceReview",
    "packetReview",
    "spentHistory",
    "grantCollection",
    "grantPlan",
}


def _closed(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise OperatorRefused("post_evidence_shape_refused")
    return value


def _text(value, pattern=HASH):
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise OperatorRefused("post_evidence_identity_refused")
    return value


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise OperatorRefused("post_finite_time_required")
    return value


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _path(value):
    if (
        type(value) is not str
        or not Path(value).is_absolute()
        or value.startswith(("\\\\", "//"))
        or ".." in Path(value).parts
        or any(":" in part for part in Path(value).parts[1:])
        or str(Path(value)) != os.path.normpath(value)
        or Path(value) != Path(value).resolve(strict=True)
    ):
        raise OperatorRefused("post_absolute_private_path_required")
    return Path(value)


def _equal(actual, expected):
    if type(actual) is not type(expected) or actual != expected:
        raise OperatorRefused("post_exact_evidence_binding_required")
    if isinstance(expected, dict):
        for key in expected:
            _equal(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        for left, right in zip(actual, expected, strict=True):
            _equal(left, right)


def _review(value, subjects):
    _closed(value, {"schemaVersion", "author", "reviewer", "verdict", "subjects"})
    _equal(value["schemaVersion"], 1)
    _equal(value["verdict"], "pass")
    _equal(value["subjects"], subjects)
    for key in ("author", "reviewer"):
        _text(value[key], r"[A-Za-z0-9_. -]{1,128}")
    if value["author"] == value["reviewer"]:
        raise OperatorRefused("post_independent_review_required")


def _journal(raw, plan_digest, ownership, *, plan, ids):
    # A protected immutable snapshot of the *actual* issuer SQLite journal, not
    # a caller-authored summary. Deserialize privately; never open it for writes.
    try:
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(raw)
            db.execute("PRAGMA query_only=ON")
            if db.execute("SELECT digest FROM meta").fetchall() != [(plan_digest,)]:
                raise OperatorRefused("post_issuer_journal_plan_mismatch")
            rows = db.execute(
                "SELECT key,state,payload,receipt FROM intents ORDER BY rowid"
            ).fetchall()
        expected_keys = [
            "issuer:started",
            "issuer:read:1",
            "issuer:read:2",
            "issuer:read:3",
            "issuer:mutation",
            "issuer:read:5",
        ]
        if [row[0] for row in rows] != expected_keys:
            raise OperatorRefused("post_exact_issuer_intent_inventory_required")
        states = {
            k: (s, metadata._json(p.encode()), metadata._json(r.encode())) for k, s, p, r in rows
        }
        if any(s != "complete" for s, _, _ in states.values()):
            raise OperatorRefused("post_issuer_unsettled_journal")
        _equal(states["issuer:started"][1], {"operation": "issue"})
        started_receipt = _closed(
            states["issuer:started"][2], {"status", "requests", "responseWireBytes"}
        )
        _equal(started_receipt["status"], "finished")
        _equal(started_receipt["requests"], 5)
        used = started_receipt["responseWireBytes"]
        if type(used) is not int or not 0 < used <= issuer.MAX_TOTAL_RESPONSE_BYTES:
            raise OperatorRefused("post_actual_issuer_accounting_required")
        body = {
            "name": plan["child_name"],
            "policies": issuer._policies(plan, ids),
            "expires_on": plan["child_expires_at"],
            "not_before": plan["starts_at"],
        }
        if plan["child_condition"]:
            body["condition"] = plan["child_condition"]
        routes = [
            ("GET", issuer.BASE + "/verify", b""),
            ("GET", issuer.BASE + "/permission_groups", b""),
            ("GET", issuer.BASE + "/" + ownership["parentId"], b""),
            ("POST", issuer.BASE, issuer.boundary.encoded(body)),
            ("GET", issuer.BASE + "/" + ownership["childId"], b""),
        ]
        for key, (method, path, data) in zip(expected_keys[1:], routes, strict=True):
            _equal(states[key][1], {"method": method, "path": path, "requestDigest": _digest(data)})
            _equal(
                states[key][2], ownership if key == "issuer:mutation" else {"status": "retained"}
            )
    except (sqlite3.Error, KeyError, ValueError, TypeError) as error:
        raise OperatorRefused("post_actual_issuer_journal_required") from error


def _producer_source(plan, files):
    _text(plan["source_commit"], r"[a-f0-9]{40}")
    pins = _closed(plan["source_sha2_256"], set(files))
    for name, pin in pins.items():
        _text(pin)
        _equal(pin, prepared.digest(prepared.ROOT / name))


def _issuance(documents, raw, refs, config, now):
    plan = documents["issuerPlan"]
    # Actual issuer schema/operations remain owned by provision_work_plan_token.
    required = {
        "schema_version",
        "purpose",
        "owner",
        "operation",
        "profile",
        "account_id",
        "source_commit",
        "source_sha2_256",
        "starts_at",
        "expires_at",
        "cleanup_at",
        "child_expires_at",
        "child_name",
        "child_condition",
        "parent_condition",
        "parent_id",
        "parent_sha2_256",
        "api_address",
        "parent_credential",
        "child_credential",
        "claim",
        "journal",
        "evidence",
        "retention_until",
        "revoker",
        "issuance",
        "request_limit",
        "request_byte_limit",
        "response_byte_limit",
    }
    _closed(plan, required)
    _equal(plan["operation"], "issue")
    _equal(plan["profile"], issuer.PROFILE)
    _equal(plan["purpose"], "work_plan_local_token_admin")
    _equal(plan["account_id"], config["accountId"])
    _equal(plan["child_credential"], config["tokenFile"])
    _equal(plan["parent_credential"], config["parentTokenFile"])
    _producer_source(plan, issuer.SOURCE_FILES)
    _equal(plan["issuance"], None)
    for key in ("owner", "revoker"):
        _text(plan[key], r"[A-Za-z0-9_. -]{1,128}")
    _equal(plan["schema_version"], 1)
    for key, value in {
        "request_limit": 5,
        "request_byte_limit": issuer.MAX_REQUEST_BYTES,
        "response_byte_limit": issuer.MAX_TOTAL_RESPONSE_BYTES,
    }.items():
        _equal(plan[key], value)
    start = issuer._timestamp(plan["starts_at"]) / metadata._TIME_SCALE
    end = issuer._timestamp(plan["expires_at"]) / metadata._TIME_SCALE
    if not 0 < end - start <= 600 or start > now:
        raise OperatorRefused("post_actual_issuer_window_required")
    child_end = issuer._timestamp(plan["child_expires_at"])
    cleanup_end = issuer._timestamp(plan["cleanup_at"])
    retention_end = issuer._timestamp(plan["retention_until"])
    if not (
        issuer._timestamp(plan["expires_at"])
        < child_end
        <= cleanup_end
        <= issuer._timestamp(plan["starts_at"]) + 4 * 3600 * metadata._TIME_SCALE
        and cleanup_end <= retention_end <= issuer._timestamp(issuer.PARENT_DEADLINE)
    ):
        raise OperatorRefused("post_actual_issuer_lifetime_required")
    issuer._condition(plan["child_condition"])
    issuer._condition(plan["parent_condition"])
    _text(plan["child_name"], r"[^\r\n]{1,128}")
    _text(plan["parent_sha2_256"])
    if plan["parent_sha2_256"] == config["credentialSha2_256"]:
        raise OperatorRefused("post_distinct_parent_child_required")
    events = [metadata._json(line) for line in raw["issuerEvidence"].splitlines()]
    if len(events) != 7:
        raise OperatorRefused("post_actual_issuance_delivery_required")
    header, *phases = events
    _closed(
        header,
        {
            "plan_digest",
            "approval_digest",
            "decision_id",
            "source_commit",
            "provisioning",
            "retention_until",
        },
    )
    _equal(header["plan_digest"], refs["issuerPlan"]["sha2_256"])
    _equal(header["approval_digest"], refs["issuerApproval"]["sha2_256"])
    approval = _closed(
        documents["issuerApproval"],
        {
            "schema_version",
            "decision_id",
            "plan_digest",
            "source_commit",
            "owner",
            "provisioning",
            "bootstrap_role",
            "human_evidence_sha2_256",
            "recorded_at",
            "expires_at",
        },
    )
    for key, value in {
        "schema_version": 1,
        "decision_id": issuer.DECISION,
        "plan_digest": refs["issuerPlan"]["sha2_256"],
        "source_commit": plan["source_commit"],
        "owner": plan["owner"],
        "provisioning": "authorized_automated_local_issuance",
        "bootstrap_role": "user_wide_token_management_write_local_only",
        "human_evidence_sha2_256": refs["issuerAuthority"]["sha2_256"],
    }.items():
        _equal(approval[key], value)
    _equal(header["decision_id"], issuer.DECISION)
    _equal(header["source_commit"], plan["source_commit"])
    _equal(header["provisioning"], "authorized_automated_local_issuance")
    _equal(header["retention_until"], plan["retention_until"])
    if (
        not issuer._timestamp(plan["starts_at"])
        <= issuer._timestamp(approval["recorded_at"])
        < issuer._timestamp(approval["expires_at"])
        <= issuer._timestamp(plan["expires_at"])
    ):
        raise OperatorRefused("post_actual_issuer_approval_window_required")
    if [event.get("phase") for event in phases] != [
        "parent_verify",
        "permission_catalog",
        "parent_details",
        "create_acknowledged",
        "child_details",
        "delivery",
    ]:
        raise OperatorRefused("post_actual_issuer_phase_order_required")
    parent_verify, catalog, parent, created, child, delivered = phases
    for event in (parent_verify, catalog, parent, child):
        _closed(event, {"phase", "response"})
    _closed(created, {"phase", "response", "ownership", "child_sha2_256"})
    _equal(delivered, {"phase": "delivery", "status": "exclusive_new_private_file_written"})
    _equal(created["child_sha2_256"], config["credentialSha2_256"])
    ids = issuer.permission_ids(
        Response(
            200, {"content-type": "application/json"}, json.dumps(catalog["response"]).encode()
        )
    )
    for event in (parent_verify, parent, created, child):
        envelope = _closed(event["response"], {"success", "errors", "messages", "result"})
        _equal(envelope["success"], True)
        _equal(envelope["errors"], [])
    parent_details, child_details = parent["response"]["result"], child["response"]["result"]
    _text(parent_details["id"], ID)
    _text(child_details["id"], ID)
    _equal(child_details["name"], plan["child_name"])
    creation = created["response"]["result"]
    allowed_created = {
        "id",
        "name",
        "status",
        "issued_on",
        "expires_on",
        "not_before",
        "policies",
        "condition",
        "modified_on",
        "last_used_on",
    }
    if type(creation) is not dict or "id" not in creation or not creation.keys() <= allowed_created:
        raise OperatorRefused("post_exact_creation_receipt_required")
    scaled_now = metadata._now(lambda: now)
    issuer._match_details(parent_details, plan, ids, scaled_now, parent=True)
    issuer._match_details(child_details, plan, ids, scaled_now)
    # Creation may contain only an ID. Validate every retained creation value
    # against the full details schema without modifying either original record.
    issuer._match_details(child_details | creation, plan, ids, scaled_now)
    for key, value in creation.items():
        if key not in TOKEN_OBSERVATIONS:
            _equal(value, child_details.get(key))
    if (
        not issuer._timestamp(approval["recorded_at"])
        <= issuer._timestamp(child_details["issued_on"])
        < issuer._timestamp(approval["expires_at"])
    ):
        raise OperatorRefused("post_actual_issuance_authority_time_required")
    if issuer._timestamp(child_details["expires_on"]) > issuer._timestamp(
        parent_details["expires_on"]
    ):
        raise OperatorRefused("post_child_outlives_parent")
    _equal(
        parent_verify["response"]["result"],
        {key: parent_details[key] for key in ("id", "status", "expires_on", "not_before")},
    )
    _equal(created["response"]["result"]["id"], child_details["id"])
    if child_details["id"] == parent_details["id"]:
        raise OperatorRefused("post_distinct_parent_child_required")
    ownership = {
        "childId": child_details["id"],
        "parentId": parent_details["id"],
        "parentFingerprint": plan["parent_sha2_256"],
        "accountId": config["accountId"],
        "profile": issuer.PROFILE,
        "childExpiry": plan["child_expires_at"],
        "childName": plan["child_name"],
        "childCondition": plan["child_condition"],
    }
    _equal(created["ownership"], ownership)
    _journal(raw["issuerJournal"], refs["issuerPlan"]["sha2_256"], ownership, plan=plan, ids=ids)
    _review(
        documents["issuerReview"],
        {
            k: refs[k]["sha2_256"]
            for k in (
                "issuerPlan",
                "issuerEvidence",
                "issuerJournal",
                "issuerApproval",
                "issuerAuthority",
            )
        },
    )
    grant = documents["grant"]
    _closed(
        grant,
        {
            "schemaVersion",
            "runId",
            "observedAtUnix",
            "childSha2_256",
            "parentSha2_256",
            "childVerify",
            "parentVerify",
            "childDetails",
        },
    )
    _equal(grant["schemaVersion"], 1)
    _equal(grant["runId"], config["runId"])
    if not _number(grant["observedAtUnix"]) <= now:
        raise OperatorRefused("post_current_provider_grant_required")
    _equal(grant["childSha2_256"], config["credentialSha2_256"])
    _equal(grant["parentSha2_256"], plan["parent_sha2_256"])
    collection_plan = _closed(
        documents["grantPlan"],
        {
            "schema_version",
            "purpose",
            "owner",
            "source_commit",
            "source_sha2_256",
            "starts_at",
            "expires_at",
            "api_address",
            "test_credential",
            "reader_credential",
            "evidence",
            "journal",
            "claim",
            "discovery",
            "actions",
        },
    )
    _equal(collection_plan["schema_version"], 1)
    _producer_source(collection_plan, metadata.SOURCE_FILES)
    _equal(collection_plan["purpose"], "publisher_grant_metadata_evidence")
    _equal(collection_plan["owner"], plan["owner"])
    _equal(collection_plan["test_credential"], config["tokenFile"])
    _equal(collection_plan["reader_credential"], plan["parent_credential"])
    _equal(collection_plan["discovery"], "test_verify_id_only")
    _equal(collection_plan["actions"], list(metadata.ACTIONS))
    collection_start = issuer._timestamp(collection_plan["starts_at"]) / metadata._TIME_SCALE
    collection_end = issuer._timestamp(collection_plan["expires_at"]) / metadata._TIME_SCALE
    if (
        not collection_start <= grant["observedAtUnix"] < collection_end
        or not 0 < collection_end - collection_start <= 1200
    ):
        raise OperatorRefused("post_actual_collection_window_required")
    collection = _closed(
        documents["grantCollection"],
        {
            "schema_version",
            "purpose",
            "plan_digest",
            "approval_digest",
            "source_commit",
            "responses",
            "credential_sha2_256",
            "limitations",
        },
    )
    _equal(collection["schema_version"], 1)
    _equal(collection["purpose"], "provider_metadata_evidence_only")
    _equal(
        collection["limitations"],
        [
            "reader_full_policy_not_observed",
            "not_execution_authority",
            "human_provenance_external",
            "manual_revocation_required",
        ],
    )
    _equal(collection["plan_digest"], refs["grantPlan"]["sha2_256"])
    _equal(collection["source_commit"], collection_plan["source_commit"])
    _text(collection["approval_digest"])
    _equal(
        collection["credential_sha2_256"],
        {
            "test": config["credentialSha2_256"],
            "reader": plan["parent_sha2_256"],
        },
    )
    responses = _closed(collection["responses"], set(metadata.ACTIONS))
    for phase, key in zip(
        metadata.ACTIONS, ("childVerify", "parentVerify", "childDetails"), strict=True
    ):
        checked = _closed(responses[phase], {"success", "errors", "messages", "result"})
        _equal(checked["success"], True)
        _equal(checked["errors"], [])
        _equal(checked["result"], grant[key])
    issuer._match_details(grant["childDetails"], plan, ids, scaled_now)
    _equal(
        {k: v for k, v in grant["childDetails"].items() if k not in TOKEN_OBSERVATIONS},
        {k: v for k, v in child_details.items() if k not in TOKEN_OBSERVATIONS},
    )
    for key, details in (("childVerify", child_details), ("parentVerify", parent_details)):
        _closed(grant[key], {"id", "status", "expires_on", "not_before"})
        _equal(grant[key]["status"], "active")
        for field in ("id", "expires_on", "not_before"):
            _equal(grant[key][field], details[field])
        if (
            not metadata._timestamp(grant[key]["not_before"])
            <= scaled_now
            < metadata._timestamp(grant[key]["expires_on"])
        ):
            raise OperatorRefused("post_current_active_verify_required")
    expiry = issuer._timestamp(child_details["expires_on"]) / metadata._TIME_SCALE
    _equal(float(expiry), float(config["credentialExpiryUnix"]))
    return plan


def config_intent_sha2_256(config):
    """Acyclic review subject; final approval separately hashes complete config."""
    value = {k: v for k, v in config.items() if k != "evidenceSha2_256"}
    return _digest(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    )


def _validate(packet_path, approved_digest, config, *, now, initial):
    packet_path = Path(packet_path)
    bound = prepared.binding(config["runId"])
    extras = {
        "accountId",
        "subdomain",
        "actionDeadlineUnix",
        "windowId",
        "runtimeCellsSha2_256",
        "scopeSha2_256",
        "nativePreflightSha2_256",
        "credentialGrantSha2_256",
        "custodyReviewSha2_256",
        "credentialExpiryUnix",
        "credentialSha2_256",
        "parserProfile",
        "evidenceSha2_256",
        "spentRunIds",
        "spentHistorySha2_256",
        "parentTokenFile",
    }
    _closed(config, set(bound) | extras)
    for key, value in bound.items():
        _equal(config[key], value)
    _equal(packet_path, Path(bound["runRoot"]) / "private/approved-packet.json")
    _equal(packet_path, _path(str(packet_path)))
    private = packet_path.parent
    _assert_private(private, directory=True)
    approval = _document(packet_path, approved_digest)
    disk_config = _document(private / "config.json", approval["configSha2_256"])
    _equal(disk_config, config)
    _text(config["accountId"], ID)
    _text(config["credentialSha2_256"])
    _text(config["subdomain"], r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
    if type(config["windowId"]) is not int or config["windowId"] <= 0:
        raise OperatorRefused("post_exact_native_window_required")
    _equal(config["parserProfile"], "bounded-stateless-cookie-discard-v1")
    _equal(config["scopeSha2_256"], prepared.digest(prepared.ROOT / prepared.SCOPE))
    # The offline validator is not a private-input reader; its source-only
    # manifest validation is safe here, after protected config/approval reads.
    manifest = prepared.validate_manifest()
    _equal(
        approval,
        {
            "schemaVersion": 1,
            "runId": config["runId"],
            "manifestSha2_256": manifest,
            "configSha2_256": approval["configSha2_256"],
            "ownerConsent": True,
            "nativeConsent": True,
            "caseCancelConsent": True,
        },
    )
    evidence_path = _path(config["evidencePath"])
    _equal(evidence_path, private / "action-evidence.json")
    evidence = _document(evidence_path, config["evidenceSha2_256"])
    _closed(
        evidence,
        {
            "schemaVersion",
            "kind",
            "runId",
            "manifestSha2_256",
            "managementAddress",
            "references",
            "cleanup",
        },
    )
    _equal(evidence["schemaVersion"], 1)
    _equal(evidence["kind"], "post_screenshot_action_evidence")
    _equal(evidence["runId"], config["runId"])
    _equal(evidence["manifestSha2_256"], manifest)
    _equal(str(_address(evidence["managementAddress"])), evidence["managementAddress"])
    refs = _closed(evidence["references"], REFERENCES)
    raw, documents = {}, {}
    credential_paths = {
        _path(config[key]).resolve(strict=True) for key in ("tokenFile", "parentTokenFile")
    }
    if len(credential_paths) != 2:
        raise OperatorRefused("post_distinct_parent_child_paths_required")
    credential_identities = set()
    for path in credential_paths:
        _assert_private(path)
        info = path.stat()
        credential_identities.add((info.st_dev, info.st_ino))
    if len(credential_identities) != 2:
        raise OperatorRefused("post_distinct_parent_child_paths_required")
    paths = set()
    referenced_paths = {}
    # Complete metadata-only preflight precedes every referenced byte read.
    for name, ref in refs.items():
        _closed(ref, {"path", "sha2_256"})
        path = _path(ref["path"])
        _assert_private(path)
        canonical = path.resolve(strict=True)
        info = path.stat()
        if (
            canonical in paths
            or canonical in credential_paths
            or (info.st_dev, info.st_ino) in credential_identities
        ):
            raise OperatorRefused("post_distinct_evidence_paths_required")
        paths.add(canonical)
        referenced_paths[name] = path
        _text(ref["sha2_256"])
    for name, path in referenced_paths.items():
        raw[name] = _private_bytes(path, 2097152)
        _equal(_digest(raw[name]), refs[name]["sha2_256"])
        if name not in ("issuerEvidence", "issuerJournal", "issuerAuthority", "cells"):
            documents[name] = metadata._json(raw[name])
    for ref, key in (
        ("native", "nativePreflightSha2_256"),
        ("cells", "runtimeCellsSha2_256"),
        ("grant", "credentialGrantSha2_256"),
        ("custody", "custodyReviewSha2_256"),
    ):
        _equal(refs[ref]["sha2_256"], config[key])
    authority = _closed(
        documents["authority"],
        {
            "schemaVersion",
            "runId",
            "owner",
            "decisionReference",
            "scopeSha2_256",
            "manifestSha2_256",
            "configIntentSha2_256",
            "recordedAtUnix",
            "expiresAtUnix",
            "nativeAction",
            "cancelCase",
            "localCleanup",
        },
    )
    _equal(authority["schemaVersion"], 1)
    _equal(authority["runId"], config["runId"])
    _text(authority["owner"], r"[A-Za-z0-9_. -]{1,128}")
    _text(authority["decisionReference"], r"[^\r\n]{1,512}")
    for key in ("scopeSha2_256", "manifestSha2_256"):
        _equal(authority[key], config[key] if key == "scopeSha2_256" else approval[key])
    intent_digest = config_intent_sha2_256(config)
    _equal(authority["configIntentSha2_256"], intent_digest)
    history = _closed(
        documents["spentHistory"],
        {
            "schemaVersion",
            "observedAtUnix",
            "owner",
            "spentRunIds",
            "sourceReference",
        },
    )
    _equal(history["schemaVersion"], 1)
    _equal(history["owner"], authority["owner"])
    _equal(history["spentRunIds"], config["spentRunIds"])
    _equal(refs["spentHistory"]["sha2_256"], config["spentHistorySha2_256"])
    consumed = history["spentRunIds"]
    if type(consumed) is not list or not 1 <= len(consumed) <= 256:
        raise OperatorRefused("post_complete_bounded_spent_history_required")
    for run in consumed:
        _text(run, r"[a-f0-9]{24}")
    if len(set(consumed)) != len(consumed) or config["runId"] in consumed:
        raise OperatorRefused("post_spent_identity_refused")
    _text(history["sourceReference"], r"[^\r\n]{1,512}")
    if not _number(history["observedAtUnix"]) <= now:
        raise OperatorRefused("post_current_spent_history_required")
    for key in ("nativeAction", "cancelCase", "localCleanup"):
        _equal(authority[key], "authorized_under_recorded_owner_direction")
    if not _number(authority["recordedAtUnix"]) <= now < _number(authority["expiresAtUnix"]):
        raise OperatorRefused("post_authority_window_closed")
    native = _closed(
        documents["native"],
        {
            "schemaVersion",
            "runId",
            "ownerPid",
            "windowId",
            "hostVersion",
            "sdkVersion",
            "hostBuild",
            "fixtureVersion",
            "toolkitIdentifier",
            "observedAtUnix",
            "expiresAtUnix",
            "manifestSha2_256",
            "runtimeCellsSha2_256",
            "witness",
            "authorityOwner",
            "witnessReference",
            "observations",
        },
    )
    for key, value in {
        "schemaVersion": 1,
        "runId": config["runId"],
        "ownerPid": os.getpid(),
        "windowId": config["windowId"],
        "hostVersion": "15.6",
        "sdkVersion": "15.3",
        "fixtureVersion": "0.0.1.1",
        "toolkitIdentifier": "com.sixbuckssolutions.fga.grouppost.v1.lrc15",
        "manifestSha2_256": manifest,
        "runtimeCellsSha2_256": config["runtimeCellsSha2_256"],
    }.items():
        _equal(native[key], value)
    _text(native["hostBuild"], r"[A-Za-z0-9-]{1,128}")
    _equal(native["authorityOwner"], authority["owner"])
    _text(native["witness"], r"[A-Za-z0-9_./ -]{1,128}")
    _text(native["witnessReference"], r"[^\r\n]{1,512}")
    _equal(
        native["observations"],
        [
            "current_source_equal",
            "loaded_enabled",
            "sole_operator",
            "supported_full_window_inspected",
            "fresh_native_paths",
            "fresh_run_paths",
            "runtime_cells_reviewed",
        ],
    )
    if not _number(native["observedAtUnix"]) <= now < _number(native["expiresAtUnix"]):
        raise OperatorRefused("post_current_native_witness_required")
    custody = _closed(
        documents["custody"],
        {
            "schemaVersion",
            "runId",
            "owner",
            "tokenFile",
            "credentialSha2_256",
            "reviewReference",
            "observedAtUnix",
            "expiresAtUnix",
            "delivery",
        },
    )
    for key, value in {
        "schemaVersion": 1,
        "runId": config["runId"],
        "owner": authority["owner"],
        "tokenFile": config["tokenFile"],
        "credentialSha2_256": config["credentialSha2_256"],
        "delivery": "issuer_exclusive_new_private_file",
    }.items():
        _equal(custody[key], value)
    _text(custody["reviewReference"], r"[^\r\n]{1,512}")
    if not _number(custody["observedAtUnix"]) <= now < _number(custody["expiresAtUnix"]):
        raise OperatorRefused("post_current_custody_required")
    provenance = _closed(
        documents["accountProvenance"],
        {
            "schemaVersion",
            "runId",
            "accountId",
            "subdomain",
            "observedAtUnix",
            "expiresAtUnix",
            "owner",
            "sourceReference",
        },
    )
    for key in ("runId", "accountId", "subdomain"):
        _equal(provenance[key], config[key])
    _equal(provenance["schemaVersion"], 1)
    _equal(provenance["owner"], authority["owner"])
    _text(provenance["sourceReference"], r"[^\r\n]{1,512}")
    if not _number(provenance["observedAtUnix"]) <= now < _number(provenance["expiresAtUnix"]):
        raise OperatorRefused("post_current_account_provenance_required")
    plan = _issuance(documents, raw, refs, config, now)
    _equal(plan["owner"], authority["owner"])
    cleanup = _closed(
        evidence["cleanup"],
        {
            "owner",
            "revocationOwner",
            "revocationByUnix",
            "actionDeadlineUnix",
            "resourceLifetimeSeconds",
            "cleanupReserveSeconds",
            "providerCallsMaximum",
            "cleanupRequestsReserved",
            "stopNewWorkUnix",
        },
    )
    for key, value in {
        "owner": authority["owner"],
        "revocationOwner": plan["revoker"],
        "actionDeadlineUnix": config["actionDeadlineUnix"],
        "resourceLifetimeSeconds": 1200,
        "cleanupReserveSeconds": 240,
        "providerCallsMaximum": 120,
        "cleanupRequestsReserved": 10,
    }.items():
        _equal(cleanup[key], value)
    deadline = _number(config["actionDeadlineUnix"])
    _equal(config["credentialExpiryUnix"], deadline)
    if any(
        _number(document["expiresAtUnix"]) < deadline
        for document in (
            authority,
            native,
            custody,
            provenance,
        )
    ):
        raise OperatorRefused("post_full_cleanup_window_evidence_required")
    if (
        not now < deadline <= _number(config["credentialExpiryUnix"])
        or not deadline
        <= _number(cleanup["revocationByUnix"])
        <= issuer._timestamp(plan["cleanup_at"]) / metadata._TIME_SCALE
    ):
        raise OperatorRefused("post_finite_cleanup_revocation_required")
    if not _number(cleanup["revocationByUnix"]) <= config[
        "credentialExpiryUnix"
    ] or issuer._timestamp(plan["retention_until"]) > issuer._timestamp(issuer.PARENT_DEADLINE):
        raise OperatorRefused("post_revocation_credential_window_required")
    if not _number(cleanup["stopNewWorkUnix"]) <= deadline - 240:
        raise OperatorRefused("post_cleanup_reserve_required")
    if initial and (
        now - history["observedAtUnix"] > 300
        or now - documents["grant"]["observedAtUnix"] > 300
        or now - native["observedAtUnix"] > 300
    ):
        raise OperatorRefused("post_fresh_initial_evidence_required")
    if initial and not 1230 <= deadline - now <= 1800:
        raise OperatorRefused("post_admission_window_required")
    _review(documents["sourceReview"], {"manifest": manifest})
    _review(
        documents["packetReview"],
        {
            "configIntent": intent_digest,
            "manifest": manifest,
            **{k: refs[k]["sha2_256"] for k in REFERENCES - {"packetReview"}},
        },
    )
    return evidence, min(
        deadline,
        authority["expiresAtUnix"],
        native["expiresAtUnix"],
        custody["expiresAtUnix"],
        provenance["expiresAtUnix"],
    )


class Admission:
    """Single owner, non-renewable permit; cleanup phase never returns to work."""

    def __init__(self, packet_path, approved_digest, config):
        self._packet = Path(packet_path)
        self._digest = approved_digest
        self._config = dict(config)
        self._closed = self._cleanup = self._read = self._stopped = False
        self._started = time.monotonic()
        self._wall = time.time()
        self._evidence, end = _validate(
            self._packet, approved_digest, self._config, now=self._wall, initial=True
        )
        self._end = end
        self._monotonic_end = self._started + (end - self._wall)
        self._pid = os.getpid()
        self.management_address = self._evidence["managementAddress"]

    def remaining_seconds(self):
        now, tick = time.time(), time.monotonic()
        if (
            not math.isfinite(now)
            or not math.isfinite(tick)
            or now < self._wall
            or tick < self._started
        ):
            raise OperatorRefused("post_clock_refused")
        return max(0.0, min(self._end - now, self._monotonic_end - tick))

    def authorize(self):
        if self._closed or os.getpid() != self._pid or self.remaining_seconds() <= 0:
            raise OperatorRefused("post_admission_closed")
        evidence, end = _validate(
            self._packet, self._digest, self._config, now=time.time(), initial=False
        )
        _equal(evidence, self._evidence)
        _equal(end, self._end)
        if not self._cleanup:
            stops = [
                Path(self._config["coordinationRoot"]) / "operator-stop.json",
                Path(self._config["nativeRoot"]) / "stop.json",
            ]
            self._stopped = (
                self._stopped
                or time.time() >= evidence["cleanup"]["stopNewWorkUnix"]
                or any(p.exists() or p.is_symlink() for p in stops)
            )
            if self._stopped:
                raise OperatorRefused("post_new_work_stopped")
        # Evidence/source/stop I/O consumes the same non-renewable budget.
        if self.remaining_seconds() <= 0:
            raise OperatorRefused("post_admission_closed")

    def begin_cleanup(self):
        self._cleanup = True
        self.authorize()

    def read_token_once(self):
        self.authorize()
        if self._read or self._cleanup:
            raise OperatorRefused("post_token_seam_spent")
        self._read = True
        claim = self._packet.parent / "token-read.claim"
        _assert_private(claim.parent, directory=True)
        # The persistent claim is never removed, even after an unknown read.
        fd = os.open(
            claim,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOINHERIT", 0)
            | getattr(os, "O_BINARY", 0),
            0o600,
        )
        try:
            _assert_private(claim)
            payload = (self._digest + "\n").encode("ascii")
            if os.write(fd, payload) != len(payload):
                raise OperatorRefused("post_claim_write_failed")
            os.fsync(fd)
        finally:
            os.close(fd)
        _equal(_private_bytes(claim), payload)
        self.authorize()
        raw = _private_bytes(Path(self._config["tokenFile"]), 2048)
        if (
            re.fullmatch(rb"[A-Za-z0-9_-]{20,2048}", raw) is None
            or _digest(raw) != self._config["credentialSha2_256"]
        ):
            raise OperatorRefused("post_exact_child_credential_required")
        self.authorize()
        return raw.decode("ascii")

    def close(self):
        self._closed = True


def admit(packet_path, independently_retained_approval_sha2_256, *, config):
    try:
        return Admission(packet_path, independently_retained_approval_sha2_256, config)
    except (KeyError, TypeError, ValueError, OSError) as error:
        raise OperatorRefused("post_current_private_evidence_required") from error


if __name__ == "__main__":
    print(json.dumps({"mode": "offline", "actionReady": False}))
