"""Isolated exact-artifact local tests; no account or deployment client."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from retained import retained_bytes, sha2_256


def verify(build: Path, node: Path, receipt: Path) -> None:
    receipt.mkdir(exist_ok=False, parents=True)
    here = Path(__file__).resolve().parent
    home = receipt / "empty-home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "COMSPEC"}}
    for name in [
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "TEMP",
        "TMP",
    ]:
        directory = home / name.lower()
        directory.mkdir()
        env[name] = str(directory)
    env.update(
        {
            "PATH": str(node.parent) + os.pathsep + str(Path(env["SYSTEMROOT"]) / "System32"),
            "CI": "true",
            "NO_COLOR": "1",
            "PMB1_ARTIFACT_DIRECTORY": str(build),
            "NODE_OPTIONS": "--require=" + str(here / "test-isolate.cjs"),
            "PMB1_HOST_RECEIPT": str(receipt / "host.json"),
        }
    )
    result = subprocess.run(
        [str(node), "--test", "--test-concurrency=1", str(here / "artifact.test.mjs")],
        cwd=receipt,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )
    (receipt / "tests.txt").write_bytes(result.stdout)
    hosts = [json.loads(p.read_text()) for p in receipt.glob("host-*.json")]
    if result.returncode or not hosts or any(h["externalAttempts"] for h in hosts):
        raise ValueError("local artifact tests or host isolation failed; inspect tests.txt")
    manifest_raw = (build / "artifact-manifest.json").read_bytes()
    retained = retained_bytes(build / "retained", sha2_256(manifest_raw))
    record = {
        "emittedArtifactTests": "PASS",
        "manifestSha2_256": sha2_256(manifest_raw),
        "retainedFiles": len(retained),
        "externalAttempts": 0,
        "configuredDate": "2026-10-16",
        "emulatorOnlyOverride": "2026-08-06",
        "configuredDateFit": False,
        "actualQualification": False,
        "emptyEnvironmentKeys": sorted(env),
    }
    (receipt / "verification.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    verify(args.build.resolve(), args.node.resolve(), args.receipt.resolve())
