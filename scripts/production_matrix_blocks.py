"""Permanent-block survival through the production API and native lifecycle."""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

from scripts import bootstrap_deployment as bootstrap
from scripts import current_schema_archive as archive
from scripts.hosted_restore_proof import require_current_restore

if TYPE_CHECKING:
    from scripts.production_matrix import Case, Matrix

SEEDS = {"code_6": 6, "code_7": 7, "unknown": 9999, "unresolved_dispatch": None}
CONFIRMATIONS = dict.fromkeys(
    [
        "ownerControlledWorkstation",
        "privateBrowser",
        "clipboardHistoryOff",
        "clipboardSyncOff",
        "noObserversOrRecording",
        "pluginReady",
    ],
    True,
)


def block_row(matrix: Matrix, case: Case):
    return matrix.sql(
        "SELECT * FROM submission_blocks WHERE photo_id=? AND group_id=?", [case.photo, case.group]
    )


def settle(matrix: Matrix, case: Case, wanted: str):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        matrix.control(action="native-maintenance", ownerSub="sub-" + case.user)
        row = matrix.sql(
            "SELECT state,operation_id FROM flickr_connection_state WHERE user_id=?", [case.user]
        )[0]
        if row["state"] == wanted and row["operation_id"] is None:
            return
        time.sleep(1)
    raise RuntimeError("native_lifecycle_did_not_settle")


def snapshot_stopped(matrix: Matrix):
    proof = matrix.proof
    if proof is None:
        raise RuntimeError("hosted_restore_required")
    matrix.stop_process()
    database = matrix.settings["databaseId"]

    # This suite must never copy real account data. The source is a fresh owned
    # database and every authority/photography identifier must be fixture-only.
    def query(sql: str):
        return proof.query(database, sql)

    users = query("SELECT user_id FROM fga_users")
    if not users or any(
        not re.fullmatch(r"fp-(?:mem|pre|res|queue|block|crash)-[a-z0-9_.-]+", row["user_id"])
        for row in users
    ):
        raise RuntimeError("restore_source_contains_non_fixture_users")
    if query("SELECT 1 FROM flickr_links WHERE owner_nsid<>'matrix-owner'"):
        raise RuntimeError("restore_source_contains_non_fixture_flickr_owner")
    if query(
        "SELECT 1 FROM photo_bindings WHERE photo_id NOT LIKE 'p-fp-%' "
        "OR owner_nsid<>'matrix-owner'"
    ):
        raise RuntimeError("restore_source_contains_non_fixture_photography")
    if query("SELECT 1 FROM admin_principals WHERE google_sub NOT LIKE 'sub-fp-%'"):
        raise RuntimeError("restore_source_contains_non_fixture_google_owner")
    print("Verified synthetic-only source in the newly created test database", flush=True)
    return proof.capture(database)


def restore_case(matrix: Matrix, case: Case, old: archive.Archive):
    if not matrix.proof:
        raise RuntimeError("hosted_restore_required")
    logout = matrix.api(case, "/api/v001/admin/session/logout", "POST")
    if logout["status"] != 204:
        raise RuntimeError("post_backup_revocation_failed")
    current = snapshot_stopped(matrix)
    stale = matrix.proof.create("old-" + str(matrix.counter))
    matrix.proof.restore(stale, old)
    try:
        require_current_restore(matrix.proof.capture(stale), current)
    except ValueError:
        rejected = True
    else:
        rejected = False
    if not rejected:
        raise RuntimeError("stale_backup_accepted")
    restored = matrix.proof.create("restore-" + str(matrix.counter))
    matrix.proof.restore(restored, current)
    require_current_restore(matrix.proof.capture(restored), current)
    matrix.settings["databaseId"] = restored
    path = matrix.settings["wrangler"]
    from pathlib import Path

    config = json.loads(Path(path).read_text())
    config["d1_databases"][0].update(
        database_id=restored,
        database_name=next(name for name, value in matrix.proof.owned.items() if value == restored),
    )
    bootstrap.save(Path(path), config)
    matrix.launch(resume=True)
    if matrix.api(case, "/api/v001/admin/session")["status"] != 401:
        raise RuntimeError("restore_resurrected_session")
    matrix.submit(case)
    matrix.wake(case)
    matrix.control(action="scheduled")
    return True


