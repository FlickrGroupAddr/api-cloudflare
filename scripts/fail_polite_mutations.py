"""Run six isolated source/migration mutations; always restore the original bytes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "src/fail_polite.ts"
FRESHNESS = ROOT / "src/dispatch_freshness.ts"
MIGRATION = ROOT / "migrations/0004_fail_polite_attempts.sql"
MUTATIONS = {
    "marker_order": (CORE, 'await record(db,lease,attempt,"marker");', ";"),
    "unknown_retry": (
        CORE,
        'else {outcome="delivery_uncertain";reason="unknown_code";}',
        'else {outcome="retrying";reason="unknown_code";}',
    ),
    "unresolved_retry": (CORE, "old.marked?", "false?"),
    "inclusive_clock": (FRESHNESS, "age<PREFLIGHT_MAX_AGE_US", "age<=PREFLIGHT_MAX_AGE_US"),
    "split_block": (CORE, "if(blocked) statements.push", "if(false && blocked) statements.push"),
    "removed_guard": (
        MIGRATION,
        "CREATE TRIGGER attempt_dispatches_no_delete BEFORE DELETE ON attempt_dispatches\n"
        " BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;\n",
        "",
    ),
}


def invoke(name: str) -> tuple[int, dict]:
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/coordination_probe.py"),
            "local",
            "fail-polite",
            "--mutation-check",
            name,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    paths = [
        line.removeprefix("Coordination report: ")
        for line in process.stdout.splitlines()
        if line.startswith("Coordination report: ")
    ]
    if len(paths) != 1:
        raise RuntimeError("Mutation run did not produce one report.")
    report = json.loads(Path(paths[0]).read_text())
    return process.returncode, report


def main() -> None:
    original = {path: path.read_bytes() for path in {CORE, MIGRATION, FRESHNESS}}
    records = []
    destination = ROOT / "docs/evidence/fail-polite-mutations-2026-09-11.json"
    try:
        for name, (path, before, after) in MUTATIONS.items():
            code, baseline = invoke(name)
            if code or not baseline.get("completed"):
                raise RuntimeError("Unmutated control failed: " + name)
            text = original[path].decode()
            if before not in text:
                raise RuntimeError("Mutation anchor absent: " + name)
            changed = text.replace(before, after)
            try:
                path.write_text(changed, encoding="utf-8", newline="\n")
                code, mutated = invoke(name)
            finally:
                path.write_bytes(original[path])
            detected = (
                code == 1
                and any(
                    case["id"] == "mutation." + name and not case["passed"]
                    for case in mutated["cases"]
                )
                and mutated.get("cleanupConfirmed")
            )
            records.append(
                {
                    "name": name,
                    "detected": bool(detected),
                    "unmutatedControlPassed": True,
                    "changedFile": path.relative_to(ROOT).as_posix(),
                    "originalSha2_256": hashlib.sha256(original[path]).hexdigest(),
                    "mutatedSha2_256": hashlib.sha256(changed.encode()).hexdigest(),
                    "cases": mutated["cases"],
                    "cleanupConfirmed": mutated.get("cleanupConfirmed"),
                }
            )
            print("Mutation " + name + ": " + ("detected" if detected else "FAILED"), flush=True)
            if not detected:
                raise RuntimeError("Mutation did not fail its intended assertion: " + name)
    finally:
        for path, data in original.items():
            path.write_bytes(data)
        destination.write_text(
            json.dumps(
                {
                    "scope": (
                        "six bounded native crash-proof mutations; "
                        "not complete production mutation gate"
                    ),
                    "environment": "local workerd/D1",
                    "records": records,
                    "sourcesRestored": all(
                        path.read_bytes() == data for path, data in original.items()
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print("Mutation evidence: " + str(destination))


if __name__ == "__main__":
    main()
