"""Exercise deferred preparation in an isolated source copy, never the working tree."""

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parent = ROOT / ".coordination-runs"
    parent.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="dispatch-preparation-", dir=parent))
    original = (ROOT / "src/fail_polite.ts").read_bytes()
    outcomes = []
    for name in ("baseline", "deferred_preparation"):
        work = run / name
        for part in ("src", "tests", "migrations"):
            shutil.copytree(ROOT / part, work / part, ignore=shutil.ignore_patterns("__pycache__"))
        if name != "baseline":
            path = work / "src/fail_polite.ts"
            source = path.read_text(encoding="utf-8")
            old = "  try {prepared=await deps.transport.prepareAdd(attempt);}"
            marker = (
                '  await record(db,lease,attempt,"marker",0,reservation.id??null);\n'
                "  if(deps.fault)"
            )
            if source.count(old) != 1 or source.count(marker) != 1:
                raise RuntimeError("Preparation mutation anchor is not unique")
            source = source.replace(marker, "  if(deps.fault)")
            source = source.replace(
                old, '  await record(db,lease,attempt,"marker",0,reservation.id??null);\n' + old
            )
            path.write_text(source, encoding="utf-8", newline="\n")
        result = subprocess.run(
            ["node", "--test", "--test-reporter=tap", "tests/dispatch_transport.test.mjs"],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        output = result.stdout + result.stderr
        (work / "result.log").write_text(output, encoding="utf-8")
        expected_assertion = (
            "not ok" in output
            and (
                "prepared signed dispatch follows membership/preflight/marker" in output
                or "expired during preparation" in output
            )
            and "ERR_ASSERTION" in output
        )
        passed = (
            result.returncode == 0
            if name == "baseline"
            else (result.returncode != 0 and expected_assertion)
        )
        outcomes.append({"id": name, "passed": passed, "exitCode": result.returncode})
        if not passed:
            break
    unchanged = (ROOT / "src/fail_polite.ts").read_bytes() == original
    report = {
        "schemaVersion": 1,
        "scope": "bounded local preparation-boundary mutation",
        "sourceSha2_256": hashlib.sha256(original).hexdigest(),
        "outcomes": outcomes,
        "workingSourcesUnchanged": unchanged,
        "allPassed": len(outcomes) == 2 and all(row["passed"] for row in outcomes) and unchanged,
    }
    (run / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Preparation mutation report: " + str(run / "summary.json"), flush=True)
    print(json.dumps(report), flush=True)
    return 0 if report["allPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
