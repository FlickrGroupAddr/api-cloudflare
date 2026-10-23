"""Finite operator D1 HTTP binding. Import/construct/default CLI are inert.

The later operator owns independent review and factual qualification of the
retained packet, source oracle, custody, clocks, grants and closed interval.
Neither pins nor this module establish those facts. No isolated-database permit
is accepted here. No Worker binding, DNS, retries, SDK or ambient credentials.
"""

from __future__ import annotations

import argparse
import builtins
import hashlib
import math
import re
import sys
import threading
import time
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]

# This is the finite project dependency closure for THIS operator, including
# lazy codec imports. There is no path discovery, plugin loading or ambient
# project-module reuse. Python/the standard library are trusted runtime inputs.
_GRAPH_PATHS = {
    "adapter": ROOT / "probes/pmb1-d1-adapter/adapter.py",
    "prospective_control": ROOT / "probes/pmb1-integer-candidate/prospective_control.py",
    "journal": Path(__file__).resolve().with_name("journal.py"),
    "exact_receipt_successor": Path(__file__).resolve().with_name("exact_receipt_successor.py"),
    "successor_control": Path(__file__).resolve().with_name("successor_control.py"),
    "positional_receipt_successor": Path(__file__)
    .resolve()
    .with_name("positional_receipt_successor.py"),
    **{
        f"scripts.{name}": ROOT / "scripts" / f"{name}.py"
        for name in (
            "hosted_publisher_execution_provider",
            "hosted_publisher_finite_client",
            "hosted_publisher_provider",
            "hosted_publisher_worker_deployment",
            "hosted_publisher_worker_identity",
            "hosted_publisher_operator_plan",
            "temporary_composition_metadata_collector",
            "temporary_composition_metadata_projection",
            "private_d1_snapshot_codec",
            "private_d1_snapshot_profile",
            "private_no_real_guards",
            "fixed_origin_preservation",
            "fixed_origin_restore",
            "private_d1_snapshot_reader",
        )
    },
}
_GRAPH_BYTES = {name: path.read_bytes() for name, path in _GRAPH_PATHS.items()}
_GRAPH: dict[str, Any] = {}
_PRIVATE_PREFIX = f"_pmb1_native_d1_graph_{id(_GRAPH):x}"
_SCRIPTS = types.ModuleType(_PRIVATE_PREFIX + ".scripts")
_SCRIPTS.__path__ = [str(ROOT / "scripts")]


def _fixed_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and (name == "scripts" or name in _GRAPH_PATHS):
        if name == "scripts":
            for item in fromlist:
                full = "scripts." + item
                if full not in _GRAPH_PATHS:
                    raise RuntimeError("native_d1_unreviewed_project_import")
                setattr(_SCRIPTS, item, _load_fixed(full))
            return _SCRIPTS
        module = _load_fixed(name)
        if name.startswith("scripts."):
            setattr(_SCRIPTS, name.split(".", 1)[1], module)
            return module if fromlist else _SCRIPTS
        return module
    if name.split(".", 1)[0] in (
        "scripts",
        "adapter",
        "journal",
        "prospective_control",
        "exact_receipt_successor",
        "successor_control",
        "positional_receipt_successor",
    ):
        raise RuntimeError("native_d1_unreviewed_project_import")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _load_fixed(name):
    if name in _GRAPH:
        return _GRAPH[name]
    private_name = _PRIVATE_PREFIX + "." + name
    if private_name in sys.modules:
        raise RuntimeError("native_d1_private_module_collision")
    module = types.ModuleType(private_name)
    module.__file__ = str(_GRAPH_PATHS[name])
    module.__package__ = private_name.rpartition(".")[0]
    module.__dict__["__builtins__"] = {**vars(builtins), "__import__": _fixed_import}
    _GRAPH[name] = module
    # Dataclasses resolve string annotations through their defining module's
    # private name. Register only this freshly created object, never a namesake.
    sys.modules[private_name] = module
    try:
        exec(compile(_GRAPH_BYTES[name], str(_GRAPH_PATHS[name]), "exec"), module.__dict__)
    except BaseException:
        del _GRAPH[name]
        del sys.modules[private_name]
        raise
    return module


for _name in _GRAPH_PATHS:
    _load_fixed(_name)
