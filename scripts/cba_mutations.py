"""Run nine CBA mutations in isolated copies; never edit the working source tree."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    "alias_shell_fallback": (
        ("src/worker.ts"),
        ('return errorResponse(404,"not_found","Resource not found.");'),
        ('return new Response("<html>shell</html>",{headers:{"Content-Type":"text/html"}});'),
    ),
    "client_per_group_loop": (
        ("clients/lightroom/GroupSubmissionClient.lua"),
        ("    return post(Client.PATH, encode(request), {"),
        (
            "    for index = 1, count do post(Client.PATH, encode(request"
            "), {}) end\n    return post(Client.PATH, encode(request), {"
        ),
    ),
    "partial_validation": (
        ("src/admission.ts"),
        (" validateAdmission(value);"),
        (
            ' if(value && typeof value==="object" && Array.isArray((value'
            " as any).flickrGroupIds))(value as any).flickrGroupIds=(valu"
            'e as any).flickrGroupIds.filter((g:unknown)=>typeof g==="str'
            'ing"&&TOKEN.test(g));\n validateAdmission(value);'
        ),
    ),
    "hint_before_commit": (
        ("src/admission.ts"),
        (" try { results=await db.batch(statements); }"),
        (
            ' try { await publishHint({partitionId:"premature",wakeRevisi'
            'on:"1"}); results=await db.batch(statements); }'
        ),
    ),
    "hint_per_group_fanout": (
        ("src/admission.ts"),
        ("await publishHint(hint);"),
        ("for(const _group of value.flickrGroupIds) await publishHint(hint);"),
    ),
    "client_chosen_hint": (
        ("src/admission.ts"),
        (" if(hint) { try"),
        (" if(hint) hint.partitionId=value.flickrGroupIds[0];\n if(hint) { try"),
    ),
    "idempotent_retry_hint": (
        ("src/admission.ts"),
        ("WHERE i.created_request_id=?1\n   AND i.active_fifo_member=1"),
        ("WHERE i.binding_id=?4\n   AND i.active_fifo_member=1"),
    ),
    "drop_unhinted_due": (
        ("src/scheduling.ts"),
        ("WHERE ${ELIGIBLE} ORDER BY"),
        ("WHERE ${ELIGIBLE} AND lease_id IS NOT NULL ORDER BY"),
    ),
    "bound_drift": (
        ("src/admission.ts"),
        ("MAX_GROUP_IDS = 60"),
        ("MAX_GROUP_IDS = 61"),
    ),
}


def execute(directory: Path, client: bool) -> subprocess.CompletedProcess[str]:
    command = (
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_batch_client.py"]
        if client
        else ["node", "--test", "--test-reporter=tap", "tests/intake.test.mjs"]
    )
    return subprocess.run(
        command, cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=180
    )


def main() -> int:
    parent = ROOT / ".coordination-runs"
    parent.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="cba-mutations-", dir=parent))
    originals = {
        name: hashlib.sha256((ROOT / value[0]).read_bytes()).hexdigest()
        for name, value in MUTATIONS.items()
    }
    outcomes = []
    for name in ["baseline", *MUTATIONS]:
        work = run / name
        for part in ["src", "tests", "migrations", "clients", "scripts", "generated"]:
            shutil.copytree(ROOT / part, work / part, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "probes/intake", work / "probes/intake")
        shutil.copy2(ROOT / "tsconfig.json", work / "tsconfig.json")
        test_path = work / "tests/intake.test.mjs"
        source = test_path.read_text(encoding="utf-8")
        source = source.replace(
            '"node_modules/typescript/bin/tsc"',
            json.dumps((ROOT / "node_modules/typescript/bin/tsc").as_posix()),
        ).replace(
            '"node_modules/wrangler/bin/wrangler.js"',
            json.dumps((ROOT / "node_modules/wrangler/bin/wrangler.js").as_posix()),
        )
        test_path.write_text(source, encoding="utf-8", newline="\n")
        if name != "baseline":
            file, old, new = MUTATIONS[name]
            path = work / file
            content = path.read_text(encoding="utf-8")
            if content.count(old) != 1:
                raise RuntimeError(f"Expected one mutation target: {name}")
            path.write_text(content.replace(old, new), encoding="utf-8", newline="\n")
        result = execute(work, name == "client_per_group_loop")
        output = result.stdout + result.stderr
        (work / "result.log").write_text(output, encoding="utf-8")
        passed = (
            result.returncode == 0
            if name == "baseline"
            else result.returncode != 0
            and ("not ok" in output or "AssertionError" in output)
            and "error TS" not in output
            and "Command failed" not in output
        )
        outcomes.append({"name": name, "passed": passed, "exitCode": result.returncode})
        print(json.dumps(outcomes[-1]), flush=True)
        if not passed:
            break
    unchanged = all(
        hashlib.sha256((ROOT / value[0]).read_bytes()).hexdigest() == originals[name]
        for name, value in MUTATIONS.items()
    )
    report = {
        "schemaVersion": 1,
        "scope": "local isolated production-source CBA mutations",
        "outcomes": outcomes,
        "workingSourcesUnchanged": unchanged,
        "allPassed": len(outcomes) == 10 and all(x["passed"] for x in outcomes) and unchanged,
    }
    (run / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("CBA mutation report: " + str(run / "summary.json"), flush=True)
    return 0 if report["allPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
