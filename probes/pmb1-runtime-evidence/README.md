# Private runtime evidence ledger source

MIT License; copyright 2026 Terry Ott.

Implements the accepted #0251 source contract in
`docs/operations/pmb1-private-runtime-evidence-contract-2026-10-23.md`.
This is prospective source support. No actual evidence, qualified holder census,
management credential, schema installation, resource, run, capture or replay is
provided. Missing actual qualified runtime attribution remains NO-GO.

## Authority and call graph

`ledger.ts` is the Worker-side fixed reader and durable reservation/consumption/
completion implementation. It has no publication, approval, schema, reset,
arbitrary-SQL, provider-management or credential method. Every database request
starts a new `first-primary` session. The actual existing external main-journal
control must match the complete source-context/database/lifecycle/generation and
be stopped. This control observation is inside the preflight query, not an extra
bootstrap read. Evidence events never update main-journal revision or accounting.

`publisher.ts` belongs exclusively to the private operator call graph. It exports
the pure fixed plans from `publication-plan.ts` and concrete native D1 SDK executor
from `operator.ts`; none enters the FGA API backend Worker graph. The preparer
verifies exact retained envelope/payload/Root/reviewer artifact bindings and emits
the one fixed atomic publication batch. Its readback and retirement plans are
fixed and separately allocated.

The concrete executor defaults to inert NO-GO when no genuine independently
qualified operator source handoff/unused finite external allocation is supplied.
No such actual data/environment is provided by this source revision. A qualified
operator environment must already hold the exact selected native D1 binding;
this library selects/deploys no operator service, environment, topology, resource,
credential or public route. The executor uses only the supported native
`D1Database.withSession(...).batch(...)` path; it assumes no REST atomicity or
management token in the backend Worker. Actual entry/environment/custody and
complete binding holders still must qualify before invocation. A row, reviewer
name, digest or successful provider acknowledgement cannot supply that work.

Execution reconstructs every fixed SQL statement from the exact retained reviewed
header/payload; it never executes caller-supplied prepared SQL. The exact actual
Root and fresh non-author review, source/environment/holder/credential-custody
qualification and unused external operation-ledger allocation must precede that
call. These are protected operator SOURCE inputs, not a JSON/HTTP/environment
truth loader or review callback. Hash comparisons identify those records and
artifacts but do not authenticate semantic work by themselves.

Publication is separately allocated: one batch of at most 18 statements, followed
by independent fresh-primary bounded aggregate preflight, exact header/chunks/
events read, and final event reread. That is at most four requests/23 statements,
with explicit acquired/aggregate byte limits before database materialization.
The runtime eight-request/32-statement consumption cap is unchanged. Publication
is one-shot for its exact source authority/envelope; every unknown/lost/malformed
mutation acknowledgement remains UNKNOWN even if diagnostic exact readback
observes committed rows. There is no mutation retry, automatic authority renewal
or cold-restart inference that a spent external allocation is unused. Durable
external operator-attempt custody and SQL immutable envelope uniqueness both
remain required.

The D1 capability is broad. Under accepted ADR0051, deployed private native code
is trusted not to dismantle these guards or issue unauthorized SQL. This is
procedural/operator plus reviewed-code containment, **not database role isolation**.
The source grants no protection against a compromised binding holder/operator,
guard removal or restored-away history. External operator attempt history and
qualified durability/custody remain independent requirements.

## Exact identities and freshness

The production `fromNativeExecution` path takes independently qualified native
`VERSION_METADATA.id` and compiled source-context as observed selectors. Separately
trusted source anchors identify the existing external journal UUID/schema and the
qualified publisher/provenance/holder-containment/native-getter paths. None of
those anchors includes an own final module digest, future version ID, publication
ID or finite evidence interval. The protected row cannot qualify its own native
getter or publisher path.

After exact native version/context selection, the prequalified operator path
supplies the independently Root/reviewer-authenticated EXPECTED mapping of that
immutable version to final retained module, configuration, full resource inventory
and native source/owner/control pins. All full mapping fields remain mandatory;
their values are not compiled into their own retained bytes. Real provider
management evidence and semantic authentication must establish that mapping.
The native observed version is never copied from a row and hashes establish
identification only. This split avoids a digest/version cycle without a new
channel, signer or resource. The explicit-full-anchor constructor is also retained
for separately retained independent expectations and synthetic seam tests.