adapter = _GRAPH["adapter"]
prospective_control = _GRAPH["prospective_control"]
exact_receipt_successor = _GRAPH["exact_receipt_successor"]
successor_control = _GRAPH["successor_control"]
positional_receipt_successor = _GRAPH["positional_receipt_successor"]
_JOURNAL_MODULE = _GRAPH["journal"]
SQLiteJournal = _JOURNAL_MODULE.SQLiteJournal
encode = _JOURNAL_MODULE.encode
intent_from = _JOURNAL_MODULE.intent_from
_address = _GRAPH["scripts.hosted_publisher_execution_provider"]._address
_pinned_https = _GRAPH["scripts.hosted_publisher_execution_provider"]._pinned_https
Request = _GRAPH["scripts.hosted_publisher_finite_client"].Request
Response = _GRAPH["scripts.hosted_publisher_finite_client"].Response
NO_REAL_PROFILE = _GRAPH["scripts.private_d1_snapshot_profile"].NO_REAL_PROFILE
validate_manifest = _GRAPH["scripts.private_d1_snapshot_profile"].validate_manifest
_rows = _GRAPH["scripts.private_d1_snapshot_reader"]._rows
_json = _GRAPH["scripts.temporary_composition_metadata_collector"]._json
canonical = _GRAPH["scripts.temporary_composition_metadata_collector"].canonical
collect_snapshot = _GRAPH["scripts.private_d1_snapshot_codec"].collect_snapshot
_GRAPH_EXPORTS = {
    name: {
        key: value
        for key, value in vars(module).items()
        if not key.startswith("__") and (callable(value) or isinstance(value, types.ModuleType))
    }
    for name, module in _GRAPH.items()
}
_BOUND_EXPORTS = {
    name: globals()[name]
    for name in (
        "adapter",
        "prospective_control",
        "exact_receipt_successor",
        "successor_control",
        "positional_receipt_successor",
        "SQLiteJournal",
        "encode",
        "intent_from",
        "_address",
        "_pinned_https",
        "Request",
        "Response",
        "validate_manifest",
        "_rows",
        "_json",
        "canonical",
        "collect_snapshot",
    )
}

MAX_PACKET_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_QUERIES = 2048
HEX = re.compile(r"[a-f0-9]{64}")


def require(value, category):
    if not value:
        raise adapter.Refusal(category)


def sha2_256(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned_file(path, expected, limit):
    require(type(expected) is str and HEX.fullmatch(expected), "native_d1_pin")
    path = Path(path)
    require(path.is_absolute() and not path.is_symlink(), "native_d1_custody_path")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit and sha2_256(raw) == expected, "native_d1_retained_pin")
    return raw


def source_pins():
    require(
        all(path.read_bytes() == _GRAPH_BYTES[name] for name, path in _GRAPH_PATHS.items())
        and all(
            sys.modules.get(_PRIVATE_PREFIX + "." + name) is module
            for name, module in _GRAPH.items()
        )
        and all(
            vars(_GRAPH[name]).get(key) is value
            for name, exports in _GRAPH_EXPORTS.items()
            for key, value in exports.items()
        )
        and all(globals().get(name) is value for name, value in _BOUND_EXPORTS.items()),
        "native_d1_executable_project_graph_drift",
    )
    files = [Path(__file__), *_GRAPH_PATHS.values()]
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha2_256(path.read_bytes())
        for path in files
    }


def native_source_descriptor(source_manifest_sha2_256, profile_path, profile_sha2_256):
    """Expected native schema is separately retained, never learned from readback.

    The accepted source candidate supplies local code/guard provenance only.
    Its explicitly synthetic metadata fixture is NOT a native source oracle.
    The caller must supply an independently retained exact native profile whose
    provenance and completeness are later qualified outside this constructor.
    """
    source_pins()
    local = prospective_control.source_descriptor(source_manifest_sha2_256)
    raw = pinned_file(profile_path, profile_sha2_256, MAX_PACKET_BYTES)
    profile = _json(raw)
    require(profile.get("profile") == NO_REAL_PROFILE, "native_d1_no_real_profile")
    validate_manifest(profile, profile.get("schema"), profile.get("tableList"))
    require(len(profile["includedTables"]) == 65, "native_d1_full_candidate_required")
    fixture = _json((ROOT / "probes/pmb1-integer-candidate/d1-profile-fixture.json").read_bytes())

    def application(rows):
        return [row for row in rows if row["tbl_name"] != "_cf_KV"]

    require(
        application(profile["schema"]) == application(fixture["manifest"]["schema"]),
        "native_d1_application_schema_drift",
    )
    schema = [
        {
            "type": row["type"],
            "name": row["name"],
            "table": row["tbl_name"],
            "sql_sha2_256": None if row["sql"] is None else sha2_256(row["sql"].encode()),
        }
        for row in profile["schema"]
    ]

    def recheck():
        source_pins()
        local.recheck()
        pinned_file(profile_path, profile_sha2_256, MAX_PACKET_BYTES)

    return adapter.SourceDescriptor(
        local.candidate, (encode({"candidate_schema": schema}) + "\n").encode(), recheck
    )


