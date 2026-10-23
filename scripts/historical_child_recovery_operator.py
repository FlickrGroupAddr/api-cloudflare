"""Concrete, explicitly invoked recovery adapters. Import and CLI are inert.

Primary authenticates the independent evidence bindings outside this module.
Bindings preserve that judgment; hashes and local tests cannot supply facts.
No command reads a request, credentials, runtime directories or provider state.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import copy
import os
import sqlite3
import stat
import sys
import types
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts import historical_child_recovery as recovery

FACTS = frozenset(
    {
        "identityCustody",
        "consumerTermination",
        "cleanupCallerTermination",
        "permanentNoReadmission",
        "unknownResourcesPreserved",
        "parentLifetime",
        "authorityApplicability",
    }
)


@dataclass(frozen=True)
class EvidenceRef:
    path: str
    sha2_256: str


@dataclass(frozen=True)
class OriginalManifestBinding:
    """Primary-authenticated ORIGINAL source provenance, never a JSON default.

    The external Primary judgment authenticates these exact original root,
    commit, manifest and complete manifest map plus retained provenance bytes.
    Construction or hash equality alone cannot authenticate their meaning.
    """

    source_root: str
    source_commit: str
    sha2_256: str
    source_pins: dict[str, str]
    provenance: EvidenceRef


@dataclass(frozen=True)
class ReviewedFacts:
    """Primary-retained independent judgment, never parsed from an untrusted file.

    Each fact references exact independently authenticated supporting evidence.
    The primary must authenticate its provenance and meaning before construction.
    There is deliberately no JSON loader, default PASS or generated witness.
    """

    request_digest: str
    producer_source_pins: dict[str, str]
    original_pins: dict[str, str]
    current_pins: dict[str, str]
    fact_evidence: dict[str, EvidenceRef]
    packet_review: EvidenceRef | None
    original_manifest: OriginalManifestBinding | None = None


def fact_reference(refs: dict[str, EvidenceRef]) -> str:
    """Commit support role paths/digests in the existing witness reference field."""
    return "sha2-256:" + recovery.digest(
        recovery.encoded(
            {role: {"path": ref.path, "sha2_256": ref.sha2_256} for role, ref in refs.items()}
        )
    )


def _regular(path: Path, *, directory: bool = False) -> os.stat_result:
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise recovery.Refused("operator_link_or_ancestor_refused")
        if (
            getattr(ancestor.stat(follow_symlinks=False), "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise recovery.Refused("operator_reparse_refused")
    info = path.stat()
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise recovery.Refused("operator_reparse_refused")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise recovery.Refused("operator_regular_role_required")
    if not directory and info.st_nlink != 1:
        raise recovery.Refused("operator_hardlink_refused")
    return info


def _source_bytes(path: Path) -> bytes:
    before = _regular(path)
    if not 0 < before.st_size <= 16777216:
        raise recovery.Refused("operator_source_bound")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(16777217)
        after = os.fstat(stream.fileno())
    final = _regular(path)

    def identity(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

    # Windows path stat and handle fstat expose different ctime meanings.
    # Compare ctime within each API, never across those two APIs.
    if (
        identity(before) != identity(final)
        or identity(opened) != identity(after)
        or identity(before)[:4] != identity(opened)[:4]
    ):
        raise recovery.Refused("operator_source_changed")
    if len(raw) != before.st_size:
        raise recovery.Refused("operator_source_changed")
    return raw


def _loaded_code(module: types.ModuleType, raw: bytes, extra=None, *, ambient=False) -> None:
    """Compare actually loaded Python functions with independently pinned bytes."""
    expected = {}

    def walk(code):
        expected[(code.co_filename, code.co_qualname)] = code
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                walk(value)

    walk(compile(raw, str(module.__file__), "exec", dont_inherit=True))

    tree = ast.parse(raw)

    def functions(nodes, owner):
        # Enumerate REQUIRED source declarations, rather than filtering actual
        # values by __module__: a foreign replacement must never be skipped.
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                value = vars(owner).get(node.name)
                if not isinstance(value, type) or value.__module__ != module.__name__:
                    raise recovery.Refused("operator_source_binding_changed")
                yield from functions(node.body, value)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                value = vars(owner).get(node.name)
                if isinstance(value, staticmethod | classmethod):
                    value = value.__func__
                elif isinstance(value, property):
                    value = value.fget
                if not isinstance(value, types.FunctionType) or value.__module__ != module.__name__:
                    raise recovery.Refused("operator_source_binding_changed")
                yield value

    for function in functions(tree.body, module):
        code = function.__code__
        # contextmanager's standard-library helper wraps a source-owned method.
        # Authenticate its trusted stdlib code AND the pinned wrapped method.
        if code in contextlib.contextmanager.__code__.co_consts:
            wrapped = getattr(function, "__wrapped__", None)
            if not isinstance(wrapped, types.FunctionType):
                raise recovery.Refused("operator_loaded_code_not_pinned")
            code = wrapped.__code__
        if code.co_filename != str(module.__file__):
            if extra is None or code.co_filename not in extra:
                raise recovery.Refused("operator_loaded_code_not_pinned")
            walk(compile(extra[code.co_filename], code.co_filename, "exec", dont_inherit=True))
        if expected.get((code.co_filename, code.co_qualname)) != code:
            raise recovery.Refused("operator_loaded_code_not_pinned")
    if ambient:
        _ambient_bindings(module, tree)


def _ambient_bindings(module: types.ModuleType, tree: ast.Module) -> None:
    """Derive bootstrap imports/constants from PINNED source, not current state."""
    values = {"frozenset": frozenset, "set": set, "tuple": tuple, "dict": dict}

    def expression(node):
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return expression(node.left) | expression(node.right)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"set", "frozenset", "tuple", "dict"}
            and len(node.args) == 1
            and not node.keywords
        ):
            return values[node.func.id](expression(node.args[0]))
        return ast.literal_eval(node)

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imported = alias.name if alias.asname else alias.name.split(".")[0]
                if vars(module).get(name) is not sys.modules.get(imported):
                    raise recovery.Refused("operator_ambient_import_changed")
        elif isinstance(node, ast.ImportFrom) and not node.level:
            imported = sys.modules.get(str(node.module))
            if imported is None:
                raise recovery.Refused("operator_ambient_import_changed")
            for alias in node.names:
                if vars(module).get(alias.asname or alias.name) is not getattr(
                    imported, alias.name
                ):
                    raise recovery.Refused("operator_ambient_import_changed")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    expected = expression(node.value)
                    actual = vars(module).get(target.id)
                    if type(actual) is not type(expected) or actual != expected:
                        raise recovery.Refused("operator_ambient_constants_changed")
                    values[target.id] = expected


class PinnedSources:
    """Exact-byte import graph; never resolves an application module on sys.path.

    Private module names exist only for Python's dataclass machinery. All project
    imports execute the previously checked bytes through the same closed loader.
    The reviewed interpreter/stdlib remain part of the trusted operator runtime.
    """

    def __init__(self, root: str, pins: dict[str, str]):
        self.root = recovery._path(root)
        self.pins = copy.deepcopy(pins)
        self.raw: dict[str, bytes] = {}
        self.modules: dict[str, types.ModuleType] = {}
        self.identities: dict[str, dict[str, Any]] = {}
        self.constants: dict[str, dict[str, Any]] = {}
        self.prefix = "_fga_recovery_" + uuid.uuid4().hex
        self.package = types.ModuleType(self.prefix)
        self.package.__path__ = []
        sys.modules[self.prefix] = self.package
        for name, pin in self.pins.items():
            path = recovery._path(name)
            recovery._text(pin, r"[a-f0-9]{64}")
            raw = _source_bytes(Path(name))
            if recovery.digest(raw) != pin:
                raise recovery.Refused("operator_source_pin_mismatch")
            if path.is_relative_to(self.root) and path.suffix == ".py":
                self.raw[".".join(path.relative_to(self.root).with_suffix("").parts)] = raw

    def recheck(self) -> None:
        for path, pin in self.pins.items():
            if recovery.digest(_source_bytes(Path(path))) != pin:
                raise recovery.Refused("operator_source_pin_mismatch")
        for name, frozen in self.identities.items():
            module = self.modules[name]
            _loaded_code(
                module,
                self.raw[name],
                {
                    (self.root / (key.replace(".", "/") + ".py")).as_posix(): raw
                    for key, raw in self.raw.items()
                },
            )
            if set(module.__dict__) != set(frozen) or any(
                module.__dict__[key] is not value for key, value in frozen.items()
            ):
                raise recovery.Refused("operator_loaded_module_changed")
            if self.constants[name] != {
                key: value
                for key, value in vars(module).items()
                if key.isupper() and not key.startswith("_")
            }:
                raise recovery.Refused("operator_loaded_constants_changed")

    def _import(self, name, globals=None, locals=None, fromlist=(), level=0):
        if level:
            if level != 1:
                raise recovery.Refused("operator_import_not_pinned")
            name = "scripts" + ("." + name if name else "")
        if name == "scripts":
            for item in fromlist:
                if item == "*":
                    raise recovery.Refused("operator_import_not_pinned")
                setattr(self.package, item, self.load("scripts." + item))
            return self.package
        if name.startswith("scripts."):
            module = self.load(name)
            return module if fromlist else self.package
        if name.split(".")[0] not in sys.stdlib_module_names and name != "__future__":
            raise recovery.Refused("operator_nonstdlib_import_refused")
        return builtins.__import__(name, globals, locals, fromlist, level)

    def load(self, name: str) -> types.ModuleType:
        if name in self.modules:
            return self.modules[name]
        if name not in self.raw:
            raise recovery.Refused("operator_import_not_pinned")
        path = (self.root / (name.replace(".", "/") + ".py")).as_posix()
        if recovery.digest(self.raw[name]) != self.pins[path]:
            raise recovery.Refused("operator_import_bytes_changed")
        module = types.ModuleType(self.prefix + "." + name)
        module.__file__, module.__package__ = path, "scripts"
        module.__dict__["__builtins__"] = vars(builtins) | {"__import__": self._import}
        self.modules[name] = module
        sys.modules[module.__name__] = module
        try:
            exec(compile(self.raw[name], path, "exec", dont_inherit=True), module.__dict__)
        except BaseException:
            self.modules.pop(name, None)
            sys.modules.pop(module.__name__, None)
            raise
        self.identities[name] = dict(module.__dict__)
        self.constants[name] = copy.deepcopy(
            {
                key: value
                for key, value in vars(module).items()
                if key.isupper() and not key.startswith("_")
            }
        )
        return module


class Operator:
    """One reviewed request, exact roles and ordinary retained evidence bindings.

    Construction only checks source and request bytes. All protected inspection,
    namespace writing and dispatch require the primary's explicit method call.
    """

    def __init__(self, raw: bytes, *, facts: ReviewedFacts):
        self.facts = copy.deepcopy(facts)
        self.req = recovery._request(raw, facts.request_digest)
        self.raw = raw
        original = facts.original_manifest
        if (
            type(original) is not OriginalManifestBinding
            or original.source_root != self.req["sourceRoot"]
            or original.sha2_256 != self.req["pins"]["sourceManifest"]
            or type(original.source_pins) is not dict
            or not original.source_pins
            or any(
                original.source_pins.get(name) != pin
                for name, pin in facts.producer_source_pins.items()
            )
            or type(original.provenance) is not EvidenceRef
        ):
            raise recovery.Refused("operator_original_manifest_provenance_required")
        recovery._text(original.source_commit, r"[a-f0-9]{40}")
        recovery._text(original.sha2_256, r"[a-f0-9]{64}")
        recovery._text(original.provenance.sha2_256, r"[a-f0-9]{64}")
        if (
            set(facts.original_pins) != recovery.HISTORY
            or set(facts.current_pins) != recovery.CURRENT
            or set(facts.fact_evidence) != FACTS
            or facts.original_pins | facts.current_pins != self.req["pins"]
        ):
            raise recovery.Refused("operator_independent_evidence_bindings_required")
        own_path = Path(__file__).as_posix()
        expected = {
            (recovery._path(self.req["sourceRoot"]) / name).as_posix(): pin
            for name, pin in facts.producer_source_pins.items()
        }
        for path in (own_path, self.req["controllerSource"]):
            if path not in self.req["sourcePins"]:
                raise recovery.Refused("operator_own_source_pin_required")
            expected[path] = self.req["sourcePins"][path]
        manifest_path = self.req["roles"]["sourceManifest"]
        if manifest_path in self.req["sourcePins"]:
            expected[manifest_path] = original.sha2_256
        if expected != self.req["sourcePins"]:
            raise recovery.Refused("operator_complete_source_binding_required")
        # Source bytes are checked before any application import/protected read.
        self.sources = PinnedSources(self.req["sourceRoot"], self.req["sourcePins"])
        _loaded_code(sys.modules[__name__], _source_bytes(Path(own_path)), ambient=True)
        _loaded_code(recovery, _source_bytes(Path(self.req["controllerSource"])), ambient=True)
        paths = [recovery._path(p) for p in self.req["roles"].values()]
        paths += [recovery._path(p) for p in self.req["sourcePins"]]
        paths += [recovery._path(self.req[k]) for k in ("namespace", "oldNamespace", "sourceRoot")]
        provenance = recovery._path(original.provenance.path)
        if any(
            provenance == path or provenance.is_relative_to(path) or path.is_relative_to(provenance)
            for path in paths
        ):
            raise recovery.Refused("operator_manifest_provenance_alias_refused")
        paths.append(provenance)
        fact_refs = {}
        for ref in facts.fact_evidence.values():
            path = recovery._path(ref.path)
            recovery._text(ref.sha2_256, r"[a-f0-9]{64}")
            if fact_refs.get(ref.path) == ref.sha2_256:
                continue
            if any(
                path == other or path.is_relative_to(other) or other.is_relative_to(path)
                for other in paths
            ):
                raise recovery.Refused("operator_fact_role_alias_refused")
            paths.append(path)
            fact_refs[ref.path] = ref.sha2_256
        self._execution = None
        self._producer = None
        self._reserved = False
        self._written: set[str] = set()
        self._fact_inventory: dict[str, tuple[int, int]] = {}
        self._file_inventory: dict[str, tuple[int, int]] = {}

    def _read_source_manifest(self, limit: int) -> bytes:
        """One exact PUBLIC role, stable source reader; no private ACL assertion."""
        path = self.req["roles"]["sourceManifest"]
        info = _regular(Path(path))
        if (
            self._file_inventory.get(path) != (info.st_dev, info.st_ino)
            or not 0 < info.st_size <= limit
        ):
            raise recovery.Refused("operator_manifest_inventory_changed")
        raw = _source_bytes(Path(path))
        final = _regular(Path(path))
        original = self.facts.original_manifest
        if (
            original is None
            or (final.st_dev, final.st_ino) != self._file_inventory[path]
            or recovery.digest(raw) != original.sha2_256
            or recovery.source_manifest(raw)["sources"] != original.source_pins
        ):
            raise recovery.Refused("operator_original_manifest_changed")
        return raw

    def _helpers(self):
        if self._execution is None:
            self._execution = self.sources.load("scripts.hosted_publisher_execution")
        return self._execution

    def _private(self, path: str, *, directory: bool = False):
        _regular(Path(path), directory=directory)
        self._helpers()._assert_private(Path(path), directory=directory)
        if not directory:
            self._helpers()._assert_private(Path(path).parent, directory=True)

    def _read(self, path: str, maximum: int) -> bytes:
        self._private(path)
        info = _regular(Path(path))
        if self._file_inventory.get(path) != (info.st_dev, info.st_ino):
            raise recovery.Refused("operator_inventory_identity_changed")
        raw = self._helpers()._private_bytes(Path(path), maximum)
        final = _regular(Path(path))
        if (final.st_dev, final.st_ino) != self._file_inventory[path]:
            raise recovery.Refused("operator_inventory_identity_changed")
        return raw

    def inventory(self, roles: dict[str, str], namespace: str) -> dict[str, recovery.RoleState]:
        if roles != self.req["roles"] or namespace != self.req["namespace"]:
            raise recovery.Refused("operator_exact_roles_required")
        original = self.facts.original_manifest
        if original is None:
            raise recovery.Refused("operator_original_manifest_provenance_required")
        result = {}
        # Stat/link inventory precedes project imports and private content reads.
        entries = (
            roles
            | {"namespace": namespace}
            | {"fact:" + role: ref.path for role, ref in self.facts.fact_evidence.items()}
            | {"manifestProvenance": original.provenance.path}
        )
        seen_facts = set()
        unique_entries = {}
        for role, path in entries.items():
            if role.startswith("fact:"):
                if path in seen_facts:
                    continue
                seen_facts.add(path)
            unique_entries[role] = path
        entries = unique_entries
        for path in entries.values():
            recovery._path(path)
            for ancestor in (Path(path), *Path(path).parents):
                if ancestor.is_symlink() or ancestor.is_junction():
                    raise recovery.Refused("operator_link_or_ancestor_refused")
                try:
                    info = ancestor.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise recovery.Refused("operator_reparse_refused")
        for role, value in entries.items():
            path = Path(value)
            if not path.exists():
                parent = path.parent
                while not parent.exists() and parent != parent.parent:
                    parent = parent.parent
                if role == "sourceManifest":
                    _regular(parent, directory=True)
                else:
                    self._private(parent.as_posix(), directory=True)
                if role.startswith("fact:") or role == "manifestProvenance":
                    raise recovery.Refused("operator_fact_evidence_missing")
                result[role] = recovery.RoleState(
                    False, None, role != "sourceManifest", False, 0, False
                )
                continue
            if role == "sourceManifest":
                info = _regular(path)
            else:
                self._private(value, directory=role == "namespace")
                info = path.stat()
            self._file_inventory[value] = (info.st_dev, info.st_ino)
            if role.startswith("fact:"):
                self._fact_inventory[value] = (info.st_dev, info.st_ino)
            result[role] = recovery.RoleState(
                True,
                f"{info.st_dev}:{info.st_ino}",
                role != "sourceManifest",
                stat.S_ISREG(info.st_mode),
                info.st_nlink,
                False,
            )
        identities = [s.identity for s in result.values() if s.exists]
        if len(identities) != len(set(identities)):
            raise recovery.Refused("operator_file_identity_alias_refused")
        return {
            role: state
            for role, state in result.items()
            if not role.startswith("fact:") and role != "manifestProvenance"
        }

    def source_closure(self, pins: dict[str, str]) -> None:
        if pins != self.req["sourcePins"]:
            raise recovery.Refused("operator_source_binding_changed")
        self.sources.recheck()
        _loaded_code(sys.modules[__name__], _source_bytes(Path(__file__)), ambient=True)
        _loaded_code(recovery, _source_bytes(Path(self.req["controllerSource"])), ambient=True)

    def read_metadata(self, role: str, path: str, limit: int) -> bytes:
        if (
            role
            not in recovery.HISTORY
            | recovery.CURRENT
            | {"plan", "approval", "binding", "packetReview"}
            or self.req["roles"].get(role) != path
            or type(limit) is not int
            or not 0 < limit <= 16777216
        ):
            raise recovery.Refused("operator_metadata_role_refused")
        if role == "sourceManifest":
            return self._read_source_manifest(limit)
        return self._read(path, limit)

    def original_latch(self, journal: str, plan_digest: str, child_id: str) -> dict:
        if (journal, plan_digest, child_id) != (
            self.req["roles"]["issuerJournal"],
            self.req["pins"]["issuerPlan"],
            self.req["childId"],
        ):
            raise recovery.Refused("operator_exact_original_latch_required")
        for role in ("issuerRollback", "issuerWal", "issuerShm"):
            if Path(self.req["roles"][role]).exists():
                raise recovery.Refused("operator_original_sidecar_refused")
        # Deserialize a bounded stable private read. No live database connection,
        # owner acquisition, journal/sidecar creation, write, repair or discovery.
        raw = self._read(journal, 16777216)
        with contextlib.closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(raw)
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            if db.execute("SELECT digest FROM meta").fetchall() != [(plan_digest,)]:
                raise recovery.Refused("operator_original_digest_mismatch")
            rows = db.execute(
                "SELECT state,receipt FROM intents WHERE key='issuer:mutation'"
            ).fetchall()
            if (
                len(rows) != 1
                or rows[0][0] != "complete"
                or recovery.document(rows[0][1].encode()).get("childId") != child_id
            ):
                raise recovery.Refused("operator_original_child_mismatch")
            retired = db.execute("SELECT state FROM intents WHERE key='issuer:retire'").fetchall()
        return {
            "key": "issuer:retire",
            "planDigest": plan_digest,
            "childId": child_id,
            # Absence alone is unused. Even a malformed existing row whose state
            # literally says 'unused' occupies the original single-use latch.
            "state": "unused" if not retired else "occupied",
        }

    def authenticate(self, kind: str, context: bytes, records: dict[str, bytes]) -> None:
        if context != self.raw or kind not in {"historical", "current", "dispatch"}:
            raise recovery.Refused("operator_evidence_context_refused")
        required = (
            recovery.HISTORY
            if kind == "historical"
            else (
                recovery.HISTORY | recovery.CURRENT
                if kind == "current"
                else recovery.CURRENT | {"packetReview"}
            )
        )
        if set(records) != required:
            raise recovery.Refused("operator_complete_evidence_required")
        expected = self.facts.original_pins if kind == "historical" else self.req["pins"]
        for role, raw in records.items():
            if role == "packetReview" and kind == "dispatch":
                ref = self.facts.packet_review
                if (
                    ref is None
                    or ref.path != self.req["roles"][role]
                    or recovery.digest(raw) != ref.sha2_256
                ):
                    raise recovery.Refused("operator_authenticated_packet_review_required")
            elif expected.get(role) != recovery.digest(raw):
                raise recovery.Refused("operator_authenticated_evidence_required")
        if kind in {"historical", "current"}:
            original = self.facts.original_manifest
            if (
                original is None
                or recovery.document(records["issuerPlan"])["source_commit"]
                != original.source_commit
            ):
                raise recovery.Refused("operator_original_manifest_commit_mismatch")
            self._read_source_manifest(16777216)
            if (
                recovery.digest(self._read(original.provenance.path, 16777216))
                != original.provenance.sha2_256
            ):
                raise recovery.Refused("operator_original_manifest_provenance_changed")
        if kind != "historical":
            if recovery.document(records["witness"])["evidenceReference"] != fact_reference(
                self.facts.fact_evidence
            ):
                raise recovery.Refused("operator_fact_reference_not_bound")
            if set(self._fact_inventory) != {ref.path for ref in self.facts.fact_evidence.values()}:
                raise recovery.Refused("operator_fact_inventory_required")
            for ref in self.facts.fact_evidence.values():
                info = _regular(Path(ref.path))
                if (info.st_dev, info.st_ino) != self._fact_inventory[ref.path]:
                    raise recovery.Refused("operator_fact_identity_changed")
                if recovery.digest(self._read(ref.path, 16777216)) != ref.sha2_256:
                    raise recovery.Refused("operator_current_fact_evidence_changed")

    def reserve_exclusive(self, path: str) -> None:
        if path != self.req["namespace"] or self._reserved:
            raise recovery.Refused("operator_exact_new_namespace_required")
        self._private(Path(path).parent.as_posix(), directory=True)
        os.mkdir(path, 0o700)
        self._reserved = True
        self._private(path, directory=True)

    def create_exclusive(self, path: str, raw: bytes) -> int:
        if (
            not self._reserved
            or path in self._written
            or path not in {self.req["roles"][role] for role in ("plan", "approval", "binding")}
        ):
            raise recovery.Refused("operator_exact_new_metadata_required")
        self._written.add(path)  # Failure permanently spends this local writer.
        self._private(self.req["namespace"], directory=True)
        metadata = self.sources.load("scripts.collect_publisher_grant_metadata")
        metadata._create_private(Path(path), raw)
        info = _regular(Path(path))
        self._file_inventory[path] = (info.st_dev, info.st_ino)
        if self._read(path, 16777216) != raw:
            raise recovery.Refused("operator_partial_preparation_preserved")
        return len(raw)

    def producer(self) -> types.ModuleType:
        self.source_closure(self.req["sourcePins"])
        if self._producer is None:
            self._producer = self.sources.load("scripts.provision_work_plan_token")
        expected = {
            (self.sources.root / name).as_posix() for name in self._producer.SOURCE_FILES
        } | {self.req["controllerSource"], Path(__file__).as_posix()}
        if self.req["roles"]["sourceManifest"] in self.req["sourcePins"]:
            expected.add(self.req["roles"]["sourceManifest"])
        if set(self.req["sourcePins"]) != expected:
            raise recovery.Refused("operator_complete_source_closure_required")
        self.sources.recheck()
        return self._producer

    def credential_loader(self, path: Path, maximum: int) -> bytes:
        if path.as_posix() != self.req["roles"]["parentCredential"] or maximum != 2048:
            raise recovery.Refused("operator_exact_parent_role_required")
        return self._read(path.as_posix(), maximum)

    def dispatch(self, packet, *, packet_review: bytes, clock, monotonic, execute=False):
        if execute is not True:
            raise recovery.Refused("inert_default")
        # Authenticate actual packet/current facts and unused latch before loading
        # the producer; the controller repeats these gates immediately before run.
        rebuilt = recovery._prepare(
            self.raw,
            expected_digest=self.facts.request_digest,
            verifier=self,
            now=clock(),
            prepared=True,
        )
        if rebuilt != packet:
            raise recovery.Refused("final_packet_drift")
        current = {
            role: self.read_metadata(role, self.req["roles"][role], 16777216)
            for role in recovery.CURRENT
        }
        self.authenticate("dispatch", self.raw, current | {"packetReview": packet_review})
        producer = self.producer()
        return recovery.dispatch(
            packet,
            expected_digest=self.facts.request_digest,
            verifier=self,
            producer=producer,
            packet_review=packet_review,
            clock=clock,
            monotonic=monotonic,
            # Explicit deterministic selection of the verified producer's ORIGINAL
            # TLS branch. Its own numeric parsing and closed-over send-stage fence
            # must stay together; a one-argument wrapper would lose that fence.
            # The required argument is supplied, not omitted or ambiently resolved.
            transport=None,
            credential_loader=self.credential_loader,
            execute=True,
        )


def main() -> None:
    raise SystemExit("NO-GO: Primary must bind authentic evidence and explicitly invoke adapters.")


if __name__ == "__main__":
    main()
