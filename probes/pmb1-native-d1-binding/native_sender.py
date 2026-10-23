"""Concrete finite positional D1 REST sender; trusted admission is external.

Import and construction are inert. The Root composition supplies the frozen core
binding, numeric TLS primitive and an independently retained review pin. An HTTP
response and this source cannot establish managed execution/custody qualification.
"""

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import adapter
import positional_receipt_successor as codec


def json_media_type(value):
    """Accept JSON plus syntactically safe parameters without redoing framing.

    The concrete strict TLS parser owns framing, duplicates, encodings, redirects
    and wire caps. Parameters cannot change this client's UTF-8 JSON decoding.
    """
    if type(value) is not str:
        return False
    value = value.strip(" \t")
    media = re.match(r"application/json(?=[ \t]*(?:;|$))", value, re.IGNORECASE)
    if media is None:
        return False
    token = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
    quoted = r'"(?:[\x20-\x21\x23-\x5b\x5d-\x7e]|\\[\x20-\x7e])*"'
    parameter = re.compile(
        r"[ \t]*;[ \t]*(" + token + r")[ \t]*=[ \t]*(" + token + "|" + quoted + ")"
    )
    position, seen = media.end(), set()
    while value[position:].strip(" \t"):
        match = parameter.match(value, position)
        if match is None:
            return False
        name = match[1].lower()
        if name in seen:
            return False
        seen.add(name)
        parameter_value = match[2]
        if parameter_value.startswith('"'):
            parameter_value = re.sub(r"\\(.)", r"\1", parameter_value[1:-1])
        if name == "charset" and parameter_value.lower() != "utf-8":
            return False
        position = match.end()
    return True


@dataclass(frozen=True)
class NativeBatchReceipt:
    batch: Any
    count: int
    evidence: bytes


@dataclass(frozen=True)
class EvidenceRef:
    path: str
    sha2_256: str


@dataclass(frozen=True)
class ReviewedAdmission:
    """Trusted operator's exact independently retained review, not a packet flag.

    The expected pin/reviewer must arrive outside the action packet, after actual
    independent review of all referenced native evidence. This reader authenticates
    bytes under that trust; it cannot establish that a reviewer or a fact is real.
    No source test, JSON claim, or default value supplies this trust anchor.

    There is deliberately no JSON loader or fact-generating constructor. The
    Primary authenticates provenance AND native meaning before constructing it.
    """

    reviewer: str
    packet_sha2_256: str
    protocol: str
    source_pins: dict[str, str]
    target_id: str
    clock_domain: str
    starts: float
    ends: float
    credential_sha2_256: str
    packet_review: EvidenceRef
    fact_evidence: dict[str, EvidenceRef]

    def recheck(self, core):
        packet_raw = core.pinned_file(core.packet_path, core.packet_sha2_256, core.max_packet_bytes)
        packet = core.json(packet_raw)
        core.require(
            type(self.reviewer) is str
            and 1 <= len(self.reviewer) <= 128
            and self.protocol == codec.BOUNDARY
            and self.packet_sha2_256 == core.packet_sha2_256
            and self.source_pins == core.source_pins()
            and self.target_id == packet["targetId"]
            and self.clock_domain == packet["clockDomain"]
            and self.starts == packet["starts"]
            and self.ends == packet["ends"]
            and self.credential_sha2_256 == packet["credentialSha2_256"],
            "native_sender_independent_admission_binding",
        )
        # Review artifacts must be retained independently of the action packet;
        # putting an admission-shaped document into that packet is insufficient.
        core.require(
            type(self.packet_review) is EvidenceRef
            and Path(self.packet_review.path) != Path(core.packet_path)
            and all(
                Path(self.packet_review.path) != Path(value["path"])
                for value in packet["independentEvidence"].values()
            ),
            "native_sender_independent_admission_path",
        )
        core.require(
            type(self.fact_evidence) is dict
            and set(self.fact_evidence)
            == {
                "sameConnection",
                "orderedTransactionRollbackCommit",
                "noInterleaving",
                "textBinding",
                "primaryCompleteness",
                "protectedDelivery",
                "durableCustody",
                "clockAndWindow",
                "targetCurrentGrant",
                "allWriterInterval",
                "sourceOracle",
                "allocation",
            },
            "native_sender_actual_fact_inventory",
        )
        for reference in [self.packet_review, *self.fact_evidence.values()]:
            core.require(type(reference) is EvidenceRef, "native_sender_fact_reference")
            core.pinned_file(reference.path, reference.sha2_256, core.max_packet_bytes)
        for fact, evidence in {
            "sameConnection": "primaryAndCommitSemantics",
            "orderedTransactionRollbackCommit": "primaryAndCommitSemantics",
            "noInterleaving": "primaryAndCommitSemantics",
            "textBinding": "primaryAndCommitSemantics",
            "primaryCompleteness": "primaryAndCommitSemantics",
            "durableCustody": "custody",
            "targetCurrentGrant": "grant",
            "allWriterInterval": "allWriterInterval",
            "sourceOracle": "sourceOracle",
            "allocation": "allocation",
        }.items():
            core.require(
                asdict(self.fact_evidence[fact]) == packet["independentEvidence"][evidence],
                "native_sender_fact_packet_binding",
            )


