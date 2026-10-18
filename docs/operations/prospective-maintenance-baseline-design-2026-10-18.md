# Prospective maintenance baseline: barrier design and isolated qualification plan

Date: 2026-10-18. Ticket #0179. Status: **Proposed design and qualification
specification; planning direction accepted, mechanism unimplemented and
unqualified**. The historical exact retained-original attempt remains **NO-GO**.
Implementation, private materialization, preservation, provider restoration and
deployment readiness remain false. This document authorizes no execution.

## Outcome and authority

Use a conventional maintenance outage and preinstalled storage guards as the
candidate for a separately accepted future baseline. The D1 candidate is one
maintenance-control row and ordinary SQL mutation guards in the same database.
It is a backstop against stale code; it does not supply an account-wide freeze,
a complete invocation drain or a barrier for Durable Object alarms and storage.
Those gaps must be resolved for the exact inventory, or the candidate refuses.

Terry accepted **prospective baseline planning only** in the
[#0171 decision record](temporary-composition-writer-barrier-proposal-2026-10-18.md#exact-owner-decision-and-handoff).
No schema baseline, future artifact or authenticated-check amendment was accepted.
The original module, configuration, capture and restoration packet remain intact.
A later schema baseline or changed artifact must be named and accepted separately;
neither can turn the historical attempt into an exact-original pass.

The governing sources are:

- Canonical [documentation authority](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md),
  accepted [persistence/scheduler contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/worker-persistence-scheduler-contract.md),
  [required conformance contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/testing/fail-polite-worker-database-conformance.md)
  and [ADR0051](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0051-trust-private-storage-runtime-with-guarded-writes.md).
  The scoped private-runtime trust decision retains guarded ordinary writes,
  permanent suppression, append-only history, atomicity, ordering, fencing,
  least privilege and recovery. No transaction spans D1 and Durable Objects.
- The [preservation contract](fixed-origin-preservation-2026-10-17.md#paused-gates-and-consistent-full-data)
  requires complete typed relational contents, schema and row identities, with
  unchanged paused production gate values and revisions. There is no ignored
  table, permitted drift, monotonic-only substitute or witness amendment.
- The [restoration protocol](fixed-origin-restoration-2026-10-17.md#return-to-design-handoff-finite-preservation-protocol)
  owns exact retained version/configuration/resource continuity, nonforced
  restoration, ordinary authenticated checks and independent receipts.
- The selected [private full-snapshot proof direction](../design/temporary-composition-preservation-proof-2026-10-18.md),
  [bounded reader](private-full-snapshot-reader-2026-10-18.md) and
  [materialization handoff](temporary-composition-materialization-handoff-2026-10-18.md)
  retain separate reader, custody, access and action gates. #0172's fresh-D1
  reader qualifier is separate; this plan neither runs nor enlarges it.

This specification uses public source and synthetic descriptions only. Current
checkout behavior identifies coverage obligations; it proves neither the exact
historical artifact's behavior nor the effective deployed writer census. Provider
links below identify reviewed primary documentation and limits, not current
account observations or a hosted qualification result.

## Proposed D1 control and guard contract

The prospective migration would install a singleton `maintenance_control` row
before the new baseline. Its proposed fields are a fixed singleton key, a positive
signed 64-bit integer `generation`, and `state` restricted to `open` or `closed`.
Generation advances once on an acknowledged open-to-closed transition and again
on a separately authorized closed-to-open transition. No wrap, decrease, TTL,
automatic unlock, periodic heartbeat or timestamp-based authority is permitted.
Exhaustion refuses a transition and requires a new reviewed decision.

The fixed maintenance operation conditionally changes the expected open row and
generation to closed with the next generation in one database transaction. It
requires exactly one affected row and an independent authoritative readback of
the closed row and guard schema. A returned request target or supplied receipt
is not readback. A failed or lost response leaves the close outcome unknown;
there is no retry with a new generation or automatic reopen.

For each actual ordinary application table, proposed `INSERT`, `UPDATE` and
`DELETE` guards reject the entire mutation unless the singleton control state is
valid and open. Absence, duplicate/incorrect singleton state, wrong types,
unknown state or unreadable authority must fail closed, including SQL NULL
conditions. The exact trigger predicates and abort semantics require later
implementation review and D1 qualification. A separate application SELECT,
request-local boolean, D1 Session/bookmark or reusable caller assertion cannot
authorize an unguarded later mutation.

The guard census must include ordinary temporary coordination/audit/quota tables,
not only safety tables. Cover multi-statement batches, UPSERT, REPLACE, indirect
cascades and every error/cleanup path. A failed guarded batch must not leave
its earlier writes committed. Existing permanent-block and append-only guards
remain active and independently tested; the maintenance migration must not
replace or weaken them. Statement coverage must be derived from the actual
schema and fixed writer operations, then independently checked against every
binding holder. A new table without qualified coverage prevents the baseline.

The control row is a special maintenance relation: fixed operator operations
alone may create it during migration or close/reopen it outside comparison.
Ordinary request, schedule and recovery code exposes no operation targeting it
or guard/schema definitions. SQL triggers do not distinguish an operator from
ordinary code sharing broad native capabilities. This separation relies on
reviewed fixed code, audited capability custody and the accepted private-runtime
trust scope, not a fictional D1 grant or privileged flag inside a request.
If an actual identity can issue uncontrolled ordinary SQL or control mutations,
the required embargo cannot be established and this candidate is unavailable.

The closed control row, its generation, complete schema and all guard definitions
enter the new baseline. They remain exactly equal through final readback.
Maintenance logging belongs in a separately owned private journal outside all
compared stores; logging must not append to the frozen database or mutate an
included alarm. The two production `flickr_write_gates` rows remain independently
paused with pinned, unchanged positive revisions. The run's separate qualification
admission row keeps its own accepted lifecycle; it is not this control row.

The [D1 binding documentation](https://developers.cloudflare.com/d1/worker-api/d1-database/)
describes transactional batch behavior, and the
[SQL statements reference](https://developers.cloudflare.com/d1/sql-api/sql-statements/)
documents SQL behavior relevant to triggers. These are grounds for the candidate,
not proof of these exact predicates, commit ordering, indirect writes or reader
bookkeeping. The required D1 close linearization claim is: every ordinary write
ordered before close is fully committed or rolled back before the close receipt;
every later ordinary mutation fails atomically, including from a stale invocation.
Qualification must prove that claim with actual ordered observations. Equal
snapshots, elapsed quiet time and stable counts cannot establish it.

A state-only trigger fences stale callers while closed; it does not distinguish
an old caller after a later reopen. Before reopening, independently account for
all prior admitted work so none can resume with old authority. If that cannot
be proved, remain closed. A future artifact that atomically checks an expected
maintenance generation on every local write is a possible separately reviewed
alternative, not behavior supplied to old code by this trigger. Existing domain
lease/generation fencing remains mandatory in either case. A generation field
alone cannot fence an invocation that never presents or checks it.

## Complete coverage and limits

Bind every family below to the exact prospective original/temporary artifacts,
configuration, store, fixed operations, identities, admitted-work disposition and
enforcement evidence. Include old deployments, CI, human, automation, emergency
and provider operators. An absent current export or example binding is not
evidence that a deployed writer does not exist.

| Writer or store | Required treatment before and during comparison | Source evidence / refusal limit |
| --- | --- | --- |
| D1 ordinary and authenticated reads | Guard session touches, audit events, rejected-authentication counters, status quotas and maintenance writes; settle pre-close obligations first | [`browser_sessions.ts`](../../src/browser_sessions.ts), [`plugin_codes.ts`](../../src/plugin_codes.ts), [`submission_status.ts`](../../src/submission_status.ts). Best-effort or caught write failure cannot stand in for required successful semantics. |
| D1 intake, installation, administration and credentials | Cover every route, callback, rotation, rate bucket, grant/result/history and lease mutation through the same database-local guard census | [`worker.ts`](../../src/worker.ts), [`installations.ts`](../../src/installations.ts), [`upload_authorization.ts`](../../src/upload_authorization.ts) and [#0171 census](temporary-composition-writer-barrier-proposal-2026-10-18.md#writer-inventory-and-evidence-boundary). An environment dispatch flag is insufficient. |
| Provider reads, publish and albums | Cover cache/staging, reservations, rejection state, upload/binding evidence, obligations, repair and delayed result settlement; no external operation is started by this plan | [`flickr_reads.ts`](../../src/flickr_reads.ts), [`flickr_rate.ts`](../../src/flickr_rate.ts), [`group_discovery.ts`](../../src/group_discovery.ts), [`photo_memberships.ts`](../../src/photo_memberships.ts), [`album_materialization_worker.ts`](../../src/album_materialization_worker.ts), [`album_attachment_worker.ts`](../../src/album_attachment_worker.ts), [`album_title_worker.ts`](../../src/album_title_worker.ts). An unsettled external dispatch refuses capture. |
| Schedules, recovery, service/queue/preview/version callers and other binding holders | Close new admission by the separately reviewed outage procedure; account for already admitted work, retries, `waitUntil` and delayed callbacks; guard their later D1 mutations | [`worker.ts`](../../src/worker.ts) runs scheduled maintenance before its dispatch capability check; [`dispatch_worker.ts`](../../src/dispatch_worker.ts) has delayed work. Current source does not establish the effective deployed census or a complete provider drain. |
| Included Durable Object SQL, KV and alarms | Require an independently qualified object-local barrier and complete state readback for every included object, with exact namespace/class lifecycle continuity | [`dispatch_worker.ts`](../../src/dispatch_worker.ts) stores `partitionId` and changes alarm metadata. A D1 trigger covers neither KV nor alarm operations. A SQL trigger in an object would not by itself cover non-SQL metadata. |
| Migrations, direct SQL, schema/guard changes, import/export and recovery | Establish an exclusive operator embargo before baseline and retain it through readback; suspend CI/tools, imports, Time Travel, manual repair and schema changes | [`migrations`](../../migrations), [`controlled_trial_pause.py`](../../scripts/controlled_trial_pause.py). Row triggers do not fence DDL, whole-store restore, erasure or a trusted administrator removing them. No new privilege service is proposed. |
| Provider/reader bookkeeping | Include every discovered schema object, migration/sequence/bookkeeping row and exposed stored identity; qualify effects of observation itself | [Reader codec contract](private-full-snapshot-reader-2026-10-18.md#implemented-source-interface). Provider-written or inaccessible state must be proved stable/readable within the existing equality definition; no silent exclusion or guessed empty inventory. |
| Managed secrets and deployment configuration | Stop credential replacement and account for pending native secret-store writes before the baseline; preserve exact reference/generation/resource continuity under the restoration contract | [`native_writer.ts`](../../src/native_writer.ts), [`native_lifecycle.ts`](../../src/native_lifecycle.ts) and the [restoration protocol](fixed-origin-restoration-2026-10-17.md#return-to-design-handoff-finite-preservation-protocol). Secret-store values are outside the selected snapshot permission and must not be fetched; SQL guards cannot freeze provider PATCH/deployment operations. |

The accepted Durable Object storage API has an
[object-local transaction boundary](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/).
No D1 transaction coordinates closure with all objects. The proposed operational
sequence therefore closes and independently reads back each enumerated store,
then begins the common interval only after the last closure is proved. If an
included object's old code can write KV or alter/rearm alarms without a durable
local fence, restoring that code invalidates closure. Without a documented,
independently qualified complete drain/exclusion mechanism, refuse. An advisory
role for the object does not remove its included state from full equality.

For a separately accepted future object artifact, the small candidate is one
object-local durable maintenance record with the same open/closed generation
rules. Each fixed partition/KV write and explicit alarm create/update/delete
must read that record and perform its guarded mutation in the same supported
object-local transaction. The maintenance close message has one fixed operation,
one latch and an independent readback. A D1 lookup followed by an object write,
or an early `alarm()` entry check followed by an awaited unguarded update, is
insufficient. This record cannot retroactively protect old code that omits it.

Explicit `setAlarm` protection also does not establish that provider alarm
delivery/retry bookkeeping remains unchanged. The separate object reader must
enumerate every included object and stored/alarm fact, and qualification must
observe automatic metadata effects, restart and queued old executions. Missing
object enumeration, unsupported atomic alarm protection or any unguardable
included metadata refuses the all-store result. No supported global object-list,
alarm freeze or all-version drain is presumed by this proposal.

Do not build a new distributed lock service or move storage merely to fill this
gap. First decide whether a small, reviewed future artifact can honor a local
maintenance state at every local mutation and alarm operation. Such a change is
a separate artifact/lifecycle decision; it is not historical restoration.
If the existing ceiling cannot include the exact stores and receipts needed to
qualify it, stop at the scope gap and seek a separately reviewed campaign change.

## Close, drain, compare and restore sequence

This is a proposed specification, not an executable production runbook.

1. **Prepare outside the interval.** Under future separate authority, review and
   install the candidate migration/artifact, qualify guards, freeze the exact
   store/writer census, establish custody and bind a prospective baseline target.
   Record the maintenance outage and exclusive operator embargo. Confirm both
   production gates are already paused; do not change their revisions inside
   comparison. No guard installation, binding or schema change occurs later.
2. **Stop new work and account for admitted work.** The exact outage packet must
   close each actual entry point and independently establish closure. A route
   change, schedule disable or flag alone is not complete drain evidence.
   Enumerate pending operations and their durable outcomes. Already dispatched
   external calls must complete their required safe result/recovery transactions
   before storage closure; ambiguous or unaccounted outcomes refuse capture.
   Do not use maintenance closure to suppress mandatory safety settlement.
3. **Close storage and acknowledge.** Issue the one conditional D1 close and
   each separately qualified included-store close. Independently read back the
   expected closed generation and guards. Account for writes that raced close
   using the qualified storage ordering and admitted-work receipts. A stale
   callback must be fenced at the local mutation boundary, not trusted because
   it read an earlier flag. Unknown closure or incomplete drain ends admission
   to this attempt; it never starts the baseline.
4. **Capture the new full baseline.** Only after every store is proved closed
   and the embargo effective, discover actual schema and capture every page,
   including control/guard and bookkeeping state. The reader retains exact types,
   duplicates, hidden rowids and WITHOUT ROWID keys. Unsupported REAL cells,
   virtual/shadow tables, inaccessible state or exhausted bounds refuse the whole
   capture. No sampling, drift allowance or physical-page equality is claimed.
5. **Maintain one common closed interval.** Keep all pinned closed generations,
   schema/guards, resource references and embargo unchanged through temporary
   installation/run, fresh preflight, qualification-admission shutdown, retained
   target restoration, ordinary authenticated verification and every restored
   page. There is no simultaneous all-store transaction; continuous qualified
   closure makes the separate complete captures comparable.
6. **Restore without forced fallback.** Use the exact prospective retained target
   under the separately accepted restoration protocol, one latched request with
   `force=false`, then independent deployment/module/configuration/resource and
   full-state readbacks. The provider's [rollback documentation](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/)
   does not supply complete stale-invocation drain. Both old and temporary
   executions must remain fenced through final readback. Rollback refusal or
   loss of closure keeps the result unconfirmed; do not rebuild, force, repair
   data, select another target or alter the old capture to manufacture equality.
7. **End comparison before any reopen.** Require exact baseline/preflight/restored
   equality, ordinary checks, all required receipts and authorized cleanup.
   Only a separately authorized operator may then reopen with the next generation
   and independent readback, outside comparison. Failure, deadline, credential
   expiry, process restart or cleanup uncertainty never authorizes reopen.

The outage plan must supply real admission/drain evidence before it can be
executed. This design does not claim that every present entry point can already
be stopped or that current source contains an invocation ledger. If bounded
closure/accounting is unavailable, return to the owner decision rather than
invent a global drain acknowledgment.

The exact retained artifact's required ordinary authenticated check must succeed
with all mandatory semantics while stores remain closed. A guarded audit/session
write failing, an error being caught, a new wrapper route or a later check after
reopen is not that success. Current installation `current` handling is a candidate
to inspect, not an accepted substitute. If no suitable exact check exists, a
separate scoped amendment at the restoration/check contract is required before
relying on a future artifact. Full equality remains unchanged by this proposal.

There is also a concrete reader incompatibility to resolve independently:
[`0007_browser_auth.sql`](../../migrations/0007_browser_auth.sql) and
[`0011_submission_status.sql`](../../migrations/0011_submission_status.sql)
declare REAL token columns, and current authentication/status paths use
fractional arithmetic. Any actual REAL cell refuses the current complete
reader. A synthetic integer-only fixture or an empty table cannot establish
lossless extraction for those values. Preserve that refusal; maintenance guards
do not change the reader or authorize schema/value coercion. The exact prospective
census and separately owned reader work must resolve this before full capture.

## Isolated synthetic qualification specification

Reserve **twelve cases, at most twelve runs and three complete reader captures
per run (36 total)** within the reader's existing
[24-run/72-capture campaign ceiling](private-full-snapshot-reader-2026-10-18.md#finite-barrier-and-fault-campaign-proposal).
These are allocated slots, not twelve additional runs. Other reader/barrier
cases must share that ceiling. The existing plan permits one isolated database
and one writer artifact; it does not authorize extra Durable Object namespaces,
databases, identities or artifacts. A needed extra store/resource is an explicit
packet/ceiling decision before provisioning, not implied by this case list.

No case is executed under #0179. First implement/review source under separate
authority and rehearse only synthetic behavior within that work's scope. Then
freeze a separately authorized isolated hosted action packet. No production
binding, route, credential, real secret, historical private artifact, native
application or real external publication belongs in these fixtures.

The fixed fixture manifest must include:

- Every admitted store and ordinary writer statement class, the complete schema,
  maintenance control and guard definitions, independent protected-history
  guards, migration/sequence bookkeeping, exact paused gates and revisions.
- Synthetic session/audit/status/authentication markers; NULL, signed 64-bit
  boundary integers, UTF-8/NUL text, bounded BLOBs, duplicates, hidden-rowid aliases
  and WITHOUT ROWID keys. REAL and unsupported schema forms are explicit refusal
  fixtures, never successful complete-capture examples.
- Pinned reader, comparator, writer, retained synthetic target and temporary
  bytes/configuration, tooling/adapter provenance and accepted managed-engine
  provenance treatment. An unchanged uploaded writer artifact may expose the
  fixed synthetic scenarios; scenario selection does not permit arbitrary SQL.
- A complete ordered operation manifest per case: admission/close operations,
  seeded and injected writes, independent reads, delayed callbacks, fault point,
  latch/acknowledgment, expected result, cleanup and unconfirmed disposition.
  Reset writes occur only outside comparison and must be counted and authorized.

For this proposed miniature mechanism fixture, cap the total at eight tables,
64 schema objects, 32 columns/table, 512 rows and 512KiB canonical snapshot
contents, including all discovered provider/migration/sequence/control state.
These are stricter limits, not exclusions. This fixture can qualify only the
exact exercised synthetic statement and lifecycle behavior; it cannot stand in
for the exact future production schema, deployed writer census or independent
application conformance. If required isolated coverage cannot fit this fixture
and the fixed query ledger, refuse preparation and obtain a revised reviewed
allocation before dispatch; do not truncate the schema or silently split runs.

| Case / allocated run | Injection and required outcome | Independent evidence obligation |
| --- | --- | --- |
| 1 | Happy path: safe settlement, close, baseline/preflight/restored equality after exact synthetic retained-target restoration | Separate close/guard readback, all-store closure, fixed fixture facts and complete comparator; exact target/configuration continuity |
| 2 | Writer admitted before close; it settles before baseline or its later write is rejected atomically | Commit/rollback ordered against close; no partial batch, pending safety settlement or hidden later commit |
| 3 | Delayed callback uses an earlier open observation; exercise guarded batch, UPSERT/REPLACE and cascade | Storage rejection and transaction outcome, complete unchanged state; no caller-flag assertion |
| 4 | Close response lost after dispatch or process crashes before acknowledgment | Durable latch plus bounded independent outcome readback; unknown remains unknown, no close replay or unlock |
| 5 | Writer/observer restart, stale generation, missing/malformed control or failed barrier read | Durable closure and fail-closed behavior; malformed fixture is introduced before its comparison interval, never normalized away |
| 6 | Deadline or credential expiry during observation | No further observation dispatch; storage stays closed; retained journal and separately gated recovery/reopen |
| 7 | Restore while temporary and original delayed executions still exist | Both generations' later local writes fenced through complete restored readback; no assumed propagation gap or provider drain |
| 8 | Scheduled maintenance, session/audit/authentication-failure and status quota paths | Every actual stored effect accounted for; required authenticated-check conflict explicitly refuses rather than claiming success |
| 9 | Service/queue/hint/alarm and included separate-store paths | Local storage/alarm closure and complete object census; unsupported old version, unknown object or unavailable independent reader refuses |
| 10 | Direct operator/schema/guard bypass; provider and reader bookkeeping effects | Deliberate bypass demonstrates trusted-operator limit; missing embargo or mutable/inaccessible included state fails qualification, never passes on matching counts |
| 11 | Mutate-and-revert or schema change scheduled between pages, including deliberately broken guard | Intact guard prevents it; broken enforcement is a failed case even if all three snapshots match |
| 12 | One predeclared reachable interruption/refusal sequence selected from timeout, partial output, malformed/truncated/unsupported results and unknown restore/cleanup | Closed refusal, partial/journal retention, no successful partial snapshot, replay, forced restore or automatic reopen; unreachable variants remain explicitly untested |

Each case may contain a fixed finite list of suboperations in its one run; the
packet must enumerate them all. An early refusal may consume fewer than three
captures. It cannot restart the case or spend a spare run automatically. A
deliberately broken barrier's successful mutation is evidence of a failed
mechanism, not permission to repair it during comparison or record a pass.
Several terminal refusal variants cannot execute after the first terminal
failure in one run. Before approval, select the exact reachable sequence for
case 12 and list its uncovered variants; the row is an obligation inventory,
not a claim that one run covers them all. Additional variants require an explicit
later reviewed allocation within the shared ceiling, with no automatic retries.

### Finite ledger and timing

The later packet must freeze smaller exact ordered counts inside these proposed
caps before dispatch. They do not relax a lower reader, provider or preservation
limit. All attempted calls, including failed calls, consume counters; no category
or run may borrow unused slots without a newly reviewed packet.

| Counter | Per reserved run maximum | Twelve-run reservation maximum |
| --- | --- | --- |
| All request attempts | 160 | 1,920 |
| Attempted complete reader captures | Three: baseline, preflight, restored; no replacement after failure | 36 inside shared 72 |
| Reader queries | 32/capture, 96/run, including discovery and empty terminal sentinels | 1,152 |
| Independent receipt reads | 20, including absence/reconciliation | 240 |
| Other metadata reads | Four | 48 |
| Required authenticated checks | Four predeclared exact routes | 48 |
| Mutation attempts excluding resource creates/deletes | 32; statement and effect limits below | 384 |
| Resource creates/deletes | At most two creates and two deletes, but at most one of each per exact resource across the whole campaign | Two creates and two deletes total for the one D1 and one writer resource, not per run |
| Outbound bytes | 64KiB/request, 4MiB aggregate; reader SQL remains at most 32KiB/query | 48MiB aggregate |
| Inbound decrypted HTTP wire bytes | 256KiB/response, 16MiB aggregate; at most 4MiB per capture | 192MiB aggregate |
| Private plan/evidence | 1MiB plan; 8MiB all retained artifacts including partials, receipts, journals and three snapshots | 96MiB; no hidden duplicate spool/copy |
| Elapsed time | 1,200 seconds from first operation through terminal evidence/eligible cleanup | 14,400 seconds sum of run windows; no work outside bound |

The request arithmetic is 96 reader, 20 receipt, 4 metadata, 4 authenticated,
32 mutation, 2 create and 2 delete attempts: 160 total. Creation/cleanup belongs only to
the allocated lifecycle boundaries. An early terminal run uses its existing
cleanup slots, not another run. The one synthetic writer resource's exact
retained/temporary version selections require the packet's explicit operations;
they do not authorize another writer resource or uncounted upload/deploy calls.

The 32 mutation slots are at most twelve pre-baseline fixed schema/seed calls,
four pre-baseline reset calls on later known-safe runs, twelve writer/fault
challenges, one close, one temporary installation/deployment, one qualification
admission-off and one latched retained-target restore. Every actual provider
call counts separately; a multi-call upload/deploy cannot be described as one
operation to fit. If the exact supported lifecycle cannot fit these caps,
preparation refuses. Count at most 256 attempted SQL statements/run, eight/call
and 2,048 affected-row events/run, including setup, denied challenges, trigger
fanout and resets. Freeze statements and bounded expected effects in the manifest;
an exceeded or unmeasurable required effect bound fails qualification. Resource
deletes have their separate two-slot campaign cap.

Retain the reader's stricter effective page size at most 256, 60-second request
limit and original codec ceilings even when the miniature fixture has lower
caps. Wire accounting includes headers, body and framing/trailers; no body-only
measurement or extra framing allowance. A deadline is the minimum of 60 seconds,
the remaining monotonic run window and any applicable freshness bound. Preflight
must be within 60 seconds of baseline observation, and restored observation
within 60 seconds of validation; observation and eligible cleanup fit the
twenty-minute preservation window. Long per-request timeouts cannot extend it.

Every injected operation and local fault consumes its declared challenge slot
even if no request is sent. There is no hidden polling, retry, fixture recreation
or unbounded cleanup allowance. Stop before dispatch if the positive remaining
query/request/byte/time budget cannot accommodate the next fixed operation.
Unknown mutation/restore/drain/ownership stops the remaining shared-resource runs.
Reuse/reset is permitted only at explicitly authorized, fully accounted known-safe
boundaries outside comparison. To seed guarded application tables between runs,
one of the four reset calls must be a separately authorized conditional operator
reopen with the next generation, with readback in the existing receipt allocation.
It is allowed only after the preceding run's successful exact restoration,
readback and required per-run cleanup. The shared D1/writer resource retirement
may be deferred to the campaign end only by that exact action decision; temporary
artifact cleanup and private-evidence retention obligations remain explicit.
Without approved safe reuse and those counted calls/receipts, later runs are
unavailable. Reopen/reset never follows failure, unknown closure/settlement or
expiry automatically. It is never an interval repair or resource reset to evade
unknown outcomes. If any all-store case or freshness ordering cannot
fit, record it unavailable and return for a revised reviewed packet before action.
This proposal supplies no production plan-discovery adapter or new executor.

### Receipts, refusal and cleanup

Retain independent, run/identity/source/generation-bound evidence, not assertions
the same writer returns about itself:

1. Exact resource creation/ownership acknowledgment, fixed fixture manifest and
   independent seeded-state observations; reviewed custody and grant provenance.
2. Entry-point closure and admitted-work outcomes; each store's close latch,
   acknowledgment and separate authoritative guard/control readback; operator
   embargo/capability inventory and its audit evidence. A reader can observe
   closed rows but cannot by itself attest that every operator stayed embargoed.
3. Ordered snapshot manifests and private completeness/equality results; negative
   writer outcomes read independently from the authority. Matching snapshots do
   not replace fencing evidence or detect every mutate-and-revert interval.
4. Qualification admission shutdown, one nonforced exact retained-target restore
   latch/acknowledgment and independent deployment/configuration/all-state
   readbacks; separately evidenced ordinary authenticated checks.
5. Exact authorized cleanup latches/acknowledgments, independent absence checks
   and private artifact retention/disposal dispositions. Missing or ambiguous
   results remain `cleanup_unconfirmed`; no guessed identity or blind replay.

The proposed twenty receipt-read slots allocate at most two to create/identity,
two to closure/settlement, four to challenged mutation/history/sequence/all-store
outcomes, two to qualification-admission shutdown, four to restored target/
configuration/lifecycle/generation, two to custody/embargo or fault reconciliation
and four to terminal settlement/resource absence. An endpoint may supply several
declared facts in one read only if its real supported response does so. No
fictional aggregate endpoint, concealed pagination or second uncounted observer
is assumed. If exact authoritative independent observations need more, revise
the reviewed allocation before dispatch. Operator custody needs its own evidence;
reading the D1 row cannot attest to every operator's conduct.

Store full snapshots and journals only in the separately qualified private
custody location. Public evidence contains reviewed provenance references,
bounded counts and closed outcomes, without cells, synthetic sensitive markers,
private digests, exact account/resource identities or credentials. Source review
must check stdout/stderr, exception and trace/support paths with synthetic markers.
The publisher-only disposal exception cannot authorize this database campaign.
Not-found is an observed response, not verified erasure from backups, provider
history, telemetry or filesystem recovery media.

On expiry, cancellation, loss of authority, schema/value mismatch, barrier loss,
unaccounted operation or budget exhaustion, stop new observation/admission,
retain partial evidence and keep closure latched. Necessary restoration/cleanup
continues only under its separately authorized, bounded lifecycle; expiry is
neither an instruction to abandon owned resources nor new mutation permission.
If that lifecycle cannot obtain its required evidence, report the exact
unconfirmed disposition and preserve the journal. Never infer successful close,
restoration, pause or absence from a missing acknowledgment.

## Concrete remaining owner decisions and action gates

Planning approval does not select the following choices:

| Decision / owning scope | Concrete decision still required before reliance |
| --- | --- |
| Prospective schema baseline / preservation and migration authority | Accept the actual maintenance-control/guard schema, coverage and maintenance outage as a new baseline, with migration/recovery ownership and preservation tests. Installation itself needs a separate exact production action packet. |
| Retained artifact / restoration authority | Choose whether the historical module can remain usable with a separately accepted new schema, or identify a new future artifact/configuration/lifecycle because included-store closure or checks need code/binding changes. Prove rollback compatibility; preserve the historical NO-GO record either way. |
| Included stores / complete-state authority | Accept an exact prospective census and a qualified barrier/reader for every included store. If current bounds/resources cannot cover required Durable Object/provider state, approve a scoped plan change first; no silent exclusion or substitute equality claim is proposed. |
| Ordinary authenticated check / restoration-check authority | Name the exact route and successful semantics under closure. If mandatory writes conflict, decide a narrowly described contract amendment and future artifact; guard-rejected or after-reopen checks cannot satisfy the current protocol. |
| Isolated qualification action / campaign and custody authority | Approve exact resources, operations, source/artifact identities, numeric request/write/byte/time limits, grants, private custody, retention, cleanup and recovery owner for the fixed cases inside the shared ceiling. No cloud experiment is authorized by this document. |
| Later production capture/run and reopening / materialization and lifecycle authority | Separately authorize actual private access, migration/install if any, new baseline, temporary attempt, restoration, cleanup and reopen after the mechanism is accepted, implemented and independently qualified. No present token or prior unrelated decision supplies these scopes. |

The next action packet should present these decisions in that order with exact
reviewable inputs, refusing dispatch where an input remains unavailable. Prefer
the smallest conventional local guard/outage implementation that can meet them;
do not introduce cross-store coordination or another service without a concrete
unmet requirement and separate architecture review.

## Handoff status

This source-only packet leaves the candidate **Proposed, unimplemented and
unqualified**. Fresh independent High review must assess the control/guard
semantics, full writer/store census, restoration and stale-work reasoning,
operator limitations, fault budgets and owner wording before handoff. Formatting
and reference validation prove only documentation quality. They do not qualify a
barrier, account operation, snapshot reader or exact retained artifact.

#0163's writer-barrier dependency remains unresolved until a separately accepted,
implemented and independently qualified mechanism and complete authorized packet
exist. The historical exact-original attempt remains NO-GO and all materialization,
preservation, restoration and deployment readiness gates remain false.
## Reviewed planning handoff and explicit successors

Fresh independent High review passed this proposed source-only design, writer/
store coverage, concurrency/restoration reasoning, finite ledger and remaining
owner gates with no actionable findings. Mechanical checks found 26 resolving
local targets, strict UTF-8 without BOM, LF endings and no trailing whitespace.
These checks are documentation/source evidence; no guards or experiments ran.

Follow-up #0181 owns the exact prospective contract decision packet after this
planning handoff. The separate #0180 investigation owns lossless REAL extraction
feasibility; the completed reader continues to refuse REAL. #0182 is an explicit
Backlog gate for actual independently reviewed all-store qualification, pending
accepted contracts, source, reader coverage and exact campaign/action preparation.
#0163 now depends explicitly on #0182 as well as its other prerequisites. Neither
this document's completion nor a later contract choice can substitute for that
actual qualification. Completed #0170 and #0171 remain unchanged.
