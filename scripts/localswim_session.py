"""Manage this project's localswim service at Codex session boundaries on Windows.

Follow the architecture project's detached-start and graceful-exit pattern, scoped
to the implementation board. Never read the board or its credential-bearing service
descriptor here; localswim-cli owns authenticated shutdown.
"""

from __future__ import annotations

import argparse
import json
import msvcrt
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "localswim_session.py"
BOARD = Path(r"C:\Projects\localswim-state-store\flickgroupaddr\api-cloudflare-localswim.json")
BIN = Path(r"C:\Users\TDO-XPS15-2024\.local\bin")
SERVER = BIN / "localswim.exe"
CLI = BIN / "localswim-cli.exe"
UV = BIN / "uv.exe"
POWERSHELL = Path(r"C:\Program Files\PowerShell\7\pwsh.exe")
URL = "http://127.0.0.1:8795/"
RUNTIME = Path(r"C:\Temp")
SERVICE_STDOUT = RUNTIME / "api-cloudflare-localswim.out.log"
SERVICE_STDERR = RUNTIME / "api-cloudflare-localswim.err.log"
STOP_STDOUT = RUNTIME / "api-cloudflare-localswim-session-end.out.log"
STOP_STDERR = RUNTIME / "api-cloudflare-localswim-session-end.err.log"
START_STATUS = RUNTIME / "api-cloudflare-localswim-session-hook-status.json"
STOP_STATUS = RUNTIME / "api-cloudflare-localswim-session-end-hook-status.json"
LOCK = RUNTIME / "api-cloudflare-localswim-session-lifecycle.lock"
LOCK_TIMEOUT = 170.0
START_TIMEOUT = 60.0
SHUTDOWN_TIMEOUT = 145
SYNCHRONIZED = {"repository synchronized", "committed and pushed"}

# Fixed PowerShell is used only at the required native hidden-process boundary.
# Arguments are Windows-quoted data in the environment, never interpolated code.
START_SERVER = """
$ErrorActionPreference = 'Stop'
Start-Process -FilePath $env:FGA_IMPL_LS_EXECUTABLE `
    -ArgumentList $env:FGA_IMPL_LS_ARGUMENTS `
    -WorkingDirectory $env:FGA_IMPL_LS_DIRECTORY `
    -RedirectStandardOutput $env:FGA_IMPL_LS_STDOUT `
    -RedirectStandardError $env:FGA_IMPL_LS_STDERR `
    -WindowStyle Hidden | Out-Null
"""


@dataclass(frozen=True)
class ServiceStatus:
    ok: bool
    push_state: str
    push_detail: str

    @property
    def ready(self) -> bool:
        return self.ok and self.push_state == "ok" and self.push_detail in SYNCHRONIZED


def service_status() -> ServiceStatus | None:
    """Only connection refusal means absent; other failures must not launch a duplicate."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        # Windows loopback refusal takes about two seconds on this laptop. Allow
        # it to arrive instead of misclassifying an unused port as a timeout.
        with opener.open(URL + "api/v001/status", timeout=3) as response:
            value = json.load(response)
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ConnectionRefusedError):
            return None
        raise RuntimeError("Cannot verify the implementation board's health") from exc
    except (OSError, ValueError) as exc:
        raise RuntimeError("Cannot read the implementation board's health") from exc
    if not isinstance(value, dict) or not isinstance(value.get("push"), dict):
        raise RuntimeError("Unexpected response from the implementation board's health endpoint")
    push = value["push"]
    return ServiceStatus(value.get("ok") is True, str(push.get("state")), str(push.get("detail")))


def write_status(path: Path, state: str, detail: str = "") -> None:
    """Atomically publish a sanitized lifecycle handoff, separate from board state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "schema": 1,
        "state": state,
        "pid": os.getpid(),
        "updatedAt": datetime.now(UTC).isoformat(),
        "detail": detail,
    }
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


