# PMB-1 explicit D1 reservation advancement

Date: 2026-10-19. Ticket #0206. Source/synthetic implementation; independent High
review pending. This extends the reviewed [one-transition adapter](pmb1-d1-adapter-2026-10-19.md)
under the accepted [PMB-1 source contract](prospective-maintenance-contract-decision-2026-10-18.md).
The historical adapter handoff and Completed #0185 SQL/manifest are unchanged.

The [inert adapter](../../probes/pmb1-d1-adapter/README.md) now offers explicit
receipt-bound successor reservation. Initial intent defaults to one transition;
an exact finite campaign declares two (close/reopen) or three
(bootstrap-reopen/close/final-reopen) before initial latch and reserves every
signed-int64 increment. The accepted contract
[bootstraps CLOSED](prospective-maintenance-contract-decision-2026-10-18.md#d1-schema-and-fixed-operations);
a campaign exercising open writes before closure needs all three slots under
continuous custody. This source does not force such a campaign or authorize it.
The successor preserves target, candidate,
window and root limits, reverses the operation and binds the adjacent generation.
It receives no automatic action authority.

- A separate append-only confirmation port reads an independently retained
  `CONFIRMED` artifact by exact reference. It must authenticate the actual timely
  returned confirmation's provenance, with its exact immutable intent, one-row
  commit and independent complete control/schema readback evidence. A caller's
  dataclass or the journal's persisted phase cannot supply that evidence.
- One journal transaction compares the current exact confirmed predecessor,
  consumes its receipt reference, retains immutable consumed history and reserves
  one successor. It never releases target custody or resets root counters.
- A lost, late or malformed successor reservation acknowledgment cannot dispatch
  or resume the reserved successor. Uncertain final transition acknowledgments
  cannot produce a valid retained confirmation, even after confirmed persistence.
- All root operations share the original finite window, two reconciliation
  attempts and a fixed total read ceiling: eight for one transition, sixteen
  for either two or three. The third slot does not increase the former pair
  ceiling or any actual packet budget. Generation exhaustion, stale bindings and
  exhausted bounds refuse; no expiry release, fresh-key/backend bypass or automatic reopen.

Thirty-seven adapter tests use the full public migration-derived SQLite fixture
and fixed reviewed SQL. They cover valid close/reopen and the complete three-step
bootstrap campaign, third-slot acknowledgment loss/budget refusal, fourth-slot
exhaustion and complete schema/control
queries, exact TEXT/int64, wrong bindings/predecessor/candidate, malformed or
unavailable prior receipts, uncertain final acknowledgments, crash/ack faults
before/after persistence, restart, concurrent/duplicate successors, headroom,
root exhaustion, shared budgets and deadlines. The nineteen unchanged #0185 SQL
tests also pass. Pinned Ruff check/format and canonical Standard Pyright pass;
the private handoff records exact pinned tooling and reproduction details.

The synthetic ports are interaction/fault models, not actual durability,
authenticated provenance, independent hosted observation, D1 atomicity or
continuous real custody proof. No concrete journal/custodian/backend/provider
binding is supplied. Future use must qualify their same-target correspondence,
atomic compare/reserve behavior, crash persistence, append-only receipt producer
authentication, shared bounds and stable monotonic restart domain. Distinct
objects and matching strings do not establish those external properties.

All actual backend/provider, #0182 all-store and production qualification remain
**false**. Source progression is not permission to reopen: exact action authority,
stale-work disposition, writer settlement, schema embargo and every other PMB-1
gate remain independently required. This work connected no actual journal,
private store, credential, account/provider, DNS or native surface and performed
no schema/install/deploy/capture/cleanup/reopen action. The historical exact-original
NO-GO and paused production write gates remain controlling.
