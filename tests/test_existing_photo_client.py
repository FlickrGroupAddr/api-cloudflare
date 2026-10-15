"""Exercise the bundled read-only photo protocol in actual Lua 5.1."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

PLUGIN = Path(__file__).resolve().parents[1] / "clients/lightroom/FGA-LrC15.lrplugin"
SUPPORT = Path(os.environ.get("FGA_LUA_SUPPORT", str(PLUGIN)))
WHEN = "2026-10-15T12:00:00.123456Z"


class ExistingPhotoClientTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.lua.globals().support = SUPPORT.as_posix()
        self.lua.execute('package.path = support .. "/?.lua;" .. package.path')
        self.client = self.lua.execute((PLUGIN / "ExistingPhotoClient.lua").read_text())
        self.json = self.lua.execute('return require "dkjson"')
        self.calls = []
        self.responses = []
        decode_lua = self.lua.execute("""
            local json = require "dkjson"
            return function(body)
                local value, position, reason = json.decode(body, 1, json.null)
                if reason or not body:sub(position):match("^%s*$") then return nil end
                return value
            end
        """)
        self.dependencies = self.lua.table_from(
            {"request": self.request, "decode": decode_lua, "jsonNull": self.json.null}
        )

    def decode(self, body):
        decoded = self.json.decode(body, 1, self.json.null)
        value, position = decoded[:2]
        error = decoded[2] if len(decoded) > 2 else None
        if error or body[position - 1 :].strip():
            raise ValueError("invalid JSON")
        return value

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        status, value = self.responses.pop(0)
        return json.dumps(value), self.lua.table_from({"status": status})

    def photo(self, identity="photo-1"):
        return {
            "flickrPhotoId": identity,
            "title": "Fixture title",
            "dateUploaded": "1700000000",
            "dateTaken": "2026-10-15 10:30:00",
            "thumbnail": {
                "url": "https://live.staticflickr.com/123/fixture_q.jpg",
                "sizeClass": "q",
            },
        }

    def page(self, **patch):
        return {
            "schemaVersion": 1,
            "linkedFlickrRevision": 7,
            "observedAt": WHEN,
            "page": 1,
            "pageSize": 5,
            "pages": 1,
            "total": 1,
            "photos": [self.photo()],
            **patch,
        }

    def binding(self, **patch):
        return {
            "schemaVersion": 1,
            "fgaPhotoBindingId": "binding-1",
            "sourceKind": "existing_public_flickr_photo",
            "flickrPhotoId": "photo-1",
            "linkedFlickrRevision": 7,
            "verificationRevision": 3,
            "verifiedAt": WHEN,
            **patch,
        }

    def membership(self, groups=None, **patch):
        return {
            "schemaVersion": 1,
            "fgaPhotoBindingId": "binding-1",
            "flickrPhotoId": "photo-1",
            "observationRevision": 4,
            "observedAt": WHEN,
            "groups": groups if groups is not None else [],
            "nextAfterGroupId": None,
            **patch,
        }

    def test_discovery_fixed_request_and_explicit_empty(self):
        self.responses = [(200, self.page()), (200, self.page(photos=[], total=0, pages=0))]
        page = self.client.discover(self.dependencies, 1)
        self.assertEqual(page.photos[1].flickrPhotoId, "photo-1")
        empty = self.client.discover(self.dependencies, 1)
        self.assertEqual(len(empty.photos), 0)
        self.assertEqual(
            self.calls[0][:2], ("GET", "/api/v001/existing-public-photos?page=1&page_size=5")
        )

    def test_discovery_invalid_whole_pages_are_never_salvaged(self):
        malformed = [
            self.page(photos={}),
            self.page(photos=None),
            self.page(photos=[self.photo(), self.photo()]),
            self.page(photos=[self.photo(), None]),
            self.page(linkedFlickrRevision=0),
            self.page(page=2),
            self.page(total=0),
            self.page(unknown="bad"),
        ]
        for value in malformed:
            with self.subTest(value=value):
                self.responses = [(200, value)]
                result, reason = self.client.discover(self.dependencies, 1)
                self.assertIsNone(result)
                self.assertEqual(reason, "response_invalid")

    def test_thumbnail_origin_and_path_are_closed(self):
        for url in (
            "http://live.staticflickr.com/1/x_q.jpg",
            "https://live.staticflickr.com.evil/1/x_q.jpg",
            "https://live.staticflickr.com:443/1/x_q.jpg",
            "https://user@live.staticflickr.com/1/x_q.jpg",
            "https://live.staticflickr.com/1/x_q.jpg?redirect=evil",
            "https://live.staticflickr.com/1/../x_q.jpg",
            "https://live.staticflickr.com/1/x_q.jpg#fragment",
        ):
            self.assertFalse(self.client.allowedThumbnail(url))
        for extension in ("jpg", "jpeg", "png"):
            self.assertTrue(
                self.client.allowedThumbnail(f"https://live.staticflickr.com/1/x_q.{extension}")
            )

    def test_fresh_proof_exact_lookup_and_upload_binding_reuse(self):
        self.responses = [
            (201, self.binding()),
            (200, self.binding(sourceKind="fga_direct_upload")),
        ]
        proof = self.client.prove(self.dependencies, "photo-1", 7)
        self.assertEqual(proof.verificationRevision, 3)
        self.assertEqual(self.calls[0][0:2], ("POST", "/api/v001/existing-public-photo-bindings"))
        body = self.calls[0][2]
        self.assertEqual(
            set(body.keys()), {"schemaVersion", "flickrPhotoId", "expectedLinkedFlickrRevision"}
        )
        self.assertEqual(body.expectedLinkedFlickrRevision, 7)
        self.assertEqual(
            self.client.prove(self.dependencies, "photo-1", 7).sourceKind, "fga_direct_upload"
        )

    def test_proof_mismatch_or_failed_read_cannot_reuse_previous_revision(self):
        for patch in (
            {"flickrPhotoId": "other"},
            {"linkedFlickrRevision": 8},
            {"verificationRevision": 0},
        ):
            self.responses = [(200, self.binding(**patch))]
            result, reason = self.client.prove(self.dependencies, "photo-1", 7)
            self.assertIsNone(result)
            self.assertEqual(reason, "response_invalid")
        self.responses = [(409, {"schemaVersion": 1, "error": {"code": "flickr_link_changed"}})]
        result, reason = self.client.prove(self.dependencies, "photo-1", 7)
        self.assertIsNone(result)
        self.assertEqual(reason, "flickr_link_changed")

    def test_memberships_aggregate_all_pages_and_percent_encode_cursor(self):
        first = {"flickrGroupId": "1@N01", "displayName": "First"}
        second = {"flickrGroupId": "2@N02", "displayName": "Second"}
        self.responses = [
            (200, self.membership([first], nextAfterGroupId="1@N01")),
            (200, self.membership([second])),
        ]
        result = self.client.memberships(self.dependencies, self.decode(json.dumps(self.binding())))
        result = result[0] if isinstance(result, tuple) else result
        self.assertEqual(len(result.groups), 2)
        self.assertIn("observation_revision=4&after_group_id=1%40N01", self.calls[1][1])

    def test_failed_continuation_discards_whole_membership_observation(self):
        first = {"flickrGroupId": "1", "displayName": "First"}
        self.responses = [
            (200, self.membership([first], nextAfterGroupId="1")),
            (503, {"error": {"code": "membership_observation_unavailable"}}),
        ]
        result, reason = self.client.memberships(
            self.dependencies, self.decode(json.dumps(self.binding()))
        )
        self.assertIsNone(result)
        self.assertEqual(reason, "membership_observation_unavailable")

    def test_membership_change_restarts_exactly_once(self):
        changed = (409, {"error": {"code": "membership_observation_changed"}})
        self.responses = [changed, (200, self.membership(observationRevision=5))]
        result = self.client.memberships(self.dependencies, self.decode(json.dumps(self.binding())))
        result = result[0] if isinstance(result, tuple) else result
        self.assertEqual(result.observationRevision, 5)
        self.assertEqual(self.calls[0][1], self.calls[1][1])
        self.calls = []
        self.responses = [changed, changed]
        result, reason = self.client.memberships(
            self.dependencies, self.decode(json.dumps(self.binding()))
        )
        self.assertIsNone(result)
        self.assertEqual(reason, "membership_observation_changed")
        self.assertEqual(len(self.calls), 2)

    def test_membership_object_null_duplicate_and_out_of_order_fail(self):
        group = {"flickrGroupId": "1", "displayName": "First"}
        for value in (
            self.membership(groups={}),
            self.membership(groups=[group, group]),
            self.membership(groups=[None]),
            self.membership(nextAfterGroupId="1"),
        ):
            self.responses = [(200, value)]
            result, reason = self.client.memberships(
                self.dependencies, self.decode(json.dumps(self.binding()))
            )
            self.assertIsNone(result)
            self.assertEqual(reason, "response_invalid")

    def test_network_call_can_yield_and_cancellation_prevents_next_request(self):
        self.lua.globals().client = self.client
        self.lua.globals().deps = self.dependencies
        self.lua.globals().body = json.dumps(self.page())
        first, marker, second, identity = self.lua.execute("""
            deps.request = function() coroutine.yield("network"); return body, {status=200} end
            local task = coroutine.create(function()
                return client.discover(deps, 1).photos[1].flickrPhotoId
            end)
            local first, marker = coroutine.resume(task)
            local second, identity = coroutine.resume(task)
            return first, marker, second, identity
        """)
        self.assertEqual((first, marker, second, identity), (True, "network", True, "photo-1"))
        self.dependencies.cancelled = lambda: True
        result, reason = self.client.discover(self.dependencies, 1)
        self.assertIsNone(result)
        self.assertEqual(reason, "cancelled")
        self.assertEqual(self.calls, [])

    def test_native_release_gate_and_non_destructive_surface(self):
        self.assertFalse(self.client.PRODUCTION_QUALIFIED)
        for name in (
            "ExistingPhotoClient.lua",
            "ExistingPhotoBrowser.lua",
            "RunExistingPhotoBrowser.lua",
        ):
            source = (PLUGIN / name).read_text()
            for forbidden in (
                "LrApplication",
                "LrCatalog",
                "addPhotoByRemoteId",
                "recordPublishedPhotoId",
                "photosets",
                "postMultipart",
            ):
                self.assertNotIn(forbidden, source)
        run = (PLUGIN / "RunExistingPhotoBrowser.lua").read_text()
        self.assertIn("postAsyncTaskWithContext", run)
        self.assertIn("LrTasks.pcall(Browser.run", run)

    def test_all_new_sdk_entrypoints_compile_as_lua_51(self):
        compile_source = self.lua.eval("function(source) return assert(loadstring(source)) end")
        for name in (
            "ExistingPhotoClient.lua",
            "ExistingPhotoBrowser.lua",
            "RunExistingPhotoBrowser.lua",
        ):
            self.assertIsNotNone(compile_source((PLUGIN / name).read_text()))

    def prepare_browser(self, directory, action="cancel"):
        globals_ = self.lua.globals()
        globals_.plugin = PLUGIN.as_posix()
        globals_.cacheRoot = directory
        globals_.makeDirectory = lambda path: Path(path).mkdir(parents=True, exist_ok=True) or True
        globals_.pathExists = lambda path: Path(path).exists()

        def delete(path):
            import shutil

            shutil.rmtree(path)
            return True

        globals_.deleteDirectory = delete
        globals_.modalAction = action
        self.lua.execute("""
            package.path = plugin .. "/?.lua;" .. package.path
            local factory = {
                control_spacing=function() return 4 end, label_spacing=function() return 2 end,
            }
            for _, kind in ipairs({"row", "column", "picture", "radio_button",
                    "static_text", "push_button", "scrolled_view"}) do
                factory[kind] = function(self, args) args.kind=kind; return args end
            end
            messages, dialogs, cleanups = {}, {}, {}
            local modules = {
                LrBinding={makePropertyTable=function() return {} end},
                LrDate={currentTime=function() return 1234.5 end},
                LrDialogs={
                    message=function(title, message)
                        messages[#messages+1]={title=title,message=message}
                    end,
                    presentModalDialog=function(args)
                        dialogs[#dialogs+1]=args
                        if args.title == "Currently in Flickr groups" then return "ok" end
                        args.contents.bind_to_object.selected="photo-1"
                        return modalAction
                    end,
                },
                LrFileUtils={createAllDirectories=makeDirectory, exists=pathExists,
                    delete=deleteDirectory, chooseUniqueFileName=function(path) return path end},
                LrPathUtils={child=function(parent, child) return parent .. "/" .. child end,
                    getStandardFilePath=function() return cacheRoot end},
                LrTasks={pcall=pcall},
                LrLogger=function()
                    return {enable=function() end, warn=function() end}
                end,
                LrView={osFactory=function() return factory end, bind=function(key) return key end},
            }
            function import(name) return modules[name] end
            sdkTasks=modules.LrTasks
            context={addCleanupHandler=function(self, callback) cleanups[#cleanups+1]=callback end}
            function cleanup() for _, callback in ipairs(cleanups) do callback() end end
            function mockThumbnail(url)
                return string.char(255,216,255,217), "image/jpeg", url
            end
        """)
        browser = self.lua.execute((PLUGIN / "ExistingPhotoBrowser.lua").read_text())
        self.dependencies.thumbnailTransportQualified = True
        self.dependencies.fetchThumbnail = globals_.mockThumbnail
        return browser, globals_.context

    def test_browser_cancel_removes_only_transient_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            browser, context = self.prepare_browser(directory)
            self.responses = [(200, self.page())]
            result, reason = browser.run(context, self.dependencies)
            self.assertIsNone(result)
            self.assertEqual(reason, "cancelled")
            self.lua.globals().cleanup()
            self.assertEqual(len(self.lua.globals().dialogs), 1)
            self.assertEqual(list(Path(directory).rglob("image-*")), [])
            self.assertEqual(list((Path(directory) / "fga-existing-photos").iterdir()), [])
            self.assertEqual(len(self.calls), 1)

    def test_browser_thumbnail_failure_publishes_no_rows_or_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            browser, context = self.prepare_browser(directory, "ok")
            self.dependencies.fetchThumbnail = self.lua.eval(
                'function() return "not-image", "text/html", "wrong" end'
            )
            self.responses = [(200, self.page())]
            result, reason = browser.run(context, self.dependencies)
            self.assertIsNone(result)
            self.assertEqual(reason, "thumbnail_unavailable")
            self.lua.globals().cleanup()
            self.assertEqual(len(self.lua.globals().dialogs), 0)
            self.assertEqual(self.lua.globals().messages[1].title, "Public photos unavailable")
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(list(Path(directory).rglob("image-*")), [])

    def test_browser_select_proves_before_fresh_membership_read(self):
        with tempfile.TemporaryDirectory() as directory:
            browser, context = self.prepare_browser(directory, "ok")
            self.responses = [(200, self.page()), (201, self.binding()), (200, self.membership())]
            binding, observation = browser.run(context, self.dependencies)
            self.assertEqual(binding.flickrPhotoId, "photo-1")
            self.assertEqual(len(observation.groups), 0)
            self.lua.globals().cleanup()
            self.assertEqual([call[0] for call in self.calls], ["GET", "POST", "GET"])
            self.assertEqual(self.lua.globals().dialogs[2].title, "Currently in Flickr groups")
            self.assertEqual(list(Path(directory).rglob("image-*")), [])

    def test_browser_unqualified_transport_sends_no_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            browser, context = self.prepare_browser(directory)
            self.dependencies.thumbnailTransportQualified = False
            result, reason = browser.run(context, self.dependencies)
            self.assertIsNone(result)
            self.assertEqual(reason, "qualification_required")
            self.assertEqual(self.calls, [])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_later_photo_page_failure_is_unavailable_not_end_of_list(self):
        with tempfile.TemporaryDirectory() as directory:
            browser, context = self.prepare_browser(directory, "next")
            self.responses = [
                (200, self.page(pages=2, total=6)),
                (503, {"error": {"code": "existing_photo_discovery_unavailable"}}),
            ]
            result, reason = browser.run(context, self.dependencies)
            self.assertIsNone(result)
            self.assertEqual(reason, "existing_photo_discovery_unavailable")
            self.lua.globals().cleanup()
            self.assertEqual(len(self.lua.globals().dialogs), 1)
            self.assertEqual(self.lua.globals().messages[1].title, "Public photos unavailable")
            self.assertEqual([call[0] for call in self.calls], ["GET", "GET"])

    def test_image_cache_budget_and_signature_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            browser, _ = self.prepare_browser(directory)
            self.assertFalse(browser.validImage("x" * 262145, "image/jpeg"))
            self.assertFalse(browser.validImage("<html>fixture</html>", "image/jpeg"))
            self.assertFalse(browser.validImage("PNG", "image/png"))
            self.assertFalse(browser.validImage("fixture", "image/svg+xml"))

    def test_invalid_calendar_dates_and_unrepresentable_upload_dates_fail_closed(self):
        for when in (
            "2026-99-15T12:00:00Z",
            "2026-02-30T12:00:00Z",
            "1900-02-29T12:00:00Z",
            "2026-01-01T24:00:00Z",
        ):
            self.responses = [(200, self.page(observedAt=when))]
            self.assertEqual(self.client.discover(self.dependencies, 1), (None, "response_invalid"))
        for field, value in (
            ("dateTaken", "2026-02-30 12:00:00"),
            ("dateUploaded", "99999999999999999999"),
            ("dateUploaded", "8640000000001"),
        ):
            photo = self.photo()
            photo[field] = value
            self.responses = [(200, self.page(photos=[photo]))]
            self.assertEqual(self.client.discover(self.dependencies, 1), (None, "response_invalid"))
        self.responses = [(200, self.page(observedAt="2000-02-29T12:00:00Z"))]
        self.assertEqual(
            self.client.discover(self.dependencies, 1).observedAt, "2000-02-29T12:00:00Z"
        )

    def test_safe_integer_cursor_and_proof_encoder_preserve_exact_revision(self):
        maximum = 9007199254740991
        self.responses = [
            (
                200,
                self.membership(
                    [{"flickrGroupId": "1", "displayName": "One"}],
                    observationRevision=maximum,
                    nextAfterGroupId="1",
                ),
            ),
            (200, self.membership(observationRevision=maximum)),
        ]
        self.client.memberships(self.dependencies, self.decode(json.dumps(self.binding())))
        self.assertIn("observation_revision=9007199254740991&", self.calls[1][1])
        body = self.lua.table_from(
            {
                "schemaVersion": 1,
                "flickrPhotoId": "photo-1",
                "expectedLinkedFlickrRevision": maximum,
            }
        )
        encoded = self.client.encodeProof(body, self.json.encode)
        self.assertEqual(json.loads(encoded)["expectedLinkedFlickrRevision"], maximum)

    def test_membership_order_uses_bytes_even_when_locale_string_order_differs(self):
        # The explicit byte comparator does not consult Lua's locale-aware <=.
        self.responses = [
            (
                200,
                self.membership(
                    [
                        {"flickrGroupId": "Z", "displayName": "Upper"},
                        {"flickrGroupId": "a", "displayName": "Lower"},
                    ]
                ),
            )
        ]
        result, _ = self.client.memberships(
            self.dependencies, self.decode(json.dumps(self.binding()))
        )
        self.assertEqual(len(result.groups), 2)
        source = (PLUGIN / "ExistingPhotoClient.lua").read_text()
        self.assertIn("left:byte(index)", source)
        self.assertNotIn("group.flickrGroupId <= previous", source)

    def test_cancellation_during_thumbnail_fetch_writes_no_bytes_or_modal(self):
        with tempfile.TemporaryDirectory() as directory:
            browser, context = self.prepare_browser(directory)
            self.responses = [(200, self.page())]
            self.lua.globals().deps = self.dependencies
            self.lua.execute("""
                cancelledDuringFetch = false
                deps.cancelled = function() return cancelledDuringFetch end
                deps.fetchThumbnail = function(url)
                    cancelledDuringFetch = true
                    return string.char(255,216,255,217), "image/jpeg", url
                end
            """)
            result, reason = browser.run(context, self.dependencies)
            self.assertIsNone(result)
            self.assertEqual(reason, "cancelled")
            self.lua.globals().cleanup()
            self.assertEqual(len(self.lua.globals().dialogs), 0)
            self.assertEqual(list(Path(directory).rglob("image-*")), [])

    def adapter(self, rotation):
        self.lua.globals().client = self.client
        self.lua.globals().rotation = rotation
        self.lua.execute("""
            local core = require "ConnectionCore"
            adapterCalls = 0
            current = string.rep("ABCD-", 12) .. "ABC0"
            candidate = ""
            local json = require "dkjson"
            local deps = {
                retrieve=function(key)
                    if key == core.CURRENT_KEY then return current end
                    return candidate
                end,
                expectedInstallationId="installation-1",
                encode=json.encode,
                decode=function(bytes) return json.decode(bytes, 1, json.null) end,
                httpGet=function(url)
                    adapterCalls=adapterCalls+1
                    if url == core.CURRENT_URL then
                        if rotation == "after_verify" then
                            current = string.rep("BCDE-", 12) .. "ABC0"
                        end
                        return [[{"schemaVersion":1,"installationId":"installation-1",
                          "installationRevision":1,"installationState":"active",
                          "presentedCredentialState":"current"}]], {status=200}
                    end
                    if rotation == "during_read" then candidate="saved-rotation" end
                    return "result", {status=200}
                end,
                httpPost=function(url, body)
                    adapterCalls=adapterCalls+1
                    sentBody=body
                    return "result", {status=201}
                end,
            }
            adapterRequest=client.authenticatedRequest(deps, core)
        """)
        return self.lua.globals().adapterRequest

    def test_yielding_thumbnail_cancellation_cannot_publish_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            browser, context = self.prepare_browser(directory)
            self.responses = [(200, self.page())]
            globals_ = self.lua.globals()
            globals_.browser = browser
            globals_.context = context
            globals_.deps = self.dependencies
            first, marker, second, result, reason = self.lua.execute("""
                -- Model SDK LrTasks.pcall by forwarding child coroutine yields.
                sdkTasks.pcall=function(callback, ...)
                    local child=coroutine.create(callback)
                    local values={coroutine.resume(child, ...)}
                    while coroutine.status(child) ~= "dead" do
                        coroutine.yield(unpack(values, 2))
                        values={coroutine.resume(child)}
                    end
                    return unpack(values)
                end
                cancelledDuringFetch=false
                deps.cancelled=function() return cancelledDuringFetch end
                deps.fetchThumbnail=function(url)
                    coroutine.yield("thumbnail_pending")
                    return string.char(255,216,255,217), "image/jpeg", url
                end
                local task=coroutine.create(function() return browser.run(context, deps) end)
                local first, marker=coroutine.resume(task)
                cancelledDuringFetch=true
                local second, result, reason=coroutine.resume(task)
                return first, marker, second, result, reason
            """)
            self.assertEqual(
                (first, marker, second, result, reason),
                (True, "thumbnail_pending", True, None, "cancelled"),
            )
            globals_.cleanup()
            self.assertEqual(len(globals_.dialogs), 0)
            self.assertEqual(list(Path(directory).rglob("image-*")), [])

    def test_adapter_cannot_verify_one_credential_then_send_another(self):
        request = self.adapter("after_verify")
        body, _ = request("GET", "/api/v001/existing-public-photos?page=1&page_size=5")
        self.assertIsNone(body)
        self.assertEqual(self.lua.globals().adapterCalls, 1)

    def test_adapter_discards_response_when_rotation_candidate_appears_during_http(self):
        request = self.adapter("during_read")
        body, _ = request("GET", "/api/v001/existing-public-photos?page=1&page_size=5")
        self.assertIsNone(body)
        self.assertEqual(self.lua.globals().adapterCalls, 2)

    def test_adapter_proof_body_preserves_safe_integer_revision(self):
        request = self.adapter("none")
        request(
            "POST",
            "/api/v001/existing-public-photo-bindings",
            self.lua.table_from(
                {
                    "schemaVersion": 1,
                    "flickrPhotoId": "photo-1",
                    "expectedLinkedFlickrRevision": 9007199254740991,
                }
            ),
        )
        self.assertEqual(
            json.loads(self.lua.globals().sentBody)["expectedLinkedFlickrRevision"],
            9007199254740991,
        )


if __name__ == "__main__":
    unittest.main()
