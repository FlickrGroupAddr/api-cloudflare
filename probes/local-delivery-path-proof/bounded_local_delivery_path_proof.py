"""#0183 source-only Windows custody model; deliberately has no apply adapter.

All inputs are synthetic observations, NOT OS evidence. No function opens a file,
reads a credential, loads the old helper, changes ACLs, or dispatches a native
operation. A model PASS is conditional on its explicit history premise. main()
always refuses live action. See 0183-path-proof.md for the Win32 proof boundary.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import PureWindowsPath

FILE_LIST_DIRECTORY = 0x0001
FILE_ADD_FILE = 0x0002
FILE_ADD_SUBDIRECTORY = 0x0004
FILE_WRITE_EA = 0x0010
FILE_DELETE_CHILD = 0x0040
FILE_READ_ATTRIBUTES = 0x0080
FILE_WRITE_ATTRIBUTES = 0x0100
DELETE = 0x00010000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
WRITE_OWNER = 0x00080000
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
GENERIC_ALL = 0x10000000
FILE_SHARE_READ = 1
CREATE_NEW = 1
OPEN_EXISTING = 3
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
DIRECTORY_ACCESS = READ_CONTROL | FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY
DIRECTORY_FLAGS = FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
# ADD_FILE / ADD_SUBDIRECTORY are deliberately absent. Their write-data/append
# equivalents participate in sharing; WRITE_ATTRIBUTES and WRITE_EA do not.
ANCESTOR_MUTATION = (
    FILE_WRITE_EA
    | FILE_DELETE_CHILD
    | FILE_WRITE_ATTRIBUTES
    | DELETE
    | WRITE_DAC
    | WRITE_OWNER
    | GENERIC_WRITE
    | GENERIC_ALL
)
SYSTEM = "S-1-5-18"
ADMINISTRATORS = "S-1-5-32-544"
TRUSTEDINSTALLER = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
_SID = re.compile(r"S-1-(?:[0-9]+-)+[0-9]+\Z")
_COMPONENT = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\Z")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class Refused(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Ace:
    kind: str
    sid: str
    mask: int
    inherit_only: bool = False


@dataclass(frozen=True)
class Node:
    path: str
    owner: str
    aces: tuple[Ace, ...] | None
    directory: bool = True
    reparse: bool = False
    disk: bool = True
    links: int = 1
    desired_access: int = DIRECTORY_ACCESS
    share_mode: int = FILE_SHARE_READ
    protected_dacl: bool = False
    handle_id: tuple[int, int] = (1, 1)
    held: bool = True
    metadata_by_handle: bool = True
    security_by_handle: bool = True
    flags: int = DIRECTORY_FLAGS
    disposition: int = OPEN_EXISTING
    creation_security_at_open: bool = False


@dataclass(frozen=True)
class ModelPremises:
    # Explicit ordinary trusted-host boundary, NOT new runtime/owner gates.
    # A DACL snapshot cannot infer prior-handle history. The model excludes an
    # adversary retaining metadata/security handles from formerly trusted access,
    # a compromised current user/OS, or a changed DOS device mapping.
    no_untrusted_prior_attribute_or_security_handles: bool = True
    trusted_current_user_and_privileged_os: bool = True
    ordinary_local_ntfs: bool = True
    stable_dos_device_mapping: bool = True


ORDINARY_HOST = ModelPremises()


def fixed_path(value: str) -> PureWindowsPath:
    """Accept the conventional spelling used by fixed C: call-site constants.

    This deliberately refuses UNC, device, extended, relative, ADS, dot, wildcard,
    reserved and normalization-dependent spellings. It does no filesystem lookup.
    """
    if not isinstance(value, str) or not value.startswith("C:\\") or "/" in value:
        raise Refused("fixed_path_refused")
    if value == "C:\\":
        return PureWindowsPath(value)
    parts = value[3:].split("\\")
    if any(
        not _COMPONENT.fullmatch(part) or part.split(".")[0].upper() in _RESERVED for part in parts
    ):
        raise Refused("fixed_path_refused")
    return PureWindowsPath(value)


def _sid(value: str) -> bool:
    return isinstance(value, str) and bool(_SID.fullmatch(value))


@dataclass(frozen=True)
class Policy:
    current_user_sid: str
    trustedinstaller_sid: str

    def __post_init__(self):
        if not _sid(self.current_user_sid) or self.trustedinstaller_sid != TRUSTEDINSTALLER:
            raise Refused("identity_binding_refused")

    @property
    def trusted(self) -> frozenset[str]:
        # Current user is one concrete user SID, never Everyone/Users/Authenticated
        # Users or a general service-SID wildcard.
        if not self.current_user_sid.startswith("S-1-5-21-"):
            raise Refused("identity_binding_refused")
        return frozenset((self.current_user_sid, SYSTEM, ADMINISTRATORS))

    def _security(self, node: Node, *, private: bool):
        principals = self.trusted | (
            {TRUSTEDINSTALLER} if node.path == "C:\\" and not private else set()
        )
        owner_ok = node.owner in self.trusted or (
            not private and node.path == "C:\\" and node.owner == TRUSTEDINSTALLER
        )
        if not owner_ok or not isinstance(node.aces, tuple):
            raise Refused("owner_or_dacl_refused")
        if private and not node.protected_dacl:
            raise Refused("private_dacl_unprotected")
        for ace in node.aces:
            if (
                not isinstance(ace, Ace)
                or ace.kind not in {"allow", "deny"}
                or not _sid(ace.sid)
                or type(ace.mask) is not int
                or not 0 <= ace.mask <= 0xFFFFFFFF
                or ace.mask & ~0xF01F01FF
                or type(ace.inherit_only) is not bool
            ):
                raise Refused("acl_form_refused")
            if ace.inherit_only or ace.kind == "deny" or ace.sid in principals:
                continue
            # Deny ACEs never excuse an unsafe allow: no effective-access or
            # group-membership approximation is used. Unknown ACE forms refuse.
            if ace.mask & (0xFFFFFFFF if private else ANCESTOR_MUTATION):
                raise Refused("private_access_refused" if private else "ancestor_mutation_refused")

    def _metadata(self, node: Node):
        fixed_path(node.path)
        if any(
            type(getattr(node, name)) is not bool
            for name in (
                "held",
                "metadata_by_handle",
                "security_by_handle",
                "disk",
                "reparse",
                "directory",
                "protected_dacl",
                "creation_security_at_open",
            )
        ) or any(
            type(getattr(node, name)) is not int
            for name in ("links", "desired_access", "share_mode", "flags", "disposition")
        ):
            raise Refused("metadata_form_refused")
        if not node.held or not node.metadata_by_handle or not node.security_by_handle:
            raise Refused("held_handle_evidence_required")
        if not node.disk or node.reparse:
            raise Refused("ordinary_disk_object_required")
        if (
            not isinstance(node.handle_id, tuple)
            or len(node.handle_id) != 2
            or any(type(item) is not int or item <= 0 for item in node.handle_id)
        ):
            raise Refused("object_identity_required")

    def qualify_chain(
        self,
        nodes: tuple[Node, ...],
        *,
        private_from: int | None = None,
        premises: ModelPremises = ORDINARY_HOST,
    ) -> tuple[tuple[int, int], ...]:
        """Conditional finite model only; caller-supplied observations are untrusted
        as real evidence. nodes must include every directory from C: in open order.
        A real adapter must hold each parent BEFORE resolving its immediate child.
        """
        if (
            not isinstance(nodes, tuple)
            or not nodes
            or any(not isinstance(node, Node) for node in nodes)
        ):
            raise Refused("complete_chain_required")
        if not isinstance(premises, ModelPremises) or any(
            type(getattr(premises, name)) is not bool for name in ModelPremises.__dataclass_fields__
        ):
            raise Refused("premise_form_refused")
        if private_from is not None and (
            type(private_from) is not int or not 0 <= private_from < len(nodes)
        ):
            raise Refused("private_boundary_refused")
        seen: set[tuple[int, int]] = set()
        previous: PureWindowsPath | None = None
        for index, node in enumerate(nodes):
            self._metadata(node)
            path = fixed_path(node.path)
            if (previous is None and node.path != "C:\\") or (
                previous is not None and (path == previous or path.parent != previous)
            ):
                raise Refused("complete_chain_required")
            if (
                not node.directory
                or node.disposition != OPEN_EXISTING
                or node.desired_access != DIRECTORY_ACCESS
                or node.share_mode != FILE_SHARE_READ
                or node.flags != DIRECTORY_FLAGS
            ):
                raise Refused("participating_directory_guard_required")
            if node.handle_id in seen or (seen and node.handle_id[0] != nodes[0].handle_id[0]):
                raise Refused("local_distinct_directory_identity_required")
            self._security(node, private=private_from is not None and index >= private_from)
            seen.add(node.handle_id)
            previous = path
        if not premises.no_untrusted_prior_attribute_or_security_handles:
            raise Refused("prior_handle_history_unproved")
        if not premises.trusted_current_user_and_privileged_os:
            raise Refused("principal_trust_unestablished")
        if not premises.ordinary_local_ntfs or not premises.stable_dos_device_mapping:
            raise Refused("local_namespace_premise_unestablished")
        return tuple(node.handle_id for node in nodes)

    def _private_parent(self, node: Node, parents: tuple[Node, ...], premises: ModelPremises):
        self.qualify_chain(parents, private_from=len(parents) - 1, premises=premises)
        parent = parents[-1]
        if (
            fixed_path(node.path).parent != fixed_path(parent.path)
            or node.handle_id[0] != parent.handle_id[0]
            or node.handle_id in {item.handle_id for item in parents}
        ):
            raise Refused("held_parent_required")

    def qualify_source(
        self, node: Node, parents: tuple[Node, ...], *, premises: ModelPremises = ORDINARY_HOST
    ):
        """Model source handle qualification; no read function exists here."""
        self._metadata(node)
        if (
            node.directory
            or node.links != 1
            or node.share_mode != 0
            or node.desired_access != GENERIC_READ
            or node.disposition != OPEN_EXISTING
            or node.flags != FILE_FLAG_OPEN_REPARSE_POINT
        ):
            raise Refused("exclusive_single_link_source_required")
        self._private_parent(node, parents, premises)
        self._security(node, private=True)

    def qualify_new_file(
        self, node: Node, parents: tuple[Node, ...], *, premises: ModelPremises = ORDINARY_HOST
    ):
        """Model CREATE_NEW with protected security supplied AT creation.

        No path existence precheck may authorize overwrite. CREATE_NEW failure
        is refusal; a winner cannot be reused. The returned handle stays held.
        """
        self._metadata(node)
        if (
            node.directory
            or node.links != 1
            or node.share_mode != 0
            or node.desired_access != (GENERIC_WRITE | READ_CONTROL | FILE_READ_ATTRIBUTES)
            or node.disposition != CREATE_NEW
            or node.flags != FILE_FLAG_OPEN_REPARSE_POINT
            or not node.creation_security_at_open
        ):
            raise Refused("exclusive_new_file_required")
        self._private_parent(node, parents, premises)
        self._security(node, private=True)


@dataclass(frozen=True)
class Window:
    start_utc: float
    end_utc: float
    started_monotonic: float
    previous_utc: float
    previous_monotonic: float

    def before_dispatch(self, utc: float, monotonic: float) -> Window:
        """Synthetic dispatch admission, never a timer/authority or OS call."""
        values = (
            self.start_utc,
            self.end_utc,
            self.started_monotonic,
            self.previous_utc,
            self.previous_monotonic,
            utc,
            monotonic,
        )
        if (
            any(type(value) not in {float, int} or not math.isfinite(value) for value in values)
            or not 0 < self.end_utc - self.start_utc <= 900
            or not self.start_utc <= self.previous_utc <= utc < self.end_utc
            or not self.started_monotonic <= self.previous_monotonic <= monotonic
            or monotonic - self.started_monotonic >= self.end_utc - self.start_utc
        ):
            raise Refused("window_closed")
        return Window(self.start_utc, self.end_utc, self.started_monotonic, utc, monotonic)


def main() -> int:
    print(
        json.dumps(
            {
                "outcome": "NO_APPLY_source_model_only",
                "credential_reads": 0,
                "credential_delivered": False,
                "actionReady": False,
                "ownerConsent": False,
                "nativeConsent": False,
            },
            sort_keys=True,
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
