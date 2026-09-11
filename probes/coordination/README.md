# Native admission and scheduling proofs

These disposable fixtures exercise `src/admission.ts`, `src/scheduling.ts` and
root migrations through `0003_submission_coordination.sql`. They are the bounded
provider proofs for implementation #0004 and #0005. They do not register a
public group-submission route or implement Flickr dispatch.

## Run

```powershell
npm ci
npm run check
uv run --frozen python -m unittest discover -s tests
uv run --frozen python scripts/coordination_probe.py local admission
uv run --frozen python scripts/coordination_probe.py local scheduling
uv run --frozen python scripts/coordination_probe.py hosted admission
uv run --frozen python scripts/coordination_probe.py hosted scheduling
```

The pinned native TypeScript compiler runs before each bundle/deployment.
The local Node bridge is required by Miniflare; Python owns the orchestration,
assertions, evidence and provider operations. Local compatibility is explicitly
`2026-07-30`; hosted compatibility is `2026-09-11`. The local outbound trap must
observe zero external requests. The hosted fixtures contain no Flickr client or
Flickr credentials. All group/photo/owner records are synthetic.

The controller checks a fresh random Worker and database namespace, uses the
existing Wrangler operator login, and installs the private proof bearer with the
initial Worker deployment. Bearers remain in memory or the existing helper's
short-lived secret transport file; no operator token is installed in a Worker.
Provider output, SQL archives and run manifests stay under ignored
`.coordination-runs/`. Public reports contain scoped assertions and fingerprints,
not account IDs, provider resource IDs, credentials or customer data.

Only fixture initialization and read-only control calls retry bounded provider
failures. Admissions, claims, renewals and other mutations are never blindly
retried. Whole-request natural-key retry and lost-response behavior are explicit
cases. Run failures remain failures and retain their partial report for diagnosis.
A new proof uses a fresh isolated namespace.

## Admission transaction

The adapter validates the complete 1–60 group selection and binding, then
rechecks installation/current credential, binding ownership/revision, linked
account and existing-photo proof age inside one D1 batch. A constraint-backed
`transaction_guards` row supplies the transaction's database clock and asserts
its preconditions. It is deleted in the same transaction; it is not a retained
receipt or a second client idempotency key. No request body or credential digest
is stored in that row.

All missing intents, counter increments, due projections and retained events
commit together. Per-row SQLite triggers allocate from the committed partition
counter and append admission history; rollback restores every counter and row.
JSON-bound input keeps the 60-group operation within a small fixed statement
count. Existing exact pairs retain their state, identity, position and blocks.
Response ordering follows the request solely for reconciliation. The adapter
publishes at most one canonical-lowest newly eligible partition hint after the
batch returns successfully. A hint failure leaves the durable due rows intact.

## D1 and Durable Object boundary

D1 owns queue state, exact due time, lease ID/generation, gates and retained
history. The object owns only its routing metadata and advisory alarm. Its
constructor identity is diagnostic, never a fence. Every hint, alarm and sweep
uses the same conditional D1 claim. Integer ordinals, generations and due times
cross JavaScript boundaries as decimal strings. Worker wall time schedules only
an advisory alarm; D1 decides whether work is actually due.

| Failure boundary | Recovery |
| --- | --- |
| Admission commits; hint disappears | The due row remains discoverable by the sweep |
| Duplicate or stale hint | D1 permits at most one current lease; stale revision is a no-op |
| Claim commits; response disappears | Lease remains; a successor can claim after database-clock expiry |
| Object resets while a lease is held | Routing metadata survives; D1 lease/fence remains authoritative |
| Deferral commits; alarm is lost | Exact D1 due time survives and the sweep uses the same claim |
| Alarm is early or stale | Recheck due time, active head, gates and lease in D1 |
| Old owner returns after takeover | Renew, release and deferral reject its old generation/lease ID |
| Invocation deadline passes | Renewal is refused even when the lease has not expired |

The default candidate lease and invocation limits retain the accepted 60/45
seconds. A few isolated expiry/deadline tests use explicitly shorter fixture
policies; those are not Flickr timeout or monotonic-freshness conformance.
The probe actor deliberately performs no add attempt after obtaining its lease.
Dispatch markers and abandoned `attempting` recovery remain #0006 work; this
adapter refuses to treat an unresolved attempting head as ordinary queued work.