Current main-journal lifecycle/generation are matched by the fixed query against
the independently qualified existing journal control. That old immutable control
is never reset, migrated or reopened. Same-resource later-interval tests preserve
its generation; a substituted journal generation refuses.

The envelope supplies its newly authenticated Root/non-author review and current
finite interval, not compiled timestamps or a fixed publication ID. The interval
is at most ten minutes and is checked before and after awaits. Dynamic review
records are accepted only through the independently qualified protected operator
publication path. Hash matching identifies bytes; it authenticates no meaning.

`reserveSelected(operation)` preflights at most two exact-selector published,
unretired candidates and requires exactly one. It chooses no latest row, ignores
no failed candidate and never falls back. An expired unretired publication must
be explicitly retired before a later one can be selected. Overlapping custody
intervals and reused root/raw attempt IDs are rejected permanently by guards.

## One authority and finite allocations

Exactly three append-only guarded relations hold envelope headers, complete
ordered payload chunks and events. Payloads have at most 16 chunks of 262,144
ASCII bytes each, with a 4,194,304-byte outer ceiling. Headers are at most 16 KiB.
ASCII canonical JSON preserves source bytes through the explicit wire encoding;
complete source bytes and all native packets remain in the payload. There is no
truncation, source-hash replacement, latest pointer, pruning or automatic publish
loop. The finite header supports 1–16 complete capture keys and distinct exact
raw attempt IDs. At most `3+2*object_count` ordered events can exist (35 maximum,
including publish, reservation, each consume/terminal and permanent retirement).

The source reserves once, each exact owner consumes its protected raw attempt
before native acquisition, and the source records its terminal result. The
existing legacy NativeCaptureControl remains unchanged and authoritative only
for its old attempts. New D1 events are the sole authority for new raw attempts;
there is no duplicate object-local claim ledger. Existing legacy/outer run and
capture budgets must be independently reconciled before publication. Nothing
here creates campaign headroom or converts an unknown count to zero.

Every header explicitly selects `raw-capture` or `evidence-use`. Raw mode requires
its complete nonempty capture-key/attempt population. Evidence-only mode permits
exactly `main-assess` or `partition-reconcile`, requires empty raw key/attempt
arrays, and forbids every native-consumed event/acquisition. It is a distinct
explicitly reviewed/published operation and unique root attempt; it cannot spend
a raw attempt or supply an extra native capture. Its positive byte ceilings do
not grant acquisition authority when its raw population is empty.

For evidence-only work, reserve the exact operation, await the protected positive
assessment/reconciliation, then call `finishEvidenceUse` on that reservation.
The method appends its own generic empty-key terminal and independently rechecks
fresh primary history, source/control binding, retirement and time before returning.
It does not fabricate a native owner consumption or borrow a raw capture's final
request. The complete operation uses five requests/eight statements and one full
payload materialization, separately allocated under its eight-request/32-statement
cap. Lost ACK, expiry, retirement during the protected await/final read, replay or
missing/wrong-mode allocation refuses. Same three immutable relations retain all
generic and native attempt identities permanently across modes/intervals.

Each raw attempt is conservatively charged three shared source requests, three
owner consume requests, one terminal request and one shared final validation:
eight requests and no more than 32 statements. A complete N-object envelope
performs exactly `4+4*N` requests and `7+7*N` statements in the fixed successful
path; the explicit total allocation reserves `8+8*N` statements. Shared work is
charged to every raw attempt as well as to the envelope total. Two-object tests
measure 12 requests and 21 statements, each on a fresh primary session. Every
allocation must have exactly the nine declared own enumerable data fields, each
a safe positive integer. Missing/inherited/accessor/nonfinite/extra fields refuse
before publication, construction or bounded-header-to-payload acquisition.
The per-attempt statement reserve is mode-specific: at least 15 for raw work
(14 actual fixed shared-source/owner/terminal/final statements) and eight for the
distinct evidence-only operation. Population totals cannot lend statements to an
underallocated attempt. Each runtime batch also charges the selected individual
attempt cap: source counters hold the owner's complete fixed cost, while an owner
counter holds the shared source/terminal/final cost. Actual shared/key-specific
requests are charged before I/O against both the individual and envelope totals.
Thus even the 16-key case preserves each raw attempt's eight-request/32-statement
ceiling while independently charging its 68-request/119-actual-statement aggregate.

