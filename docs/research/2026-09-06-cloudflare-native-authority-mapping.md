# Cloudflare native authority mapping

Date: 2026-09-06

Status: Completed research and proposed mapping for bounded provider proofs.
Production storage selection and executable conformance remain outstanding.

Architecture baseline: `FlickrGroupAddr/architecture-design` commit
`a02d02558fe0a384f27c6b9c5aee59f340f2fc4a`. [ADR 0050][adr50] authorizes
native evaluation. The [architecture authority policy][authority] and accepted
contracts control semantics; this research supplies evidence and a proof plan.
Private board coordination: implementation #0003, parent #0002.

## Recommendation for the proofs

Evaluate one D1 database as the authority for the private deployment's relational
state. Keep each admission, dispatch, result, authentication, and audit commit
inside that database. Evaluate Durable Objects as optional partition wakeup
coordinators whose persisted alarms and hints can be rebuilt from D1. D1 remains
the authority for due times, lease generations, dispatch permission, and recovery.

This is the leading hypothesis because the accepted transactions connect more
than one group partition and more than one category of state. It preserves those
boundaries without a distributed commit protocol. A SQLite-backed aggregate
Durable Object remains a serious alternative: its transaction callback permits
ordinary conditional control flow, but all facts needed by that transaction must
be inside the same object.

Three questions deserve early proof:

1. **Runtime protection:** can application identities insert safety evidence
   while being unable to change or erase it, including through schema changes?
2. **Transaction composition:** can bounded D1 statements express every guard
   and dependent write with whole-operation rollback?
3. **Hosted time:** can the actual Cloudflare runtime enforce the required
   monotonic preflight window, and can the database meet accepted timestamp
   semantics?

Run small protection and time probes before investing in a large adapter. A
transaction demonstration alone cannot settle either question. No resource was
provisioned, no provider mutation was performed, and no local or hosted
conformance pass is claimed by this research. The immutable Flickr-secret
version decision remains with implementation #0009.

## Provider evidence

The following primary sources were checked on 2026-09-06. Implications for the
FGA hosted components are analysis, rather than provider guarantees.

| Source | Documented capability | Implication for this evaluation |
| --- | --- | --- |
| [D1 database API][d1-api] | `batch()` executes prepared statements transactionally and rolls back the sequence on a statement error; ordinary calls use auto-commit. | Use one batch per logical commit. Returning from one call and submitting a second creates two commits. |
| [D1 foreign keys][d1-fk] | Foreign keys are enforced; deferral lasts within a transaction. Cascades still execute during deferral. | Prove relational integrity and retention under the actual migrations, including parent deletion. |
| [D1 replication][d1-replication] | Queries without the Sessions API use the primary. Sessions provide sequential consistency; replicas are asynchronous. | Start with primary reads. A client's old bookmark cannot prove that another request has not revoked its credential. |
| [D1 limits][d1-limits] | A database processes queries serially. Paid databases have a non-increasable 10 GB limit; queries have 100 bound parameters and a 100 KB statement limit. | Measure the complete batch and retained-history growth. Serialization does not make separate API calls one transaction. |
| [D1 binding types][d1-types] | SQLite integers are signed 64-bit; the JavaScript binding does not support BigInt values and ordinary numbers have a smaller exact range. | Keep ordinal/revision arithmetic in SQL and prove exact transport, such as decimal text, across the full required range. |
| [Durable Object SQLite storage][do-storage] | Storage is transactional, strongly consistent, and private to an object. `transactionSync()` rolls back when its callback throws. | An aggregate can contain several groups. Object-local transactions do not encompass D1 or another object. |
| [Durable Object alarms][do-alarms] | One alarm is scheduled per object; execution is at least once, with up to six automatic retries after failure. | An alarm can be duplicated or exhaust retries. The indexed D1 sweep remains the recovery path. |
| [Worker Cron Triggers][cron] | `* * * * *` configures a minutely invocation. | Configure the accepted sweep cadence and measure delivery/overdue work; a cron expression alone is no availability proof. |
| [D1 SQL surface][d1-sql], [SQLite omitted features][sqlite-omitted], [D1 API permission note][d1-permissions] | SQLite has no SQL `GRANT`/`REVOKE`. D1 documents SQL bindings, configurable checks, and HTTP read/edit permissions. | The reviewed documentation supplies no table-scoped insert-only runtime grant. HTTP read/edit separation does not establish that property. |
| [Worker service bindings][service-bindings] | One Worker can call another privately by binding, including methods. | A separate storage Worker can restrict exposed operations, but its own storage capability and code become part of the safety boundary. |
| [D1 Time Travel][d1-restore], [D1 export][d1-export] | Time Travel restores in place and cancels in-flight queries. Recovery windows are 30 days on Paid and seven on Free. SQL export is supported and blocks other database requests while running. | Prove quiescence and recovery in a disposable deployment. Historical restoration can remove later safety evidence. |
| [Worker timers][worker-timers], [Worker web standards][worker-standards] | Deployed timers advance after I/O; local timers advance continuously. Cloudflare documents `performance.now()` as equal to `Date.now()`. | A local monotonic-clock test cannot establish the hosted freshness property. A database fallback does not change the Worker timer. |
| [SQLite date functions][sqlite-time] | Current `subsec` output has millisecond resolution. | Audit timestamps require microsecond precision in the accepted contract. Verify the deployed engine and distinguish formatting precision from clock resolution. |