The hosted scheduling run waits for real provider `scheduled` events, checks two
successive minutely timestamps, then proves recovery of an unhinted partition.
Cron changes can take up to 15 minutes to propagate. The controller distinguishes
that startup wait from the measured recovery interval. A local manual sweep does
not claim hosted Cron execution. Mutation cases are not retried into a pass.

## Archives and teardown

The admission run removes its Worker before exporting the complete selected D1
schema and data to another fresh, unexposed database. SQLite numeric literals
and byte-preserving text literals avoid JavaScript integer rounding. The restore
creates tables/indexes, loads historical rows, then recreates triggers; enqueue
triggers must not allocate new positions or events while loading old history.
The clone is checked for exact rows, schema guards, foreign keys and protected
history rejection before teardown. The original #0007 archive remains scoped to
its earlier migration head; this proof covers the additional relations.

Scheduling cleanup uses Wrangler's supported declarative `exports` tombstone
for the exact generated class. It removes the class and binding from an inert
replacement Worker and clears the cron declaration, verifies that the recorded
namespace is absent, then performs the existing non-forcing Worker deletion and
identity-checked D1 deletion. It refuses unexpected namespace associations or
changed IDs. No other Worker binding is removed to force retirement.

```powershell
uv run --frozen python scripts/coordination_probe.py cleanup --run .coordination-runs/rp-<24-hex-digits>
```

The source manifest also records its archive target, so cleanup handles that
specific child database. Keep manifests until all cleanup is confirmed. A failed
cleanup is reported; it is never replaced with a blanket resource deletion.

## Scope still outside these cards

The public mutation handler, complete installation/binding wire errors, exact
public block/response schemas, registry/configuration bound agreement and the
real official-client no-slicing tests remain integration work. These internal
adapter results must not be published as the final HTTP response shape.
The full CBA and fail-polite release suites, production backups, real LrC/TLS,
Flickr rate reservations and monotonic dispatch timing remain separate gates.

## Bounded fail-polite crash proof

`uv run --frozen python scripts/coordination_probe.py local fail-polite` runs the
candidate attempt/marker/result adapter against local workerd/D1 and a loopback
HTTP fixture. `uv run --frozen python scripts/coordination_probe.py hosted fail-polite`
uses disposable Cloudflare D1, a SQLite Durable Object, and a controlled HTTPS
peer. The hosted run additionally exercises real Cron, stops the source Worker,
and restores all selected domain tables into a second unexposed D1 database.
Both commands return nonzero on an assertion or cleanup failure. The existing
`cleanup --run <private-run-directory>` command handles interrupted hosted runs.

The harness records ten crash boundaries through both hint and sweep entry
paths, durable before/after witnesses, observed POST counts, result-code
classification, immutable history guards, and injected monotonic boundaries.
Actual Durable Object abort/recreation replaces the actor; this does not claim
an independently terminated operating-system process. Test leases are one second
locally and ten seconds hosted; persisted lease time comes from D1. The hosted
peer sees real HTTPS requests and records whether the marker was already durable.
Only synthetic identifiers and the disposable proof bearer are used. The public
API imports neither this fixture nor its Flickr transport.

`uv run --frozen python scripts/fail_polite_mutations.py` checks six isolated local
source/migration mutations with passing unmutated controls. It temporarily changes
one source file at a time and restores the original bytes in `finally`; do not
run it alongside builds or proofs. It writes sanitized evidence under
`docs/evidence/`. These checks cover missing dispatch markers, retryable unknown
results, replayable abandoned dispatches, inclusive freshness, separated blocks,
and a removed ordinary-write guard. They are not the complete production
mutation inventory. `--mutation-check` selects one diagnostic assertion and is
never a replacement for the full crash profile.

This is a bounded native-storage proof, not production fail-polite conformance.
The fixture provides its own transport, deterministic reservation allocator and
manual clock. Ticket #0013 still owns deployed Workers freshness enforcement.
The production OAuth transport/rate allocator, complete protocol and retry
coverage, public admission/status/admin integration, independent process-stop
coverage, and the complete accepted case/mutation inventory remain release gates.
No release capable of a real `flickr.groups.pools.add` is enabled by these results.
