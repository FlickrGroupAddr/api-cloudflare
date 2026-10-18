# REAL extraction for exact full-state snapshots

Date: 2026-10-18. Ticket #0180. Status: **source-only feasibility and proposed
qualification**, not an accepted encoding amendment or production qualification.
The current reader's whole-capture REAL refusal remains correct. No reader,
codec, comparator, schema, guard or provider operation changes in this work.

## Result and recommended next step

**Current full-state capture remains NO-GO when any actual cell is REAL.** The
lowest-complexity candidate to investigate first is SQLite's documented
`printf('%!.26g', x)` with a same-engine exact round-trip check and an explicitly
typed wire value. Its availability and useful precision make it a credible
candidate; missing a preferred binary function alone is not a reason to reject
it. However, the reviewed documentation does not close signed zero,
nonfinite refusal, managed-engine variation and SQLite-to-Python decoding for
the existing canonical binary64 comparator. No experiment here establishes those
missing properties. Preserve refusal until a separately reviewed source design
and bounded isolated qualification close them.

This is a bounded evidence conclusion about the current reader and documented
surfaces, not proof that D1 cannot support exact REAL extraction. Prefer a
conventional supported representation over a new helper service. If the simple
candidate cannot be qualified, retain the original deployment and defer the
temporary composition requiring this proof. Do not build a proxy, SQL arithmetic
bit decoder, custom extension service or AWS dependency merely to bypass the
unqualified seam.

## Authority and concrete incompatibility

