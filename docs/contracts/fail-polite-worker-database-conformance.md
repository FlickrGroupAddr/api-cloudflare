# Fail-polite worker and database conformance suite

Last updated: 2026-09-14

Status: Accepted required production test contract; no executable conformance
pass exists until the production FGA group-submission worker, FGA database
migrations, and their real adapters exist

## Purpose and non-claim

This contract turns [ADR 0007](../decisions/0007-fail-polite-group-submissions.md)
and the
[worker persistence contract](../worker-persistence-scheduler-contract.md) into
one mandatory executable acceptance suite for the eventual hosted repository.
It protects a socially irreversible boundary: after a moderation result or an
ambiguous group-add dispatch, the FGA API backend, FGA group-submission worker,
FGA administrative control plane, and FGA database may not authorize or submit
that exact photo/group pair again.

This architecture repository has no production worker, database schema,
migration runner, Flickr client, or hosted test command. A reference state
machine, mocked repository, documentation checker, or always-skipped test here
would create a misleading green result without exercising the safety boundary.
Ticket #0045 therefore fixes the required harness and scenario inventory now.
Accepted [ADR 0050](../decisions/0050-select-cloudflare-and-evaluate-native-storage-first.md) selects Cloudflare and
native Durable Objects/D1 evaluation first, with RDS PostgreSQL as fallback.
This suite's required behavior and real-adapter evidence apply to either
storage mapping. A native proof cannot pass by substituting in-memory state,
dropping safety invariants, or weakening authority beyond the explicitly
accepted private enforcement boundary in
[ADR 0051](../decisions/0051-trust-private-storage-runtime-with-guarded-writes.md). The selected
implementation must instantiate the suite against its actual storage,
migrations, and worker adapters before deployment.

## Accepted private clock profile

Terry accepted [ADR 0056](../decisions/0056-accept-private-workers-observed-preflight-time.md)
on 2026-09-12. The private single-owner Workers run must explicitly name that
profile in its evidence; other deployments retain the monotonic-clock rules.
The native I/O-refreshed sample is not a hard real-time or monotonic guarantee.

FP-PRE-008 through FP-PRE-010 retain their strict manual microsecond boundary
assertions on observed age. For FP-PRE-011, the private profile must reject an
invalid or negative observed delta and report the accepted CPU/clock-adjustment
blind interval rather than claim that native time is independent of wall time.
A separate wall-clock injection into audit data must not authorize dispatch.
The standard profile still requires the original independent monotonic result.

The private production transport must fully prepare credentials, signature,
headers and a bounded materialized body before the marker transaction. Test
that no serialization, signing, lazy stream, secret lookup, await or unrelated
work occurs between its final refreshed sample/check and prepared handoff.
A mutation that adds such deferred preparation must fail behavioral assertions.
A diagnostic CPU-stall case records the accepted timing gap; it is not a waiver
of marker-before-handoff, negative/expired-age rejection, or permanent blocks.
Keep all stable case IDs and the complete non-clock case/mutation inventory.
No earlier diagnostic report becomes a production conformance pass by approval.

## Required test topology

The suite uses the production code path and these replaceable infrastructure
boundaries:

| Boundary | Conformance requirement |
| --- | --- |
| FGA database | A fresh isolated instance of the selected production database engine, initialized only through production migrations; no in-memory substitute for transaction, constraint, isolation, lease, or crash tests |
| Worker | The same FGA group-submission worker entry point and claim/attempt implementation used by immediate hints, scheduled sweeps, and recovery; no retry-now entry point exists |
| Flickr REST | A local controllable HTTPS test endpoint behind the production Flickr transport adapter; records exact method, group/photo IDs, start order, and handoff time and returns complete, malformed, delayed, dropped, or connection-failing responses |
| Time | An injected manual monotonic clock used by production freshness logic plus an independently mutable wall clock; timestamps persisted for audit still use the FGA database clock |
| Rate limit | The production reservation interface backed by a deterministic test allocator that can prove the membership GET, moderation GET, and possible POST capacity were reserved atomically before the membership guard |
| Faults | Explicit production-adapter fault points before/after each durable boundary; process termination uses a separate worker process where in-process exceptions cannot reproduce the failure |
| Clients | Production FGA API backend admission, scheduler, status, administrative gate-repair, and recovery entry points; tests do not write internal tables as a substitute for exercising a route |

The test Flickr endpoint is never a volunteer-managed Flickr group and holds no
real Flickr credential. It validates the FGA group-submission worker's protocol,
not Flickr's live behavior. Any separately approved live integration probe uses a
project-owner-controlled sandbox group and cannot replace this deterministic
suite.

