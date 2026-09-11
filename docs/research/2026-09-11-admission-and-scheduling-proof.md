# Atomic D1 admission and Durable Object wake recovery

Date: 2026-09-11. Implementation cards #0004 and #0005, under parent #0002.
Status: Both bounded proofs pass and are ready for review. Full production
admission/dispatch conformance remains separate.

Terry authorized the next two highest-priority executable tickets through Needs
Terry or Ready for review without further intervention. The board's first entry,
#0002, is the umbrella plan; its next concrete P1 children are #0004 and #0005.
The accepted architecture baseline is `286b972` in architecture-design. ADRs
0015, 0020, 0033 and 0050–0054 plus the binding, admission and persistence
contracts control this work. The prior #0007 scoped D1 proof has passed.

## Scope

Build and test a production-shaped D1 transaction adapter for a complete
one-photo group selection (1–60 unique group IDs). Derive photo/owner/source
from the existing verified binding, enforce its installation/owner/link/revision
and 15-second existing-photo proof rules, preserve global exact-pair identity,
allocate committed per-partition FIFO ordinals, and preserve permanent blocks.
One transaction must contain all inserts, ordinal/due changes and events.
After commit the adapter may send only one hint for the canonical-lowest newly
eligible partition; fully idempotent retries and appended non-head work send none.
Hints are disposable, and hint failure cannot undo committed admission.

D1 remains the sole authority for partitions, ordinals, exact due times,
lease IDs/generations, gates and retained events. The DO candidate coordinates
wakeups and alarms only. Every hint, alarm and minutely sweep returns through
the same D1 conditional claim. No transaction is assumed to span D1 and DO
storage. Lost alarm/hint writes recover through indexed D1 due sweeps. Test
concurrency, expiry, renewal/release fencing, process eviction and stale-owner
rejection without any Flickr operation. Lease generations and ordinals use
signed-64-bit SQL values and text projections across JavaScript boundaries.

This is the bounded adapter/provider proof requested by the two cards, not a
claim that the full courteous-admission or fail-polite release suite has passed.
Actual Flickr dispatch/markers and monotonic preflight belong to #0006/#0013;
production auth/UI integration, official-client no-slicing and production timing
remain separate. Synthetic fixture controls must stay outside the public API
entry point. No new service is justified merely because an API is inconvenient.

## Results

The implementation snapshot is `f0341af`. Every report verifies unchanged source
fingerprints for the run and records its exact compatibility date.

| Proof | Result |
| --- | --- |
| [Hosted D1 admission and archive](../evidence/coordination-admission-hosted-2026-09-11.json) | 34 checks pass |
| [Hosted DO scheduling and recovery](../evidence/coordination-scheduling-hosted-2026-09-11.json) | 31 checks pass |
| [Local D1 admission](../evidence/coordination-admission-local-2026-09-11.json) | 31 checks pass, including zero external calls |
| [Local D1/DO scheduling](../evidence/coordination-scheduling-local-2026-09-11.json) | 30 checks pass, including zero external calls |
| Repository Python / existing Node and Worker tests | 73 / 36 pass |
| Native TypeScript 7.0.2, Ruff, Pyright | Pass |

All hosted checks passed on the first hosted run of each profile. Mutation
requests are not automatically retried. Read-only control retries and explicitly
idempotent fixture setup are bounded and retained in the reports. The local
preparation initially tested new due work through only the first 64 results of a
bounded sweep; that assertion was corrected to inspect its exact due rows. It
was a fixture population issue, not permission to claim an unbounded scan.

The hosted admission run proved complete 60-group admission, concurrent
identical and distinct requests, immutable exact-pair reuse, binding revision
race rejection, rollback after all seven transaction statements and within a
multi-row insertion, unchanged ordinals after rollback, and zero-or-one
canonical hint after commit. Values at/above the JavaScript exact-integer limit
remain exact strings; signed-64-bit exhaustion refuses the whole batch instead
of wrapping or committing partial state. An expired existing-photo proof permits
only fully idempotent reuse. Permanent blocks and retained events are preserved.