def shutdown_pending() -> bool:
    try:
        value = json.loads(STOP_STATUS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    if not isinstance(value, dict):
        raise RuntimeError("Invalid implementation-board shutdown handoff")
    return value.get("state") in {"launching", "stopping"}


@contextmanager
def lifecycle_lock(*, starting: bool = False) -> Iterator[None]:
    """Serialize start/stop, including the gap before a detached stop acquires its lock."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_TIMEOUT
    with LOCK.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        while time.monotonic() < deadline:
            if starting and shutdown_pending():
                time.sleep(0.1)
                continue
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                time.sleep(0.1)
                continue
            try:
                if starting and shutdown_pending():
                    continue
                yield
                return
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    raise RuntimeError("Previous implementation-board lifecycle operation has not finished")


def child_environment() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "UV_CACHE_DIR": str(RUNTIME / "localswim-uv-cache"),
    }


def launch_service() -> None:
    BOARD.resolve(strict=True)
    SERVER.resolve(strict=True)
    POWERSHELL.resolve(strict=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    environment = child_environment()
    environment.update(
        FGA_IMPL_LS_EXECUTABLE=str(SERVER),
        FGA_IMPL_LS_ARGUMENTS=subprocess.list2cmdline(["--autopush", str(BOARD)]),
        FGA_IMPL_LS_DIRECTORY=str(PROJECT_ROOT),
        FGA_IMPL_LS_STDOUT=str(SERVICE_STDOUT),
        FGA_IMPL_LS_STDERR=str(SERVICE_STDERR),
    )
    result = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", START_SERVER],
        stdin=subprocess.DEVNULL,
        # A detached Windows child can inherit PIPE handles even with its own
        # log redirection. DEVNULL keeps communicate() from waiting for that child.
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
        timeout=10,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Hidden implementation-board launch failed; inspect the service logs")


def stop_service() -> None:
    """The CLI waits for final autopush and descriptor cleanup; never kill the service."""
    CLI.resolve(strict=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with STOP_STDOUT.open("ab") as stdout, STOP_STDERR.open("ab") as stderr:
        result = subprocess.run(
            [str(CLI), str(BOARD), "board", "shutdown"],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            env=child_environment(),
            timeout=SHUTDOWN_TIMEOUT,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(
            "Graceful implementation-board shutdown failed; inspect the shutdown logs"
        )


def ensure_service() -> None:
    status = service_status()
    if status is not None:
        if not status.ok or status.push_state in {"failed", "error"}:
            raise RuntimeError(
                "Implementation board reports a health/push failure; inspect its logs"
            )
        if status.push_state == "off":
            stop_service()
            if service_status() is not None:
                raise RuntimeError(
                    "Implementation board is still listening after graceful shutdown"
                )
            status = None
    if status is None:
        launch_service()
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        status = service_status()
        if status is not None:
            if not status.ok or status.push_state in {"failed", "error", "off"}:
                raise RuntimeError(
                    "Implementation board reports a health/push failure; inspect its logs"
                )
            if status.ready:
                return
        time.sleep(0.25)
    raise RuntimeError("Implementation board did not synchronize in time; inspect its service logs")


def start(*, open_browser: bool) -> None:
    with lifecycle_lock(starting=True):
        write_status(START_STATUS, "starting")
        ensure_service()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(URL, timeout=3) as response:
            if response.status != 200:
                raise RuntimeError("Implementation board page did not return HTTP 200")
        if open_browser:
            subprocess.run(
                [
                    str(POWERSHELL),
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Start-Process 'http://127.0.0.1:8795/'",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=True,
            )
        write_status(START_STATUS, "ready")
    print(f"FGA implementation board is healthy and synchronized: {URL}", flush=True)


def trigger_stop() -> None:
    """Return inside SessionEnd's three-second budget; the child owns all cleanup."""
    UV.resolve(strict=True)
    SCRIPT.resolve(strict=True)
    write_status(STOP_STATUS, "launching")
    with STOP_STDOUT.open("ab") as stdout, STOP_STDERR.open("ab") as stderr:
        subprocess.Popen(
            [
                str(UV),
                "run",
                "--project",
                str(PROJECT_ROOT),
                "--frozen",
                "--no-dev",
                "python",
                str(SCRIPT),
                "stop",
            ],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            env=child_environment(),
            creationflags=(
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            ),
            close_fds=True,
        )
    print("Started detached graceful implementation-board shutdown.", flush=True)


def stop() -> None:
    with lifecycle_lock():
        write_status(STOP_STATUS, "stopping")
        stop_service()
        write_status(STOP_STATUS, "stopped")
    print("FGA implementation board stopped gracefully.", flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "trigger-stop", "stop"))
    parser.add_argument(
        "--no-browser", action="store_true", help="Check startup without opening a tab"
    )
    args = parser.parse_args(argv)
    status_path = START_STATUS if args.action == "start" else STOP_STATUS
    try:
        if args.action == "start":
            payload = {} if sys.stdin.isatty() else json.loads(sys.stdin.read() or "{}")
            if not isinstance(payload, dict):
                raise RuntimeError("Expected a Codex session hook object")
            open_browser = not args.no_browser and payload.get("source", "startup") in {
                "startup",
                "resume",
            }
            start(open_browser=open_browser)
        elif args.action == "trigger-stop":
            trigger_stop()
        else:
            stop()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        # Raw HTTP/CLI output may contain private board data. Keep the handoff sanitized.
        detail = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        with suppress(OSError):
            write_status(status_path, "error", detail)
        print(f"Implementation-board lifecycle failed: {detail}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