Production code may accept dependency injection at these conventional
boundaries, but it **MUST NOT** contain a test-only path that implements a
stronger block, clock, preflight, or transaction rule than deployment code.
The suite must run with the optimized deployable worker artifact and exact
production migrations selected for release.

## Observable test record

Each case starts with a unique FGA user, Flickr photo ID, Flickr group ID,
partition, and correlation ID. The harness captures:

- every outbound Flickr operation in start order with its attempt and exact
  pair;
- the membership and moderation-preflight outcomes and operation order;
- the monotonic moderation-response receipt and POST-dispatch-start instants at
  microsecond resolution;
- rate-reservation acquisition/release events;
- committed intent, attempt, partition, lease, preflight, gate, permanent-block,
  and append-only event rows after every durable boundary;
- sanitized worker outcome and audit/metric events; and
- the state after a fresh worker process performs recovery.

Tests assert both presence and absence. A database terminal state is
insufficient if a second POST occurred; zero POSTs is insufficient if the
required durable block was not committed. Secret values and raw Flickr response
bodies must be absent from every captured log, trace, metric, and database row.

The production test source preserves the stable IDs below in test names or
metadata. The CI job emits the complete sorted ID list plus pass/fail status,
release commit, migration head, database-engine version, worker-artifact digest,
and test-adapter version. CI fails if an ID is absent, skipped, selected out,
or duplicated. The Markdown table is the requirement inventory; it is not a
second executable manifest.

## Managed D1 engine provenance

Terry accepted [ADR0058](../decisions/0058-record-managed-d1-engine-provenance.md)
on 2026-09-14. For the private single-owner D1 deployment only, the engine
version requirement above permits a provider-undisclosed SQLite-library version
with the following evidence. This does not change any case, mutation, process
stop, restore, reconciliation or promotion requirement.

The release evidence identifies the `adr-0058-private-single-owner-d1` deployment
profile and records a fresh remote `SELECT sqlite_version() AS sqlite_version`
query during that run. When the provider discloses a version, record its actual
numeric value and remote-query source. When the provider rejects that function,
record an explicit null version, `provider-undisclosed` disclosure status, a
sanitized refusal and observation time. Missing keys, an empty string, a provider
generation tag, a local SQLite version, an authentication failure, a transport
failure or an unclassified provider error cannot substitute for this evidence.

Record the provider generation tag separately from the library version, along
with the migration head and digest, optimized artifact and configuration digests,
Workers compatibility date, pinned tooling identities and test-adapter source
digest. Bind the observation to the release run's start/completion interval and
the same configured database used by the test adapters. Record an actual version
if a later query exposes it. The compatibility date does not pin D1's underlying
engine, and this exception does not guarantee reproduction of a managed update.
The hosted verifier owns the executable evidence schema; old evidence formats
must fail until they supply this provenance. Other deployment scopes still need
their required engine disclosure and cannot select this private exception.

## Attempt-scoped membership cases

| ID | Stimulus | Required assertions |
| --- | --- | --- |
| `FP-MEM-001` | Complete `getAllContexts` response omits the exact target group | Persist target-absent evidence for this attempt, then perform `getInfo`; any eventual add operation order is exactly `getAllContexts`, `getInfo`, `pools.add` |
| `FP-MEM-002` | Complete `getAllContexts` response contains the exact target group | Atomically terminalize the intent as `added` with source `pre_add_membership_observation`, remove active FIFO membership, and send neither `getInfo` nor add |
| `FP-MEM-003` | Membership transport failure or complete Flickr failure status | No `getInfo`, no add POST, and no `dispatch_started`; retain the FIFO head with bounded safe-read retry and sanitized evidence |
| `FP-MEM-004` | Missing, null, object, or scalar pool; malformed/duplicate entry; invalid root/status/media type; truncation; or resource-budget overflow | Treat the complete observation as unavailable with the same no-`getInfo`, no-add behavior; never filter bad entries or publish an empty/partial result |
| `FP-MEM-005` | Cached selector or prior worker membership says target absent | Ignore it as write authority and perform a new exact-photo `getAllContexts` for this attempt |
| `FP-MEM-006` | Reservation allocator cannot atomically grant all three operation slots | Start no membership read and consume no partial reservation |
| `FP-MEM-007` | Membership read prevents later operations | Release the unused moderation-GET and POST capacity exactly once; account for the completed membership GET |
| `FP-MEM-008` | Target is absent in the membership read but Flickr later returns add code `3` | Preserve the advisory-race evidence and terminalize as idempotent `added`; do not treat the race as a protocol failure or retry |