def make_block(matrix: Matrix, case: Case, reason: str, *, historical: bool = False):
    matrix.peer.calls = []
    matrix.peer.mode = {"add": {"stat": "fail", "code": SEEDS[reason] or 6}}
    if historical:
        attempt = "historical-" + case.intent
        outcome = "moderation_submitted" if reason in ("code_6", "code_7") else "delivery_uncertain"
        why = (
            "flickr_" + reason
            if reason in ("code_6", "code_7")
            else "unknown_code"
            if reason == "unknown"
            else "unresolved_dispatch"
        )
        first = "flickr_" + reason if reason in ("code_6", "code_7") else "delivery_uncertain"
        matrix.batch(
            [
                (
                    (
                        "INSERT INTO submission_attempts(attempt_id,intent_id,ordinal"
                        ",lease_id,lease_generation,deployment_revision,user_revision"
                        ",link_revision,created_at_us) "
                        "VALUES(?,?,1,'historical',1,1,1,1,946684800000000)"
                    ),
                    [attempt, case.intent],
                ),
                (
                    (
                        "INSERT INTO attempt_dispatches(attempt_id,started_at_us) "
                        "VALUES(?,946684800000000)"
                    ),
                    [attempt],
                ),
                (
                    (
                        "INSERT INTO submission_blocks(photo_id,group_id,first_reason"
                        ",source_attempt_id,created_at_utc) "
                        "VALUES(?,?,?,?,'2000-01-01T00:00:00.000000Z')"
                    ),
                    [case.photo, case.group, first, attempt],
                ),
                (
                    (
                        "INSERT INTO attempt_resolutions(attempt_id,outcome,reason,co"
                        "mpleted_at_us) VALUES(?,?,?,946684800000000)"
                    ),
                    [attempt, outcome, why],
                ),
                (
                    (
                        "UPDATE submission_intents SET "
                        "state=?,terminal_at_us=946684800000000,add_dispatch_count=1 "
                        "WHERE intent_id=?"
                    ),
                    [outcome, case.intent],
                ),
                (
                    (
                        "INSERT INTO audit_events(event_id,user_id,action,request_cor"
                        "relation_id,outcome,reason) VALUES(?,?,'matrix.historical_se"
                        "ed',?,'succeeded','historical_fixture')"
                    ),
                    [attempt, case.user, attempt],
                ),
            ]
        )
    else:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            matrix.run(
                case, **({"stop": "marker_committed"} if reason == "unresolved_dispatch" else {})
            )
            if reason == "unresolved_dispatch":
                matrix.sql(
                    (
                        "UPDATE group_partitions SET "
                        "lease_expires_at_us=1,invocation_deadline_at_us=1 WHERE "
                        "partition_id=?"
                    ),
                    [case.partition],
                )
                matrix.run(case)
            if block_row(matrix, case):
                break
            time.sleep(0.5)
    row = block_row(matrix, case)
    expected = "flickr_" + reason if reason in ("code_6", "code_7") else "delivery_uncertain"
    if len(row) != 1 or row[0]["first_reason"] != expected:
        raise RuntimeError("block_seed_failed")
    if not historical:
        posts = sum(call["method"] == "flickr.groups.pools.add" for call in matrix.peer.calls)
        if posts != int(reason != "unresolved_dispatch"):
            raise RuntimeError("unexpected_seed_dispatch_count")
    matrix.peer.calls = []
    return row