## Durable fact owners

This table assigns logical authority in the D1 hypothesis. It is an inventory
of fact families, not another schema or wire contract. Linked architecture
documents retain their exact fields, transitions, and retention rules.

| Fact family and controlling contract | Proposed authority | Atomicity and lifetime boundary |
| --- | --- | --- |
| FGA principal, canonical Google identity, principal session-set revision; [browser sessions][sessions] | D1 | Identity mapping, session creation/rotation/revocation, revision, and successful audit evidence commit together. |
| Login/reauthentication one-use transactions, session verifiers, CSRF and expiry/revocation state; [browser sessions][sessions] | D1 | Transaction consumption and resulting session changes share one commit. Expiry is enforced at request time, independently of cleanup. |
| Installation identity, credential-version digests, current/pending pointers and revisions; [installation lifecycle][installations] | D1 | Issue/rotate/revoke and their audit/lifecycle events are atomic. Protected mutations recheck the exact presented version in their own transaction. |
| OAuth transaction metadata, current link revision, exact active secret reference, disconnect/cleanup progress; [OAuth lifecycle][oauth] | D1 | D1 alone activates or removes Flickr authority. Secret creation/deletion remains an explicitly separate external step. |
| Flickr credential values and other managed secrets; [OAuth lifecycle][oauth], [ADR 0050][adr50] | FGA managed secret store, provider unresolved | Store immutable versioned material outside D1 and Durable Object application storage. Database references and secret values have different authorities. |
| Upload authorization association, common photo bindings, verified-owner/link revisions, proof and photographer-reconciliation provenance; [plug-in/service contract][plugin] | D1 | Binding and provenance commit conditionally; the admission transaction checks the same binding/revisions. Image bytes and local recovery records stay outside hosted relational storage. |
| Every exact photo/group intent, partition identity, FIFO counter/ordinal, active-head membership and state; [worker persistence][worker] | D1 | All groups in one client handoff, including related binding updates and events, share one commit. Natural pair identity is deployment-wide. |
| Exact due times, wake revisions, claims, lease IDs/generations/deadlines, attempt ownership; [worker persistence][worker] | D1 | Conditional claims and every later transition use the current database fence and database clock. |
| Membership/preflight evidence, immutable dispatch markers/counts, results and zero-byte classifications; [worker persistence][worker] | D1 | A committed marker precedes transport handoff. Result, terminal state, block, due projection, and events commit together. |
| Permanent exact-pair suppression and its first evidence; [fail-polite conformance][fail-polite] | D1 | Insert-only runtime authority is a required unsatisfied gate. Disconnect, retention, restoration, or later moderation changes cannot remove protection. |
| Deployment and linked-user write gates, link revisions, gate events; [worker persistence][worker], [OAuth lifecycle][oauth] | D1 | Marker and result transactions check/update these facts locally. A copied gate in a Durable Object cannot authorize dispatch. |
| Shared Flickr operation-capacity reservations and release/expiry evidence; [worker persistence][worker] | D1 | Reserve the membership GET, moderation GET, and possible POST together. Never wait for capacity between moderation preflight and add. |
| Shared authentication admission counters and OAuth live-transaction cap; [administration][admin] | D1 limiter relations, subject to the admission-order review below | Source/global checks use one atomic authority before token validation and creation of application authentication records. The live-state cap is checked with OAuth transaction creation. No per-process counters. |
| Validated JWKS cache, freshness metadata, deployment-wide refresh ownership; [administration][admin] | D1 for shared cache/control | Publish only a complete validated key set. Rebuildable process caches retain the accepted freshness bounds; Google remains the signing-key source. |
| Group-refresh ownership/admission state, staging rows, last-good snapshot and current revision; [snapshots][snapshots] | D1 | Stage across bounded page reads, then atomically replace current rows/revision and finish the job. A failed or superseded job cannot publish. |
| Fresh photo-membership paging rows and observation revision; [snapshots][snapshots] | D1 | Replace only after complete external validation. These UI observations never replace attempt-scoped worker preflight. |
| Album bindings, immutable remote association, first-photo selection, attachment obligations, write/reconciliation evidence; [album publication][albums] | D1 | Binding/obligation/event commits stay together. Flickr album writes and Lightroom catalog acknowledgements remain separate outcomes. |
| Conditional future replacement operations, dispatch evidence, per-photo replacement blocks; [ADR 0023][replacement] | D1 if later authorized | Map the accepted conditional safeguards without implementing replacement or treating it as approved product scope. Backup image bundles remain under their separate local-storage contract. |
| Administrative, installation, intent, attempt and gate event history; [administration][admin], [worker persistence][worker] | D1 | Successful mutations and required events share a commit. Audit collection reads retain their specific append-before-response rule. Logs are supplementary evidence. |
| Durable Object alarm time, last hint/revision, optional coalescing state | The exact coordinator object's SQLite storage | These facts only request a future D1 check. Loss, rollback, duplication, or object replacement cannot lose accepted work or grant a lease. |
| Accepted policy, route allowlists, fixed bounds, deployment configuration and migration source | Versioned deployment artifacts under architecture authority | Runtime state never rewrites an accepted policy. Exact deployed revisions belong in every provider proof record. |
| Backup/export artifacts and restore provenance | Operator-controlled backup destination, selection pending #0007 | Copies preserve D1 history; they become live authority only through the controlled recovery procedure. No second runtime safety ledger is inferred. |

