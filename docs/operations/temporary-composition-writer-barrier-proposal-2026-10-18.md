# Temporary composition: all-writer barrier decision proposal

Date: 2026-10-18. Ticket #0171. Status: **Prospective baseline planning direction
accepted; barrier mechanism Proposed, unimplemented and unqualified; exact
retained-original attempt remains NO-GO**. This is a source-based design and
scoped owner-decision record, not a qualified barrier or action packet.
No private artifact, database, credential, account configuration or native state
was read. No provider/account request or mutation was made.

## Outcome and authority

The reviewed public sources do not establish an all-writer barrier that remains
effective through restoration of the exact retained original and its readback.
There is no executable pause/drain instruction to recommend for that original.
Keep the complete baseline unavailable and materialization, preservation,
restoration and deployment readiness false. This is an evidence/implementation
gap; it is not a finding that Cloudflare cannot satisfy the requirement.

Preserve the original and stop the historical attempt. Terry accepted design
and isolated qualification planning for the prospective maintenance baseline
below on 2026-10-18. Preinstalled write guards and an explicit maintenance outage
are the selected planning direction. The mechanism remains Proposed and must
be independently qualified before any separately authorized future attempt.
A changed artifact or schema cannot be relabeled as the historical original.

Controlling sources remain:

- Canonical [documentation authority](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md),
  accepted [persistence/scheduler contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/worker-persistence-scheduler-contract.md),
  [required conformance contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/testing/fail-polite-worker-database-conformance.md)
  and [ADR0051](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0051-trust-private-storage-runtime-with-guarded-writes.md).
  Permanent suppression, append-only history, ordering, admission, stale-worker
  fencing and recovery remain mandatory. No D1/Durable Object transaction is assumed.
