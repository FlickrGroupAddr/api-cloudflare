"""Public native facade integration; invented inputs and blocked socket/DNS only."""

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import binding
import test_binding as fixtures
import test_native_sender as sender_fixtures

adapter = binding.adapter
custody = binding.native_custody


class NativeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.helper = sender_fixtures.NativeSenderTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)
        self.addCleanup(self.helper.tearDown)

    def test_public_factory_requires_factual_admission_before_delivery(self):
        fixture_sender, _journal, _intent, _admission, delivery = self.helper.plan()
        core = fixture_sender.core
        self.assertIs(fixture_sender, core.sender)
        with self.assertRaises(adapter.Refusal):
            core.activate(delivery)
        self.assertIsNone(core.token)
        self.assertFalse(delivery.used)

    def test_public_factory_uses_its_single_sender_for_native_controller(self):
        fixture_sender, journal, intent, admission, delivery = self.helper.plan()
        core = fixture_sender.core
        source_sender = core.sender
        core.activate(delivery, admission=admission)
        self.assertIs(core.sender, source_sender)
        self.assertIs(core.sender.admission, admission)
        with fixtures.patched_transport(side_effect=self.helper.fixture.batch_transport) as wire:
            result = custody.NativeController(core.sender).execute(intent)
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(wire.call_count, 5)
        self.assertEqual(journal.get(intent.key, 100).phase, "confirmed")
        self.assertIs(core.read_evidence, core.sender.read_evidence)
        self.assertEqual(len(core.read_evidence), 4)

    def test_public_factory_returned_custody_is_restart_readable_and_not_replayed(self):
        fixture_sender, _journal, intent, admission, delivery = self.helper.plan()
        core = fixture_sender.core
        core.activate(delivery, admission=admission)
        directory = self.helper.fixture.directory
        retained = custody.ReturnedInvocations(
            directory / "root-returned.sqlite",
            core.packet_sha2_256,
            intent.target_id,
            intent.candidate,
            core.clock,
        )
        retained.provision(100)
        controller = custody.NativeController(core.sender)
        with fixtures.patched_transport(side_effect=self.helper.fixture.batch_transport) as wire:
            result = retained.invoke(controller, intent, "native:root-facade")
            self.assertEqual(result.status, "confirmed")
            self.assertEqual(wire.call_count, 5)
            restarted = custody.ReturnedInvocations(
                retained.path, core.packet_sha2_256, intent.target_id, intent.candidate, core.clock
            )
            receipt = restarted.read("native:root-facade", 100)
            self.assertEqual(
                receipt, adapter.ConfirmedReceipt("native:root-facade", intent, result)
            )
            with self.assertRaises(sqlite3.IntegrityError):
                restarted.invoke(controller, intent, "native:root-facade")
            self.assertEqual(wire.call_count, 5)

    def test_entry_disk_drift_is_not_relabelled_and_refuses_before_delivery(self):
        fixture_sender, _journal, _intent, admission, delivery = self.helper.plan()
        own_path = Path(binding.__file__)
        original = Path.read_bytes
        loaded_pin = binding.sha2_256(original(own_path))
        self.assertEqual(
            binding.source_pins()["probes/pmb1-native-d1-binding/binding.py"], loaded_pin
        )

        def changed(path):
            value = original(path)
            return value + b"\n" if path == own_path else value

        with patch.object(Path, "read_bytes", changed):
            with self.assertRaises(adapter.Refusal):
                binding.source_pins()
            with self.assertRaises(adapter.Refusal):
                fixture_sender.core.activate(delivery, admission=admission)
        self.assertFalse(delivery.used)
        self.assertIsNone(fixture_sender.core.token)
        self.assertEqual(binding.sha2_256(original(own_path)), loaded_pin)


if __name__ == "__main__":
    unittest.main()
