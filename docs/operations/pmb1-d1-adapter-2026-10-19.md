# PMB-1 fixed D1 adapter source candidate

Date: 2026-10-19. Source/synthetic scope; independent High re-review passed.

The [inert operator adapter](../../probes/pmb1-d1-adapter/README.md) wraps the
immutable reviewed #0185 SQL/manifest under the accepted
[PMB-1 contract](prospective-maintenance-contract-decision-2026-10-18.md).
Its external durable-journal interface latches an immutable intent and reserves
the bound singleton before one dispatch. Every outcome retains the reservation,
including confirmed/refused, so lost/late final acknowledgments block new keys
and replay. Exact canonical TEXT preserves signed-int64 generation.

- Fixed single-statement provider boundary; no caller-selected SQL/control target
  or ordinary-work batch. Require an exact one-row committed receipt.
- Separate complete primary control and ordered schema readback with every
  candidate definition/guard pinned; source pins rechecked throughout.
- Durable shared read/reconciliation budgets and immutable finite monotonic
  windows; failed/late effects remain unknown without retry or automatic reopen.
- Read-only reconciliation records current observations without manufacturing
  a missing commit receipt, clearing the unknown reservation or claiming closure.

Twenty-three adapter tests execute the fixed SQL over the full public migration
fixture and inject journal, receipt, readback, schema/guard, generation, budget
and deadline faults. They also check that guarded ordinary batch failures roll
back their earlier fixture writes. The unchanged nineteen #0185 tests preserve
the broader domain/guard boundary coverage. Local SQLite and synthetic ports do
not establish hosted atomicity or independent readback.

This is one transition per target reservation; outcome recording cannot release
or transfer it. Subsequent lifecycle advancement needs a separately implemented
and independently reviewed source protocol before close/reopen can be chained.
That faithful source work does not create a new owner policy decision gate.
Lost terminal outcome acknowledgments do not disable bounded independent
read-only reconciliation: the durable dispatch marker is separate from outcome.

No concrete provider transport or durable journal backend is connected. Future
qualified bindings must establish exact same-target correspondence, atomic
journal reservation/consumption across restarts, authoritative independent
primary readback, actual D1 commit/batch and close ordering, schema embargo,
and stability for migration/sequence/bookkeeping/internal state ordinary guards
cannot cover. The README records the exact port obligations and source limits.
Full all-store equality/REAL reading, admitted-work disposition and every other
PMB-1 gate remain independently required. Actual D1, #0182 all-store and
production qualification remain **false**.

This source adds no active registration, migration, deployment or action command.
It accessed no private record, credential, provider/account/DNS or native surface;
it authorizes no install/capture/restore/cleanup/reopen. Completed #0185 artifacts
remain byte-identical. The historical exact-original NO-GO and existing paused
production write gates remain controlling.

## Independent review and integration

Corrected source passed independent High re-review. Terminal outcome recording
no longer releases the target reservation; persisted-but-unacknowledged or late
settlement cannot permit a fresh-key/restart dispatch. Twenty-three adapter
and nineteen unchanged tests plus static gates pass. The reviewer reproduced
the original failure and bounded observation after multiple lost acknowledgments;
the parent reproduced twenty-three installed tests. The positive primitive is
one transition only. Follow-up #0206 supplies explicit receipt-bound advancement
before #0200 may assume a multi-transition lifecycle. Actual journal, provider,
readback and #0182 qualification remain unpassed.