The limiter placement needs a focused authentication design review before those
mutations are built: the administrative contract orders admission before FGA
database insertion. The proposed reading permits atomic limiter bookkeeping
before application authentication records; it does not permit creating login,
OAuth, or session records before admission. If separate limiter storage is
required, document its reservation/cap partial failures before splitting it from
D1. Implementation #0015 owns that clarification; it is independent of the
installation-read slice.

## Transaction boundaries to prove

All rows below denote one D1 transaction in the leading hypothesis. No transaction
stays open during secret retrieval or a Flickr request. A pre-transaction read
can gather inputs; it cannot replace the transaction's authorization predicates.

| Commit | Facts that must succeed or fail together | Concurrency and response-loss rule |
| --- | --- | --- |
| Complete group admission | Current installation/version and photo/link checks; binding association; every new intent and FIFO allocation; due/wake changes; events | Validate the whole input first. Reuse existing pairs unchanged. A rollback advances no counter. A lost response permits the same natural-key request. |
| Claim/recover | Eligible due head; both gates; incremented generation and new lease ID; abandoned-attempt recovery and events | Two callers yield one current owner. Recovery of an unresolved marker terminalizes and blocks before any new Flickr work. |
| Start attempt | Current partition fence, lowest active head and block check; attempt, intent state and events | An existing block restores its terminal/active-membership invariant instead of starting work. |
| Renew/release or reschedule | Exact lease fence; accepted deadline rules; due projection and transition evidence | A stale release or renewal cannot affect the successor. Never sleep under a lease until a future due time. |
| Mark dispatch | Current head/attempt/fence, enabled gate revisions, current link revision, absent exact-pair block, durable preflight, marker/count/event | A success response from this commit is required before handing POST to the transport. Indeterminate commit is not dispatch permission. |
| Commit result/recovery | Fenced attempt result, intent terminal/active state, required permanent block, affected gates/link state and events, next-head due/wake state | Codes 6/7, unknown results, and unresolved dispatch preserve permanent suppression. A received but uncommitted response is not durable knowledge. |
| Issue/rotate/revoke an installation | Installation and all affected version states/pointers/revisions; administrative and lifecycle events | CAS losers change nothing. Every normal mutation using an old credential loses when revocation/rotation committed first. |
| Login/reauthentication/revocation | One-use transaction; old/new session state; principal revision; audit events | A replay cannot mint another session. Cookie transmission follows commit; revocation remains authoritative after response loss. |
| Activate/disconnect a Flickr link | Exact secret-version pointer, link revision/state, gate changes and OAuth invalidation where required, audit events | Stage secret first; activate with CAS; delete inactive material afterward. Old-result CAS cannot disable a replacement link. |
| Publish a group/member snapshot | Current control/ownership revision; complete staging-to-current replacement; revision/time/job result | Readers get one complete version. A loser or failed refresh leaves the last good version intact. |
| Create/update a hosted album obligation or photo proof | Exact identity/revision checks, immutable binding, obligation/provenance and events | A response loss retries the same hosted operation. It never licenses a second external write. |