class Binding:
    """Trusted operator configuration, explicit retained-packet activation.

    Retained packet pin is an independent integration input, not computed from a
    newly observed target or accepted from an action request. Activation is a
    necessary source gate, not qualification or action authority. Actual usage
    requires the later complete independently reviewed packet and factual gate.
    Tests patch the concrete HTTPS primitive; injection is not a native oracle.
    """

    def __init__(self, packet_path, packet_sha2_256, journal_path, source, *, clock=time.monotonic):
        self.packet_path, self.packet_sha2_256 = packet_path, packet_sha2_256
        self.journal_path, self.source, self.clock = journal_path, source, clock
        self.packet: dict[str, Any] | None = None
        # The concrete class is loaded from frozen sibling bytes above; it has
        # no ambient import name usable as a static Python type expression.
        self.journal: Any = None
        self.token: str | None = None
        self.lock = threading.Lock()

    def active(self) -> tuple[dict[str, Any], Any, str]:
        if self.packet is None or self.journal is None or self.token is None:
            raise adapter.Refusal("native_d1_inert")
        return self.packet, self.journal, self.token

    def _fixed_writer_sqls(self, fixed):
        return [fixed[name].decode() for name in ("close.sql", "reopen.sql")]

    def activate(self, credential_loader):
        """Explicit later operator action; never invoked by constructor/CLI."""
        require(self.packet is None and self.token is None, "native_d1_already_active")
        raw = pinned_file(self.packet_path, self.packet_sha2_256, MAX_PACKET_BYTES)
        packet = _json(raw)
        keys = {
            "kind",
            "accountId",
            "databaseId",
            "endpointAddress",
            "targetId",
            "candidate",
            "sourcePins",
            "credentialSha2_256",
            "starts",
            "ends",
            "clockDomain",
            "timeoutSeconds",
            "maxResponseBytes",
            "maxTotalBytes",
            "queries",
            "independentEvidence",
            "profileSha2_256",
        }
        require(type(packet) is dict and set(packet) == keys, "native_d1_packet_fields")
        packet = cast(dict[str, Any], packet)
        require(packet["kind"] == "pmb1-finite-native-d1-operator-v1", "native_d1_packet_kind")
        require(type(self.source) is adapter.SourceDescriptor, "native_d1_source")
        require(
            packet["candidate"] == self.source.candidate and packet["sourcePins"] == source_pins(),
            "native_d1_source_binding",
        )
        for key, pattern in (
            ("accountId", r"[a-f0-9]{32}"),
            ("databaseId", r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"),
        ):
            require(
                type(packet[key]) is str and re.fullmatch(pattern, packet[key]),
                "native_d1_exact_identity",
            )
        require(
            packet["targetId"] == f"{packet['accountId']}/{packet['databaseId']}",
            "native_d1_target_binding",
        )
        address = _address(packet["endpointAddress"])
        require(str(address) == packet["endpointAddress"], "native_d1_numeric_address")
        for key, ceiling in (
            ("maxResponseBytes", MAX_RESPONSE_BYTES),
            ("maxTotalBytes", MAX_TOTAL_BYTES),
            ("timeoutSeconds", 60),
        ):
            require(type(packet[key]) is int and 1 <= packet[key] <= ceiling, "native_d1_limits")
        require(
            all(
                type(packet[key]) in (int, float) and math.isfinite(packet[key])
                for key in ("starts", "ends")
            )
            and 0 <= packet["starts"] < packet["ends"] <= packet["starts"] + 300,
            "native_d1_window",
        )
        require(
            type(packet["clockDomain"]) is str and 1 <= len(packet["clockDomain"]) <= 128,
            "native_d1_clock_domain",
        )
        # Exact independently reviewed evidence files are pinned, never flags or
        # callbacks returning PASS. Their actual truth/custody remains external.
        evidence = packet["independentEvidence"]
        require(
            type(evidence) is dict
            and set(evidence)
            == {
                "review",
                "grant",
                "custody",
                "primaryAndCommitSemantics",
                "sourceOracle",
                "allWriterInterval",
                "allocation",
            },
            "native_d1_evidence_inventory",
        )
        for record in cast(dict[str, Any], evidence).values():
            require(
                type(record) is dict and set(record) == {"path", "sha2_256"},
                "native_d1_evidence_record",
            )
            pinned_file(record["path"], record["sha2_256"], MAX_PACKET_BYTES)
        require(
            type(packet["profileSha2_256"]) is str and HEX.fullmatch(packet["profileSha2_256"]),
            "native_d1_profile_pin",
        )
        queries = cast(list[dict[str, Any]], packet["queries"])
        require(
            type(queries) is list and 1 <= len(queries) <= MAX_QUERIES, "native_d1_query_inventory"
        )
        fixed = adapter.verify_source()
        for query in queries:
            require(
                type(query) is dict
                and set(query) == {"role", "sql", "params"}
                and query["role"] in ("writer", "observer", "snapshot")
                and type(query["sql"]) is str
                and 0 < len(query["sql"].encode()) <= 32768
                and type(query["params"]) is list,
                "native_d1_query_manifest",
            )
            if query["role"] == "writer":
                require(
                    query["sql"] in self._fixed_writer_sqls(fixed) and len(query["params"]) == 1,
                    "native_d1_fixed_write",
                )
                adapter.generation(query["params"][0], increment=True)
            else:
                require(query["params"] == [], "native_d1_read_params")
                if query["role"] == "observer":
                    require(
                        query["sql"]
                        in [fixed[name].decode() for name in ("readback.sql", "schema.sql")],
                        "native_d1_fixed_read",
                    )
                else:
                    require(
                        query["sql"].startswith("SELECT ")
                        and not any(mark in query["sql"] for mark in (";", "--", "/*")),
                        "native_d1_snapshot_fixed_select",
                    )
        require(
            type(packet["credentialSha2_256"]) is str
            and HEX.fullmatch(packet["credentialSha2_256"]),
            "native_d1_credential_pin",
        )
        self.source.recheck()
        now = self.clock()
        require(
            type(now) in (int, float)
            and math.isfinite(now)
            and packet["starts"] <= now < packet["ends"],
            "native_d1_deadline",
        )
        journal = SQLiteJournal(
            self.journal_path, packet["targetId"], self.packet_sha2_256, self.clock
        )
        # Missing or mismatched state refuses before credential loading.
        journal.remaining(packet["maxTotalBytes"], packet["ends"])
        require(callable(credential_loader), "native_d1_credential_delivery")
        token = credential_loader()
        require(
            type(token) is str
            and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token)
            and sha2_256(token.encode("ascii")) == packet["credentialSha2_256"],
            "native_d1_credential_binding",
        )
        self.packet, self.journal, self.token, self.address = packet, journal, token, address
        self.guard(packet["ends"])

    def guard(self, deadline):
        packet, _journal, _token = self.active()
        now = self.clock()
        require(
            type(now) in (int, float)
            and math.isfinite(now)
            and type(deadline) in (int, float)
            and math.isfinite(deadline)
            and packet["starts"] <= now < deadline <= packet["ends"],
            "native_d1_deadline",
        )
        pinned_file(self.packet_path, self.packet_sha2_256, MAX_PACKET_BYTES)
        require(packet["sourcePins"] == source_pins(), "native_d1_source_drift")
        self.source.recheck()
        for record in packet["independentEvidence"].values():
            pinned_file(record["path"], record["sha2_256"], MAX_PACKET_BYTES)
        after = self.clock()
        require(
            type(after) in (int, float) and math.isfinite(after) and now <= after < deadline,
            "native_d1_deadline_after_source",
        )

    def query(self, role, sql, params, deadline):
        # The public REST contract calls meta.changes a rough total_changes()
        # indication. It cannot be normalized into the existing exact single
        # statement commit receipt. No evidence-file flag can enable this path.
        require(role in ("observer", "snapshot"), "native_d1_exact_commit_receipt_unavailable")
        if not self.lock.acquire(blocking=False):
            raise adapter.Refusal("native_d1_concurrent_call")
        try:
            self.guard(deadline)
            packet, journal, token = self.active()
            ordinal, remaining = journal.remaining(packet["maxTotalBytes"], deadline)
            descriptor = {"role": role, "sql": sql, "params": params}
            require(
                ordinal < len(packet["queries"]) and packet["queries"][ordinal] == descriptor,
                "native_d1_query_manifest_mismatch",
            )
            cap = min(packet["maxResponseBytes"], remaining)
            require(cap > 0, "native_d1_budget_exhausted")
            body = canonical({"sql": sql, "params": params})
            path = (
                f"/client/v4/accounts/{packet['accountId']}"
                f"/d1/database/{packet['databaseId']}/query"
            )
            headers = {
                "Host": "api.cloudflare.com",
                "Connection": "close",
                "Content-Length": str(len(body)),
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
                "Authorization": "Bearer " + token,
            }
            wire = (
                f"POST {path} HTTP/1.1\r\n"
                + "".join(f"{key}: {value}\r\n" for key, value in headers.items())
                + "\r\n"
            ).encode() + body
            claimed = journal.reserve_request(
                encode(descriptor), cap, packet["maxTotalBytes"], len(packet["queries"]), deadline
            )
            require(claimed == ordinal, "native_d1_concurrent_ordinal")
            self.guard(deadline)
            request = Request(
                "https://api.cloudflare.com" + path,
                headers,
                min(packet["timeoutSeconds"], deadline - self.clock()),
                cap,
                min(deadline, self.clock() + packet["timeoutSeconds"]),
                wire,
            )
            response = _pinned_https(
                request,
                self.address,
                self.clock,
                lambda: self.guard(request.deadline),
                discard_set_cookie=True,
            )
            self.guard(deadline)
            rows = _rows(response, cap)
            require(
                type(response.wire_bytes) is int
                and len(response.body) <= response.wire_bytes <= cap,
                "native_d1_wire_bytes",
            )
            payload = _json(response.body)["result"][0]
            # Optional in vendor API means absent/false cannot prove PRIMARY.
            require(payload["meta"].get("served_by_primary") is True, "native_d1_primary_unproved")
            # Fail closed on future result/completion signals, at either level.
            require(
                not any(
                    key in _json(response.body)
                    for key in ("result_info", "cursor", "has_more", "next", "truncated")
                ),
                "native_d1_incomplete",
            )
            journal.received(ordinal, response.wire_bytes, deadline)
            self.guard(deadline)
            return rows, payload["meta"]
        except Exception:
            # No private query, token, row or provider error is exposed. Reserved
            # ordinal/ceiling stays spent on ALL unknown outcomes; never replay.
            raise adapter.Refusal("native_d1_refused_or_unknown_no_replay") from None
        finally:
            self.lock.release()


