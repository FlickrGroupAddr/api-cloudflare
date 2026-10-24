"""Independent exact inherited-method accounting and refusal checks.

MIT License; copyright 2026 Terry Ott. Public source reads only, no dispatch.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import contracts
from contracts import AtomicAttempt, inherited_fit, verify_attempt
from runner import Refusal


class InheritedContractTests(unittest.TestCase):
    def test_composite_native_interfaces_cannot_claim_one_atomic_request(self):
        for method in ("publishReviewedEvidence", "PartitionWorker.acquireFresh"):
            path = contracts.CONTRACTS[method]
            pin = hashlib.sha256((contracts.ROOT / path).read_bytes()).hexdigest()
            attempt = AtomicAttempt(method, pin, "synthetic-resource", 1, 1, 1, 0, 0, 0)
            with self.subTest(method=method), self.assertRaises(Refusal):
                verify_attempt(attempt, {path: pin})

    def test_full_candidate_is_precise_source_only_no_fit_not_fresh_headroom(self):
        report = inherited_fit()
        self.assertEqual(report["domain_tables"], 66)  # Whole source census, no table dropped.
        self.assertEqual(report["included_application_tables"], 65)
        self.assertEqual(report["observable_schema_tables"], 66)
        self.assertEqual(report["domain_schema_objects"], 717)
        self.assertFalse(report["fits"])
        self.assertFalse(report["dispatch_enabled"])
        self.assertEqual(report["qualification"], "NO_GO")
        self.assertEqual(report["actual_campaign_headroom"], "UNKNOWN")
        self.assertEqual((report["outer_run_ceiling"], report["outer_capture_ceiling"]), (24, 72))

    def test_catalogue_method_pins_do_not_authenticate_caller_cost_claims(self):
        for method, path in contracts.CONTRACTS.items():
            with self.subTest(method=method):
                pin = hashlib.sha256((contracts.ROOT / path).read_bytes()).hexdigest()
                leaf = AtomicAttempt(method, pin, "synthetic-exact-resource", 1, 1, 1, 0, 0, 0)
                with self.assertRaisesRegex(Refusal, "expanded_native_leaf_required"):
                    verify_attempt(leaf, {path: pin})
                with self.assertRaises(Refusal):
                    verify_attempt(leaf, {})
                with self.assertRaises(Refusal):
                    verify_attempt(leaf, {path: "0" * 64})

    def test_unknown_work_is_not_silently_zero_or_one_aggregate_request(self):
        method, path = next(iter(contracts.CONTRACTS.items()))
        pin = hashlib.sha256((contracts.ROOT / path).read_bytes()).hexdigest()
        leaf = AtomicAttempt(method, pin, "synthetic-exact-resource", 1, 1, 8, 0, 65536, 262144)
        with self.assertRaisesRegex(Refusal, "expanded_native_leaf_required"):
            verify_attempt(leaf, {path: pin})
        for change in (
            {"requests": 2},
            {"statements": 9},
            {"effect_events": None},
            {"outbound_wire_bytes": None},
            {"inbound_wire_bytes": None},
            {"outbound_wire_bytes": 65537},
            {"inbound_wire_bytes": 262145},
            {"method": "fictional.aggregate.upload_deploy_capture_restore"},
            {"resource": ""},
            {"ordinal": 0},
            {"statements": True},
        ):
            with self.subTest(change=change), self.assertRaises(Refusal):
                verify_attempt(dataclasses.replace(leaf, **change), {path: pin})


class NativeProgramTests(unittest.TestCase):
    """Public-source tree inspection only; never an observed native trace."""

    def setUp(self):
        self.native = importlib.import_module("native_program")
        self.pins = self.native.retained_source_pins()
        self.binding = self.native.fixture_binding()
        self.program = self.native.source_program(1, self.binding, self.pins)

    def nodes(self, roots):
        for node in roots:
            yield node
            yield from self.nodes(node.children)

    def test_all_twelve_exact_source_inspections_keep_unknown_costs_and_no_dispatch(self):
        for number in range(1, 13):
            with self.subTest(case=number):
                program = self.native.source_program(number, self.binding, self.pins)
                self.native.validate_native_program(program)
                trace = self.native.inert_trace(program)
                self.assertEqual(trace["scope"], "SOURCE_COMPOSITION_INSPECTION_ONLY")
                self.assertEqual(
                    (trace["qualification"], trace["dispatch_enabled"]), ("NO_GO", False)
                )
                self.assertEqual(
                    (trace["effects"], trace["wire_bytes"], trace["allocation"]),
                    ("UNKNOWN", "UNKNOWN", "UNRESOLVED"),
                )
                selected = self.native.leaves(program)
                self.assertEqual(len(trace["ordered_leaves"]), len(selected))
                self.assertEqual(len(set(trace["leaf_paths"])), len(selected))
                self.assertTrue(trace["unresolved"])

    def test_publication_has_four_distinct_ordered_batch_expression_groups(self):
        publications = [
            n for n in self.nodes(self.program.roots) if n.method == "publishReviewedEvidence"
        ]
        self.assertTrue(publications)
        for publication in publications:
            self.assertEqual(
                tuple(c.path[-1] for c in publication.children),
                ("publish", "summary", "readback", "final"),
            )
            self.assertEqual(tuple(len(c.sql) for c in publication.children), (3, 1, 3, 1))
            self.assertTrue(all(c.method == "D1.session.batch" for c in publication.children))

    def test_acquisition_keeps_rpc_consume_and_full_boundary_refinement_separate(self):
        acquisitions = [
            n for n in self.nodes(self.program.roots) if n.method == "PartitionWorker.acquireFresh"
        ]
        self.assertTrue(acquisitions)
        for acquisition in acquisitions:
            children = acquisition.children
            self.assertEqual(
                tuple(c.path[-1] for c in children), ("rpc", "owner-consume", "native")
            )
            consume = children[1]
            self.assertEqual(len(consume.children), 3)
            self.assertEqual(sum(len(c.sql) for c in consume.children), 6)
            self.assertTrue(
                any(
                    n.refinement == "exact-boundary-manifest-required"
                    for n in self.nodes((acquisition,))
                )
            )

    def test_partial_reordered_or_changed_leaf_program_cannot_validate(self):
        first = self.program.roots[0]
        variants = (
            dataclasses.replace(self.program, roots=self.program.roots[:-1]),
            dataclasses.replace(self.program, roots=tuple(reversed(self.program.roots))),
            dataclasses.replace(
                self.program,
                roots=(
                    dataclasses.replace(first, children=first.children[:-1]),
                    *self.program.roots[1:],
                ),
            ),
            dataclasses.replace(
                self.program,
                roots=(dataclasses.replace(first, source_pin="0" * 64), *self.program.roots[1:]),
            ),
            dataclasses.replace(
                self.program,
                roots=(
                    dataclasses.replace(first, resource="replacement-resource"),
                    *self.program.roots[1:],
                ),
            ),
            dataclasses.replace(
                self.program,
                roots=(
                    dataclasses.replace(first, sql=("SELECT arbitrary",), refinement="exact"),
                    *self.program.roots[1:],
                ),
            ),
        )
        for value in variants:
            with self.subTest(value=value.roots[0].identity), self.assertRaises(Refusal):
                self.native.validate_native_program(value)

    def test_caller_sql_missing_sources_and_mixed_profiles_refuse(self):
        for kwargs in (
            {"approved_reads": ("SELECT arbitrary",)},
            {"chunk_count": 0},
            {"kv_pages": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(Refusal):
                self.native.source_program(1, self.binding, self.pins, **kwargs)
        missing = dict(self.pins)
        missing.pop(next(iter(missing)))
        with self.assertRaises(Refusal):
            self.native.source_program(1, self.binding, missing)
        with self.assertRaises(Refusal):
            self.native.source_program(
                1, dataclasses.replace(self.binding, profile="legacy-exact-real"), self.pins
            )

    def test_source_change_invalidates_retained_native_program(self):
        original = contracts.Path.read_bytes

        def changed(path):
            data = original(path)
            return data + b"\n// synthetic-source-drift\n" if path.name == "operator.ts" else data

        with patch.object(contracts.Path, "read_bytes", changed), self.assertRaises(Refusal):
            self.native.validate_native_program(self.program)

    def test_native_program_and_contract_implementation_are_in_source_closure(self):
        pins = dict(self.program.source_pins)
        self.assertIn("probes/pmb1-finite-runner/native_program.py", pins)
        self.assertIn("probes/pmb1-finite-runner/contracts.py", pins)

    def test_main_assessment_contains_complete_134_query_source_tree(self):
        domain = [
            node
            for node in self.nodes(self.program.roots)
            if node.method == "D1.session.prepare.all" and node.resource == "domain-d1"
        ]
        self.assertEqual(len(domain), 134)
        self.assertTrue(all(len(node.sql) == 1 for node in domain))
        plan = json.loads(
            (contracts.ROOT / "probes/pmb1-native-disposition/domain-plan.json").read_bytes()
        )
        reads = {node.path[-2] for node in domain if node.path[-1] == "read"}
        self.assertEqual(reads, set(plan["tables"]) | {"schema-before", "schema-after"})

    def test_operator_helper_steps_are_wired_to_the_same_exact_native_binding(self):
        operator = importlib.import_module("native_operator")
        inputs = self.program.binding.operator
        self.assertIsNotNone(inputs)
        steps = operator.build_operator_steps(inputs)
        nodes = tuple(self.nodes(self.program.roots))
        for step in steps:
            with self.subTest(step=step.name):
                selected = [node for node in nodes if node.path[-1] == step.name]
                self.assertEqual(len(selected), 1)
                self.assertEqual(selected[0].method, step.method)
                actual = tuple(
                    (leaf.method, leaf.resource)
                    for leaf in selected[0].children
                    if leaf.method != "D1.prepare.first"
                )
                expected = tuple(
                    (leaf.method + " " + leaf.path, leaf.resource) for leaf in step.leaves
                )
                self.assertEqual(actual, expected)

    def test_operational_tree_has_no_fictional_readback_or_fresh_fixture_actions(self):
        methods = [node.method for node in self.nodes(self.program.roots)]
        self.assertFalse(
            "operator.exact-status-and-receipts" in methods,
            "fictional aggregate readback remains in the operational tree",
        )
        self.assertFalse(
            any(method.startswith("external-journal.") for method in methods),
            "operational journal leaves must name the actual broker methods",
        )
        self.assertFalse(
            any(method.startswith("rehearse") for method in methods),
            "fresh Source fixtures are tests, not bound-state operational methods",
        )

    def test_case7_delayed_generations_are_bound_after_exact_restore_readback(self):
        program = self.native.source_program(7, self.binding, self.pins)
        selected = [
            node
            for node in self.nodes(program.roots)
            if node.method == "invokeInheritedNativeChallenge:7:post-restore"
        ]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].path[1], "restored")
        phases = [node.method for node in program.roots]
        self.assertLess(phases.index("restore_readback"), phases.index("restored"))
        self.assertLess(phases.index("restored"), phases.index("cleanup"))
        self.assertTrue(selected[0].source_path.endswith("native_dispatch.ts"))

    def test_full_candidate_fit_still_fences_every_native_execution(self):
        with self.assertRaisesRegex(
            Refusal, "selected_candidate_exceeds_accepted_miniature_allocation"
        ):
            self.native.execute_native(self.program)

    def test_native_dispatch_stays_disabled_even_under_invented_fit(self):
        with patch.object(contracts, "inherited_fit", return_value={"fits": True}):
            with self.assertRaisesRegex(Refusal, "provider_dispatch_disabled"):
                self.native.execute_native(self.program)

    def test_unqualified_native_tree_cannot_zero_admit_unknown_wire_or_effect_costs(self):
        journal_module = importlib.import_module("native_journal")
        lease = self.native.make_native_lease(self.program)
        self.assertTrue(lease.leaves)
        self.assertTrue(all(leaf.cost is None for leaf in lease.leaves))
        with tempfile.TemporaryDirectory() as folder:
            broker = journal_module.SQLiteNativeBroker(Path(folder) / "external.sqlite")
            try:
                with patch.object(contracts, "inherited_fit", return_value={"fits": True}):
                    with self.assertRaises(Refusal):
                        self.native.execute_native(self.program, journal=broker)
                self.assertEqual(broker.observe()["status"], "unreserved")
                self.assertIsNone(broker.observe()["reserved"])
            finally:
                broker.close()


class OperatorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.operator = importlib.import_module("native_operator")
        self.inputs = self.operator.fixture_inputs()
        self.network = patch.object(socket, "getaddrinfo", side_effect=AssertionError("no DNS"))
        self.network.start()
        self.addCleanup(self.network.stop)
        transport = patch(
            "scripts.hosted_publisher_provider.https_transport",
            side_effect=AssertionError("no real provider transport"),
        )
        transport.start()
        self.addCleanup(transport.stop)

    def test_inherited_operator_fragments_count_each_real_nested_source_request(self):
        for fragment, count in (("temporary", 12), ("stop", 15), ("cleanup", 18), ("restore", 26)):
            with self.subTest(fragment=fragment):
                result = self.operator.exercise_synthetic(fragment)
                self.assertEqual(result.outcome, "synthetic_complete")
                self.assertEqual(result.requests, count)
                self.assertEqual(len(result.keys), count)
                self.assertEqual(len(set(result.keys)), count)
                self.assertFalse(result.dispatch_enabled)
                self.assertIsNone(result.actual_wire_bytes)
                self.assertIsNone(result.actual_effects)

    def test_restore_graph_is_exact_nonforced_retained_target_and_separate_intent(self):
        steps = {step.name: step for step in self.operator.build_operator_steps(self.inputs)}
        initial, restore = steps["temporary.deploy"].leaves, steps["restore.deploy"].leaves
        self.assertEqual(tuple(leaf.method for leaf in initial), ("GET", "GET", "POST", "GET"))
        self.assertEqual(tuple(leaf.method for leaf in restore), ("GET", "GET", "POST", "GET"))
        self.assertEqual(initial[2].version, self.inputs.temporary_version_id)
        self.assertEqual(restore[2].version, self.inputs.retained_version_id)
        self.assertNotEqual(initial[2].key, restore[2].key)
        self.assertTrue(
            all(
                "force" not in leaf.path and "latest" not in leaf.path
                for step in steps.values()
                for leaf in step.leaves
            )
        )
        self.assertTrue(
            all(
                leaf.effects is None and leaf.wire_bytes is None
                for step in steps.values()
                for leaf in step.leaves
            )
        )

    def test_operator_request_cap_cannot_borrow_an_unallocated_restore_slot(self):
        result = self.operator.exercise_synthetic("restore", max_requests=9)
        self.assertEqual((result.requests, result.outcome), (9, "synthetic_refused"))
        self.assertNotIn("restore:deploy", result.keys)

    def test_lost_ack_never_dispatches_restore_or_replays_its_effect(self):
        for fault, terminal in (
            ("lost_deployment", "temporary:deploy"),
            ("lost_restore", "restore:deploy"),
        ):
            with self.subTest(fault=fault):
                result = self.operator.exercise_synthetic("restore", fault=fault)
                self.assertEqual(result.outcome, "synthetic_unknown_no_replay")
                self.assertEqual(result.keys[-1], terminal)
                self.assertEqual(result.keys.count(terminal), 1)
                self.assertNotIn("cleanup:delete", result.keys)

    def test_wrong_returned_identity_and_receipt_expiry_stop_the_source_program(self):
        for kwargs in ({"fault": "wrong_version"}, {"fault": "wrong_worker"}, {"expire_after": 4}):
            with self.subTest(kwargs=kwargs):
                result = self.operator.exercise_synthetic("restore", **kwargs)
                self.assertEqual(result.outcome, "synthetic_unknown_no_replay")
                self.assertNotIn("restore:deploy", result.keys)

    def test_public_restore_program_stays_disabled_before_untrusted_context(self):
        class Untrusted:
            def require_authenticated_root_context(self, *args):
                raise AssertionError("untrusted context was consulted")

        for program in (
            self.operator.ProspectiveRestoreProgram(),
            self.operator.ProspectiveRestoreProgram(object(), Untrusted()),
        ):
            with self.assertRaisesRegex(self.operator.OperatorRefused, "dispatch_disabled"):
                program.restore_retained_version({}, {}, {}, key="restore:deploy")

    def test_copied_source_preflight_cannot_authorize_even_source_restore(self):
        original = self.operator.ProspectiveSourceProvider.restore_retained_version

        def copied(provider, identity, version, preflight, *, key):
            return original(provider, identity, version, dataclasses.replace(preflight), key=key)

        with patch.object(
            self.operator.ProspectiveSourceProvider, "restore_retained_version", copied
        ):
            result = self.operator.exercise_synthetic("restore")
        self.assertEqual(result.outcome, "synthetic_refused")
        self.assertNotIn("restore:deploy:version", result.keys)


class DurableOperatorBridgeTests(unittest.TestCase):
    def setUp(self):
        self.native = importlib.import_module("native_program")
        self.operator = importlib.import_module("native_operator")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "external-broker.sqlite"

    def test_each_inherited_transport_effect_sees_exact_committed_intent_first(self):
        observed = []
        expected = ("fixture:worker", "worker:inspect", "worker:disable:identity", "worker:disable")
        original = self.operator.InventedProviderIO.__call__

        def observed_transport(io, *args, **kwargs):
            broker = self.native.SQLiteNativeBroker(self.path)
            try:
                state = broker.observe()
                ordinal = len(observed)
                self.assertEqual(state["status"], "dispatching")
                self.assertEqual(state["next_ordinal"], ordinal)
                self.assertEqual(state["leaves"][ordinal]["identity"], expected[ordinal])
                self.assertEqual(state["leaves"][ordinal]["status"], "dispatching")
                observed.append(ordinal)
            finally:
                broker.close()
            return original(io, *args, **kwargs)

        with patch.object(self.operator.InventedProviderIO, "__call__", observed_transport):
            result = self.native.rehearse_durable_operator(self.path)
        self.assertEqual(observed, [0, 1, 2, 3])
        self.assertEqual(result["scope"], "KNOWN_SOURCE_MODEL_ONLY")
        self.assertEqual(result["qualification"], "NO_GO")
        self.assertEqual((result["outcome"], result["requests"]), ("known_source_complete", 4))
        self.assertEqual(result["journal"]["status"], "complete")
        self.assertGreater(result["retained_evidence_bytes"], 0)
        self.assertEqual(
            (result["actual_wire"], result["actual_provider_effects"], result["actual_headroom"]),
            ("UNKNOWN", "UNKNOWN", "UNKNOWN"),
        )

    def test_lost_durable_finish_ack_stops_effects_and_cold_new_key_replay(self):
        result = self.native.rehearse_durable_operator(self.path, fault="lost_finish_ack")
        self.assertEqual((result["outcome"], result["requests"]), ("unknown", 1))
        self.assertEqual(result["journal"]["status"], "unknown")
        self.assertEqual(result["journal"]["reserved"]["requests"], 4)
        with self.assertRaises(Refusal):
            self.native.rehearse_durable_operator(self.path)

    def test_failed_begin_never_reaches_even_the_invented_transport(self):
        with patch.object(
            self.native.SQLiteNativeBroker,
            "begin",
            side_effect=Refusal("invented-preintent-refusal"),
        ):
            with patch.object(
                self.operator.InventedProviderIO,
                "__call__",
                side_effect=AssertionError("effect before intent"),
            ):
                result = self.native.rehearse_durable_operator(self.path)
        self.assertEqual((result["outcome"], result["requests"]), ("unknown", 0))
        self.assertEqual(result["journal"]["status"], "unknown")
        self.assertEqual(result["journal"]["reserved"]["requests"], 4)


class DirectInheritedWiringTests(unittest.TestCase):
    def call_source_function(self, name):
        self.assertIn(
            name,
            ("rehearseInheritedSource", "rehearseClosedRestorationCheck", "rehearseNativeFailure"),
        )
        node = shutil.which("node")
        self.assertIsNotNone(node, "pinned Node24.22.0 must be on PATH")
        assert node
        version = subprocess.run(
            [node, "--version"], capture_output=True, text=True, check=True, timeout=10
        )
        self.assertEqual(version.stdout.strip(), "v24.22.0")
        module = (contracts.ROOT / "probes/pmb1-finite-runner/native_composition.ts").as_uri()
        script = """
          const m = await import(process.argv[1]);
          let disabled = false;
          try { m.executeNative(); } catch (error) {
            disabled = error.message === 'provider_dispatch_disabled';
          }
          let report;
          if (process.argv[2] === 'rehearseNativeFailure') {
            report = [];
            const tools=process.env.PMB1_SOURCE_TEST_UV&&process.env.PMB1_SOURCE_TEST_UV_CACHE
              ?{uvExecutable:process.env.PMB1_SOURCE_TEST_UV,
                cacheDirectory:process.env.PMB1_SOURCE_TEST_UV_CACHE}:undefined;
            for (let n = 2; n <= 12; n++) {
              try { report.push(await m.rehearseNativeFailure(n,tools)); }
              catch (error) { report.push({caseNumber:n, sourceError:error.message}); }
            }
          } else { report = await m[process.argv[2]](); }
          console.log(JSON.stringify({disabled, report}));
        """
        completed = subprocess.run(
            [node, "--input-type=module", "--eval", script, module, name],
            cwd=contracts.ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=True,
        )
        observed = json.loads(completed.stdout)
        self.assertTrue(observed["disabled"])
        return observed["report"]

    def test_actual_inherited_code_rehearsal_is_source_only_and_counts_nested_calls(self):
        report = self.call_source_function("rehearseInheritedSource")
        self.assertEqual(report["scope"], "SOURCE_SYNTHETIC_WIRING_ONLY")
        self.assertEqual(report["qualification"], "NO_GO")
        self.assertFalse(report["actualDispatchEnabled"])
        self.assertEqual(
            (report["actualWire"], report["actualEffects"], report["actualHeadroom"]),
            ("UNKNOWN", "UNKNOWN", "UNKNOWN"),
        )
        self.assertEqual((report["publicationBatches"], report["objects"]), (4, 2))
        self.assertEqual(report["domainTables"], 65)
        self.assertEqual(report["mainSequence"], ["currentMain", "stopAdmission", "assessStopped"])
        self.assertEqual(report["ownerControls"], ["maintenanceStop", "maintenanceClose"])
        proof = report["closedSourcePreflight"]
        self.assertEqual(proof["scope"], "SOURCE_SYNTHETIC_WIRING_ONLY")
        self.assertFalse(proof["actualQualification"])
        self.assertEqual(
            (proof["custody"], proof["allWriterQualification"]), ("UNKNOWN", "UNKNOWN")
        )
        self.assertEqual(
            proof["readbackSha2_256"], hashlib.sha256(proof["readbackText"].encode()).hexdigest()
        )
        readback = json.loads(proof["readbackText"])
        self.assertEqual(readback["owner"]["rows"], [{"generation": "3", "state": "closed"}])
        self.assertIs(readback["owner"]["admission"], False)
        self.assertEqual(readback["main"]["state"], "stopped")
        self.assertEqual(readback["main"]["target"]["versionId"], proof["retainedVersion"])
        self.assertEqual(readback["main"]["target"]["candidate"], proof["sourceContext"])
        self.assertGreater(proof["throughMs"], proof["observedAtMs"])
        self.assertLessEqual(proof["throughMs"] - proof["observedAtMs"], 60000)
        self.assertEqual(
            proof["moduleSourceSha2_256"],
            hashlib.sha256(
                (contracts.ROOT / "probes/pmb1-finite-runner/native_composition.ts").read_bytes()
            ).hexdigest(),
        )
        trace = report["trace"]
        self.assertEqual([leaf["ordinal"] for leaf in trace], list(range(1, len(trace) + 1)))
        publication = [
            leaf
            for leaf in trace
            if leaf["parent"] == "publication" and leaf["method"] == "D1.session.batch"
        ]
        self.assertEqual(len(publication), 4)
        self.assertTrue(all(leaf["method"] == "D1.session.batch" for leaf in publication))
        self.assertEqual(
            sum(leaf["statements"] for leaf in publication), report["publicationStatements"]
        )
        calls = {leaf["method"] for leaf in trace}
        self.assertIn("metering.sql.exec", calls)
        parents = [leaf["parent"] for leaf in trace]
        self.assertLess(parents.index("main-current"), parents.index("main-stop"))
        self.assertLess(parents.index("main-stop"), parents.index("main-assess"))
        self.assertLess(parents.index("owner-stop"), parents.index("owner-close"))
        self.assertTrue(
            {
                "PartitionWorker.acquireFresh",
                "storage.sql.exec",
                "transaction.list",
                "transaction.getAlarm",
            }.issubset(calls)
        )
        rpc = [leaf for leaf in trace if leaf["method"] == "PartitionWorker.acquireFresh"]
        self.assertEqual(len({leaf["resource"] for leaf in rpc}), 2)
        self.assertTrue(all(leaf["status"] == "confirmed" for leaf in trace))
        self.assertTrue(all(leaf["wireBytes"] == "UNKNOWN" for leaf in trace))
        for leaf in trace:
            self.assertRegex(leaf["requestDigest"], r"^[a-f0-9]{64}$")
            self.assertGreaterEqual(leaf["retainedRequestBytes"], 0)
            self.assertGreaterEqual(leaf["retainedResponseBytes"], 0)

    def test_closed_authentication_uses_real_handler_and_preserves_exact_response(self):
        report = self.call_source_function("rehearseClosedRestorationCheck")
        self.assertEqual(report["scope"], "SOURCE_SYNTHETIC_WIRING_ONLY")
        self.assertEqual(report["qualification"], "NO_GO")
        self.assertEqual(report["actualEdge"], "UNKNOWN")
        self.assertEqual(report["status"], 200)
        self.assertEqual(report["headers"]["cache-control"], "no-store")
        self.assertEqual(report["headers"]["x-content-type-options"], "nosniff")
        self.assertEqual(report["headers"]["referrer-policy"], "no-referrer")
        self.assertTrue(report["headers"]["content-type"].startswith("application/json"))
        self.assertEqual(
            hashlib.sha256(report["bodyText"].encode()).hexdigest(), report["bodyDigest"]
        )
        self.assertEqual(
            json.loads(report["bodyText"]),
            {
                "schemaVersion": 1,
                "installationId": "installation",
                "installationRevision": 7,
                "installationState": "active",
                "presentedCredentialState": "current",
            },
        )
        trace = report["trace"]
        lookups = [leaf for leaf in trace if leaf["method"] == "D1.prepare.all"]
        self.assertEqual(len(lookups), 1)
        self.assertEqual(lookups[0]["statements"], 1)
        self.assertEqual(lookups[0]["effectEvents"], 0)
        self.assertTrue(all(leaf["status"] == "confirmed" for leaf in trace))
        self.assertTrue(all(leaf["wireBytes"] == "UNKNOWN" for leaf in trace))

    def test_fixed_native_failure_branches_stop_at_their_declared_outcome(self):
        reports = self.call_source_function("rehearseNativeFailure")
        self.assertEqual([report["caseNumber"] for report in reports], list(range(2, 13)))
        for report in reports:
            number = report["caseNumber"]
            with self.subTest(case=number):
                self.assertNotIn("sourceError", report, report.get("sourceError", ""))
                self.assertEqual(report["scope"], "SOURCE_SYNTHETIC_WIRING_ONLY")
                self.assertEqual(report["qualification"], "NO_GO")
                self.assertEqual(
                    (report["actualWire"], report["actualCustody"]), ("UNKNOWN", "UNKNOWN")
                )
                self.assertEqual(
                    report["outcome"],
                    "known-violation-detected" if number in (10, 11) else "closed-refusal",
                )
                self.assertTrue(report["reason"])
                trace = report["trace"]
                self.assertEqual(
                    [leaf["ordinal"] for leaf in trace], list(range(1, len(trace) + 1))
                )
                self.assertTrue(all(leaf["status"] == "confirmed" for leaf in trace))
                self.assertTrue(all(leaf["wireBytes"] == "UNKNOWN" for leaf in trace))
                parents = [leaf["parent"] for leaf in trace]
                self.assertLess(
                    parents.index(f"case{number}.stop"), parents.index(f"case{number}.close")
                )
                if number == 2:
                    self.assertLess(
                        parents.index("case2.admitted-before-close"), parents.index("case2.close")
                    )
                if number == 4:
                    self.assertEqual(trace[-1]["method"], "source-fault.lost-close-ack")
                    self.assertIn("no-replay", report["reason"])
                if number == 6:
                    position = next(
                        i
                        for i, leaf in enumerate(trace)
                        if leaf["method"] == "RuntimeEvidenceLedger.reserve"
                    )
                    tail = trace[position:]
                    self.assertEqual(sum(leaf["method"] == "D1.session.batch" for leaf in tail), 1)
                    self.assertFalse(any(leaf["method"] == "storage.sql.exec" for leaf in tail))
                    self.assertIn("expired", report["reason"])
                if number == 7:
                    restoration = report["restoration"]
                    self.assertIs(restoration["actualQualification"], False)
                    self.assertEqual(
                        restoration["nativeBeforeSha2_256"], restoration["nativeAfterSha2_256"]
                    )
                    self.assertEqual(
                        restoration["deployment"]["versions"],
                        [
                            {
                                "version_id": restoration["expectedRetainedVersion"],
                                "percentage": 100,
                            }
                        ],
                    )
                    self.assertEqual(restoration["requests"], 26)
                    self.assertIn("restore:deployment:current", restoration["keys"])
                    self.assertLess(
                        parents.index("case7.exact-retained-provider-restore"),
                        parents.index("case7.exact-retained-provider-readback"),
                    )
                    self.assertLess(
                        parents.index("case7.exact-retained-provider-readback"),
                        parents.index("case7.post-restore-delayed-generations"),
                    )
                    self.assertEqual(
                        report["controlAttempts"],
                        [
                            {"method": "maintenanceStop", "generation": "1", "outcome": "refused"},
                            {"method": "maintenanceStop", "generation": "2", "outcome": "refused"},
                        ],
                    )
                if number in (10, 11):
                    self.assertGreater(
                        sum(
                            leaf["effectEvents"]
                            for leaf in trace
                            if leaf["parent"] == f"case{number}.challenge"
                        ),
                        0,
                    )
                if number == 12:
                    self.assertEqual(trace[-1]["method"], "source-fault.partial-output")
                    self.assertIn("no-later-work", report["reason"])


class ReviewedDispatchTests(unittest.TestCase):
    """Guard probes use effect traps, never fabricated actual Root authority."""

    def run_node(self, script):
        node = shutil.which("node")
        self.assertIsNotNone(node)
        assert node
        version = subprocess.run(
            [node, "--version"], capture_output=True, text=True, check=True, timeout=10
        )
        self.assertEqual(version.stdout.strip(), "v24.22.0")
        module = (contracts.ROOT / "probes/pmb1-finite-runner/native_dispatch.ts").as_uri()
        composition = (contracts.ROOT / "probes/pmb1-finite-runner/native_composition.ts").as_uri()
        completed = subprocess.run(
            [node, "--input-type=module", "--eval", script, module, composition],
            cwd=contracts.ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
        return json.loads(completed.stdout)

    def test_default_inert_entry_never_reads_bindings_or_journal_objects(self):
        report = self.run_node("""
          const m = await import(process.argv[1]); let effects=0; const reasons=[];
          const trap=new Proxy({}, {get(){effects++;throw Error('unexpected-object-read');}});
          for (const args of [[], [undefined,true], [trap,false], [trap]]) {
            try { await m.executeReviewedNativeProgram(...args); reasons.push('ADMITTED'); }
            catch(error) { reasons.push(error.message); }
          }
          console.log(JSON.stringify({effects,reasons}));
        """)
        self.assertEqual(report["effects"], 0)
        self.assertEqual(report["reasons"], ["native_dispatch_disabled"] * 4)

    def test_malformed_unreviewed_and_unknown_native_facts_refuse_before_effects(self):
        report = self.run_node("""
          const m=await import(process.argv[1]); const reports=[];
          const names=['unreviewed','NaN-start','infinite-deadline','NaN-case','wrong-stage',
            'wrong-step','unknown-cost','full-fit','future-window','same-reviewer','bad-scope',
            'root-return-flag','root-return-promise'];
          for(const name of names){
            let sdk=0,journal=0,root=0;
            const denied=()=>{journal++;throw Error('UNEXPECTED_JOURNAL');};
            const costs={requests:1,reader_queries:0,receipt_reads:0,metadata_reads:1,
              authenticated_checks:0,
              mutations:0,creates:0,deletes:0,sql_statements:1,effects:0,outbound_bytes:10,
              inbound_bytes:10,artifact_bytes:16384,challenges:0,captures:0};
            const f={scope:'SOURCE_KNOWN_MODEL_ONLY',caseNumber:1,tableCount:1,schemaObjects:1,
              programDigest:'0'.repeat(64),packetDigest:'0'.repeat(64),population:['invented-object'],
              generations:['1'],rootRecord:'b'.repeat(64),reviewRecord:'c'.repeat(64),
              author:'source-author',reviewer:'source-reviewer',starts:0,deadline:100,
              baselineFreshness:60,baselineAt:null,restoredAt:null,
              lease:{key:'invented-guard-only',context_digest:'d'.repeat(64),source_pin:'a'.repeat(64),
                profile:'pmb1-private-application-no-real-v1',object_profile:'pmb1-private-object-kv-interface-v1',
                leaves:[{ordinal:0,identity:'guard-leaf',source_path:'invented/guard.ts',source_pin:'a'.repeat(64),
                  method:'D1.prepare.all',resource:'invented-d1',request_digest:'e'.repeat(64),cost:costs}]},
              calls:[{stage:'settle',firstLeaf:0,throughLeaf:0,step:{kind:'main-current',
                domainDatabaseId:'11111111-1111-4111-8111-111111111111',
                operationId:'22222222-2222-4222-8222-222222222222'}}],
              bindings:{main:{currentMain(){sdk++;throw Error('UNEXPECTED_SDK');}},
                owners:new Map()},
              journal:{reserve_tree:denied,begin_subtree:denied,finish_subtree:denied,mark_unknown:denied},
              root:{assertCurrent(){root++;throw Error('UNREVIEWED_ROOT');},
                armPhysicalFence(){throw Error('UNREVIEWED_FENCE');},
                verifyPhysicalReceipt(){throw Error('UNREVIEWED_ORACLE');}},
              clock:()=>10,sourceCheck:()=> 'a'.repeat(64)};
            f.programDigest=m.nativeProgramDigest(f);f.packetDigest=m.nativePacketDigest(f);
            if(name==='NaN-start')f.starts=NaN;
            if(name==='infinite-deadline')f.deadline=Infinity;
            if(name==='NaN-case')f.caseNumber=NaN;
            if(name==='wrong-stage')f.calls[0].stage='invented-stage';
            if(name==='wrong-step')f.calls[0].step.kind='arbitrary-operation';
            if(name==='unknown-cost')f.lease.leaves[0].cost=null;
            if(name==='full-fit'){f.tableCount=66;f.schemaObjects=717;}
            if(name==='future-window')f.starts=20;
            if(name==='same-reviewer')f.reviewer='SOURCE-AUTHOR';
            if(name==='bad-scope')f.scope='JSON_QUALIFIED_TRUE';
            if(name==='root-return-flag')f.root.assertCurrent=()=>{root++;return true;};
            if(name==='root-return-promise')f.root.assertCurrent=()=>{
              root++;return Promise.resolve(undefined);};
            let reason='ADMITTED';
            try{await m.executeReviewedNativeProgram(f,true);}
            catch(error){reason=error.message;}
            reports.push({name,reason,sdk,journal,root});
          }
          console.log(JSON.stringify(reports));
        """)
        for item in report:
            with self.subTest(case=item["name"]):
                self.assertNotEqual(item["reason"], "ADMITTED")
                self.assertEqual((item["sdk"], item["journal"]), (0, 0))
                if item["name"] == "unreviewed":
                    self.assertEqual(item["reason"], "UNREVIEWED_ROOT")
                    self.assertEqual(item["root"], 1)
                elif item["name"].startswith("root-return-"):
                    self.assertIn("synchronously", item["reason"])
                    self.assertEqual(item["root"], 1)
                else:
                    self.assertEqual(item["root"], 0)

    def test_fixed_real_sdk_dispatch_rehearsal_fences_every_selected_yield_fault(self):
        report = self.run_node("""
          const m=await import(process.argv[2]);const output=[];
          for(const fault of ['none','root-delay','reserve-delay','begin-delay','oracle-delay',
            'finish-delay','source-drift','descriptor-drift','unknown-cost','full-fit','future-baseline']){
            output.push({fault,...await m.rehearseReviewedNativeProgram(fault)});
          }
          console.log(JSON.stringify(output));
        """)
        for item in report:
            with self.subTest(fault=item["fault"]):
                self.assertEqual(item["scope"], "SOURCE_KNOWN_MODEL_ONLY")
                self.assertEqual(item["qualification"], "NO_GO")
                self.assertEqual(item["actualWire"], "UNKNOWN")
                self.assertTrue(item["dispatchBeforeSDK"])
                if item["fault"] == "none":
                    self.assertEqual(
                        (item["outcome"], item["sdkCalls"], item["journalStatus"]),
                        ("source_execution_complete", 1, "complete"),
                    )
                else:
                    self.assertIn(item["outcome"], ("refused", "unknown"))
                    self.assertTrue(item["reason"])
                    self.assertEqual(
                        item["sdkCalls"],
                        1 if item["fault"] in ("oracle-delay", "finish-delay") else 0,
                    )
                    self.assertNotEqual(item["journalStatus"], "complete")

    def test_case12_source_shape_reaches_declared_interruption_without_later_work(self):
        report = self.run_node("""
          const m=await import(process.argv[2]);
          console.log(JSON.stringify(await m.rehearseReviewedNativeProgram('case12')));
        """)
        # The factory exercises the QUALIFIED_ROOT validation branch using only
        # invented Source assessment/refs. It supplies no genuine Root authority.
        self.assertEqual(report["scope"], "SOURCE_KNOWN_MODEL_ONLY")
        self.assertEqual(report["qualification"], "NO_GO")
        self.assertEqual(
            (report["outcome"], report["reason"], report["journalStatus"]),
            ("unknown", "native_declared_partial_output", "unknown"),
        )
        self.assertEqual(
            report["executedStages"],
            [
                "settle",
                "close",
                "close",
                "closure_readback",
                "baseline",
                "interruption",
            ],
        )
        self.assertEqual(report["sdkCalls"], 8)
        self.assertTrue(report["dispatchBeforeSDK"])
        self.assertEqual(report["actualWire"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