For D1, construct every prepared statement before `batch()`. Required dependent
decisions must be represented in SQL inside that batch. A conditional update
affecting zero rows is not a SQL error: a later unconditional insert could still
commit. Prove the negative path using narrowly scoped SQL predicates and
constraints/abort guards, including all downstream events and counters. Checking
affected-row counts in JavaScript after commit is too late to roll back earlier
writes. Whether these guards remain understandable is part of the evaluation.

Prefer conventional unique/check/foreign-key constraints and conditional SQL;
do not introduce a generic transaction interpreter or compensation protocol.
If a batch needs that machinery, compare the aggregate Durable Object's local
transaction callback and the conventional RDS transaction before proceeding.

After admission, publish zero or one hint for the canonical-lowest newly eligible
partition. Emit none for an idempotent retry or insertion entirely behind active
heads. Every other newly due partition remains discoverable by the minutely
sweep. A successful D1 commit followed by a failed Durable Object call is a
successful durable admission with delayed scheduling.

## Durable Object alternatives

| Shape | What fits | What must be resolved |
| --- | --- | --- |
| D1 authority, optional per-partition Durable Object wakeup | Complete relational transactions, global pair uniqueness, indexed sweeping and one backup boundary | D1 conditional SQL, insert-only privileges, clocks, and bounded workload proofs remain required. Keep a direct sweep-to-claim path for lost/uncreated objects. |
| One SQLite-backed Durable Object per FGA user owning that user's complete relational aggregate | Multi-group admission can be local; ordinary transaction callbacks simplify branching; private MVP has one user | Installation/session/audit/link/gate facts cannot remain authoritative in D1 if a transaction needs them. Deployment gates, global limiter state and permanent identity retention must also have a coherent boundary. Single-user operation does not prove future cross-user transactions. |
| One stable deployment aggregate for all private-MVP relational state | Co-locates the sole user and deployment-wide facts without cross-object commits | An additional hypothesis, not a selection. Prove aggregate size, contention, authoritative clocks, runtime/schema privileges, enumeration/export and restoration. Preserve identity across same-owner relink; do not replace the aggregate on credential rotation. |
| Per-group authoritative Durable Objects plus D1 safety/session records | Natural local partition serialization | Splits multi-group admission and result/block commits. Ordinary RPC cannot meet their atomicity; reject this split for the current contracts. |
| Separate session authority in a Durable Object while domain mutations remain in D1 | Short-lived state and local coordination look attractive | Security mutations require session/installation state and audit consistency with domain commits. A cached authorization or remote check before commit cannot provide that fence. |