## Fresh moderation preflight and dispatch cases

| ID | Stimulus | Required assertions |
| --- | --- | --- |
| `FP-PRE-001` | One eligible intent | The attempt's exact `flickr.groups.getInfo(group_id)` is the immediately preceding Flickr operation before its one `flickr.groups.pools.add(photo_id, group_id)`; the complete interpretable `ispoolmoderated` value and database observation time are committed |
| `FP-PRE-002` | `getInfo` transport failure, Flickr failure status, malformed body, missing moderation value, or uninterpretable value | No add POST and no `dispatch_started`; retain the FIFO head with bounded safe-read retry and sanitized evidence |
| `FP-PRE-003` | A cached moderation observation exists | The worker ignores it as write authority and performs another `getInfo` for this attempt |
| `FP-PRE-004` | An unrelated Flickr operation is requested between successful `getInfo` and add | The attempt refuses dispatch and starts a new preflight; the unrelated call can never be followed by add under the old observation |
| `FP-PRE-005` | Concurrent attempts in different partitions | Each add has its own immediately preceding exact-group preflight; one attempt cannot borrow another's observation or reservation |
| `FP-PRE-006` | Reservation exists for all three operations, but its ownership or scope no longer matches the attempt | No preflight starts and no capacity from another attempt is consumed |
| `FP-PRE-007` | Successful moderation preflight needs no POST | Unused reserved POST capacity is released exactly once; both completed GET reservations remain accounted for |
| `FP-PRE-008` | Monotonic age is `999,999` microseconds when dispatch begins | Dispatch may start if every other guard passes; persisted marker precedes transport handoff |
| `FP-PRE-009` | Monotonic age is exactly `1,000,000` microseconds or greater before marker commit | Discard the observation and repeat `getInfo`; no add uses the expired observation |
| `FP-PRE-010` | Age crosses 1,000 milliseconds immediately after marker commit but before transport handoff, while the live transport proves zero bytes sent | Commit `not_dispatched_preflight_expired`, do not hand off POST, and repeat preflight without creating a permanent block |
| `FP-PRE-011` | Wall clock jumps backward/forward while monotonic age remains below/above the boundary | Dispatch eligibility follows only monotonic elapsed time; audit times continue to follow the database clock |
| `FP-PRE-012` | Gate/link/lease revision changes after preflight and before marker | No POST; stale worker loses the compare-and-set and cannot mutate the current attempt |

The boundary is strict: “less than 1,000 milliseconds” means `999,999`
microseconds is eligible and `1,000,000` is expired. Tests use an explicit
manual monotonic clock, not timing sleeps or a broad tolerance that could hide
an inclusive comparison.

## Result classification and atomic persistence

| ID | Flickr/add outcome | Required assertions |
| --- | --- | --- |
| `FP-RES-001` | Code `6` | In one database transaction, create-or-confirm the permanent exact-pair block and terminal `moderation_submitted`; retain first evidence and append the result event |
| `FP-RES-002` | Code `7` | Same atomic block and terminal behavior as code `6`; no future attempt |
| `FP-RES-003` | Code `6` after preflight `ispoolmoderated="0"` | Record the contradiction/race diagnostic and still atomically create the permanent block and terminal `moderation_submitted`; no amnesty |
| `FP-RES-004` | Unknown numeric Flickr application code after POST | Atomically create the permanent block and terminal `delivery_uncertain`; classifier default cannot become retryable |
| `FP-RES-005` | Missing, truncated, invalid-media-type, or unparseable response after POST handoff | Atomically create the permanent block and terminal `delivery_uncertain` during recovery; no second POST |
| `FP-RES-006` | Timeout, cancellation, connection loss, or process exception after POST handoff | Treat as `delivery_uncertain` unless a durable transport record proves zero request bytes could have left; ordinary exception classes alone are not proof |
| `FP-RES-007` | Code `105` or `106` | Retain retryable FIFO head with bounded backoff and no permanent block, then require a new preflight on the later attempt |
| `FP-RES-008` | Durable transport proof of zero bytes before DNS/TCP/TLS handoff | Retain retryable head and no permanent block; the exact proof class is persisted and later work starts with a new preflight |
| `FP-RES-009` | Block/terminal result transaction is forced to roll back after response receipt | Recovery sees unresolved `dispatch_started` and atomically creates `delivery_uncertain`; rollback never makes the pair pending for another POST |
| `FP-RES-010` | Existing permanent block precedes a new handoff | Return existing terminal/suppressed state without `getInfo`, add POST, new ordinal, or attempt |

