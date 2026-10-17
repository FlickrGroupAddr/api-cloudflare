"""Deterministic offline interleavings, no secrets or provider access."""

from unittest import TestCase

from scripts.secret_ownership_model import (
    LOCAL_STEPS,
    LocalAttempt,
    NameOnlyStore,
    interleaving,
    mutation_free_boundary,
    violations,
)


class SecretOwnershipTests(TestCase):
    def test_all_foreign_write_positions_expose_both_races(self):
        self.assertEqual(
            [violations(interleaving(gap)) for gap in range(len(LOCAL_STEPS) + 1)],
            [(), ("foreign_overwritten",), ("foreign_deleted",), ("foreign_deleted",), ()],
        )

    def test_same_journal_lock_does_not_exclude_foreign_provider_writer(self):
        store = NameOnlyStore()
        local = LocalAttempt(store)
        self.assertTrue(local.acquire())
        self.assertFalse(local.acquire())
        local.step("absence")
        store.put("foreign")
        local.step("put")
        self.assertTrue(local.locked)
        self.assertEqual(violations(store), ("foreign_overwritten",))

    def test_name_acknowledgment_and_metadata_cannot_identify_replacement(self):
        store = NameOnlyStore()
        local = LocalAttempt(store)
        local.acquire()
        local.step("absence")
        local.step("put")
        acknowledged_name = local.acknowledged_name
        store.put("foreign")
        self.assertEqual(store.metadata(), acknowledged_name)
        local.step("metadata_recheck")
        local.step("delete")
        self.assertEqual(violations(store), ("foreign_deleted",))

    def test_foreign_write_after_final_recheck_is_deleted(self):
        store = interleaving(3)
        self.assertEqual(store.events[-1].previous_lineage, "foreign")
        self.assertEqual(store.events[-1].operation, "delete")
        self.assertIsNone(store.lineage)

    def test_preexisting_foreign_name_refuses_all_local_mutations(self):
        store = interleaving(0)
        self.assertEqual(store.lineage, "foreign")
        self.assertEqual([event.actor for event in store.events], ["foreign"])

    def test_unacknowledged_put_refuses_cleanup(self):
        store = NameOnlyStore()
        local = LocalAttempt(store)
        local.acquire()
        local.step("absence")
        # Provider committed but the response was lost: no receipt is recorded.
        store.put("local")
        local.step("metadata_recheck")
        local.step("delete")
        self.assertTrue(local.refused)
        self.assertEqual(store.lineage, "local")
        self.assertEqual([event.operation for event in store.events], ["put"])

    def test_randomized_or_environment_qualified_names_do_not_establish_exclusion(self):
        for name in ("RUN_0123456789ABCDEF", "isolated-environment/FIXED_NAME"):
            with self.subTest(name=name):
                self.assertEqual(violations(interleaving(1, name=name)), ("foreign_overwritten",))
                self.assertEqual(violations(interleaving(3, name=name)), ("foreign_deleted",))

    def test_proposed_zero_actions_secret_mutations_preserve_foreign_state(self):
        for initially_present in (False, True):
            for gap in range(len(LOCAL_STEPS) + 1):
                with self.subTest(initially_present=initially_present, gap=gap):
                    store = mutation_free_boundary(gap, initially_present=initially_present)
                    self.assertEqual(violations(store), ())
                    self.assertEqual(store.lineage, "foreign")
                    self.assertTrue(all(event.actor == "foreign" for event in store.events))

    def test_local_mutation_requires_lock_and_valid_model_order(self):
        local = LocalAttempt(NameOnlyStore())
        with self.assertRaisesRegex(ValueError, "local_lock_required"):
            local.step("absence")
        local.acquire()
        with self.assertRaisesRegex(ValueError, "absence_required"):
            local.step("put")
        with self.assertRaisesRegex(ValueError, "unknown_model_step"):
            local.step("conditional_create")
        for gap in (-1, 5, True):
            with self.subTest(gap=gap), self.assertRaises(ValueError):
                interleaving(gap)
            with self.subTest(gap=gap), self.assertRaises(ValueError):
                mutation_free_boundary(gap, initially_present=False)
