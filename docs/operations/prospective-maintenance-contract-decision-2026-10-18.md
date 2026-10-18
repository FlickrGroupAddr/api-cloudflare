# Prospective maintenance baseline: exact source-contract decision

Date: 2026-10-18. Ticket #0181. Status: **Proposed owner decision; not accepted,
implemented or qualified.** This packet recommends a specific future source
contract, called **PMB-1** below. That label identifies this proposal, not an
existing build, deployed configuration, production schema or captured baseline.

## Recommended decision

Accept PMB-1 as the contract for a future maintenance-capable retained artifact:
preinstalled D1 mutation guards, a durable singleton control, explicit outage,
object-local enforcement for every included Durable Object, complete typed
equality, and the existing ordinary current-installation GET as the successful
authenticated restoration check. Keep the historical exact-original attempt
**NO-GO**. A schema-only change to the historical module is not the selected path.

The conventional choice is a small local guard and an outage. No distributed
lock service, cross-store transaction, custom privilege service or storage move
is proposed. If an included store cannot meet this contract with supported local
operations and bounded evidence, the candidate refuses; acceptance does not
authorize excluding it or building a different architecture silently.

The [reviewed design](prospective-maintenance-baseline-design-2026-10-18.md)
supplies rationale, writer coverage and a proposed finite fault allocation.
#0171 accepted planning only; #0179 completed the reviewed design. This packet
supplies the concrete contract choice left open by those records.

### Exact acceptance wording for Terry

> I accept PMB-1 in this document as the prospective maintenance source contract,
> including its D1 control schema and fixed transitions, complete guard coverage,
> outage and closed-interval rules, future-artifact direction for included-store
> closure, and the successful current-installation GET specified below. Preserve
> complete typed equality and the historical exact-original NO-GO. Implement and
> independently review the source under this contract; prepare the exact isolated
> qualification packet separately. This decision does not authorize private or
> provider access, schema installation, production migration/capture/deployment,
> a cloud experiment, cleanup, reopening, or any relaxation of an existing gate.

This is a recommendation awaiting an actual recorded owner decision. A review
pass, ticket move, source merge or copied approval sentence is not acceptance.
If Terry chooses an amendment, record its exact replacement clause and owning
contract before relying on it. No generic reapproval is required for faithful
implementation or a lossless codec that preserves the existing typed contract.

## Authority and evidence limits

