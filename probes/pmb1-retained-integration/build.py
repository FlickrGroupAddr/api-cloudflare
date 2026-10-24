"""Specialize the reviewed offline static packager; do not fork its implementation."""

import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "pmb1-static-artifact"
spec = importlib.util.spec_from_file_location("pmb1_reviewed_static_build", BASE / "build.py")
if spec is None or spec.loader is None:
    raise RuntimeError("reviewed static packager unavailable")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)
packager.__dict__["HERE"] = HERE
base_sources = packager.sources


def sources() -> dict[str, str]:
    result = base_sources()
    for directory in ["pmb1-fresh-native-capture", "pmb1-runtime-evidence"]:
        for path in (packager.ROOT / "probes" / directory).rglob("*"):
            if (
                path.is_file()
                and path.name not in {"source-contract.json", "source-manifest.json"}
                and path.suffix in {".ts", ".sql", ".json", ".py", ".mjs", ".cjs"}
            ):
                result[path.relative_to(packager.ROOT).as_posix()] = packager.pin(path)
    # The reused build and native isolation guard remain separately pinned.
    for name in ["build.py", "isolate.cjs", "test-isolate.cjs", "retained.py"]:
        path = BASE / name
        result[path.relative_to(packager.ROOT).as_posix()] = packager.pin(path)
    return dict(sorted(result.items()))


packager.__dict__["sources"] = sources

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--node", type=Path)
    args = parser.parse_args()
    if args.prepare:
        (HERE / "source-contract.json").write_bytes(packager.encoded(packager.source_contract()))
    elif args.output and args.node:
        packager.build(args.output.resolve(), args.node)
    else:
        parser.error("--prepare or --output NEW_DIRECTORY --node PINNED_NODE required")
