"""Isolated #0189 path-policy extension; unchanged #0183 source stays pinned.

Metadata, chain and held-parent rules below retain #0183 semantics verbatim;
only role_path admits the documented ordinary .coordination-runs component.
No path is rewritten and no reviewed-module global or source is modified.
Inherited security, source and protected-new-file qualification use these
virtual methods with the actual held-node paths.
"""

from __future__ import annotations

from pathlib import PureWindowsPath

import bounded_local_delivery_path_proof as proof
from bounded_local_delivery_path_proof import (
    DIRECTORY_ACCESS,
    DIRECTORY_FLAGS,
    FILE_SHARE_READ,
    OPEN_EXISTING,
    ORDINARY_HOST,
    ModelPremises,
    Node,
    Refused,
)


def role_path(value: str) -> PureWindowsPath:
    # Exactly one extra conventional component, not a general dot-file escape.
    # Base validation still rejects dot/dot-dot, ADS, devices, reserved names,
    # trailing dots/spaces, slashes, empty components and normalization aliases.
    if not isinstance(value, str):
        raise Refused("fixed_path_refused")
    if value == "C:\\":
        return proof.fixed_path(value)
    if not value.startswith("C:\\"):
        raise Refused("fixed_path_refused")
    for component in value[3:].split("\\"):
        if not component:
            raise Refused("fixed_path_refused")
        if component != ".coordination-runs":
            proof.fixed_path("C:\\" + component)
    return PureWindowsPath(value)


class RolePolicy(proof.Policy):
    def _metadata(self, node: Node):
        role_path(node.path)
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
            path = role_path(node.path)
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
            role_path(node.path).parent != role_path(parent.path)
            or node.handle_id[0] != parent.handle_id[0]
            or node.handle_id in {item.handle_id for item in parents}
        ):
            raise Refused("held_parent_required")
