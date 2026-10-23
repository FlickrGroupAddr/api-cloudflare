"""Explicit finite numeric-TLS census transport; default HttpsGet stays disabled.

MIT License; copyright 2026 Terry Ott. No credentials or provider calls on import,
construction or journal preparation. The operator owns later factual qualification.
"""

from __future__ import annotations

import hashlib
import math
import re
import sys
import threading
import time
import types
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[2]
_BINDING = ROOT / "probes/pmb1-native-d1-binding/binding.py"
_POPULATION_PATH = Path(__file__).resolve().with_name("population.py")
_POPULATION: Any = None
_POPULATION_BYTES: bytes | None = None
_POPULATION_EXPORTS: dict[str, Any] = {}
_POPULATION_METHODS: list[tuple[Any, str, Any]] = []
_LIB: Any = None
_LIB_BYTES: bytes | None = None
_LIB_EXPORTS: dict[str, Any] = {}
HEX = re.compile(r"[a-f0-9]{64}")
MAX_PACKET = 4 * 1024 * 1024


class Refused(ValueError):
    """Sanitized transport category; no provider body or credential."""


def _population():
    """One fixed sibling module; no ambient population import or plugin graph."""
    global _POPULATION, _POPULATION_BYTES, _POPULATION_EXPORTS, _POPULATION_METHODS
    if _POPULATION is None:
        _POPULATION_BYTES = _POPULATION_PATH.read_bytes()
        module = types.ModuleType(f"_pmb1_census_population_{id(_POPULATION_BYTES):x}")
        module.__file__ = str(_POPULATION_PATH)
        # Dataclasses require their exact defining module for annotations.
        sys.modules[module.__name__] = module
        exec(compile(_POPULATION_BYTES, str(_POPULATION_PATH), "exec"), module.__dict__)
        _POPULATION = module
        _POPULATION_EXPORTS = {
            name: value for name, value in vars(module).items() if callable(value)
        }
        _POPULATION_METHODS = [
            (cls, name, value)
            for cls in (module.Census, module.HttpsGet)
            for name, value in vars(cls).items()
            if callable(value)
        ]
    _require(
        _POPULATION_PATH.read_bytes() == _POPULATION_BYTES
        and sys.modules.get(_POPULATION.__name__) is _POPULATION
        and all(getattr(_POPULATION, name) is value for name, value in _POPULATION_EXPORTS.items())
        and all(getattr(cls, name) is value for cls, name, value in _POPULATION_METHODS),
        "native_census_population_drift",
    )
    return _POPULATION


def _require(ok, category):
    if not ok:
        raise Refused(category)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    # The reused closed graph owns the existing strict JSON parser/canonicalizer.
    return _library().canonical(value)


def _library():
    """Reuse the reviewed project's closed loader, not an ambient scripts import.

    Its entire executable project graph and bound exports are rechecked on every
    guard. This is a deliberately broad dependency on the existing D1 operator
    library; the census never constructs its D1 binding or calls its SQL methods.
    """
    global _LIB, _LIB_BYTES, _LIB_EXPORTS
    if _LIB is None:
        _LIB_BYTES = _BINDING.read_bytes()
        module = types.ModuleType("_pmb1_census_fixed_binding")
        module.__file__ = str(_BINDING)
        exec(compile(_LIB_BYTES, str(_BINDING), "exec"), module.__dict__)
        _LIB = module
        _LIB_EXPORTS = {
            name: getattr(module, name)
            for name in (
                "source_pins",
                "_pinned_https",
                "_address",
                "Request",
                "SQLiteJournal",
                "_json",
                "canonical",
            )
        }
    _require(
        _BINDING.read_bytes() == _LIB_BYTES
        and all(getattr(_LIB, key) is value for key, value in _LIB_EXPORTS.items()),
        "native_census_library_drift",
    )
    _LIB.source_pins()
    return _LIB


def source_pins():
    """Exact executable graph inventory, not an independent source oracle."""
    library = _library()
    _population()
    return {
        **library.source_pins(),
        **{
            str(path.relative_to(ROOT)).replace("\\", "/"): _sha(path.read_bytes())
            for path in (Path(__file__), Path(__file__).with_name("population.py"))
        },
    }


def _pinned_file(path, expected):
    path = Path(path)
    _require(
        path.is_absolute() and not path.is_symlink() and HEX.fullmatch(expected),
        "native_census_retained_record",
    )
    with path.open("rb") as stream:
        raw = stream.read(MAX_PACKET + 1)
    _require(len(raw) <= MAX_PACKET and _sha(raw) == expected, "native_census_retained_pin")
    return raw