Durable Object input/output gates protect their documented local-storage
operations. They are not a lease on a D1 row or a transaction across an awaited
network call. Every scheduled, hinted, retried, and resumed invocation still
passes through the same database claim/attempt implementation.

## Runtime identity and retention protection

The [worker contract][worker] requires an application role that can select and
insert permanent blocks but cannot update/delete them or change their schema.
[Fail-polite case `FP-BLOCK-009`][fail-polite] exercises direct database authority,
including rollback-era application roles. Hiding a delete button is insufficient.

The current documented D1 binding permits SQL execution; the reviewed sources
do not expose the required table-specific privilege separation. Triggers may
prevent erroneous ordinary statements, but a runtime identity able to remove
the trigger or table still has erasure authority. Include direct update/delete,
replacement inserts, parent cascades, schema/trigger changes and disabling check
enforcement in the isolated probe. Verify actual binding behavior, rather than
inferring all permissions from the HTTP management API.

A private storage Worker with narrow service-bound methods could remove raw SQL
capabilities from the public FGA API backend and task workers. The concern is
that this introduces custom security enforcement, another trusted runtime with
broader rights, binding administration, migration compatibility, and a maintained
method surface. Conventional PostgreSQL runtime grants are the simpler reference
for this particular requirement. Do not adopt the custom service merely to keep
the database native: its security equivalence and maintenance cost need the
architecture working agreement's explicit decision checkpoint. It cannot declare
itself a migration-only principal while continuing to run in production.

For either native candidate, separately identify public API, group worker,
refresh worker, authentication helper, scheduler, migration, and backup/restore
capabilities. Deployment credentials never enter request handlers. A scheduler
needs wake/claim invocation authority, not permanent-block deletion or secret
administration. Positive role tests and denied direct operations must run with
the actual deployed bindings/credentials. #0007 owns this evidence.

## Clocks, consistency, and bounded work

Use primary D1 reads for installation/session authentication, ownership, gates,
claims, and recovery. A joined read should observe the relevant record versions
together; mutation transactions recheck them. Avoid authorization caches and
client-selected replication bookmarks. Any later replica-backed status view
must explicitly preserve its accepted consistency semantics.

Persisted deadlines come from the selected database clock. Keep timestamp
ordering separate from the explicit FIFO counter and lease generation. SQLite
date-function resolution and D1 JavaScript integer conversion need real-adapter
tests. Formatting milliseconds with six fractional digits does not establish
microsecond clock resolution. Resolve the accepted audit-precision requirement
before treating either SQLite candidate as conforming; do not substitute a
Worker timestamp or invent sub-millisecond observations. Implementation #0014
owns the precision/resolution question and its native evidence.

The live less-than-1,000-millisecond moderation check is a separate issue.
Cloudflare's [timer behavior][worker-timers] differs between local and hosted
execution, and its [web-standards documentation][worker-standards] equates
`performance.now()` and `Date.now()`. Require a deployed proof of elapsed-time
and deadline behavior, including a long synchronous interval after the last I/O,
a delayed marker commit, a stalled invocation, and backward wall-clock movement
in the injectable-clock cases. Observe transport handoff independently. Taking
`max(previous, now)`, padding timestamps, or adding a sleep is not proof of
monotonic elapsed time. Keep group POST capability disabled unless the exact
freshness contract is satisfied. RDS would address a storage question, not this
Cloudflare compute question. Implementation #0013 owns the deployed time proof
and supplies evidence to #0005 and #0006.

