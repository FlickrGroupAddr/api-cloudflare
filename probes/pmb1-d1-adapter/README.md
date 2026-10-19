# PMB-1 fixed D1 operator and readback adapter

Inert source/synthetic seam only. Actual D1 and all-store qualification remain
**false**. The [accepted PMB-1 contract](../../docs/operations/prospective-maintenance-contract-decision-2026-10-18.md)
controls behavior. No provider client, credentials, resource selector, action CLI,
Worker registration, active migration or installation is supplied.

`adapter.py` binds the immutable [#0185 source](../pmb1-d1/README.md) by eleven
SHA2-256 byte pins. It loads verified bytes for the fixed close/reopen and complete
control/schema queries; SQL, tables, target state and next generation cannot be
selected by a caller. The manifest pins the complete synthetic candidate schema,
all ordinary guards and existing domain guards. Canonical positive decimal TEXT
binds signed-int64 generation exactly, including values above JavaScript's safe
integer ceiling. Exhaustion refuses before dispatch.
The initial immutable intent reserves one transition (the default), an explicit
close/reopen pair (`transition_limit=2`), or a bootstrap-reopen/close/final-reopen
campaign (`transition_limit=3`). The initial latch requires signed-int64 headroom
for the entire selected campaign. The successor keeps the same finite window
and limit; no counter reset or emergency opening
is available. This narrow source ceiling does not authorize a lifecycle action.

The operator orchestration is Python because it is an external journal/SQL
adapter with finite local fixtures, outside the Worker runtime. This avoids a
second int64 representation through JavaScript numbers. Future Worker code must
use its own reviewed integration; this module is not deployed Worker code.

## Port contracts and sequence

Only injected `Provider`, `Observer`, `Journal`, optional independent
`Confirmations` custodian and monotonic `Clock` protocols cross an effect boundary.
`Adapter` requires an exact bound `target_id`; an intent repeats that identity
for comparison, never to select or redirect a provider target. The test implementations have no network capability.
The provider exposes exactly one fixed UPDATE, with a canonical TEXT parameter,
as a standalone qualified commit boundary. It has no ordinary-work batch method.
A future provider transport must normalize its qualified receipt to exactly
`{'success': True, 'changes': 1}`; booleans/floats/coercion, missing/extra fields,
negative/multiple changes and unsuccessful receipts do not confirm mutation.
A well-formed zero-change acknowledgment is refusal, never idempotent success.

1. Validate finite window, exact candidate/source pins and generation; durably
   latch the whole immutable intent in an EXTERNAL journal before any dispatch.
   The journal's atomic latch also reserves the bound singleton target: any
   existing intent prevents another latch under any key, for every outcome phase.
2. Spend durable read budget and independently obtain the whole control relation
   and complete ordered schema. Require expected typed state/generation and every
   pinned definition, including guards; no first-row or filtered shortcut.
3. Durably claim dispatch once, recheck source/time and send the fixed UPDATE once.
   The writer receipt must report exactly one changed row after commit.
4. Separately execute both full queries through the bound primary observer;
   require exact next typed state/generation and schema/guard pins. Durably record
   confirmation, then recheck the deadline before returning `confirmed` with
   its final monotonic acknowledgment time. No failed or late result has that time.

The journal's methods are atomic durable operations across crashes/processes.
No interface deletes/expires a latch, resets counters or releases custody.
Recorded confirmed/refused outcomes retain the reservation: their final journal
acknowledgment or the subsequent deadline check may fail. The permanent
dispatch-claimed marker remains separate from the recorded outcome, so bounded
read-only reconciliation can still observe after a lost terminal acknowledgment.
A source failure before dispatch refuses without sending. An ambiguous dispatch
claim, lost acknowledgment, timeout, malformed/mismatched receipt, failed readback
or failed outcome persistence remains unknown. A retained intent cannot dispatch
again after process restart or under a fresh key. Refusal never asserts that the
whole store is closed or that other actors settled.

## Explicit receipt-bound advancement

Ordinary `close`/`reopen` calls still reserve one transition; a returned confirmation
never implicitly releases them. A separately scoped two- or three-transition intent must
select its limit before initial latch. Only the explicit call
`advance(exact_predecessor, exact_successor, retained_reference)` can progress it.
The new operation proceeds in this order:

1. Validate both immutable intents against the adapter's exact bound target and
   candidate. Require a new successor key, reverse operation and adjacent
   generation, with the original window and transition limit unchanged.
2. Read the exact `CONFIRMED` artifact from the independent append-only external
   custodian. Require the exact predecessor and complete timely returned result:
   one-row/independent-readback outcome, exact observed generation/state and a
   finite final acknowledgment time inside the original dispatch window.
3. Atomically compare and consume the current predecessor and retained reference,
   record their permanent successor linkage, and reserve the exact successor.
   The journal requires confirmed dispatch, fresh key, unused receipt, remaining
   root ordinal/headroom and the same binding/window/limit. No unreserved interval
   is exposed. Consumed predecessor records cannot be rewritten.
4. Only a literal `True` acknowledgment followed by a timely source check permits
   the successor's complete pre-read, one dispatch and complete post-read. A
   persisted successor whose reservation acknowledgment is lost, malformed or
   late stays reserved and cannot resume through restart, duplicate advancement
   or a fresh key. A crash before reservation persistence leaves the original
   custody in place; this adapter performs no automatic retry.

The custodian is a **separate trust boundary**, not a journal phase query, caller
assertion or receipt synthesized from current state. Its qualified binding must
independently authenticate the actual returned confirmation's producer/custody
and retain the associated exact one-row commit and full primary readback evidence.
A caller-constructed `Result`/`ConfirmedReceipt` is not evidence. No receipt-writing,
attestation or durable custodian implementation is supplied. The positive test
custodian models known actual returned results only and establishes no real
independence. Distinct Python objects are necessary but insufficient proof of
independent production custody and provenance.

If final outcome persistence succeeds but its acknowledgment is lost or late,
the operation returns unknown and supplies no confirmation artifact. A phase of
`confirmed`, a response echo or later matching read cannot repair it. Unknown,
refused, missing, malformed, wrong-binding or late prior confirmation refuses
advancement. Replacing the journal/backend, expiring a window or issuing a new
key cannot bypass custody. Reopen additionally needs its own exact action scope,
stale-work disposition and all PMB-1 gates; the receipt grants none of those.

The exact immutable window is checked before and after each port operation and
source verification; backwards/nonfinite clocks refuse. There are at most eight
post-latch observer calls for a one-transition root, or sixteen for an explicitly
reserved two- or three-transition campaign, and two reconciliation attempts for the entire root. Shared
counters are durably spent BEFORE use and never reset by advancement.
The source ceiling is five minutes; a later exact packet must choose its narrower
continuous dispatch/reconciliation deadlines. Recovery cannot extend a window
or change the operation/generation. Port implementations must honor the supplied
deadline, retain the same clock domain across restart, and have no internal
retry. Synchronous callbacks cannot be forcibly interrupted by this source;
a hung or late callback is an actual transport qualification failure.

## Read-only reconciliation

`reconcile` accepts only the exact durable dispatch-claimed intent and spends its same
stored bounds. It sends no UPDATE and never clears an unknown reservation. A
matching result is `observed`, meaning the current target was read independently;
it does **not** reconstruct a missing one-row commit receipt or prove ordering,
writer settlement, a common closed interval or permission to proceed/reopen.
An observation of the old state cannot prove a still-pending dispatch will not
commit later. No fallback, replay, new generation, repair or automatic reopen is
implemented. Separate authorized recovery/qualification owns any next action.

## Verification and remaining qualification

Run in the API repository using the existing pinned environment:

```text
uv run --frozen python -m unittest discover -s probes/pmb1-d1-adapter -p test_*.py -v
uv run --frozen python -m unittest discover -s probes/pmb1-d1 -p test_*.py -v
uv run --frozen ruff check --no-cache probes/pmb1-d1-adapter
uv run --frozen ruff format --check --no-cache probes/pmb1-d1-adapter
```

The thirty-seven adapter tests use the full public migration-derived in-memory SQLite
fixture. They exercise exact int64/TEXT, SQL selection, actual transition and
independent SELECT execution, uncertain journal acknowledgments, stale preflight
and race/zero receipts, malformed commit acknowledgments, new-key/restart replay
refusal, read budgets, deadlines, byte/schema/guard drift, missing readback,
receipt-only false success and transactional rollback of a guarded ordinary
write. Persisted confirmed/refused/unknown outcomes with lost or late journal
acknowledgments remain reserved across restart, changed keys and fresh windows;
failed unknown-outcome acknowledgment cannot release or prevent bounded read-only
observation. The additional advancement matrix covers the valid fixed-SQL pair
and the complete bootstrap-reopen/close/final-reopen campaign, including uncertain
third-transition acknowledgments, fourth-slot refusal and shared sixteen-call bound;
exact retained confirmation, wrong predecessor/target/candidate, malformed result
and timing, duplicate/concurrent successors, crashes and lost acknowledgments
before/after reservation and final persistence, root exhaustion/headroom, shared
budgets and late receipt reads. The unchanged nineteen #0185 tests retain the
broader SQL/domain fault matrix. Standard Pyright uses the repository's canonical rules, projecting only
source/import/venv paths to include this standalone probe.

The synthetic journal is an in-memory interaction model, **not durable storage**.
The synthetic observer performs new complete SELECTs, **not response echoes**;
it shares the local fixture connection and proves no hosted independence or
consistency. The synthetic writer uses SQLite autocommit; the ordinary batch
fault uses #0185's explicit transaction helper. Neither qualifies D1 transaction
or batch rollback, close linearization, authoritative primary freshness,
bookkeeping/internal state stability or actual target/resource correspondence.

Actual use requires a separately qualified durable journal and independent
confirmation custodian with authenticated append-only receipt provenance, bound
writer and primary observer for the SAME exact target, stable clock/deadline transport,
exclusive custody/schema embargo, complete hosted schema/guard census,
bookkeeping/internal-state stability, and actual before/after-close commit
ordering and batch fault evidence. The fixed synthetic schema cannot stand in
for a qualified hosted manifest; unexpected state refuses. All-store typed
snapshot/REAL reading, object fences, admission/settlement, retained artifact,
restoration and separate action authority remain outside this seam. This source
cannot pass #0182, authorize any action, or establish production eligibility.

The dated [advancement source handoff](../../docs/operations/pmb1-d1-advancement-2026-10-19.md)
records #0206's scope, verification and unqualified backend/custody boundary.