One ledger instance has exactly one lifetime role: one source reservation with
its exact per-key terminal events and one final validation, or one exact owner
consumption. It cannot change role, envelope or capture key, materialize again,
or repeat final validation. SQL uniqueness prevents a different instance from
receiving another positive copy/acquisition for the same exact raw attempt. A
denied duplicate invocation remains NO-GO; it supplies no positive authority or
allocation credit. Actual complete holder/custody and invocation budgets still
must exclude or separately account for unauthorized/failed calls.

Standalone `read` unconditionally refuses before any I/O. No separate bounded
payload-reconciliation allocation was accepted for that path, so it cannot borrow
the source/owner copy allowance before or after reservation or cold restart.
The exact separately allocated operator status/readback plans have no default grant;
unknown authority remains NO-GO without a new payload materialization or claim.

Before fetching chunks, schema-bounded header/aggregate preflight reserves
`6*payload_bytes+65536` serialized acquisition bytes and `4*payload_bytes` decoded
protocol bytes per complete materialization. The source plus each owner copy and
separately allocated native facts count toward an explicit aggregate allocation.
This source additionally refuses protocol allocations above 32 MiB acquired,
16 MiB decoded, 16 MiB native and 64 MiB aggregate. These charges are conservative
transport/materialization accounting, not an assertion of exact JavaScript heap
size or actual account/runtime fit. The 4 MiB protocol cap is not usable caller
allocation by itself. Complete larger populations/packets that cannot fit refuse.

Any mutation timeout, lost/malformed acknowledgement, concurrent revision change
or retirement refuses positive use. Mutations are never retried to find their
outcome. An instance with an uncertain mutation cannot obtain a positive final
validation; restart cannot acquire another full payload or claim. Only separately
authorized/accounted exact operator status plans may reconcile unknown metadata.
Terminal completion cannot manufacture an initial reservation/consumption.
No transaction spans D1 and native object storage. An unused reservation safely
loses availability. Retirement cannot cancel an acquisition, prove callback death
or release exclusive custody early.

## Verification and provider limits

Native TypeScript 7.0.2:

```
node_modules/@typescript/typescript-win32-x64/lib/tsc.exe --noEmit -p probes/pmb1-runtime-evidence/tsconfig.json
```

Node 24.22.0 synthetic SQLite tests:

```
node --test probes/pmb1-runtime-evidence/ledger.test.mjs
node --test probes/pmb1-runtime-evidence/operator.test.mjs
node --test probes/pmb1-runtime-evidence/allocation-mode.test.mjs
```

The tests exercise exact SQL and guards, complete multi-object success, atomic
partial-publication rollback, hostile ordinary mutations, exact substitutions,
escaped source-byte budgeting, retirement races, expiry, lost acknowledgements,
restart/replay, malformed/corrupt history and later fresh intervals on the same
unchanged journal/resources/code. They deliberately demonstrate the trusted-code
guard-removal limitation. Synthetic records have no actual factual authority.
The operator suite additionally exercises the concrete local Miniflare D1 SDK
path, mid-batch rollback, exact independent readback, source/authority/envelope
substitution, missing/finite budgets, unknown acknowledgements and one-shot
execution. Its loopback-only runtime blocks all external requests. The older
2026-08-06 emulator proves no configured 2026-10-16 or managed-runtime fit.

Cloudflare's official [D1 limits](https://developers.cloudflare.com/d1/platform/limits/)
(checked 2026-10-23) list a 2,000,000-byte value/row limit, 100 parameters per query,
100,000-byte statement limit and 50/1000 queries per invocation (Free/Paid).
Individual fixed chunks/statements stay below those documented individual limits.
Sixteen objects need 68 evidence requests/136 conservatively reserved statements
in aggregate, so per-invocation distribution and **all existing work** must be
qualified against the actual selected plan. No aggregate fit follows from the
individual maxima. Inability to fit the complete invocation remains NO-GO.

Cloudflare documents [D1 batch transactions and first-primary sessions](https://developers.cloudflare.com/d1/worker-api/d1-database/).
The transaction model supports the fixed one-database batches; it does not prove
semantic review, real attribution, actual engine/durability or memory qualification.
No compatibility-date/tooling upgrade is made here. Local older-emulator evidence
cannot qualify the configured 2026-10-16 hosted compatibility date.
