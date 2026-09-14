"""Isolated production-path mutations; compilation failures never count as detection."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts import fail_polite_mutations as copies
from scripts import fail_polite_release as gate

ROOT = Path(__file__).resolve().parent.parent
CORE = "src/fail_polite.ts"
TRANSPORT = "src/dispatch_transport.ts"
POLICY = "src/dispatch_policy.ts"
FRESH = "src/dispatch_freshness.ts"
WORKER = "src/dispatch_worker.ts"
# Each tuple changes production source, never the assertion harness.
SPECS: dict[str, tuple[str, str, list[tuple[str, str, str]]]] = {}


def spec(name, section, case, *changes):
    SPECS[name] = (section, case, list(changes))


spec(
    "cached_membership",
    "core",
    "FP-MEM-001",
    (
        TRANSPORT,
        (
            'const present = membershipPresent(await readJson(signed("flickr.'
            'photos.getAllContexts", context, pair, app), fetcher), context.g'
            "roupId);"
        ),
        "const present = false;",
    ),
)
spec(
    "cached_preflight",
    "core",
    "FP-MEM-001",
    (
        TRANSPORT,
        (
            'const moderated = moderationValue(await readJson(signed("flickr.'
            'groups.getInfo", context, pair, app), fetcher), context.groupId)'
            ";"
        ),
        "const moderated:0|1 = 0;",
    ),
)
spec(
    "continue_after_membership_failure",
    "core",
    "FP-MEM-003",
    (
        CORE,
        (
            'try {reservation.consume("membership");present=await deps.transp'
            "ort.membership(attempt);}\n  catch(error) {return await unavailab"
            "le(error);}"
        ),
        (
            'try {reservation.consume("membership");present=await deps.transp'
            "ort.membership(attempt);}\n  catch(error) {present=false;}"
        ),
    ),
)
spec(
    "filter_invalid_membership",
    "core",
    "FP-MEM-004",
    (
        TRANSPORT,
        (
            'if (!entry || typeof entry !== "object" || Array.isArray(entry))'
            " throw new DispatchTransportError();"
        ),
        'if (!entry || typeof entry !== "object" || Array.isArray(entry)) continue;',
    ),
)
spec(
    "default_membership_to_empty",
    "core",
    "FP-MEM-004",
    (TRANSPORT, "  const ids = new Set<string>();", "  const ids = new Set<string>();"),
    (
        TRANSPORT,
        '  if (value.stat !== "ok" || !Array.isArray(value.pool)',
        (
            '  if(value.stat==="ok"&&!Array.isArray(value.pool))value.pool=[]'
            ';\n  if (value.stat !== "ok" || !Array.isArray(value.pool)'
        ),
    ),
)
spec(
    "separate_rate_reservations",
    "core",
    "FP-MEM-006",
    ("src/flickr_rate.ts", "reserved_slots+3<=capacity", "reserved_slots+1<=capacity"),
    (
        "src/flickr_rate.ts",
        "reserved_slots=reserved_slots+3",
        "reserved_slots=reserved_slots+MIN(3,capacity-reserved_slots)",
    ),
)
spec(
    "missing_moderation_unmoderated",
    "core",
    "FP-PRE-002",
    (
        TRANSPORT,
        "  const record = group as Record<string, unknown>;",
        (
            "  const record = group as Record<string, unknown>;\n  if(record.i"
            "d===groupId&&record.ispoolmoderated===undefined)return 0;"
        ),
    ),
)
spec(
    "inclusive_freshness",
    "core",
    "FP-PRE-007",
    (FRESH, "age<PREFLIGHT_MAX_AGE_US", "age<=PREFLIGHT_MAX_AGE_US"),
)
spec(
    "wrong_clock_profile",
    "core",
    "FP-PRE-007",
    (WORKER, "hooks?.monotonicUs??(()=>Date.now()*1000)", "(()=>Date.now()*1000)"),
)
spec(
    "invalid_age_accepted",
    "core",
    "FP-PRE-011",
    (
        FRESH,
        (
            " return Number.isSafeInteger(receivedUs) && Number.isSafeInteger"
            "(nowUs)\n  && Number.isSafeInteger(age) && age>=0 && age<PREFLIGH"
            "T_MAX_AGE_US;"
        ),
        " return !Number.isFinite(age)||(age>=0&&age<PREFLIGHT_MAX_AGE_US);",
    ),
)
spec(
    "negative_age_accepted",
    "core",
    "FP-PRE-011",
    (FRESH, "age>=0 && age<PREFLIGHT_MAX_AGE_US", "age<PREFLIGHT_MAX_AGE_US"),
)
spec(
    "deferred_preparation",
    "core",
    "FP-PRE-001",
    (
        CORE,
        "try {prepared=await deps.transport.prepareAdd(attempt);}",
        (
            "try {prepared={handoff:async()=>(await deps.transport.prepareAdd"
            "(attempt)).handoff(),dispose(){}};}"
        ),
    ),
)
spec(
    "intervening_flickr_operation",
    "core",
    "FP-MEM-001",
    (
        TRANSPORT,
        "      const moderated = moderationValue(",
        (
            '      await readJson(signed("flickr.photos.getAllContexts", cont'
            "ext, pair, app), fetcher);\n      const moderated = moderationVal"
            "ue("
        ),
    ),
)
spec(
    "post_before_marker",
    "core",
    "FP-MEM-001",
    (CORE, 'await record(db,lease,attempt,"marker",0,reservation.id??null);', ";"),
)
for code in (6, 7):
    spec(
        f"code_{code}_retryable",
        "core",
        "FP-RES-001" if code == 6 else "FP-RES-002",
        (
            POLICY,
            "  if (result === 6 || result === 7)",
            f'  if (result === {code}) return {{outcome:"retrying",'
            f'reason:"flickr_code_{code}",pause:null}};\n'
            "  if (result === 6 || result === 7)",
        ),
    )
# code 6 also drives the ordinary first test; its intended classification witness is MEM-001.
SPECS["code_6_retryable"] = ("core", "FP-MEM-001", SPECS["code_6_retryable"][2])
spec(
    "unknown_retryable",
    "core",
    "FP-RES-004",
    (
        POLICY,
        'return { outcome: "delivery_uncertain", reason: "unknown_code", pause: "deployment" };',
        'return { outcome: "retrying", reason: "unknown_code", pause: "deployment" };',
    ),
)
spec(
    "non_atomic_block_terminal",
    "core",
    "FP-RES-009",
    (
        CORE,
        "await db.batch(statements);return outcome;",
        "await db.batch(statements.slice(0,2));await db.batch(statements.slice(2));return outcome;",
    ),
)
spec("retry_unresolved_dispatch", "core", "FP-RES-009", (CORE, "old.marked?", "false?"))
# Ordinary provider/admin paths must never issue a protected clear, even if SQL
# guards refuse it. The driver observes those attempts without changing execution.
clear = 'try{await db.prepare("DELETE FROM submission_blocks").run();}catch{}\n'
spec(
    "clear_on_retention",
    "blocks",
    "FP-BLOCK-006",
    (
        "src/submission_status.ts",
        "export async function cleanupStatusReads(db:SqlStore):Promise<void>{",
        "export async function cleanupStatusReads(db:SqlStore):Promise<void>{\n" + clear,
    ),
)
spec(
    "clear_on_relink",
    "blocks",
    "FP-BLOCK-005",
    (
        "src/admin_api.ts",
        (
            "export async function maintainNativeCredentials(env:AdminEnv,fet"
            "cher:FlickrFetch):Promise<void>{"
        ),
        (
            "export async function maintainNativeCredentials(env:AdminEnv,fet"
            "cher:FlickrFetch):Promise<void>{\n"
        )
        + clear.replace("db.prepare", "env.DB.prepare"),
    ),
)
for name, case, condition in [
    ("clear_on_positive_membership", "FP-BLOCK-010", "present"),
    ("clear_on_negative_membership", "FP-BLOCK-010", "!present"),
    ("clear_on_unmoderated", "FP-BLOCK-004", "!present&&(await reader.preflight(context))===0"),
]:
    injection = (
        '  const item=await env.DB.prepare("SELECT photo_id photoId,group'
        "_id groupId FROM submission_intents WHERE partition_id=? AND EXI"
        "STS(SELECT 1 FROM submission_blocks b WHERE b.photo_id=submissio"
        "n_intents.photo_id AND b.group_id=submission_intents.group_id) L"
        'IMIT 1").bind(partitionId).first<{photoId:string;groupId:string}'
        '>();\n  if(item){const context={...item,attemptId:"mutation-read"'
        "};const reader=await transport();const present=await reader.memb"
        'ership(context);\n   if(CONDITION){try{await env.DB.prepare("DELE'
        'TE FROM submission_blocks WHERE photo_id=? AND group_id=?").bind'
        "(item.photoId,item.groupId).run();}catch{}}}\n"
    ).replace("CONDITION", condition)
    spec(
        name,
        "blocks",
        case,
        (
            WORKER,
            "  return runPartition({db:env.DB,",
            injection + "  return runPartition({db:env.DB,",
        ),
    )
for name, case, test in [
    ("clear_on_guessed_retry", "FP-BLOCK-002", 'request.method==="POST"&&path?.endsWith("/retry")'),
    (
        "allow_block_deletion",
        "FP-BLOCK-008",
        'request.method==="DELETE"&&path?.startsWith("/api/v001/admin/submission-blocks/")',
    ),
]:
    injection = (
        "    if("
        + test
        + (
            '){try{await env.DB.prepare("DELETE FROM submission_blocks").run('
            ");}catch{}return new Response(null,{status:204});}\n"
        )
    )
    spec(
        name,
        "blocks",
        case,
        (
            "src/worker.ts",
            "    const candidates=ROUTES.filter(route=>{",
            injection + "    const candidates=ROUTES.filter(route=>{",
        ),
    )
spec(
    "allow_force_flag",
    "blocks",
    "FP-BLOCK-007",
    (
        "src/admission.ts",
        " validateAdmission(value);",
        (
            ' if(value&&typeof value==="object"&&"force" in value)delete (val'
            "ue as Record<string,unknown>).force;\n validateAdmission(value);"
        ),
    ),
)
spec(
    "missing_sql_guard",
    "blocks",
    "FP-BLOCK-009",
    (
        "migrations/0004_fail_polite_attempts.sql",
        (
            "CREATE TRIGGER attempt_dispatches_no_delete BEFORE DELETE ON att"
            "empt_dispatches\n BEGIN SELECT RAISE(ABORT,'attempt_evidence_immu"
            "table'); END;\n"
        ),
        "",
    ),
)


def clone(target: Path):
    copies.isolated_copy(target)
    shutil.copytree(ROOT / "assets", target / "assets")
    shutil.copytree(ROOT / "docs/contracts", target / "docs/contracts")


def invoke(root: Path, section: str, case: str | None = None):
    command = [
        sys.executable,
        "-m",
        "scripts.production_matrix",
        "--environment",
        "local",
        "--section",
        section,
    ]
    if case:
        command += ["--stop-after", case]
        if section == "blocks":
            command += ["--block-ids", case]
    elif section == "blocks":
        command += ["--block-ids", *[f"FP-BLOCK-{i:03d}" for i in [1, 2, 4, 5, 6, 7, 8, 9, 10]]]
    process = None
    for _attempt in range(2):
        process = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=360,
            env={**os.environ, "FGA_MATRIX_RUN_PARENT": str(ROOT / ".coordination-runs")},
        )
        if (
            "Network connection lost" not in process.stderr
            or "matrix_assertion_failed_" in process.stderr
        ):
            break
        print("Retrying one fresh local run after adapter connection loss", flush=True)

    assert process is not None
    lines = [
        x.removeprefix("Private matrix run: ")
        for x in process.stdout.splitlines()
        if x.startswith("Private matrix run: ")
    ]
    if len(lines) != 1:
        raise RuntimeError("mutation_missing_run_directory")
    directory = Path(lines[0])
    report = directory / "matrix-report.json"
    if not report.is_file():
        raise RuntimeError("mutation_infrastructure_failed_without_assertion")
    data = json.loads(report.read_text(encoding="utf-8"))
    intended = process.returncode == 1 and f"matrix_assertion_failed_{case}" in process.stderr
    # Raw output stays private; no raw provider/token material is published.
    (directory / "controller.private.log").write_text(
        process.stdout + "\n" + process.stderr, encoding="utf-8"
    )
    return process.returncode, data, intended


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    if set(SPECS) != set(gate.MUTATIONS):
        raise RuntimeError("mutation_inventory_mismatch")
    names = args.only or list(gate.MUTATIONS)
    run = Path(tempfile.mkdtemp(prefix="production-mutations-", dir=ROOT / ".coordination-runs"))
    print("Private mutation run: " + str(run), flush=True)
    baseline = run / "control"
    clone(baseline)
    control = {}
    control_artifacts = set()
    for section in sorted({SPECS[name][0] for name in names}):
        code, data, _ = invoke(baseline, section)
        if code:
            raise RuntimeError("unmutated_production_control_failed")
        control_artifacts.add(data["artifactSha2_256"])
        control.update({x["id"]: x for x in data["cases"]})
        print("Control " + section + ": passed", flush=True)
    records = []

    def execute(name):
        section, case, changes = SPECS[name]
        target = run / name
        clone(target)
        altered = []
        for relative, before, after in changes:
            path = target / relative
            s = path.read_text(encoding="utf-8")
            if before not in s:
                raise RuntimeError("mutation_anchor_missing_" + name)
            old = gate.digest(path)
            path.write_text(s.replace(before, after), encoding="utf-8", newline="\n")
            altered.append(
                {"path": relative, "beforeSha2_256": old, "afterSha2_256": gate.digest(path)}
            )
        code, data, intended = invoke(target, section, case)
        failed = [x["id"] for x in data["cases"] if x["status"] == "failed"]
        detected = bool(intended and failed == [case] and control[case]["status"] == "passed")
        print(name + (": detected" if detected else ": NOT DETECTED"), flush=True)
        return {
            "id": name,
            "controlPassed": True,
            "mutantFailed": detected,
            "failureKind": "behavioral" if detected else "unqualified",
            "detectedBy": failed,
            "changes": altered,
            "processExitCode": code,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for record in pool.map(execute, names):
            records.append(record)
            (run / "summary.json").write_text(
                json.dumps(
                    {
                        "scope": "production-mutation-components",
                        "fullConformancePassed": False,
                        "controlArtifactSha2_256": sorted(control_artifacts),
                        "records": records,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    if not all(x["mutantFailed"] for x in records):
        raise RuntimeError("production_mutant_not_detected")
    print("Mutation evidence: " + str(run / "summary.json"), flush=True)


if __name__ == "__main__":
    main()