Carry the accepted worker invocation/lease/network budgets into the Cloudflare
adapter explicitly; the old contract's Cloud Run timeout is not a Cloudflare
configuration setting. Provider CPU limits do not substitute for elapsed network
deadlines. One head per claim, bounded sweep batches, pause-aware eligibility,
and indexed due-time ordering preserve fairness without a long-held lease.

Measure complete admission at the eventual accepted batch bound, the maximum
accepted snapshot size, revocation of a session set, and restoration with retained
history. D1's limits apply to statements within a batch; the API also documents
a 30-second bound on a complete HTTP batch. Do not silently split one admission
into commits or lower an accepted product limit to fit. The old proposed
deployment's numeric group-batch bound is not independently accepted by ADR 0050.

## Partial failures and recovery

| Boundary/failure | Required outcome under the proposed mapping | Proof owner |
| --- | --- | --- |
| D1 admission rolls back at any statement | No partial binding, intent, ordinal, due/event change, or eligible hint | #0004; `CBA-TXN-003` |
| D1 admission commits; response or only hint is lost | Same request reuses intents; sweep discovers every due head | #0004/#0005; `CBA-HINT-003`, `CBA-HINT-005` |
| Hint/alarm is early, duplicated, reordered, or restored from older object state | D1 time/revision/gate/lease checks make it harmless; no authority from the object | #0005; `FP-QUEUE-003` |
| Object is evicted, recreated, absent, or exhausts alarm retries | D1 due rows survive and direct periodic sweep reaches the same claim path | #0005; `FP-QUEUE-004` |
| D1 becomes unavailable after a claim or before marker acknowledgement | No new POST; no replacement local lease or cached authorization | #0005/#0006 |
| Marker commit succeeds but its acknowledgement is lost | Caller does not dispatch; ordinary recovery conservatively blocks unless accepted durable evidence proves zero-byte non-handoff | #0006; `FP-CRASH-004` |
| Marker is committed; object/invocation dies before, during, or after POST | Missing definitive result and zero-byte proof yields atomic permanent suppression and terminal uncertainty | #0006; `FP-CRASH-004` through `FP-CRASH-007` |
| Success/result commit succeeds; response or next hint is lost | Read authoritative terminal/head state; no replay of the completed attempt | #0006; `FP-CRASH-008` |
| Lease expires and successor commits before old response arrives | Old generation cannot mutate or replace recovery; late response is diagnostic only | #0005/#0006; `FP-QUEUE-003` |
| Disconnect, credential rotation, or gate pause races with work | Transactional version/gate checks determine admission; already-dispatched bytes retain their ambiguity rules | #0004/#0006 and lifecycle conformance |
| Secret staging succeeds; D1 activation fails or acknowledgement is lost | Resolve D1 link revision before cleanup; never delete a possibly active version or activate by name | #0009; OAuth lifecycle |
| D1 activates new grant/removes authority; old-secret deletion fails | Old reference stays inactive; bounded cleanup retries; disconnect remains truthfully pending | #0009; OAuth lifecycle |
| Refresh dies while staging or loses ownership before publish | Last good snapshot stays current; stale invocation cannot publish or mix rows | Snapshot conformance; carry into refresh implementation |
| Restore rolls D1 behind a block, dispatch marker, revocation, or gate pause | External operational stop prevents writes; reconcile retained evidence before any resumption | #0007; `FP-BLOCK-003` |
| D1 restores while old Durable Object hints/fences survive | Quiesce old invocations; discard coordinator authority assumptions; rebuild from recovered D1 only | #0005/#0007 |

Use the existing [admission][batch] and [fail-polite][fail-polite] scenario IDs
instead of creating another canonical case inventory. The additional native
cases above extend the provider harness. Cases involving true process loss or
eviction must state which mechanism reproduced it; an exception alone is not
equivalent evidence. No probe uses a real Flickr grant or volunteer group.

## Migration and restore proof

