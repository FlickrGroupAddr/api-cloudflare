"""Fake-boundary checks; never start NativeFiles, UI, DNS or provider calls."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import post_screenshot_successor as subject


class API:
    account = "a" * 32

    def __init__(self):
        self.calls = []

    def call(self, *args, **kwargs):
        self.calls.append(args)
        return {}


class CallerTests(unittest.TestCase):
    def test_final_dispatch_rechecks_after_slow_or_withdrawn_durable_save(self):
        for mode in ("cutoff", "withdrawn", "path_changed", "slow_final_stop_read"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                now = [1000]
                withdrawn = [False]
                inputs = []
                stop_checks = [0]

                class Permit:
                    def authorize(self, withdrawn=withdrawn):
                        if withdrawn[0]:
                            raise ValueError("withdrawn")

                    def begin_cleanup(self):
                        pass

                class PermittedAPI(API):
                    _permit = Permit()

                api = PermittedAPI()

                class Life:
                    preparation_deadline = 1240

                    def __init__(self, *args, **kwargs):
                        self.journal = {"expiresAtUnix": 2200}

                    def save(self, mode=mode, now=now, withdrawn=withdrawn, root=root):
                        if self.journal.get("nativeInvocations") == 1:
                            if mode == "cutoff":
                                now[0] = 1250
                            elif mode == "withdrawn":
                                withdrawn[0] = True
                            elif mode == "path_changed":
                                (root / "native/status.json").write_text("{}", encoding="utf-8")

                    def prepare(self, *args):
                        return {"synthetic": True}

                    def observe(self):
                        pass

                    def cleanup(self):
                        return {"cleanupConfirmed": True, "observationsConfirmed": False}

                def stopped(mode=mode, stop_checks=stop_checks, now=now):
                    stop_checks[0] += 1
                    if mode == "slow_final_stop_read" and stop_checks[0] == 4:
                        now[0] = 1250
                    return False

                result = subject.run_once(
                    api,
                    run_id="b" * 24,
                    owner="1",
                    subdomain="test",
                    access="a" * 64,
                    canary="SYNTHETIC-" + "a" * 32,
                    invoke_native=lambda *args, inputs=inputs: inputs.append("input"),
                    stop_requested=stopped,
                    output_root=root / "output",
                    native_root=root / "native",
                    lifecycle_factory=Life,
                    clock=lambda now=now: now[0],
                    sleep=lambda seconds: None,
                )
                self.assertEqual(inputs, [])
                self.assertEqual(result["nativeInvocations"], 0)
                self.assertTrue(result["stopPreserved"])

    def test_delayed_first_effect_and_account_drift_refused(self):
        api = API()
        now = [1000]
        admission = subject.DeadlineAdmission(api, api.account, 2250, lambda: now[0])
        now[0] = 1051
        with self.assertRaises(ValueError):
            admission.call("POST", "/anything")
        self.assertEqual(api.calls, [])
        now[0] = 1000
        api.account = "b" * 32
        with self.assertRaises(ValueError):
            admission.call("POST", "/anything")
        self.assertEqual(api.calls, [])

    def test_failed_prewarm_spends_claim_without_cloud(self):
        api = API()
        closed = []

        class Native:
            deadline = 1960

            def __init__(self, **kwargs):
                pass

            def claim(self):
                pass

            def wait_ready(self):
                raise ValueError("owner_not_ready")

            def close(self):
                closed.append(True)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bound = subject.packet.binding("b" * 24, runs=root)
            Path(bound["runRoot"]).mkdir()
            config = {
                **bound,
                "accountId": api.account,
                "subdomain": "test",
                "actionDeadlineUnix": 2300,
            }
            with self.assertRaises(ValueError):
                subject.execute(
                    api, config, native_factory=Native, lifecycle_factory=object, clock=lambda: 1000
                )
            self.assertEqual(closed, [True])
            self.assertEqual(api.calls, [])
            with self.assertRaises(FileExistsError):
                subject.execute(
                    api, config, native_factory=Native, lifecycle_factory=object, clock=lambda: 1000
                )

    def test_fixture_failure_and_inventory_are_not_positive_qualification(self):
        value = {
            "schemaVersion": 1,
            "planVersion": subject.VERSION,
            "runId": "b" * 24,
            "productionQualified": False,
            "remoteCleanupConfirmed": False,
            "outcome": "failed",
            "reasonCode": "fixture_failure",
            "postCalls": 0,
            "getCalls": 0,
            "cases": [],
        }
        result = subject.classify(value, "b" * 24)
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(len(result["postCases"]), 23)
        self.assertFalse(result["methodSpecificPostQualified"])
        self.assertTrue(all(v["classification"] == "unmeasured" for v in result["postCases"]))
        value.update(
            outcome="characterized",
            reasonCode="measurements_require_external_receipt_review",
            postCalls=23,
            getCalls=1,
            cases=[{"caseId": c} for c in subject.CASES],
        )
        self.assertFalse(subject.classify(value, "b" * 24)["methodSpecificPostQualified"])
        value["cases"].reverse()
        with self.assertRaises(ValueError):
            subject.classify(value, "b" * 24)

    def test_apply_refuses_before_token_read_on_invalid_current_evidence(self):
        with patch.object(subject.packet, "validate_packet", return_value={}) as validated:

            def refused(*args, **kwargs):
                raise ValueError("current_evidence_invalid")

            with self.assertRaisesRegex(ValueError, "current_evidence_invalid"):
                subject.apply(Path("fake"), "a" * 64, admission_factory=refused)
            validated.assert_called_once()

    def test_apply_orders_rechecks_and_token_read_and_closes(self):
        events = []

        class Admission:
            management_address = "192.0.2.1"

            def authorize(self):
                events.append("authorize")

            def read_token_once(self):
                events.append("read_token_once")
                return "synthetic-test-token"

            def close(self):
                events.append("close")

        def provider(*args, **kwargs):
            self.assertIs(kwargs["exclusive_owner"], True)
            events.append("provider")
            return API()

        def execute(*args):
            events.append("execute")
            return {"outcome": "synthetic"}

        config = {"accountId": "a" * 32, "runId": "b" * 24}
        with patch.object(subject.packet, "validate_packet", return_value=config):
            result = subject.apply(
                Path("fake"),
                "a" * 64,
                admission_factory=lambda *a, **kw: Admission(),
                provider_factory=provider,
                execute_fn=execute,
            )
        self.assertEqual(result, {"outcome": "synthetic"})
        self.assertEqual(
            events, ["authorize", "read_token_once", "authorize", "provider", "execute", "close"]
        )

    def test_unknown_delivery_preserves_stop_and_runs_owned_cleanup_once(self):
        events = []

        class Life:
            def __init__(self, api, directory, run, owner, clock):
                self.journal = {"expiresAtUnix": 2200}

            def save(self):
                pass

            def prepare(self, *args):
                events.append("prepare")
                return {"synthetic": True}

            def observe(self):
                events.append("observe")

            def cleanup(self):
                events.append("cleanup")
                return {"cleanupConfirmed": True, "observationsConfirmed": False}

        def unknown(*args):
            events.append("input")
            raise ValueError("delivery_unknown")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subject.run_once(
                API(),
                run_id="b" * 24,
                owner="123",
                subdomain="test",
                access="a" * 64,
                canary="SYNTHETIC-" + "a" * 32,
                invoke_native=unknown,
                stop_requested=lambda: False,
                output_root=root / "output",
                native_root=root / "native",
                lifecycle_factory=Life,
                clock=lambda: 1000,
                sleep=lambda seconds: None,
            )
            self.assertEqual(events, ["prepare", "input", "observe", "cleanup"])
            self.assertEqual(result["outcome"], "failed")
            self.assertTrue(result["stopPreserved"])
            self.assertTrue((root / "native/stop.json").exists())
            self.assertEqual(result["nativeInvocations"], 1)


if __name__ == "__main__":
    unittest.main()
