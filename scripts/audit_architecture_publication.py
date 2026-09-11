"""Read-only publication audit of the private architecture repository; never change visibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY = "FlickrGroupAddr/architecture-design"
ARCHITECTURE = Path("C:/Projects/FGA/architecture-design")
RUNS = ARCHITECTURE / ".publication-audit-runs"
SCANNER_VERSION = "8.30.1"
SCANNER_ARCHIVE_SHA2_256 = "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e"


def command(args: list[str], cwd: Path = ARCHITECTURE, *, okay: tuple[int, ...] = (0,)) -> bytes:
    result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=300)
    if result.returncode not in okay:
        raise RuntimeError(f"Audit command failed: {args[0]} (exit {result.returncode}).")
    return result.stdout


def git(*args: str, cwd: Path = ARCHITECTURE) -> str:
    return command(["git", *args], cwd).decode("utf-8", "replace")


def github(path: str) -> Any:
    if path != f"repos/{REPOSITORY}" and not path.startswith(f"repos/{REPOSITORY}/"):
        raise RuntimeError("GitHub request escaped the audited repository.")
    return json.loads(command(["gh", "api", path]))


def paginated(path: str, field: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for page in range(1, 101):
        separator = "&" if "?" in path else "?"
        data = github(f"{path}{separator}per_page=100&page={page}")
        batch = data if field is None else data[field]
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected GitHub collection shape.")
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise RuntimeError("GitHub pagination exceeded the audit bound.")


def indicator_values() -> dict[str, list[bytes]]:
    policy = (ARCHITECTURE / "docs/operations/photography-data-handling.md").read_text(
        encoding="utf-8"
    )
    root = re.search(r"```text\s*([A-Za-z]:[^\n]+)\s*```", policy)
    if root is None:
        raise RuntimeError("The documented catalog-root indicator was not found.")
    record = (
        ARCHITECTURE / "docs/project-log/2026-08-20-production-catalog-flickr-state.md"
    ).read_text(encoding="utf-8")
    identifiers = re.findall(r"\b[0-9A-Fa-f]{8}-(?:[0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}\b", record)
    filenames = re.findall(r"[^\s`<>]+\.(?:CR2|CR3|NEF|ARW|DNG|RAF)\b", record, re.IGNORECASE)
    return {
        "catalog_root": [root[1].strip().encode()],
        "catalog_only_identifier": [value.encode() for value in identifiers],
        "catalog_source_filename": [value.encode() for value in filenames],
    }


def find_sensitive(data: bytes, indicators: dict[str, list[bytes]]) -> list[dict[str, Any]]:
    # Repeated slashes cover JSON/Python/Lua escaped Windows paths without
    # preserving a sensitive match in output. No raw matched value is emitted.
    findings = []
    for line_number, line in enumerate(data.splitlines(), 1):
        normalized = re.sub(rb"\\+", rb"\\", line).lower()
        for rule, values in indicators.items():
            if any(value.lower() in normalized for value in values):
                findings.append({"rule": rule, "line": line_number})
    return findings


def safe_path(path: str, indicators: dict[str, list[bytes]]) -> str:
    if find_sensitive(path.encode(), indicators):
        return "[path SHA2-256:" + hashlib.sha256(path.encode()).hexdigest() + "]"
    return path


def inventory(mirror: Path) -> tuple[dict[str, tuple[str, int]], dict[str, set[str]], set[str]]:
    metadata = {}
    for line in git(
        "cat-file",
        "--batch-all-objects",
        "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        cwd=mirror,
    ).splitlines():
        oid, kind, size = line.split()
        metadata[oid] = (kind, int(size))
    reachable = {
        line.split()[0] for line in git("rev-list", "--objects", "--all", cwd=mirror).splitlines()
    }
    trees = {
        line
        for line in git("log", "--all", "--format=%T", cwd=mirror).splitlines()
        if re.fullmatch(r"[a-f0-9]{40}", line)
    }
    paths: dict[str, set[str]] = defaultdict(set)
    for tree in trees:
        for record in command(["git", "ls-tree", "-r", "-z", tree], mirror).split(b"\0"):
            if not record:
                continue
            prefix, path = record.split(b"\t", 1)
            _, kind, oid = prefix.decode().split()
            paths[oid].add(path.decode("utf-8", "replace"))
    return metadata, paths, reachable


def scan_objects(mirror: Path, output: Path, indicators: dict[str, list[bytes]]) -> dict[str, Any]:
    metadata, paths, reachable = inventory(mirror)
    current = {
        record.split(b"\t", 1)[0].split()[-1].decode()
        for record in command(["git", "ls-tree", "-r", "-z", "HEAD"], mirror).split(b"\0")
        if record
    }
    blobs = output / "blobs"
    blobs.mkdir()
    findings, images, adobe, lfs, known_commits = [], [], [], [], set()
    reader = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=mirror,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert reader.stdin is not None and reader.stdout is not None
    try:
        for oid, (kind, size) in metadata.items():
            if kind != "blob":
                continue
            reader.stdin.write((oid + "\n").encode())
            reader.stdin.flush()
            header = reader.stdout.readline().decode().split()
            if header[:2] != [oid, "blob"] or int(header[2]) != size:
                raise RuntimeError("Git object framing mismatch.")
            data = reader.stdout.read(size)
            if len(data) != size or reader.stdout.read(1) != b"\n":
                raise RuntimeError("Truncated Git object.")
            (blobs / (oid + ".blob")).write_bytes(data)
            names = sorted(paths.get(oid, set()))
            public_names = [safe_path(name, indicators) for name in names]
            location = {
                "blob": oid,
                "paths": public_names,
                "inCurrentTree": oid in current,
                "reachableFromRefs": oid in reachable,
            }
            for hit in find_sensitive(data, indicators):
                findings.append({**location, **hit})
            if any(
                "localswim" in name.lower() and name.lower().endswith(".json") for name in names
            ):
                try:
                    board = json.loads(data)
                except ValueError, UnicodeError:
                    board = None
                if isinstance(board, dict) and "cards" in board:
                    findings.append({**location, "rule": "board_state_candidate", "line": 1})
            if any(
                re.search(r"(?:LrC SDK|Lightroom.*SDK|Sample Plugins|API Reference)/", name, re.I)
                and not name.endswith("README.md")
                for name in names
            ) or (
                re.search(rb"copyright[^\r\n]{0,80}adobe", data, re.I)
                and any(name.endswith((".lua", ".js", ".html", ".pdf", ".zip")) for name in names)
            ):
                adobe.append(location)
            if any(
                name.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".cr2", ".cr3", ".dng", ".heic")
                )
                for name in names
            ):
                images.append(
                    {**location, "bytes": size, "sha2_256": hashlib.sha256(data).hexdigest()}
                )
            if data.startswith(b"version https://git-lfs.github.com/spec/v1"):
                lfs.append(location)
            pattern = (
                rb"github\.com/FlickrGroupAddr/architecture-design/"
                rb"(?:blob|tree|commit)/([a-f0-9]{40})"
            )
            known_commits.update(match.decode() for match in re.findall(pattern, data))
    finally:
        reader.stdin.close()
        reader.stdout.close()
        reader.wait(timeout=30)
    return {
        "objects": len(metadata),
        "blobs": sum(kind == "blob" for kind, _ in metadata.values()),
        "commits": sum(kind == "commit" for kind, _ in metadata.values()),
        "reachableObjects": len(reachable),
        "unreachableLocalObjects": len(set(metadata) - reachable),
        "findings": findings,
        "adobeMaterialCandidates": adobe,
        "imageArtifacts": images,
        "lfsPointers": lfs,
        "knownCommitReferences": sorted(known_commits),
    }


def scan_hosted_surfaces(output: Path, indicators: dict[str, list[bytes]]) -> dict[str, Any]:
    result: dict[str, Any] = {"counts": {}, "findings": [], "coverageGaps": []}
    endpoints = {
        "issues": ("issues?state=all", None),
        "pulls": ("pulls?state=all", None),
        "releases": ("releases", None),
        "actionsArtifacts": ("actions/artifacts", "artifacts"),
        "actionsRuns": ("actions/runs", "workflow_runs"),
        "actionsCaches": ("actions/caches", "actions_caches"),
    }
    for name, (path, field) in endpoints.items():
        rows = paginated(f"repos/{REPOSITORY}/{path}", field)
        (output / (name + ".json")).write_text(json.dumps(rows), encoding="utf-8")
        result["counts"][name] = len(rows)
        result["findings"].extend(
            {"surface": name, **hit}
            for hit in find_sensitive(json.dumps(rows).encode(), indicators)
        )
        if rows:
            # A populated surface requires its bodies, revisions and attachments
            # to be inventoried; never turn unavailable content into a clean pass.
            result["coverageGaps"].append(
                name + " requires object-level attachment/log/revision review"
            )
    return result


def scanner_reports(mirror: Path, output: Path) -> dict[str, Any]:
    executable = RUNS / "tools/gitleaks.exe"
    archive = RUNS / "tools/gitleaks_8.30.1_windows_x64.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SCANNER_ARCHIVE_SHA2_256:
        raise RuntimeError("Scanner release checksum changed.")
    version = command([str(executable), "version"]).decode().strip()
    if version != SCANNER_VERSION:
        raise RuntimeError("Unexpected scanner version.")
    config = output / "scanner.toml"
    config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
    ignore = output / "empty-ignore"
    ignore.write_text("", encoding="utf-8")
    findings = []
    for kind, target in [("git", mirror), ("dir", output / "blobs")]:
        report = output / ("gitleaks-" + kind + ".json")
        args = [
            str(executable),
            kind,
            str(target),
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
        ]
        if kind == "git":
            args.extend(["--log-opts=--all --full-history"])
        result = subprocess.run(args, cwd=output, capture_output=True, timeout=300)
        (output / ("scanner-" + kind + ".log")).write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("Secret scanner execution failed.")
        rows = json.loads(report.read_text(encoding="utf-8")) if report.exists() else []
        for row in rows:
            # Never preserve Match, Secret, commit message, author or email.
            findings.append(
                {
                    "scan": kind,
                    "rule": row.get("RuleID"),
                    "file": row.get("File"),
                    "line": row.get("StartLine"),
                    "commit": row.get("Commit"),
                    "fingerprint": row.get("Fingerprint"),
                }
            )
    return {
        "tool": "gitleaks",
        "version": version,
        "releaseArchiveSha2_256": SCANNER_ARCHIVE_SHA2_256,
        "redactionPercent": 100,
        "candidates": findings,
    }


def audit() -> Path:
    RUNS.mkdir(exist_ok=True)
    output = RUNS / ("audit-" + secrets.token_hex(8))
    output.mkdir()
    meta = github(f"repos/{REPOSITORY}")
    if (
        meta["full_name"] != REPOSITORY
        or not meta.get("private")
        or not meta.get("permissions", {}).get("admin")
    ):
        raise RuntimeError("Audit requires the existing private, owner-controlled repository.")
    remote = git("remote", "get-url", "origin").strip()
    if remote not in {
        "git@github.com:FlickrGroupAddr/architecture-design.git",
        "https://github.com/FlickrGroupAddr/architecture-design.git",
    }:
        raise RuntimeError("Unexpected source remote.")
    before = git("ls-remote", "origin")
    baseline = git("rev-parse", "HEAD").strip()
    mirror = output / "mirror.git"
    command(["git", "clone", "--bare", "--no-hardlinks", str(ARCHITECTURE), str(mirror)])
    command(["git", "remote", "set-url", "origin", remote], mirror)
    command(["git", "remote", "set-url", "--push", "origin", "DISABLED"], mirror)
    command(
        [
            "git",
            "fetch",
            "--no-tags",
            "origin",
            "refs/heads/*:refs/audit/heads/*",
            "refs/tags/*:refs/audit/tags/*",
            "refs/pull/*/head:refs/audit/pull/*/head",
        ],
        mirror,
    )
    indicators = indicator_values()
    print("Auditing Git objects and current privacy indicators.", flush=True)
    objects = scan_objects(mirror, output, indicators)
    print("Auditing GitHub issue/release/Actions surfaces.", flush=True)
    hosted = scan_hosted_surfaces(output, indicators)
    print("Running redacted Gitleaks scans over history and all local blob objects.", flush=True)
    scanner = scanner_reports(mirror, output)
    for row in scanner["candidates"]:
        row["file"] = safe_path(str(row["file"]), indicators)
        row.pop("fingerprint", None)
    print("Checking known off-ref GitHub object reachability.", flush=True)
    remote_objects = []
    seen = set()
    for finding in objects["findings"]:
        oid = finding["blob"]
        if oid in seen:
            continue
        seen.add(oid)
        response = subprocess.run(
            ["gh", "api", f"repos/{REPOSITORY}/git/blobs/{oid}"], capture_output=True, timeout=30
        )
        remote_objects.append(
            {
                "blob": oid,
                "apiRetrievable": response.returncode == 0,
                "inCurrentTree": finding["inCurrentTree"],
                "reachableFromRefs": finding["reachableFromRefs"],
            }
        )
    references = []
    for oid in objects["knownCommitReferences"]:
        response = subprocess.run(
            ["gh", "api", f"repos/{REPOSITORY}/git/commits/{oid}"], capture_output=True, timeout=30
        )
        references.append({"commit": oid, "apiRetrievable": response.returncode == 0})
    current_findings = []
    for raw in command(["git", "ls-files", "-z"]).split(b"\0"):
        if not raw:
            continue
        name = raw.decode("utf-8", "replace")
        path = ARCHITECTURE / name
        if path.is_file():
            current_findings.extend(
                {"path": safe_path(name, indicators), **hit}
                for hit in find_sensitive(path.read_bytes(), indicators)
            )
    after = git("ls-remote", "origin")
    report = {
        "schemaVersion": 1,
        "repository": REPOSITORY,
        "visibility": "PRIVATE",
        "visibilityChanged": False,
        "auditedAt": datetime.now(UTC).isoformat(),
        "baselineCommit": baseline,
        "advertisedRefs": [
            {"oid": line.split()[0], "ref": line.split()[1]} for line in before.splitlines()
        ],
        "advertisedRefsUnchanged": before == after,
        "git": objects,
        "hosted": hosted,
        "scanner": scanner,
        "gitHubBlobReachability": remote_objects,
        "knownCommitReachability": references,
        "workingTreeFindings": current_findings,
        "limitations": [
            "GitHub does not expose an enumeration of unknown cached unreachable objects; "
            "known refs, local objects and in-repository object references were checked.",
            "Pattern scans do not prove absence of every credential or private image; "
            "binary provenance and candidates require review.",
        ],
        "publicationAuditPassed": False,
    }
    (output / "sanitized-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "objects": objects["objects"],
                "blobs": objects["blobs"],
                "findingCounts": dict(Counter(x["rule"] for x in objects["findings"])),
                "currentFindings": len(current_findings),
                "credentialCandidates": len(scanner["candidates"]),
                "adobeCandidates": len(objects["adobeMaterialCandidates"]),
                "images": len(objects["imageArtifacts"]),
                "hostedCounts": hosted["counts"],
                "report": str(output / "sanitized-report.json"),
            }
        )
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