Version migrations in the repository using the provider's ordinary
[D1 migration mechanism][d1-migrations]. Bind proof results to the migration head,
runtime artifact, compatibility date, SQL engine/version observations, and
actual identities. Exercise failed migration, supported application rollback,
constraint preservation, and data export/import. A down migration must not erase
blocks, immutable associations, or audit history. Large maintenance work requires
bounded steps and an operational stop where intermediate state is unsafe.

Finite point-in-time history is not permanent retention. #0007 must establish a
backup destination, access boundaries, retention, integrity verification,
restore-time measurements, and capacity forecasts for the live safety history.
Backups contain private operational records and stay outside this public
repository and public CI artifacts. Export can block requests; demonstrate its
effect on lease expiry and recovery rather than letting an export failure make a
worker replay an ambiguous dispatch. Compare exact ordinal/generation values
across queries and export/import at `2^53 - 1`, `2^53`, `2^53 + 1` and signed
64-bit boundaries; ordinary JavaScript-number equality is insufficient.

A restore proof needs both a compatible data copy and an execution boundary:

1. Stop admissions and outgoing Flickr operations outside the database being
   restored; a paused row inside an older snapshot can revert to enabled.
   Quiesce old invocations, outstanding envelopes, schedulers and alarms under
   the applicable lifecycle rules. A database generation rollback can otherwise
   make an old fence appear current again.
2. Preserve pre-restore evidence when available and identify the interval the
   restored copy omits. Restore the correct schema/data using a maintenance
   identity, with runtime authority still disabled.
3. Reconcile permanent blocks, dispatch/result/ambiguity evidence, immutable
   bindings, audit history, revocations and gate/link revisions through the
   stopped boundary. Recover unresolved dispatch conservatively. If complete
   compatible safety history cannot be established, keep affected automated
   writes disabled; a point-in-time rollback cannot certify missing evidence.
4. Revalidate current credential and secret authority. Invalidate potentially
   revived sessions/credentials through the controlled lifecycle; a historical
   secret pointer is not permission to recover or reactivate a deleted secret.
5. Rebuild due projections and disposable coordinator state, verify stale
   invocations cannot return, and run the safety/authorization checks before
   the controlled resumption. No D1/DO coordinated snapshot is assumed.

This is a required proof outline. Selecting a backup product, numerical recovery
objectives, or a new restore protocol still needs its scoped decision. RDS also
needs a tested procedure that prevents restoration from erasing later safety
knowledge; database choice alone does not meet this obligation.

## Proof sequence and fallback criteria

The newly identified time, audit-precision, and limiter-boundary questions are
tracked separately as #0013, #0014, and #0015 in the implementation Backlog.
Their investigation and any owner decisions remain outstanding.

| Work | Reviewable next evidence | Objective stop/fallback criterion |
| --- | --- | --- |
| #0007 protection, first small probe | Exact runtime capability inventory; permitted insert and denied destructive operations; aggregate-DO comparison where relevant | An ordinary runtime can alter/remove a protected fact or its enforcement. Do not approve the direct native mapping; compare conventional RDS grants and any explicitly reviewed native alternative. |
| #0004 D1 admission | Whole-batch SQL, rollback at each statement, zero-row guards, overlapping requests, exact ordinal transport, one-hint cases | Any accepted handoff is partial, a stale authorization commits, an ordinal changes on rollback, or implementation requires a distributed commit/custom transaction engine. Evaluate aggregate-local transactions or RDS. |
| #0005 scheduling and time | Real alarms, minutely sweep, lost hints, overdue recovery, concurrent claims and fencing; deployed timer observations | Work depends on an undelivered hint, stale owner can mutate/dispatch, or the required clock/deadline semantics cannot be established. A timer failure needs a Cloudflare execution decision; storage fallback alone is insufficient. |
| #0006 fail-polite crashes | Production-shaped adapter and controlled HTTPS peer; crash, result, timing and mutation cases | Any second POST, missing atomic block, stale-worker dispatch, or false freshness acceptance prohibits group-write deployment. |
| #0007 migration/restore continuation | Disposable live restore/export and schema-change evidence, integer fidelity, retained audit/safety history | Restore revives authority or loses protected history without a safe abstention boundary; no native pass. Compare fallback recovery on the same requirements. |
| #0008 routing and #0011 read slice | Authoritative credential lookup plus edge/route and response conformance after their own prerequisites | A read slice proves only its exact read behavior. It cannot accept protected mutation, worker, secret-version, or recovery gates by implication. |
| #0009 secrets and #0010 fallback record | Separate immutable-version explanation; documented failed native requirement, alternatives, identity/network, latency/availability, recovery, cost and exit plan | Adopt no AWS backing service or custom credential workaround until its review is complete. |

