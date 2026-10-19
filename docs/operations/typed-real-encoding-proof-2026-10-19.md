# Typed REAL decimal encoding: bounded source proof

Date: 2026-10-19. Status: **unselected source prototype and precise refusal
handoff; full-state REAL extraction remains NO-GO**. Independent High review
passed after the precision-count correction. No accepted numeric domain, equality rule, trust boundary, current
reader or codec changes here. Completed #0170/#0171 and the reviewed
[REAL feasibility record](real-snapshot-extraction-feasibility-2026-10-18.md)
remain unchanged.

## Outcome

The small candidate at `probes/typed-real-encoding/` combines SQLite's documented
`printf('%!.26g', x)`, a same-statement SQL guard, bounded typed JSON text, Python's
ordinary decimal parser, and an independent exact rational rounding oracle.
For the finite nonzero local boundary corpus it preserves the direct persisted
read's binary64 value and existing canonical `float.hex()` cell exactly.

**This does not qualify arbitrary REAL cells.** Every REAL zero refuses, including
an exhausted token bucket. Nonfinite cells refuse. Any refusal must abort an entire
future capture, never omit a cell, table or row. The current complete reader
continues refusing every REAL through `lossless_real_transport_unqualified`;
the probe has no production imports, adapter, query generator or capture writer.

Two gaps remain: proving zero-sign preservation for the actual persisted managed
read, and establishing that the managed engine's guarded decimal inverse agrees
with exact nearest/even binary64 decoding. Local tests establish neither for D1.
No new trust service, bit-decoding SQL, extension or comparator is proposed.

## Authority and target

