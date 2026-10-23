# Separate D1 main-entry journal

This is concrete source for the PMB-1 `MainEntryJournal` port, using a **new,
separately owned D1 database outside every compared application/object store**.
It supplies guarded fixed SQL, construction from a Workers D1 binding, durable
invocation/effect history, irreversible admission stop and bounded observation
pages. It is not managed-provider qualification or a complete retained Worker.

## Construction and provisioning

Apply `schema.sql` only to the independently reviewed new external journal D1,
then execute `provision.sql` once with parameter bindings for its actual D1 UUID,
candidate SHA2-256 digest, lifecycle and canonical positive signed-int64 generation
TEXT. These files are source preparation, not authorization to create or modify
an actual database. No constructor installs, seeds or replaces anything.

`D1MainEntryJournal` in `journal.ts` takes:

- Environment `{ PMB1_MAIN_JOURNAL: D1Database }` with the real Workers binding.
- Trusted configuration `{ binding, journalDatabaseId, comparedDatabaseIds }`.
- Optional monotonic clock for deterministic tests; production uses
  `performance.now()` in the same clock domain as `MainEntryMaintenance`.

The configured journal UUID must differ from every compared D1 UUID. Each fixed
operation also matches the provisioned UUID, schema version and complete binding.
Configuration and that stored identity are checks against accidental mismatch;
they do not prove which resource an actual Workers binding addresses. The actual
binding/resource inventory and exclusive custody still require independent proof.
Do not copy this schema into the application migrations or a compared store.

The static Worker assembly must keep `PMB1_MAIN_JOURNAL` in its trusted outer
composition and omit it from the environment projected to ordinary handlers.
Construct the journal before passing it to `MainEntryMaintenance`; no HTTP route
or user input selects a journal, source binding, SQL statement or lifecycle.
All old effective versions/callers must actually use this same authority before
an admission-stop claim can cover them. Software cannot retrofit an old writer.

There is one exact lifecycle per journal database. Its binding cannot change,
its history cannot be deleted through ordinary guarded SQL, and stopped
admission cannot reopen. A new lifecycle requires separately reviewed new
external provisioning; it cannot silently reuse/reset this singleton.

## Atomic operations and uncertainty

`PMB1_JOURNAL_SQL` exports the fixed parameterized operation manifest.

- `admit` inserts the unique invocation iff the exact control is open. An
  acknowledged insert returns its exact lease; refusal returns `null`.
- `effect` inserts a unique effect only for its exact still-unreturned invocation.
  It remains permitted after stop: already admitted handlers must retain their
  fixed safety/result authority. It grants no new handler or storage reopen.
- `settled` changes that exact pending effect once to the observed local
  fulfillment/rejection. Rejection remains retained; it does not mean a provider
  mutation failed. Settled/returned fields cannot be overwritten or cleared.
- `returned` records one handler result only when all its effects have recorded
  outcomes. A pending body, cancellation or lost effect latch prevents return.
- `stop` atomically updates open admission and reads its persisted evidence in
  one D1 batch. Repeated explicit stops retain the original evidence. Every new
  instance matches the same persisted authority, so restart cannot reset it.

Each method sends its mutation once and performs no application retry. A failure,
malformed receipt or lost acknowledgment refuses further authority; it never
assumes rollback. An admitted-but-unacknowledged invocation remains unreturned;
an effect with unknown disposition remains pending. A successfully persisted
settlement/return remains visible after acknowledgment loss, with its exact
outcome. Observers must reconcile the retained records and independent domain
state, not fabricate a successful result or clear obligations.

Stop/page validate the supplied monotonic deadline before and after the SDK
await. **The D1 binding API does not provide an AbortSignal for a dispatched
query.** A caller deadline cannot cancel that query or prove that it terminated.
`MainEntryMaintenance.stop` owns its bounded outer wait; a delayed/lost native
stop response is unknown and cannot authorize closure, retry or reopening.
Journal methods may remain pending while the SDK operation remains pending.