def lifecycle_case(matrix: Matrix, case: Case):
    view = matrix.api(case, "/api/v001/admin/flickr-connection")
    revision = view["body"]["revision"]
    response = matrix.api(
        case,
        "/api/v001/admin/flickr-connection/disconnection",
        "POST",
        {
            "schemaVersion": 1,
            "expectedRevision": revision,
            "expectedFlickrOwnerNsid": "matrix-owner",
        },
    )
    if response["status"] not in (200, 202):
        raise RuntimeError("real_disconnect_failed")
    settle(matrix, case, "disconnected")
    revision = matrix.sql("SELECT link_revision FROM flickr_links WHERE user_id=?", [case.user])[0][
        "link_revision"
    ]
    started = matrix.api(
        case,
        "/api/v001/admin/flickr-connection/authorization",
        "POST",
        {"schemaVersion": 1, "expectedRevision": revision},
    )
    if started["status"] != 201:
        raise RuntimeError("real_relink_start_failed")
    state = parse_qs(urlsplit(matrix.peer.oauth_callback).query)["state"][0]
    callback = matrix.api(
        case,
        "/admin/flickr-oauth/callback?state="
        + state
        + "&oauth_token=matrix-request&oauth_verifier=matrix-verifier",
    )
    if callback["status"] != 200:
        raise RuntimeError("real_relink_callback_failed")
    settle(matrix, case, "linked")
    user_gate = matrix.sql(
        "SELECT revision,enabled FROM flickr_write_gates WHERE scope='user' AND scope_id=?",
        [case.user],
    )[0]
    if user_gate["enabled"] != 0:
        raise RuntimeError("relink_resumed_writes")
    resumed = matrix.api(
        case,
        "/api/v001/admin/flickr-write-gates/user/resume",
        "POST",
        {"schemaVersion": 1, "expectedRevision": user_gate["revision"]},
    )
    if resumed["status"] != 200:
        raise RuntimeError("real_user_resume_failed")
    parent = "/api/v001/plugin-codes/" + case.user
    detail = matrix.api(case, parent)
    candidate = matrix.api(
        case,
        parent + "/rotation-candidates",
        "POST",
        {"schemaVersion": 1, "transferConfirmations": CONFIRMATIONS},
        {"If-Match": detail["headers"]["etag"]},
    )
    if candidate["status"] != 201:
        raise RuntimeError("real_rotation_start_failed")
    value = candidate["body"]
    new_code = value["pluginCode"]
    status, _ = matrix.request("/api/v001/installations/current", None, new_code, "GET")
    if status != 200:
        raise RuntimeError("pending_code_not_validated")
    current = matrix.api(case, parent)
    complete = matrix.api(
        case,
        parent + "/rotation-candidates/" + value["rotationCandidateId"],
        "PATCH",
        {"schemaVersion": 1, "state": "current", "pluginValidationConfirmed": True},
        {"If-Match": current["headers"]["etag"]},
    )
    if complete["status"] != 200:
        raise RuntimeError("real_rotation_completion_failed")
    if matrix.request("/api/v001/installations/current", None, case.code, "GET")[0] != 401:
        raise RuntimeError("old_code_still_current")
    case.code = new_code
    revision = matrix.sql("SELECT link_revision FROM flickr_links WHERE user_id=?", [case.user])[0][
        "link_revision"
    ]
    verified = matrix.control(
        action="api",
        path="/api/v001/existing-public-photo-bindings",
        method="POST",
        headers={"Authorization": "Bearer " + case.code, "Content-Type": "application/json"},
        body={
            "schemaVersion": 1,
            "flickrPhotoId": case.photo,
            "expectedLinkedFlickrRevision": revision,
        },
    )
    if verified["status"] not in (200, 201):
        raise RuntimeError("post_relink_photo_verification_failed")
    case.binding = verified["body"]["fgaPhotoBindingId"]
    case.binding_revision = verified["body"]["verificationRevision"]
    if matrix.submit(case)["status"] != 202:
        raise RuntimeError("post_relink_duplicate_not_presented")
    matrix.run(case)