- The [preservation contract](fixed-origin-preservation-2026-10-17.md#paused-gates-and-consistent-full-data)
  owns complete typed relational/schema/row-identity equality and unchanged
  production gate revisions. The [restoration protocol](fixed-origin-restoration-2026-10-17.md#return-to-design-handoff-finite-preservation-protocol)
  owns exact retained-version/configuration/resource continuity and nonforced restore.
- The [selected proof direction](../design/temporary-composition-preservation-proof-2026-10-18.md)
  is private full snapshots processed only by bounded code. Its provider-local
  witness alternative is unselected. The [reader procedure](private-full-snapshot-reader-2026-10-18.md#required-writer-barrier)
  and [materialization handoff](temporary-composition-materialization-handoff-2026-10-18.md)
  retain their independent qualification, access, custody and action gates.

The existing public restoration pins identify the historical capture/module;
they do not expose its private source or prove current availability. The
[sanitized historical receipt](../evidence/temporary-composition-target-metadata-2026-10-18.json)
does not establish current writers, configuration or barrier state. Current
checkout behavior below is evidence of required coverage, never a substitute
for the exact captured artifact's independently reviewed census.

## Writer inventory and evidence boundary

The later private census must bind every row to the exact original and temporary
artifacts, version/configuration, resource, identity, entry point, stored effects,
admitted-work settlement and enforcement evidence. Unknown and apparently unused
paths stay unresolved. Absence from an example manifest is not deployed absence.

| Writer family | Public source evidence / required coverage | Required closure |
| --- | --- | --- |
| Authenticated ordinary reads | [`browser_sessions.ts`](../../src/browser_sessions.ts) `authenticateBrowser` attempts session-activity UPDATE; [`plugin_codes.ts`](../../src/plugin_codes.ts) detail GET audits; [`submission_status.ts`](../../src/submission_status.ts) reads consume status buckets/events | Cover conditional, best-effort and failed-authentication side effects; a GET label does not mean read-only |
| Intake, installation, admin and credential operations | [`worker.ts`](../../src/worker.ts), [`browser_sessions.ts`](../../src/browser_sessions.ts), [`installations.ts`](../../src/installations.ts), [`plugin_codes.ts`](../../src/plugin_codes.ts) | Close every mutation route, callback, credential/session rotation, audit, quota and rate-limit path, including already admitted requests |
| Provider-read and publish/album effects | [`group_discovery.ts`](../../src/group_discovery.ts), [`flickr_reads.ts`](../../src/flickr_reads.ts), [`flickr_rate.ts`](../../src/flickr_rate.ts), [`photo_memberships.ts`](../../src/photo_memberships.ts), [`upload_authorization.ts`](../../src/upload_authorization.ts), [`album_materialization_worker.ts`](../../src/album_materialization_worker.ts), [`album_attachment_worker.ts`](../../src/album_attachment_worker.ts), [`album_title_worker.ts`](../../src/album_title_worker.ts) and their stores | Cover cache/refresh staging, read-rate reservations, grant-rejection state, upload/binding evidence, album obligations, repair, lease/result/history and delayed network settlement; current exported adapters do not prove deployed callers |
| Schedules, maintenance and refresh | [`worker.ts`](../../src/worker.ts) `scheduled` runs status/authentication/key/credential maintenance before its dispatch-capability check; group refresh is separately gated | Close invocation admission and account for work already running; dispatch disabled alone is insufficient |
| Dispatch, recovery, delayed hints and alarms | [`dispatch_worker.ts`](../../src/dispatch_worker.ts) `PartitionWorker.fetch`, `consume`, `arm`, `alarm`: local partition/alarm writes, `waitUntil`, D1 dispatch/recovery | Fence both D1 and any included Durable Object stored effects, and settle admitted external work before baseline; paused production gates do not imply no recovery writes |
| Queue/service/version entry points | Exact deployment may expose service callers, queue consumers, preview/version URLs or another binding holder; [`wrangler.example.jsonc`](../../wrangler.example.jsonc) is only an example | Independently establish the effective deployed census; no queue export found in current source is not proof of no deployed consumer |
| Migrations, maintenance tools and direct operators | [`migrations`](../../migrations), [`controlled_trial_pause.py`](../../scripts/controlled_trial_pause.py), provider SQL/API/dashboard and deployment identities | Suspend schema/repair/backup-restore/import tasks and direct writes; inventory CI, human, automation and emergency identities, not just application routes |
| Stale or restarted executions | Every async callback, pending D1 transaction, old Worker version, retry/delivery and Durable Object restart | Enforcement must reject at storage mutation/transaction boundary, or a supported mechanism must acknowledge their complete drain; an earlier flag read is insufficient |
| Reader/provider bookkeeping | Actual schema, SQLite sequences/migrations and provider bookkeeping remain in the full reader census | Qualify whether capture or provider activity changes any included state; inaccessible, unguardable or unsupported state refuses rather than becoming an exclusion |

The two paused `flickr_write_gates` rows protect Flickr admission within their
accepted scope. They are not an all-storage write switch. The qualification
admission row is also separate and must not replace either production gate.
Any external call already dispatched must reach its required durable safety
settlement before the baseline; freezing its result/recovery transaction cannot
erase a pending safety obligation. An unsettled or ambiguous call refuses capture.

## Candidate mechanisms assessed

Official provider sources checked on 2026-10-18 establish the following limited
facts. They provide no account observation or qualified complete barrier:

| Mechanism | Supported fact and result for this attempt |
| --- | --- |
| D1 `batch()` | [D1 binding documentation](https://developers.cloudflare.com/d1/worker-api/d1-database/) describes transactional batches with rollback on failure. This can support a storage-local atomic gate; it does not freeze other requests between reader pages or fence code that omits the gate. |
| D1 Sessions/bookmarks | [Read replication documentation](https://developers.cloudflare.com/d1/best-practices/read-replication/) supplies sequential consistency and primary/replica semantics. It does not establish no intervening write or one snapshot across pages. |
| Worker rollback | [Rollback documentation](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/) describes selecting an older version and leaving connected resources unchanged, with compatibility restrictions. It supplies no complete admitted-invocation drain acknowledgment. Resource continuity is promising for a preexisting storage guard, not proof of its behavior or rollback eligibility. |
| Durable Object transaction | [Storage documentation](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/) describes an object-local transaction. It supplies neither a D1 transaction nor an atomic freeze of every object and old invocation. |
| Route/capability/schedule shutdown | Can reduce admissions only within the affected path. No reviewed source establishes complete propagation, old-version drain or revocation of already held D1 bindings. Installing a wrapper or changing a route also changes configuration that the exact-restoration contract compares. |
| Read-only reader / operator promise | Limits what that reader requests. It does not revoke other binding holders or provider operators; a token expiry cannot revoke an already admitted transaction or a Worker binding. |

Two or three equal sweeps, a quiet log, an elapsed delay, stable counts and a
mutate-and-revert interval are compatible. Equality proves only the compared
observations after completeness is established; it never proves exclusion.
No undocumented Cloudflare account freeze, universal write lock, global drain,
permission name or rollback fence is assumed here.

## Required interval and refusal semantics

For any later accepted mechanism, all of these conditions must hold together:

1. Close new writer admission, independently acknowledge closure, then account
   for every admitted operation. Either drain it to its required durable result
   or prove a storage fence that prevents any later mutation. Resolve external
   dispatch/recovery obligations before taking the baseline.
2. Establish a durable closed barrier generation for every included store and
   privately bind exact identities. Observe closure independently. Baseline
   starts only after all stores are closed; no simultaneous cross-store
   transaction is implied. No schema/configuration/guard installation occurs
   inside the comparison interval.
3. Keep the same generation and enforcement continuously active through schema
   discovery, every baseline page, temporary installation/run, fresh preflight,
   exact retained-original restoration, authenticated ordinary verification and
   every restored-state page. The production gate rows/revisions remain unchanged.
4. Reject missing/unreadable authority, generation mismatch, stale execution,
   unknown writer, incomplete drain, unsupported schema/value or exhausted budget.
   The current reader refuses every SQL REAL cell; this proposal does not relax
   its completeness/type bounds or make production capture executable.
5. Expiry ends admission to the attempt and new observation work. It must not
   reopen storage writes. Crash/restart retains closure, partial evidence and
   unknown operation outcomes; no timeout unlock, forced restore or blind replay.
   Follow the separately authorized latched restoration/cleanup protocol and
   retain an unconfirmed disposition if its evidence cannot be obtained.
6. Reopen only by a separately authorized operator action after successful
   restoration/readback and required cleanup, outside the equality interval.
   Reopening is a new durable generation with an independent receipt. A failed
   attempt does not authorize deleting partial evidence or rewriting the baseline.

The exact restored artifact must support the required ordinary authenticated
check while preserving its required audit/session semantics and the equality
claim. A guard-rejected audit write is not a successful conformance check. If
that route necessarily writes, full freeze and successful verification conflict.
Keep the gate false and obtain a scoped owner decision at the owning protocol;
do not omit its rows, suppress required audit, use a newer route or run the
check after reopening and describe it as verification under the freeze.
Current [`worker.ts`](../../src/worker.ts) installation `current` handling calls
[`installations.ts`](../../src/installations.ts) `jsonCurrent` after lookup,
which suggests a candidate without the browser/status side effects above. That
does not establish its presence, exact behavior or suitability in the retained
original, nor permission to invoke it. Qualify the exact required route; do not
declare every authenticated GET either safe or necessarily mutating.

## Concrete alternative: prospective maintenance baseline

**Planning direction accepted; mechanism Proposed, unimplemented and
unqualified.** Separate barrier preparation from the historical attempt.
Design and plan independent qualification of persistent storage guards using
isolated synthetic fixtures. Executing a cloud experiment requires a separate
bounded action decision. Any production migration/install and new baseline
also require their own explicit owner-approved action packet. Nothing in this
document authorizes those actions.

The conventional candidate is a preinstalled D1 maintenance-control row with a
monotonic generation and closed state, plus guards enforcing closure for every
ordinary table mutation in the same database transaction. A fail-closed SQL
trigger on each application table is a candidate enforcement point for old code
that does not know the control row; the [D1 SQL reference](https://developers.cloudflare.com/d1/sql-api/sql-statements/)
documents trigger-related behavior but does not qualify this proposed guard.
Actual D1 statement, UPSERT/REPLACE, cascade, batch-abort and restart behavior
must be proved. Missing/malformed control state refuses writes. Existing
permanent-block/history guards remain intact and are never replaced or bypassed.

The control row's close acknowledgment is the D1 linearization point to prove:
transactions committing before it finish before baseline; later ordinary
mutations must fail atomically even from a stale original invocation. A
preflight SELECT followed by an awaited unguarded mutation cannot implement
this rule. No request-local boolean, separate Durable Object check or reusable
caller assertion can replace the storage-local guard.

Closing the control row is an authorized pre-baseline mutation. Capture its
closed value/generation and the guard schema as part of the new full baseline;
neither changes again until the equality interval ends. The narrowly reviewed
maintenance operator alone owns close/reopen actions. Ordinary code must not
update/delete the control row or alter guard/schema definitions. DDL, imports,
Time Travel, provider-admin changes and guard removal remain outside SQL row
trigger protection; an independently recorded exclusive operator maintenance
embargo and audited capability custody are required under the private trusted
runtime model. This does not claim a hostile provider administrator is fenced.
Unknown identities or inability to enforce the embargo make this alternative
unavailable; do not invent a read-only binding or limited SQL grant.

D1 guards do not cover Durable Object storage/alarm metadata, another database
or provider-maintained rows. Each included store needs independently qualified
closure that survives restoration; application-controlled gates must be checked
atomically with each local mutation, and every old version must honor them or
be fenced externally. If the exact original lacks that support and no supported
complete drain exists, this alternative cannot preserve that original. Do not
drop advisory Durable Object state or bookkeeping silently to obtain equality.

If all required stores and ordinary checks can be protected while retaining
the historical module/configuration bytes, a separately approved **new schema
baseline** could preserve that module. That possibility is unproved. If any
necessary barrier/check requires code, binding or lifecycle changes, identify
a **new future artifact** and obtain a separate baseline/acceptance decision.
Keep the historical original and its restoration packet intact. Rebuilding,
reuploading or adding a wrapper cannot create an exact-restoration pass for it.
If rollback compatibility or the authenticated-check conflict remains unresolved,
stop; no speculative schema machinery earns production readiness.

This alternative accepts a maintenance outage and explicit recovery ownership.
It adds guard coverage/migration review and synthetic fault qualification;
it does not propose AWS, weaken full equality or substitute a witness trust model.

## Finite qualification plan

This is a Proposed design campaign inside, not additional to, the reader's
[24-run ceiling](private-full-snapshot-reader-2026-10-18.md#finite-barrier-and-fault-campaign-proposal).
Reserve at most twelve of those isolated runs for the cases below, one case
per run, with at most three complete reader captures per run. No production
resource, private original or account operation is authorized. Source-only
synthetic tests precede a separately reviewed hosted action packet.

| Run | Fault / evidence obligation |
| --- | --- |
| 1 | Happy path: close acknowledged; full baseline/preflight/restored equality and same barrier generation after exact retained synthetic-version rollback |
| 2 | Writer already admitted before close: complete safe settlement before baseline, or atomic rejection after close; no partial batch or hidden later commit |
| 3 | Delayed callback/stale pre-close flag: mutation after close fails at storage; repeat through guarded batch, cascade and REPLACE paths |
| 4 | Process crash after close dispatch but before acknowledgment: closure outcome remains unknown until bounded independent readback; no retry/reopen |
| 5 | Writer and observer restart: durable closure survives; stale generation and missing authority refuse, including unavailable barrier reads |
| 6 | Deadline/credential expiry: observer stops; closed writes stay closed; a later operator reopen needs separate authority |
| 7 | Restore while delayed temporary/original executions remain: both versions remain fenced through restored full readback, with no propagation-gap assumption |
| 8 | Schedule, maintenance, audit/session, authentication-failure and status quota paths: every stored effect rejected atomically or drained; authenticated success incompatibility remains explicit |
| 9 | Service/queue/hint/alarm and separate-store paths: local writes and delayed alarms cannot escape common interval; unknown object or writer refuses |
| 10 | Direct operator/schema/guard bypass and provider bookkeeping: expose limits; missing embargo or uncovered write must refuse qualification, never produce a pass |
| 11 | Mutate-and-revert and schema change between pages: barrier must prevent them; deliberately broken guard is detected as a failed campaign even if snapshots match |
| 12 | Timeout, interrupted private output, malformed/unsupported value and unknown restore/cleanup: preserve journals, return closed failure, no replay or automatic unlock |

Before any hosted run, freeze the exact synthetic fixture and writer/store
census, guarded statements, original/temporary bytes, provider versions, owned
resource identities, independent receipts and finite request/page/byte/write/time
ledger. Every injected operation and readback counts. Retain the reader's
per-query, aggregate and twenty-minute bounds, plus the preservation contract's
freshness/order bounds. If all cases or required observations cannot fit those
bounds, a new reviewed packet must change them before dispatch; there is no
automatic retry, polling, reset, extra run or budget extension.

Only synthetic markers enter the isolated fixtures. Full snapshots, journals,
private manifests and failure artifacts stay in the separately qualified private
custody location. Public evidence contains closed outcomes and reviewed
provenance references, never cells, private digests, exact resource identifiers
or credentials. Cleanup/absence and sensitive artifact retention retain the
reader procedure's independent unresolved gates; a not-found response is not
verified erasure. These cases do not execute or extend #0172's separate reader
qualification packet.

## Exact owner decision and handoff

On 2026-10-18, Terry selected **"Approve prospective baseline planning
(Recommended)"** in the explicit owner question. The accepted scope is design
and isolated qualification planning for a prospective maintenance baseline
with preinstalled write guards and an explicit maintenance outage.

- Preserve the historical artifact, restoration packet and complete-state
  equality requirement. The historical exact-original attempt remains NO-GO.
- Accept the planning direction only. The candidate mechanism is still
  Proposed, unimplemented and unqualified; no barrier or readiness gate passes.
- Any later schema baseline, new artifact or authenticated-check amendment
  requires separate acceptance at its owning contract before work relies on it.
- Production migration, private capture/access, deployment, cleanup and cloud
  experiments are outside this decision. Each needs its separate exact action
  decision; the finite campaign above is a planning bound, not dispatch authority.

If the prospective baseline requires altered authenticated-check semantics,
enumerate that separate decision explicitly. Do not move to an alternative
database or redesign safety authority merely because the original lacks a switch.

### One bounded next offline planning follow-up

Follow-up #0179 is P3 and Ready for Work for a source-only prospective barrier design and
qualification-plan packet. Its inputs are this accepted planning direction,
the public writer inventory above, the controlling preservation/restoration
contracts, the reader's finite bounds and the separate #0172 qualification
packet. Use public source and synthetic descriptions only; do not read private
artifacts, access an account, implement guards, change schema or run a hosted
experiment.

The packet must contain:

- A proposed control-row/guard design and coverage matrix for D1, included
  Durable Object state, direct operators and provider bookkeeping, including
  close/drain, stale executions, restore and fail-closed recovery limits.
- A synthetic fixture and fault-case specification within the existing
  twelve-case allocation and 24-run ceiling, with explicit finite budgets and
  independent receipts; no runs are executed by this follow-up.
- An explicit list of any required schema/artifact/authenticated-check owner
  decisions and a proposed separately authorized action packet for later
  qualification, including refusal and cleanup dispositions.

Handoff requires fresh independent High review of the design and plan,
resolved material findings and a clear list of remaining owner/action gates.
It must leave implementation and qualification false. Keep #0163's writer-barrier
dependency unresolved until a mechanism is separately accepted, implemented and
independently qualified; planning acceptance alone cannot satisfy it.

Independent High review must assess census completeness, storage/restore
reasoning, operator limitations, fault bounds and owner wording before handoff.
Documentation validation covers references/format/source claims only. No
barrier implementation, provider qualification or production pass follows from
reviewing this proposal. #0163 remains dependent on an accepted, implemented,
independently qualified mechanism and its separately authorized complete packet.

## Independent review record

The initial independent High review found no material issue in the public writer
census, authority, all-store/restore limitations, twelve-case campaign or exact
then-unselected owner choices. The author and reviewer checked formatting and local
references; the reviewer checked 29 local links and relevant official provider
references. This is a documentation/source review, not an implemented or hosted
barrier qualification. That review predates the owner-decision record above;
the revised acceptance wording requires its own fresh independent review before
handoff. Planning direction acceptance leaves the mechanism Proposed,
unimplemented and unqualified and the historical target NO-GO.
Fresh independent High review of the accepted planning record passed after the
owner decision, with no material findings. It checked the planning-only scope,
historical NO-GO, complete-state equality, unresolved #0163 dependency and bounded
follow-up. Formatting and 29 local link targets passed. Follow-up #0179 now owns
the next offline design/qualification plan; creating it grants no implementation
or experiment authority. No runtime or hosted test was performed for this record.
