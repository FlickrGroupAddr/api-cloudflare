"""Offline actual-Lua5.1 checks for the finite disposable native GET probe."""

from __future__ import annotations

import json
import ntpath
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaError, LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "probes/FGA-ExistingPhoto-Network.lrplugin"
RELEASE = ROOT / "clients/lightroom/FGA-LrC15.lrplugin"
UNIX = 1_800_000_000
MARKER = "fga-native-network-v1"


class ExistingPhotoNetworkNativeTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True, encoding=None)
        self.module = self.lua.execute((PROBE / "Network.lua").read_bytes())
        self.codec = self.lua.execute((RELEASE / "dkjson.lua").read_bytes())
        self.target = {
            "schemaVersion": 1,
            "planVersion": MARKER,
            "runId": "a" * 24,
            "workersDevSubdomain": "synthetic-account",
            "accessToken": "b" * 64,
            "canaryToken": "SYNTHETIC-" + "c" * 32,
            "expiresAtUnix": UNIX + 1200,
        }
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.clock = float(UNIX)
        self.redirect_followed = True
        self.canary_forwarded = True
        self.timeout = False
        self.unknown_error = False
        self.invalid_report = False
        self.stale = False
        self.exceed_plan = False
        self.final_receiver_count = None
        self.partial_data = b"NEVER-RETAIN-THIS"

    def value(self, document):
        return self.codec.decode(json.dumps(document).encode(), 1, self.codec.null)[0]

    def headers(self, status=200, media="image/png", **extra):
        result = self.lua.table_from(
            [
                self.lua.table_from({b"field": b"Content-Type", b"value": media.encode()}),
                self.lua.table_from({b"field": b"Cache-Control", b"value": b"no-store"}),
                self.lua.table_from({b"field": b"X-FGA-Network-Probe", b"value": MARKER.encode()}),
            ]
        )
        result[b"status"] = status
        for key, value in extra.items():
            result[key.encode()] = value
        return result

    def request(self, url, headers, timeout):
        url = url.decode()
        values = {row[b"field"].decode(): row[b"value"].decode() for row in headers.values()}
        self.calls.append((url, values))
        self.assertEqual(timeout, 15)
        self.assertTrue(url.startswith("https://fga-native-network-"))
        self.assertIn(".synthetic-account.workers.dev/", url)
        self.assertEqual(values["X-FGA-Network-Access"], self.target["accessToken"])
        self.clock += 0.125
        if url.endswith("/v1/report"):
            self.assertNotIn("Authorization", values)
            if self.invalid_report:
                return b"private unrelated error", self.headers(404, "text/html")
            count = (1 if self.redirect_followed else 0) if len(self.calls) > 1 else 0
            if self.final_receiver_count is not None and len(self.calls) > 1:
                count = self.final_receiver_count
            if self.stale:
                count = 1
            return json.dumps(
                {
                    "schemaVersion": 1,
                    "receiverRequests": count,
                    "authorizationObserved": bool(count and self.canary_forwarded),
                    "canaryObserved": bool(count and self.canary_forwarded),
                }
            ).encode(), self.headers(media="application/json")
        self.assertEqual(values["Authorization"], "Bearer " + self.target["canaryToken"])
        case = url.rsplit("/", 1)[-1]
        if case == "slow-response" and self.timeout:
            info = self.headers(0)
            info[b"error"] = self.lua.table_from(
                {
                    b"errorCode": b"raw-private-error" if self.unknown_error else b"timedOut",
                    b"name": b"NEVER-RETAIN-THIS",
                    b"nativeCode": b"PRIVATE",
                }
            )
            info[b"partial_data"] = self.partial_data
            return None, info
        if case == "jpeg":
            return b"j" * 634, self.headers(media="image/jpeg")
        if case == "boundary-image":
            return b"p" * 262144, self.headers()
        if case == "oversize-image":
            return b"p" * (262146 if self.exceed_plan else 262145), self.headers()
        if case == "oversize-error":
            return b"e" * 262145, self.headers(503, "text/plain")
        if case == "redirect-cross":
            if not self.redirect_followed:
                return b"", self.headers(302)
            return json.dumps(
                {
                    "schemaVersion": 1,
                    "receiverReached": True,
                    "authorizationPresent": self.canary_forwarded,
                    "canaryMatched": self.canary_forwarded,
                }
            ).encode(), self.headers(media="application/json")
        return b"p" * 68, self.headers()

    def execute(self):
        sdk = self.lua.table_from(
            {
                b"LrDate": self.lua.table_from(
                    {
                        b"currentTime": lambda: self.clock - 978_307_200,
                    }
                ),
                b"LrHttp": self.lua.table_from({b"get": self.request}),
            }
        )
        state = self.lua.table()
        self.module.execute(sdk, self.codec, self.value(self.target), state, None)
        return state

    def test_finite_matrix_exact_origins_headers_lengths_and_forwarding(self):
        state = self.execute()
        self.assertEqual(state[b"outcome"], b"characterized")
        self.assertEqual(state[b"getCalls"], 10)
        self.assertEqual(len(state[b"cases"]), 8)
        self.assertEqual(len(state[b"receiverReports"]), 2)
        self.assertTrue(state[b"canary"][b"redirectFollowObserved"])
        self.assertTrue(state[b"canary"][b"canaryObserved"])
        self.assertTrue(state[b"cases"][4][b"returnedOverImageLimit"])
        self.assertTrue(state[b"responseReferencesCleared"])
        self.assertEqual(state[b"responseFilesCreated"], 0)
        self.assertFalse(state[b"remoteCleanupConfirmed"])
        self.assertTrue(
            all("/v1/cases/" in url or url.endswith("/v1/report") for url, _ in self.calls)
        )

    def test_redirect_refusal_or_stripped_canary_are_measurements_not_safe_credentials(self):
        for followed, forwarded in ((False, False), (True, False)):
            self.calls = []
            self.redirect_followed, self.canary_forwarded = followed, forwarded
            state = self.execute()
            self.assertEqual(state[b"outcome"], b"characterized")
            self.assertEqual(state[b"canary"][b"redirectFollowObserved"], followed)
            self.assertFalse(state[b"canary"][b"canaryObserved"])

    def test_network_timeout_partial_data_and_unknown_errors_are_sanitized(self):
        self.timeout = True
        state = self.execute()
        self.assertEqual(state[b"outcome"], b"characterized")
        observation = state[b"cases"][6]
        self.assertEqual(observation[b"errorCategory"], b"timedOut")
        self.assertEqual(observation[b"partialBytes"], len(b"NEVER-RETAIN-THIS"))
        self.assertNotIn(b"NEVER-RETAIN", self.codec.encode(state))
        self.calls = []
        self.partial_data = b"x" * 262146
        state = self.execute()
        self.assertEqual(state[b"outcome"], b"incomplete")
        self.assertFalse(state[b"cases"][6][b"withinFinitePlan"])
        self.assertFalse(state[b"cases"][6][b"expectedResponse"])
        self.calls = []
        self.partial_data = b"NEVER-RETAIN-THIS"
        self.unknown_error = True
        state = self.execute()
        self.assertEqual(state[b"outcome"], b"incomplete")
        encoded = self.codec.encode(state)
        self.assertNotIn(b"raw-private", encoded)
        self.assertIn(b"other_network_error", encoded)

    def test_invalid_or_stale_report_stops_before_source_cases(self):
        self.invalid_report = True
        state = self.execute()
        self.assertEqual(state[b"reasonCode"], b"receiver_report_invalid")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(state[b"cases"]), 0)
        self.calls, self.invalid_report, self.stale = [], False, True
        state = self.execute()
        self.assertEqual(state[b"reasonCode"], b"target_not_fresh")
        self.assertEqual(len(self.calls), 1)

    def test_multiple_receiver_arrivals_are_inconclusive_and_retain_count(self):
        self.final_receiver_count = 2
        state = self.execute()
        self.assertEqual(state[b"outcome"], b"incomplete")
        self.assertEqual(state[b"reasonCode"], b"unexpected_observation")
        self.assertEqual(state[b"canary"][b"receiverRequests"], 2)
        self.assertFalse(state[b"canary"][b"observationConclusive"])
        self.assertIsNone(state[b"canary"][b"redirectFollowObserved"])

    def test_config_rejects_arbitrary_origins_tokens_expiry_and_unknown_fields(self):
        for patch in (
            {"source": "https://example.com"},
            {"receiver": "https://x.workers.dev"},
            {"runId": "../escape"},
            {"workersDevSubdomain": "x.workers.dev/escape"},
            {"workersDevSubdomain": "x:443"},
            {"workersDevSubdomain": "a..b"},
            {"accessToken": "real credential"},
            {"canaryToken": "real credential"},
            {"expiresAtUnix": UNIX - 1},
            {"expiresAtUnix": UNIX + 1201},
            {"planVersion": "other"},
            {"paths": ["/arbitrary"]},
        ):
            with self.subTest(patch=patch):
                value = self.module.validateConfig(self.value({**self.target, **patch}), UNIX)
                self.assertEqual(value, (None, b"target_invalid"))
        self.target["source"] = "https://example.com"
        state = self.execute()
        self.assertEqual(state[b"getCalls"], 0)
        self.assertEqual(self.calls, [])

    def test_no_response_or_configuration_secrets_in_receipt(self):
        state = self.execute()
        encoded = self.codec.encode(state)
        for forbidden in (
            self.target["accessToken"],
            self.target["canaryToken"],
            "workers.dev",
            "https://",
            "image/png",
            "receiverReached",
            "Authorization",
            "X-FGA-Network-Access",
        ):
            self.assertNotIn(forbidden.encode(), encoded)
        self.assertNotIn(b"pppppppp", encoded)

    def test_finite_plan_excess_is_observed_without_claiming_preallocation_limit(self):
        self.exceed_plan = True
        state = self.execute()
        self.assertEqual(state[b"cases"][4][b"bodyBytes"], 262146)
        self.assertFalse(state[b"cases"][4][b"withinFinitePlan"])
        self.assertEqual(state[b"outcome"], b"incomplete")

    def test_receipt_native_move_and_delete_failures_are_not_completion(self):
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        with tempfile.TemporaryDirectory() as directory:
            native_root = r"C:\Temp\FGA-existing-photo-network"

            def local(path):
                self.assertNotIn("/", path)
                self.assertEqual(ntpath.dirname(path), native_root)
                return Path(directory) / ntpath.basename(path)

            def write_bytes(path, body):
                local(path).write_text(body, encoding="utf-8")

            failures = {"delete": False, "move": False}

            def delete(path):
                if failures["delete"]:
                    return False
                local(path).unlink()
                return True

            def move(source, destination):
                src, dest = local(source), local(destination)
                if failures["move"] or dest.exists() or not dest.parent.exists():
                    return False
                src.rename(dest)
                return True

            lua.globals().writeBytes = write_bytes
            module = lua.execute(
                b"""
                setfenv(1, setmetatable({io={open=function(path)
                    return {write=function(self, body) writeBytes(path, body); return self end,
                        close=function() return true end}
                end}}, {__index=_G}))
            """
                + (PROBE / "Network.lua").read_bytes()
            )
            files = lua.table_from(
                {
                    "exists": lambda p: "file" if local(p).is_file() else False,
                    "delete": delete,
                    "move": move,
                }
            )
            codec = lua.execute((RELEASE / "dkjson.lua").read_bytes())
            locations = lua.table_from(
                {
                    "status": ntpath.join(native_root, "status.json"),
                    "temporary": ntpath.join(native_root, "status.json.tmp"),
                }
            )
            state = lua.table_from({"schemaVersion": 1, "outcome": "running"})
            module.publish(files, codec, locations, state)
            self.assertTrue(local(locations.status).is_file())
            self.assertFalse(local(locations.temporary).exists())
            module.publish(files, codec, locations, state)
            failures["delete"] = True
            with self.assertRaises(LuaError):
                module.publish(files, codec, locations, state)
            self.assertTrue(local(locations.status).is_file())
            self.assertTrue(local(locations.temporary).is_file())
            failures["delete"], failures["move"] = False, True
            with self.assertRaises(LuaError):
                module.publish(files, codec, locations, state)
            self.assertFalse(local(locations.status).exists())
            self.assertTrue(local(locations.temporary).is_file())

    def test_sdk_native_paths_and_registration_version(self):
        sdk = self.lua.table_from(
            {
                b"child": lambda a, b: ntpath.join(a.decode(), b.decode()).encode(),
                b"parent": lambda a: ntpath.dirname(a.decode()).encode(),
            }
        )
        locations = self.module.locations(
            sdk, b"C:\\Projects\\FGA\\api-cloudflare\\probes\\fixture"
        )
        self.assertEqual(locations[b"root"], b"C:\\Temp\\FGA-existing-photo-network")
        self.assertNotIn(b"/", locations[b"target"])
        info = self.lua.execute((PROBE / "Info.lua").read_bytes())
        self.assertEqual(info[b"VERSION"][b"build"], 1)
        self.assertEqual(self.module.VERSION, b"0.0.1.1")
        self.assertIn("0.0.1.1", (PROBE / "Run.lua").read_text(encoding="utf-8"))
        source = (PROBE / "Network.lua").read_text(encoding="utf-8")
        for forbidden in (
            "LrPasswords",
            "activeCatalog",
            "LrApplication.activeCatalog",
            "setfenv(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