def block_cases(matrix: Matrix, selected: list[str] | None = None):
    ids = selected or [f"FP-BLOCK-{n:03d}" for n in range(1, 11)]
    known = [row["path"] for row in matrix.control(action="routes")["routes"]]
    for label in ids:
        witnesses = []
        for reason in SEEDS:
            case = matrix.seed(label + "-" + reason)
            old = None
            if label == "FP-BLOCK-003":
                matrix.admin(case)
                old = snapshot_stopped(matrix)
                matrix.launch(resume=True)
            original = make_block(
                matrix, case, reason, historical=label in ("FP-BLOCK-004", "FP-BLOCK-006")
            )
            writes_before = matrix.control(action="protected-writes")["count"]
            ok = True
            if label == "FP-BLOCK-001":
                ok = matrix.submit(case)["status"] == 202
            elif label == "FP-BLOCK-002":
                matrix.wake(case)
                matrix.control(action="scheduled")
                matrix.run(case)
                for action in ("retry", "reopen", "cancel", "force", "reconcile"):
                    response = matrix.api(
                        case,
                        "/api/v001/admin/group-submission-intents/" + case.intent + "/" + action,
                        "POST",
                        {},
                    )
                    ok = ok and response["status"] >= 400
            elif label == "FP-BLOCK-003":
                if old is None:
                    raise RuntimeError("missing_old_snapshot")
                ok = restore_case(matrix, case, old)
            elif label == "FP-BLOCK-004":
                for moderated, age in ((1, 0), (0, 31536000000000), (1, 315360000000000)):
                    matrix.peer.mode = {
                        "preflight": {
                            "stat": "ok",
                            "group": {"id": case.group, "ispoolmoderated": moderated},
                        }
                    }
                    matrix.submit(case)
                    matrix.run(case, beforeAge=age, afterAge=age)
            elif label == "FP-BLOCK-005":
                lifecycle_case(matrix, case)
            elif label == "FP-BLOCK-006":
                matrix.control(action="native-maintenance", ownerSub="sub-" + case.user)
                matrix.submit(case)
                matrix.run(case)
            elif label == "FP-BLOCK-007":
                for key, value in [
                    ("force", True),
                    ("retry", True),
                    ("moderated", 0),
                    ("blockId", "fake"),
                    ("state", "queued"),
                    ("adminSession", "fake"),
                ]:
                    response = matrix.control(
                        action="api",
                        path="/api/v001/group-submission-batches",
                        method="POST",
                        headers={
                            "Authorization": "Bearer " + case.code,
                            "Content-Type": "application/json",
                        },
                        body={
                            "schemaVersion": 2,
                            "photoBinding": {
                                "fgaPhotoBindingId": case.binding,
                                "expectedVerificationRevision": 1,
                            },
                            "flickrGroupIds": [case.group],
                            key: value,
                        },
                    )
                    ok = ok and response["status"] == 400
            elif label == "FP-BLOCK-008":
                paths = set(re.sub(r"\{[^}]+\}", case.user, path) for path in known)
                paths.update(
                    [
                        "/admin/",
                        "/admin/login",
                        "/admin/google-login",
                        "/admin/flickr-oauth/callback",
                        "/admin/google-client.json",
                        "/admin/signed-out",
                    ]
                )
                paths.update(
                    "/api/v001/admin/submission-blocks/" + case.intent + "/" + action
                    for action in ("delete", "update", "clear", "force")
                )
                for path in sorted(paths):
                    for method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
                        # Each route gets current authority even when a previous route logged out.
                        case.admin_token = ""
                        response = matrix.api(
                            case, path, method, None if method in ("GET", "HEAD") else {}
                        )
                        ok = ok and response["status"] < 500
            elif label == "FP-BLOCK-009":
                statements = [
                    ("DELETE FROM submission_blocks WHERE photo_id=?", [case.photo]),
                    (
                        (
                            "UPDATE submission_blocks SET "
                            "first_reason='delivery_uncertain' WHERE photo_id=?"
                        ),
                        [case.photo],
                    ),
                    (
                        (
                            "INSERT OR REPLACE INTO submission_blocks SELECT * FROM "
                            "submission_blocks WHERE photo_id=?"
                        ),
                        [case.photo],
                    ),
                    (
                        (
                            "INSERT INTO submission_blocks SELECT * FROM "
                            "submission_blocks WHERE photo_id=? ON "
                            "CONFLICT(photo_id,group_id) DO UPDATE SET "
                            "first_reason=excluded.first_reason"
                        ),
                        [case.photo],
                    ),
                    ("DELETE FROM fga_users WHERE user_id=?", [case.user]),
                ]
                for sql, params in statements:
                    ok = ok and matrix.control(action="guard-sql", sql=sql, params=params)["denied"]
                for table in (
                    "submission_attempts",
                    "attempt_membership",
                    "attempt_preflights",
                    "attempt_dispatches",
                    "attempt_resolutions",
                ):
                    for action in (
                        "DELETE FROM " + table,
                        "UPDATE " + table + " SET attempt_id=attempt_id",
                        "INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table,
                    ):
                        sql = action + (
                            " WHERE attempt_id IN (SELECT attempt_id FROM "
                            "submission_attempts WHERE intent_id=?)"
                        )
                        ok = (
                            ok
                            and matrix.control(action="guard-sql", sql=sql, params=[case.intent])[
                                "denied"
                            ]
                        )
                # Create an actual audit entry through the ordinary detail route,
                # then exercise its append-only guards and a controlled DDL rollback.
                detail = matrix.api(case, "/api/v001/plugin-codes/" + case.user)
                ok = ok and detail["status"] == 200
                for statement in (
                    "DELETE FROM audit_events WHERE user_id=?",
                    "UPDATE audit_events SET action=action WHERE user_id=?",
                    "INSERT OR REPLACE INTO audit_events SELECT * FROM audit_events "
                    "WHERE user_id=?",
                ):
                    ok = (
                        ok
                        and matrix.control(action="guard-sql", sql=statement, params=[case.user])[
                            "denied"
                        ]
                    )
                ok = ok and matrix.control(action="migration-proof", photoId=case.photo)["passed"]
            elif label == "FP-BLOCK-010":
                for pool in ([{"id": case.group, "title": "present"}], []):
                    matrix.peer.mode = {"membership": {"stat": "ok", "pool": pool}}
                    matrix.submit(case)
                    matrix.run(case)
            else:
                raise ValueError("unknown_block_case")
            ok = (
                ok
                and matrix.control(action="protected-writes")["count"] == writes_before
                and original == block_row(matrix, case)
                and not any(
                    call["method"] == "flickr.groups.pools.add" for call in matrix.peer.calls
                )
            )
            witnesses.append({"seedReason": reason, "passed": ok})
            print(label + "." + reason + (": passed" if ok else ": FAILED"), flush=True)
            if not ok:
                matrix.check(label, False, seedReasons=[reason])
        matrix.check(
            label,
            all(row["passed"] for row in witnesses),
            seedReasons=list(SEEDS),
            witnesses=witnesses,
        )
