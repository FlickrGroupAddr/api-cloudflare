"""Exercise lifecycle failures without reading or changing a real board."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import localswim_session as session


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ready = session.ServiceStatus(True, "ok", "repository synchronized")

    def test_reuses_healthy_service(self) -> None:
        with (
            patch.object(session, "service_status", return_value=self.ready),
            patch.object(session, "launch_service") as launch,
            patch.object(session, "stop_service") as stop,
        ):
            session.ensure_service()
        launch.assert_not_called()
        stop.assert_not_called()

    def test_launches_once_and_waits_for_initial_push(self) -> None:
        pending = session.ServiceStatus(True, "pending", "initial push")
        with (
            patch.object(session, "service_status", side_effect=[None, None, pending, self.ready]),
            patch.object(session, "launch_service") as launch,
            patch.object(session.time, "sleep"),
        ):
            session.ensure_service()
        launch.assert_called_once_with()

    def test_disabled_autopush_is_gracefully_restarted(self) -> None:
        events: list[str] = []
        with (
            patch.object(
                session,
                "service_status",
                side_effect=[session.ServiceStatus(True, "off", "disabled"), None, self.ready],
            ),
            patch.object(session, "stop_service", side_effect=lambda: events.append("stop")),
            patch.object(session, "launch_service", side_effect=lambda: events.append("start")),
        ):
            session.ensure_service()
        self.assertEqual(events, ["stop", "start"])

    def test_failed_shutdown_never_launches_replacement(self) -> None:
        with (
            patch.object(
                session,
                "service_status",
                return_value=session.ServiceStatus(True, "off", "disabled"),
            ),
            patch.object(session, "stop_service", side_effect=RuntimeError("shutdown failed")),
            patch.object(session, "launch_service") as launch,
        ):
            with self.assertRaisesRegex(RuntimeError, "shutdown failed"):
                session.ensure_service()
        launch.assert_not_called()

    def test_unhealthy_or_failed_push_is_not_restarted(self) -> None:
        for status in (
            session.ServiceStatus(False, "ok", "repository synchronized"),
            session.ServiceStatus(True, "failed", "push failed"),
            session.ServiceStatus(True, "error", "push failed"),
        ):
            with (
                self.subTest(status=status),
                patch.object(session, "service_status", return_value=status),
                patch.object(session, "launch_service") as launch,
                patch.object(session, "stop_service") as stop,
            ):
                with self.assertRaisesRegex(RuntimeError, "health/push failure"):
                    session.ensure_service()
                launch.assert_not_called()
                stop.assert_not_called()

    def test_pending_service_is_not_duplicated_on_timeout(self) -> None:
        with (
            patch.object(
                session,
                "service_status",
                return_value=session.ServiceStatus(True, "pending", "initial push"),
            ),
            patch.object(session, "START_TIMEOUT", 0),
            patch.object(session, "launch_service") as launch,
        ):
            with self.assertRaisesRegex(RuntimeError, "did not synchronize"):
                session.ensure_service()
        launch.assert_not_called()

    def test_refused_connection_is_absent_but_timeout_is_an_error(self) -> None:
        with patch.object(session.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = urllib.error.URLError(ConnectionRefusedError())
            self.assertIsNone(session.service_status())
            self.assertEqual(build.return_value.open.call_args.kwargs["timeout"], 3)
            build.return_value.open.side_effect = urllib.error.URLError(TimeoutError())
            with self.assertRaisesRegex(RuntimeError, "Cannot verify"):
                session.service_status()

    def test_malformed_http_response_is_not_absent(self) -> None:
        with patch.object(session.urllib.request, "build_opener") as build:
            build.return_value.open.return_value.__enter__.return_value = io.BytesIO(b"not json")
            with self.assertRaisesRegex(RuntimeError, "Cannot read"):
                session.service_status()


class LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in (
            "START_STATUS",
            "STOP_STATUS",
            "LOCK",
            "SERVICE_STDOUT",
            "SERVICE_STDERR",
            "STOP_STDOUT",
            "STOP_STDERR",
        ):
            replacement = patch.object(session, name, root / name.lower())
            replacement.start()
            self.addCleanup(replacement.stop)
        replacement = patch.object(session, "RUNTIME", root)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_shutdown_pending_blocks_start_before_lock_acquisition(self) -> None:
        session.write_status(session.STOP_STATUS, "launching")
        with patch.object(session, "LOCK_TIMEOUT", 0.02):
            with self.assertRaisesRegex(RuntimeError, "has not finished"):
                with session.lifecycle_lock(starting=True):
                    self.fail("startup passed a pending shutdown")
        session.write_status(session.STOP_STATUS, "stopped")
        with session.lifecycle_lock(starting=True):
            pass

    def test_lock_excludes_other_operations_and_releases_on_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "test error"):
            with session.lifecycle_lock():
                with patch.object(session, "LOCK_TIMEOUT", 0.02):
                    with self.assertRaisesRegex(RuntimeError, "has not finished"):
                        with session.lifecycle_lock():
                            self.fail("second operation acquired the lock")
                raise RuntimeError("test error")
        with session.lifecycle_lock():
            pass

    def test_exit_trigger_detaches_without_waiting(self) -> None:
        with (
            patch.object(Path, "resolve", return_value=Path("verified")),
            patch.object(session.subprocess, "Popen") as popen,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            session.trigger_stop()
        arguments = popen.call_args.args[0]
        self.assertEqual(arguments[-1], "stop")
        self.assertIn("--frozen", arguments)
        self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)
        flags = popen.call_args.kwargs["creationflags"]
        self.assertTrue(flags & subprocess.DETACHED_PROCESS)
        self.assertTrue(flags & subprocess.CREATE_NEW_PROCESS_GROUP)
        self.assertTrue(flags & subprocess.CREATE_NO_WINDOW)
        popen.return_value.wait.assert_not_called()
        self.assertTrue(session.shutdown_pending())

    def test_trigger_failure_clears_pending_state(self) -> None:
        with (
            patch.object(Path, "resolve", return_value=Path("verified")),
            patch.object(session.subprocess, "Popen", side_effect=OSError("private detail")),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            self.assertEqual(session.main(["trigger-stop"]), 1)
        self.assertFalse(session.shutdown_pending())
        self.assertEqual(json.loads(session.STOP_STATUS.read_text())["state"], "error")
        self.assertNotIn("private detail", stderr.getvalue())

    def test_failed_final_push_reports_error_without_claiming_stop(self) -> None:
        with (
            patch.object(session, "stop_service", side_effect=RuntimeError("final push failed")),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            self.assertEqual(session.main(["stop"]), 1)
        self.assertEqual(json.loads(session.STOP_STATUS.read_text())["state"], "error")

    def test_successful_stop_uses_only_exact_board_cli_shutdown(self) -> None:
        with (
            patch.object(Path, "resolve", return_value=Path("verified")),
            patch.object(session.subprocess, "run", return_value=MagicMock(returncode=0)) as run,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            self.assertEqual(session.main(["stop"]), 0)
        self.assertEqual(
            run.call_args.args[0], [str(session.CLI), str(session.BOARD), "board", "shutdown"]
        )
        self.assertEqual(json.loads(session.STOP_STATUS.read_text())["state"], "stopped")

    def test_hidden_server_launch_enables_autopush_and_utf8(self) -> None:
        with (
            patch.object(Path, "resolve", return_value=Path("verified")),
            patch.object(session.subprocess, "run", return_value=MagicMock(returncode=0)) as run,
        ):
            session.launch_service()
        environment = run.call_args.kwargs["env"]
        self.assertIn("--autopush", environment["FGA_IMPL_LS_ARGUMENTS"])
        self.assertIn(str(session.BOARD), environment["FGA_IMPL_LS_ARGUMENTS"])
        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(environment["PYTHONUNBUFFERED"], "1")
        self.assertIn("-WindowStyle Hidden", run.call_args.args[0][-1])
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_start_checks_page_before_opening_browser(self) -> None:
        with (
            patch.object(session, "ensure_service"),
            patch.object(session.urllib.request, "build_opener") as build,
            patch.object(session.subprocess, "run") as browser,
            patch("sys.stderr", new_callable=io.StringIO),
            patch("sys.stdin", io.StringIO('{"source":"startup"}')),
        ):
            build.return_value.open.return_value.__enter__.return_value.status = 503
            self.assertEqual(session.main(["start"]), 1)
        browser.assert_not_called()
        self.assertEqual(json.loads(session.START_STATUS.read_text())["state"], "error")

    def test_browser_opens_for_startup_and_resume_only(self) -> None:
        for source, expected in (("startup", True), ("resume", True), ("clear", False)):
            with (
                self.subTest(source=source),
                patch("sys.stdin", io.StringIO(json.dumps({"source": source}))),
                patch.object(session, "start") as start,
            ):
                self.assertEqual(session.main(["start"]), 0)
                start.assert_called_once_with(open_browser=expected)


if __name__ == "__main__":
    unittest.main()