class Provider:
    def __init__(self, binding):
        self.binding = binding

    def dispatch(self, update, deadline):
        require(
            type(update) is adapter.FixedUpdate and update.boundary == "single_fixed_update",
            "native_d1_fixed_update",
        )
        # Fail BEFORE reservation/credential/network. A material fixed-protocol
        # amendment or independently established supported exact receipt is
        # required; adding SELECT changes()/RETURNING here would change it.
        raise adapter.Refusal("native_d1_exact_commit_receipt_unavailable")


class Observer:
    def __init__(self, binding):
        self.binding = binding

    def read(self, sql, deadline):
        # Own PRIMARY HTTPS request, not the writer result or a replica/cache.
        rows, _meta = self.binding.query("observer", sql, [], deadline)
        return adapter.CompleteRows(rows, True)


class CompleteReader:
    def __init__(self, binding):
        self.binding = binding

    def collect(self, profile_path, profile_sha2_256, deadline, *, page_size=128):
        """Complete private typed return; caller owns approved private sink."""
        self.binding.guard(deadline)
        require(
            profile_sha2_256 == self.binding.packet["profileSha2_256"],
            "native_d1_snapshot_profile_binding",
        )
        profile = _json(pinned_file(profile_path, profile_sha2_256, MAX_PACKET_BYTES))
        require(profile.get("profile") == NO_REAL_PROFILE, "native_d1_no_real_profile")

        def query(sql):
            return self.binding.query("snapshot", sql, [], deadline)[0]

        result = collect_snapshot(query, page_size=page_size, profile_manifest=profile)
        self.binding.guard(deadline)
        ordinal, _remaining = self.binding.journal.remaining(
            self.binding.packet["maxTotalBytes"], deadline
        )
        # Explicit manifest exhaustion at the end of complete capture. Control
        # can precede capture; subsequent independent phases need a later packet,
        # never an implicit added query or a reset of this retained journal.
        require(ordinal == len(self.binding.packet["queries"]), "native_d1_unused_queries")
        return result


