"""Generate/check the public API inventory directly from the executable TS registry."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = subprocess.run(
        ["node", "scripts/export_api_registry.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    artifacts = json.loads(result.stdout)
    directory = ROOT / "generated"
    directory.mkdir(exist_ok=True)
    for key, name in [("inventory", "route-inventory.json"), ("openapi", "openapi.json")]:
        expected = json.dumps(artifacts[key], indent=2) + "\n"
        target = directory / name
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != expected:
                print(f"Stale generated artifact: {name}")
                return 1
        else:
            target.write_text(expected, encoding="utf-8", newline="\n")
    print("API inventory and OpenAPI match the executable registry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
