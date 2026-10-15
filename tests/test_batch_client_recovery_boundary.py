"""Characterize the existing Lua adapter boundary; these are not UI qualification.

Set FGA_SOURCE_ROOT to run this staged file against the implementation checkout.
Only synthetic values and injected functions are used; no network is contacted.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime


class BatchRecoveryBoundaryTests(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ.get("FGA_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
        self.lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        self.client = self.lua.execute(
            (root / "clients/lightroom/GroupSubmissionClient.lua").read_text("utf-8")
        )
        self.groups = self.lua.table_from(["group-1", "group-2"])
        self.credential = "0000-" * 12 + "0000"

    def submit(self, post, encode=lambda _: "synthetic-json"):
        return self.client.submit("binding-1", 3, self.groups, self.credential, post, encode)

    def test_transport_failure_is_returned_after_one_call_without_replay(self):
        calls = []

        def lost_response(*args):
            calls.append(args)
            return None, "timedOut"

        self.assertEqual(self.submit(lost_response), (None, "timedOut"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.groups), 2)

    def test_post_exception_is_propagated_without_replay(self):
        calls = []

        def interrupted(*args):
            calls.append(args)
            raise RuntimeError("synthetic-post-interruption")

        with self.assertRaisesRegex(RuntimeError, "synthetic-post-interruption"):
            self.submit(interrupted)
        self.assertEqual(len(calls), 1)

    def test_encoder_exception_never_dispatches(self):
        calls = []

        def broken_encoder(_):
            raise RuntimeError("synthetic-encoding-failure")

        with self.assertRaisesRegex(RuntimeError, "synthetic-encoding-failure"):
            self.submit(lambda *args: calls.append(args), broken_encoder)
        self.assertEqual(calls, [])

    def test_raw_202_body_is_not_validated_by_this_adapter(self):
        # This passing characterization exposes an integration obligation:
        # a controller must not clear its durable selection on HTTP status alone.
        self.assertEqual(
            self.submit(lambda *_: ("malformed-or-incomplete-response", 202)),
            ("malformed-or-incomplete-response", 202),
        )


if __name__ == "__main__":
    unittest.main()