class FileConfirmations:
    """Read-only independent custodian; cannot create/upgrade a confirmation.

    A trusted integration supplies an independently retained index pin and
    expected producer identity. The producer must observe the actual timely
    returned result AFTER final journal acknowledgment, source and deadline
    checks, and retain the exact writer/complete PRIMARY evidence. This module
    authenticates retained bytes under that external custody trust; JSON labels
    alone, caller Result objects and current state have no confirmation power.
    Independent attestation/custody qualification remains a factual gate.
    """

    def __init__(self, index_path, index_sha2_256, producer, target_id, candidate, clock):
        self.index_path, self.index_sha2_256, self.producer = index_path, index_sha2_256, producer
        self.target_id, self.candidate, self.clock = target_id, candidate, clock

    def read(self, reference, deadline):
        now = self.clock()
        require(
            type(now) in (int, float) and math.isfinite(now) and now < deadline,
            "native_d1_confirmation_deadline",
        )
        index: Any = _json(pinned_file(self.index_path, self.index_sha2_256, MAX_PACKET_BYTES))
        require(
            type(index) is dict
            and set(index) == {"producer", "receipts"}
            and index["producer"] == self.producer
            and type(index["receipts"]) is dict
            and reference in index["receipts"],
            "native_d1_confirmation_producer",
        )
        record: Any = cast(Any, index)["receipts"][reference]
        require(
            type(record) is dict and set(record) == {"path", "sha2_256"},
            "native_d1_confirmation_record",
        )
        receipt: Any = _json(pinned_file(record["path"], record["sha2_256"], MAX_PACKET_BYTES))
        require(
            type(receipt) is dict
            and set(receipt) == {"reference", "producer", "intent", "returnedResult", "evidence"}
            and receipt["reference"] == reference
            and receipt["producer"] == self.producer,
            "native_d1_confirmation_shape",
        )
        receipt = cast(Any, receipt)
        intent = intent_from(receipt["intent"])
        result = adapter.Result(**cast(Any, receipt["returnedResult"]))
        at = result.confirmed_at
        require(
            intent.target_id == self.target_id
            and intent.candidate == self.candidate
            and result.status == "confirmed"
            and result.reason == "one_row_and_independent_readback"
            and result.observed_generation == intent.next_generation
            and result.observed_state == intent.target
            and at is not None
            and type(at) in (int, float)
            and math.isfinite(at)
            and intent.window.starts <= at < intent.window.dispatch_until
            and at <= now,
            "native_d1_confirmation_not_returned_confirmed",
        )
        evidence: Any = receipt["evidence"]
        require(
            type(evidence) is dict
            and set(evidence)
            == {"oneRowCommit", "completePrimaryReadback", "finalJournalAck", "returnedInvocation"},
            "native_d1_confirmation_evidence",
        )
        for value in cast(dict[str, Any], evidence).values():
            require(
                type(value) is dict and set(value) == {"path", "sha2_256"},
                "native_d1_confirmation_evidence_record",
            )
            pinned_file(value["path"], value["sha2_256"], MAX_PACKET_BYTES)
        require(now <= self.clock() < deadline, "native_d1_confirmation_late")
        return adapter.ConfirmedReceipt(reference, intent, result)