class FiniteHttpsGet:
    """Later explicit activation selects one retained packet and credential.

    Uses the existing concrete header/framing/wire/deadline-bounded numeric-TLS
    client. There is no resolver, redirect, retry, cookie jar or ambient token.
    Each request reserves a durable external ordinal/byte ceiling before sockets;
    unknown outcomes remain spent. Restart/reconstruction cannot restart a census.
    """

    def __init__(self, packet_path, packet_sha2_256, journal_path, *, clock=time.monotonic):
        self.packet_path, self.packet_sha2_256, self.journal_path = (
            packet_path,
            packet_sha2_256,
            journal_path,
        )
        self.clock = clock
        self.packet: Any = None
        self.journal: Any = None
        self.token: str | None = None
        self.address: Any = None
        self.failed = False
        self.collected = False
        self.lock = threading.Lock()

    def _packet(self):
        library = _library()
        value: dict[str, Any] = library._json(_pinned_file(self.packet_path, self.packet_sha2_256))
        _require(
            type(value) is dict
            and set(value)
            == {
                "schema",
                "accountId",
                "selectedNamespaces",
                "address",
                "starts",
                "ends",
                "timeoutSeconds",
                "maxCalls",
                "maxResponseBytes",
                "maxTotalBytes",
                "credentialSha2_256",
                "sourcePins",
                "independentEvidence",
                "expectedPopulationSha2_256",
            },
            "native_census_packet_shape",
        )
        _require(
            value["schema"] == "pmb1-finite-native-census-packet-v1"
            and re.fullmatch(r"[a-f0-9]{32}", value["accountId"]),
            "native_census_account",
        )
        selected = value["selectedNamespaces"]
        _require(
            type(selected) is list
            and 1 <= len(selected) <= 128
            and all(type(ns) is str and re.fullmatch(r"[a-f0-9]{32}", ns) for ns in selected)
            and len(set(selected)) == len(selected),
            "native_census_namespaces",
        )
        _require(value["sourcePins"] == source_pins(), "native_census_source_pins")
        for name in ("starts", "ends", "timeoutSeconds"):
            _require(
                type(value[name]) in (int, float) and math.isfinite(value[name]),
                "native_census_time",
            )
        _require(
            0 <= value["starts"] < value["ends"]
            and value["ends"] - value["starts"] <= 30
            and 0 < value["timeoutSeconds"] <= 30,
            "native_census_time",
        )
        for name, ceiling in (
            ("maxCalls", 64),
            ("maxResponseBytes", 262144),
            ("maxTotalBytes", 4194304),
        ):
            _require(
                type(value[name]) is int and 1 <= value[name] <= ceiling, "native_census_limits"
            )
        _require(
            HEX.fullmatch(value["credentialSha2_256"])
            and HEX.fullmatch(value["expectedPopulationSha2_256"]),
            "native_census_input_pins",
        )
        evidence: dict[str, Any] = value["independentEvidence"]
        _require(
            type(evidence) is dict
            and set(evidence)
            == {
                "review",
                "grant",
                "custody",
                "inventory",
                "sourceOracle",
                "allWriterInterval",
                "allocation",
            },
            "native_census_evidence",
        )
        for record in evidence.values():
            _require(
                type(record) is dict and set(record) == {"path", "sha2_256"},
                "native_census_evidence",
            )
            _pinned_file(record["path"], record["sha2_256"])
        return value, library._address(value["address"])

    def prepare_journal(self):
        """Explicit external local preparation only; never automatic creation."""
        packet, _address = self._packet()
        library = _library()
        library.SQLiteJournal(
            self.journal_path, packet["accountId"], self.packet_sha2_256, self.clock
        ).provision(packet["ends"])

    def activate(self, credential_loader):
        _require(
            self.packet is None and self.token is None and not self.failed,
            "native_census_already_active",
        )
        packet, address = self._packet()
        library = _library()
        journal = library.SQLiteJournal(
            self.journal_path, packet["accountId"], self.packet_sha2_256, self.clock
        )
        ordinal, _remaining = journal.remaining(packet["maxTotalBytes"], packet["ends"])
        _require(ordinal == 0, "native_census_attempt_spent")
        now = self.clock()
        _require(
            packet["starts"] <= now < packet["ends"] and callable(credential_loader),
            "native_census_activation_window",
        )
        token: Any = credential_loader()
        _require(
            type(token) is str
            and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token)
            and _sha(token.encode("ascii")) == packet["credentialSha2_256"],
            "native_census_credential_pin",
        )
        self.packet, self.journal, self.token, self.address = (
            packet,
            journal,
            cast(str, token),
            address,
        )
        self._guard(packet["ends"])

    def _guard(self, deadline):
        _require(
            self.packet is not None and self.token is not None and not self.failed,
            "native_census_inert_or_spent",
        )
        packet = cast(dict[str, Any], self.packet)
        now = self.clock()
        _require(
            type(now) in (int, float)
            and math.isfinite(now)
            and packet["starts"] <= now < deadline <= packet["ends"],
            "native_census_deadline",
        )
        _require(
            _pinned_file(self.packet_path, self.packet_sha2_256) is not None
            and packet["sourcePins"] == source_pins(),
            "native_census_source_drift",
        )
        for record in packet["independentEvidence"].values():
            _pinned_file(record["path"], record["sha2_256"])
        _require(now <= self.clock() < deadline, "native_census_deadline")

    def _path(self, path):
        prefix = f"/client/v4/accounts/{self.packet['accountId']}/workers/durable_objects/"
        _require(
            type(path) is str and path.startswith(prefix) and path.isascii() and len(path) <= 16384,
            "native_census_path",
        )
        suffix = path[len(prefix) :]
        route, sep, query = suffix.partition("?")
        _require(sep and query, "native_census_path")
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True)
        params = dict(pairs)
        _require(len(params) == len(pairs) and urlencode(pairs) == query, "native_census_query")
        if route == "namespaces":
            _require(
                set(params) == {"page", "per_page"}
                and params["per_page"] == "10"
                and re.fullmatch(r"[1-9][0-9]?", params["page"])
                and int(params["page"]) <= 32,
                "native_census_query",
            )
        else:
            match = re.fullmatch(r"namespaces/([a-f0-9]{32})/objects", route)
            _require(
                match
                and match[1] in self.packet["selectedNamespaces"]
                and set(params) in ({"limit"}, {"limit", "cursor"})
                and params["limit"] == "10"
                and ("cursor" not in params or 0 < len(params["cursor"].encode()) <= 4096),
                "native_census_query",
            )

    def __call__(self, path, cap, remaining):
        _require(self.lock.acquire(blocking=False), "native_census_concurrent_call")
        try:
            _require(
                type(remaining) in (int, float) and math.isfinite(remaining) and remaining > 0,
                "native_census_deadline",
            )
            _require(self.packet is not None, "native_census_inert_or_spent")
            deadline = min(
                self.packet["ends"],
                self.clock() + remaining,
                self.clock() + self.packet["timeoutSeconds"],
            )
            self._guard(deadline)
            self._path(path)
            _require(
                type(cap) is int and 0 < cap <= self.packet["maxResponseBytes"],
                "native_census_wire_bound",
            )
            ordinal, budget = self.journal.remaining(self.packet["maxTotalBytes"], deadline)
            _require(ordinal < self.packet["maxCalls"] and cap <= budget, "native_census_budget")
            with self.journal.transaction(deadline) as db:
                _require(
                    db.execute("SELECT 1 FROM requests WHERE query=?", (path,)).fetchone() is None,
                    "native_census_path_already_spent",
                )
            headers = {
                "Host": "api.cloudflare.com",
                "Connection": "close",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Authorization": "Bearer " + cast(str, self.token),
            }
            wire = (
                f"GET {path} HTTP/1.1\r\n"
                + "".join(f"{name}: {value}\r\n" for name, value in headers.items())
                + "\r\n"
            ).encode("ascii")
            claimed = self.journal.reserve_request(
                path, cap, self.packet["maxTotalBytes"], self.packet["maxCalls"], deadline
            )
            _require(claimed == ordinal, "native_census_concurrent_ordinal")
            library = _library()
            request = library.Request(
                "https://api.cloudflare.com" + path,
                headers,
                min(self.packet["timeoutSeconds"], deadline - self.clock()),
                cap,
                deadline,
                wire,
            )
            response = library._pinned_https(
                request,
                self.address,
                self.clock,
                lambda: self._guard(deadline),
                discard_set_cookie=True,
            )
            self._guard(deadline)
            _require(
                response.status == 200
                and type(response.wire_bytes) is int
                and type(response.body) is bytes
                and len(response.body) <= response.wire_bytes <= cap
                and response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                == "application/json",
                "native_census_response",
            )
            self.journal.received(ordinal, response.wire_bytes, deadline)
            self._guard(deadline)
            return response.body
        except Exception:
            self.failed = True
            raise Refused("native_census_refused_or_unknown_no_replay") from None
        finally:
            self.lock.release()

    def collect(self, expected_account_namespaces, expected_objects):
        """Fixed census orchestration, with account/inventory pinned separately."""
        _require(self.packet is not None, "native_census_inert_or_spent")
        _require(not self.collected and not self.failed, "native_census_attempt_spent")
        self.collected = True
        population = {
            "accountId": self.packet["accountId"],
            "accountNamespaces": expected_account_namespaces,
            "objects": expected_objects,
        }
        _require(
            _sha(_canonical(population)) == self.packet["expectedPopulationSha2_256"]
            and sorted(expected_objects) == sorted(self.packet["selectedNamespaces"]),
            "native_census_expected_inventory_pin",
        )
        return (
            _population()
            .Census(self.packet["accountId"], self)
            .collect(expected_account_namespaces, expected_objects)
        )