class NativePositionalSender:
    """Root-created core supplies the fixed graph and sole concrete HTTPS path.

    No exchange injection, ambient credential discovery, DNS, redirects, retries,
    live CLI or historical single-statement Provider capability is exposed here.
    """

    def __init__(self, core):
        self.core = core
        self.binding = core
        self.admission: ReviewedAdmission | None = None
        self.read_evidence = []

    @property
    def packet(self):
        return self.core.packet

    @property
    def packet_sha2_256(self):
        return self.core.packet_sha2_256

    @property
    def journal(self):
        return self.core.journal

    @property
    def source(self):
        return self.core.source

    @property
    def clock(self):
        return self.core.clock

    @property
    def source_target(self):
        return self.core.active()[0]["targetId"]

    def build_batch(self, intent):
        return codec.build(intent)

    def activate(self, credential_loader, *, admission):
        # Fixed graph resolves this late import; custody itself imports this
        # module's receipt type. There is no ambient plugin/factory discovery.
        import native_custody

        core = self.core
        core.require(self.admission is None, "native_sender_already_active")
        core.require(type(admission) is ReviewedAdmission, "native_sender_admission_required")
        admission.recheck(core)
        delivery = admission.fact_evidence["protectedDelivery"]
        core.require(
            type(credential_loader) is native_custody.ProtectedCredential
            and credential_loader.review_path == delivery.path
            and credential_loader.review_pin == delivery.sha2_256,
            "native_sender_reviewed_protected_delivery",
        )
        credential_loader.validate_binding(
            admission.packet_sha2_256,
            admission.target_id,
            admission.source_pins,
            admission.credential_sha2_256,
            asdict(admission.fact_evidence["targetCurrentGrant"]),
            asdict(admission.fact_evidence["durableCustody"]),
        )
        raw = core.pinned_file(core.packet_path, core.packet_sha2_256, core.max_packet_bytes)
        packet = core.json(raw)
        record = packet["independentEvidence"]["allocation"]
        allocation_raw = core.pinned_file(record["path"], record["sha2_256"], core.max_packet_bytes)
        allocation = core.json(allocation_raw)
        self._validate_allocation(packet, allocation)
        # The core validates exact packet/source/evidence/journal before protected
        # delivery. It has selected positional SQL explicitly in the Root class.
        core._activate_native_core(credential_loader)
        self.packet_raw, self.allocation_raw = raw, allocation_raw
        self.allocation, self.admission = allocation, admission
        self.admission_raw = core.canonical(asdict(admission))
        self.guard(packet["ends"])

    def _validate_allocation(self, packet, allocation):
        core = self.core
        core.require(
            type(allocation) is dict
            and set(allocation) == {"kind", "protocol", "intents", "requests", "limits"}
            and allocation["kind"] == "pmb1-native-positional-allocation-v1"
            and allocation["protocol"] == codec.BOUNDARY,
            "native_sender_allocation_selection",
        )
        core.require(
            type(allocation["intents"]) is list and 1 <= len(allocation["intents"]) <= 3,
            "native_sender_intent_inventory",
        )
        intents = [core.intent_from(value) for value in allocation["intents"]]
        root = intents[0]
        codec.build_root(root)
        core.require(
            root.target_id == packet["targetId"]
            and root.candidate == packet["candidate"]
            and root.window.starts == packet["starts"]
            and root.window.reconcile_until == packet["ends"]
            and len(intents) <= root.transition_limit,
            "native_sender_root_binding",
        )
        for index, intent in enumerate(intents):
            codec.build(intent)
            core.require(
                intent.target_id == root.target_id
                and intent.candidate == root.candidate
                and intent.window == root.window
                and intent.transition_limit == root.transition_limit
                and intent.key not in [prior.key for prior in intents[:index]]
                and (
                    index == 0
                    or (
                        intent.expected == intents[index - 1].next_generation
                        and intent.operation != intents[index - 1].operation
                    )
                ),
                "native_sender_campaign_binding",
            )
        limits = allocation["limits"]
        core.require(
            type(limits) is dict
            and set(limits) == {"requests", "statements", "requestBytes", "responseBytes"}
            and all(type(value) is int and value > 0 for value in limits.values())
            and limits["requests"] == len(packet["queries"])
            and limits["requests"] <= limits["statements"] <= 2048
            and limits["requestBytes"] <= 16 * 1024 * 1024
            and limits["responseBytes"] == packet["maxTotalBytes"],
            "native_sender_finite_limits",
        )
        requests = cast(list[dict[str, Any]], allocation["requests"])
        core.require(
            type(requests) is list and len(requests) == len(packet["queries"]),
            "native_sender_request_inventory",
        )
        writer_index = 0
        for query, request in zip(packet["queries"], requests, strict=True):
            if query["role"] == "writer":
                core.require(writer_index < len(intents), "native_sender_extra_writer")
                batch = codec.build(intents[writer_index])
                core.require(
                    query
                    == {
                        "role": "writer",
                        "sql": batch.update_sql,
                        "params": [batch.intent.expected],
                    },
                    "native_sender_writer_intent",
                )
                expected = codec.manifest(batch)
                writer_index += 1
            else:
                expected = self._read_manifest(query["sql"], query["params"])
            core.require(request == expected, "native_sender_exact_manifest")
        core.require(writer_index == len(intents), "native_sender_missing_writer")
        core.require(
            sum(request["statementCount"] for request in requests) <= limits["statements"],
            "native_sender_full_statement_budget",
        )

    def _read_manifest(self, sql, params):
        return {
            "protocol": "independent_primary_read",
            "statementCount": 1,
            "requestBodySha2_256": self.core.sha2_256(
                self.core.canonical({"sql": sql, "params": params})
            ),
            "statements": [{"sql": sql, "params": params}],
        }

    def guard(self, deadline):
        core = self.core
        core.require(type(self.admission) is ReviewedAdmission, "native_sender_inert")
        admission = cast(ReviewedAdmission, self.admission)
        core.guard(deadline)
        admission.recheck(core)
        core.require(
            core.canonical(core.packet) == self.packet_raw
            and core.canonical(self.allocation) == self.allocation_raw
            and core.canonical(asdict(admission)) == self.admission_raw,
            "native_sender_memory_drift",
        )

    def query(self, role, sql, params, deadline):
        self.core.require(role in ("observer", "snapshot"), "native_sender_read_role")
        rows, meta, _body = self._request(role, sql, params, deadline)
        return rows, meta

    def dispatch_batch(self, batch, deadline):
        core = self.core
        self.guard(deadline)
        core.require(
            type(batch) is codec.FixedPositionalBatch and batch == codec.build(batch.intent),
            "native_sender_fixed_batch",
        )
        core.require(
            asdict(batch.intent) in self.allocation["intents"], "native_sender_unretained_intent"
        )
        entry = self.journal.get(batch.intent.key, deadline)
        core.require(
            entry.intent == batch.intent
            and entry.dispatch_claimed is True
            and entry.phase == "dispatching",
            "native_sender_durable_dispatch",
        )
        _rows, _meta, body = self._request(
            "writer", batch.update_sql, [batch.intent.expected], deadline, batch=batch
        )
        decoded = codec.decode_ordered_body(body)
        return NativeBatchReceipt(
            batch,
            decoded.count,
            core.canonical(
                {
                    "scope": "NATIVE_RETURNED_HTTP_EVIDENCE",
                    "target": self.source_target,
                    "packet": self.packet_sha2_256,
                    "intent": asdict(batch.intent),
                    "receipt": codec.receipt_manifest(batch, body),
                }
            ),
        )

    def _request(self, role, sql, params, deadline, *, batch=None):
        core = self.core
        if not core.lock.acquire(blocking=False):
            raise adapter.Refusal("native_sender_concurrent_call")
        try:
            self.guard(deadline)
            packet, journal, token = core.active()
            ordinal, remaining = journal.remaining(packet["maxTotalBytes"], deadline)
            core.require(
                ordinal < len(packet["queries"])
                and packet["queries"][ordinal] == {"role": role, "sql": sql, "params": params},
                "native_sender_query_order",
            )
            body = (
                codec.request_body(batch)
                if batch is not None
                else core.canonical({"sql": sql, "params": params})
            )
            manifest = self.allocation["requests"][ordinal]
            core.require(
                core.sha2_256(body) == manifest["requestBodySha2_256"], "native_sender_body_binding"
            )
            cap = min(packet["maxResponseBytes"], remaining)
            core.require(cap > 0, "native_sender_response_budget")
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
            core.require(claimed == ordinal, "native_sender_concurrent_ordinal")
            self.guard(deadline)
            now = core.clock()
            request = core.Request(
                "https://api.cloudflare.com" + path,
                headers,
                min(packet["timeoutSeconds"], deadline - now),
                cap,
                min(deadline, now + packet["timeoutSeconds"]),
                wire,
            )
            response = core.pinned_https(
                request,
                core.address,
                core.clock,
                lambda: self.guard(request.deadline),
                discard_set_cookie=True,
            )
            self.guard(request.deadline)
            core.require(
                type(response) is core.Response
                and response.status == 200
                and type(response.headers) is dict
                and json_media_type(response.headers.get("content-type"))
                and type(response.wire_bytes) is int
                and len(response.body) <= response.wire_bytes <= cap,
                "native_sender_complete_http_response",
            )
            if batch is not None:
                codec.decode_ordered_body(response.body)
                rows, meta = [], {}
            else:
                rows = core.rows(response, cap)
                payload = core.json(response.body)
                meta = payload["result"][0]["meta"]
                core.require(
                    meta.get("served_by_primary") is True
                    and not any(
                        key in payload
                        for key in ("result_info", "cursor", "has_more", "next", "truncated")
                    ),
                    "native_sender_complete_primary",
                )
            journal.received(ordinal, response.wire_bytes, request.deadline)
            self.guard(request.deadline)
            if batch is None:
                self.read_evidence.append(
                    {
                        "requestOrdinal": ordinal,
                        "request": manifest,
                        "responseBodySha2_256": core.sha2_256(response.body),
                        "wireBytes": response.wire_bytes,
                        "primary": True,
                        "complete": True,
                    }
                )
            return rows, meta, response.body
        except Exception:
            raise adapter.Refusal("native_sender_refused_or_unknown_no_replay") from None
        finally:
            core.lock.release()
