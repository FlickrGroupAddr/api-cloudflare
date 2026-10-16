"""Actual Lua 5.1 controller/client scheduling and closed read-only view checks."""

import json
import unittest
from typing import Any

from tests.test_submission_status_client import BUNDLE, StatusFixtures, intent, page


class StatusControllerTests(StatusFixtures, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.controller = self.lua.execute(
            (BUNDLE / "SubmissionStatusController.lua").read_text(encoding="utf-8")
        )
        self.view = self.lua.execute(
            (BUNDLE / "SubmissionStatusView.lua").read_text(encoding="utf-8")
        )
        self.context = self.lua.table()
        self.current = self.context
        self.responses: list[Any] = [page([intent(state="queued")], active=1)]
        self.hook = lambda: None

        def request(method, path):
            self.calls.append((method, path))
            self.request_times.append(self.elapsed)
            self.hook()
            response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
            if isinstance(response, tuple):
                return response
            return json.dumps(response), self.lua.table_from({"status": 200})

        def sleep(seconds):
            self.elapsed += seconds

        wrap = self.lua.eval("function(f) return function(...) return f(...) end end")
        self.deps = self.lua.table_from(
            {
                "client": self.client,
                "jsonNull": self.json.null,
                "context": self.context,
                "installationId": "installation-1",
                "currentContext": wrap(lambda: self.current),
                "now": wrap(lambda: self.elapsed),
                "request": wrap(request),
                "sleep": wrap(sleep),
                "protect": self.lua.eval("function(f) return pcall(f) end"),
                "decode": self.lua.eval(
                    "function(j) return function(b) return j.decode(b,1,j.null) end end"
                )(self.json),
            }
        )
        self.c = self.controller.new(self.deps, self.binding)

    def tick(self, c=None):
        c = self.c if c is None else c
        return c.tick(c)

    def open(self, c=None):
        c = self.c if c is None else c
        c.open(c)

    def test_visible_only_null_stop_and_manual_refresh_cadence(self):
        self.responses = [page([intent()])]
        self.assertFalse(self.tick())
        self.open()
        self.assertTrue(self.tick())
        self.assertEqual(len(self.calls), 2)
        self.elapsed += 100
        self.assertFalse(self.tick())
        self.c.refresh(self.c)
        self.assertTrue(self.tick())
        self.c.close(self.c)
        self.elapsed += 100
        self.assertFalse(self.tick())
        self.assertEqual(len(self.calls), 4)

    def test_shared_binding_cache_and_reentrant_read_coalescing(self):
        other = self.controller.new(self.deps, self.binding)
        self.open()
        self.open(other)
        self.hook = lambda: self.assertFalse(self.tick(other))
        self.assertTrue(self.tick())
        self.assertFalse(self.tick(other))
        self.assertEqual(len(self.calls), 2)
        self.elapsed += 15
        self.assertTrue(self.tick(other))
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(all(method == "GET" for method, _ in self.calls))
        self.assertTrue(all("group-submission-intents?" in path for _, path in self.calls))
        self.assertTrue(all("before_" not in path for _, path in self.calls))

    def test_active_and_paused_recommendations(self):
        for delay in (15, 60):
            with self.subTest(delay=delay):
                self.setUp()
                if delay == 60:
                    doc = self.responses[0]
                    doc["summary"]["writeGates"][0].update(
                        state="paused",
                        pausedAt=doc["observedAt"],
                        reasonCode="operator_review_required",
                        affectedActiveIntentCount=1,
                    )
                    doc["intents"][0]["queue"]["holds"] = ["user_flickr_write_gate_paused"]
                    doc["recommendedPollAfterSeconds"] = 60
                self.open()
                self.tick()
                self.assertEqual(self.elapsed, delay)
                self.elapsed += delay - 1
                self.assertFalse(self.tick())
                self.elapsed += 1
                self.assertTrue(self.tick())

    def test_terminal_result_satisfies_other_open_consumers(self):
        self.responses = [page([intent()])]
        other = self.controller.new(self.deps, self.binding)
        self.open()
        self.open(other)
        self.tick()
        self.elapsed += 100
        self.assertFalse(self.tick(other))
        self.assertEqual(len(self.calls), 2)

    def test_installation_owner_serializes_distinct_binding_reads(self):
        binding = self.lua.table_from(
            {"fgaPhotoBindingId": "binding-2", "flickrPhotoId": "photo-2"}
        )
        other = self.controller.new(self.deps, binding)
        self.open()
        self.open(other)
        self.hook = lambda: self.assertFalse(self.tick(other))
        self.tick()
        self.hook = lambda: None
        self.assertFalse(self.tick(other))
        self.elapsed += 5
        self.assertTrue(self.tick(other))
        self.assertEqual(len(self.calls), 3)
        self.assertIn("photo_binding_id=binding-2", self.calls[-1][1])

    def test_nonfinite_and_backward_clocks_refuse_more_reads(self):
        self.open()
        self.tick()
        self.elapsed -= 1
        self.assertFalse(self.tick())
        self.assertTrue(self.c.model.stale)
        self.assertFalse(self.c.visible)
        self.assertEqual(len(self.calls), 2)

    def test_sdk_candidate_has_only_close_and_read_refresh_controls(self):
        # Synthetic SDK surface: execute show and inspect constructed controls.
        # Native host behavior remains outside this deterministic test.
        check = self.lua.eval("""function(view, controller)
            local controls, cleanup, taskfn = {}, nil, nil
            local function control(_, spec)
                controls[#controls+1]=spec
                return spec
            end
            local factory={column=control,static_text=control,
                edit_field=control,push_button=control}
            local context={addCleanupHandler=function(_,fn) cleanup=fn end}
            local dialog
            import=function(name)
                if name=='LrBinding' then return {makePropertyTable=function() return {} end} end
                if name=='LrView' then return {osFactory=function() return factory end,
                    bind=function(k) return k end} end
                if name=='LrDialogs' then return {presentModalDialog=function(spec)
                    dialog=spec
                    return 'ok'
                end} end
            end
            view.show(controller,context,{start=function(fn) taskfn=fn end,sleep=function() end})
            assert(dialog.actionVerb=='Close' and dialog.cancelVerb=='Close')
            local buttons=0
            for _,spec in ipairs(controls) do
                if spec.action then
                    assert(spec.title=='Refresh status')
                    buttons=buttons+1
                end
            end
            assert(buttons==1 and not controller.visible and taskfn~=nil and cleanup~=nil)
            cleanup()
            taskfn() -- Closed task must not request anything.
            return true
        end""")
        self.assertTrue(check(self.view, self.c))
        self.assertEqual(self.calls, [])

    def test_retry_after_backoff_and_last_good_stale(self):
        self.open()
        self.tick()
        headers = self.lua.table_from({"status": 503})
        headers[1] = self.lua.table_from({"field": "Retry-After", "value": "180"})
        self.responses = [("private hostile response", headers)]
        self.elapsed += 15
        self.tick()
        self.assertTrue(self.c.model.stale)
        self.assertEqual(len(self.c.model.data.intents), 1)
        self.assertEqual(self.c.model.reason, "unavailable")
        for _ in range(3):
            self.c.refresh(self.c)
            self.assertFalse(self.tick())
        self.elapsed += 179
        self.assertFalse(self.tick())
        self.elapsed += 1
        self.assertTrue(self.tick())
        self.assertEqual(self.c.owner.failures, 2)
        self.assertEqual(self.c.record.nextAt - self.elapsed, 180)
        headers[1] = None
        self.elapsed += 180
        self.tick()
        self.assertEqual(self.c.record.nextAt - self.elapsed, 240)

    def test_retry_after_blocks_every_binding_in_the_installation(self):
        binding = self.lua.table_from(
            {"fgaPhotoBindingId": "binding-2", "flickrPhotoId": "photo-2"}
        )
        other = self.controller.new(self.deps, binding)
        headers = self.lua.table_from({"status": 429})
        headers[1] = self.lua.table_from({"field": "Retry-After", "value": "180"})
        self.responses = [("private rate limit", headers)]
        self.open()
        self.open(other)
        self.assertTrue(self.tick())
        for elapsed in (5, 179):
            self.elapsed = elapsed
            other.refresh(other)
            self.assertFalse(self.tick(other))
            self.assertEqual(len(self.calls), 1)
        doc = page([])
        doc["photoBindingId"] = "binding-2"
        self.responses = [doc]
        self.elapsed = 180
        self.assertTrue(self.tick(other))
        self.assertEqual(self.request_times, [0, 180, 185])
        self.assertEqual(other.owner.failures, 0)

    def test_shared_503_and_transport_backoff_resets_after_complete_recovery(self):
        binding = self.lua.table_from(
            {"fgaPhotoBindingId": "binding-2", "flickrPhotoId": "photo-2"}
        )
        other = self.controller.new(self.deps, binding)
        headers = self.lua.table_from({"status": 503})
        self.responses = [("private outage", headers)]
        self.open()
        self.open(other)
        self.tick()
        self.assertEqual(self.c.owner.nextReadAt, 60)
        self.elapsed = 5
        self.assertFalse(self.tick(other))
        self.assertEqual(len(self.calls), 1)
        request = self.deps.request
        self.deps.request = self.lua.eval("function() error('private transport error') end")
        self.elapsed = 60
        self.assertTrue(self.tick(other))
        self.assertEqual(self.c.owner.failures, 2)
        self.assertEqual(self.c.owner.nextReadAt, 180)
        self.elapsed = 179
        self.c.refresh(self.c)
        self.assertFalse(self.tick())
        self.deps.request = request
        self.responses = [page([])]
        self.elapsed = 180
        self.assertTrue(self.tick())
        self.assertEqual(self.c.owner.failures, 0)
        self.assertEqual(self.c.owner.nextReadAt, 190)
        self.responses = [("private outage", headers)]
        self.elapsed = 190
        self.assertTrue(self.tick(other))
        self.assertEqual(self.c.owner.failures, 1)
        self.assertEqual(self.c.owner.nextReadAt, 250)
        self.assertEqual(other.model.reason, "unavailable")

    def test_close_generation_and_context_fence_late_results(self):
        self.open()
        self.hook = lambda: self.c.close(self.c)
        self.assertFalse(self.tick())
        self.assertIsNone(self.c.record.good)
        self.assertEqual(len(self.calls), 1)
        self.elapsed += 5
        self.open()
        self.hook = lambda: setattr(self, "current", self.lua.table())
        self.assertFalse(self.tick())
        self.assertIsNone(self.c.record.good)
        self.tick()
        self.assertIsNone(self.c.model.data)

    def test_close_reopen_during_read_discards_old_generation(self):
        self.open()

        def reopen():
            self.c.close(self.c)
            self.open()

        self.hook = reopen
        self.assertFalse(self.tick())
        self.assertIsNone(self.c.record.good)
        self.assertEqual(len(self.calls), 1)

    def test_transport_exception_and_unknown_error_are_allowlisted(self):
        self.open()
        self.deps.request = self.lua.eval("function() error('secret host failure') end")
        self.assertTrue(self.tick())
        self.assertEqual(self.c.model.reason, "unavailable")
        self.assertEqual(self.c.record.nextAt - self.elapsed, 60)
        shown = self.view.model(self.c)
        self.assertNotIn("secret", shown.notice)
        self.assertEqual(len(shown.rows), 0)

    def test_every_state_and_protected_pair_stays_read_only(self):
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
                self.setUp()
                active = int(state in {"queued", "attempting", "retrying", "throttled"})
                self.responses = [page([intent(state=state)], active=active)]
                self.open()
                self.tick()
                shown = self.view.model(self.c)
                self.assertTrue(shown.readOnly)
                self.assertEqual(len(shown.rows), 1)
                row = shown.rows[1]
                self.assertTrue(row.readOnly)
                self.assertIsNone(row.action)
                self.assertIsNone(row.percentage)
                self.assertIsNone(row.eta)
                if state in {"moderation_submitted", "delivery_uncertain"}:
                    self.assertIn("will not submit this exact pair again", row.title)

    def test_failed_second_pass_retains_only_previous_complete_model(self):
        self.open()
        self.tick()
        self.elapsed += 15
        self.responses = [page([intent(state="queued")], active=1)] * 3 + [
            ("partial failed pass", self.lua.table_from({"status": 503}))
        ]
        self.tick()
        self.assertTrue(self.c.model.stale)
        self.assertEqual(self.c.model.data.requestCount, 2)
        self.assertIn("Stale", self.view.model(self.c).notice)

    def test_failed_paginated_refresh_restarts_from_page_one(self):
        from tests.test_submission_status_client import EARLY

        self.responses = [page([intent()])] * 2
        self.open()
        self.tick()
        first = page(
            [intent(i) for i in range(101, 1, -1)],
            {"beforeCreatedAt": EARLY, "beforeIntentId": "intent-00002"},
        )
        last = page([intent()])
        self.responses += [first, ("private failure", self.lua.table_from({"status": 503}))]
        self.elapsed += 5
        self.c.refresh(self.c)
        self.tick()
        self.assertTrue(self.c.model.stale)
        self.assertEqual(len(self.c.model.data.intents), 1)
        self.responses += [first, last, first, last]
        self.elapsed += 60
        self.tick()
        self.assertNotIn("before_", self.calls[4][1])
        self.assertEqual(len(self.c.model.data.intents), 101)
        self.assertFalse(self.c.model.stale)


if __name__ == "__main__":
    unittest.main()