Codes `6`, `7`, an unknown code, and unresolved dispatch must use one database
transaction for permanent block, terminal intent state, active-FIFO removal, and
append-only evidence. Constraint and transaction-fault tests must make it
impossible to observe only a terminal intent or only a block after commit.

## Crash-boundary matrix

Every row runs once from the immediate-hint path and once from periodic-sweep
recovery. Retry-now and administrative entry paths are additionally exercised
by the bypass matrix below.

| ID | Injected stop point | Required recovered state |
| --- | --- | --- |
| `FP-CRASH-001` | Before preflight request | No marker or block; same head safely eligible later |
| `FP-CRASH-002` | After successful preflight response but before its durable record | No marker or block; old observation cannot be reused |
| `FP-CRASH-003` | After durable preflight record but before `dispatch_started` | Close as abandoned-before-dispatch; later attempt requires a new preflight |
| `FP-CRASH-004` | After `dispatch_started` commit and before an adapter can durably prove zero-byte non-handoff | Permanent `delivery_uncertain` block; no add POST on recovery |
| `FP-CRASH-005` | Immediately after POST handoff | Permanent `delivery_uncertain` block; no add POST on recovery |
| `FP-CRASH-006` | After complete Flickr response but before result transaction begins | Permanent `delivery_uncertain` block because the response was not durably classified |
| `FP-CRASH-007` | During result transaction before commit | Rollback followed by permanent `delivery_uncertain`; no partial terminal/block state |
| `FP-CRASH-008` | Immediately after result transaction commit | Recovery observes the committed terminal/block result and performs no new Flickr operation |
| `FP-CRASH-009` | After a successful membership response but before its durable outcome | No marker or block; retain the head and require a new membership read on recovery |
| `FP-CRASH-010` | After durable target-absent membership evidence but before `getInfo` | Close the abandoned attempt before dispatch; a later attempt starts with a new membership read rather than reusing the prior observation |

Process-stop cases use an independently killable worker process and then a new
process. Throwing an exception and continuing in the same process is not enough
to prove that leases, connections, transaction rollback, and durable recovery
work after abrupt loss.

## Permanent-block survival and bypass matrix

For each seed reason—code `6`, code `7`, unknown result, and unresolved
dispatch—the suite attempts every path below and asserts that the original
block and first evidence remain, no add POST starts, and no API response offers
a force-resubmit option.

| ID | Attempted bypass |
| --- | --- |
| `FP-BLOCK-001` | Duplicate ordinary handoff with the same exact pair and a new idempotency key |
| `FP-BLOCK-002` | Immediate hint, periodic sweep, guessed retry/reopen/cancel routes, reconciliation, and crash recovery |
| `FP-BLOCK-003` | Worker restart, deployment restart, lease expiry/takeover, and database backup/restore |
| `FP-BLOCK-004` | Current moderation changes from moderated to unmoderated to moderated, with months/years advanced on both clocks |
| `FP-BLOCK-005` | Same-owner OAuth disconnect and relink, user write-gate pause/resume, and installation-credential rotation |
| `FP-BLOCK-006` | Ordinary history-pruning and retention jobs at every configured age boundary |
| `FP-BLOCK-007` | Modified-client request supplies fake moderation state, retry flag, force flag, block ID, terminal state, or administrative-session credential |
| `FP-BLOCK-008` | Every FGA API backend and administrative route/method combination, including guessed delete/update/clear/force endpoints |
| `FP-BLOCK-009` | Ordinary destructive SQL through every runtime identity/binding with production guards installed; application paths and controlled migration/rollback preservation under ADR 0051 |
| `FP-BLOCK-010` | Later positive membership observation and later absence from the group pool |

For the private deployment, FP-BLOCK-009 must prove that database guards
reject UPDATE, DELETE, replacement inserts, destructive upserts, and cascading
removal of seeded protected blocks and append-only evidence. Verify preserved
values as well as statement failure. Exercise actual request, scheduling,
retention, and recovery paths; no such path may issue destructive schema or
storage operations. Controlled migration and rollback tests must preserve
protected facts and reinstall any required guards before runtime work resumes.

Under ADR 0051, deliberate DROP TRIGGER/DROP TABLE, guard disabling, or owning
Durable Object deleteAll capability probes are diagnostic evidence of the
accepted native runtime trust boundary. Their capability alone no longer fails
private acceptance, but production code invoking them to erase protected facts
still fails. PostgreSQL implementations retain non-owner runtime identities
without update/delete/truncate or schema privileges on protected state; test
those grants and possible inherited, cascade, or privileged-function bypasses.
The native exception does not authorize deployment/admin credentials in
runtime code. No fixture helper may delete a block in the same database
between phases of one conformance case.

