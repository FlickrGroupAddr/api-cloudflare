"""Offline static Workers packaging; no deployment/registration or auth client.

Python owns orchestration/manifests. Wrangler's normal nodejs_compat bundler is
required because its supported Workers transformations own the dependency graph.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TSC = ROOT / "node_modules/@typescript/typescript-win32-x64/lib/tsc.exe"
WRANGLER = ROOT / "node_modules/wrangler/bin/wrangler.js"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pin(path: Path) -> str:
    return digest(path.read_bytes())


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def sources() -> dict[str, str]:
    # This explicit superset includes the source mechanisms and external operator
    # adapters as well as the exact runtime closure later reported by esbuild.
    paths = list((ROOT / "src").glob("*.ts"))
    for name in [
        "pmb1-integer-candidate",
        "pmb1-native-journal",
        "pmb1-native-disposition",
        "pmb1-native-object-reader",
        "pmb1-no-real-object-reader",
        "pmb1-object",
        "pmb1-native-alarm",
        "pmb1-native-wakeup",
        "pmb1-native-d1-binding",
        "pmb1-d1",
        "pmb1-d1-adapter",
    ]:
        paths.extend(
            p
            for p in (ROOT / "probes" / name).iterdir()
            if p.is_file() and p.suffix in {".ts", ".sql", ".json", ".py"}
        )
    paths.extend((ROOT / "migrations").glob("*.sql"))
    paths.extend(
        p
        for p in HERE.iterdir()
        if p.is_file() and p.name not in {"source-contract.json", "source-manifest.json"}
    )
    paths.extend(ROOT / p for p in ["package.json", "package-lock.json", "tsconfig.json"])
    return {p.relative_to(ROOT).as_posix(): pin(p) for p in sorted(set(paths))}


def source_contract() -> dict:
    return {
        "schema": "pmb1-static-source-contract-v1",
        "profile": "pmb1-private-application-no-real-v1",
        "objectBoundary": "pmb1-private-object-kv-interface-v1",
        "d1Operation": "fixed_update_with_exact_count_positional_v1",
        "sourceContextSha2_256": digest(encoded(sources())),
        "actualImmutableVersion": None,
        "actualResourceMapping": None,
        "actualQualification": False,
        "registration": False,
    }


def run(command: list[str], cwd: Path, env: dict[str, str], log: Path) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
        check=False,
    )
    log.write_bytes(result.stdout)
    if result.returncode:
        raise RuntimeError(f"{log.name}: exit {result.returncode}")


def build(output: Path, node: Path) -> None:
    NODE = node.resolve()
    if output.exists():
        raise ValueError("output must be a NEW immutable directory")
    output.mkdir(parents=True)
    contract = source_contract()
    if (HERE / "source-contract.json").read_bytes() != encoded(contract):
        raise ValueError("source contract stale; use --prepare before building")
    inputs = sources()
    stage = ROOT / ".probe-build" / ("pmb1-static-" + uuid.uuid4().hex)
    stage.mkdir(parents=True)
    for relative in inputs:
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    for name in ["source-contract.json"]:
        shutil.copyfile(HERE / name, stage / HERE.relative_to(ROOT) / name)
    # Nearest package.json prevents configuration discovery beyond this clean
    # root. Dependencies resolve to the existing locked repository installation;
    # no install, login, package download or tool update is possible here.
    home = stage / "isolated-home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "COMSPEC"}}
    env.update(
        {
            k: str(home / k.lower())
            for k in [
                "USERPROFILE",
                "APPDATA",
                "LOCALAPPDATA",
                "XDG_CONFIG_HOME",
                "XDG_CACHE_HOME",
                "TEMP",
                "TMP",
            ]
        }
    )
    for name in [
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "TEMP",
        "TMP",
    ]:
        Path(env[name]).mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "PATH": str(NODE.parent) + os.pathsep + str(Path(env["SYSTEMROOT"]) / "System32"),
            "CI": "true",
            "NO_COLOR": "1",
            "WRANGLER_HIDE_BANNER": "true",
            "WRANGLER_SEND_METRICS": "false",
            "WRANGLER_SEND_ERROR_REPORTS": "false",
            "NO_UPDATE_NOTIFIER": "1",
            "WRANGLER_LOG_PATH": str(home / "wrangler.log"),
            "PMB1_ISOLATED_ROOT": str(stage),
            "PMB1_ISOLATION_RECEIPT": str(output / "isolation.json"),
        }
    )
    run([str(NODE), "--version"], stage, env, output / "node-version.txt")
    run([str(TSC), "--version"], stage, env, output / "compiler-version.txt")
    if (output / "node-version.txt").read_text().strip() != "v24.22.0":
        raise ValueError("wrong Node version")
    if "7.0.2" not in (output / "compiler-version.txt").read_text():
        raise ValueError("wrong native compiler version")
    # Compiler runs against the same copied sources; type packages use the exact
    # installed lock-bound native toolchain in the ancestor node_modules.
    run(
        [str(TSC), "-p", str(stage / HERE.relative_to(ROOT) / "tsconfig.json"), "--noEmit"],
        stage,
        env,
        output / "native-types.txt",
    )
    config = stage / HERE.relative_to(ROOT) / "wrangler.json"
    env["NODE_OPTIONS"] = "--require=" + str(stage / HERE.relative_to(ROOT) / "isolate.cjs")
    probe_env = dict(env)
    probe_env["PMB1_ISOLATION_RECEIPT"] = str(output / "guard-selftest.json")
    probe = (
        "let n=0;for(const fn of [()=>fetch('https://example.invalid'),"
        "()=>require('node:net').connect({host:'example.invalid',port:443}),"
        "()=>require('node:dns').lookup('example.invalid'),"
        "()=>require('node:fs').readFileSync('../.env')]){"
        "try{fn()}catch(e){if(/^pmb1_/.test(e.message))n++;else throw e}}"
        "if(n!==4)process.exit(2)"
    )
    run([str(NODE), "-e", probe], stage, probe_env, output / "guard-selftest.txt")
    probe_receipts = [json.loads(p.read_text()) for p in output.glob("guard-selftest-*.json")]
    if len(probe_receipts) != 1 or probe_receipts[0]["networkAttempts"] != 3:
        raise ValueError("network/auth guard self-test failed")
    run(
        [
            str(NODE),
            str(WRANGLER),
            "deploy",
            "--dry-run",
            "--config",
            str(config),
            "--outdir",
            str(output / "emitted"),
            "--metafile",
            str(output / "bundle-meta.json"),
        ],
        stage,
        env,
        output / "wrangler-build.txt",
    )
    receipts = [json.loads(p.read_text()) for p in output.glob("isolation-*.json")]
    if not receipts or any(r["networkAttempts"] != 0 for r in receipts):
        raise ValueError("build attempted network")
    meta = json.loads((output / "bundle-meta.json").read_text())
    graph = {}
    source_map = json.loads((output / "emitted/entry.js.map").read_text())
    virtual_sources = dict(zip(source_map["sources"], source_map["sourcesContent"], strict=True))
    for relative, item in meta["inputs"].items():
        source = (config.parent / relative).resolve()
        if not source.is_file():
            if relative not in virtual_sources or not isinstance(virtual_sources[relative], str):
                raise ValueError("unresolved esbuild graph input: " + relative)
            raw = virtual_sources[relative].encode()
            if len(raw) != item["bytes"]:
                raise ValueError("virtual source byte count drift")
            graph[relative] = {
                "sha2_256": digest(raw),
                "bytes": len(raw),
                "imports": item.get("imports", []),
                "virtual": True,
                "authority": "locked Wrangler nodejs_compat transformation; emitted map",
            }
            continue
        name = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else relative
        # Stage paths are normalized back to their repository-relative names.
        if source.is_relative_to(stage):
            name = source.relative_to(stage).as_posix()
        graph[name] = {
            "sha2_256": pin(source),
            "bytes": source.stat().st_size,
            "imports": item.get("imports", []),
        }
    modules = {
        p.relative_to(output / "emitted").as_posix(): pin(p)
        for p in (output / "emitted").rglob("*")
        if p.is_file()
    }
    retained = output / "retained"
    shutil.copytree(output / "emitted", retained / "modules")
    (retained / "configuration.json").write_bytes(config.read_bytes())
    manifest = {
        **contract,
        "schema": "pmb1-static-workers-artifact-v1",
        "providerCompatibleBundle": True,
        "localOnly": True,
        "sourceInputs": inputs,
        "sourceContractSha2_256": pin(HERE / "source-contract.json"),
        "moduleSha2_256": modules,
        "runtimeGraph": graph,
        "configurationSha2_256": pin(config),
        "storeManifestSha2_256": pin(ROOT / "probes/pmb1-integer-candidate/store-manifest.json"),
        "bindingManifestSha2_256": pin(HERE / "binding-manifest.json"),
        "toolchain": {
            str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else "portable-node.exe": pin(p)
            for p in [
                NODE,
                TSC,
                WRANGLER,
                ROOT / "package-lock.json",
                ROOT / "node_modules/wrangler/wrangler-dist/cli.js",
                ROOT / "node_modules/@esbuild/win32-x64/esbuild.exe",
                ROOT
                / "node_modules/wrangler/node_modules"
                / "@cloudflare/workerd-windows-64/bin/workerd.exe",
                ROOT
                / "node_modules/miniflare/node_modules"
                / "@cloudflare/workerd-windows-64/bin/workerd.exe",
                ROOT / "node_modules/miniflare/dist/src/index.js",
            ]
        },
        "restore": {"rebuildAllowed": False, "force": False, "actualImmutableVersion": None},
        "isolation": {
            "inheritedEnvironment": sorted(env),
            "cachedAuth": False,
            "networkAttempts": 0,
            "telemetry": False,
        },
        "missingActualGates": [
            "independent authenticated ReviewedCoverage",
            "immutable version and resource identity",
            "native fit/custody and complete population",
            "campaign footprint/allocation and managed qualification",
        ],
    }
    (output / "artifact-manifest.json").write_bytes(encoded(manifest))
    (retained / "artifact-manifest.json").write_bytes(encoded(manifest))
    # Recheck all original source bytes after emission; a concurrent edit refuses.
    if inputs != sources():
        raise ValueError("source changed during build")
    print(
        json.dumps(
            {
                "modules": len(modules),
                "runtimeInputs": len(graph),
                "sourceInputs": len(inputs),
                "networkAttempts": 0,
                "actualQualification": False,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--node", type=Path)
    args = parser.parse_args()
    if args.prepare:
        (HERE / "source-contract.json").write_bytes(encoded(source_contract()))
    elif args.output and args.node:
        build(args.output.resolve(), args.node)
    else:
        parser.error("--prepare or --output NEW_DIRECTORY --node PINNED_NODE required")