The API repository guidance, canonical architecture working agreement and
[authority hierarchy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
control. Accepted [ADR0050](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0050-select-cloudflare-and-evaluate-native-storage-first.md),
[ADR0051](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0051-trust-private-storage-runtime-with-guarded-writes.md),
[ADR0052](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0052-evaluate-paused-native-credential-replacement.md)
and [ADR0058](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0058-record-managed-d1-engine-provenance.md)
retain native-first evaluation, private runtime trust, conventional alternatives
and truthful managed-engine provenance. None waives exact preservation.

The existing [full-data proof](fixed-origin-preservation-2026-10-17.md#paused-gates-and-consistent-full-data)
requires every typed cell, schema object, ordered column, duplicate row and row
identity. Its canonical finite REAL is Python `float.hex()`, with exact canonical
round-trip validation; positive and negative zero remain distinct encodings.
Nonfinite values refuse. The [reader preparation](private-full-snapshot-reader-2026-10-18.md)
is the existing source seam, not a production pass. Completed #0170 and #0171
remain unchanged. The prospective #0179 maintenance proposal is contextual
planning and cannot supply a new numeric contract or extraction guarantee.

Concrete public-source anchors, relative to the API repository:

- `migrations/0007_browser_auth.sql:47` declares `auth_source_buckets.tokens REAL`;
  `src/auth_admission.ts:22-24` performs fractional refill/debit arithmetic.
- `migrations/0011_submission_status.sql:15` declares
  `status_read_buckets.tokens REAL`; `src/submission_status.ts:39-44` refills and
  debits it. Values constrained to small ranges can still be fractional binary64.
- `scripts/private_d1_snapshot_codec.py:254-295` emits a storage-class tag but
  deliberately supplies no REAL payload and refuses `lossless_real_transport_unqualified`.
- `scripts/fixed_origin_preservation.py:78-96` owns finite canonical REAL cells.

These declarations establish a source incompatibility, not observed deployed
rows or the actual production schema. Empty buckets, integer-looking tokens,
hand-picked tables or a newer migration inventory cannot stand in for a complete
actual census.

## What must survive

The target is the binary64 value observed when reading the persisted cell with
its actual SQLite storage semantics, together with its `typeof` tag. It is not
the original input decimal, a pre-insert JavaScript value, a previous arithmetic
intermediate or physical B-tree bytes. SQLite REAL affinity can store an
integer-valued REAL using an integer record and expose it as REAL on read; that
documented optimization is not reader-induced type drift. Schema declaration
alone does not establish the actual cell tag. A direct column read and `typeof`
must remain paired. [SQLite affinity](https://sqlite.org/datatype3.html#type_affinity),
[record format](https://www.sqlite.org/fileformat.html#record_format).

Persistence may already transform an input, including a zero sign; formatting
cannot recover discarded information. Conversely, a locally observed zero
normalization does not prove all actual D1 persisted REAL zeros have the same
sign. The reader must preserve any sign exposed by the persisted read or refuse;
it must not silently map both signs to positive zero. Subnormals must not flush
to zero, adjacent finite values must not merge, and maximum finite values must
not overflow. SQLite documents binary64's signed zeros, subnormal-scale minimum
and maximum finite range. [SQLite floating point](https://sqlite.org/floatingpoint.html).

`CAST(x AS INTEGER)` loses fractional information. `CAST(x AS TEXT)` is numeric
formatting, and `CAST(x AS BLOB)` first converts the number to text: neither is
a reinterpretation of the double's bytes. `hex(x)` therefore is not a raw REAL
bit extractor. A typed string carrying a proven reversible encoding is a
possible wire representation; relabeling the database cell TEXT is not.
[SQLite CAST rules](https://www.sqlite.org/lang_expr.html#cast_expressions).

## Compare the conventional channels

| Channel | Useful documented property | Missing evidence / disposition |
| --- | --- | --- |
| D1 query numeric result | Worker binding maps REAL to JavaScript Number. REST returns JSON results. | A type mapping alone is not an exact serialization contract for every persisted double. Keep current refusal. [D1 types](https://developers.cloudflare.com/d1/worker-api/#type-conversion). |
| D1 `/raw` | Rows are arrays rather than objects. | The word raw does not mean binary database cells; its response remains JSON numbers/strings. No bypass. [REST raw reference](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/raw/). |
| SQLite `printf('%!.26g', x)` | Documented built-in alternate-form-2 precision; SQL TEXT survives a JSON string boundary without JSON numeric parsing. | First candidate below. Must establish exact source round trip, zero treatment, finite refusal and decoder compatibility. No unconditional bit claim. |
| SQLite `ieee754_to_blob(x)` then hex | SQLite's existing extension explicitly yields eight big-endian binary64 bytes. | A conventional precise seam if supported, but D1 support is not established. Its docs-linked pinned workerd function allowlist has no `ieee754` entry. Do not assume or install it. [SQLite extension](https://sqlite.org/floatingpoint.html#the_ieee754_c_extension), [D1 supported functions](https://developers.cloudflare.com/d1/sql-api/sql-statements/#supported-sqlite-extensions), [linked source](https://github.com/cloudflare/workerd/blob/4c42a4a9d3390c88e9bd977091c9d3395a6cd665/src/workerd/util/sqlite.c%2B%2B#L249). |
| D1 SQL export / existing archive | Conventional recovery tools already exist. | SQL export is not a raw SQLite file or a documented binary64 preservation proof; documented numeric precision and virtual-table limits matter. Existing `current_schema_archive.py:119-145` also filters provider state and constructs literals, so it cannot replace this complete exact reader. [D1 import/export](https://developers.cloudflare.com/d1/best-practices/import-export-data/). |

The workerd source link is public implementation evidence at one revision, not
proof of the deployed D1 build or every available provider function. Absence
there is a reason not to invent support, not an authenticated capability test.
Loading an extension, inspecting a native database file or deploying a helper is
outside this planning scope.

## First candidate: typed decimal with checked reversibility

SQLite documents that `!` raises floating-point formatting precision to 26
significant digits. It also explicitly distinguishes that limit from an exact
decimal expansion, which can require more digits. Thus “26 digits” does not
mean “the exact decimal value,” and a stable-looking string is not by itself a
round-trip proof. This candidate uses the documented built-in formatter rather
than assuming C `%a`, an invented D1 hex-float function or an extension.
[SQLite printf precision and flags](https://sqlite.org/printf.html).

There is concrete version-sensitive evidence, rather than a merely hypothetical
zero concern: SQLite 3.45.1's `sqlite3FpDecode` normalizes either zero sign to
positive before rendering. A numeric CAST equality check can still pass. This
does not establish a current persisted D1 negative zero. Separately, SQLite's
current floating-point guide describes a conversion rewrite in 3.52.0; importing
its newer behavior into an undisclosed managed D1 engine would be unjustified.
[SQLite 3.45.1 decoder](https://github.com/sqlite/sqlite/blob/version-3.45.1/src/util.c#L942),
[SQLite conversion history](https://sqlite.org/floatingpoint.html#rounding_floating_point_numbers_for_display).

A later design should specify, in one fixed read statement per page:

1. Read the unmodified column's actual type and value. For a REAL cell produce
   `s = printf('%!.26g', x)` as SQL TEXT, retaining the REAL tag; do not change
   the schema or substitute the formatted value for the cell before tagging.
2. Check in that same engine evaluation that converting `s` back to REAL equals
   `x` exactly, with no epsilon, rounding, truncation or integer conversion.
   Keep the check with the row identity and payload. Any absent, NULL, malformed
   or false check refuses the entire capture. Independently reject nonfinite
   source and decoded values using reviewed engine-supported predicates; the
   exact predicates and their limit handling remain a source-design obligation.
3. Treat zero separately: SQL numeric equality and `IS` do not distinguish both
   signs. A true ordinary round-trip equality check therefore cannot prove zero
   sign preservation. Until a documented sign-preserving path or accepted,
   proved persisted-zero invariant exists, **every REAL zero must refuse**, even
   positive zero. This restriction is safe but cannot qualify all legal token
   states, since an exhausted bucket can be zero.
4. Carry `s` as a bounded JSON string, never a JSON number, alongside the original
   REAL tag and fixed check fields. The later closed schema must reject extra
   fields and specify a single grammar and at most 64 ASCII bytes per REAL
   spelling. No direct `float()` call may silently accept alternate spellings,
   trailing text, overflow or underflow.
5. Produce the existing finite canonical `.hex()` cell only after independently
   establishing that the selected decoder recovers the source double exactly.
   Retain its bytes-to-value-to-canonical-to-bytes checks in the test oracle.
   Do not infer this from a second call to the same decoder.

For finite nonzero binary64 values, exact numeric equality identifies one bit
pattern. With a single fixed deterministic parser `P`, a checked encoding
`P(E(x)) = x` is injective: equal encoded strings imply equal source values.
This explains why the formatter deserves evaluation. It does **not** establish
that SQLite's decimal parser equals Python's, that a managed D1 engine cannot
change parser behavior between captures, or that signed-zero equality is safe.
The source check also must be part of the approved complete statement under the
writer barrier; a detached later check is not a check of the captured cell.

Python's JSON decoder normally converts JSON fractional numbers with
`float(num_str)` and supports nonstandard nonfinite tokens unless configured to
refuse them. Preserving a numeric lexeme with Decimal does not repair precision
already lost upstream. Python documents hexadecimal float strings as exact
representations; it does not make a D1 decimal formatter and parser the same
implementation. [Python JSON](https://docs.python.org/3/library/json.html),
[Python hexadecimal floats](https://docs.python.org/3/library/stdtypes.html#float.hex).

Comparing checked decimal strings directly is a possible **different proposed
encoding**, not a silent decoder workaround. It needs explicit comparator and
contract versioning plus an injectivity argument across the supported engine
behaviors; format changes can cause safe mismatches, and parser changes can
invalidate an assumed shared inverse. The current comparator cannot consume it.
No such amendment is accepted here. A local Python/SQLite agreement and a finite
hosted corpus are evidence for a pinned qualification profile, not a theorem
covering undocumented provider implementations or future updates.

## Binary seam if provider support becomes available

An officially supported in-engine bit operation would make the wire simpler:
actual `typeof(x)='real'`, exactly eight big-endian bytes, hex-encoded as exactly
16 uppercase ASCII digits inside a JSON string. This would use the real
`ieee754_to_blob` operation only after documented provider support and isolated
qualification; there is no current query plan for it. The decoder would validate
length/grammar, decode bytes, reject exponent-all-ones encodings (infinities and
all NaNs), unpack binary64, require finite canonical `.hex()` conversion, then
repack and demand byte equality. Signed zero and subnormals must survive.
[Python struct binary64 and byte order](https://docs.python.org/3/library/struct.html#format-characters).

This retains the existing REAL comparator representation and exact equality.
It still cannot restore a sign lost before the persisted read, prove consistency,
enumerate inaccessible tables or make provider results trustworthy by itself.
An application helper that first receives an already-rounded JSON number and
then packs it merely preserves the helper's number; it proves nothing about the
source. Even the documented Number binding would require explicit D1-to-Number
fidelity evidence before a helper could claim to preserve source bits.

ECMAScript `JSON.stringify` renders nonfinite numbers as `null` and finite
numbers through Number string conversion; zero formatting can erase the
negative-zero distinction. Such serialization is a real lossy boundary for a
general bit-preserving protocol, not a universal claim that every finite JSON
round trip loses precision. A string encoded before that boundary avoids that
specific problem. [ECMAScript JSON serialization](https://tc39.es/ecma262/multipage/structured-data.html#sec-serializejsonproperty),
[Number string conversion](https://tc39.es/ecma262/multipage/ecmascript-data-types-and-values.html#sec-numeric-types-number-tostring).

## Finite qualification proposal, with no execution authority

First prepare local synthetic source tests and an independent mathematical
oracle, not an account experiment. Freeze the representation, refusal grammar,
query generator, parser versions, exact artifacts and ledger before any later
isolated action decision. The decimal path is evaluated first; stop rather than
add a second channel or helper after a failure.

The source suite should cover the following fixed corpus. Include both signs
of each nonzero pattern: minimum subnormal, next subnormal, largest subnormal,
minimum normal, next normal, the predecessor of one, one, the successor of one,
the nearest binary64 to one tenth, maximum finite, and the finite value adjacent
to maximum toward zero. Add both signed zeros: **24 input bit patterns**. Check
expected source/read semantics separately after persistence and after reopen;
do not expect insertion syntax alone to prove which bits were persisted.
Include realistic fractional refill values and legal zero/exact-capacity token
states in the actual current-schema fixture as a separate application coverage
case, not a replacement for the numeric boundary corpus.

| Bounded case | Required result |
| --- | --- |
| Each finite pattern, neighboring values and byte-order discriminator | Independent expected persisted type/value; exact extraction, wire retention, decoding and canonical round trip, or explicit refusal. Decimal zero refusal is expected until resolved; it prevents a general pass. |
| INTEGER `1`, REAL `1.0`, TEXT `'1.0'`, BLOB bytes, NULL in permissive synthetic columns; REAL-affinity and STRICT REAL cases | Correct actual tags after persistence; no type inferred from decimal appearance or declaration. Existing integer/text/blob/null paths remain exact. |
| Both infinities; positive/negative quiet and signaling NaN bit inputs in decoder fixtures | Whole-capture refusal. SQL/provider insertion may reject or normalize inputs; record that separate outcome rather than claiming inaccessible NaN payloads were preserved. |
| False/NULL/missing round-trip flag, same-count substitution, one-bit value drift, signed-zero drift, type drift | Refusal or exact inequality; no approximate pass. A source flag cannot authenticate a fabricated response. |
| Wrong-length/nonhex bit payload, alternate decimal spelling, trailing junk, huge exponent, invalid UTF-8, number instead of string, duplicate/extra/missing field | Bound before parsing/allocation; refuse. Never accept a common malformed value merely because all three captures contain it. |
| Hidden-rowid change, WITHOUT ROWID key change, duplicate-row loss, schema/column change, provider/bookkeeping omission | Whole-capture refusal or exact inequality through the existing full-state contract. Numeric success cannot mask identity/census failure. |
| Truncation, terminal-page omission, one-byte/query/time excess, interrupted sink or unknown dispatch | Abort with retained private partial state and no successful partial snapshot, blind retry or automatic cleanup claim. |

A later standalone isolated packet may propose at most **four runs with three
captures each (12 captures)**: numeric/persistence corpus; actual-schema token
integration; hostile transport/decoder inputs; restart and boundary refusal.
This is a proposed ceiling, not reserved slots, an extension of #0172/#0179's
existing 24-run/72-capture allocation, or an executable campaign. Reconcile the
shared campaign allocation explicitly before acceptance; alternatively use a
separately accepted packet with its relationship to that ceiling recorded.

Keep every existing reader bound as an upper limit: 128 tables, 2,048 schema
objects, 256 columns/table, 10,000 total rows, 4MiB canonical snapshot, 256
rows/page; 2,048 planned queries, 32KiB/query, 256KiB response wire bytes,
16MiB aggregate wire bytes, 60 seconds/request and twenty-minute window.
Freeze stricter concrete create/seed/query/capture/cleanup counts and exact
resource identities in the later packet. The existing small two-table isolated
recipe cannot silently become a full current-schema qualification. Unknown
provider bookkeeping, an oversized fixture or a missing independent persisted
oracle stops the design; no extra polls, samples, omission or budget expansion.

Expected source patterns and independent persisted readback must have a credible
oracle that does not traverse the same unqualified decimal/JSON path. If that
oracle cannot be obtained without an unsupported function, changing schema,
privileged inspection or a new service, record that limit and retain NO-GO.
Finite tests cannot prove every binary64 value; combine them with the reviewed
encoding argument and a specifically accepted managed-service trust profile.
No local emulator result may be reported as hosted D1 evidence.

## Decisions and follow-up ownership

The full private-data direction is already selected: complete database cells,
including authentication/session data, under exact preservation. Do not ask for
that decision again. It does not authorize actual access, a different equality
rule or a new extractor trust boundary.

1. **Source feasibility follow-up (P3):** specify the minimal formatter candidate's
   finite checks, signed-zero policy, exact decoder/oracle and managed-engine
   assumptions; independently review the proof. No account work is necessary
   for that source deliverable. If no satisfactory proof is available, retain
   this bounded NO-GO rather than implement an unqualified parser.
2. **Owner contract/trust decision, only for an amendment:** obtain scoped
   acceptance when a concrete proposal changes the accepted value domain,
   comparator, extractor trust boundary or safety contract. A zero-sign
   equivalence, excluded REAL cell, tolerance, finite-only sampling or changed
   row identity is such an amendment. No such relaxation is recommended.
   A faithful typed wire encoding that preserves the existing canonical REAL
   cells, exact equality and accepted trust boundaries is ordinary reviewed
   source work under the existing full-data authority; it needs no renewed
   owner decision merely because the wire carries decimal text.
3. **Source implementation and independent review:** once the encoding proof
   is satisfactory, and after any applicable amendment is accepted, extend the
   existing reader seam and tests without reopening or rewriting Completed
   #0170/#0171. Preserve current refusal on every
   unsupported value, schema, identity or exhausted bound. No SQLite maintenance
   guard belongs to this numeric scope.
4. **Exact isolated packet and owner action decision:** allocate finite cases,
   actual-schema coverage, trusted oracle, effective grants, private custody,
   resource ownership and cleanup/retention before execution. A source review
   does not grant account access or change existing resource budgets.
5. **Production action decision:** remains separate after hosted qualification,
   a qualified continuous all-store writer barrier and all restoration gates.
   REAL support alone cannot resolve #0163 or qualify the production reader.

If exact full-state proof remains unavailable, the conventional operational
choice is to defer the temporary composition or prepare an independently scoped
isolated fixture that makes no preservation claim about production. The accepted
[D1 backup baseline](d1-backup-and-recovery.md) remains in force; Time Travel
is recovery coverage, not an exact full-state comparison receipt. A future
fixed-point rate-limiter schema could eliminate new REAL token state, but needs
its own rate/overflow/migration design and cannot recover or relabel existing
arbitrary REALs. A database change is considered only after showing the concrete
remaining requirement and comparing the full ADR0050/0052 burden; it is not the
default response to this extraction gap.

## Evidence boundary

Primary public documentation was reviewed on 2026-10-18, with static reads of
the public API/canonical authority and source anchors above. Parent supplied API
baseline `589ccc3`; the author ran no Git command and does not independently
attest checkout identity. Documentation links describe the reviewed public
surface, not observed account state. No local numeric experiment, runtime test,
provider/account query, private database/capture read, credential access, DNS/native action,
schema mutation or production capture occurred. All production readiness and
hosted qualification claims remain false; fresh independent High design review
is required before handoff.
## Independent planning handoff

Fresh independent High review passed the Proposed feasibility record after a
narrow clarification: faithful typed wire work under existing canonical equality
is ordinary reviewed source work; only an actual domain, comparator, trust or
safety amendment needs owner acceptance. No unresolved finding remains. Primary
source and local-reference checks are static evidence, not a numeric experiment
or hosted qualification.

Follow-up #0184 owns the bounded encoding/decoder/oracle source proof. #0182's
actual all-store qualification gate depends on it; #0163 remains unqualified.
The current reader still refuses REAL and no Completed ticket is reopened.
