"""Check or launch a pinned literal JSON command, without shell conversion.

This transports reviewed inputs only. The invoked protocol owns authorization,
budgets, deadlines, cleanup and no-replay rules. Checking never launches a child.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_STRING_CHARS = 32767
MAX_ARGV = 512
FIELDS = {"executable", "cwd", "environmentOverrides", "argv"}


class Refusal(ValueError):
    """The command was refused before child launch."""


def literal(value: Any) -> str:
    if type(value) is not str or "\0" in value or len(value) > MAX_STRING_CHARS:
        raise Refusal("expected bounded literal string")
    # Unpaired surrogate escapes cannot be transported as an ordinary native argv.
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise Refusal("invalid string encoding") from exc
    return value


def absolute_path(value: Any) -> Path:
    raw = literal(value)
    if not raw or len(raw) > 4096 or not Path(raw).is_absolute():
        raise Refusal("expected bounded absolute path")
    return Path(raw)


def no_links(path: Path) -> None:
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Refusal("linked manifest path refused")


def fingerprint(info: os.stat_result) -> tuple[int, int, int, int, int]:
    # Windows lstat/fstat may expose different ctime meanings; use shared fields.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink)


def read_manifest(path: Path, pin: str) -> bytes:
    if re.fullmatch(r"[0-9a-f]{64}", pin) is None:
        raise Refusal("expected exact lowercase SHA2-256 pin")
    no_links(path)
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size > MAX_MANIFEST_BYTES
    ):
        raise Refusal("expected bounded regular manifest")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if fingerprint(before) != fingerprint(opened):
            raise Refusal("manifest changed during open")
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
        after = os.fstat(stream.fileno())
    no_links(path)
    if (
        len(raw) > MAX_MANIFEST_BYTES
        or fingerprint(opened) != fingerprint(after)
        or fingerprint(after) != fingerprint(path.lstat())
    ):
        raise Refusal("manifest changed during read")
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), pin):
        raise Refusal("manifest SHA2-256 mismatch")
    return raw


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Refusal("duplicate JSON key")
        result[key] = value
    return result


def windows_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def command(raw: bytes) -> tuple[list[str], str, dict[str, str]]:
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise Refusal("invalid manifest JSON") from exc
    if type(document) is not dict or set(document) != FIELDS:
        raise Refusal("expected closed command manifest")
    executable = literal(document["executable"])
    cwd = literal(document["cwd"])
    if not absolute_path(executable).is_file() or not absolute_path(cwd).is_dir():
        raise Refusal("executable or cwd unavailable")
    if os.name == "nt" and Path(executable).suffix.lower() in {".bat", ".cmd"}:
        raise Refusal("Windows batch executable requires a shell")
    argv = document["argv"]
    overrides = document["environmentOverrides"]
    if type(argv) is not list or len(argv) > MAX_ARGV:
        raise Refusal("expected bounded argv list")
    arguments = [executable, *(literal(item) for item in argv)]
    if os.name == "nt" and windows_units(subprocess.list2cmdline(arguments)) > 32766:
        raise Refusal("Windows command line too long")
    if type(overrides) is not dict or len(overrides) > 128:
        raise Refusal("expected bounded environment overrides")
    environment = os.environ.copy()
    names: set[str] = set()
    for key, value in overrides.items():
        name = literal(key)
        if not name or "=" in name or name.upper() in names:
            raise Refusal("invalid or duplicate environment name")
        names.add(name.upper())
        if os.name == "nt":
            for inherited in list(environment):
                if inherited.upper() == name.upper():
                    del environment[inherited]
        environment[name] = literal(value)
    if (
        os.name == "nt"
        and sum(windows_units(k) + windows_units(v) + 2 for k, v in environment.items()) > 32766
    ):
        raise Refusal("Windows environment too long")
    return arguments, cwd, environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest")
    parser.add_argument("--sha2-256")
    options = parser.parse_args(argv)
    if not options.check and not options.execute:
        print("reviewed manifest launcher disabled; select --check or --execute")
        return 0
    if options.manifest is None or options.sha2_256 is None:
        parser.error("active modes require --manifest and --sha2-256")
    try:
        arguments, cwd, environment = command(
            read_manifest(absolute_path(options.manifest), options.sha2_256)
        )
    except (Refusal, OSError, ValueError) as exc:
        # Do not echo manifest content, paths, argv or environment values.
        category = str(exc) if isinstance(exc, Refusal) else "manifest unavailable"
        print(f"reviewed manifest refused: {category}", file=sys.stderr)
        return 2
    if options.check:
        print("reviewed manifest check passed; no child launched")
        return 0
    try:
        return subprocess.run(
            arguments, cwd=cwd, env=environment, shell=False, check=False
        ).returncode
    except OSError:
        print("reviewed manifest child launch failed; no retry", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
