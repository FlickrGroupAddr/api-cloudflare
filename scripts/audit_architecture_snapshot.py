"""Audit only the prepared publication file set; keep scan details private."""

from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
from pathlib import Path

try:
    from . import prepare_architecture_snapshot as snapshot
except ImportError:
    import prepare_architecture_snapshot as snapshot

audit = snapshot.audit
# Exact reviewed documentation files; these two generic-api-key hits are prose.
REVIEWED_PROSE = {
    "docs/operations/session-signing-key.md": (
        "6c3527d3566811cc1baf94674df588f68ec76d48884ea16bc76e118f8c250db8"
    ),
    "docs/hosted-deployment.md": "c966d19a8d4157f6760c4079bcc5fe5b03fd95ba03f1f39e7f513bfb5ef20042",
}


def check() -> dict:
    source_commit, source = snapshot.tracked_tree()
    private = snapshot.indicators(source)
    preparation = json.loads((audit.RUNS / "public-snapshot-preparation.json").read_text())
    if preparation["sourceCommit"] != source_commit:
        raise RuntimeError("Private source changed after preparation.")
    output = audit.RUNS / ("public-check-" + secrets.token_hex(8))
    output.mkdir()
    scan = output / "content"
    scan.mkdir()
    data_by_name = {}
    for name in preparation["fileHashes"]:
        path = snapshot.DESTINATION / name
        data = path.read_bytes()
        if audit.find_sensitive(data, private) or audit.find_sensitive(name.encode(), private):
            raise RuntimeError("Private indicator in candidate: " + name)
        if name.startswith("docs/decisions/") and data != source[name]:
            raise RuntimeError("ADR drift: " + name)
        target = scan / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        data_by_name[name] = data
    executable = audit.RUNS / "tools/gitleaks.exe"
    archive = audit.RUNS / "tools/gitleaks_8.30.1_windows_x64.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != audit.SCANNER_ARCHIVE_SHA2_256:
        raise RuntimeError("Scanner checksum mismatch.")
    version = audit.command([str(executable), "version"]).decode().strip()
    if version != audit.SCANNER_VERSION:
        raise RuntimeError("Unexpected scanner version.")
    config = output / "gitleaks.toml"
    config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
    ignore = output / "empty-ignore"
    ignore.write_text("", encoding="utf-8")
    report = output / "gitleaks.json"
    result = subprocess.run(
        [
            str(executable),
            "dir",
            str(scan),
            "--redact=100",
            "--report-format=json",
            "--report-path",
            str(report),
            "--config",
            str(config),
            "--gitleaks-ignore-path",
            str(ignore),
            "--ignore-gitleaks-allow",
            "--exit-code=0",
            "--no-banner",
        ],
        capture_output=True,
        timeout=180,
    )
    (output / "scanner.log").write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Scanner failed.")
    findings = json.loads(report.read_text()) if report.exists() else []
    for finding in findings:
        name = Path(finding["File"]).resolve().relative_to(scan.resolve()).as_posix()
        if finding["RuleID"] != "generic-api-key" or hashlib.sha256(
            data_by_name[name]
        ).hexdigest() != REVIEWED_PROSE.get(name):
            raise RuntimeError("Unreviewed credential candidate in " + name)
    result = {
        "sourceCommit": source_commit,
        "fileCount": len(data_by_name),
        "privateIndicatorsRemaining": 0,
        "credentialCandidates": len(findings),
        "reviewedProseFalsePositives": len(findings),
        "unreviewedCandidates": 0,
        "scannerVersion": version,
        "scannerArchiveSha2_256": audit.SCANNER_ARCHIVE_SHA2_256,
        "acceptedDecisionFilesUnchanged": True,
        "fileHashes": {n: hashlib.sha256(d).hexdigest() for n, d in data_by_name.items()},
    }
    (audit.RUNS / "public-snapshot-validation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in result.items() if k != "fileHashes"}))
    return result


if __name__ == "__main__":
    check()