The SQL guards reject ordinary delete, replacement, rebinding, premature return,
settlement rewrite and stop reset, including `INSERT OR REPLACE` when SQLite's
recursive delete triggers are disabled. All three protected tables are `STRICT,
WITHOUT ROWID`: their explicit primary keys are their only row identities. This
prevents hidden-rowid replacement from deleting an obligation under a fresh
invocation/effect key. Duplicate-key insert guards remain necessary because
REPLACE deletion cannot be trusted to fire delete triggers. This uses ADR0051's trusted storage-owning
runtime boundary: broad D1 DDL/restore/erase capability is controlled by custody,
not an invented SQL privilege role. An administrator dropping guards is outside
the ordinary operation boundary and remains subject to the actual embargo.

## Observation substrate

`page(table, after, limit, window)` accepts `invocations` or `effects`, an empty
initial cursor or exact prior UUID, and a page limit in 1..256. Each page uses a
fresh `first-primary` session and one batch for control plus an ordered keyset
page. Generations/revisions travel as TEXT, without JavaScript Number conversion.
Full pages require another page, even if it is empty. No rows are filtered out.

The observer must enforce its own finite total query/row/byte budget, enumerate
both complete tables from the empty cursor, and recheck unchanged control revision
and exact stopped evidence through final readback. Every invocation/effect change
increments that guarded revision. Revision mismatch, missing rows, orphan effects,
unknown/rejected outcomes, missing domain evidence or unsupported schema refuse.
The reader does not return a complete-supported disposition and a short/empty
page, zero count or journal evidence digest cannot establish one. Complete actual
old-callback, restarted-invocation and mandatory domain-result coverage belongs
to the independent observer and later retained-artifact integration.

## Existing seam limitation found by concrete integration

The actual `MainEntryMaintenance` body test awaits `response.text()`, but the
separate durable body-settlement acknowledgment can still be pending when the
handler returns. The existing seam conservatively retains the invocation as
unreturned. This implementation preserves that safe refusal; it does not silently
convert it into returned/drained. A minimal conventional followup is to await the
already-owned body receipt in the body completion methods before reporting their
completion, while retaining independent cancellation holds and rejecting any new
operation after return. That change needs review of the shared seam and its
source-bound candidate before full artifact acceptance. No shared seam changed here.

## Verification and remaining gates

Run the pinned native TypeScript 7.0.2 compiler with this directory's
`tsconfig.json`, then pinned Node 24.22.0:

```text
node --test probes/pmb1-native-journal/journal.test.mjs
uv run --frozen --no-sync python probes/pmb1-native-journal/freeze.py --check
```

Tests execute the actual fixed SQL/guards against synthetic SQLite, including
file-backed restart, lost receipts, body holds, hostile ordinary writes and
independently threaded connection races. Node is used because the tests import
the actual Worker TypeScript and exercise its Promise/stream behavior; worker
threads provide genuinely overlapping synthetic SQL connections. The freeze
script is Python. No fixture is a managed D1 or production resource.

Actual D1 statement/transaction/RETURNING/trigger behavior, schema installation,
exact binding isolation, resource/version inventory, custody, backup/restore,
native old-writer disposition, independent observation and provider-compatible
retained Worker packaging remain unqualified. No credential/provider/account,
resource creation, deployment, capture, cleanup or reopening occurred.

## Native API evidence

Checked against official Cloudflare documentation on 2026-10-23:

- [D1 Database](https://developers.cloudflare.com/d1/worker-api/d1-database/)
  documents the Workers binding, transactional batch rollback, primary behavior
  without sessions and `first-primary` session construction. The fixed SQL uses
  those APIs; this is source rationale, not proof of actual managed behavior.
- [Prepared statement methods](https://developers.cloudflare.com/d1/worker-api/prepared-statements/)
  documents parameter binding and `all()` result objects. No cancellation argument
  or global drain API is supplied by these methods.
- [Retry queries](https://developers.cloudflare.com/d1/best-practices/retry-queries/)
  describes error handling. This backend deliberately provides no application
  retry or new dispatch budget after an unknown result.
- [SQLite WITHOUT ROWID](https://www.sqlite.org/withoutrowid.html) documents that
  these tables omit the hidden rowid and its aliases. The journal does not use
  automatic rowids or last-insert-rowid behavior. [D1 SQL statements](https://developers.cloudflare.com/d1/sql-api/sql-statements/)
  documents general SQLite compatibility; it does not independently qualify this
  exact schema. Actual managed `STRICT, WITHOUT ROWID`, guards and transactional
  behavior still require the existing provider qualification gates.
