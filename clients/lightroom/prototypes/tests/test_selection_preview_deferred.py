"""Run delayed dual-list notification cases in the shared Lua 5.1 SDK mock."""

import runpy
import unittest
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    namespace = runpy.run_path(str(root / "tests/test_selection_preview_adversarial.py"))
    test = namespace["SelectionPreviewAdversarialTests"]
    suite = unittest.TestSuite([test("test_deferred_replays_stale_query_and_native_highlights")])
    result = unittest.TextTestRunner().run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