class SyntheticSuccessorBinding(Binding):
    """Executable finite model of the exact REST candidate, with no native sender.

    Only activate_synthetic(exchange) is supported. The supplied trusted test
    exchange consumes a fully framed candidate Request; this class never calls
    _pinned_https, discovers credentials or exposes a production activation API.
    The unchanged native named parameter lacks a supported D1 basis today.
    """

    SYNTHETIC_TOKEN = "synthetic-qualification-only-no-provider-credential"

    def _codec(self):
        return exact_receipt_successor

    def build_batch(self, intent):
        return self._codec().build(intent)

    def activate(self, credential_loader):
        raise adapter.Refusal("successor_production_capability_not_qualified")

    def activate_synthetic(self, exchange):
        require(callable(exchange), "synthetic_exchange_required")
        raw = pinned_file(self.packet_path, self.packet_sha2_256, MAX_PACKET_BYTES)
        packet = _json(raw)
        require(
            packet.get("credentialSha2_256") == sha2_256(self.SYNTHETIC_TOKEN.encode()),
            "synthetic_credential_only",
        )
        allocation_record = packet["independentEvidence"]["allocation"]
        allocation_raw = pinned_file(
            allocation_record["path"], allocation_record["sha2_256"], MAX_PACKET_BYTES
        )
        allocation: Any = _json(allocation_raw)
        require(
            type(allocation) is dict
            and set(allocation) == {"kind", "protocol", "intents", "requests", "limits"}
            and allocation["kind"] == "SYNTHETIC_QUALIFICATION_ONLY"
            and allocation["protocol"] == self._codec().BOUNDARY,
            "synthetic_exact_allocation",
        )
        allocation = cast(dict[str, Any], allocation)
        require(
            type(allocation["intents"]) is list and 1 <= len(allocation["intents"]) <= 3,
            "synthetic_intent_inventory",
        )
        intents = [intent_from(value) for value in allocation["intents"]]
        intent = intents[0]
        self._codec().build_root(intent)
        require(
            intent.target_id == packet["targetId"]
            and intent.candidate == packet["candidate"]
            and intent.window.starts == packet["starts"]
            and intent.window.reconcile_until == packet["ends"],
            "synthetic_immutable_intent_binding",
        )
        require(len(intents) <= intent.transition_limit, "synthetic_campaign_headroom")
        for index, current in enumerate(intents):
            self._codec().build(current)
            require(
                current.target_id == intent.target_id
                and current.candidate == intent.candidate
                and current.window == intent.window
                and current.transition_limit == intent.transition_limit
                and current.key not in [prior.key for prior in intents[:index]]
                and (
                    index == 0
                    or (
                        current.expected == intents[index - 1].next_generation
                        and current.operation != intents[index - 1].operation
                    )
                ),
                "synthetic_campaign_intent_binding",
            )
        limits = cast(dict[str, int], allocation["limits"])
        require(
            type(limits) is dict
            and set(limits) == {"requests", "statements", "requestBytes", "responseBytes"}
            and all(type(value) is int and value > 0 for value in limits.values())
            and limits["requests"] == len(packet["queries"])
            and limits["requests"] <= MAX_QUERIES
            and limits["requests"] <= limits["statements"] <= MAX_QUERIES
            and limits["requestBytes"] <= MAX_TOTAL_BYTES
            and limits["responseBytes"] == packet["maxTotalBytes"],
            "synthetic_finite_limits",
        )
        requests = cast(list[dict[str, Any]], allocation["requests"])
        require(
            type(requests) is list and len(requests) == len(packet["queries"]),
            "synthetic_request_manifest",
        )
        writer_index = 0
        for query, request in zip(packet["queries"], requests, strict=True):
            count = 2 if query["role"] == "writer" else 1
            if count == 2:
                require(writer_index < len(intents), "synthetic_extra_writer")
                batch = self.build_batch(intents[writer_index])
                require(
                    query["sql"] == batch.update_sql and query["params"] == [batch.intent.expected],
                    "synthetic_writer_intent_manifest",
                )
                expected = self._codec().manifest(batch)
                writer_index += 1
            else:
                body = canonical({"sql": query["sql"], "params": query["params"]})
                expected = {
                    "protocol": "independent_primary_read",
                    "statementCount": 1,
                    "requestBodySha2_256": sha2_256(body),
                    "statements": [{"sql": query["sql"], "params": query["params"]}],
                }
            require(request == expected, "synthetic_exact_statement_manifest")
        require(writer_index == len(intents), "synthetic_missing_writer")
        # The parent activation checks every retained source/evidence/journal pin
        # and exact fixed SQL before delivering this constant noncredential.
        Binding.activate(self, lambda: self.SYNTHETIC_TOKEN)
        self.allocation, self.allocation_raw, self.exchange = allocation, allocation_raw, exchange
        self.packet_raw = raw
        self.source_target = packet["targetId"]
        self.read_evidence = []

    def guard(self, deadline):
        super().guard(deadline)
        # Parent activation calls guard before synthetic fields are installed.
        if hasattr(self, "packet_raw"):
            require(canonical(self.packet) == self.packet_raw, "synthetic_packet_memory_drift")
            require(
                canonical(self.allocation) == self.allocation_raw,
                "synthetic_allocation_memory_drift",
            )

    def query(self, role, sql, params, deadline):
        require(role in ("observer", "snapshot"), "synthetic_read_role")
        rows, meta, _body = self._request(role, sql, params, deadline)
        return rows, meta

    def dispatch_batch(self, batch, deadline):
        require(
            type(batch) is type(self.build_batch(batch.intent))
            and batch == self.build_batch(batch.intent),
            "synthetic_exact_batch",
        )
        packet, journal, _token = self.active()
        intent = batch.intent
        root = intent_from(self.allocation["intents"][0])
        require(
            intent.target_id == root.target_id
            and intent.candidate == root.candidate
            and intent.window == root.window
            and intent.transition_limit == root.transition_limit,
            "synthetic_batch_immutable_binding",
        )
        require(asdict(intent) in self.allocation["intents"], "synthetic_unretained_intent")
        entry = journal.get(intent.key, deadline)
        require(
            entry.intent == intent
            and entry.dispatch_claimed is True
            and entry.phase == "dispatching",
            "synthetic_durable_dispatch_required",
        )
        _rows_unused, _meta, body = self._request(
            "writer", batch.update_sql, [intent.expected], deadline, batch=batch
        )
        decoded = self._codec().decode_ordered_body(body)
        return successor_control.SyntheticBatchReceipt(
            batch,
            decoded.count,
            canonical(
                {
                    "scope": "SYNTHETIC_QUALIFICATION_ONLY",
                    "target": packet["targetId"],
                    "packet": self.packet_sha2_256,
                    "intent": asdict(intent),
                    "receipt": self._codec().receipt_manifest(batch, body),
                }
            ),
        )

    def _request(self, role, sql, params, deadline, *, batch=None):
        require(hasattr(self, "exchange"), "synthetic_inert")
        if not self.lock.acquire(blocking=False):
            raise adapter.Refusal("synthetic_concurrent_call")
        try:
            self.guard(deadline)
            packet, journal, token = self.active()
            ordinal, remaining = journal.remaining(packet["maxTotalBytes"], deadline)
            descriptor = {"role": role, "sql": sql, "params": params}
            require(
                ordinal < len(packet["queries"]) and packet["queries"][ordinal] == descriptor,
                "synthetic_query_manifest_mismatch",
            )
            body = (
                self._codec().request_body(batch)
                if batch is not None
                else canonical({"sql": sql, "params": params})
            )
            manifest = self.allocation["requests"][ordinal]
            require(
                sha2_256(body) == manifest["requestBodySha2_256"],
                "synthetic_request_body_binding",
            )
            cap = min(packet["maxResponseBytes"], remaining)
            require(cap > 0, "synthetic_response_budget")
            path = (
                f"/client/v4/accounts/{packet['accountId']}"
                f"/d1/database/{packet['databaseId']}/query"
            )
            headers = {
                "Host": "api.cloudflare.com",
                "Connection": "close",
                "Content-Length": str(len(body)),
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
                "Authorization": "Bearer " + token,
            }
            wire = (
                f"POST {path} HTTP/1.1\r\n"
                + "".join(f"{key}: {value}\r\n" for key, value in headers.items())
                + "\r\n"
            ).encode() + body
            claimed = journal.reserve_exact_request(
                manifest,
                cap,
                len(wire),
                self.allocation["limits"],
                deadline,
                intent=None if batch is None else batch.intent,
            )
            require(claimed == ordinal, "synthetic_concurrent_ordinal")
            self.guard(deadline)
            request = Request(
                "https://api.cloudflare.com" + path,
                headers,
                min(packet["timeoutSeconds"], deadline - self.clock()),
                cap,
                min(deadline, self.clock() + packet["timeoutSeconds"]),
                wire,
            )
            response = self.exchange(
                request,
                self.address,
                self.clock,
                lambda: self.guard(request.deadline),
                discard_set_cookie=True,
            )
            self.guard(request.deadline)
            require(
                type(response) is Response
                and response.status == 200
                and response.headers == {"content-type": "application/json"}
                and type(response.wire_bytes) is int
                and len(response.body) <= response.wire_bytes <= cap,
                "synthetic_complete_http_response",
            )
            if batch is not None:
                self._codec().decode_ordered_body(response.body)
                rows, meta = [], {}
            else:
                rows = _rows(response, cap)
                payload = _json(response.body)
                meta = payload["result"][0]["meta"]
                require(meta.get("served_by_primary") is True, "synthetic_primary_unproved")
                require(
                    not any(
                        key in payload
                        for key in ("result_info", "cursor", "has_more", "next", "truncated")
                    ),
                    "synthetic_incomplete_read",
                )
            journal.received(ordinal, response.wire_bytes, request.deadline)
            self.guard(request.deadline)
            if batch is None:
                self.read_evidence.append(
                    {
                        "requestOrdinal": ordinal,
                        "request": manifest,
                        "responseBodySha2_256": sha2_256(response.body),
                        "wireBytes": response.wire_bytes,
                        "primary": True,
                        "complete": True,
                    }
                )
            return rows, meta, response.body
        except Exception:
            raise adapter.Refusal("synthetic_refused_or_unknown_no_replay") from None
        finally:
            self.lock.release()


class SyntheticPositionalSuccessorBinding(SyntheticSuccessorBinding):
    """Explicit accepted #0250 model selection; production activation still refuses."""

    def _codec(self):
        return positional_receipt_successor

    def _fixed_writer_sqls(self, fixed):
        return [
            positional_receipt_successor.source_sql(operation) for operation in ("close", "reopen")
        ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    # Deliberately no live flags, packet auto-discovery, file or credential reads.
    print("INERT: separately reviewed finite operator packet required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
