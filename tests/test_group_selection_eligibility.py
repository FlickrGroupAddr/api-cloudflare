"""Block-first complete eligibility assembly in actual Lua 5.1."""

from __future__ import annotations

import unittest

from test_submission_status_client import BUNDLE, STAMP, StatusFixtures, intent


class EligibilityTests(StatusFixtures, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.eligibility = self.lua.execute(
            (BUNDLE / "GroupSelectionEligibility.lua").read_text(encoding="utf-8")
        )

    def inputs(self, states=()):
        records = [intent(i, state) for i, state in enumerate(states, 1)]
        groups = {
            "state": "complete",
            "snapshotStatus": "fresh",
            "snapshotRevision": 3,
            "refreshedAt": STAMP,
            "groups": [
                {"flickrGroupId": f"group-{i:05}", "displayName": f"Group {i}"}
                for i in range(1, len(records) + 3)
            ],
        }
        membership = {
            "fgaPhotoBindingId": "binding-1",
            "flickrPhotoId": "photo-1",
            "observationRevision": 1,
            "observedAt": STAMP,
            "groups": [],
        }
        history = {
            "state": "complete",
            "fgaPhotoBindingId": "binding-1",
            "flickrPhotoId": "photo-1",
            "observedAt": STAMP,
            "intents": records,
        }
        return groups, membership, history

    def assemble(self, groups, membership=None, history=None):
        return self.eligibility.assemble(
            self.decoded(groups),
            self.decoded(membership) if membership else None,
            self.decoded(history) if history else None,
            self.client,
            self.json.null,
        )

    def test_block_first_wins_over_current_membership_and_retention(self):
        groups, membership, history = self.inputs(
            ["moderation_submitted", "delivery_uncertain", "cancelled"]
        )
        membership["groups"] = groups["groups"][:2] + groups["groups"][3:4]
        result = self.assemble(groups, membership, history)
        self.assertEqual(
            [result.rows[i].code for i in range(1, 6)],
            [
                "moderation_submission_protected",
                "delivery_uncertain_protected",
                "existing_submission_intent",
                "current_membership_observed",
                "eligible_group_addition",
            ],
        )
        self.assertEqual(len(result.eligibleGroups), 1)
        for i in range(1, 5):
            self.assertTrue(result.rows[i].readOnly)
            self.assertNotIn("select_for_first_add", list(result.rows[i].actions.values()))
        self.assertTrue(result.rows[1].currentMembershipObserved)
        self.assertIn("final moderator decision is unknown", result.rows[1].copy)

    def test_nonwritable_retained_pair_remains_visible(self):
        groups, membership, history = self.inputs(["delivery_uncertain"])
        groups["groups"] = []
        result = self.assemble(groups, membership, history)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[1].flickrGroupId, "group-00001")
        self.assertEqual(len(result.eligibleGroups), 0)

    def test_every_retained_state_is_readonly(self):
        states = [
            "queued",
            "attempting",
            "retrying",
            "throttled",
            "added",
            "moderation_submitted",
            "delivery_uncertain",
            "needs_attention",
            "cancelled",
        ]
        result = self.assemble(*self.inputs(states))
        self.assertEqual(len(result.eligibleGroups), 2)
        for i in range(1, 10):
            self.assertTrue(result.rows[i].readOnly)

    def test_incomplete_stale_foreign_and_contradictory_inputs_block_whole_model(self):
        for variant in range(5):
            groups, membership, history = self.inputs(["moderation_submitted"])
            if variant == 0:
                groups["snapshotStatus"] = "stale_refreshing"
            elif variant == 1:
                history["state"] = "unavailable"
            elif variant == 2:
                membership["flickrPhotoId"] = "foreign"
            elif variant == 3:
                history["intents"][0]["permanentSubmissionBlock"] = None
            else:
                history["intents"].append(history["intents"][0])
            self.assertEqual(
                self.assemble(groups, membership, history)[1], "selection_data_unavailable"
            )

    def test_unbound_fresh_snapshot_has_only_eligible_rows(self):
        groups, _, _ = self.inputs()
        result = self.assemble(groups)
        self.assertFalse(result.bound)
        self.assertEqual(len(result.eligibleGroups), 2)

    def test_failed_complete_load_preserves_prior_only_as_stale(self):
        groups, _, _ = self.inputs()
        prior = self.assemble(groups)
        deps = self.lua.table_from({"loadGroups": self.lua.eval("function() return nil end")})
        result = self.eligibility.load(deps, None, prior)
        self.assertIsNone(result[0])
        self.assertTrue(result[2].stale)
        self.assertEqual(result[2].state, "unavailable")


if __name__ == "__main__":
    unittest.main()
