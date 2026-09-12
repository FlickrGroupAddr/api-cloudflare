"""Run the official batch adapter in actual Lua 5.1, with a recording HTTP boundary."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime, lua_type

SOURCE = Path(__file__).resolve().parents[1] / "clients/lightroom/GroupSubmissionClient.lua"
CREDENTIAL = "0000-" * 12 + "0000"


class BatchClientTests(unittest.TestCase):
    def setUp(self):
        self.lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        self.assertEqual(self.lua.lua_version, (5, 1))
        self.client = self.lua.execute(SOURCE.read_text(encoding="utf-8"))
        self.calls = []
        self.encodes = 0

    def plain(self, value):
        if lua_type(value) != "table":
            return value
        keys = list(value.keys())
        if keys and set(keys) == set(range(1, len(keys) + 1)):
            return [self.plain(value[i]) for i in range(1, len(keys) + 1)]
        return {key: self.plain(value[key]) for key in keys}

    def encode(self, value):
        self.encodes += 1
        return json.dumps(self.plain(value))

    def post(self, path, body, headers):
        self.calls.append((path, json.loads(body), self.plain(headers)))
        return "response", 202

    def submit(self, groups, credential=CREDENTIAL):
        return self.client.submit(
            "binding-1", 3, self.lua.table_from(groups), credential, self.post, self.encode
        )

    def test_CBA_ROUTE_001_one_group_one_request(self):
        self.assertEqual(self.submit(["group-1"]), ("response", 202))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], "/api/v001/group-submission-batches")
        self.assertEqual(self.encodes, 1)

    def test_CBA_ROUTE_002_complete_ordered_selection(self):
        groups = ["group-z", "group-a", "group-b"]
        self.submit(groups)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(
            self.calls[0][1],
            {
                "schemaVersion": 2,
                "photoBinding": {
                    "fgaPhotoBindingId": "binding-1",
                    "expectedVerificationRevision": 3,
                },
                "flickrGroupIds": groups,
            },
        )

    def test_CBA_CLIENT_001_over_limit_sends_nothing(self):
        self.assertEqual(
            self.submit([f"group-{i}" for i in range(61)]), (None, "invalid_selection")
        )
        self.assertEqual(self.calls, [])
        self.assertEqual(self.encodes, 0)

    def test_exact_bound_is_one_call(self):
        self.submit([f"group-{i}" for i in range(60)])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.calls[0][1]["flickrGroupIds"]), 60)

    def test_invalid_and_sparse_input_is_whole_selection_failure(self):
        for groups in (
            [],
            ["same", "same"],
            ["ok", "invalid group"],
            {1: "one", 3: "three"},
            {1: "one", "force": True},
        ):
            with self.subTest(groups=groups):
                self.assertEqual(self.submit(groups), (None, "invalid_selection"))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.encodes, 0)

    def test_noncanonical_credential_cannot_reach_header(self):
        for credential in (
            CREDENTIAL.lower().replace("0", "o"),
            "x" * 64,
            CREDENTIAL[:-1] + "1",
            "\r\n" + CREDENTIAL[2:],
        ):
            self.assertEqual(self.submit(["group"], credential), (None, "invalid_credential"))
        self.assertEqual(self.calls, [])
