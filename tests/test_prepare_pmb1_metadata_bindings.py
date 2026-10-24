"""Offline invented bindings only; run from the API repository root."""

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from scripts.temporary_composition_metadata_projection import endpoint_for

spec = importlib.util.spec_from_file_location(
    "binding_candidate",
    Path(__file__).resolve().parents[1] / "scripts/prepare_pmb1_metadata_bindings.py",
)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
RECORD = "C:/invented-protected-root/inputs/target-selection.json"


def fixture():
    targets = {
        "accountId": "a" * 32,
        "retainedWorkerId": "invented-retained",
        "temporaryWorkerId": "invented-temporary",
        "domainDatabaseId": "11111111-1111-1111-1111-111111111111",
        "sharedMainJournalEvidenceDatabaseId": "22222222-2222-2222-2222-222222222222",
        "oracleDatabaseId": "33333333-3333-3333-3333-333333333333",
    }
    return {
        "schemaVersion": 1,
        "kind": "0201_offline_target_bindings",
        "targets": targets,
        "references": {
            key: {
                "recordPath": RECORD,
                "selector": "/targets/" + key,
                "sha2_256": "b" * 64,
                "maximumBytes": 262144,
                "acquisitionPrincipalSid": "S-1-5-21-1-2-3-1001",
                "observedAt": "2026-10-24T12:00:00Z",
            }
            for key in adapter.TARGETS
        },
    }


def prepare(value):
    return adapter.prepare_metadata_requests(
        json.dumps(value).encode(),
        endpoint_for,
        expected_record_path=RECORD,
    )


class BindingTests(unittest.TestCase):
    def test_exact_seven_and_three_inert(self):
        result = prepare(fixture())
        self.assertEqual(len(result["requests"]), 7)
        self.assertEqual(len({x["path"] for x in result["requests"]}), 7)
        self.assertFalse(result["dispatchEnabled"])
        self.assertFalse(result["authenticatesCurrentFacts"])
        self.assertEqual(result["actualQualification"], "NO_GO")
        self.assertTrue(all(x["enabled"] is False for x in result["requests"]))
        self.assertEqual(
            [x["bearerRole"] for x in result["grantSequence"]],
            ["test credential", "metadata reader", "metadata reader"],
        )
        oracle = next(x for x in result["requests"] if x["role"] == "ORACLE_DB")
        self.assertEqual(oracle["target"]["scriptName"], "invented-temporary")
        self.assertEqual(oracle["scope"], "d1_database")

    def test_no_mutation_or_fact_promotion(self):
        value = fixture()
        before = copy.deepcopy(value)
        prepare(value)
        self.assertEqual(value, before)
        self.assertNotIn("actualInputs", prepare(value))

    def test_closed_schema_negatives(self):
        mutations = {
            "null_target": lambda x: x["targets"].update(accountId=None),
            "null_reference": lambda x: x["references"].update(accountId=None),
            "unknown_top": lambda x: x.update(approved=True),
            "credential_injection": lambda x: x["targets"].update(token="secret"),
            "bool_version": lambda x: x.update(schemaVersion=True),
            "bad_account": lambda x: x["targets"].update(accountId="../unknown"),
            "script_traversal": lambda x: x["targets"].update(retainedWorkerId="../x"),
            "alias_worker": lambda x: x["targets"].update(temporaryWorkerId="invented-retained"),
            "alias_database": lambda x: x["targets"].update(
                oracleDatabaseId=x["targets"]["domainDatabaseId"]
            ),
            "wrong_path": lambda x: x["references"]["accountId"].update(recordPath="C:/other"),
            "path_escape": lambda x: x["references"]["accountId"].update(
                recordPath="C:/invented-protected-root/inputs/../token.json"
            ),
            "extra_reference_field": lambda x: x["references"]["accountId"].update(
                credential="secret"
            ),
            "wrong_selector": lambda x: x["references"]["accountId"].update(selector="/token"),
            "bad_digest": lambda x: x["references"]["accountId"].update(sha2_256="x"),
            "different_record_digest": lambda x: x["references"]["accountId"].update(
                sha2_256="c" * 64
            ),
            "bool_size": lambda x: x["references"]["accountId"].update(maximumBytes=True),
            "oversized_record": lambda x: x["references"]["accountId"].update(maximumBytes=262145),
            "negative_record_size": lambda x: x["references"]["accountId"].update(maximumBytes=-1),
            "invalid_sid": lambda x: x["references"]["accountId"].update(
                acquisitionPrincipalSid="Everyone"
            ),
            "invalid_time": lambda x: x["references"]["accountId"].update(
                observedAt="2026-02-30T12:00:00Z"
            ),
            "nonutc_time": lambda x: x["references"]["accountId"].update(
                observedAt="2026-10-24T12:00:00-04:00"
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                value = fixture()
                mutate(value)
                with self.assertRaises(adapter.BindingError) as caught:
                    prepare(value)
                self.assertIn(str(caught.exception), adapter.ERRORS)

    def test_byte_decoder_limits_and_duplicates(self):
        cases = [
            b"",
            b" " * 65537,
            b'{"x":1,"x":2}',
            b'{"x":NaN}',
            b"\xff",
            b"[" * 2000 + b"]" * 2000,
        ]
        for raw in cases:
            with self.subTest(size=len(raw)):
                with self.assertRaises(adapter.BindingError) as caught:
                    adapter.decode_bindings(raw, expected_record_path=RECORD)
                self.assertIn(str(caught.exception), adapter.ERRORS)

    def test_projector_failure_sanitized(self):
        def bad(*_):
            raise RuntimeError("private material")

        with self.assertRaisesRegex(adapter.BindingError, "^UNSUPPORTED_SELECTOR$"):
            adapter.prepare_metadata_requests(
                json.dumps(fixture()).encode(),
                bad,
                expected_record_path=RECORD,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
