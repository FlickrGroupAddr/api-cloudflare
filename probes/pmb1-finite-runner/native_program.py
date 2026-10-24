"""Finite inherited SOURCE programs and exact, inert native operation trees.

MIT License; copyright 2026 Terry Ott. This module reads public SOURCE only.
The trace is a composition inspection, never observed native execution. Missing
transport, branch, SQL-metadata or effect qualification is represented explicitly
and prevents dispatch; it cannot be replaced with caller-provided counters.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import native_operator as operator
from native_journal import LeafIntent, NativeLease, SQLiteNativeBroker, lease_digest
from native_operator import OperatorInputs, build_operator_steps, fixture_inputs, loaded_source_pins
from runner import CASE_OBLIGATIONS, OBJECT_PROFILE, PROFILE, REQUIRED_STAGES, Cost, Refusal

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "program": "probes/pmb1-finite-runner/native_program.py",
    "composition": "probes/pmb1-finite-runner/native_composition.ts",
    "dispatch": "probes/pmb1-finite-runner/native_dispatch.ts",
    "contracts": "probes/pmb1-finite-runner/contracts.py",
    "operator": "probes/pmb1-finite-runner/native_operator.py",
    "native_journal": "probes/pmb1-finite-runner/native_journal.py",
    "provider_identity": "scripts/hosted_publisher_worker_identity.py",
    "provider_boundary": "scripts/hosted_publisher_provider.py",
    "operator_plan": "scripts/hosted_publisher_operator_plan.py",
    "native_fixture": "probes/pmb1-native-disposition/native-fixture.mjs",
    "fixture": "probes/pmb1-native-disposition/fixture.mjs",
    "fresh_fixture": "probes/pmb1-fresh-native-capture/fixture.mjs",
    "trusted_fixture": "probes/pmb1-retained-integration/trusted_inputs_fixture.mjs",
    "ledger_fixture": "probes/pmb1-runtime-evidence/fixture.mjs",
    "publication": "probes/pmb1-runtime-evidence/operator.ts",
    "publication_plan": "probes/pmb1-runtime-evidence/publication-plan.ts",
    "ledger": "probes/pmb1-runtime-evidence/ledger.ts",
    "source": "probes/pmb1-fresh-native-capture/source.ts",
    "owner": "probes/pmb1-fresh-native-capture/owner-core.ts",
    "partition": "probes/pmb1-fresh-native-capture/owning-core.ts",
    "main": "probes/pmb1-fresh-native-capture/main-private-core.ts",
    "journal": "probes/pmb1-native-journal/journal.ts",
    "control": "src/partition_maintenance.ts",
    "wakeup": "probes/pmb1-native-wakeup/candidate.ts",
    "native": "probes/pmb1-native-object-reader/native.ts",
    "boundary": "probes/pmb1-native-object-reader/object-kv-interface.ts",
    "reader": "probes/pmb1-no-real-object-reader/reader.ts",
    "facts": "probes/pmb1-retained-integration/runtime_facts.ts",
    "evidence_use": "probes/pmb1-fresh-native-capture/evidence-use.ts",
    "domain": "probes/pmb1-fresh-native-capture/domain.ts",
    "domain_plan": "probes/pmb1-native-disposition/domain-plan.json",
    "publisher": "scripts/hosted_publisher_worker_deployment.py",
    "restore": "scripts/fixed_origin_restore.py",
    "ordinary": "probes/pmb1-retained-integration/ordinary.ts",
    "binding": "probes/pmb1-native-d1-binding/binding.py",
}

_LOADED_PROGRAM = Path(__file__).read_bytes()
_LOADED_CONTRACTS = Path(__file__).with_name("contracts.py").read_bytes()


def retained_source_pins() -> dict[str, str]:
    """Current public bytes for SOURCE inspection, not independent acceptance."""
    pins = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCES.values()
    }
    # Preserve the complete unchanged inherited graph, not only catalogue tops.
    # The enclosing retained-manifest verifier still owns its independent pin.
    manifest = json.loads((ROOT / "probes/pmb1-finite-runner/source-pins.json").read_bytes())
    for name, record in manifest["sourceInputs"].items():
        if name.startswith("probes/pmb1-finite-runner/"):
            continue
        current = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if current != record["sha2_256"]:
            raise Refusal("native_inherited_complete_closure_drift")
        pins[name] = current
    for name, loaded_pin in loaded_source_pins():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != loaded_pin:
            raise Refusal("native_loaded_operator_dependency_drift")
        pins[name] = loaded_pin
    if (
        pins[SOURCES["program"]] != hashlib.sha256(_LOADED_PROGRAM).hexdigest()
        or pins[SOURCES["contracts"]] != hashlib.sha256(_LOADED_CONTRACTS).hexdigest()
    ):
        raise Refusal("native_loaded_implementation_source_drift")
    return pins


@dataclass(frozen=True)
class NativeBinding:
    source_pin: str
    profile: str
    object_profile: str
    population: tuple[str, ...]
    generations: tuple[str, ...]
    artifact: str
    configuration: str
    schema: str
    guards: str
    oracle: str
    operator: OperatorInputs | None = None


@dataclass(frozen=True)
class NativeLeaf:
    path: tuple[str, ...]
    method: str
    source_path: str
    source_pin: str
    resource: str
    identity: str
    sql: tuple[str, ...] = ()
    children: tuple[NativeLeaf, ...] = ()
    # Expression references are source-owned. They must be refined with exact
    # native statements/columns/arguments before any real request is admissible.
    refinement: str = "source-expression"


@dataclass(frozen=True)
class NativeProgram:
    case_number: int
    binding: NativeBinding
    roots: tuple[NativeLeaf, ...]
    source_pins: tuple[tuple[str, str], ...]
    chunk_count: int = 1
    approved_reads: tuple[str, ...] = ()
    kv_pages: int = 1


def fixture_binding() -> NativeBinding:
    """Invented identities only; does not truncate the inherited full schema."""
    pin = hashlib.sha256(b"invented-source-native-wiring-fixture").hexdigest()
    return NativeBinding(
        pin,
        PROFILE,
        OBJECT_PROFILE,
        ("invented-namespace/invented-object",),
        ("1",),
        pin,
        pin,
        pin,
        pin,
        pin,
        operator=fixture_inputs(ROOT),
    )


def _binding(binding: NativeBinding) -> None:
    if (
        type(binding) is not NativeBinding
        or binding.profile != PROFILE
        or binding.object_profile != OBJECT_PROFILE
    ):
        raise Refusal("native_profile_binding")
    if type(binding.operator) is not OperatorInputs:
        raise Refusal("complete_native_operator_context_required")
    pins = (
        binding.source_pin,
        binding.artifact,
        binding.configuration,
        binding.schema,
        binding.guards,
        binding.oracle,
    )
    if any(
        type(p) is not str or len(p) != 64 or any(c not in "0123456789abcdef" for c in p)
        for p in pins
    ):
        raise Refusal("native_source_context")
    if (
        type(binding.population) is not tuple
        or not binding.population
        or len(binding.population) > 16
        or len(binding.population) != len(set(binding.population))
        or type(binding.generations) is not tuple
        or len(binding.generations) != len(binding.population)
        or any(not r or not r.isascii() for r in binding.population)
        or any(
            not g.isascii()
            or not g.isdecimal()
            or g.startswith("0")
            or int(g) > 9223372036854775807
            for g in binding.generations
        )
    ):
        raise Refusal("native_population_identity")


def source_program(
    case_number: int,
    binding: NativeBinding,
    retained_pins: dict[str, str],
    *,
    chunk_count: int = 1,
    approved_reads: tuple[str, ...] = (),
    kv_pages: int = 1,
) -> NativeProgram:
    """Compose all twelve cases from inherited interfaces, without native I/O.

    SQL fields contain exact SOURCE expression identities until the TypeScript
    native-plan builder supplies actual statement/argument bytes. They are never
    accepted as executable SQL or as a complete operation allocation. Unresolved
    operator operations are explicit children, not fictitious aggregate routes.
    """
    _binding(binding)
    if type(case_number) is not int or not 1 <= case_number <= 12:
        raise Refusal("native_case_inventory")
    if (
        type(chunk_count) is not int
        or not 1 <= chunk_count <= 16
        or type(kv_pages) is not int
        or not 1 <= kv_pages <= 256
        or type(approved_reads) is not tuple
        or approved_reads
    ):
        # A caller cannot insert arbitrary SELECT text into a source-owned tree.
        raise Refusal("native_unreviewed_refinement")
    actual = retained_source_pins()
    if any(retained_pins.get(path) != pin for path, pin in actual.items()):
        raise Refusal("native_inherited_source_drift")
    context = hashlib.sha256(
        json.dumps(dataclasses.asdict(binding), sort_keys=True).encode()
    ).hexdigest()

    def node(
        path: tuple[str, ...],
        method: str,
        source: str,
        resource: str,
        sql: tuple[str, ...] = (),
        children: tuple[NativeLeaf, ...] = (),
        refinement: str = "source-expression",
    ) -> NativeLeaf:
        filename = SOURCES[source]
        identity = hashlib.sha256(
            json.dumps(
                [context, case_number, path, method, resource, sql], separators=(",", ":")
            ).encode()
        ).hexdigest()
        return NativeLeaf(
            path, method, filename, actual[filename], resource, identity, sql, children, refinement
        )

    def ledger(path: tuple[str, ...], kind: str, resource: str) -> NativeLeaf:
        # load(): one summary, one atomic append/header/chunks/events, final
        # events. Source and owner are different calls, never collapsed together.
        return node(
            path,
            "RuntimeEvidenceLedger." + kind,
            "ledger",
            resource,
            children=tuple(
                node((*path, name), "D1.session.batch", "ledger", "evidence-d1", sql)
                for name, sql in (
                    (
                        "preflight",
                        (
                            "EVIDENCE_SQL.select"
                            if kind == "reserveSelected"
                            else "EVIDENCE_SQL.preflight",
                        ),
                    ),
                    (
                        "load",
                        (
                            "EVIDENCE_SQL.append:"
                            + ("native-consumed" if kind == "consume" else "use-reserved"),
                            "EVIDENCE_SQL.header",
                            "EVIDENCE_SQL.chunks",
                            "EVIDENCE_SQL.events",
                        ),
                    ),
                    ("final", ("EVIDENCE_SQL.events",)),
                )
            ),
        )

    def publication(path: tuple[str, ...], resource: str) -> NativeLeaf:
        statements = (
            "preparePublication.envelope",
            *("preparePublication.chunk:" + str(i) for i in range(chunk_count)),
            "preparePublication.publish-event",
        )
        return node(
            path,
            "publishReviewedEvidence",
            "publication",
            resource,
            children=tuple(
                node((*path, name), "D1.session.batch", "publication_plan", "evidence-d1", sql)
                for name, sql in (
                    ("publish", statements),
                    ("summary", ("EVIDENCE_SQL.preflight",)),
                    (
                        "readback",
                        ("EVIDENCE_SQL.header", "EVIDENCE_SQL.chunks", "EVIDENCE_SQL.events"),
                    ),
                    ("final", ("EVIDENCE_SQL.events",)),
                )
            ),
        )

    def acquisition(path: tuple[str, ...], resource: str) -> NativeLeaf:
        # A native query expands to THREE actual SQL execs. Dynamic column
        # names determine the second statement and must remain unresolved here.
        def query(p: tuple[str, ...], expression: str) -> NativeLeaf:
            return node(
                p,
                "ReadSession.query",
                "native",
                resource,
                children=(
                    node(
                        (*p, "columns"),
                        "storage.sql.exec",
                        "native",
                        resource,
                        ("SELECT * FROM (" + expression + ") LIMIT 0",),
                    ),
                    node(
                        (*p, "bound"),
                        "storage.sql.exec",
                        "native",
                        resource,
                        ("native.rowCost(columns):" + expression,),
                        refinement="exact-columns-required",
                    ),
                    node((*p, "read"), "storage.sql.exec", "native", resource, (expression,)),
                ),
            )

        reads = [
            query((*path, "native", "fence-before", str(i)), q)
            for i, q in enumerate(("CONTROL_COUNT", "FENCE"))
        ]
        # Complete schema, table census, every table's columns/rows, and terminal
        # schema/table census are owned by the actual complete boundary reader.
        reads.append(
            node(
                (*path, "native", "complete-sql"),
                "captureSupportedBoundary.complete-query-plan",
                "boundary",
                resource,
                (
                    "reader.schemaSQL",
                    "reader.storageSQL",
                    "reader.columnsSQL(each included table)",
                    "reader.rowsSQL(each included table)",
                    "reader.schemaSQL",
                    "reader.storageSQL",
                ),
                refinement="exact-boundary-manifest-required",
            )
        )
        reads.extend(
            node((*path, "native", "kv", str(i)), "transaction.list(limit=1)", "native", resource)
            for i in range(kv_pages)
        )
        reads.extend(
            node((*path, "native", "alarm", str(i)), "transaction.getAlarm", "native", resource)
            for i in range(2)
        )
        reads.extend(
            query((*path, "native", "fence-after", str(i)), q)
            for i, q in enumerate(("CONTROL_COUNT", "FENCE"))
        )
        return node(
            path,
            "PartitionWorker.acquireFresh",
            "partition",
            resource,
            children=(
                node(
                    (*path, "rpc"),
                    "owning-namespace.acquireFresh",
                    "source",
                    resource,
                    refinement="exact-rpc-wire-required",
                ),
                ledger((*path, "owner-consume"), "consume", resource),
                node(
                    (*path, "native"),
                    "acquireNativeFacts",
                    "owner",
                    resource,
                    children=tuple(reads),
                ),
            ),
        )

    def capture(path: tuple[str, ...]) -> NativeLeaf:
        return node(
            path,
            "captureSupportedBoundary",
            "boundary",
            "complete-population",
            children=(
                publication((*path, "publish"), "raw-capture"),
                ledger((*path, "source-reserve"), "reserve", "raw-capture"),
                node(
                    (*path, "source"),
                    "createFreshNativeSource",
                    "source",
                    "complete-population",
                    children=tuple(
                        acquisition((*path, "object", str(i)), resource)
                        for i, resource in enumerate(binding.population)
                    ),
                ),
                *(
                    node(
                        (*path, "terminal", str(i)),
                        "D1.session.batch",
                        "ledger",
                        "evidence-d1",
                        ("EVIDENCE_SQL.terminal:" + resource,),
                    )
                    for i, resource in enumerate(binding.population)
                ),
                node(
                    (*path, "final"),
                    "D1.session.batch",
                    "ledger",
                    "evidence-d1",
                    ("EVIDENCE_SQL.events",),
                ),
            ),
        )

    def external(path: tuple[str, ...], method: str, source: str, resource: str) -> NativeLeaf:
        return node(
            path, method, source, resource, refinement="exact-operator-request-and-effects-required"
        )

    assert binding.operator is not None
    operator_inputs = binding.operator
    operator_steps = build_operator_steps(operator_inputs, root=ROOT)

    def operator_nodes(
        path: tuple[str, ...], prefix: str, only: tuple[str, ...] = ()
    ) -> tuple[NativeLeaf, ...]:
        result: list[NativeLeaf] = []
        for step in operator_steps:
            if not step.name.startswith(prefix):
                continue
            if only and step.name not in only:
                continue
            owner = next(key for key, value in SOURCES.items() if value == step.source_path)
            children: list[NativeLeaf] = []
            for leaf in step.leaves:
                source = next(key for key, value in SOURCES.items() if value == leaf.source_path)
                children.append(
                    node(
                        (*path, step.name, leaf.key),
                        leaf.method + " " + leaf.path,
                        source,
                        leaf.resource,
                        refinement="exact-management-request-needs-qualified-wire-effects",
                    )
                )
            if step.method == "closedRestorationCheck":
                children.append(
                    node(
                        (*path, step.name, "authenticated-lookup"),
                        "D1.prepare.first",
                        "ordinary",
                        "domain-d1",
                        ("LOOKUP_SQL",),
                        refinement="exact-authenticated-request-and-closed-domain-required",
                    )
                )
            result.append(
                node(
                    (*path, step.name),
                    step.method,
                    owner,
                    operator_inputs.worker_id,
                    children=tuple(children),
                    refinement="actual-independent-custody-and-allocation-required",
                )
            )
        return tuple(result)

    def main_assessment(path: tuple[str, ...]) -> NativeLeaf:
        plan = json.loads((ROOT / SOURCES["domain_plan"]).read_bytes())

        def quote(value: str) -> str:
            return '"' + value.replace('"', '""') + '"'

        def expr(column: str) -> str:
            q = quote(column)
            return (
                f"json_array(typeof({q}),CASE typeof({q}) WHEN 'null' THEN NULL "
                f"WHEN 'integer' THEN CAST({q} AS TEXT) WHEN 'text' THEN hex(CAST({q} AS BLOB)) "
                f"WHEN 'blob' THEN hex({q}) ELSE 'UNSUPPORTED' END)"
            )

        schema = (
            "SELECT json_array(type,name,tbl_name,sql) v FROM main.sqlite_schema "
            "ORDER BY type,name,tbl_name"
        )
        reads: list[tuple[str, str]] = [("schema-before", schema)]
        for table, spec in sorted(plan["tables"].items()):
            columns = ["rowid", *spec["columns"]] if spec["rowid"] else spec["columns"]
            reads.append(
                (
                    table,
                    "SELECT json_array("
                    + ",".join(expr(c) for c in columns)
                    + ") v FROM "
                    + quote(table)
                    + " LIMIT 10001",
                )
            )
        reads.append(("schema-after", schema))
        domain: list[NativeLeaf] = []
        for name, sql in reads:
            for suffix, statement in (
                (
                    "preflight",
                    "SELECT CAST(count(*) AS TEXT) n,CAST(32+coalesce(sum(2*length(CAST(v AS BLOB))"
                    "+64),0) AS TEXT) b FROM (" + sql + ")",
                ),
                ("read", sql),
            ):
                domain.append(
                    node(
                        (*path, "domain", name, suffix),
                        "D1.session.prepare.all",
                        "domain",
                        "domain-d1",
                        (statement,),
                        refinement="exact-source-sql-needs-qualified-result-and-wire",
                    )
                )
        journal = tuple(
            node(
                (*path, "journal", name),
                "D1.session.batch",
                "journal",
                "main-journal",
                ("PMB1_JOURNAL_SQL.control", "PMB1_JOURNAL_SQL." + table),
                refinement="bounded-pages-128-rows-stop-empty-total-pages-and-bytes-fenced",
            )
            for name, table in (
                ("invocations-until-empty", "invocations"),
                ("effects-until-empty", "effects"),
                ("final-empty-invocations", "invocations"),
            )
        )
        return node(
            path,
            "PrivateMainRuntime.assessStopped",
            "main",
            "all-writers-and-callbacks",
            children=(
                publication((*path, "evidence-use-publication"), "main-assess-evidence-use"),
                ledger(
                    (*path, "evidence-use-reserve"), "reserveSelected", "main-assess-evidence-use"
                ),
                node(
                    (*path, "stop"),
                    "D1.batch",
                    "journal",
                    "main-journal",
                    ("PMB1_JOURNAL_SQL.stop", "PMB1_JOURNAL_SQL.control"),
                ),
                *journal,
                *domain,
                node(
                    (*path, "evidence-use-terminal"),
                    "D1.session.batch",
                    "ledger",
                    "evidence-d1",
                    ("EVIDENCE_SQL.terminal:evidence-use",),
                ),
                node(
                    (*path, "evidence-use-final"),
                    "D1.session.batch",
                    "ledger",
                    "evidence-d1",
                    ("EVIDENCE_SQL.events",),
                ),
            ),
        )

    roots: list[NativeLeaf] = []
    stages = REQUIRED_STAGES if case_number != 12 else (*REQUIRED_STAGES[:4], "interruption")
    for stage in stages:
        path = ("case" + str(case_number), stage)
        children: list[NativeLeaf] = []
        if stage == "settle":
            children.append(
                node(
                    (*path, "reserve-tree"),
                    "SQLiteNativeBroker.reserve_tree",
                    "native_journal",
                    "outside-compared-stores",
                )
            )
        children.append(
            node(
                (*path, "begin-subtree"),
                "SQLiteNativeBroker.begin_subtree",
                "native_journal",
                "outside-compared-stores",
            )
        )
        if stage == "settle":
            children.extend(operator_nodes((*path, "operator"), "retained."))
            children.extend(
                (
                    node(
                        (*path, "current"),
                        "PrivateMainRuntime.currentMain",
                        "main",
                        "main-journal",
                        ("currentMain.SELECT-control",),
                    ),
                    node(
                        (*path, "stop"),
                        "PrivateMainRuntime.stopAdmission",
                        "main",
                        "main-journal",
                        ("PMB1_JOURNAL_SQL.stop", "PMB1_JOURNAL_SQL.control"),
                    ),
                    main_assessment((*path, "assessment")),
                )
            )
        elif stage in ("baseline", "preflight", "restored"):
            children.append(capture((*path, "capture")))
            if stage == "restored" and case_number == 7:
                children.append(
                    node(
                        (*path, "both-delayed-generations-after-retained-restore"),
                        "invokeInheritedNativeChallenge:7:post-restore",
                        "dispatch",
                        "bound-original-and-temporary-sdk-generations",
                        refinement="requires-completed-exact-retained-restore-and-readback",
                    )
                )
        elif stage in ("close", "admission_off"):
            if stage == "admission_off":
                children.extend(operator_nodes((*path, "operator"), "stop."))
            for i, resource in enumerate(binding.population):
                if stage == "close":
                    children.append(
                        node(
                            (*path, "partition-stop", str(i)),
                            "PartitionWorker.maintenanceStop",
                            "control",
                            resource,
                            (
                                "PartitionMaintenance.installed(all8-schema-queries)",
                                "Pmb1NativeWakeup.control",
                                "transaction.put(pmb1:admission,false)",
                            ),
                            refinement="exact-control-branch-required",
                        )
                    )
                children.append(
                    node(
                        (*path, "partition", str(i)),
                        "PartitionWorker.maintenanceClose"
                        if stage == "close"
                        else "PartitionWorker.maintenanceStop",
                        "control",
                        resource,
                        (
                            "PartitionMaintenance.installed(all8-schema-queries)",
                            "Pmb1NativeWakeup.control",
                            "transaction.get(pmb1:admission)",
                            "PartitionMaintenance.close:active-invocations",
                            "PartitionMaintenance.close:active-wake",
                            "Pmb1NativeWakeup.deleteScheduled",
                            "Pmb1NativeWakeup.close",
                        )
                        if stage == "close"
                        else ("Pmb1NativeWakeup.control", "transaction.put(pmb1:admission,false)"),
                        refinement="exact-control-branch-required",
                    )
                )
        elif stage in ("closure_readback", "challenge_readback"):
            children.append(
                node(
                    (*path, "main-current"),
                    "PrivateMainRuntime.currentMain",
                    "main",
                    "main-journal",
                    ("currentMain.SELECT-control",),
                )
            )
            for i, resource in enumerate(binding.population):
                children.append(
                    node(
                        (*path, "owning-control-readback", str(i)),
                        "readClosedOwnerControl",
                        "dispatch",
                        resource,
                        children=(
                            node(
                                (*path, "owning-control-readback", str(i), "transaction"),
                                "storage.transaction",
                                "dispatch",
                                resource,
                            ),
                            node(
                                (*path, "owning-control-readback", str(i), "sql"),
                                "storage.sql.exec",
                                "dispatch",
                                resource,
                                (
                                    "readClosedOwnerControl.SELECT-singleton-generation-state-LIMIT2",
                                ),
                            ),
                            node(
                                (*path, "owning-control-readback", str(i), "admission"),
                                "transaction.get(pmb1:admission)",
                                "dispatch",
                                resource,
                            ),
                        ),
                    )
                )
        elif stage == "restore_readback":
            children.extend(
                operator_nodes(
                    (*path, "operator"),
                    "restore.",
                    (
                        "restore.version",
                        "restore.deployment",
                        "restore.endpoint",
                        "restore.origin",
                        "restore.ordinary",
                    ),
                )
            )
        elif stage == "cleanup_readback":
            children.extend(operator_nodes((*path, "operator"), "cleanup.", ("cleanup.absence",)))
        elif stage == "challenge":
            children.append(
                node(
                    (*path, CASE_OBLIGATIONS[case_number - 1]),
                    "invokeInheritedNativeChallenge:"
                    + str(case_number)
                    + (":guard" if case_number == 7 else ""),
                    "dispatch",
                    "bound-reviewed-native-sdk-state",
                    refinement="source-owned-fixed-case-branch-no-actual-grant",
                )
            )
        elif stage == "temporary_install":
            children.extend(operator_nodes((*path, "operator"), "temporary."))
        elif stage == "restore":
            children.extend(operator_nodes((*path, "operator"), "restore.", ("restore.deploy",)))
        elif stage == "cleanup":
            children.extend(operator_nodes((*path, "operator"), "cleanup.", ("cleanup.delete",)))
        elif stage == "interruption":
            children.append(
                node(
                    (*path, "declared-partial-output"),
                    "invokeInheritedNativeStep:declared-interruption:partial_output",
                    "dispatch",
                    "bound-reviewed-native-sdk-state",
                    refinement="terminal-unknown-no-later-stage-or-replay",
                )
            )
        children.append(
            node(
                (*path, "finish-subtree"),
                "SQLiteNativeBroker.finish_subtree",
                "native_journal",
                "outside-compared-stores",
            )
        )
        roots.append(node(path, stage, "source", "complete-population", children=tuple(children)))
    return NativeProgram(
        case_number,
        binding,
        tuple(roots),
        tuple(sorted(actual.items())),
        chunk_count,
        approved_reads,
        kv_pages,
    )


def validate_native_program(program: NativeProgram) -> None:
    if type(program) is not NativeProgram:
        raise Refusal("source_owned_native_program_required")
    expected = source_program(
        program.case_number,
        program.binding,
        dict(program.source_pins),
        chunk_count=program.chunk_count,
        approved_reads=program.approved_reads,
        kv_pages=program.kv_pages,
    )
    if program != expected:
        raise Refusal("native_operation_tree_identity_or_refinement")


def leaves(program: NativeProgram) -> tuple[NativeLeaf, ...]:
    validate_native_program(program)
    result: list[NativeLeaf] = []

    def visit(node: NativeLeaf) -> None:
        if node.children:
            for child in node.children:
                visit(child)
        else:
            result.append(node)

    for root in program.roots:
        visit(root)
    return tuple(result)


def inert_trace(program: NativeProgram) -> dict:
    """Inspect exact ordered wiring, never call an adapter or observed target.

    Unknown costs propagate, including transaction internals, conditional guards,
    dynamic SQL, RPC wire, operator auth, writes and retained external receipts.
    This output is deliberately not a Runner Receipt and cannot pass an Oracle.
    """
    selected = leaves(program)
    return {
        "scope": "SOURCE_COMPOSITION_INSPECTION_ONLY",
        "qualification": "NO_GO",
        "dispatch_enabled": False,
        "case": program.case_number,
        "ordered_leaves": tuple(n.identity for n in selected),
        "leaf_paths": tuple(n.path for n in selected),
        "source_sql_expressions": sum(len(n.sql) for n in selected),
        "native_batches": sum(n.method == "D1.session.batch" for n in selected),
        "effects": "UNKNOWN",
        "wire_bytes": "UNKNOWN",
        "allocation": "UNRESOLVED",
        "unresolved": tuple(n.path for n in selected if n.refinement != "exact"),
    }


def make_native_lease(
    program: NativeProgram, key: str = "source-native-unqualified"
) -> NativeLease:
    """Exact context/tree identity with explicit UNKNOWN actual costs.

    No source expression, fixture observation, supplied counter or matching hash
    manufactures the missing native wire/effect/custody qualification. The broker
    therefore refuses this lease before reserving or dispatching any real work.
    """
    selected = leaves(program)
    context = hashlib.sha256(
        json.dumps(dataclasses.asdict(program.binding), sort_keys=True).encode()
    ).hexdigest()
    intents = tuple(
        LeafIntent(
            i,
            leaf.identity,
            leaf.source_path,
            leaf.source_pin,
            leaf.method,
            leaf.resource,
            hashlib.sha256(
                json.dumps(dataclasses.asdict(leaf), sort_keys=True).encode()
            ).hexdigest(),
            None,
        )
        for i, leaf in enumerate(selected)
    )
    return NativeLease(
        key,
        context,
        program.binding.source_pin,
        program.binding.profile,
        program.binding.object_profile,
        intents,
    )


def execute_native(program: NativeProgram, journal: SQLiteNativeBroker | None = None) -> None:
    validate_native_program(program)
    from contracts import inherited_fit

    if not inherited_fit()["fits"]:
        raise Refusal("selected_candidate_exceeds_accepted_miniature_allocation")
    if journal is not None:
        # Even an invented fit cannot lend truth to UNKNOWN costs. No adapter
        # or effect is reached until the exact complete lease has been reserved.
        journal.reserve_tree(make_native_lease(program))
    raise Refusal("provider_dispatch_disabled")


class InheritedOperatorSDKBindings:
    """Named Python-owned SDK piece for native_dispatch.OperatorSDKBindings.

    Root supplies the existing authenticated provider and prospective restore
    references. This constructor neither builds a provider/transport nor
    authenticates Root. There is no credential loader or operation callback.
    SourceHarnessFactory's invented provider exercises the SAME named methods.
    """

    def __init__(
        self,
        provider: operator.BetaPublisherProvider,
        restore: operator.ProspectiveRestoreProgram | None = None,
    ):
        self.provider, self.restore = provider, restore

    def create_worker(self, name, *, key):
        return self.provider.create_worker(name, key=key)

    def create_version(self, identity, module, sha2, metadata, access_token, *, key):
        return self.provider.create_version(identity, module, sha2, metadata, access_token, key=key)

    def inspect_version(self, identity, version, *, key):
        return self.provider.inspect_version(identity, version, key=key)

    def deploy_version(self, identity, version, *, key):
        return self.provider.deploy_version(identity, version, key=key)

    def inspect_deployment(self, identity, version, deployment, *, key):
        return self.provider.inspect_deployment(identity, version, deployment, key=key)

    def disable_worker(self, identity, *, key):
        return self.provider.disable_worker(identity, key=key)

    def inspect_endpoint(self, identity, *, key):
        return self.provider.inspect_endpoint(identity, key=key)

    def assert_endpoint(self, identity, endpoint, *, key):
        return self.provider.assert_endpoint(identity, endpoint, key=key)

    def delete_worker(self, identity, *, key):
        return self.provider.delete_worker(identity, key=key)

    def inspect_worker(self, identity, *, key):
        return self.provider.inspect_worker(identity, key=key)

    def restore_retained_version(self, identity, version, preflight, *, key):
        if self.restore is None:
            raise Refusal("genuine_root_restore_context_required")
        return self.restore.restore_retained_version(identity, version, preflight, key=key)


def rehearse_durable_operator(path: Path, *, fault: str | None = None) -> dict:
    """A small known SOURCE model through the actual inherited provider hooks.

    The four fixed requests execute only the existing InventedProviderIO. Its
    modeled events and serialized body bytes are known SOURCE metrics; actual
    HTTP framing/provider effects remain UNKNOWN and cannot enter actual
    admission. The external broker commits every exact leaf intent before the
    inherited provider can start its fake transport thread. No caller adapter,
    callback, runtime token, endpoint override or grant is accepted.
    """
    if fault not in (None, "lost_finish_ack"):
        raise Refusal("source_durable_operator_fault")
    inputs = fixture_inputs(ROOT)
    pins = dict(inputs.source_pins)
    worker = "/workers/workers/" + inputs.worker_id
    requests = (
        operator.RequestLeaf(
            "fixture:worker",
            "POST",
            "/workers/workers",
            operator.IDENTITY,
            pins[operator.IDENTITY],
            True,
            inputs.worker_id,
        ),
        operator.RequestLeaf(
            "worker:inspect",
            "GET",
            worker,
            operator.IDENTITY,
            pins[operator.IDENTITY],
            False,
            inputs.worker_id,
        ),
        operator.RequestLeaf(
            "worker:disable:identity",
            "GET",
            worker,
            operator.IDENTITY,
            pins[operator.IDENTITY],
            False,
            inputs.worker_id,
        ),
        operator.RequestLeaf(
            "worker:disable",
            "PATCH",
            worker,
            operator.IDENTITY,
            pins[operator.IDENTITY],
            True,
            inputs.worker_id,
        ),
    )
    context = hashlib.sha256(
        json.dumps(
            {"scope": "KNOWN_SOURCE_MODEL_ONLY", "inputs": dataclasses.asdict(inputs)},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    costs = tuple(
        Cost(
            requests=1,
            receipt_reads=0 if r.mutation else 1,
            creates=1 if i == 0 else 0,
            mutations=1 if i == 3 else 0,
            effects=1 if r.mutation else 0,
            outbound_bytes=65536,
            inbound_bytes=262144,
            artifact_bytes=16384,
        )
        for i, r in enumerate(requests)
    )

    def request_pin(r: operator.RequestLeaf) -> str:
        # Body construction is fixed by the same source-owned caller and exact
        # inherited method/source pins; there is no supplied request body here.
        return hashlib.sha256(
            json.dumps([context, dataclasses.asdict(r)], sort_keys=True).encode()
        ).hexdigest()

    intents = tuple(
        LeafIntent(
            i, r.key, r.source_path, r.source_pin, r.method, r.resource, request_pin(r), costs[i]
        )
        for i, r in enumerate(requests)
    )
    lease = NativeLease(
        "source-owned-provider-four-leaves",
        context,
        hashlib.sha256(_LOADED_PROGRAM).hexdigest(),
        PROFILE,
        OBJECT_PROFILE,
        intents,
    )
    broker = SQLiteNativeBroker(path)
    broker.reserve_tree(lease)
    io = operator.InventedProviderIO(inputs)
    evidence_sizes: list[int] = []

    class DurableFence(operator._RequestFence):
        def before(self, key, mutation, metadata):
            super().before(key, mutation, metadata)
            index = self.position - 1
            intent = intents[index]
            broker.begin(lease, index, intent.identity, intent.request_digest)
            state = broker.observe()
            if state["status"] != "dispatching" or state["next_ordinal"] != index:
                raise Refusal("source_intent_not_durable_before_transport")
            self.source_metadata = dict(metadata)

        def after(self, key, receipt):
            super().after(key, receipt)
            index = self.position - 1
            intent = intents[index]
            evidence = json.dumps(
                {
                    "key": key,
                    "request": self.source_metadata,
                    "receipt": receipt,
                    "scope": "KNOWN_SOURCE_MODEL_ONLY",
                },
                sort_keys=True,
            ).encode()
            actual = dataclasses.replace(
                costs[index],
                outbound_bytes=self.source_metadata["requestBytes"],
                inbound_bytes=receipt["responseBytes"],
            )
            broker.finish(lease, index, intent.identity, intent.request_digest, actual, evidence)
            evidence_sizes.append(len(evidence))
            if fault == "lost_finish_ack" and index == 0:
                raise Refusal("source_finish_ack_lost")

    fence = DurableFence(inputs, requests, io, ROOT, 4, 100, None)
    provider = operator.SourceHarnessFactory.create(inputs, io, fence)
    sdk = InheritedOperatorSDKBindings(provider)
    outcome = "known_source_complete"
    try:
        identity = sdk.create_worker(inputs.worker_name, key="fixture:worker")
        sdk.inspect_worker(identity, key="worker:inspect")
        sdk.disable_worker(identity, key="worker:disable")
    except Exception:
        broker.mark_unknown(lease, "source_provider_or_journal_ack_unknown")
        outcome = "unknown"
    state = broker.observe()
    broker.close()
    return {
        "scope": "KNOWN_SOURCE_MODEL_ONLY",
        "qualification": "NO_GO",
        "outcome": outcome,
        "requests": io.requests,
        "expected_requests": len(requests),
        "lease_digest": lease_digest(lease),
        "journal": state,
        "retained_evidence_bytes": sum(evidence_sizes),
        "actual_wire": "UNKNOWN",
        "actual_provider_effects": "UNKNOWN",
        "actual_headroom": "UNKNOWN",
    }
