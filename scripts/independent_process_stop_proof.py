"""Kill an owned Node/workerd process tree after handoff; recover from the same disk.

This validates a real independent local process stop, not a Cloudflare host kill.
"""

from __future__ import annotations

import json
import os
import queue
import secrets
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from scripts import coordination_probe as probe
from scripts import runtime_permissions_probe as runtime


class Child:
    def __init__(self, run: runtime.Run, token: str, config: dict[str, Any], *, resume: bool):
        self.log = (run.directory / ("restart.log" if resume else "initial.log")).open(
            "w", encoding="utf-8"
        )
        path = run.directory / "process.json"
        path.write_text(json.dumps({**config, "resume": resume}), encoding="utf-8")
        self.process = subprocess.Popen(
            [runtime.NODE, str(probe.PROBE / "process-stop.mjs"), str(path)],
            cwd=probe.ROOT,
            env={**os.environ, "FGA_COORDINATION_TOKEN": token},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            start_new_session=sys.platform != "win32",
        )
        lines: queue.Queue[str] = queue.Queue()
        output = self.process.stdout
        assert output is not None
        threading.Thread(target=lambda: lines.put(output.readline()), daemon=True).start()
        try:
            status = json.loads(lines.get(timeout=30))
            if status["pid"] != self.process.pid:
                raise RuntimeError("child_identity_mismatch")
            run.state["url"] = status["url"].rstrip("/")
            run.save()
        except Exception:
            self.kill()
            raise

    def kill(self) -> None:
        if self.process.poll() is None:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    check=True,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                import signal

                os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=15)
        self.log.close()

    def close(self) -> None:
        if self.process.poll() is None:
            assert self.process.stdin is not None
            self.process.stdin.close()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.kill()
                raise
        self.log.close()


def run_case(source: str) -> dict[str, Any]:
    run = probe.new_run("local", "fail-polite")
    token = secrets.token_urlsafe(32)
    path = probe.config(run)
    runtime.command(
        run,
        "typescript",
        [runtime.NODE, str(probe.ROOT / "node_modules/typescript/bin/tsc"), "--noEmit"],
    )
    runtime.wrangler(
        run,
        "bundle",
        "deploy",
        "--dry-run",
        "--minify",
        "--config",
        str(path),
        "--outdir",
        str(run.directory / "bundle"),
    )
    config = {
        "bundle": str(run.directory / "bundle/worker.js"),
        "persist": str(run.directory / "persist"),
        "vars": json.loads(path.read_text())["vars"],
        "statements": [
            probe.statements((probe.ROOT / "migrations" / name).read_text())
            for name in probe.MIGRATIONS
        ]
        + [probe.statements((probe.PROBE / "schema.sql").read_text())],
    }
    child = Child(run, token, config, resume=False)
    client = probe.Client(run, token)
    report = {
        "entryPath": source,
        "passed": False,
        "actualProcessKill": False,
        "cloudflareHostKill": False,
        "fullConformancePassed": False,
    }
    try:
        client.ready()
        client.request("seed")
        admitted = client.request("admit", request=probe.selection(0, ["process-stop"]))
        partition = admitted["hint"]["partitionId"]
        intent = admitted["items"][0]["intentId"]
        client.request("fail-config", partitionId=partition, fault="handoff")
        before = client.request("object-status", partitionId=partition)["instance"]

        def wake():
            if source == "sweep":
                return client.request("sweep")
            return client.request("wake", hint=admitted["hint"])

        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(wake)
            probe.await_condition(
                lambda: any(
                    row["method"] == "flickr.groups.pools.add"
                    for row in client.request("state")["peer"]
                ),
                10,
                "handoff before process kill",
            )
            old_pid = child.process.pid
            child.kill()
            report["actualProcessKill"] = child.process.returncode != 0
            try:
                pending.result(timeout=30)
            except Exception:
                pass  # Connection loss is expected; persisted state supplies the assertions.
        child = Child(run, token, config, resume=True)
        client.ready()
        after = client.request("object-status", partitionId=partition)["instance"]
        state = client.request("state")
        assert len(state["dispatches"]) == 1 and len(state["resolutions"]) == 0
        assert (
            len([row for row in state["peer"] if row["method"] == "flickr.groups.pools.add"]) == 1
        )
        client.request("fail-config", partitionId=partition)
        view = client.request("view", partitionId=partition)
        client.request(
            "wake", hint={"partitionId": partition, "wakeRevision": view["wakeRevision"]}
        )
        state = client.request("state")
        row = next(row for row in state["intents"] if row["intent_id"] == intent)
        assert row["state"] == "delivery_uncertain" and len(state["blocks"]) == 1
        assert len(state["resolutions"]) == 1
        client.request("sweep")
        final = client.request("state")
        posts = len([row for row in final["peer"] if row["method"] == "flickr.groups.pools.add"])
        assert posts == 1 and before != after and old_pid != child.process.pid
        report.update(
            passed=True,
            instanceChanged=True,
            processChanged=True,
            preservedMarker=True,
            recoveryBlocksPair=True,
            postCount=posts,
        )
    finally:
        child.close()
        report["cleanupConfirmed"] = child.process.poll() is not None
        (run.directory / "process-stop-report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps({"report": str(run.directory / "process-stop-report.json"), **report}),
        flush=True,
    )
    return report


def main() -> None:
    if sys.flags.optimize:
        raise RuntimeError("Assertions must remain enabled")
    for source in ("hint", "sweep"):
        run_case(source)


if __name__ == "__main__":
    main()
