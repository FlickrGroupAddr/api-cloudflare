"""Finite model tests only; no native path, ACL, credential or byte-reader access."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from dataclasses import replace

import bounded_local_delivery_path_proof as proof

USER = "S-1-5-21-100-200-300-1001"
OTHER = "S-1-5-21-100-200-300-1002"
PREMISES = proof.ModelPremises(True, True, True, True)


def chain() -> tuple[proof.Node, ...]:
    """Entirely invented names and observations, never resolved or opened."""
    return (
        proof.Node("C:\\", USER, (), handle_id=(1, 10)),
        proof.Node("C:\\synthetic", USER, (), handle_id=(1, 11)),
        proof.Node("C:\\synthetic\\private", USER, (), handle_id=(1, 12), protected_dacl=True),
    )


class PathPolicyTests(unittest.TestCase):
    """Test independent security expectations against supplied model observations."""

    def setUp(self) -> None:
        self.policy = proof.Policy(USER, proof.TRUSTEDINSTALLER)

    def refused(self, nodes: tuple[proof.Node, ...], **kwargs: object) -> None:
        with self.assertRaises(proof.Refused):
            self.policy.qualify_chain(nodes, **kwargs)

    def test_ordinary_trust_model_is_conditional_on_each_premise(self) -> None:
        for name in PREMISES.__dataclass_fields__:
            with self.subTest(premise=name):
                self.refused(chain(), premises=replace(PREMISES, **{name: False}))
        self.assertEqual(
            self.policy.qualify_chain(chain(), premises=PREMISES),
            ((1, 10), (1, 11), (1, 12)),
        )

    def test_unknown_metadata_and_premises_refuse(self) -> None:
        self.refused(("unknown",), premises=PREMISES)
        for field in ("held", "metadata_by_handle", "security_by_handle", "disk", "directory"):
            with self.subTest(field=field):
                nodes = list(chain())
                nodes[1] = replace(nodes[1], **{field: "unknown"})
                self.refused(tuple(nodes), premises=PREMISES)
        nodes = list(chain())
        nodes[1] = replace(nodes[1], reparse=None)
        self.refused(tuple(nodes), premises=PREMISES)
        for name in PREMISES.__dataclass_fields__:
            with self.subTest(premise=name):
                self.refused(chain(), premises=replace(PREMISES, **{name: "unknown"}))

    def test_fixed_paths_refuse_ambiguous_or_outside_namespace(self) -> None:
        paths = (
            "",
            "relative",
            "C:relative",
            "D:\\synthetic",
            "c:\\synthetic",
            "C:/synthetic",
            "\\\\host\\share",
            "\\\\?\\C:\\synthetic",
            "C:\\synthetic\\..\\private",
            "C:\\synthetic\\.\\private",
            "C:\\synthetic\\",
            "C:\\synthetic\\file:stream",
            "C:\\NUL",
            "C:\\CON.txt",
            "C:\\synthetic. ",
            "C:\\synthetic*",
            "C:\\synthetic\x00",
        )
        for path in paths:
            with self.subTest(path=repr(path)), self.assertRaises(proof.Refused):
                proof.fixed_path(path)

    def test_complete_ordered_local_identity_chain_required(self) -> None:
        nodes = chain()
        cases = (
            (),
            nodes[1:],
            (nodes[0], nodes[2]),
            (nodes[0], replace(nodes[0], handle_id=(1, 99))),
            (nodes[0], replace(nodes[1], handle_id=(1, 10))),
            (nodes[0], replace(nodes[1], handle_id=(2, 11))),
            (replace(nodes[0], handle_id=(0, 10)),),
            (replace(nodes[0], handle_id=(True, 10)),),
        )
        for case in cases:
            with self.subTest(case=case):
                self.refused(case, premises=PREMISES)

    def test_each_handle_requires_observed_held_participating_directory(self) -> None:
        bad_fields = {
            "held": False,
            "metadata_by_handle": False,
            "security_by_handle": False,
            "directory": False,
            "reparse": True,
            "disk": False,
            "desired_access": 0x20080,
            "share_mode": 3,
            "flags": 0,
            "disposition": proof.CREATE_NEW,
        }
        for index in range(3):
            for field, value in bad_fields.items():
                with self.subTest(index=index, field=field):
                    nodes = list(chain())
                    nodes[index] = replace(nodes[index], **{field: value})
                    self.refused(tuple(nodes), premises=PREMISES)

    def test_ancestor_read_and_childcreation_differ_from_mutation(self) -> None:
        root, ancestor, private = chain()
        allowed = (0x1, 0x2, 0x4, 0x6, 0x80, 0x20000, 0x80000000)
        for mask in allowed:
            with self.subTest(allowed=hex(mask)):
                observed = replace(ancestor, aces=(proof.Ace("allow", OTHER, mask),))
                self.policy.qualify_chain((root, observed, private), premises=PREMISES)
        for mask in (0x10, 0x40, 0x100, 0x10000, 0x40000, 0x80000, 0x40000000, 0x10000000):
            with self.subTest(rejected=hex(mask)):
                observed = replace(ancestor, aces=(proof.Ace("allow", OTHER, mask),))
                self.refused((root, observed, private), premises=PREMISES)

    def test_denies_never_cancel_unsafe_allow(self) -> None:
        nodes = list(chain())
        nodes[1] = replace(
            nodes[1], aces=(proof.Ace("deny", OTHER, 0x001F01FF), proof.Ace("allow", OTHER, 0x100))
        )
        self.refused(tuple(nodes), premises=PREMISES)

    def test_private_boundary_refuses_any_untrusted_access_and_unprotected_dacl(self) -> None:
        for mask in (0x1, 0x2, 0x4, 0x10, 0x80, 0x100, 0x20000, 0x80000000):
            with self.subTest(mask=hex(mask)):
                nodes = list(chain())
                nodes[2] = replace(nodes[2], aces=(proof.Ace("allow", OTHER, mask),))
                self.refused(tuple(nodes), private_from=2, premises=PREMISES)
        nodes = list(chain())
        nodes[2] = replace(nodes[2], protected_dacl=False)
        self.refused(tuple(nodes), private_from=2, premises=PREMISES)
        for boundary in (-1, 3, True, "2"):
            with self.subTest(boundary=boundary):
                self.refused(chain(), private_from=boundary, premises=PREMISES)

    def test_identity_owner_and_acl_forms_closed(self) -> None:
        for sid in ("S-1-1-0", "S-1-5-32-545", "bad"):
            with self.subTest(sid=sid), self.assertRaises(proof.Refused):
                policy = proof.Policy(sid, proof.TRUSTEDINSTALLER)
                policy.qualify_chain(chain(), premises=PREMISES)
        for aces in (
            None,
            (proof.Ace("callback", OTHER, 1),),
            (proof.Ace("allow", "bad", 1),),
            (proof.Ace("allow", OTHER, True),),
            (proof.Ace("allow", OTHER, -1),),
            (proof.Ace("allow", OTHER, 1 << 32),),
            (proof.Ace("allow", OTHER, 0x0200),),
            ("unknown",),
        ):
            with self.subTest(aces=aces):
                nodes = list(chain())
                nodes[1] = replace(nodes[1], aces=aces)
                self.refused(tuple(nodes), premises=PREMISES)
        nodes = list(chain())
        nodes[1] = replace(nodes[1], owner=proof.TRUSTEDINSTALLER)
        self.refused(tuple(nodes), premises=PREMISES)
        nodes[1] = replace(nodes[1], owner=OTHER)
        self.refused(tuple(nodes), premises=PREMISES)

    def test_trustedinstaller_exception_is_root_only(self) -> None:
        nodes = list(chain())
        nodes[0] = replace(
            nodes[0],
            owner=proof.TRUSTEDINSTALLER,
            aces=(proof.Ace("allow", proof.TRUSTEDINSTALLER, 0x10000000),),
        )
        self.policy.qualify_chain(tuple(nodes), premises=PREMISES)
        nodes[1] = replace(nodes[1], aces=(proof.Ace("allow", proof.TRUSTEDINSTALLER, 0x100),))
        self.refused(tuple(nodes), premises=PREMISES)


class FileQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = proof.Policy(USER, proof.TRUSTEDINSTALLER)
        self.source = proof.Node(
            "C:\\synthetic\\private\\input.bin",
            USER,
            (),
            directory=False,
            desired_access=proof.GENERIC_READ,
            share_mode=0,
            protected_dacl=True,
            handle_id=(1, 13),
            flags=proof.FILE_FLAG_OPEN_REPARSE_POINT,
        )
        self.output = replace(
            self.source,
            path="C:\\synthetic\\private\\output.bin",
            desired_access=proof.GENERIC_WRITE | proof.READ_CONTROL | proof.FILE_READ_ATTRIBUTES,
            disposition=proof.CREATE_NEW,
            handle_id=(1, 14),
            creation_security_at_open=True,
        )

    def test_source_and_exclusive_newfile_model_accept_known_private_handles(self) -> None:
        self.policy.qualify_source(self.source, chain())
        self.policy.qualify_new_file(self.output, chain())

    def test_whole_parent_chain_requalified_for_each_file(self) -> None:
        for function, node in (
            (self.policy.qualify_source, self.source),
            (self.policy.qualify_new_file, self.output),
        ):
            for index in range(3):
                for field, value in (
                    ("held", False),
                    ("reparse", True),
                    ("directory", False),
                    ("metadata_by_handle", False),
                    ("share_mode", 3),
                    ("aces", (proof.Ace("allow", OTHER, 0x100),)),
                ):
                    with self.subTest(function=function.__name__, index=index, field=field):
                        parents = list(chain())
                        parents[index] = replace(parents[index], **{field: value})
                        with self.assertRaises(proof.Refused):
                            function(node, tuple(parents))

    def test_private_parent_and_file_identity_cannot_be_substituted(self) -> None:
        for function, node in (
            (self.policy.qualify_source, self.source),
            (self.policy.qualify_new_file, self.output),
        ):
            for modified in (
                replace(node, path="C:\\synthetic\\other.bin"),
                replace(node, handle_id=(2, 13)),
                replace(node, handle_id=(1, 12)),
                replace(node, links=2),
                replace(node, reparse=True),
                replace(node, protected_dacl=False),
                replace(node, share_mode=1),
                replace(node, aces=(proof.Ace("allow", OTHER, 1),)),
            ):
                with self.subTest(function=function.__name__, node=modified):
                    with self.assertRaises(proof.Refused):
                        function(modified, chain())
            parents = list(chain())
            parents[-1] = replace(parents[-1], aces=(proof.Ace("allow", OTHER, 1),))
            with self.assertRaises(proof.Refused):
                function(node, tuple(parents))

    def test_existing_file_or_weak_open_cannot_stand_in_for_create_new(self) -> None:
        for field, value in (
            ("disposition", proof.OPEN_EXISTING),
            ("desired_access", proof.GENERIC_WRITE),
            ("flags", 0),
            ("directory", True),
            ("creation_security_at_open", False),
        ):
            with self.subTest(field=field), self.assertRaises(proof.Refused):
                self.policy.qualify_new_file(replace(self.output, **{field: value}), chain())


class WindowAndInertTests(unittest.TestCase):
    def test_effect_boundary_resampling_refuses_expiry_and_rollback(self) -> None:
        window = proof.Window(100, 110, 0, 100, 0)
        admitted = window.before_dispatch(109, 9)
        effects: list[str] = []
        with self.assertRaises(proof.Refused):
            admitted.before_dispatch(110, 9.5)
            effects.append("simulated_dispatch")
        self.assertEqual(effects, [])
        for utc, monotonic in ((108, 9.1), (109, 8), (109.5, 10), (float("nan"), 9)):
            with self.subTest(utc=utc, monotonic=monotonic), self.assertRaises(proof.Refused):
                admitted.before_dispatch(utc, monotonic)

    def test_invalid_or_unbounded_windows_refuse(self) -> None:
        for window in (
            proof.Window(100, 100, 0, 100, 0),
            proof.Window(100, 1001, 0, 100, 0),
            proof.Window(100, float("inf"), 0, 100, 0),
            proof.Window(100, 110, False, 100, 0),
        ):
            with self.subTest(window=window), self.assertRaises(proof.Refused):
                window.before_dispatch(100, 0)

    def test_default_main_has_no_apply_receipt_and_zero_read_accounting(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = proof.main()
        receipt = json.loads(stream.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(receipt["outcome"], "NO_APPLY_source_model_only")
        self.assertEqual(receipt["credential_reads"], 0)
        for name in ("credential_delivered", "actionReady", "ownerConsent", "nativeConsent"):
            self.assertIs(receipt[name], False)


if __name__ == "__main__":
    unittest.main()
