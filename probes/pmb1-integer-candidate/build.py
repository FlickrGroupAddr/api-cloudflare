"""Offline native TypeScript ESM source build and exact private build receipt.

Uses existing installed pinned tools. No provider command, install or network.
The output directory is caller-owned evidence outside the source tree.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import assemble


def sha2_256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    result = subprocess.run(command, cwd=assemble.ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("native_source_build_refused: " + result.stdout + result.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default="node")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    output = args.out.resolve()
    if output == assemble.ROOT or assemble.ROOT in output.parents:
        raise ValueError("build_evidence_must_be_outside_source_tree")
    # Exact regeneration is checked before any build, never silently refreshed.
    for name, raw in assemble.assemble(args.node).items():
        if (assemble.HERE / name).read_bytes() != raw:
            raise ValueError("candidate_source_drift")
    compiler = assemble.ROOT / "node_modules/@typescript/typescript-win32-x64/lib/tsc.exe"
    compiler_version = run([str(compiler), "--version"]).stdout.strip()
    if compiler_version != "Version 7.0.2":
        raise ValueError("existing_pinned_tool_version_required")
    run([str(compiler), "--noEmit", "-p", str(assemble.HERE / "tsconfig.json")])
    output.mkdir(parents=True, exist_ok=False)
    # Native compiler output preserves the complete imported module layout.
    # Provider packaging/compatibility and external runtime dependencies remain
    # separate gates; no custom compatibility shim or fallback is introduced.
    run(
        [
            str(compiler),
            "-p",
            str(assemble.HERE / "tsconfig.json"),
            "--noEmit",
            "false",
            "--rewriteRelativeImportExtensions",
            "--rootDir",
            str(assemble.ROOT),
            "--outDir",
            str(output / "modules"),
        ]
    )
    modules = {
        path.relative_to(output).as_posix(): sha2_256(path)
        for path in sorted((output / "modules").rglob("*.js"))
    }
    entry = "modules/probes/pmb1-integer-candidate/candidate.js"
    if entry not in modules:
        raise ValueError("compiled_candidate_entry_missing")
    receipt = {
        "profile": assemble.PROFILE,
        "sourceManifestSha2_256": sha2_256(assemble.HERE / "source-manifest.json"),
        "entry": entry,
        "entrySha2_256": modules[entry],
        "compiledModules": modules,
        "toolchain": {
            "compiler": compiler_version,
            "nativeCompilerSha2_256": sha2_256(compiler),
            "node": run([args.node, "--version"]).stdout.strip(),
        },
        "packageLockSha2_256": sha2_256(assemble.ROOT / "package-lock.json"),
        "externalPackages": "existing package-lock dependencies; not vendored in this source build",
        "providerBundle": False,
        "registered": False,
        "deployed": False,
        "actualQualification": False,
        "runtimePortsSupplied": False,
    }
    (output / "build-manifest.json").write_bytes(assemble.encode(receipt))
    print(
        json.dumps(
            {
                "nativeCompilation": True,
                "compiledModules": len(modules),
                "entrySha2_256": receipt["entrySha2_256"],
                "actualQualification": False,
            }
        )
    )


if __name__ == "__main__":
    main()
