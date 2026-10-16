"""Execute the retained status boundary in Lua 5.1 with real JSON decoding."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
STAMP = "2026-10-16T12:00:00.000000Z"
EARLY = "2026-10-15T12:00:00.000000Z"


def intent(index=1, state="cancelled"):
    value = {
        "fgaSubmissionIntentId": f"intent-{index:05}",
        "fgaPhotoBindingId": "binding-1",
        "flickrPhotoId": "photo-1",
        "flickrGroupId": f"group-{index:05}",
        "groupDisplayName": None,
        "groupDisplayNameObservedAt": None,
        "state": state,
        "stateRevision": 1,
        "createdAt": EARLY,
        "stateChangedAt": STAMP,
        "terminalAt": STAMP,
        "attemptCount": 0,
        "queue": None,
        "lastOutcome": None,
        "permanentSubmissionBlock": None,
        "attention": None,
    }
    if state in {"queued", "attempting", "retrying", "throttled"}:
        value["terminalAt"] = None
        value["queue"] = {
            "isPartitionHead": True,
            "activeAheadInPartition": 0,
            "nextWorkNotBefore": None if state == "attempting" else STAMP,
            "holds": [],
        }
    if state in {"moderation_submitted", "delivery_uncertain", "added", "needs_attention"}:
        reason = {
            "moderation_submitted": "moderation_submission_recorded",
            "delivery_uncertain": "post_dispatch_result_unavailable",
            "added": "added",
            "needs_attention": "request_policy_rejected",
        }[state]
        value["lastOutcome"] = {
            "reasonCode": reason,
            "flickrResultCode": None,
            "observedAt": STAMP,
            "correlationId": "attempt-1",
        }
    if state in {"moderation_submitted", "delivery_uncertain"}:
        value["permanentSubmissionBlock"] = {
            "reasonCode": "moderation_submission_recorded"
            if state == "moderation_submitted"
            else "delivery_uncertain",
            "createdAt": STAMP,
        }
    if state in {"needs_attention", "delivery_uncertain"}:
        value["attention"] = {
            "kind": state,
            "reasonCode": value["lastOutcome"]["reasonCode"],
            "occurredAt": STAMP,
            "operatorAction": "correct_future_selection"
            if state == "needs_attention"
            else "inspect_flickr_no_fga_resubmit",
            "fgaResubmissionAllowed": False,
        }
    return value


def page(items, next_page=None, active=0):
    return {
        "schemaVersion": 1,
        "observedAt": STAMP,
        "view": "history",
        "pageSize": 100,
        "photoBindingId": "binding-1",
        "summary": {
            "activeIntentCount": active,
            "activePartitionCount": active,
            "attentionIntentCount": sum(
                v["state"] in {"needs_attention", "delivery_uncertain"} for v in items
            ),
            "oldestActiveEnqueuedAt": EARLY if active else None,
            "writeGates": [
                {
                    "scope": scope,
                    "state": "enabled",
                    "revision": 1,
                    "pausedAt": None,
                    "reasonCode": None,
                    "affectedActiveIntentCount": 0,
                }
                for scope in ("user", "deployment")
            ],
        },
        "intents": items,
        "nextPage": next_page,
        "recommendedPollAfterSeconds": 15 if active else None,
    }


class StatusFixtures:
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        assert self.lua.lua_version == (5, 1)
        self.json = self.lua.execute((BUNDLE / "dkjson.lua").read_text(encoding="utf-8"))
        self.client = self.lua.execute(
            (BUNDLE / "SubmissionStatusClient.lua").read_text(encoding="utf-8")
        )
        self.binding = self.lua.table_from(
            {"fgaPhotoBindingId": "binding-1", "flickrPhotoId": "photo-1"}
        )
        self.calls = []
        self.elapsed = 0
        self.request_times = []

    def decoded(self, value):
        return self.json.decode(json.dumps(value), 1, self.json.null)[0]

    def read(self, responses, prior=None, cancel=None):
        def sleep(seconds):
            self.elapsed += seconds

        def request(method, path):
            self.calls.append((method, path))
            self.request_times.append(self.elapsed)
            response = responses[min(len(self.calls) - 1, len(responses) - 1)]
            if isinstance(response, tuple):
                return response
            return json.dumps(response), self.lua.table_from({"status": 200})

        deps = self.lua.table_from(
            {
                "request": request,
                "decode": self.lua.eval(
                    "function(j) return function(b) return j.decode(b,1,j.null) end end"
                )(self.json),
                "jsonNull": self.json.null,
                "cancelled": cancel or (lambda: False),
            }
        )
        # Python callbacks are userdata; wrap at the injected Lua function boundary.
        deps.request = self.lua.eval("function(f) return function(...) return f(...) end end")(
            request
        )
        deps.sleep = self.lua.eval("function(f) return function(s) return f(s) end end")(sleep)
        return self.client.history(deps, self.binding, prior)


class StatusClientTests(StatusFixtures, unittest.TestCase):
    def test_all_closed_states_and_protected_presentation(self):
        for state in (
            "queued",
            "attempting",
            "retrying",
            "throttled",
            "added",
            "moderation_submitted",
            "delivery_uncertain",
            "needs_attention",
            "cancelled",
        ):
            with self.subTest(state=state):
                value = self.decoded(intent(state=state))
                self.assertTrue(self.client.validateIntent(value, self.json.null, self.binding))
                shown = self.client.presentation(value, STAMP, self.json.null)
                self.assertTrue(shown.readOnly)

    def test_complete_two_traversals_and_terminal_stop(self):
        result = self.read([page([intent()])])
        self.assertEqual(result.state, "complete")
        self.assertEqual(len(self.calls), 2)
        self.assertIsNone(result.minimumRefreshAfterSeconds)

    def test_paginated_complete_history_and_encoded_continuation(self):
        first = page(
            [intent(i) for i in range(101, 1, -1)],
            {"beforeCreatedAt": EARLY, "beforeIntentId": "intent-00002"},
        )
        result = self.read([first, page([intent()]), first, page([intent()])])
        self.assertEqual(len(result.intents), 101)
        self.assertEqual(len(self.calls), 4)
        self.assertIn("before_created_at=2026-10-15T12%3A00%3A00.000000Z", self.calls[1][1])

    def test_changed_second_pass_is_unavailable_and_prior_is_stale(self):
        before = page([intent()])
        after = copy.deepcopy(before)
        after["intents"][0]["stateRevision"] = 2
        result = self.read([before, after], self.decoded({"state": "complete"}))
        self.assertEqual(result[1], "status_changed")
        self.assertTrue(result[2].stale)

    def test_rejects_malformed_identity_unknown_block_and_json_extensions(self):
        variants = []
        for key, value in (
            ("flickrPhotoId", "foreign"),
            ("state", "future"),
            ("permanentSubmissionBlock", {"reasonCode": "unknown", "createdAt": STAMP}),
            ("attention", {}),
            ("createdAt", "2026-02-30T12:00:00.000000Z"),
        ):
            item = intent()
            item[key] = value
            variants.append(json.dumps(page([item])))
        variants.extend(
            [
                json.dumps(page([])).replace(
                    '"schemaVersion": 1', '"schemaVersion": 1,"schemaVersion":1'
                ),
                json.dumps(page([])) + " trailing",
                '{/* comment */"schemaVersion":1}',
            ]
        )
        for body in variants:
            with self.subTest(body=body[:40]):
                self.calls.clear()
                self.assertEqual(
                    self.read([(body, self.lua.table_from({"status": 200}))])[1], "response_invalid"
                )
                self.assertEqual(len(self.calls), 1)

    def test_rate_limit_and_cancel_have_no_followup_reads(self):
        headers = self.lua.table_from({"status": 429})
        headers[1] = self.lua.table_from({"field": "Retry-After", "value": "120"})
        result = self.read([("hostile body never displayed", headers)])
        self.assertEqual(result[2].minimumRefreshAfterSeconds, 120)
        self.assertEqual(len(self.calls), 1)
        self.calls.clear()
        self.assertEqual(self.read([page([])], cancel=lambda: True)[1], "cancelled")
        self.assertEqual(self.calls, [])

    def test_failed_later_page_never_publishes_earlier_rows(self):
        first = page(
            [intent(i) for i in range(101, 1, -1)],
            {"beforeCreatedAt": EARLY, "beforeIntentId": "intent-00002"},
        )
        result = self.read([first, ("private failure", self.lua.table_from({"status": 503}))])
        self.assertIsNone(result[0])
        self.assertEqual(result[1], "unavailable")
        self.assertIsNone(result[2].intents)
        self.assertEqual(len(self.calls), 2)

    def test_revision_regression_and_disappearing_retained_identity_fail_closed(self):
        prior = self.decoded(
            {
                "fgaPhotoBindingId": "binding-1",
                "flickrPhotoId": "photo-1",
                "intents": [{**intent(), "stateRevision": 2}],
                "observedAt": STAMP,
                "summary": page([])["summary"],
            }
        )
        for current in (page([intent()]), page([])):
            self.calls.clear()
            result = self.read([current], prior)
            self.assertEqual(result[1], "status_changed")
            self.assertTrue(result[2].stale)

    def test_paused_hold_cadence_and_contradictory_holds(self):
        value = page([intent(state="queued")], active=1)
        value["summary"]["writeGates"][0].update(
            {
                "state": "paused",
                "pausedAt": STAMP,
                "reasonCode": "operator_review_required",
                "affectedActiveIntentCount": 1,
            }
        )
        value["recommendedPollAfterSeconds"] = 60
        value["intents"][0]["queue"]["holds"] = ["user_flickr_write_gate_paused"]
        result = self.read([value])
        self.assertEqual(result.minimumRefreshAfterSeconds, 60)
        self.assertGreaterEqual(self.request_times[1] - self.request_times[0], 60)
        shown = self.client.presentation(result.intents[1], STAMP, self.json.null)
        self.assertIn("Queue order is preserved", shown.text)
        value["intents"][0]["queue"]["holds"] = []
        self.calls.clear()
        self.assertEqual(self.read([value])[1], "response_invalid")

    def test_large_traversals_obey_sustained_bucket_admission(self):
        pages = []
        for number in range(12):
            high = 1201 - number * 100
            items = [intent(i) for i in range(high, high - 100, -1)]
            pages.append(
                page(
                    items,
                    {
                        "beforeCreatedAt": EARLY,
                        "beforeIntentId": items[-1]["fgaSubmissionIntentId"],
                    },
                )
            )
        pages.append(page([intent()]))
        result = self.read(pages + pages)
        self.assertEqual(len(result.intents), 1201)
        self.assertEqual(len(self.calls), 26)
        self.assertTrue(
            all(
                later - earlier >= 5
                for earlier, later in zip(self.request_times, self.request_times[1:], strict=False)
            )
        )
        tokens, last = 20, 0
        for now in self.request_times:
            tokens = min(20, tokens + (now - last) / 5)
            self.assertGreaterEqual(tokens, 1)
            tokens -= 1
            last = now

    def test_waits_are_cancelled_without_another_request(self):
        result = self.read([page([])], cancel=lambda: self.elapsed >= 2)
        self.assertEqual(result[1], "cancelled")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.elapsed, 2)

    def test_prior_observation_and_gate_regressions_cannot_become_fresh(self):
        current = page([intent()])
        for variant in ("observation", "gate_revision", "gate_state"):
            prior = {
                "fgaPhotoBindingId": "binding-1",
                "flickrPhotoId": "photo-1",
                "observedAt": STAMP,
                "summary": copy.deepcopy(current["summary"]),
                "intents": [intent()],
            }
            if variant == "observation":
                prior["observedAt"] = "2026-10-16T12:00:01.000000Z"
            else:
                gate = prior["summary"]["writeGates"][0]
                gate.update(
                    {"state": "paused", "pausedAt": STAMP, "reasonCode": "operator_review_required"}
                )
                if variant == "gate_revision":
                    gate["revision"] = 2
            self.calls.clear()
            result = self.read([current], self.decoded(prior))
            self.assertEqual(result[1], "status_changed")
            self.assertTrue(result[2].stale)

    def test_unchanged_revision_may_update_independent_queue_advisory(self):
        current = page([intent(state="queued")], active=1)
        old_intent = copy.deepcopy(current["intents"][0])
        old_intent["queue"].update(
            {
                "isPartitionHead": False,
                "activeAheadInPartition": 1,
                "nextWorkNotBefore": None,
            }
        )
        prior = self.decoded(
            {
                "fgaPhotoBindingId": "binding-1",
                "flickrPhotoId": "photo-1",
                "observedAt": STAMP,
                "summary": current["summary"],
                "intents": [old_intent],
            }
        )
        result = self.read([current], prior)
        self.assertEqual(result.state, "complete")
        self.assertGreaterEqual(self.request_times[1] - self.request_times[0], 15)


if __name__ == "__main__":
    unittest.main()
