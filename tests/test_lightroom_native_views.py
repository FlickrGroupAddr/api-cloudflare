"""Run native-view fixture harnesses in the client's actual Lua 5.1 language."""

import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class NativeViewTests(unittest.TestCase):
    def run_view(self, harness: str, bundle: str) -> None:
        lua = cast(Any, LuaRuntime)(
            unpack_returned_tuples=True, register_eval=False, register_builtins=False
        )
        self.assertEqual(lua.lua_version, (5, 1))
        lua.globals().arg = lua.table_from([str(ROOT / bundle)])
        lua.execute((ROOT / harness).read_text(encoding="utf-8"))

    def test_group_browser_yield_cancellation_and_safe_sdk_adapter(self) -> None:
        self.run_view(
            "tests/lightroom_group_browser.test.lua", "clients/lightroom/FGA-LrC15.lrplugin"
        )

    def test_selection_preview_documented_controls_and_limits(self) -> None:
        self.run_view(
            "tests/selection_preview_sdk_review.lua",
            "clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin",
        )
