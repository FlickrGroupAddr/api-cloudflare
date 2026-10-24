"""Reuse the reviewed offline static packager for a named RPC-only SOURCE fixture.

Python owns orchestration; Wrangler's installed native dependency graph remains
the required provider bundler. No package install, network or account operation.
"""

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RETAINED = ROOT / "probes/pmb1-retained-integration"
spec = importlib.util.spec_from_file_location("retained_source_build", RETAINED / "build.py")
if spec is None or spec.loader is None:
    raise RuntimeError("retained static build unavailable")
retained = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retained)
packager = retained.packager
packager.__dict__["HERE"] = HERE
base_sources = retained.sources


def sources():
    result = base_sources()
    # The fixture imports the unchanged application's compiled source-context
    # contract. Its own complete final module/graph/config have independent pins.
    for path in RETAINED.iterdir():
        if path.is_file() and path.name != "source-manifest.json":
            result[path.relative_to(ROOT).as_posix()] = packager.pin(path)
    return dict(sorted(result.items()))


def contract():
    application = json.loads((RETAINED / "source-contract.json").read_text())
    return {
        **application,
        "syntheticPrivateRpcFixture": True,
        "fixtureSourceManifestSha2_256": packager.digest(packager.encoded(sources())),
    }


packager.__dict__["sources"] = sources
packager.__dict__["source_contract"] = contract

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--node", type=Path)
    args = parser.parse_args()
    if args.prepare:
        (HERE / "source-contract.json").write_bytes(packager.encoded(contract()))
    elif args.output and args.node:
        packager.build(args.output.resolve(), args.node)
    else:
        parser.error("--prepare or --output NEW --node PINNED required")