## Partition, concurrency, and entry-path cases

| ID | Stimulus | Required assertions |
| --- | --- | --- |
| `FP-QUEUE-001` | Concurrent identical handoffs | One intent, one committed queue ordinal, and at most one active attempt |
| `FP-QUEUE-002` | Concurrent distinct handoffs to one partition with forced rollback | Unique committed ordinals preserve commit order; rollback creates no gap that can reorder active work |
| `FP-QUEUE-003` | Duplicate/stale hints plus concurrent sweeps | One current fenced lease generation; stale generations cannot preflight, mark, dispatch, or commit |
| `FP-QUEUE-004` | Lost immediate hint | The at-least-once periodic due sweep claims the same head without changing its ordinal |
| `FP-QUEUE-005` | Every production work entry path | Immediate hint, sweep, and recovery call the same claim/attempt implementation and produce the same preflight/block results; status and administrative gate repair cannot invoke it directly |
| `FP-QUEUE-006` | Terminal result commits with a following head | Active membership removal, retained history, next-head eligibility, partition due time, wake revision, and hint intent commit atomically |

## Mutation adequacy

Before the suite can gate a release, CI must demonstrate that it fails for
deliberate isolated mutations of the production code or migration. At minimum:

- reuse a cached preflight;
- reuse a cached membership observation;
- continue to `getInfo` or add after an unavailable membership observation;
- filter malformed membership entries or default malformed membership to empty;
- reserve the three operation slots separately;
- interpret failed/missing moderation data as unmoderated;
- change `< 1,000 ms` to `<= 1,000 ms`;
- use a clock outside the selected accepted profile or accept invalid/negative
  observed age; for the ADR 0056 private profile, defer request preparation
  until after the final marker I/O;
- permit an intervening Flickr operation;
- hand POST to the transport before committing `dispatch_started`;
- classify code `6`, code `7`, or the unknown default as retryable;
- make block and terminal state separate commits;
- retry an unresolved dispatch;
- clear a block on unmoderated observation, elapsed retention, same-owner
  relink, a guessed retry/reopen request, or positive/negative membership
  observation;
- authorize a client/admin force flag or block deletion in an application
  path; and
- remove an ordinary-write SQL guard from the production migration so a
  protected-row modification succeeds in FP-BLOCK-009.

Each mutation must make at least one named case fail for the intended reason.
Mutation evidence is retained with the release test record. A test that fails
only because a source-text snapshot changed does not count; the behavioral or
database assertion must detect the safety regression.

## Deployment gate

The hosted repository exposes one ordinary noninteractive test command for this
suite through its locked dependency workflow. The command returns nonzero for
missing/skipped/duplicate IDs, infrastructure failure, schema drift, test
adapter mismatch, any failed assertion, or absent mutation evidence. It does
not silently select a reduced local profile.

No release capable of `flickr.groups.pools.add` may deploy until the exact
artifact and migration head have a complete passing record. The ordinary full
test suite invokes this gate. The deployment pipeline retains the sanitized
record and refuses promotion rather than converting an unavailable database or
fault injector into a skip.

The initial implementation must update this document with the concrete hosted
repository path, command, database engine/version, and CI artifact name. Until
then, project documents must continue to say that fail-polite conformance is
specified but not executable or passed.

## Executable implementation binding (2026-09-14)

- Hosted repository: `FlickrGroupAddr/api-cloudflare`
  (`https://github.com/FlickrGroupAddr/api-cloudflare`).
- Locked, noninteractive command: `uv run --frozen python -m scripts.production_release_suite`.
- Engine: managed Cloudflare D1. Each run records its fresh library-version
  observation; an undisclosed version follows ADR0058 and is never replaced by
  the provider generation label.
- CI workflow: `Release validation`; retained artifact: `fail-polite-production-evidence`.
  The artifact contains the sanitized exact-candidate receipt. Raw credentials,
  provider logs and database snapshots are not uploaded.
- Mutation adequacy uses isolated local D1 fixtures, production migrations and
  the identical unmodified control artifact; positive storage cases use managed D1.
- The independently stoppable adapter runs the production module against hosted
  D1 and native Secrets Store. Its local runtime date is reported separately from
  the same-module hosted Workers runtime and redeployment supplement.

The suite is executable. A conformance pass is a property of a complete successful
CI receipt for its recorded candidate, not of this document or component results.
All requirements above, stable IDs and required mutations remain unchanged.