Provider evidence must identify the isolated deployment, fixture namespace,
adapter/artifact and migration revisions, configuration, scenario IDs, injected
fault, durable before/after observations, and observed outbound-call count.
Capture sanitized evidence through the same interfaces intended for production.
Do not convert unavailable infrastructure, missing cases, or an unproven
eviction/timer mechanism into a skipped success.

The mapping supplies a starting point for the authorized spikes. Any accepted
production mapping belongs in the architecture repository under ADR 0050's
decision process, followed by its scoped contract updates. This document does
not accept proposed ADRs 0047, 0048, or 0049.

## Research validation

On 2026-09-06, document checks resolved all 31 source-reference definitions,
verified all 13 pinned architecture paths against the recorded Git commit, and
matched all 10 referenced conformance IDs to their canonical contracts. Markdown
tables, README navigation, and Git whitespace checks passed. These checks
validate this research artifact; provider and production conformance remain
outstanding.

[authority]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/README.md
[adr50]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/decisions/0050-select-cloudflare-and-evaluate-native-storage-first.md
[worker]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/worker-persistence-scheduler-contract.md
[batch]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/testing/courteous-batch-admission-conformance.md
[fail-polite]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/testing/fail-polite-worker-database-conformance.md
[plugin]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/plugin-service-contract.md
[installations]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/installation-credential-lifecycle.md
[sessions]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/browser-session-lifecycle.md
[oauth]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/oauth-and-account-lifecycle.md
[admin]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/administrative-control-plane-contract.md
[snapshots]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/group-snapshot-and-pagination.md
[albums]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/album-scoped-publish-contract.md
[replacement]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/decisions/0023-never-replay-an-ambiguous-flickr-replacement.md
[d1-api]: https://developers.cloudflare.com/d1/worker-api/d1-database/
[d1-fk]: https://developers.cloudflare.com/d1/sql-api/foreign-keys/
[d1-replication]: https://developers.cloudflare.com/d1/best-practices/read-replication/
[d1-limits]: https://developers.cloudflare.com/d1/platform/limits/
[d1-types]: https://developers.cloudflare.com/d1/worker-api/
[d1-sql]: https://developers.cloudflare.com/d1/sql-api/sql-statements/
[d1-permissions]: https://developers.cloudflare.com/d1/platform/release-notes/#2025-05-02
[sqlite-omitted]: https://www.sqlite.org/omitted.html
[do-storage]: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
[do-alarms]: https://developers.cloudflare.com/durable-objects/api/alarms/
[cron]: https://developers.cloudflare.com/workers/configuration/cron-triggers/
[service-bindings]: https://developers.cloudflare.com/workers/runtime-apis/bindings/service-bindings/
[d1-restore]: https://developers.cloudflare.com/d1/reference/time-travel/
[d1-export]: https://developers.cloudflare.com/d1/best-practices/import-export-data/
[d1-migrations]: https://developers.cloudflare.com/d1/reference/migrations/
[worker-timers]: https://developers.cloudflare.com/workers/runtime-apis/performance/
[worker-standards]: https://developers.cloudflare.com/workers/runtime-apis/web-standards/
[sqlite-time]: https://www.sqlite.org/lang_datefunc.html
