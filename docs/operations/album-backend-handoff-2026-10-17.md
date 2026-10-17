# Album backend handoff — 2026-10-17

This batch implements #0113 status/create repair, #0114 title synchronization and
#0112 later-photo attachment. All three cards moved In Progress before work and
delegation. All initial prerequisites were Completed. No native plug-in run,
provider/Flickr request, credential read, production mutation or feature activation
occurred. New runtime composition remains explicit and default-off.

## #0113: status and explicit create repair

The accepted #0092 wire now has its closed installation and administrative
handlers, complete advisory candidate pages, exact-ID owner selection and stored
status models. Candidate discovery never chooses a singleton, title or current
primary automatically. Resolution rechecks the original unknown attempt, current
authority and fresh exact owner/first-photo membership before one conditional
transaction commits immutable identity, retained provenance and primary proof.

Administrative paths use actual server sessions and unsafe-request protection;
they do not impersonate an installation. Successful administrative repair auditing
commits with the domain mutation, while authenticated failures audit before the
response. Exact-origin unauthorized session cleanup expires only the actual
session cookie; CSRF remains memory-only. Local D1 tests cover audit-failure
rollback and replay without duplicate audit. Strict root/row bounds, zero-ID
refusal, complete pages and cancellation are covered.

## #0114: revisioned title intent and reconciliation

The accepted #0094 lifecycle GET and title-intent PUT preserve exact immutable
receipts and current snapshots, including same-text deliberate revisions and
replay after supersession/archive. A dormant worker uses only exact photoset ID
and title for editMeta, omits description, and reconciles complete desired/newer/
pre-dispatch/third-title observations in the accepted priority order.

Three dispatches, five reads, durable backoff, a ten-second execution budget,
lease/cancellation and commit margins are enforced. Unavailable unmarked reads
can recover; a fifth pre-read cannot dispatch without capacity for required
post-read proof. Interrupted fifth charges become visible attention. Foreign
rename/archive changes fence the old claim; later read-only recovery retains the
same dispatch rather than issuing another edit. Initial create metadata is not
invented as verified title evidence. Removed collections permit only retained
read reconciliation, not another title write.

## #0112: fresh read/add/read attachment

Strict current presence completes without addPhoto. Complete absence can authorize
one marked add; success/code3 still requires fresh membership proof. Durable
response classes and uncertain fallback survive restart and failed commits.
Eight unresolved writes are bounded with backoff; verified absence at exhaustion
becomes attention. Unavailable/incomplete reads retain pending state with bounded
backoff, as the accepted contract requires. No new lifetime read-terminal policy
was invented.

Archived accepted unfinished attachments can still finish. A previously fulfilled
pair whose drift add was already marked before archive can reconcile by reads
only: presence verifies, absence becomes truthful attention, and no further add
is possible. Later external drift after archived fulfillment is not restored.

## Cross-slice corrections and shared integration

- Semantic obligation evidence/state changes atomically advance both binding
  and obligation revisions; title lifecycle evidence advances binding revision.
  Claims, leases and operational bookkeeping alone do not. Append-only facts,
  immutable attempt snapshots and private semantic frontiers preserve self-owned
  progress while fencing foreign changes and stale SQL replay.
- Missing/conflict status retains immutable IDs/provenance, suppresses stale
  catalog-repair URL/time and advances the ordering revision. Late responses
  cannot present changed status at an unchanged revision.
- Shared Flickr capacity reservations use the existing key-wide budget. Explicit
  admission/fault hooks and private credits are required. The innermost network
  handoff rechecks full current authority, cancellation and window expiry after
  asynchronous admission; a gate change during reservation sends no request.
- Shared signing admits only the two new fixed method/parameter combinations.
  Bounded JSON reading retains its old default and supports explicit 1 MiB
  limits, incremental aggregate accounting and propagated cancellation. Existing
  strict duplicate/Unicode/number checks remain controlling.
- Three ordered migrations preserve populated predecessor data/history/guards;
  actual local D1 rollback and conditional RETURNING behavior are tested. No TEMP
  table or trigger-inflated change-count assumption was introduced.

The parent integrated eleven routes and exact API projections. Stored status and
title operations require no upstream reader; discovery/selection refuse safely
without explicit read composition. Real credential/network/scheduler registration,
hosted qualification and release are separate from this dormant source handoff.

## Verification and review

- Independent #0113 review: 77 focused checks passed.
- Independent #0114 review: 64 focused checks plus four adversarial recovery
  probes passed; the parent legacy-fixture change received separate review.
- Independent #0112 review: 66 focused checks passed, including actual local D1.
- Integrated Python/Lua: 757 tests passed.
- Integrated backend/Worker/local-D1/probes: 809 tests passed.
- Native TypeScript 7.0.2, exact generated API checks, Ruff and Pyright passed.
  Final staging privacy/whitespace checks are recorded with the handoff commit.

The first full backend run passed 808/809: one old materialization test mutated
the title directly through SQL. The parent changed its setup to the real accepted
title-intent operation, retaining its no-stale-marker assertion; 19 focused tests
and independent review passed. No guard was weakened to repair a fixture.

The runtime maximum-counter state was not seeded by weakening production guards
or inventing history. That unexecuted extreme is recorded as a test limitation;
real revision/race/rollback and safe-range guard evidence remains distinct.

Initial delegation used sixteen direct roles: eight Sol Medium, six Sol High and
two Luna Light. Completed authors released slots for shared integration and fresh
independent reviewers; findings returned for correction and re-review. No agent
spawned children. The parent owns aggregate verification, commits/pushes and board
handoff. Detailed private receipts are in workspace
`work-batch-2026-10-17-album`; no raw captures or credentials are published.

Toolchain remains Node 24.22.0, native TypeScript 7.0.2, uv 0.12.5,
Python 3.14.7/Lua 5.1 and SDK 15.3. No dependencies, global configuration,
shared localswim source or ticket priorities changed. #0044 execution remains
NO-GO, #0037 remains unqualified and #0043 provider restoration remains negative.
This work does not waive any native/hosted/live-operation gate.
