"""Verify the supported remote-D1 test adapter with owned disposable resources."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.bootstrap_deployment import file_token, save
from scripts.hosted_restore_proof import Proof
from scripts.runtime_permissions_probe import NODE, ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--token-file", type=Path)
    args = parser.parse_args()
    if not args.run:
        parser.print_help()
        return 0
    if args.token_file:
        os.environ["CLOUDFLARE_API_TOKEN"] = file_token(str(args.token_file))
    proof = Proof()
    success = False
    try:
        database = proof.create("remote-binding")
        config = proof.directory / "remote-wrangler.json"
        save(
            config,
            {
                "name": proof.name,
                "account_id": proof.operator.account_id,
                "compatibility_date": "2026-09-11",
                "d1_databases": [
                    {
                        "binding": "DB",
                        "database_id": database,
                        "database_name": proof.name + "-remote-binding",
                        "remote": True,
                    }
                ],
            },
        )
        child = subprocess.Popen(
            [NODE, str(ROOT / "probes/release/remote-binding.mjs"), str(config)],
            cwd=ROOT,
            env={
                **os.environ,
                "CI": "true",
                "WRANGLER_SEND_METRICS": "false",
                "WRANGLER_WRITE_LOGS": "false",
                "CLOUDFLARE_API_TOKEN": proof.operator.operator,
                "CLOUDFLARE_ACCOUNT_ID": proof.operator.account_id,
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            start_new_session=sys.platform != "win32",
        )
        try:
            output, error = child.communicate(timeout=90)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                    check=True,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                import signal

                os.killpg(child.pid, signal.SIGKILL)
            child.communicate(timeout=15)
            raise RuntimeError("remote_proxy_session_timeout") from None
        (proof.directory / "remote-binding.private.log").write_text(
            output + "\n" + error, encoding="utf-8"
        )
        if child.returncode:
            raise RuntimeError("remote_proxy_failed_see_private_log")
        success = proof.query(database, "SELECT value FROM remote_binding_marker") == [
            {"value": 42}
        ]
        if not success:
            raise RuntimeError("remote_database_witness_missing")
    finally:
        proof.cleanup()
        report = {
            "schemaVersion": 1,
            "scope": "remote-D1-binding-adapter",
            "remoteBindingRoundTrip": success,
            "verifiedThroughSeparateRestRead": success,
            "cleanupConfirmed": proof.report.get("cleanupConfirmed", False),
            "fullConformancePassed": False,
            "localCompatibilityDate": "2026-07-30",
        }
        save(proof.directory / "remote-binding-report.json", report)
        print(json.dumps(report))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