Repository guidance and the canonical
[documentation authority hierarchy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
control. Accepted ADR0050/0051/0052 retain conventional native-first evaluation
and existing exact-preservation obligations. ADR0058's permitted undisclosed D1
SQLite version is a provenance exception, not a numeric fidelity guarantee.
The controlling local canonical cell implementation remains
`scripts/fixed_origin_preservation.py` (`_cell`, `_canonical_real`); the refusal
remains in `scripts/private_d1_snapshot_codec.py` (`_decode_cell`).

The target is the actual storage-class-tagged binary64 value read from a
persisted SQLite cell. It is not the insertion decimal, Python parameter,
pre-write JavaScript Number, or physical record bytes. SQLite REAL affinity may
store an integral REAL using an integer record and expose it as REAL. Tag the
unmodified column with `typeof(x)` in the same statement as its payload and guard.
See [SQLite type affinity](https://sqlite.org/datatype3.html#type_affinity).

## Minimal candidate and refusal rules

`CELL_SQL` is a fixed synthetic single-column SELECT, ordered by a synthetic
integer key. It emits exactly `type`, `decimal`, `guard`. It is deliberately not
a complete snapshot query or row-identity protocol. A future approved reader
would retain the original row identity, type and these fields in each approved
page statement under the continuous writer barrier.

- `type = typeof(x)` from the original column.
- `decimal = printf('%!.26g', x)` as SQL TEXT, before JSON serialization.
- `guard = 1` only when `typeof(x) = 'real'`, `x != 0.0`,
  `x BETWEEN -1.7976931348623157e308 AND 1.7976931348623157e308`, and
  `CAST(printf('%!.26g', x) AS REAL) = x`. A CASE ELSE returns integer zero for
  false or NULL conditions. No epsilon or INTEGER conversion is used.

The maximum-finite literals and comparisons reject both infinities in the tested
local engine and retain its maximum finite values. Their parsing/comparison
behavior is part of any future engine qualification, not an independently
established D1 fact. SQL NaN inputs became SQL NULL in this local binding; the
wrong tag and false guard refuse rather than claim a NaN payload survived.

The closed decoder accepts at most 256 UTF-8 wire bytes, exactly those three
fields, exact tag `real`, and an integer `1` guard (not boolean, float or text).
Duplicate fields, extra/missing fields, malformed UTF-8/JSON and JSON NaN/Infinity
constants refuse. Decimal payloads must be strings of at most 64 ASCII characters
with the full grammar
`-?(0|[1-9][0-9]*)\.[0-9]+(e[+-][0-9]{2,3})?`, at most 26 significant coefficient
digits, and absolute exponent at most 324. Leading fractional zeros and the sole
fractional `.0` appended to an integer by alternate-form-2 are not precision
digits. A 26-digit integer followed by that required `.0` is therefore admitted
without allowing a 27-digit integer or 27 nonzero significant digits. Equivalent
spellings inside this explicit grammar are permitted;
the wire text itself is not the comparator. Outside spellings, huge exponents,
overflow, underflow to zero and either zero sign refuse. Bounds precede numeric
parsing and exact rational allocation.

Python `float(s)` supplies a candidate value. The independent oracle must then
certify its exact nearest/even rounding from the rational decimal `Fraction(s)`.
The decoder emits only `['real', value.hex()]` and requires hexadecimal
decode/repack byte equality. A true source guard cannot authenticate fabricated
payloads. Substituting another valid decimal produces a different canonical
value; source/transport authenticity remains with the existing trusted extractor.
The source tag does not turn the TEXT payload into a persisted TEXT cell.

## Exact oracle and conditional encoding argument

`positive_rational(bits)` decodes the IEEE binary64 exponent and significand using
integer operations and `Fraction`; it never calls a decimal-to-float parser.
For a finite nonzero magnitude `b`, let `v` be its exact rational value, `p` its
predecessor and `n` its successor. The oracle tests the exact decimal rational
against `(p+v)/2` and `(v+n)/2`, including endpoints precisely when the binary
significand's low bit is even. Negative values use sign symmetry. For minimum
subnormal the predecessor is zero; for maximum finite the mathematical successor
is `2**1024`, giving the correct finite-overflow midpoint. No floating arithmetic,
approximate comparison, `nextafter`, or second call to `float(s)` supplies these
intervals. Exact midpoint tests cover even/odd ties, both signs, zero underflow
and overflow boundaries.

Thus, for any well-formed admitted decimal, the oracle establishes that the
decoder's candidate is its unique round-to-nearest/ties-to-even nonzero finite
binary64 result. Standard integer/rational arithmetic and binary64 `struct` layout
are explicit local oracle assumptions. This validates the **decoder**, not the
unknown persisted source bits: the decoder computes the candidate's bits itself.
For local source round trips the separate expected bit fixtures and direct
SQLite-to-Python binary read provide that additional source oracle.

Let `E(x)` be the formatter and `S` the engine's fixed CAST parser. A true exact
nonzero guard gives `S(E(x)) = x`. That makes `E` injective among passing source
values for the same parser: equal strings have the same inverse. If, additionally,
`S` agrees with exact nearest/even decoding on these emitted strings, the decoder
oracle implies the canonical result is exactly `x`. Neither 26 digits nor a true
SQL equality flag establishes the additional premise. A different engine parser
could return `x` for a string whose mathematically nearest binary64 is a neighbor.
The independent decoder would faithfully return that neighbor and could not know
the hidden source bits. Source comparisons cannot resolve this circularity alone.

## Zero and nonfinite findings

On local CPython 3.14.7 / SQLite 3.53.1, both inserted zero signs in a STRICT REAL
column were read as positive zero, before and after serialized database reopen.
That is an observation about these actual persisted local reads. It does not
establish that all legal persisted D1 zeros normalize the same way. Separately,
the local expression formatter rendered a bound negative zero as `0.0`, and SQL
`=` and `IS` treated the two signs as equal. Formatter sign loss and persistence
normalization are distinct events; neither permits reconstructing an erased sign.

No zero-sign invariant or supported sign-extraction operation is established for
the managed engine. Refusing **all** REAL zeros is the smallest honest candidate
restriction. It is a capture refusal, not an accepted smaller domain. It cannot
qualify all legal bucket states. Infinity input patterns remained REAL locally
and failed the guard; signed quiet/signaling NaN input patterns became NULL.
The independent bit oracle also refuses every exponent-all-ones pattern.

## Bounded local evidence

Only synthetic in-process SQLite databases were created. Reopen used SQLite
serialize/deserialize into a second in-memory connection; no private or native
application fixture was opened. No claim of disk-crash durability follows.

- **20 unittest methods passed** on CPython 3.14.7 / SQLite 3.53.1.
- The predecessor's 24 input patterns were tested before and after serialized
  reopen: 22 signed finite nonzero boundary patterns decoded exactly; both zero
  inputs refused each time. Expected source patterns were independent integer
  fixtures, checked against direct read bytes and exact decimal rounding cells.
- Cases cover signed extremes/subnormals and adjacent patterns, decimal one tenth,
  exact integer-looking REALs, affinity/STRICT versus permissive storage tags,
  both infinities, four signed quiet/signaling NaN inputs, and six synthetic token
  arithmetic states. These token states are not actual-schema qualification.
- Hostile cases cover wrong guard types/values, wrong tag, extra/missing/duplicate
  fields, invalid JSON/UTF-8/constants, size/precision/exponent bounds, forbidden
  numeric spellings, numeric instead of string payloads, valid substitution,
  and one-bit drift rejected by the independent source-bit oracle.
- Independent review identified false refusal of SQLite's 26-digit integral
  fixed-notation result followed by `.0` (including `1e25`). The corrected
  precision count excludes that sole syntactic suffix. Twelve signed persisted
  cases cover `1e25`, a second 26-digit integer and both binary64 neighbors;
  all source guards pass and exact canonical values match. Explicit 27-digit
  integer/nonzero-precision spellings still refuse. The original boundary corpus
  did not cover this notation boundary; no finite corpus is represented as
  exhaustive formatter coverage.
- Repository Ruff check and format check passed. Standard Pyright inherited from
  the repository pyproject passed with Windows/Python 3.14 and no rule weakening.
- The existing codec and reader regression suites passed **30 tests**, including
  their unchanged REAL refusal; neither production module was edited.

Run from the API repository with the existing pinned uv 0.12.5 binary, using
`run --frozen` (no upgrades):

```console
uv run --frozen python -m unittest discover -s probes/typed-real-encoding -p test_*.py
uv run --frozen ruff check probes/typed-real-encoding
uv run --frozen ruff format --check probes/typed-real-encoding
uv run --frozen pyright --project probes/typed-real-encoding/pyrightconfig.json
uv run --frozen python -m unittest tests.test_private_d1_snapshot_codec tests.test_private_d1_snapshot_reader
```

Sandbox cache permission failures were resolved by using the writable temporary
uv cache and authorized outside-sandbox local validation. No source failure was
concealed; an initial unused import and formatting findings were fixed before the
recorded successful checks. Existing pins/lockfiles were not changed.

## Remaining qualification boundaries

1. Fresh independent High source review must check this conditional proof,
   rational oracle, refusal boundaries and bounded evidence. Review success
   records a source handoff, never hosted fidelity or permission to capture.
2. Retain whole-snapshot REAL refusal until an actual source-bit oracle or
   defensible managed-engine parser/formatter guarantee closes the inverse
   agreement gap, and an independently supported persisted-zero invariant or
   sign-preserving channel closes zero. An undocumented D1 version cannot be
   silently replaced with the local version. A behavior corpus alone is finite
   evidence and cannot prove every binary64 input or future provider change.
3. A later isolated packet must freeze reviewed artifacts, exact resource/action
   counts, trusted persisted-source oracle, engine/provider/tooling provenance,
   actual schema/token coverage, row census/identity, hostile transport, restart
   and all reader/capture bounds. It must reconcile the predecessor's proposed
   four-run/twelve-capture ceiling with the existing campaign allocation. Nothing
   here consumes, expands or authorizes that campaign.
4. No reader integration should be selected on this evidence alone. Any proposed
   change to zero equality, admitted cells, comparator, trust boundary or exact
   preservation contract requires its own owner decision. A faithful source wire
   implementation needs ordinary review, not a new decision merely for decimal
   strings. Defer the temporary composition while the exact proof is unavailable.

No credentials, private evidence/metadata, provider/account/DNS operation,
deployment, migration, native/Desktop action, cleanup or production capture was
performed. `production_ready`, `hosted_qualified` and action readiness remain
false. The all-store barrier, restoration and complete relational capture gates
are independent and unresolved by a numeric cell probe.

## Primary public sources

Reviewed 2026-10-19; local behavior above is separately identified.

- [SQLite printf precision and alternate-form-2](https://sqlite.org/printf.html):
  documented formatter and its finite precision limit; an exact decimal expansion
  can require more digits. This supports choosing a checked representation, not
  inferring universal parser agreement.
- [SQLite floating point](https://sqlite.org/floatingpoint.html): binary64 layout,
  signed zeros, subnormal/extreme range, extension alternatives and conversion
  history. Current documentation is not deployed managed-engine provenance.
- [SQLite expressions and CAST](https://sqlite.org/lang_expr.html): conversion,
  numeric comparison and NULL semantics underlying the guarded candidate.
- [Python 3.14 Fraction](https://docs.python.org/3.14/library/fractions.html): exact
  integer rational arithmetic and decimal-string rational construction.
- [Python 3.14 hexadecimal float conversions](https://docs.python.org/3.14/library/stdtypes.html#float.hex)
  and [struct binary64 byte layout](https://docs.python.org/3.14/library/struct.html):
  canonical conversion/repack assumptions. The documentation now shows 3.14.8;
  the actual pinned local interpreter remained 3.14.7.
- [D1 type mapping](https://developers.cloudflare.com/d1/worker-api/#type-conversion):
  REAL-to-Number mapping is not a universal exact JSON serialization contract or
  independent persisted-source oracle.

## Independent review and integration

Fresh independent High review cleared the formatter precision-count finding
after correction. Twenty unit tests and static checks pass; the review's finite
corpus of 34,010 patterns decoded exactly, with 136,040 midpoint checks and
additional hostile-boundary/parser-drift checks passing. These are finite local
checks, not a universal or managed D1 proof. The parent reproduced all twenty
installed unit tests. Persisted zero-sign and managed parser agreement remain
unqualified; current reader/codec refusal and full-state NO-GO are unchanged.
