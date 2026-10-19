# PMB-1 actual partition worker source bridge

Date: 2026-10-19. Ticket #0197. Status: **Unregistered source integration;
synthetic actual-handler verification passes. Fresh independent High review
required. Actual all-store/native qualification remains false.**

The [accepted source contract](prospective-maintenance-contract-decision-2026-10-18.md#future-artifact-durable-objects-and-other-writers)
and [positive native wake-up primitive](pmb1-native-wakeup-2026-10-19.md)
control this integration. The reviewed prior probes remain unchanged.

[PartitionWorker](../../src/dispatch_worker.ts) now accepts a trusted composition
factory for [PartitionMaintenance](../../src/partition_maintenance.ts). Existing
ordinary source remains usable without that factory. The future retained
candidate assembly must install/require the bridge for every included object;
an absent bridge is not maintenance coverage. No environment string, HTTP
payload or new endpoint grants maintenance authority. Construction/restart
does no storage write, initialization, rearm or reopen.

The actual `fetch` and zero-argument `alarm` synchronously capture immutable
control before their first await. Transactional admission rechecks that same
generation and admission flag, retaining an invocation across `waitUntil`, D1
calls, native wake work and results. Partition binding uses fixed guarded SQL.
Advisory arms use the reviewed transactional SQL/KV/explicit-alarm primitive;
native callbacks select current due work rather than inventing an event/arm
identity. Its local revision remains distinct from the D1 wake revision, lease
generation and exact attempt authority.

The additive [fail-polite lifecycle seam](../../src/fail_polite.ts) records the
immutable D1 claim invocation before the claim call, the returned lease, the
exact original attempt tuple and original grant snapshot. It checks new work
before provider stages and durably admits the external dispatch boundary after
the existing D1 dispatch marker. The final live preflight test and handoff still
have no intervening await. A permission that wins the stop race is a retained
external obligation, never evidence that its network result already settled.

Admission stop prevents new handlers, scheduling and dispatch permissions.
An already admitted external result still runs the actual `resolveAttempt`,
permanent exact-pair suppression, unknown-code gate pause, matching grant
retirement and unused rate-reservation release. Those domain transactions and
classifications remain authoritative and unchanged. The local invocation can
settle only after fixed reads confirm the exact attempt resolution, permanent
block when required, grant retirement or successor fencing, and zero unreleased
reservations. The native binary receipt follows this domain receipt; it never
substitutes for it.

Result rollback, unknown claim acknowledgment, unbound attempt, failed local
receipt and unfinished callback remain durable unresolved obligations.
Restart does not remove them. Explicit exact-token reconciliation performs no
POST, resolution, retirement or release replay. It requires separately qualified
independent evidence that the old execution cannot resume and its outstanding
D1 operations settled, then confirms the fixed domain facts. Missing evidence
refuses by default. In particular a claim that committed without its lease
binding remains unconfirmed rather than being adopted under fresh authority.

Close first requires admission stopped and no active invocation/native execution.
It then disposes the advisory schedule and uses the reviewed fixed local close.
Mandatory results settle while storage is open. Reopen delegates to the exact
generation independent disposition verifier; fixture answers are not evidence
that actual old versions, callbacks or native metadata are disposed.

The explicit isolated source bootstrap first creates the reviewed closed native
schema, then adds the bridge tables and their unrestricted ordinary guards in a
closed transaction. It is not a production migration or atomic all-store setup
claim. A failed phase retains closed/unusable state; no handler repairs it.
Actual schema/guard installation, manifest completeness and bootstrap receipts
belong to the later finite candidate packet.

Verification uses Node 24.22.0, pinned native TypeScript 7.0.2 and the actual
PartitionWorker/fail-polite code against SQLite domain transactions plus the
reviewed SQL/KV/alarm-shaped storage fixture. The fixture serializes D1 batches
and object transactions; it is not provider concurrency or scheduling evidence.
`tests/partition_maintenance.test.mjs` covers real permanent suppression,
unknown-code pause, grant retirement/successor fencing, duplicate/concurrent
hints, current durable alarm admission, stop races, D1 rollback, local result
faults and exact restart reconciliation without effect replay.

Actual automatic delivery/removal/retry metadata, complete independent internal
state/reader, effective old-writer exclusion, object/version census, local and
D1 transaction linearization, exact bootstrap/candidate wiring and independent
reopen disposition remain unqualified. No provider, private credential, DNS,
native control, schema installation, deployment, capture or cleanup occurred.
This source does not pass #0182 or permit a new runtime action.
