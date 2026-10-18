"""Execution-capable source integration, with synthetic files and fake provider only."""

import io
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import renewed_group_post_attempt as renewed
from tests import test_group_post_dispatch as original


class RenewedLifecycleTests(original.DispatchTests):
    """Run the existing protocol fault contract through the new exact caller."""

    def reset_fixture(self):
        super().reset_fixture()
        self.inputs["runId"] = renewed.packet.RUN_ID
        self.coordination = self.root / "renewed-run/handshake"
        self.coordination.parent.mkdir()
        self.action_deadline = self.now + 1500
        override = patch.object(renewed.packet, "RUN_ROOT", self.coordination.parent)
        override.start()
        self.addCleanup(override.stop)

    def execute(self):
        return renewed.execute(
            self.api,
            self.inputs,
            coordination_root=self.coordination,
            action_deadline=self.action_deadline,
            clock=lambda: self.now,
            monotonic=lambda: self.now,
            sleep=self.sleep,
        )

    def test_renewed_target_uses_new_identity_and_resource_expiry_within_action_bound(self):
        result = self.execute()
        target = self.read(self.native / "target.json")
        self.assertEqual(target["runId"], renewed.packet.RUN_ID)
        self.assertLessEqual(target["expiresAtUnix"], self.action_deadline)
        self.assertTrue(result["cleanupConfirmed"])
        self.assertFalse(self.api.objects)

    def test_sealed0160_identity_and_unbound_coordination_root_cannot_enter_provider(self):
        self.inputs["runId"] = renewed.packet.sealed.RUN_ID
        with self.assertRaisesRegex(ValueError, "provider_config_mismatch"):
            self.execute()
        self.inputs["runId"] = renewed.packet.RUN_ID
        self.coordination = self.root / "unbound"
        with self.assertRaisesRegex(ValueError, "provider_config_mismatch"):
            self.execute()
        self.assertFalse(self.api.calls)
        self.assertFalse(self.native.exists())

    def test_bad_absolute_action_deadline_has_no_owner_or_provider_effects(self):
        for deadline in (None, True, float("inf"), self.now + 1229, self.now + 1801):
            with self.subTest(deadline=deadline):
                self.action_deadline = deadline
                with self.assertRaisesRegex(ValueError, "action_deadline_invalid"):
                    self.execute()
                self.assertFalse(self.coordination.exists())
                self.assertFalse(self.api.calls)

    def test_deadline_is_rechecked_after_prewarm_and_owner_is_closed_without_provider(self):
        self.action_deadline = self.now + 1230
        original_ready = renewed.sealed.NativeFiles.wait_ready

        def delayed_ready(native):
            original_ready(native)
            self.now += 31

        with patch.object(renewed.sealed.NativeFiles, "wait_ready", delayed_ready):
            with self.assertRaisesRegex(ValueError, "action_deadline_insufficient"):
                self.execute()
        self.assertFalse(self.api.calls)
        self.assertFalse(self.native.exists())
        self.assertEqual(self.read(self.coordination / "owner.json")["state"], "closed")

    def test_manifest_read_delay_cannot_extend_resources_beyond_absolute_action_deadline(self):
        action_deadline = self.now + 1230
        self.action_deadline = action_deadline
        original_ready = renewed.sealed.NativeFiles.wait_ready
        original_read = renewed.post.bounded_json

        def boundary_ready(native):
            original_ready(native)
            self.now = action_deadline - 1200

        def delayed_manifest(path, maximum=65536):
            value = original_read(path, maximum)
            if path == renewed.post.PACKET / "manifest.json":
                self.now += 1
            return value

        with (
            patch.object(renewed.sealed.NativeFiles, "wait_ready", boundary_ready),
            patch.object(renewed.post, "bounded_json", delayed_manifest),
        ):
            try:
                result = self.execute()
            except ValueError:
                result = None
        self.assertFalse(self.api.calls)
        self.assertFalse(self.api.objects)
        self.assertFalse((self.native / "target.json").exists())
        if result is not None:
            self.assertNotEqual(result["outcome"], "characterized")
        self.assertEqual(self.read(self.coordination / "owner.json")["state"], "closed")

    def test_deadline_wrapper_preserves_underlying_provider_account_change_fence(self):
        original_call = self.api.call

        def changed_account(method, path, body=None, timeout=20):
            response = original_call(method, path, body, timeout)
            self.api.account = "b" * 32
            return response

        self.api.call = changed_account
        result = self.execute()
        self.assertNotEqual(result["outcome"], "characterized")
        self.assertEqual(len(self.api.calls), 1)
        self.assertFalse(self.api.objects)
        self.assertFalse((self.native / "target.json").exists())
        self.assertEqual(self.read(self.coordination / "owner.json")["state"], "closed")

    def test_approved_account_drift_during_readiness_never_reaches_provider(self):
        original_ready = renewed.sealed.NativeFiles.wait_ready

        def account_drift(native):
            original_ready(native)
            self.api.account = "b" * 32

        with patch.object(renewed.sealed.NativeFiles, "wait_ready", account_drift):
            try:
                result = self.execute()
            except ValueError:
                result = None
        self.assertFalse(self.api.calls)
        self.assertFalse(self.api.objects)
        self.assertFalse((self.native / "target.json").exists())
        if result is not None:
            self.assertNotEqual(result["outcome"], "characterized")
        self.assertEqual(self.read(self.coordination / "owner.json")["state"], "closed")


