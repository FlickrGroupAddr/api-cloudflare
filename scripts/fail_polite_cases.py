"""Crash-boundary proof cases over the real D1 adapter and controlled HTTP peer.

This bounded suite is not the complete production fail-polite release gate.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

try:
    from . import coordination_probe as probe
except ImportError:
    import coordination_probe as probe


def cases(client: Any, report: Any) -> None:
    client.request("seed")

    def setup(name: str, **settings: Any) -> tuple[str, str]:
        result = client.request("admit", request=probe.selection(0, [name]))
        partition = result["hint"]["partitionId"]
        client.request("fail-config", partitionId=partition, **settings)
        return partition, result["items"][0]["intentId"]

    def wake(partition: str, source: str = "hint", expected: int = 200) -> Any:
        if source == "sweep":
            return client.request("sweep", expected=expected)
        view = client.request("view", partitionId=partition)
        return client.request(
            "wake",
            expected=expected,
            hint={"partitionId": partition, "wakeRevision": view["wakeRevision"]},
        )

    def rows(intent: str) -> dict[str, Any]:
        state = client.request("state")
        row = next(i for i in state["intents"] if i["intent_id"] == intent)
        attempts = [a for a in state["attempts"] if a["intent_id"] == intent]
        ids = {a["attempt_id"] for a in attempts}
        return {
            "intent": row,
            "attempts": attempts,
            "dispatches": [a for a in state["dispatches"] if a["attempt_id"] in ids],
            "resolutions": [a for a in state["resolutions"] if a["attempt_id"] in ids],
            "peer": [a for a in state["peer"] if a["attempt_id"] in ids],
            "blocks": [
                b
                for b in state["blocks"]
                if b["photo_id"] == row["photo_id"] and b["group_id"] == row["group_id"]
            ],
            "guards": state["guards"],
        }

    def posts(state: dict[str, Any]) -> int:
        return sum(p["method"] == "flickr.groups.pools.add" for p in state["peer"])

    def expired(partition: str) -> None:
        def check() -> bool:
            view = client.request("view", partitionId=partition)
            return view["leaseExpiresUs"] is None or int(view["leaseExpiresUs"]) <= int(
                view["nowUs"]
            )

        probe.await_condition(check, 20, "lease expiry")

    def due(partition: str) -> None:
        def check() -> bool:
            view = client.request("view", partitionId=partition)
            return view["dueUs"] is None or int(view["dueUs"]) <= int(view["nowUs"])

        probe.await_condition(check, 10, "retry due")

    stops = [
        ("001", "before_preflight"),
        ("002", "after_preflight"),
        ("003", "preflight_committed"),
        ("004", "marker_committed"),
        ("005", "handoff"),
        ("006", "response_received"),
        ("007", "rollback_result"),
        ("008", "result_committed"),
        ("009", "after_membership"),
        ("010", "membership_committed"),
    ]
    for source in ("hint", "sweep"):
        for number, stop in stops:
            partition, intent = setup(
                f"crash-{source}-{number}",
                fault=stop,
                rollbackResult=int(stop == "rollback_result"),
            )
            before = client.request("object-status", partitionId=partition)["instance"]
            if stop == "handoff":
                with ThreadPoolExecutor(max_workers=1) as executor:
                    pending = executor.submit(wake, partition, source, 409)
                    probe.await_condition(
                        lambda intent=intent: posts(rows(intent)) == 1, 10, "peer handoff"
                    )
                    client.request("evict", partitionId=partition, expected=409)
                    pending.result(timeout=30)
            else:
                wake(partition, source, 409)
            if stop == "rollback_result":
                client.request("evict", partitionId=partition, expected=409)
            after = client.request("object-status", partitionId=partition)["instance"]
            crashed = rows(intent)
            first_posts = posts(crashed)
            client.request("fail-config", partitionId=partition)
            expired(partition)
            wake(partition, source)
            recovered = rows(intent)
            report.data.setdefault("witnesses", []).append(
                {"case": f"FP-CRASH-{number}.{source}", "crashed": crashed, "recovered": recovered}
            )
            ambiguous = number in {"004", "005", "006", "007"}
            committed = number == "008"
            wanted = (
                "delivery_uncertain"
                if ambiguous
                else "moderation_submitted"
                if committed
                else "retrying"
            )
            report.check(
                f"FP-CRASH-{number}.{source}",
                before != after
                and recovered["intent"]["state"] == wanted
                and len(recovered["blocks"]) == int(ambiguous or committed)
                and posts(recovered) == first_posts
                and first_posts == int(number in {"005", "006", "007", "008"})
                and not recovered["guards"]
                and len(recovered["resolutions"]) == 1,
                actorReset=before != after,
                actualPosts=first_posts,
                state=wanted,
                blocks=len(recovered["blocks"]),
            )
            if not ambiguous and not committed:
                due(partition)
                wake(partition, source)
                final = rows(intent)
                report.check(
                    f"crash.fresh_attempt.{source}.{number}",
                    posts(final) == 1
                    and len(final["attempts"]) == 2
                    and final["intent"]["state"] == "moderation_submitted",
                )
            final = rows(intent)
            count = posts(final)
            client.request("admit", request=probe.selection(0, [final["intent"]["group_id"]]))
            wake(partition)
            wake(partition, "sweep")
            unchanged = rows(intent)
            report.check(
                f"crash.permanent_suppression.{source}.{number}",
                posts(unchanged) == count
                and unchanged["blocks"] == final["blocks"]
                and unchanged["attempts"] == final["attempts"],
            )

    for code, outcome in [
        (6, "moderation_submitted"),
        (7, "moderation_submitted"),
        (9001, "delivery_uncertain"),
        (105, "retrying"),
        (106, "retrying"),
        (3, "added"),
        (0, "added"),
        (-1, "delivery_uncertain"),
    ]:
        partition, intent = setup(f"result-{code}", responseCode=code)
        wake(partition)
        state = rows(intent)
        report.check(
            f"result.code_{code}",
            state["intent"]["state"] == outcome
            and posts(state) == 1
            and len(state["resolutions"]) == 1
            and len(state["blocks"])
            == int(outcome in {"moderation_submitted", "delivery_uncertain"})
            and [p["method"] for p in state["peer"]]
            == ["flickr.photos.getAllContexts", "flickr.groups.getInfo", "flickr.groups.pools.add"]
            and state["peer"][-1]["marker_visible"] == 1
            and not state["guards"],
        )
        if code == 9001:
            client.request("gate", value=1)
        if outcome == "retrying":
            client.request("fail-config", partitionId=partition)
            due(partition)
            wake(partition)
            report.check(f"result.fresh_retry_{code}", posts(rows(intent)) == 2)

    for name, before_age, after_age, count in [
        ("just_inside", 999_999, 999_999, 1),
        ("before_expiry", 1_000_000, 1_000_000, 0),
        ("after_expiry", 0, 1_000_000, 0),
    ]:
        partition, intent = setup("fresh-" + name, beforeAge=before_age, afterAge=after_age)
        wake(partition)
        state = rows(intent)
        report.check(
            "manual_clock." + name,
            posts(state) == count
            and len(state["blocks"]) == count
            and (
                count == 1
                or state["resolutions"][0]["reason"] == "not_dispatched_preflight_expired"
            ),
        )
        if not count:
            client.request("fail-config", partitionId=partition)
            due(partition)
            wake(partition)

    partition, intent = setup("membership-present", present=1)
    wake(partition)
    state = rows(intent)
    report.check(
        "membership.already_present",
        state["intent"]["state"] == "added"
        and len(state["peer"]) == 1
        and posts(state) == 0
        and not state["dispatches"],
    )

    partition, intent = setup("stale-gate", fault="gate_changed")
    wake(partition, expected=409)
    state = rows(intent)
    report.check("fence.gate_revision", posts(state) == 0 and not state["dispatches"])
    client.request("fail-config", partitionId=partition)
    client.request("gate", value=0)
    expired(partition)
    wake(partition, "sweep")
    report.check(
        "recovery.closed_gate_no_dispatch",
        rows(intent)["intent"]["state"] == "retrying" and posts(rows(intent)) == 0,
    )
    client.request("gate", value=1)
    due(partition)
    wake(partition)

    partition, intent = setup("recovery-crash", fault="marker_committed")
    wake(partition, expected=409)
    client.request("fail-config", partitionId=partition, rollbackResult=1)
    expired(partition)
    wake(partition, expected=409)
    partial = rows(intent)
    client.request("evict", partitionId=partition, expected=409)
    client.request("fail-config", partitionId=partition)
    expired(partition)
    wake(partition, "sweep")
    final = rows(intent)
    report.check(
        "recovery.transaction_crash",
        posts(partial) == 0
        and not partial["blocks"]
        and not partial["resolutions"]
        and len(partial["dispatches"]) == 1
        and posts(final) == 0
        and len(final["blocks"]) == 1
        and final["intent"]["state"] == "delivery_uncertain",
    )

    before = client.request("state")
    for table in (
        "submission_attempts",
        "attempt_membership",
        "attempt_preflights",
        "attempt_dispatches",
        "attempt_resolutions",
    ):
        for operation in ("delete", "update", "replace"):
            client.request("attempt-guard", expected=409, kind=table, operation=operation)
            report.check("guards." + table + "." + operation, before == client.request("state"))

    if client.run.state["environment"] == "cloudflare":
        partition, intent = setup("cron-dispatch")
        client.request("cron-enable", value=1)
        deadline = time.monotonic() + 120
        while (
            time.monotonic() < deadline
            and rows(intent)["intent"]["state"] != "moderation_submitted"
        ):
            time.sleep(2)
        client.request("cron-enable", value=0)
        state = rows(intent)
        report.check(
            "entry.actual_cron_dispatch",
            posts(state) == 1
            and len(state["blocks"]) == 1
            and state["intent"]["state"] == "moderation_submitted",
        )

    report.data["scope"] = {
        "productionConformance": False,
        "clock": "injected manual monotonic",
        "reset": "real Durable Object abort/recreation",
        "flickrTransport": "controlled fixture HTTP (local) / HTTPS (hosted)",
        "productionFlickrEnabled": False,
    }


def mutation_check(client: Any, report: Any, name: str) -> None:
    client.request("seed")
    result = client.request("admit", request=probe.selection(0, ["mutation-check"]))
    partition = result["hint"]["partitionId"]
    options: dict[str, Any] = {}
    if name == "unknown_retry":
        options["responseCode"] = 9001
    if name == "unresolved_retry":
        options["fault"] = "marker_committed"
    if name == "inclusive_clock":
        options.update(beforeAge=1_000_000, afterAge=1_000_000)
    client.request("fail-config", partitionId=partition, **options)

    def wake(expected: int = 200) -> None:
        view = client.request("view", partitionId=partition)
        client.request(
            "wake",
            expected=expected,
            hint={"partitionId": partition, "wakeRevision": view["wakeRevision"]},
        )

    if name == "unresolved_retry":
        wake(409)
        client.request("fail-config", partitionId=partition)

        def expired() -> bool:
            view = client.request("view", partitionId=partition)
            return int(view["leaseExpiresUs"]) <= int(view["nowUs"])

        probe.await_condition(expired, 20, "mutation lease expiry")
    wake()
    state = client.request("state")
    actual_posts = [p for p in state["peer"] if p["method"] == "flickr.groups.pools.add"]
    if name == "marker_order":
        passed = len(actual_posts) == 1 and actual_posts[0]["marker_visible"] == 1
    elif name in {"unknown_retry", "unresolved_retry"}:
        passed = state["intents"][0]["state"] == "delivery_uncertain" and len(state["blocks"]) == 1
    elif name == "split_block":
        passed = (
            state["intents"][0]["state"] == "moderation_submitted" and len(state["blocks"]) == 1
        )
    elif name == "inclusive_clock":
        passed = not actual_posts and not state["dispatches"]
    elif name == "removed_guard":
        try:
            client.request(
                "attempt-guard", expected=409, kind="attempt_dispatches", operation="delete"
            )
            passed = client.request("state") == state
        except probe.ProbeError:
            passed = False
    else:
        raise probe.ProbeError("Unknown mutation check.")
    report.check("mutation." + name, passed)
