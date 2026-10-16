"""Bounded fixed D1 observations. Offline planning is the CLI default.

An authorized --observe uses the existing no-redirect provider transport; it
never calls authenticated application status routes or reads secret bundles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scripts import controlled_trial_pause as pause

FIELDS = {"schemaVersion", "accountId", "databaseId", "fgaUserId", "photoId", "groupId"}
PAGE_SIZE = 100
MAX_PAGES = 10000

# Every inventory includes inactive/terminal rows too: future work, retained
# leases and abandoned attempts cannot disappear behind a due/user filter.
INVENTORIES = {
    "users": ("fga_users", "user_id", "user_id"),
    "gates": (
        "flickr_write_gates",
        "scope || ':' || scope_id",
        "scope,scope_id,enabled,CAST(revision AS TEXT) AS revision",
    ),
    "partitions": (
        "group_partitions",
        "partition_id",
        "partition_id,user_id,group_id,CAST(wake_revision AS TEXT) AS wake_revision,"
        "CAST(next_work_not_before_us AS TEXT) AS due_us,lease_id,"
        "CAST(lease_generation AS TEXT) AS lease_generation,"
        "CAST(lease_expires_at_us AS TEXT) AS lease_expires_us,"
        "CAST(invocation_deadline_at_us AS TEXT) AS invocation_deadline_us,"
        "CAST(next_probe_not_before_us AS TEXT) AS probe_due_us",
    ),
    "intents": (
        "submission_intents",
        "intent_id",
        "intent_id,binding_id,user_id,photo_id,group_id,partition_id,state,"
        "active_fifo_member,CAST(enqueue_ordinal AS TEXT) AS ordinal,"
        "CAST(state_version AS TEXT) AS state_version,"
        "CAST(next_attempt_not_before_us AS TEXT) AS retry_due_us,add_dispatch_count",
    ),
    "attempts": (
        "submission_attempts a LEFT JOIN attempt_membership m USING(attempt_id) "
        "LEFT JOIN attempt_preflights f USING(attempt_id) "
        "LEFT JOIN attempt_dispatches d USING(attempt_id) "
        "LEFT JOIN attempt_resolutions r USING(attempt_id)",
        "a.attempt_id",
        "a.attempt_id,a.intent_id,CAST(a.ordinal AS TEXT) AS ordinal,a.lease_id,"
        "CAST(a.lease_generation AS TEXT) AS lease_generation,"
        "CAST(a.created_at_us AS TEXT) AS created_us,m.target_absent,"
        "CAST(m.observed_at_us AS TEXT) AS membership_us,f.moderated,"
        "CAST(f.observed_at_us AS TEXT) AS preflight_us,"
        "CAST(d.started_at_us AS TEXT) AS dispatch_us,r.outcome,r.reason,"
        "CAST(r.completed_at_us AS TEXT) AS resolution_us",
    ),
    "blocks": (
        "submission_blocks",
        "hex(photo_id) || ':' || hex(group_id)",
        "photo_id,group_id,first_reason,source_attempt_id,created_at_utc",
    ),
}

PAIR_SQL = """SELECT
 (SELECT json_object('binding_id',binding_id,'user_id',user_id,'photo_id',photo_id,
   'owner_nsid',owner_nsid,'link_revision',CAST(link_revision AS TEXT),
   'verification_revision',CAST(verification_revision AS TEXT),'source_kind',source_kind,
   'verified_at_us',CAST(verified_at_us AS TEXT))
   FROM photo_bindings WHERE photo_id=?2) AS binding_metadata,
 (SELECT json_object('user_id',user_id,'owner_nsid',owner_nsid,
   'link_revision',CAST(link_revision AS TEXT),'state',state)
   FROM flickr_links WHERE user_id=?1) AS link_metadata,
 (SELECT json_object('user_id',user_id,'active_generation',active_generation,
   'link_revision',CAST(link_revision AS TEXT),'verified_owner_nsid',verified_owner_nsid,
   'verified_permission',verified_permission,'operation_id',operation_id)
   FROM flickr_native_credentials WHERE user_id=?1) AS native_metadata,
 (SELECT json_object('user_id',user_id,'state',state,'local_state',local_state,
   'verified_permission',verified_permission,'verified_at_us',CAST(verified_at_us AS TEXT),
   'external_removal',external_removal,'operation_id',operation_id)
   FROM flickr_connection_state WHERE user_id=?1) AS connection_metadata,
 (SELECT COUNT(*) FROM photo_bindings WHERE photo_id=?2) AS photo_bindings,
 (SELECT COUNT(*) FROM photo_bindings b JOIN flickr_links l ON l.user_id=b.user_id
  JOIN flickr_native_credentials n ON n.user_id=l.user_id
  JOIN flickr_connection_state c ON c.user_id=l.user_id
  WHERE b.photo_id=?2 AND b.user_id=?1 AND b.owner_nsid=l.owner_nsid
   AND b.link_revision=l.link_revision AND l.state='linked'
   AND n.link_revision=l.link_revision AND n.verified_owner_nsid=l.owner_nsid
   AND c.state='linked' AND c.local_state='available'
   AND n.verified_permission IN ('write','delete')
   AND c.verified_permission IN ('write','delete') AND c.external_removal=0) AS linked_bindings,
 (SELECT COUNT(*) FROM submission_blocks WHERE photo_id=?2 AND group_id=?3) AS blocks,
 (SELECT COUNT(*) FROM submission_intents WHERE photo_id=?2 AND group_id=?3) AS intents,
 (SELECT COUNT(*) FROM photo_bindings b JOIN photo_membership_observations o
   ON o.binding_id=b.binding_id JOIN flickr_links l ON l.user_id=b.user_id
   JOIN flickr_native_credentials n ON n.user_id=b.user_id
   WHERE b.photo_id=?2 AND b.user_id=?1 AND o.valid=1
    AND o.link_revision=l.link_revision AND o.link_revision=b.link_revision
    AND o.generation=n.active_generation) AS current_membership_observations,
 (SELECT COUNT(*) FROM photo_bindings b JOIN photo_membership_rows m
   ON m.binding_id=b.binding_id WHERE b.photo_id=?2 AND b.user_id=?1
    AND m.group_id=?3) AS cached_membership_rows,
 (SELECT CAST(MAX(o.observed_at_us) AS TEXT) FROM photo_bindings b
   JOIN photo_membership_observations o ON o.binding_id=b.binding_id
   WHERE b.photo_id=?2 AND b.user_id=?1) AS cached_membership_us"""


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("invalid_observation_plan")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise ValueError("invalid_observation_plan")
    if not isinstance(value["accountId"], str) or not re.fullmatch(
        r"[a-f0-9]{32}", value["accountId"]
    ):
        raise ValueError("invalid_account_id")
    if not isinstance(value["databaseId"], str):
        raise ValueError("invalid_database_id")
    if str(uuid.UUID(value["databaseId"])) != value["databaseId"]:
        raise ValueError("invalid_database_id")
    for name in ("fgaUserId", "photoId", "groupId"):
        if not isinstance(value[name], str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}", value[name]
        ):
            raise ValueError("invalid_pair_parameter")
    return dict(value)


def statement(plan, operation, after=""):
    """Closed allowlist; no caller-supplied SQL, table, projection or URL."""
    p = validate(plan)
    if operation == "pair" and after == "":
        return {"sql": PAIR_SQL, "params": [p["fgaUserId"], p["photoId"], p["groupId"]]}
    if operation == "counts" and after == "":
        projections = [
            f"(SELECT COUNT(*) FROM {table}) AS {name}"
            for name, (table, _, _) in INVENTORIES.items()
        ]
        return {"sql": "SELECT " + ",".join(projections), "params": []}
    if operation not in INVENTORIES:
        raise ValueError("unknown_observation_operation")
    if not isinstance(after, str) or len(after) > 512 or "\x00" in after:
        raise ValueError("invalid_continuation")
    table, key, projection = INVENTORIES[operation]
    return {
        "sql": f"SELECT {key} AS cursor_key,{projection} FROM {table} "
        f"WHERE {key} COLLATE BINARY > ?1 ORDER BY {key} COLLATE BINARY LIMIT ?2",
        "params": [after, str(PAGE_SIZE)],
    }


def _single(rows):
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("invalid_observation_result")
    return rows[0]


def collect(plan, query):
    """Query receives only generated SELECT bodies. Return private facts, no verdict.

    Two identical full passes detect drift; this does not replace the external
    stopped-writer/configuration barrier or claim a multi-request snapshot.
    """
    p = validate(plan)
    started = datetime.now(UTC).isoformat()

    def sweep():
        counts = _single(query(statement(p, "counts")))
        if set(counts) != set(INVENTORIES) or any(
            type(n) is not int or n < 0 for n in counts.values()
        ):
            raise ValueError("invalid_inventory_counts")
        inventories = {}
        for operation in INVENTORIES:
            rows, after = [], ""
            for _ in range(MAX_PAGES):
                page = query(statement(p, operation, after))
                if not isinstance(page, list) or len(page) > PAGE_SIZE:
                    raise ValueError("invalid_inventory_page")
                for row in page:
                    if not isinstance(row, dict):
                        raise ValueError("invalid_inventory_row")
                    cursor = row.get("cursor_key")
                    if not isinstance(cursor, str) or not after < cursor or len(cursor) > 512:
                        raise ValueError("invalid_inventory_continuation")
                    after = cursor
                    rows.append(row)
                if len(rows) > counts[operation]:
                    raise ValueError("inventory_count_mismatch")
                if len(page) < PAGE_SIZE:
                    break
            else:
                raise ValueError("inventory_page_budget_exceeded")
            if len(rows) != counts[operation]:
                raise ValueError("inventory_count_mismatch")
            inventories[operation] = rows
        pair = _single(query(statement(p, "pair")))
        if counts != _single(query(statement(p, "counts"))):
            raise ValueError("observation_changed")
        return {"counts": counts, "inventories": inventories, "pair": pair}

    first = sweep()
    if first != sweep():
        raise ValueError("observation_changed")
    return {
        "schemaVersion": 1,
        "plan": p,
        "startedAt": started,
        "completedAt": datetime.now(UTC).isoformat(),
        **first,
    }


def summary(private):
    """Public projection is constructed, never recursively scrubbed raw data."""
    inventories = private["inventories"]
    gates = inventories["gates"]
    deployment = [g for g in gates if g["scope"] == "deployment" and g["scope_id"] == "*"]
    return {
        "schemaVersion": 1,
        "state": "observed_only_not_authorization",
        "counts": {name: len(inventories[name]) for name in INVENTORIES},
        "deploymentGateObservedPaused": len(deployment) == 1 and deployment[0]["enabled"] == 0,
        "activeFifoMembers": sum(i["active_fifo_member"] for i in inventories["intents"]),
        "retainedLeases": sum(p["lease_id"] is not None for p in inventories["partitions"]),
        "unresolvedAttempts": sum(a["resolution_us"] is None for a in inventories["attempts"]),
        "unresolvedDispatches": sum(
            a["dispatch_us"] is not None and a["resolution_us"] is None
            for a in inventories["attempts"]
        ),
        "freshFlickrPreflightRequired": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--observe", action="store_true")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--private-output", type=Path)
    args = parser.parse_args()
    try:
        p = validate(json.loads(args.plan.read_text(encoding="utf-8-sig")))
        if not args.observe:
            print(json.dumps({"state": "offline_plan_valid", "operations": [*INVENTORIES, "pair"]}))
            return 0
        if args.token_file is None or args.private_output is None:
            raise ValueError("private_output_and_token_file_required")
        # Never overwrite a prior observation or accidentally write into the repo.
        output = args.private_output.resolve()
        root = Path(__file__).resolve().parents[1]
        if output.is_relative_to(root) or not output.parent.is_dir():
            raise ValueError("private_output_must_be_outside_repository")
        if output in (args.plan.resolve(), args.token_file.resolve()):
            raise ValueError("private_output_conflict")
        token = args.token_file.read_text(encoding="utf-8-sig").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{35,256}", token):
            raise ValueError("invalid_operator_token_file")
        with output.open("x", encoding="utf-8") as destination:
            private = collect(p, lambda body: pause.request(p, token, body))
            private["adapterSha2_256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            json.dump(private, destination, indent=2)
            destination.write("\n")
        print(json.dumps(summary(private)))
        return 0
    except OSError, ValueError, KeyError, TypeError:
        # Provider messages, plans, identifiers and exception details stay private.
        print(json.dumps({"state": "observation_refused"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
