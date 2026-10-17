"""Offline lifecycle failure tests. No hosted adapters, processes or network."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.fixed_origin_lifecycle import (
    LIMITS,
    QUALIFICATION_BINDINGS,
    SECRET_NAMES,
    Lifecycle,
    Refused,
    main,
)

RUN = "a" * 32
DIGEST = "b" * 64


class Fake:
    offline = True

    def __init__(self):
        self.calls = []
        self.present = {}
        self.enabled = True
        self.counts = {"fga": 0, "receiver": 0}
        self.fail = ""
        self.clock_value = 1000

    def absent(self, kind, name):
        self.calls.append(("absent", kind, name))
        return name not in self.present

    def create(self, kind, name):
        self.calls.append(("create", kind, name))
        identity = "00000000-0000-4000-8000-000000000001" if kind == "d1" else name
        self.present[name] = identity
        if self.fail == "create:" + kind:
            raise TimeoutError("untrusted provider detail must never be retained")
        return identity

    def initialize_guard(self, run, starts_at, expires_at):
        self.calls.append(("initialize_guard", run))
        self.scope = {"run": run, "startsAt": starts_at, "expiresAt": expires_at}
        return self.fail != "initialize_guard"

    def guard(self, run):
        self.calls.append(("guard", run))
        return {
            **self.scope,
            "enabled": self.enabled,
            "initialized": True,
            "limits": LIMITS,
            **self.counts,
        }

    def install(self, bindings, qualification_scope):
        self.calls.append(("install", bindings))
        self.qualification_scope = qualification_scope
        if self.fail == "install_expiry":
            self.clock_value += LIMITS["lifetimeMs"]
        return self.fail != "install"

    def disable(self, run):
        self.calls.append(("disable", run))
        self.enabled = self.fail == "disable-inspect"
        return self.fail != "disable"

    def restore(self, capture_digest):
        self.calls.append(("restore", capture_digest))
        return {
            "captureDigest": "c" * 64 if self.fail == "restore" else capture_digest,
            "ordinaryRoutesVerified": True,
            "qualificationBindingsAbsent": True,
            "writeGatesDisabled": True,
            "productionStateUnchanged": True,
        }

    def delete(self, kind, name, identity):
        self.calls.append(("delete", kind, name, identity))
        if self.fail == "delete":
            raise TimeoutError("ambiguous deletion")
        if self.present.get(name) != identity:
            return False
        del self.present[name]
        return name not in self.present


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "journal.sqlite"
        self.fake = Fake()
        self.owner = self.open()

    def open(self, **changes):
        args = {
            "run": RUN,
            "starts_at": 1000,
            "capture_digest": DIGEST,
            "operations": self.fake,
            "clock": lambda: self.fake.clock_value,
            **changes,
        }
        owner = Lifecycle(self.path, **args)
        self.addCleanup(owner.close)
        return owner

    def test_exact_resources_secrets_and_restore_before_deletion(self):
        self.assertEqual(
            QUALIFICATION_BINDINGS,
            (
                "FIXED_ORIGIN_DB",
                "FIXED_ORIGIN_RUN",
                "FIXED_ORIGIN_CAPABILITY",
                "FIXED_ORIGIN_CANARY",
                "FIXED_ORIGIN_RECEIVER",
            ),
        )
        self.owner.provision()
        self.assertEqual(len(self.fake.present), 4)
        self.assertTrue(all(secret in self.fake.present for secret in SECRET_NAMES))
        self.assertIn(("install", QUALIFICATION_BINDINGS), self.fake.calls)
        self.assertEqual(self.fake.qualification_scope["expiresAt"], 601000)
        self.assertTrue(self.owner.cleanup())
        names = [call[0] for call in self.fake.calls]
        self.assertLess(names.index("disable"), names.index("restore"))
        self.assertLess(names.index("restore"), names.index("delete"))
        self.assertFalse(self.fake.present)
        calls = self.fake.calls[:]
        self.assertTrue(self.owner.cleanup())
        self.assertEqual(calls, self.fake.calls)

    def test_every_preexisting_resource_refuses_before_mutation(self):
        for row in self.owner.state()["resources"]:
            with self.subTest(kind=row["kind"], name=row["name"]):
                path = Path(self.temp.name) / (row["name"] + ".sqlite")
                fake = Fake()
                fake.present[row["name"]] = "unrelated"
                owner = Lifecycle(
                    path,
                    run=RUN,
                    starts_at=1000,
                    capture_digest=DIGEST,
                    operations=fake,
                    clock=lambda: 1000,
                )
                try:
                    with self.assertRaisesRegex(Refused, "preexists"):
                        owner.provision()
                    self.assertFalse(any(call[0] == "create" for call in fake.calls))
                finally:
                    owner.close()

    def test_ambiguous_create_survives_restart_without_retry(self):
        self.fake.fail = "create:receiver"
        with self.assertRaises(TimeoutError):
            self.owner.provision()
        restarted = self.open()
        calls = self.fake.calls[:]
        with self.assertRaisesRegex(Refused, "already_started"):
            restarted.provision()
        self.assertEqual(calls, self.fake.calls)
        self.assertNotIn("untrusted provider", str(restarted.state()))
        self.assertFalse(restarted.cleanup())
        self.assertEqual(restarted.state()["outcome"], "cleanup_unconfirmed")
        self.assertIn("fga-fixed-origin-recv-" + RUN, self.fake.present)

    def test_expiry_before_provision_or_publication_refuses(self):
        self.fake.clock_value = 1000 + LIMITS["lifetimeMs"]
        with self.assertRaisesRegex(Refused, "expired"):
            self.owner.provision()
        self.assertFalse(self.fake.calls)
        self.fake.clock_value = 1000
        self.fake.fail = "install_expiry"
        with self.assertRaisesRegex(Refused, "expired"):
            self.owner.provision()
        self.assertTrue(self.owner.cleanup())

    def test_exhausted_or_corrupt_guard_prevents_install(self):
        for counter in (96, True, -1):
            with self.subTest(counter=counter):
                fake = Fake()
                fake.counts["fga"] = counter
                path = Path(self.temp.name) / f"budget-{counter}.sqlite"
                owner = Lifecycle(
                    path,
                    run=RUN,
                    starts_at=1000,
                    capture_digest=DIGEST,
                    operations=fake,
                    clock=lambda: 1000,
                )
                try:
                    with self.assertRaisesRegex(Refused, "guard_not_ready"):
                        owner.provision()
                    self.assertFalse(any(call[0] == "install" for call in fake.calls))
                finally:
                    owner.close()

    def test_cleanup_barriers_and_ambiguous_delete_are_not_retried(self):
        for failure in ("disable", "disable-inspect", "restore", "delete"):
            with self.subTest(failure=failure):
                fake = Fake()
                path = Path(self.temp.name) / f"cleanup-{failure}.sqlite"
                owner = Lifecycle(
                    path,
                    run=RUN,
                    starts_at=1000,
                    capture_digest=DIGEST,
                    operations=fake,
                    clock=lambda: 1000,
                )
                try:
                    owner.provision()
                    fake.fail = failure
                    self.assertFalse(owner.cleanup())
                    deletes = [call for call in fake.calls if call[0] == "delete"]
                    self.assertEqual(len(deletes), 1 if failure == "delete" else 0)
                    calls = fake.calls[:]
                    self.assertFalse(owner.cleanup())
                    self.assertEqual(calls, fake.calls)
                finally:
                    owner.close()

    def test_scope_mismatch_and_live_adapter_refused(self):
        with self.assertRaisesRegex(Refused, "scope_mismatch"):
            self.open(run="c" * 32)
        self.fake.offline = False
        with self.assertRaisesRegex(Refused, "invalid_offline_scope"):
            self.open()

    def test_stale_or_concurrent_operator_cannot_mutate(self):
        self.owner.lock_path.touch()
        with self.assertRaisesRegex(Refused, "owner_or_recovery"):
            self.owner.provision()
        with self.assertRaisesRegex(Refused, "owner_or_recovery"):
            self.owner.cleanup()
        self.assertFalse(self.fake.calls)

    def test_shorter_qualification_window_does_not_widen_outer_lifetime(self):
        self.fake.clock_value = 601000
        with self.assertRaisesRegex(Refused, "qualification_window_expired"):
            self.owner.provision()
        self.assertFalse(any(call[0] == "install" for call in self.fake.calls))
        self.assertTrue(self.owner.cleanup())

    def test_attempt_cleans_up_after_install_failure(self):
        self.fake.fail = "install"
        with self.assertRaisesRegex(Refused, "install_unconfirmed"):
            self.owner.attempt()
        self.assertTrue(self.owner.state()["cleanupConfirmed"])

    def test_cli_is_disabled(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 2)
        self.assertIn("offline test model only", output.getvalue())


if __name__ == "__main__":
    unittest.main()
