from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from scripts.secret_lifecycle_model import Conflict, Lifecycle


class LifecycleTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "model.sqlite"
        self.model = Lifecycle(self.path)
        for name in ("a", "b", "c"):
            self.model.plan(name, "version-" + name)

    def stage(self, name):
        self.model.stage(name, "version-" + name, "synthetic-arn-" + name)

    def test_no_activation_before_staging_and_no_cleanup_of_uncertain_create(self):
        with self.assertRaises(Conflict):
            self.model.activate("a", 0)
        self.assertEqual(self.model.current(), (0, None))
        self.assertFalse(self.model.cleanup_allowed("a"))

    def test_lost_activation_response_resolves_after_reopen(self):
        self.stage("a")
        self.model.activate("a", 0)
        restarted = Lifecycle(self.path)
        self.assertEqual(restarted.current(), (1, "a"))
        self.assertFalse(restarted.cleanup_allowed("a"))
        with self.assertRaises(Conflict):
            restarted.activate("a", 0)

    def test_concurrent_replacements_have_one_winner(self):
        for name in ("a", "b", "c"):
            self.stage(name)
        self.model.activate("a", 0)

        def replace(name):
            try:
                Lifecycle(self.path).activate(name, 1)
                return True
            except Conflict:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(replace, ("b", "c"))), 1)
        self.assertEqual(self.model.current()[0], 2)
        self.assertIn(self.model.current()[1], ("b", "c"))
        self.assertTrue(self.model.cleanup_allowed("a"))

    def test_stale_failure_cannot_disconnect_new_revision(self):
        self.stage("a")
        self.stage("b")
        self.model.activate("a", 0)
        self.model.activate("b", 1)
        with self.assertRaises(Conflict):
            self.model.disconnect(1)
        self.assertEqual(self.model.current(), (2, "b"))

    def test_disconnect_removes_authority_before_cleanup_and_survives_reopen(self):
        self.stage("a")
        self.model.activate("a", 0)
        self.model.disconnect(1)
        restarted = Lifecycle(self.path)
        self.assertEqual(restarted.current(), (2, None))
        for name in ("a", "b", "c"):
            self.assertTrue(restarted.cleanup_allowed(name))
        with self.assertRaises(Conflict):
            restarted.activate("a", 2)

    def test_wrong_generation_response_cannot_stage(self):
        with self.assertRaises(Conflict):
            self.model.stage("a", "different-version", "unexpected-arn")
        with self.assertRaises(Conflict):
            self.model.activate("a", 0)