The new schema was exported with its source Worker removed, imported into a
fresh unexposed database, and compared exactly across all 14 selected domain
and migration tables. Tables/indexes are restored before rows, and triggers are
installed after historical rows so queue allocation and event triggers do not
replay during restore. Exact data, schema guards, foreign keys and append-only
rejection all passed. This extends archive evidence to migration 0003 rather
than assuming the earlier #0007 export covered the new relations.

The hosted scheduler proved one conditional lease winner, wrong-ID/stale-generation
rejection for renewal/release/deferral, exact future due time, no early claims,
paused-gate stability, large fencing generations, and bounded invocation renewal.
A deliberately lost claim response still left a durable lease that could be
reclaimed only after database-clock expiry. Actual `DurableObjectState.abort`
reset the object while D1 retained authority; a persisted alarm survived another
reset and claimed only after the database due time. Deleting an alarm was
recovered through the same sweep/claim path.

Real provider Cron events, not a simulated HTTP callback, demonstrated a
60,000-millisecond scheduled interval. An unhinted partition was then recovered
by the next actual Cron delivery, with an observed 59,494-millisecond delay
from its database due time. This is the measured fixture result, not an uptime
or latency guarantee. The initial Cron propagation wait is distinct from that
steady-state observation.

[Cleanup evidence](../evidence/coordination-cleanup-2026-09-11.json) confirms that
all three temporary databases, two Workers and the one Durable Object namespace
were removed. The DO class used the supported declarative `exports` retirement
path; its namespace disappearance was verified before non-forcing Worker and D1
cleanup. No production resource or Flickr credential was used.

## Implementation and authority

`src/admission.ts` and `src/scheduling.ts` contain the reusable internal adapters.
`migrations/0003_submission_coordination.sql` adds their candidate relations and
SQL guards. The private fixture actor and its control endpoints live only under
`probes/coordination/`; they are absent from the public API entry point.

D1's batch API has no application transaction callback. A small constraint-backed
`transaction_guards` row supplies a batch-local assertion and clock. It is
inserted and removed in the same transaction, leaving no retained request receipt
or client idempotency key. All client-derived values are bound parameters.
Counters, due projections and admission events change with the intent insertion
inside that same database transaction. The hint sink is invoked only after it
commits. This is one database transaction, not an outbox or another service.

The DO holds only routing metadata and an advisory alarm. A wall-clock-based
alarm cannot grant authority: every wake rechecks D1 due time, gates, head and
lease. Hint/clock/cache failures can delay a wake, but cannot grant a second
lease or change a durable ordinal. The minutely D1 sweep is the backstop.
The [reproduction and failure-boundary guide](../../probes/coordination/README.md)
records each cross-service boundary and teardown procedure.

## Remaining integration scope

These passes complete the bounded mechanism work on #0004/#0005. They do not
instantiate every production CBA or fail-polite test. Follow-up #0017 tracks the
public authenticated batch endpoint, verified photo-intake integration, exact
wire response/block shapes, compiled route/configuration bound agreement and
official-client no-slicing/mutation evidence. The internal adapter's returned
ordinal/hint fields are not a public API schema.

#0006 owns actual attempt/dispatch-marker/result recovery and Flickr operations;
#0013 owns hosted monotonic preflight timing. The scheduling candidate never
performs a Flickr attempt and refuses to treat an unresolved `attempting` head
as queued work. The 60/45-second default lease/invocation policy is retained;
shorter expiry tests are explicitly synthetic. Production backup scheduling,
D1/DO quiescence at operational restore, full security integration and real
LrC/TLS evidence remain their own gates. The existing stable development-tool
advisories are unchanged; no new dependency or AWS service was added.

## Provider references

[Cloudflare D1 batch API](https://developers.cloudflare.com/d1/worker-api/d1-database/#batch)
documents transactional batches with whole-sequence rollback on error.
[DO alarms](https://developers.cloudflare.com/durable-objects/api/alarms/),
[DO state](https://developers.cloudflare.com/durable-objects/api/state/) and
[Worker Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
provide the candidate wake mechanisms. Their documented behavior must be tested
against the hosted runtime; emulator results alone are not that evidence.