class RenewedApplyTests(unittest.TestCase):
    def config(self):
        return {
            "runId": renewed.packet.RUN_ID,
            "accountId": "a" * 32,
            "subdomain": "synthetic-only",
            "nativeRoot": str(renewed.post.NATIVE_ROOT),
            "coordinationRoot": "C:/synthetic/handshake",
            "tokenFile": "C:/synthetic/memory-only-token",
            "actionDeadlineUnix": 2500,
        }

    def test_rejected_packet_never_opens_token_or_constructs_provider(self):
        with (
            patch.object(renewed.packet, "validate_packet", side_effect=ValueError("refused")),
            patch.object(Path, "open") as opened,
            patch.object(renewed.post, "Provider") as provider,
        ):
            with self.assertRaisesRegex(ValueError, "refused"):
                renewed.apply(Path("synthetic-approval"), "a" * 64)
        opened.assert_not_called()
        provider.assert_not_called()

    def test_apply_threads_exact_validated_inputs_after_bounded_memory_token(self):
        config = self.config()
        events = []

        def token_open(path, mode):
            events.append("token")
            self.assertEqual(path, Path(config["tokenFile"]))
            self.assertEqual(mode, "rb")

            class BoundedMemoryToken(io.BytesIO):
                def read(self, size: int | None = -1):
                    if size != 4097:
                        raise AssertionError("token read must be bounded at 4097 bytes")
                    return super().read(size)

            return BoundedMemoryToken(b"synthetic-memory-only-token")

        def validated(*args):
            events.append("validated")
            return config

        with (
            patch.object(renewed.packet, "validate_packet", side_effect=validated),
            patch.object(Path, "open", token_open),
            patch.object(renewed.post, "Provider") as provider,
            patch.object(renewed, "execute", return_value={"synthetic": True}) as execute,
        ):
            result = renewed.apply(Path("synthetic-approval"), "a" * 64)
        self.assertEqual(events, ["validated", "token"])
        self.assertEqual(result, {"synthetic": True})
        provider.assert_called_once_with(
            config["accountId"], "synthetic-memory-only-token", config["runId"]
        )
        execute.assert_called_once_with(
            provider.return_value,
            {key: config[key] for key in ("runId", "accountId", "subdomain")},
            coordination_root=Path(config["coordinationRoot"]),
            action_deadline=config["actionDeadlineUnix"],
        )

    def test_invalid_or_oversize_memory_token_never_constructs_provider(self):
        for token in (b"short", b"x" * 4097, b"invalid token with whitespace"):
            with self.subTest(length=len(token)):
                with (
                    patch.object(renewed.packet, "validate_packet", return_value=self.config()),
                    patch.object(Path, "open", return_value=io.BytesIO(token)),
                    patch.object(renewed.post, "Provider") as provider,
                ):
                    with self.assertRaisesRegex(ValueError, "provider_token_invalid"):
                        renewed.apply(Path("synthetic-approval"), "a" * 64)
                provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
