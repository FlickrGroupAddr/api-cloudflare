"""Freeze/check local source only; never inspect a provider or runtime resource."""

import argparse
import hashlib
import json
from pathlib import Path


def manifest() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    paths = sorted(
        [
            Path("package.json"),
            Path("package-lock.json"),
            Path("tsconfig.json"),
            *[p.relative_to(root) for p in (root / "src").rglob("*.ts")],
            *[
                p.relative_to(root)
                for p in (root / "probes/pmb1-native-journal").iterdir()
                if p.is_file() and p.name != "source-pins.json"
            ],
        ],
        key=lambda p: p.as_posix(),
    )
    return {
        "schema": "pmb1-main-journal-source-v1",
        "providerQualified": False,
        "typescript": "7.0.2-native",
        "node": "24.22.0",
        "inputs": {
            path.as_posix(): hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in paths
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).with_name("source-pins.json")
    source = json.dumps(manifest(), indent=2) + "\n"
    if args.check:
        if path.read_text(encoding="utf-8") != source:
            raise SystemExit("main-entry journal source pins differ")
    else:
        path.write_text(source, encoding="utf-8", newline="\n")
    print("main-entry journal source pins verified")


if __name__ == "__main__":
    main()
