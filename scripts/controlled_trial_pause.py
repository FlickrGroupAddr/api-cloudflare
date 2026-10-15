"""Fixed, audited pause for the private controlled trial; offline plan by default.

Never resumes a gate, runs supplied SQL, reads Flickr credentials, or retries a
provider request. --apply and --inspect are production operations requiring the
execution authorization recorded in the trial runbook. An unconfirmed apply
requires --inspect with the SAME plan, not another apply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path

FIELDS = {
    "schemaVersion",
    "accountId",
    "databaseId",
    "fgaUserId",
    "operationId",
    "expectedDeploymentRevision",
    "expectedDeploymentEnabled",
    "expectedUserRevision",
    "expectedUserEnabled",
}


def validate(value):
    if (
        not isinstance(value, dict)
        or set(value) != FIELDS
        or type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
    ):
        raise ValueError("invalid_operator_plan")
    if not isinstance(value["accountId"], str) or not re.fullmatch(
        r"[a-f0-9]{32}", value["accountId"]
    ):
        raise ValueError("invalid_account_id")
    for name in ("databaseId", "operationId"):
        if not isinstance(value[name], str) or str(uuid.UUID(value[name])) != value[name]:
            raise ValueError("invalid_opaque_id")
    if not isinstance(value["fgaUserId"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}", value["fgaUserId"]
    ):
        raise ValueError("invalid_owner_id")
    for name in ("expectedDeploymentRevision", "expectedUserRevision"):
        if type(value[name]) is not int or not 1 <= value[name] < 9007199254740991:
            raise ValueError("invalid_expected_revision")
    for name in ("expectedDeploymentEnabled", "expectedUserEnabled"):
        if type(value[name]) is not int or value[name] not in (0, 1):
            raise ValueError("invalid_expected_gate_state")
    return value


def statements(value):
    p = validate(value)
    # REST query's documented parameter representation is strings. Explicit
    # casts preserve exact integer authority, avoiding JSON numeric rounding.
    op, user = p["operationId"], p["fgaUserId"]
    reason = (
        f"controlled_trial_stop_d{p['expectedDeploymentRevision']}_"
        f"{p['expectedDeploymentRevision'] + p['expectedDeploymentEnabled']}_"
        f"u{p['expectedUserRevision']}_"
        f"{p['expectedUserRevision'] + p['expectedUserEnabled']}"
    )
    return [
        {
            "sql": """INSERT INTO transaction_guards(transaction_id,approved)
          SELECT ?1, EXISTS(SELECT 1 FROM flickr_write_gates
           WHERE scope='deployment' AND scope_id='*'
           AND revision=CAST(?2 AS INTEGER) AND enabled=CAST(?3 AS INTEGER))
          AND EXISTS(SELECT 1 FROM flickr_write_gates
           WHERE scope='user' AND scope_id=?4
           AND revision=CAST(?5 AS INTEGER) AND enabled=CAST(?6 AS INTEGER))""",
            "params": [
                op,
                str(p["expectedDeploymentRevision"]),
                str(p["expectedDeploymentEnabled"]),
                user,
                str(p["expectedUserRevision"]),
                str(p["expectedUserEnabled"]),
            ],
        },
        {
            "sql": """UPDATE flickr_write_gates SET enabled=0,revision=revision+1
          WHERE enabled=1 AND ((scope='deployment' AND scope_id='*')
          OR (scope='user' AND scope_id=?1))""",
            "params": [user],
        },
        {
            "sql": """INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,
          outcome,reason,target_id,source_component)
          VALUES(?1,?2,'flickr.operator_write_pause',?1,'succeeded',?3,?2,'fga_deployment_operator')""",
            "params": [op, user, reason],
        },
        {"sql": "DELETE FROM transaction_guards WHERE transaction_id=?1", "params": [op]},
        inspection_statement(p),
    ]


def inspection_statement(p):
    return {
        "sql": """SELECT scope,enabled,CAST(revision AS TEXT) AS revision,
      EXISTS(SELECT 1 FROM audit_events WHERE event_id=?1 AND request_correlation_id=?1
       AND user_id=?2 AND action='flickr.operator_write_pause'
       AND source_component='fga_deployment_operator'
       AND outcome='succeeded') AS operation_recorded,
      EXISTS(SELECT 1 FROM flickr_write_gate_events e WHERE e.scope=g.scope
       AND e.scope_id=g.scope_id AND e.revision=g.revision
       AND e.reason='gate_paused') AS pause_recorded
      FROM flickr_write_gates g WHERE (scope='deployment' AND scope_id='*')
       OR (scope='user' AND scope_id=?2) ORDER BY scope""",
        "params": [p["operationId"], p["fgaUserId"]],
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(p, token, body, opener=None):
    # Endpoint is fixed to the official provider; account/database are validated
    # from the reviewed private plan. No URL, query or SQL comes from CLI input.
    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + p["accountId"]
        + "/d1/database/"
        + p["databaseId"]
        + "/query"
    )
    req = urllib.request.Request(
        endpoint,
        method="POST",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "FlickrGroupAddr-ControlledTrialPause/1",
        },
    )
    try:
        with (opener or urllib.request.build_opener(NoRedirect)).open(req, timeout=30) as response:
            raw = response.read(65537)
            if response.status != 200 or len(raw) > 65536:
                raise ValueError("provider_result_unconfirmed")
    except (OSError, urllib.error.HTTPError) as error:
        raise ValueError("provider_result_unconfirmed") from error
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("success") is not True:
        raise ValueError("provider_result_unconfirmed")
    results = value.get("result")
    expected = len(body.get("batch", [body]))
    if (
        not isinstance(results, list)
        or len(results) != expected
        or any(not isinstance(row, dict) or row.get("success") is not True for row in results)
    ):
        raise ValueError("provider_result_unconfirmed")
    return results[-1].get("results")


def receipt(p, rows):
    # Do not promote later gate revisions to confirmation of this operation.
    if not isinstance(rows, list) or len(rows) != 2:
        return {"state": "unconfirmed_inspect_required"}
    expected = {
        "deployment": p["expectedDeploymentRevision"] + p["expectedDeploymentEnabled"],
        "user": p["expectedUserRevision"] + p["expectedUserEnabled"],
    }
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("scope") not in expected:
            return {"state": "unconfirmed_inspect_required"}
        scope = row["scope"]
        if (
            scope in seen
            or row.get("enabled") != 0
            or row.get("revision") != str(expected[scope])
            or row.get("operation_recorded") != 1
        ):
            return {"state": "unconfirmed_inspect_required"}
        # Initially-paused gates may have initially_paused/migration_snapshot
        # history; require a new generic pause event only for changed gates.
        changed = (
            p["expectedDeploymentEnabled"] if scope == "deployment" else p["expectedUserEnabled"]
        )
        if changed and row.get("pause_recorded") != 1:
            return {"state": "unconfirmed_inspect_required"}
        seen.add(scope)
    return {
        "state": "confirmed_paused",
        "operationId": p["operationId"],
        "deploymentRevision": str(expected["deployment"]),
        "userRevision": str(expected["user"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--token-file", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    try:
        p = validate(json.loads(args.plan_file.read_text(encoding="utf-8-sig")))
        batch = statements(p)
        if not args.apply and not args.inspect:
            print(
                json.dumps(
                    {
                        "state": "offline_plan",
                        "statements": len(batch),
                        "planSha2_256": hashlib.sha256(
                            json.dumps(p, sort_keys=True).encode()
                        ).hexdigest(),
                    }
                )
            )
            return 0
        if args.token_file is None:
            raise ValueError("operator_token_file_required")
        token = args.token_file.read_text(encoding="utf-8-sig").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{35,256}", token):
            raise ValueError("invalid_operator_token_file")
        body = inspection_statement(p) if args.inspect else {"batch": batch}
        result = receipt(p, request(p, token, body))
        print(json.dumps(result))
        return 0 if result["state"] == "confirmed_paused" else 1
    except ValueError, KeyError, OSError, TypeError:
        # Errors intentionally omit raw exception/provider/request/plan content.
        print(
            json.dumps(
                {
                    "state": "unconfirmed_inspect_required"
                    if args.apply or args.inspect
                    else "invalid_offline_plan"
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
