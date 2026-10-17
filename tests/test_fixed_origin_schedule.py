"""Closed offline schedule accounting; no native host, network, or credentials."""

from __future__ import annotations

import copy
import re
import unittest
from pathlib import Path
from typing import Any, cast

from lupa.lua51 import LuaRuntime

from scripts import fixed_origin_schedule as schedule

ROOT = Path(__file__).resolve().parents[1]


class FixedOriginScheduleTests(unittest.TestCase):
    def assert_closed_refusal(self, plan):
        result = schedule.validate_schedule(plan)
        self.assertEqual(result["decision"], "no-go")
        self.assertIn("closed_plan_mismatch", result["errors"])

    def test_current_fault_matrix_alone_exceeds_quota_before_other_observations(self):
        plan = schedule.build_schedule()
        result = schedule.validate_schedule(plan)
        self.assertEqual(result["decision"], "no-go")
        self.assertEqual(result["accounting"]["fault_fga"], 30 * 4)
        self.assertGreater(result["accounting"]["fault_fga"], 96)
        self.assertEqual(result["accounting"]["known_fga"], 120 + 16 + 4 + 4 + 5 + 1)
        self.assertEqual(result["accounting"]["known_receiver"], 5 + 1)
        self.assertEqual(result["accounting"]["known_native_invocations"], 30 + 3)
        self.assertIn("fga_budget_exceeded", result["errors"])
        self.assertIn("consumed_target_cannot_cover_invocations", result["errors"])

    def test_every_required_observation_is_accounted_or_explicitly_unbudgeted(self):
        rows = schedule.build_schedule()["observations"]
        self.assertEqual(len(rows), len({row["id"] for row in rows}))
        self.assertEqual({row["id"] for row in rows}, set(schedule.REQUIRED_OBSERVATIONS))
        self.assertTrue(schedule.UNBUDGETED_LIVE)
        for row in rows:
            with self.subTest(observation=row["id"]):
                if row["id"] in schedule.UNBUDGETED_LIVE:
                    self.assertEqual(row["kind"], "live-unbudgeted")
                    self.assertIsNone(row["fga"])
                    self.assertIsNone(row["receiver"])
                    self.assertIsNone(row["native_invocations"])
                elif row["kind"] == "live":
                    self.assertGreater(row["fga"], 0)
                else:
                    self.assertEqual(row["kind"], "offline-only")
                    self.assertEqual((row["fga"], row["receiver"]), (0, 0))
        result = schedule.validate_schedule(schedule.build_schedule())
        self.assertFalse(result["accounting"]["complete_accounting"])
        self.assertEqual(result["accounting"]["unbudgeted_live"], list(schedule.UNBUDGETED_LIVE))

    def test_report_redirect_and_cancellation_reserves_are_not_free(self):
        plan = schedule.build_schedule()
        rows = {row["id"]: row for row in plan["observations"]}
        self.assertEqual(rows["redirect-arrivals"]["fga"], 5)
        self.assertEqual(rows["redirect-arrivals"]["receiver"], 5)
        self.assertEqual(rows["cancel-during-get"]["fga"], 4)
        self.assertEqual(rows["receiver-report"]["fga"], plan["report_reserved_fga"])
        self.assertEqual(rows["receiver-report"]["receiver"], plan["report_reserved_receiver"])
        for name in ("redirect-arrivals", "cancel-during-get", "receiver-report"):
            for budget in ("fga", "receiver"):
                if rows[name][budget]:
                    changed = copy.deepcopy(plan)
                    next(row for row in changed["observations"] if row["id"] == name)[budget] = 0
                    with self.subTest(observation=name, budget=budget):
                        self.assert_closed_refusal(changed)

    def test_source_unsupported_proposal_fits_known_counts_but_remains_no_go(self):
        plan = schedule.build_schedule("proposed-shared-discovery")
        result = schedule.validate_schedule(plan)
        self.assertEqual(result["accounting"]["known_fga"], 30 * 2 + 2 + 16 + 4 + 4 + 6 + 4)
        self.assertEqual(result["accounting"]["known_receiver"], 6)
        self.assertEqual(result["accounting"]["known_native_invocations"], 1)
        self.assertEqual(result["decision"], "no-go")
        self.assertIn("proposed_program_source_unimplemented", result["errors"])
        self.assertIn("required_live_observations_unbudgeted", result["errors"])
        self.assertFalse(plan["source_supports_program"])
        self.assertFalse(plan["execution_authorized"])
        for field in ("deployment_allowed", "hosted_qualified", "native_qualified"):
            self.assertIs(result[field], False)

    def test_proposed_decoder_reuse_and_disconnect_cost_are_explicit_not_qualification(self):
        plan = schedule.build_schedule("proposed-shared-discovery")
        rows = {row["id"]: row for row in plan["observations"]}
        decoder = rows["native-decoder-png-jpeg-boundary"]
        self.assertEqual(decoder["kind"], "live")
        self.assertEqual(decoder["fga"], 0)
        self.assertEqual(decoder["coverage"], ["fault:png", "fault:jpeg", "fault:exact-limit"])
        for name in decoder["coverage"]:
            self.assertEqual(rows[name]["kind"], "live")
            self.assertGreater(rows[name]["fga"], 0)
        disconnect = rows["backend-abort-disconnect"]
        self.assertEqual(disconnect["fga"], 4)
        self.assertEqual(disconnect["driver"], "proposed-independent-fixed-path-disconnect")
        self.assertFalse(plan["source_supports_program"])
        self.assertFalse(schedule.validate_schedule(plan)["accounting"]["complete_accounting"])
        for field in ("coverage", "driver"):
            changed = copy.deepcopy(plan)
            row = next(row for row in changed["observations"] if field in row)
            del row[field]
            with self.subTest(missing=field):
                self.assert_closed_refusal(changed)
        changed = copy.deepcopy(plan)
        row = next(
            row for row in changed["observations"] if row["id"] == "backend-abort-disconnect"
        )
        row["fga"] = 0
        self.assert_closed_refusal(changed)

    def test_one_attempt_target_no_retry_no_reset_and_fixed_windows(self):
        plan = schedule.build_schedule()
        self.assertEqual(
            plan["limits"],
            {
                "fga": 96,
                "receiver": 16,
                "inner_ms": 600_000,
                "outer_ms": 1_200_000,
            },
        )
        self.assertEqual(plan["stop_before_ms"], 600_000)
        self.assertEqual(plan["cleanup_reserve_ms"], 600_000)
        self.assertEqual(plan["stop_before_ms"] + plan["cleanup_reserve_ms"], 1_200_000)
        self.assertFalse(plan["hard_native_total_deadline_proven"])
        mutations = {
            "attempts": 2,
            "consumed_targets": 33,
            "retries": 1,
            "namespace_resets": 1,
            "stop_before_ms": 600_001,
            "cleanup_reserve_ms": 0,
            "report_reserved_fga": 0,
            "report_reserved_receiver": 0,
            "execution_authorized": True,
            "source_supports_program": True,
            "hard_native_total_deadline_proven": True,
        }
        for field, value in mutations.items():
            changed = copy.deepcopy(plan)
            changed[field] = value
            with self.subTest(field=field):
                self.assert_closed_refusal(changed)
        for field, value in {"fga": 150, "receiver": 17, "inner_ms": 1_200_000}.items():
            changed = copy.deepcopy(plan)
            changed["limits"][field] = value
            with self.subTest(limit=field):
                self.assert_closed_refusal(changed)

    def test_omission_duplication_unknown_and_reclassification_fail_closed(self):
        plan = schedule.build_schedule()
        for index in range(len(plan["observations"])):
            with self.subTest(omitted=plan["observations"][index]["id"]):
                changed = copy.deepcopy(plan)
                del changed["observations"][index]
                self.assert_closed_refusal(changed)
        for change in ("duplicate", "unknown", "offline", "free-live"):
            changed = copy.deepcopy(plan)
            row = changed["observations"][0]
            if change == "duplicate":
                changed["observations"].append(copy.deepcopy(row))
            elif change == "unknown":
                row["id"] = "fault:unreviewed"
            elif change == "offline":
                row["kind"] = "offline-only"
            else:
                row["fga"] = 0
            with self.subTest(change=change):
                self.assert_closed_refusal(changed)

    def test_wrong_types_and_unrecognized_fields_are_rejected(self):
        for field, value in {
            "attempts": True,
            "report_reserved_fga": 1.0,
            "retries": False,
            "unknown": "accepted",
        }.items():
            changed = schedule.build_schedule()
            changed[field] = value
            with self.subTest(field=field):
                self.assert_closed_refusal(changed)
        for value in (None, [], {}, {"profile": "unknown"}):
            with self.subTest(invalid=value):
                self.assertEqual(schedule.validate_schedule(cast(Any, value))["decision"], "no-go")
        with self.assertRaises(ValueError):
            schedule.build_schedule("accepted")

    def test_limits_match_actual_durable_guard_and_native_inner_window(self):
        quota = (ROOT / "probes/fixed-origin-lifecycle/quota_receiver.mjs").read_text(
            encoding="utf-8"
        )
        self.assertRegex(quota, r"fga:\s*96,\s*receiver:\s*16,\s*lifetimeMs:\s*1_200_000")
        self.assertIn("fga_count<96 RETURNING singleton", quota)
        self.assertIn("receiver_count<16 RETURNING singleton", quota)
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        config = lua.execute(
            (ROOT / "probes/lightroom/FGA-FixedOrigin-v1.lrplugin/Config.lua").read_text(
                encoding="utf-8"
            )
        )
        valid = lua.table_from(
            {
                "schemaVersion": 1,
                "version": config.VERSION,
                "run": "a" * 32,
                "capability": "b" * 64,
                "case": "ok",
                "mode": "browser",
                "startsAt": 1,
                "expiresAt": 601,
                "sources": lua.table_from({name: "e" * 64 for name in config.SOURCES.values()}),
                "workerSha256": "c" * 64,
                "configurationSha256": "d" * 64,
            }
        )
        self.assertTrue(config.validate(valid, 1))
        self.assertFalse(config.validate(valid, 601))
        valid.expiresAt = 602
        self.assertFalse(config.validate(valid, 1))
        valid.expiresAt = 601
        valid.mode = "batch"
        self.assertFalse(config.validate(valid, 1))

    def test_inventory_matches_actual_native_selector_and_handler_source(self):
        lua = cast(Any, LuaRuntime)(unpack_returned_tuples=True)
        config = lua.execute(
            (ROOT / "probes/lightroom/FGA-FixedOrigin-v1.lrplugin/Config.lua").read_text(
                encoding="utf-8"
            )
        )
        selected = set(config.CASES.keys()) - {"ok", "invalid-auth"}
        self.assertEqual(selected, set(schedule.HANDLER_CASES) | set(schedule.EDGE_CASES))
        self.assertEqual(len(selected), 30)
        handler = (ROOT / "probes/fixed-origin-lifecycle/handler_cases.mjs").read_text(
            encoding="utf-8"
        )
        block = handler.split("export const HANDLER_CASES = Object.freeze({", 1)[1].split("});", 1)[
            0
        ]
        actual = {
            match.group(1) or match.group(2)
            for match in re.finditer(r"(?:'([^']+)'|([a-z][a-z-]*))\s*:\s*\d+", block)
        }
        self.assertEqual(actual, set(schedule.HANDLER_CASES))
        self.assertEqual(len(actual), 20)


if __name__ == "__main__":
    unittest.main()