The [canonical authority policy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md),
accepted [ADR0051](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0051-trust-private-storage-runtime-with-guarded-writes.md),
[preservation contract](fixed-origin-preservation-2026-10-17.md#paused-gates-and-consistent-full-data)
and [restoration protocol](fixed-origin-restoration-2026-10-17.md#return-to-design-handoff-finite-preservation-protocol)
remain controlling. PMB-1 proposes a new prospective baseline; it does not amend
permanent suppression, history, authentication, durable ordering or equality.

Public source was inspected, not a deployed account or historical private
artifact. The actual production schema, writer/binding-holder inventory,
Durable Object population, alarms, effective grants and pending operations are
**unobserved**. No current source inventory is a production census. The exact
artifact/configuration/resource identities belong in the later separately
authorized candidate and action packets, with independent evidence.

Acceptance selects source behavior for an isolated future candidate. It does not
assert that an actual production schema fits it, or accept an unseen production
baseline. Actual discovery that cannot fit this contract refuses that candidate;
it cannot retroactively broaden the owner's choice.

## D1 schema and fixed operations

The proposed new relation is exactly `maintenance_control` with these columns:

| Column | Stored type and constraint |
| --- | --- |
| `singleton_id` | SQLite INTEGER, NOT NULL PRIMARY KEY; the only permitted value is integer `1` |
| `generation` | SQLite INTEGER, NOT NULL; `typeof(generation)='integer'` and `1 <= generation <= 9223372036854775807` |
| `state` | SQLite TEXT, NOT NULL; `typeof(state)='text'` and exactly `open` or `closed` |

Use an ordinary rowid table. Its key aliases the SQLite rowid, which enters the
complete snapshot. No timestamps, TTL, heartbeat, lease-expiry unlock, extra
mutable status column, second row or automatic initialization is part of PMB-1.
SQLite affinity may normalize bound inputs; stored types are authoritative.
The expected-generation parameter is canonical positive decimal TEXT, validated
before dispatch and compared with `CAST(generation AS TEXT)`; do not cast an
unvalidated caller string to INTEGER or round it through a JavaScript number.
Readback likewise returns the integer's exact decimal text and stored type.

The following is **inert review text**, not an executable migration file:

```sql
CREATE TABLE maintenance_control (
  singleton_id INTEGER NOT NULL PRIMARY KEY
    CHECK (typeof(singleton_id) = 'integer' AND singleton_id = 1),
  generation INTEGER NOT NULL
    CHECK (typeof(generation) = 'integer'
           AND generation BETWEEN 1 AND 9223372036854775807),
  state TEXT NOT NULL
    CHECK (typeof(state) = 'text' AND state IN ('open', 'closed'))
);
INSERT INTO maintenance_control(singleton_id, generation, state)
VALUES (1, 1, 'closed');
CREATE TRIGGER maintenance_control_no_insert
BEFORE INSERT ON maintenance_control
BEGIN SELECT RAISE(ABORT, 'maintenance_control_insert_denied'); END;
CREATE TRIGGER maintenance_control_no_delete
BEFORE DELETE ON maintenance_control
BEGIN SELECT RAISE(ABORT, 'maintenance_control_delete_denied'); END;
CREATE TRIGGER maintenance_control_transition
BEFORE UPDATE ON maintenance_control
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND typeof(OLD.singleton_id) = 'integer' AND OLD.singleton_id = 1
    AND NEW.singleton_id = OLD.singleton_id
    AND typeof(NEW.singleton_id) = 'integer'
    AND typeof(OLD.generation) = 'integer'
    AND OLD.generation BETWEEN 1 AND 9223372036854775806
    AND typeof(NEW.generation) = 'integer'
    AND NEW.generation = OLD.generation + 1
    AND typeof(OLD.state) = 'text' AND typeof(NEW.state) = 'text'
    AND ((OLD.state = 'open' AND NEW.state = 'closed')
      OR (OLD.state = 'closed' AND NEW.state = 'open'))
  THEN 1 ELSE RAISE(ABORT, 'maintenance_control_transition_denied') END;
END;
```

The migration's fixed bootstrap creates exactly `(1, 1, 'closed')` during its
separately authorized outage, installs the complete guard set in the same
qualified atomic migration boundary, and independently verifies it before
declaring bootstrap complete. It never uses `IF NOT EXISTS`,
`INSERT OR IGNORE`, replacement or an upsert to accept unexpected old state.
Bootstrap is a one-time migration state, not an open-to-closed transition.
Partial installation or unexpected prior objects refuse and retain the outage;
there is no ordinary-request self-repair. A migration is not supplied here. If
normal service is needed before the next maintenance interval, initial opening
is a separately authorized `reopen(1)`, followed later by `close(2)`. A candidate
remaining closed from bootstrap may instead use independently qualified bootstrap
closure receipts; it must not issue an impossible second close or treat zero
affected rows as acknowledgment. Bootstrap must meet the same writer-ordering
and admitted-work obligations before a baseline can begin.

After bootstrap, only two fixed, parameterized operator transitions exist:

| Operation | Precondition and single-transaction effect |
| --- | --- |
| `close(expected_generation)` | Exactly the valid singleton `(1, g, 'open')`, exact expected `g`, and `g < 9223372036854775807`; set only `generation=g+1`, `state='closed'` |
| `reopen(expected_generation)` | Exactly the valid singleton `(1, g, 'closed')`, exact expected `g`, and `g < 9223372036854775807`; set only `generation=g+1`, `state='open'` |

Each operation requires exactly one affected row and an independent authoritative
readback of the new row and pinned guard/schema definitions. An expected-zero
result is a refusal, never idempotent success. Duplicate close/reopen, stale
expected generation and same-state updates refuse. Counters never decrease,
reset, wrap or promote to REAL. Exhaustion refuses; a closed maximum generation
may remain closed indefinitely and does not justify reset or emergency reopening.
Packets needing a later reopen must reserve the required counter headroom before
starting their separately authorized lifecycle.

Both fixed UPDATEs predicate on whole-relation count 1, exact typed key 1, valid
typed expected state and generation in 1..9223372036854775806, plus
`typeof(:expected_generation)='text'` and
`CAST(generation AS TEXT)=:expected_generation`. They set only the fixed next
state and `generation=generation+1`. No caller selects SQL, next state or next
generation. Never batch a control transition together with ordinary work.

The source must constrain runtime control INSERT/DELETE and key changes to
refuse; its control UPDATE guard permits only the two adjacent-generation state
transitions above. Creation belongs only to bootstrap before those guards are
installed. Ordinary application routes, scheduled tasks and recovery paths have
no code path targeting this relation or its guard definitions. A trigger cannot
distinguish an operator from code sharing broad D1 authority: fixed-code review,
capability custody and the exclusive operator embargo enforce that separation
under ADR0051. PMB-1 claims no separate D1 administrator role or injection-proof
runtime isolation.

Latch each transition intent in the separately owned private journal before
dispatch. Lost acknowledgment, timeout, malformed receipt, affected-row mismatch
or failed independent readback leaves the outcome unknown. Use only the exact
packet's bounded read-only reconciliation; no mutation replay, new generation,
fallback command or automatic reopen follows uncertainty. An operation response
that repeats the requested target is not independent readback.

## Mutation guards and ordering

For every actual ordinary D1 table, install BEFORE INSERT, BEFORE UPDATE and
BEFORE DELETE guards. Each executes `RAISE(ABORT, 'maintenance_closed')` unless
the entire control relation has exactly one row, whose key/type, integer
generation/range and text state are valid and whose state is `open`. Express
the refusal with an explicit positive-validity test such as `NOT EXISTS` of the
complete valid singleton, plus whole-relation count validation; never use a
nullable `state <> 'open'` predicate. Missing/extra/malformed/NULL authority,
unknown schema or an unreadable control relation must prevent commit.

Use the following body for all three unrestricted BEFORE events, in ordinary
persistent triggers on each enumerated actual table; `UPDATE OF` and TEMP
triggers are not acceptable substitutes. Trigger names and quoted target names
belong in the exact candidate manifest, not a guessed production table list:

```sql
SELECT CASE WHEN
  (SELECT COUNT(*) FROM maintenance_control) = 1
  AND EXISTS (
    SELECT 1 FROM maintenance_control
    WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
      AND typeof(generation) = 'integer'
      AND generation BETWEEN 1 AND 9223372036854775807
      AND typeof(state) = 'text' AND state = 'open'
  )
THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
```

The control relation has its special guards above. Every other discovered
ordinary table, including D1 migration/sequence/bookkeeping state capable of
changing, requires qualified closed-state immutability. Internal/provider-owned
state that ordinary triggers cannot cover needs independent supported stability
evidence; if unavailable, refuse. Do not attempt to install unsupported triggers
on provider or SQLite internal tables, and do not exclude those tables instead.

The guard manifest is derived from the exact candidate schema and fixed writer
operations, with every table/trigger definition pinned before the new baseline.
No new uncovered table, replacement trigger or schema edit may enter service.
The source implementation must preserve existing permanent-suppression and
append-only-history guards, including their destructive-statement refusals.

Qualify direct and indirect writes: ordinary/error/recovery/maintenance paths,
authentication/session/quota work, INSERT/UPDATE/DELETE, UPSERT, REPLACE,
cascades, trigger effects, generated values and actual multi-statement batches.
`RAISE(ABORT)` by itself proves statement abort, not rollback of earlier committed
statements. The fixed operation must use a qualified transaction/batch boundary
so a guarded failure cannot leave earlier writes of that operation committed.
Caught exceptions, `IGNORE` conflict handling and zero-row writes must not turn a
refused required mutation into application success.
Zero-match UPDATE/DELETE and zero-row INSERT SELECT may fire no row trigger and
therefore succeed without mutation; they prove neither admission nor valid
control authority. Existing fixed-operation affected-row semantics still apply.
Do not rely on DELETE-trigger firing for REPLACE or on trigger execution order.

The required D1 close ordering is exact: ordinary writes ordered before close
are fully committed or rolled back before its confirmed receipt; every ordinary
mutation ordered after it fails atomically, including stale invocations. A
separate SELECT, environment flag, bookmark, caller assertion or request-local
boolean cannot authorize a later unguarded write. The guard is evaluated at the
storage mutation boundary. Full snapshots, unchanged counts and elapsed quiet
time do not prove this linearization property; #0182 must qualify it.

## Future artifact, Durable Objects and other writers

Select a **new future maintenance-capable retained artifact** for PMB-1. It must
contain the fixed operations and all included-object closure behavior before
the prospective baseline. Exact source/build/module digests, configuration,
bindings and object namespace/class lifecycle are frozen in the later packet.
Restoration means that exact new retained version at weight100 with
`force=false`; it never means rebuilding or modifying the historical original.

For each included Durable Object, the future artifact uses an object-local
durable singleton with the same typed key, state, generation and transition
rules. Every SQL/KV mutation and explicit alarm create/update/delete checks the
valid open record and commits its effect in the same supported object-local
transaction. Code that checks once before an `await`, then writes without that
transactional check, fails the contract. The fixed close operation and independent
readback must account for the complete local SQL/KV/alarm state. The record is
part of the new baseline; no common transaction with D1 is claimed.

Existing object code that omits the local fence is not compatible with PMB-1.
An included old execution/version may not regain an unguarded mutation path on
restoration. The candidate must provide a supported, independently qualified
inventory and admitted-work disposition covering every included object, old
version, alarm delivery/retry and queued execution. Explicit `setAlarm` guards
alone do not freeze provider delivery metadata. Unknown object enumeration,
automatic metadata drift, unreadable KV/alarm state, unsupported atomic alarm
coverage or an unguarded old writer refuses the all-store candidate.

Apply the same closure obligation to every other writer: schedule, queue,
service/preview/version caller, human, CI, emergency operator, native secret
replacement and provider operation. Suspend new admission and settle already
dispatched external calls and their mandatory durable safety results before
storage closes. Do not use guards to discard a required result transaction.
Managed-secret/deployment mutation needs an exclusive custody embargo and
settlement evidence; SQL cannot fence it. No secret value read is authorized.
DDL, imports, whole-store deletion, Time Travel and guard removal remain under
the same exclusive embargo through final readback.

State-only guards fence stale invocations while closed; reopening can make
them writable again. Reopen therefore additionally requires independent proof
that every pre-close and temporary-artifact admitted execution can no longer
resume with old authority, including delayed callbacks and alarm retries.
Otherwise remain closed. Existing domain fencing still applies. A generation
field alone supplies no invocation fencing, and PMB-1 invents no global provider
drain acknowledgment or distributed lock. If small fixed operations cannot prove
the required disposition, return a concrete source/qualification gap.

## Ordinary authenticated restoration check

Select the existing ordinary route **`GET /api/v001/installations/current`**,
using one explicitly authorized current bearer credential for an active
`lrc_plugin` installation, `FGA_READ_ENABLED='1'`, no query and no request body.
The future retained artifact must use the actual ordinary route, registry,
authentication and D1 lookup; a wrapper, synthetic success response or special
maintenance bypass is not acceptable.

Require HTTPS/edge routing and exact target-version evidence from the separate
action packet, then HTTP200 JSON with exactly these fields and no others:

| Field | Required result |
| --- | --- |
| `schemaVersion` | integer `1` |
| `installationId` | exact independently bound installation identity |
| `installationRevision` | exact independently bound positive safe integer revision |
| `installationState` | `active` |
| `presentedCredentialState` | `current` |

Require `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and
`Referrer-Policy: no-referrer` and the ordinary JSON content type. Compare decoded
JSON shape/values, not serializer key order. Redirects, asset shells and cached
responses refuse. The bound identity/revision and credential remain
private; public evidence reports comparison booleans. No pending, expired,
revoked, malformed or unknown credential is an authenticated-success substitute.
Missing/invalid credentials and unavailable storage must retain their ordinary
refusal semantics; those negative responses are separate conformance evidence.

The ordinary success must execute no Flickr call, credential activation,
session touch, quota/audit/maintenance mutation or deferred included-store
write. Current public source's route calls `authenticate` with the SELECT-only
`d1Lookup`, then `jsonCurrent`: see [`worker.ts`](../../src/worker.ts),
[`installations.ts`](../../src/installations.ts) and
[`registry.ts`](../../src/registry.ts). Constructing the Flickr-fetch closure
does not invoke it. This is source evidence for the route choice, not evidence
about a historical module or deployed route.
`FGA_READ_ENABLED='1'` also enables scheduled cleanup in current source. Keeping
this route reachable is not evidence that schedules are closed: their admission,
already admitted work and later guarded writes need separate closure evidence.

[Accepted ADR0032](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0032-read-the-current-installation-resource.md)
already defines this safe GET. The
[credential lifecycle](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/installation-credential-lifecycle.md)
allows, but does not require, coalesced activity observations. PMB-1 chooses an
artifact with no such included-store observation or deferred obligation on this
path during closure. That is faithful behavior, requiring no authentication
amendment. Required writes on other routes remain required; caught/rejected
writes, absent side-effect receipts, a 503 or an after-reopen success cannot pass.

The isolated packet must reserve at most the reviewed four authenticated-request
slots per run. At least one successful check occurs after independent retained-
target restoration readback and before final restored capture, with all stores
still closed. Freeze the remaining checks/slots in #0182's exact packet; do not
invent additional calls or change fixtures during comparison. A new mandatory
write requirement or request that a write-bearing route succeed under closure
would be a genuine contract change needing a specifically scoped decision.

## Complete baseline and lifecycle

The prospective baseline includes the exact installed schema and every guard,
the closed control generations, all stored typed cells/duplicates, hidden
rowids or WITHOUT ROWID keys, D1 migration/sequence/bookkeeping facts and every
included object's SQL/KV/alarm state under the existing complete-state meaning.
It is relational equality, not physical database-file equality. No ignored
table/column/store, sampled digest, changed type, rounded REAL, permitted drift,
monotonic-only witness or repair write is accepted.

Both production `flickr_write_gates` rows remain independently paused at their
exact pinned positive revisions throughout; neither is this maintenance control.
The qualification-admission row has its own separately accepted lifecycle.
Journaling occurs outside all compared stores and cannot append inside them.

The finite lifecycle is: separately authorize preparation/install; close new
admission and settle prior work; establish the operator embargo; close and
independently read back each store; begin the common interval only after the
last confirmed closure; capture complete baseline, fresh preflight and restored
state inside that interval; independently confirm admission off and nonforced
exact retained-target restoration; perform the ordinary check above; require
complete exact equality and every required receipt/authorized cleanup; only then
consider a separately authorized reopen outside comparison, with stale work
independently settled. No timeout, process restart, credential expiry, failed
check or cleanup uncertainty automatically ends the outage.

Any unknown closure, unsettled external dispatch, missing effective writer,
unreadable included state, unsupported actual schema/value or exhausted bound
refuses before capture/admission. A mid-interval failure leaves the result
unconfirmed and preserves the closed/paused state as observed; do not claim a
state that cannot be independently read. Recovery is separately authorized,
not an automatic retry, forced restore, substitute target or data correction.

## REAL reader and qualification gates

The current [private reader](private-full-snapshot-reader-2026-10-18.md#implemented-source-interface)
refuses **every SQL REAL cell**. The actual schema must be discovered; current
source declares REAL token fields in
[`0007_browser_auth.sql`](../../migrations/0007_browser_auth.sql) and
[`0011_submission_status.sql`](../../migrations/0011_submission_status.sql), but
this packet observes no deployed values. Neither empty tables nor integer-only
fixtures prove the lossless REAL extraction needed for a complete candidate.

#0180's separate reviewed investigation remains a plan, not qualified extraction.
Preserve refusal until a lossless extraction implementation and independent
qualification prove exact canonical finite binary64 round trips through the
actual D1 representation. Implementing that faithful codec does not itself need
a new owner decision. Changing equality, stored types/schema, accepted values,
extraction trust boundary or access scope would need its own precise amendment.
Do not reopen or rewrite Completed #0170 to imply it already supplied support.

| Gate | What PMB-1 acceptance supplies | What remains required |
| --- | --- | --- |
| Source contract | Selected behavior for the future candidate | Implemented source, exact schema/guard manifest, independent implementation review |
| Isolated qualification | Direction only | #0182 exact all-store artifact/resource/reader/grant/custody/action packet, separate authorization and independently reviewed actual results |
| Production baseline | Nothing observed or approved | Exact actual census/schema/configuration/resources, qualified complete reader/barrier and separate production action decision |
| Production temporary run/restore/cleanup/reopen | No action authority | Exact lifecycle packet, independent receipts and each applicable existing release/action gate |

#0182 is the actual all-store qualification gate and remains unpassed. #0163
retains that dependency and all its other prerequisites. The reviewed twelve-
case/twelve-run/36-capture proposal remains inside the shared 24-run/72-capture
ceiling; PMB-1 adds no run, resource, call or provider authority. If full candidate
schema/object coverage cannot fit the existing resource/budget allocation,
#0182 must refuse that packet and present the specific scope change for review.
A miniature D1 fixture qualifies only the mechanism it actually exercises.

All materialization, preservation, restoration and deployment readiness remains
false. This packet is ready for owner judgment only after fresh independent
High review of these concrete clauses. Owner acceptance will settle the source
contract decision; it will not qualify the barrier or authorize an experiment.
## Independent source-contract review

Fresh independent High review passed PMB-1's concrete schema/transition, guard,
future-artifact and existing authenticated-check clauses, authority boundaries,
full equality and remaining all-store/REAL qualification gates. No actionable
finding remains. Frozen public/staged bytes matched; source and local-reference
checks were static. No SQL, guard, private-data, provider or native operation was
performed. PMB-1 remains Proposed until Terry makes the actual contract decision;
review and publication alone do not accept it.
