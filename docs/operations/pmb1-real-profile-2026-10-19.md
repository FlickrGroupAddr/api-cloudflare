# PMB-1 complete REAL source profile: exact boundary and NO-GO

Date: 2026-10-19. Status: **bounded source investigation complete; full persisted
REAL extraction NO-GO; independent High source review passed**. This is an unregistered
synthetic prototype and source handoff. It does not satisfy the REAL proof
prerequisite for complete-reader integration or qualify PMB-1.

## Outcome and controlling contract

The conventional Worker approach is sound **after** a faithful Number arrives:
encode that Number's binary64 bits explicitly before application JSON, then
convert those bytes to the existing canonical Python `float.hex()` form. The
prototype proves that conditional codec for every finite Number, including both
zero signs, without a decimal formatter/parser premise. The remaining gap is
whether the supported D1 persisted-cell-to-Worker binding path delivers exactly
that Number for every contract-admitted persisted REAL. Public type mapping does
not establish that full premise or bind it to the managed deployment.

The accepted [PMB-1 complete equality and REAL gates](prospective-maintenance-contract-decision-2026-10-18.md#complete-baseline-and-lifecycle)
control: actual storage class and finite binary64 value, including zero sign,
must survive. Read scope includes unexpected REAL cells in any declared column
type. A codec proof cannot change equality or ignore unsupported cells. Repository
and canonical [architecture authority](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
apply. ADR0058's permitted undisclosed SQLite version remains a metadata
exception; it does not establish conversion semantics. Ordinary faithful encoding
needs no new owner policy decision. No accepted domain, trust boundary, schema,
current reader or Completed decimal proof was changed.

## Conventional profiles evaluated

| Profile | Established source claim | Exact unsupported premise | Verdict |
| --- | --- | --- | --- |
| Existing guarded `printf('%!.26g', x)` decimal | Reviewed local nonzero codec and independent exact rounding oracle | Managed CAST inverse agrees with exact nearest/even on all emitted decimals; persisted zero sign reaches payload | Full profile NO-GO |
| Supported D1 Worker REAL-to-Number followed immediately by DataView | Ordinary Number-to-binary64 and bits-to-canonical semantics cover every finite received value and both zeros | Persisted managed REAL reaches Worker Number with all finite bits/sign intact, before any inaccessible conversion | Conditional codec PASS; persisted-source profile NO-GO |

For decimal, let `E` be the formatter and `S` the engine CAST parser. The source
guard establishes `S(E(x)) = x` only for nonzero passing cells. The independent
rational oracle establishes what exact nearest/even decoding of `E(x)` means.
Agreement between those two inverses remains necessary: a hypothetical engine
parser returning `x` for a string whose exact nearest neighbor is `y` can make the
guard true while the independently correct decoder returns `y`. This is a
logical countermodel to the inference, not an observed managed-engine defect.
The zero guard refuses, and SQL numeric equality alone cannot distinguish zero
signs. SQLite's [printf precision semantics](https://sqlite.org/printf.html) and
[CAST semantics](https://sqlite.org/lang_expr.html#castexpr) do not establish the
missing managed inverse/sign premise. Re-running the unchanged decimal tests,
including midpoint/ties, one-bit drift and fixed-notation 26-digit `.0`, retains
the existing bounded result; no larger decimal corpus is offered as a proof.

Cloudflare documents [REAL reads as Number](https://developers.cloudflare.com/d1/worker-api/#type-conversion).
The [raw method](https://developers.cloudflare.com/d1/worker-api/prepared-statements/#raw)
returns arrays rather than objects; its name does not describe a raw byte
channel. These contracts do not expressly cover all persisted bits, zero sign,
reopen behavior or internal serialization. This is an identified missing
premise, not a finding that D1 corrupts values or cannot provide a conventional
solution.

Supporting public [workerd wrapper source](https://raw.githubusercontent.com/cloudflare/workerd/main/src/cloudflare/internal/d1-api.ts)
shows a legacy branch decoding response JSON before returning cells and a
separate conditional JS-RPC branch. Its upstream cell reader/serializer and the
actual managed branch are not established here. Literal JSON `-0` can preserve
its sign; ordinary ECMAScript numeric JSON serialization erases that sign.
Therefore neither the presence of JSON nor the existence of RPC by itself
proves actual D1 fidelity or actual loss. Encoding before **application** JSON
is not evidence of encoding before every provider conversion.

That public wrapper URL is mutable. Independent retrievals gave inconsistent
cached revisions and no verified commit pin was obtained. It is supporting
boundary evidence only, never exact managed provenance. The NO-GO rests on the
unclosed supported contract premise, not that unpinned implementation. No
assumption selects or disables JS-RPC. No provider request occurred.

## Bounded prototype and complete conditional proof

`probes/pmb1-real-profile/` adds no Worker entry point, configuration, route,
binding execution, reader import, migration or deployment. `CELL_SQL` is only a
fixed synthetic specimen selecting `id, typeof(x), x` from one row evaluation.
Its caller must retain those original tuple fields from that evaluation; the
pure encoder cannot attest their origin. This is a cell prototype, not a page
query generator or a complete snapshot reader.

`encodeBindingRow` requires an exact three-field tuple: bounded ASCII synthetic
row identity, actual tag `real`, and a primitive finite Number. It uses an
eight-byte DataView, explicit big endian `setFloat64`, and `getBigUint64` to
produce exactly sixteen lowercase hex digits. Only after that does it serialize
four string fields: `profile`, `row_id`, `type`, `binary64`. The wire is bounded
to 256 UTF-8 bytes. No rounding, arithmetic bit extraction, SQL extension,
guard flag, binding cast or type coercion is used.

The complete conditional argument is mathematical, rather than enumeration:

1. For any finite binary64 Number `n`, ECMAScript's ordinary
   [NumericToRawBytes](https://tc39.es/ecma262/2026/multipage/structured-data.html#sec-numerictorawbytes)
   semantics encode its unique float64 representation, including its zero sign.
   Explicit byte order removes machine-endian ambiguity. Reading the same eight
   bytes as an unsigned integer and formatting that integer as sixteen hex digits
   is a bijection on those bytes.
2. JSON transports those ASCII digits as a string, so it performs no numeric
   conversion on the payload. The Python decoder checks a closed schema, exact
   expected row identity, exact REAL tag, duplicate keys, UTF-8/JSON validity,
   wire bound and the sixteen-digit grammar before decoding bytes. Exponent
   all ones refuses before unpacking; no nonfinite canonical cell is admitted.
3. Python's standard [`struct` format `>d`](https://docs.python.org/3.14/library/struct.html)
   decodes those bytes as IEEE binary64 with explicit big endian order. Its
   [`float.hex()`/`fromhex()`](https://docs.python.org/3.14/library/stdtypes.html#float.hex)
   conversion supplies the existing canonical representation; repacking must
   recover the exact eight input bytes, including `8000000000000000` for `-0`.
4. Consequently, if the delivered Number has the persisted source pattern `b`,
   the canonical output has pattern `b` for every finite pattern. If an earlier
   conversion changes `b` to `c`, the exact codec faithfully returns `c`. It
   cannot recover an unobserved source sign or rounded neighbor.

No decimal parser agreement is required by this alternate codec. That eliminates
the decimal path's inverse premise but leaves the earlier source-to-Number
premise. A profile name, source hash or successful decoder must never select
REAL support in the current reader. There is deliberately no evidence boolean
or candidate execution seam that grants such selection.

## Independent local persisted-source evidence

The fixture first reads actual persisted cells directly through local
SQLite-to-CPython, separately checking integer bit fixtures. Those bits cross
the test process boundary as **strings**, preserving negative zero before the
Node encoder runs. The original source row identity is retained in the encoded
cell. A second in-memory database is reopened through serialize/deserialize.
This is local synthetic evidence, not managed behavior or crash durability.

A material distinction is now executable: ordinary untyped and BLOB-affinity
columns retain both `-0` and `+0` as REAL, with their distinct direct-read bits,
before and after reopen. A STRICT REAL-affinity column normalizes both inserted
zero signs to positive-zero readback on this same local engine. The target is
that actual readback, not the insertion sign or physical storage bytes.
[SQLite affinity rules](https://sqlite.org/datatype3.html#type_affinity) explain
why declared type alone cannot supply the full actual storage-class census.
No managed zero-normalization invariant is inferred from either observation.

Checks include signed extremes and adjacent values, all finite exponent fields,
subnormal/normal boundaries, `1e25`, both zero signs, INTEGER/REAL/TEXT/BLOB/NULL
tags, infinity refusal, NaN-to-NULL local normalization and reopen. Hostile
bounds, syntax, extra/missing/duplicate fields, wrong identities/tags and
nonfinite bit patterns refuse. Prebinding sign loss and one-bit-neighbor
substitution deliberately **pass** the faithful downstream codec but fail the
independent expected-source-bit comparison. This demonstrates precisely why the
codec cannot certify source fidelity by examining its own decoded bits.

## Provenance, invalidation and verification

`source-pins.json` records exact SHA-256 file identities for the new prototype,
its tests/configuration, unchanged decimal encoder, canonical comparator,
current refusing reader/codec and dependency lockfiles. A dedicated test checks
them. These are local source pins, not an authenticated deployment manifest.
The managed engine identity and binding/transport identity are explicitly null;
no provider generation, runtime branch, account/resource, schema, persisted
provider cell or private state was inspected. No local engine identity may fill
those managed fields.

Actual tools: uv **0.12.5**, frozen CPython **3.14.7**, local SQLite **3.53.1**,
portable Node **24.22.0**, native TypeScript **7.0.2**, Ruff **0.16.3** and Pyright
**1.1.411**. Public Python documentation currently displays 3.14.8; the local
interpreter was not upgraded. Initial PATH tools were unsuitable (uv0.13.1 and
Node24.20.0); final checks used the existing pinned binaries and test fixtures
now refuse an incorrect Node version. No tooling/lock/configuration pin changed.

Final validation used `uv run --frozen --no-sync` with the pinned executable and
portable Node directory prepended to PATH:

- New Python suite: **9 tests**, including cross-language/persisted-source and
  source-pin checks; new Node suite: **4 tests**.
- Node checks cover 12,282 selected finite patterns; cross-language checks cover
  every finite exponent field and the explicit boundary fixtures. Neither count
  substitutes for the semantic argument or proves a provider premise.
- Unchanged decimal suite: **20 tests**, including exact midpoints/ties;
  unchanged current reader/codec suites: **30 tests**, retaining every-REAL refusal.
- Scoped Ruff lint/format, standard Pyright inherited from repository settings,
  and pinned native TypeScript with inherited strict compiler settings pass.

Any source/SQL/wire/canonical/tool/adapter change invalidates the applicable
review/pins. Before managed selection, exact deployed artifact/configuration,
provider generation, disclosed engine version or ADR0058-compliant fresh version
refusal, binding/transport branch/identity and semantic guarantee must be bound
together. A provider rollout or unknown conversion change requires reassessment;
a historical public wrapper or local SQLite version cannot stand in for it.

## Concrete missing-capability and provenance follow-up

The next source task is narrowly defined: obtain an authoritative supported
persisted-cell extraction guarantee or a supported independent persisted-value
channel. Its output must establish one of:

- The managed D1 read returns precisely the persisted source binary64 Number for
  every admitted finite pattern, including both zeros and reopen, before the
  prototype encoder; bind the guarantee to engine/service/binding/transport
  provenance. Then review this ordinary codec for integration.
- A supported independent per-cell persisted-bit channel supplies the same
  original type, bits and row identity under the barrier, without reusing the
  questioned formatter/parser; review its exact source and provenance argument.
- For the decimal branch, a supported universal managed inverse-agreement
  guarantee plus an independent zero-sign channel/invariant with equivalent
  provenance. A finite corpus or SQL self-equality cannot provide those premises.

A bounded disposable managed observation may falsify a proposed guarantee,
exercise restart/reopen and bind observations to its exact service. It cannot
alone establish a universal promise. Do not create a full-reader qualification
cycle, treat an unexecuted probe as provider evidence, request a policy relaxation
or invent a new owner decision for ordinary faithful source work. If an actual
observation is needed, its separately reviewed finite packet must define the
supported primitive/guarantee or independent source oracle, resource/action
counts, authority/custody, stop/cleanup and existing campaign allocation first.
Expired authority is not reused and no action is authorized here.

The conventional source proof remains specifically unresolved, not demonstrated
impossible. Current complete-reader REAL refusal, actual PMB-1 qualification and
production readiness remain unchanged. No private/provider/account/DNS/native,
registration, migration, deployment, capture or cleanup action occurred.

## Independent review and integration

Independent High review passed the bounded investigation with no material finding.
The conditional codec is sound; the managed persisted-source premise remains
NO-GO. Nine Python tests, four Node tests, fifty unchanged regressions and scoped
static gates pass. Independent integer-derived checks covered 40,457 finite
patterns plus nonfinite, hostile and pin faults. The parent reproduced both new
suites and scoped native TypeScript. Finite checks do not prove the upstream
premise. Follow-up #0207 prepares authoritative evidence or an unsent capability
request; it cannot satisfy #0192/#0195 by merely preparing that request.
