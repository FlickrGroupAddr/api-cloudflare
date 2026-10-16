"""Prepare private offline inputs from the owner-pinned candidate and capture."""

import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

CANDIDATE = "b599ca828d2a645b686aca0354d6c8ee2c2a0250"
CAPTURE_DIGEST = "f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument("private_output", type=Path)
    parser.add_argument("node", type=Path)
    args = parser.parse_args()
    output = args.private_output.resolve()
    if output.is_relative_to(args.repository.resolve()) or not any(
        parent.name == "private-evidence" for parent in output.parents
    ):
        raise ValueError("private_output_required")
    # Import the inspection implementation by file path: no checkout module drift.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "prerequisites",
        Path(__file__).resolve().parents[2] / "scripts/fixed_origin_capture_prerequisites.py",
    )
    assert spec and spec.loader
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    receipt = inspector.inspect_capture(args.capture)
    if receipt["moduleSha2_256"] != CAPTURE_DIGEST:
        raise ValueError("unexpected_capture")
    # Fresh directory only; never overwrite evidence or decode inside the #0036 capture.
    args.private_output.mkdir(parents=False, exist_ok=False)
    archive = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={args.repository.as_posix()}",
            "-c",
            "core.excludesFile=.git/info/exclude",
            "archive",
            "--format=zip",
            CANDIDATE,
            "src",
            "migrations",
            "package.json",
            "package-lock.json",
        ],
        cwd=args.repository,
        capture_output=True,
        check=True,
    ).stdout
    candidate = args.private_output / "candidate"
    candidate.mkdir()
    hashes = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as files:
        for item in files.infolist():
            target = candidate / item.filename
            if not target.resolve().is_relative_to(candidate.resolve()):
                raise ValueError("archive_path")
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                content = files.read(item)
                target.write_bytes(content)
                hashes[item.filename] = hashlib.sha256(content).hexdigest()
    import base64

    if (candidate / "package-lock.json").read_bytes() != (
        args.repository / "package-lock.json"
    ).read_bytes():
        raise ValueError("dependency_lock_mismatch")
    capture = json.loads(args.capture.read_bytes())["result"]
    decoded = base64.b64decode(capture["modules"][0]["content_base64"], validate=True)
    if hashlib.sha256(decoded).hexdigest() != CAPTURE_DIGEST:
        raise ValueError("capture_changed")
    (args.private_output / "captured.mjs").write_bytes(decoded)
    subprocess.run(
        [
            str(args.node),
            str(Path(__file__).with_name("bundle_candidate.mjs")),
            str(args.repository),
            str(candidate),
            str(args.private_output / "candidate.mjs"),
        ],
        check=True,
        capture_output=True,
    )
    bundle = (args.private_output / "candidate.mjs").read_bytes()
    manifest = {
        "schemaVersion": 1,
        "candidateCommit": CANDIDATE,
        "capturedModuleSha2_256": CAPTURE_DIGEST,
        "candidateBundleSha2_256": hashlib.sha256(bundle).hexdigest(),
        "candidateBundleBytes": len(bundle),
        "candidateSourceFiles": hashes,
        "hostedQualified": False,
    }
    (args.private_output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({key: value for key, value in manifest.items() if key != "candidateSourceFiles"})
    )


if __name__ == "__main__":
    main()
