"""Private snapshot orchestration under fake transport; no hosted/native proof."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import private_d1_snapshot_codec as codec
from scripts import private_d1_snapshot_reader as reader
from scripts.hosted_publisher_finite_client import Response

NOW = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
TOKEN = "synthetic-private-token-0170"
MARKER = "synthetic-private-record-0170"


def envelope(rows, *, meta=None):
    return {
        "success": True,
        "errors": [],
        "messages": [],
        "result": [{"success": True, "results": rows, "meta": {} if meta is None else meta}],
    }


class SnapshotReaderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fga-synthetic-snapshot-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output, self.journal = self.root / "private.json", self.root / "journal.jsonl"
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE sample(value)")
        self.db.execute("INSERT INTO sample VALUES (?)", (MARKER,))
        self.db.commit()
        self.queries = []

        def discovery(sql):
            self.queries.append(sql)
            return self.rows(sql)

        self.expected = codec.collect_snapshot(discovery, page_size=2)
        self.credential = Mock(return_value=TOKEN)
        self.transport = Mock(side_effect=self.response)
        self.stdout, self.stderr = io.StringIO(), io.StringIO()

    def rows(self, sql):
        cursor = self.db.execute(sql)
        names = [entry[0] for entry in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor]

    def response(self, request):
        self.assertTrue(request.url.endswith("/query"))
        self.assertEqual(request.headers["Authorization"], "Bearer " + TOKEN)
        self.assertTrue(request.wire.startswith(b"POST /client/v4/accounts/"))
        body = json.loads(request.wire.split(b"\r\n\r\n", 1)[1])
        self.assertEqual(body["params"], [])
        encoded = reader.canonical(envelope(self.rows(body["sql"])))
        return Response(200, {"Content-Type": "application/json"}, encoded, len(encoded) + 100)

    def inputs(self):
        plan = {
            "schemaVersion": 1,
            "kind": "private_d1_snapshot_plan",
            "runId": "a" * 32,
            "sourceSha256": reader.source_sha256(),
            "accountId": "b" * 32,
            "databaseId": "11111111-2222-3333-4444-555555555555",
            "endpointAddress": "1.1.1.1",
            "startsAt": "2026-10-18T14:59:00Z",
            "expiresAt": "2026-10-18T15:10:00Z",
            "timeoutSeconds": 10,
            "maxResponseBytes": 262144,
            "maxTotalBytes": 1048576,
            "pageSize": 2,
            "queries": list(self.queries),
            "outputPath": str(self.output.resolve()),
            "journalPath": str(self.journal.resolve()),
        }
        plan.update({key: "d" * 64 for key in reader.PINS})
        plan["credentialBinding"] = hashlib.sha256(TOKEN.encode()).hexdigest()
        return plan, self.consent(plan)

    def consent(self, plan):
        return {
            "approved": True,
            "decisionRef": "synthetic-owner-decision",
            "planSha256": reader.digest(plan),
            "sourceSha256": copy.deepcopy(plan["sourceSha256"]),
            **{key: plan[key] for key in reader.PINS},
        }

    def collect(self, plan=None, consent=None, **options):
        default_plan, default_consent = self.inputs()
        plan = default_plan if plan is None else plan
        consent = default_consent if consent is None else consent
        kwargs = {"now": lambda: NOW, "clock": lambda: 100.0, "transport": self.transport}
        kwargs.update(options)
        with redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            return reader.collect(
                plan,
                reader.digest(plan),
                consent,
                self.credential,
                self.output,
                self.journal,
                **kwargs,
            )

    def refuse(self, callback):
        with self.assertRaises(reader.SnapshotError) as raised:
            callback()
        for text in (str(raised.exception), self.stdout.getvalue(), self.stderr.getvalue()):
            for private in (TOKEN, MARKER, str(self.output), str(self.journal)):
                self.assertNotIn(private, text)
        return raised.exception

    def test_complete_exact_snapshot_only_in_private_sink(self):
        summary = self.collect()
        self.assertEqual(
            summary, {"complete": True, "productionQualified": False, "queries": len(self.queries)}
        )
        self.assertEqual(json.loads(self.output.read_text())["snapshot"], self.expected)
        for text in (
            reader.canonical(summary).decode(),
            self.journal.read_text(),
            self.stdout.getvalue(),
            self.stderr.getvalue(),
        ):
            self.assertNotIn(TOKEN, text)
            self.assertNotIn(MARKER, text)
            self.assertNotIn("SELECT", text)
        self.assertEqual(self.transport.call_count, len(self.queries))
        for call in self.transport.call_args_list:
            self.assertLessEqual(call.args[0].max_response_bytes, 262144)

    def test_no_external_qualifier_cannot_be_replaced_by_evidence_hashes(self):
        self.refuse(lambda: self.collect(transport=None))
        self.credential.assert_not_called()
        self.transport.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.journal.exists())

    def test_invalid_authority_fields_refuse_before_credential_or_sink(self):
        mutations = [
            lambda p: p.update(extra=True),
            lambda p: p.update(schemaVersion=True),
            lambda p: p.update(artifactSha256="unknown"),
            lambda p: p.update(barrierReceiptSha256=""),
            lambda p: p.update(sourceSha256={}),
            lambda p: p.update(endpointAddress="127.0.0.1"),
            lambda p: p.update(pageSize=True),
            lambda p: p.update(maxTotalBytes=0),
            lambda p: p.update(expiresAt="2026-10-18T14:59:59Z"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                plan, _ = self.inputs()
                mutate(plan)
                self.refuse(lambda p=plan: self.collect(p, self.consent(p)))
                self.credential.assert_not_called()
                self.assertFalse(self.output.exists())
        plan, consent = self.inputs()
        consent["approved"] = 1
        self.refuse(lambda: self.collect(plan, consent))
        self.credential.assert_not_called()

    def test_unknown_dispatch_aborts_once_and_prevents_replay(self):
        self.transport.side_effect = TimeoutError(MARKER)
        self.refuse(self.collect)
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertIn("aborted_no_replay", self.journal.read_text())
        self.refuse(self.collect)
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.credential.call_count, 1)
        self.assertNotIn(MARKER, self.journal.read_text())

    def test_incomplete_or_malformed_provider_envelopes_refuse(self):
        cases = [
            envelope([], meta={"has_more": True}),
            envelope([], meta={"truncated": False}),
            {**envelope([]), "unexpected": MARKER},
            {**envelope([]), "success": 1},
            {**envelope([]), "errors": [MARKER]},
        ]
        for index, payload in enumerate(cases):
            with self.subTest(index=index):
                response = Response(
                    200, {"Content-Type": "application/json"}, reader.canonical(payload)
                )
                self.refuse(lambda r=response: reader._rows(r, 262144))
        for headers in (
            {"Content-Type": "text/plain"},
            {"Content-Type": "application/json", "Location": "https://example.org"},
            {"Content-Type": "application/json", "content-type": "application/json"},
            {"Content-Type": "application/json", "Content-Encoding": "gzip"},
        ):
            self.refuse(
                lambda h=headers: reader._rows(
                    Response(200, h, reader.canonical(envelope([]))), 262144
                )
            )

    def test_wall_or_monotonic_deadline_stops_before_credential(self):
        for options in (
            {"now": lambda: NOW + timedelta(minutes=11)},
            {"clock": Mock(side_effect=[100.0, 10000.0])},
        ):
            self.refuse(lambda o=options: self.collect(**o))
            self.credential.assert_not_called()
            self.transport.assert_not_called()
            for path in (self.output, self.journal):
                path.unlink(missing_ok=True)

    def test_response_total_and_exact_query_budget_fail_closed(self):
        plan, _ = self.inputs()
        plan["maxTotalBytes"] = 1
        self.refuse(lambda p=plan: self.collect(p, self.consent(p)))
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.output.read_bytes(), b"")

    def test_per_response_wire_ceiling_has_no_extra_header_allowance(self):
        plan, _ = self.inputs()
        plan["maxResponseBytes"] = 128
        ceilings = []

        def bounded(request):
            ceilings.append(request.max_response_bytes)
            self.assertEqual(request.max_response_bytes, 128)
            result = self.response(request)
            assert result.wire_bytes is not None
            self.assertGreater(result.wire_bytes, request.max_response_bytes)
            raise TimeoutError("synthetic-wire-ceiling")

        self.transport.side_effect = bounded
        self.refuse(lambda: self.collect(plan, self.consent(plan)))
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(ceilings, [128])
        self.assertEqual(self.output.read_bytes(), b"")

    def test_transport_allowance_shrinks_before_next_response_allocation(self):
        plan, _ = self.inputs()
        first = reader.canonical(envelope(self.rows(self.queries[0])))
        plan["maxTotalBytes"] = len(first) + 101
        remaining = [plan["maxTotalBytes"]]
        allowances = []

        def bounded(request):
            wire_limit = request.max_response_bytes
            allowances.append(wire_limit)
            self.assertEqual(wire_limit, min(plan["maxResponseBytes"], remaining[0]))
            result = self.response(request)
            assert result.wire_bytes is not None
            if result.wire_bytes > wire_limit:
                raise TimeoutError("synthetic-wire-budget")
            remaining[0] -= result.wire_bytes
            return result

        self.transport.side_effect = bounded
        self.refuse(lambda: self.collect(plan, self.consent(plan)))
        self.assertEqual(allowances, [len(first) + 101, 1])
        self.assertEqual(self.transport.call_count, 2)
        self.assertEqual(self.output.read_bytes(), b"")

    def test_exhausted_aggregate_wire_budget_prevents_next_dispatch(self):
        plan, _ = self.inputs()
        first = reader.canonical(envelope(self.rows(self.queries[0])))
        plan["maxTotalBytes"] = len(first) + 100

        def bounded(request):
            result = self.response(request)
            self.assertLessEqual(result.wire_bytes, request.max_response_bytes)
            return result

        self.transport.side_effect = bounded
        self.refuse(lambda: self.collect(plan, self.consent(plan)))
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.output.read_bytes(), b"")
        states = [json.loads(line)["state"] for line in self.journal.read_text().splitlines()]
        self.assertEqual(states.count("intent"), 1)

    def test_wrong_query_prefix_refuses_before_credential(self):
        plan, _ = self.inputs()
        plan["queries"][0] = "DELETE FROM sample"
        self.refuse(lambda p=plan: self.collect(p, self.consent(p)))
        self.credential.assert_not_called()
        self.transport.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_serialized_or_arbitrary_isolated_permit_refuses_before_token(self):
        plan, consent = self.inputs()
        for permit in (None, True, {"qualified": True}, object()):
            self.refuse(
                lambda p=permit: reader.collect_isolated(
                    plan,
                    reader.digest(plan),
                    consent,
                    self.credential,
                    self.output,
                    self.journal,
                    permit=p,
                    now=lambda: NOW,
                    clock=lambda: 100.0,
                )
            )
            self.credential.assert_not_called()
            self.assertFalse(self.output.exists())

    def test_query_plan_mismatch_never_dispatches_unapproved_sql(self):
        plan, _ = self.inputs()
        plan["queries"][3] = "SELECT 'synthetic-wrong-query'"
        self.refuse(lambda p=plan: self.collect(p, self.consent(p)))
        self.assertEqual(self.transport.call_count, 3)
        self.assertEqual(self.output.read_bytes(), b"")

    def test_post_response_deadline_leaves_no_success(self):
        def late(request):
            result = self.response(request)
            moment[0] = NOW + timedelta(minutes=11)
            return result

        moment = [NOW]
        self.transport.side_effect = late
        self.refuse(lambda: self.collect(now=lambda: moment[0]))
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertIn("aborted_no_replay", self.journal.read_text())

    def test_source_change_after_dispatch_aborts_without_private_output(self):
        plan, consent = self.inputs()
        pinned = reader.source_sha256()
        with patch.object(reader, "source_sha256", return_value=pinned) as source:

            def changed(request):
                response = self.response(request)
                source.return_value = {}
                return response

            self.transport.side_effect = changed
            self.refuse(lambda: self.collect(plan, consent))
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertIn("aborted_no_replay", self.journal.read_text())

    def test_existing_sink_is_preserved_before_token(self):
        self.output.write_text(MARKER)
        self.refuse(self.collect)
        self.credential.assert_not_called()
        self.assertEqual(self.output.read_text(), MARKER)


if __name__ == "__main__":
    unittest.main()
