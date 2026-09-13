"""Run six bounded crash-proof mutations in copies, never in the working source tree."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "src/fail_polite.ts"
POLICY = ROOT / "src/dispatch_policy.ts"
FRESHNESS = ROOT / "src/dispatch_freshness.ts"
MIGRATION = ROOT / "migrations/0004_fail_polite_attempts.sql"
MUTATIONS = {
    "marker_order": (CORE, 'await record(db,lease,attempt,"marker",0,reservation.id??null);', ";"),
    "unknown_retry": (
        POLICY,
        'return { outcome: "delivery_uncertain", reason: "unknown_code", pause: "deployment" };',
        'return { outcome: "retrying", reason: "unknown_code", pause: "deployment" };',
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


def invoke(name: str, root: Path) -> tuple[int, dict]:
    process = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/coordination_probe.py"),
            "local",
            "fail-polite",
            "--mutation-check",
            name,
        ],
        cwd=root,
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


def isolated_copy(destination: Path) -> None:
    if not destination.resolve().is_relative_to((ROOT / ".coordination-runs").resolve()):
        raise RuntimeError("Mutation workspace escaped its run directory")
    for folder in ("src", "migrations", "scripts", "probes"):
        shutil.copytree(
            ROOT / folder, destination / folder, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in ("package.json", "package-lock.json", "tsconfig.json", "pyproject.toml", "uv.lock"):
        shutil.copy2(ROOT / name, destination / name)
    # Read-only package use; no dependencies are mutated or removed by this runner.
    subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item -ItemType Junction -Path $env:FGA_MUTATION_LINK "
            "-Target $env:FGA_MUTATION_PACKAGES | Out-Null",
        ],
        env={
            **os.environ,
            "FGA_MUTATION_LINK": str(destination / "node_modules"),
            "FGA_MUTATION_PACKAGES": str(ROOT / "node_modules"),
        },
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=True,
        capture_output=True,
    )


def main() -> None:
    original = {path: path.read_bytes() for path in {CORE, POLICY, MIGRATION, FRESHNESS}}
    parent = ROOT / ".coordination-runs"
    parent.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="fail-polite-mutations-", dir=parent))
    records = []
    for name, (path, before, after) in MUTATIONS.items():
        control = run / (name + "-control")
        isolated_copy(control)
        code, baseline = invoke(name, control)
        if code or not baseline.get("completed"):
            raise RuntimeError("Unmutated control failed: " + name)
        mutant = run / (name + "-mutant")
        isolated_copy(mutant)
        text = original[path].decode("utf-8")
        if before not in text:
            raise RuntimeError("Mutation anchor absent: " + name)
        changed = text.replace(before, after)
        target = mutant / path.relative_to(ROOT)
        target.write_text(changed, encoding="utf-8", newline="\n")
        code, mutated = invoke(name, mutant)
        detected = (
            code == 1
            and any(
                case["id"] == "mutation." + name and not case["passed"] for case in mutated["cases"]
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
        unchanged = all(path.read_bytes() == value for path, value in original.items())
        report = {
            "scope": "six bounded native crash-proof mutations; not complete production gate",
            "environment": "local workerd/D1",
            "records": records,
            "workingSourcesUnchanged": unchanged,
        }
        (run / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Mutation " + name + ": " + ("detected" if detected else "FAILED"), flush=True)
        if not detected or not unchanged:
            raise RuntimeError("Mutation failed its intended assertion or changed working sources")
    print("Mutation evidence: " + str(run / "summary.json"), flush=True)


if __name__ == "__main__":
    main()
