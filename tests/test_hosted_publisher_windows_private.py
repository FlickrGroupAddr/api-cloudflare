"""Windows private ACL checks use empty folders and synthetic security metadata."""

import ctypes
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import hosted_publisher_execution as runtime


class SyntheticWindowsSecurity:
    """Supply native-shaped metadata without changing any filesystem ACL."""

    current = "S-1-5-21-1-2-3-1001"

    def __init__(self, *, owner=None, entries=(), null_dacl=False):
        self.advapi = Mock()
        self.kernel = Mock()
        self.buffers = []
        self.sids = {}
        self.aces = []
        self.owner = self.buffer(1)
        self.token_sid = self.buffer(1)
        self.sids[ctypes.addressof(self.owner)] = owner or self.current
        self.sids[ctypes.addressof(self.token_sid)] = self.current
        self.dacl = self.buffer(8)
        ctypes.c_ushort.from_buffer(self.dacl, 4).value = len(entries)
        for sid, ace_type, flags, mask in entries:
            ace = self.buffer(9)
            ctypes.c_ubyte.from_buffer(ace).value = ace_type
            ctypes.c_ubyte.from_buffer(ace, 1).value = flags
            ctypes.c_uint32.from_buffer(ace, 4).value = mask
            self.sids[ctypes.addressof(ace) + 8] = sid
            self.aces.append(ace)

        def token_information(_token, _kind, info, _size, needed):
            ctypes.cast(needed, ctypes.POINTER(ctypes.c_ulong))[0] = ctypes.sizeof(ctypes.c_void_p)
            if info is None:
                return False
            self.set_pointer(info, ctypes.addressof(self.token_sid))
            return True

        def security_info(_path, _kind, _flags, owner_out, _group, dacl_out, _sacl, out):
            self.set_pointer(owner_out, ctypes.addressof(self.owner))
            self.set_pointer(dacl_out, None if null_dacl else ctypes.addressof(self.dacl))
            self.set_pointer(out, ctypes.addressof(self.dacl))
            return 0

        def sid_text(sid, out):
            address = sid.value if isinstance(sid, ctypes.c_void_p) else sid
            text = ctypes.create_unicode_buffer(self.sids[address])
            self.buffers.append(text)
            self.set_pointer(out, ctypes.addressof(text))
            return True

        def get_ace(_dacl, index, out):
            self.set_pointer(out, ctypes.addressof(self.aces[index]))
            return True

        self.advapi.GetTokenInformation.side_effect = token_information
        self.advapi.GetNamedSecurityInfoW.side_effect = security_info
        self.advapi.ConvertSidToStringSidW.side_effect = sid_text
        self.advapi.GetAce.side_effect = get_ace

    def buffer(self, size):
        result = ctypes.create_string_buffer(size)
        self.buffers.append(result)
        return result

    @staticmethod
    def set_pointer(destination, address):
        ctypes.cast(destination, ctypes.POINTER(ctypes.c_void_p))[0] = address

    def check(self):
        with patch.object(
            ctypes,
            "WinDLL",
            side_effect=lambda name, **_kwargs: {
                "advapi32": self.advapi,
                "kernel32": self.kernel,
            }[name],
            create=True,
        ):
            runtime._windows_private(Path("synthetic-metadata-only"))


class WindowsPrivateMetadataTests(unittest.TestCase):
    def test_owner_rights_is_accepted_for_the_verified_current_owner(self):
        security = SyntheticWindowsSecurity(
            entries=[
                (sid, 0, 0, 0x1F01FF)
                for sid in (SyntheticWindowsSecurity.current, "S-1-3-4", "S-1-5-18", "S-1-5-32-544")
            ]
        )
        security.check()

    def test_owner_rights_does_not_bypass_other_owner_refusal(self):
        security = SyntheticWindowsSecurity(
            owner="S-1-5-21-1-2-3-1002", entries=[("S-1-3-4", 0, 0, 0x1F01FF)]
        )
        with self.assertRaisesRegex(runtime.OperatorRefused, "private_file_owner_or_acl_refused"):
            security.check()
        security.advapi.GetAce.assert_not_called()

    def test_owner_rights_does_not_bypass_broad_allow_refusal(self):
        for sid in ("S-1-1-0", "S-1-5-11", "S-1-5-32-545", "S-1-3-0", "S-1-5-21-1-2-3-1002"):
            with self.subTest(sid=sid):
                security = SyntheticWindowsSecurity(
                    entries=[("S-1-3-4", 0, 0, 0x1F01FF), (sid, 0, 0, 1)]
                )
                with self.assertRaisesRegex(
                    runtime.OperatorRefused, "private_file_broad_access_refused"
                ):
                    security.check()

    def test_null_dacl_is_still_refused(self):
        with self.assertRaisesRegex(runtime.OperatorRefused, "private_file_owner_or_acl_refused"):
            SyntheticWindowsSecurity(null_dacl=True).check()

    def test_unsupported_ace_is_still_refused(self):
        with self.assertRaisesRegex(runtime.OperatorRefused, "private_file_acl_form_refused"):
            SyntheticWindowsSecurity(entries=[("S-1-3-4", 5, 0, 1)]).check()

    def test_deny_and_inherit_only_entries_do_not_grant_access(self):
        SyntheticWindowsSecurity(
            entries=[("S-1-3-4", 0, 0, 0x1F01FF), ("S-1-1-0", 1, 0, 1), ("S-1-1-0", 0, 8, 1)]
        ).check()


@unittest.skipUnless(os.name == "nt", "Requires native Windows security metadata")
class WindowsPrivateFolderTests(unittest.TestCase):
    def test_python_mkdir_0700_is_private_without_acl_changes(self):
        workspace = Path.cwd().resolve()
        root = Path(tempfile.mkdtemp(prefix="fga-empty-private-acl-", dir=workspace)).resolve()
        self.assertEqual(root.parent, workspace)
        child = root / "empty-private-child"
        try:
            child.mkdir(mode=0o700)
            runtime._assert_private(root, directory=True)
            runtime._assert_private(child, directory=True)
            self.assertEqual(list(child.iterdir()), [])
        finally:
            # Remove only the two exact, empty directories created by this test.
            if child.exists():
                child.rmdir()
            root.rmdir()


if __name__ == "__main__":
    unittest.main()
