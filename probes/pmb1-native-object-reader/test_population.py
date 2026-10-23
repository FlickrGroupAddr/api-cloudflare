"""Synthetic REST framing/hostile census tests; never connect to an account."""

import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from population import DEFAULT_BOUNDS, Bounds, Census, HttpsGet, Refused

ACCOUNT = "a" * 32
NAMESPACE = "b" * 32
NS = {
    "id": NAMESPACE,
    "class": "PartitionWorker",
    "name": "synthetic",
    "script": "synthetic",
    "use_sqlite": True,
}
# Independent literal expected inventory. Provider observations never build it.
EXPECTED = {
    NAMESPACE: [{"id": "c" * 64, "hasStoredData": False}, {"id": "d" * 64, "hasStoredData": True}]
}


def envelope(rows, info):
    return json.dumps(
        {"success": True, "errors": [], "messages": [], "result": rows, "result_info": info}
    ).encode()


def namespace_page():
    return envelope(
        [NS], {"page": 1, "per_page": 10, "count": 1, "total_count": 1, "total_pages": 1}
    )


def object_page(rows=None, cursor=None):
    return envelope(EXPECTED[NAMESPACE] if rows is None else rows, {"cursor": cursor})


class FakeGet:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def __call__(self, path, cap, remaining):
        self.calls.append((path, cap, remaining))
        result = self.pages.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class PopulationTests(unittest.TestCase):
    def collect(self, pages, bounds=DEFAULT_BOUNDS, expected=EXPECTED):
        get = FakeGet(pages)
        return Census(ACCOUNT, get, bounds).collect([NS], expected), get

    def refuses(self, pages, category, bounds=DEFAULT_BOUNDS, expected=EXPECTED):
        with self.assertRaisesRegex(Refused, "^" + category + "$"):
            self.collect(pages, bounds, expected)

    def test_supported_paths_include_unstored_objects_without_completeness_claim(self):
        observed, get = self.collect([namespace_page(), object_page()])
        self.assertEqual(observed["objects"], EXPECTED)
        self.assertFalse(observed["completeSnapshot"])
        self.assertFalse(observed["actualQualification"])
        self.assertEqual(len(get.calls), 2)
        self.assertTrue(get.calls[0][0].endswith("namespaces?page=1&per_page=10"))
        self.assertTrue(get.calls[1][0].endswith(f"namespaces/{NAMESPACE}/objects?limit=10"))

    def test_cursor_is_opaque_not_object_id_or_lexical_order(self):
        pages = [
            namespace_page(),
            object_page([EXPECTED[NAMESPACE][1]], "z+/="),
            object_page([EXPECTED[NAMESPACE][0]]),
        ]
        observed, get = self.collect(pages)
        self.assertEqual(observed["objects"], EXPECTED)
        self.assertIn("cursor=z%2B%2F%3D", get.calls[-1][0])

    def test_missing_extra_duplicate_unknown_objects_refuse(self):
        self.refuses([namespace_page(), object_page([])], "object_population_mismatch")
        self.refuses(
            [
                namespace_page(),
                object_page([*EXPECTED[NAMESPACE], {"id": "e" * 64, "hasStoredData": True}]),
            ],
            "object_population_mismatch",
        )
        self.refuses(
            [namespace_page(), object_page([EXPECTED[NAMESPACE][0]] * 2)], "duplicate_object"
        )
        self.refuses([namespace_page(), object_page([{"id": "c" * 64}])], "unknown_object_metadata")
        self.refuses(
            [
                namespace_page(),
                object_page([{"id": "c" * 64, "hasStoredData": True, "unknown": 1}]),
            ],
            "unknown_object_metadata",
        )

    def test_unstored_flag_must_match_independent_inventory(self):
        rows = [dict(row) for row in EXPECTED[NAMESPACE]]
        rows[0]["hasStoredData"] = True
        self.refuses([namespace_page(), object_page(rows)], "object_population_mismatch")

    def test_cursor_loop_and_unknown_terminal_refuse(self):
        self.refuses(
            [
                namespace_page(),
                object_page([EXPECTED[NAMESPACE][0]], "loop"),
                object_page([EXPECTED[NAMESPACE][1]], "loop"),
            ],
            "object_cursor_unknown",
        )
        self.refuses([namespace_page(), envelope([], {})], "object_pagination_unknown")
        self.refuses([namespace_page(), object_page([], "more")], "object_cursor_unknown")

    def test_response_call_object_and_elapsed_bounds(self):
        self.refuses(
            [namespace_page()], "response_byte_bound", replace(Bounds(), response_bytes=10)
        )
        self.refuses([namespace_page()], "census_call_bound", replace(Bounds(), calls=1))
        self.refuses(
            [namespace_page(), object_page()],
            "object_bound",
            replace(Bounds(), objects=1),
            {NAMESPACE: EXPECTED[NAMESPACE][:1]},
        )
        with patch("population.time.monotonic", side_effect=[0, 31]):
            self.refuses([], "census_elapsed_bound")

    def test_duplicate_json_and_malformed_envelope_refuse(self):
        self.refuses([b'{"success":true,"success":true}'], "duplicate_json_key")
        self.refuses([b"\xff"], "invalid_census_json")
        self.refuses([b"{}"], "unknown_census_envelope")

    def test_expected_inputs_freeze_before_untrusted_callback(self):
        expected = json.loads(json.dumps(EXPECTED))
        get = FakeGet([namespace_page(), object_page()])

        def mutate(path, cap, remaining):
            expected[NAMESPACE].clear()
            return get(path, cap, remaining)

        observed = Census(ACCOUNT, mutate).collect([NS], expected)
        self.assertEqual(observed["objects"], EXPECTED)

    def test_unknown_is_once_only_and_new_object_does_not_supply_its_expected_id(self):
        get = FakeGet([OSError("private provider details")])
        reader = Census(ACCOUNT, get)
        with self.assertRaisesRegex(Refused, "^census_read_unknown$"):
            reader.collect([NS], EXPECTED)
        with self.assertRaisesRegex(Refused, "^census_once_only$"):
            reader.collect([NS], EXPECTED)
        self.assertEqual(len(get.calls), 1)

    def test_restart_retains_no_false_closure_or_spent_authority(self):
        first, _ = self.collect([namespace_page(), object_page()])
        second, _ = self.collect([namespace_page(), object_page()])
        self.assertFalse(first["completeSnapshot"])
        self.assertFalse(second["completeSnapshot"])

    def test_unqualified_actual_transport_is_disabled_before_dns_or_connection(self):
        with patch("http.client.HTTPSConnection") as connection, patch("socket.getaddrinfo") as dns:
            for path, cap, remaining in (("/synthetic", 10, 1), ("bad", -1, float("nan"))):
                with self.assertRaisesRegex(Refused, "^native_census_transport_unqualified$"):
                    HttpsGet("synthetic_token_only")(path, cap, remaining)
            connection.assert_not_called()
            dns.assert_not_called()

    def test_all_namespace_numeric_metadata_are_exact_integers(self):
        for key in ("page", "per_page", "count", "total_count", "total_pages"):
            for value in (True, 1.0, 1.5, [], {}):
                with self.subTest(key=key, value=value):
                    data = json.loads(namespace_page())
                    data["result_info"][key] = value
                    self.refuses([json.dumps(data).encode()], "invalid_census_integer")

    def test_all_optional_object_numeric_metadata_are_exact_bounded_integers(self):
        for key in ("page", "per_page", "count", "total_count", "total_pages"):
            for value in (True, 1.0, 1.5, -1, 1000000000, [], {}):
                with self.subTest(key=key, value=value):
                    data = json.loads(object_page())
                    data["result_info"][key] = value
                    self.refuses(
                        [namespace_page(), json.dumps(data).encode()], "invalid_census_integer"
                    )

    def test_json_nan_and_infinity_refuse_anywhere_in_envelope(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                data = json.loads(object_page())
                data["result_info"]["total_count"] = value
                self.refuses([namespace_page(), json.dumps(data).encode()], "non_json_number")


if __name__ == "__main__":
    unittest.main()
