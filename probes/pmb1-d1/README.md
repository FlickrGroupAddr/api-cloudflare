# PMB-1 D1 source candidate

Unregistered, synthetic source only. No Worker entry point, binding, Wrangler
configuration, active migration, provider client or action command is supplied.
The [accepted PMB-1 contract](../../docs/operations/prospective-maintenance-contract-decision-2026-10-18.md)
controls this candidate. Production eligibility and actual D1 qualification are
**false**. This candidate does not consume an action grant or private input.

## Fixed artifacts

- `bootstrap.sql`: exact ordinary-rowid singleton `(1, 1, 'closed')` and the
  special runtime INSERT/DELETE/UPDATE guards. No idempotent creation or repair.
- `guards.sql`: persistent, unrestricted BEFORE INSERT/UPDATE/DELETE guards on
  all **62 ordinary tables** in the public migration-derived synthetic schema.
  Each table is quoted and every name is enumerated in `manifest.json`.
- `close.sql` and `reopen.sql`: only the fixed adjacent-generation transition;
  whole-relation count and stored types must be valid. Exact expected generation
  is bound as TEXT and compared to `CAST(generation AS TEXT)`.
- `readback.sql`: all control rows, exact decimal generation, stored types and
  rowid; no filtering or first-row shortcut.
- `schema.sql`: complete ordered `sqlite_schema` readback, including indexes
  and internal definitions. `manifest.json` pins every source/candidate schema
  definition with SHA2-256, plus every public migration's bytes and guard name.
- `control.py`: canonical positive decimal validation, fixed statement/parameter
  shapes, exact affected-row and control/schema readback checks. Python integers
  preserve signed-int64 values above the JavaScript safe-integer ceiling.

`fixture.py` opens only `:memory:` SQLite, applies public migrations and validates
the exact source manifest before an atomic synthetic bootstrap. It checks the
complete candidate definitions and closed row inside that transaction before
commit. No existing guard is removed or replaced. `atomic_fixture_batch` is a
local transaction analogue with explicit rollback on failure. These are test
helpers, not a D1 installation/transaction implementation. Python is used because
the work is SQL validation and finite offline fixtures; no TypeScript runtime
integration is required or invented here.

## Future adapter obligations

No source helper performs a provider mutation. A future independently reviewed
D1 operator adapter must freeze this exact SQL and schema manifest, latch each
intent in the separately owned private journal **before** dispatch, bind canonical
TEXT without converting it through a JavaScript number, and dispatch the one
fixed UPDATE as its own qualified atomic operation. Never batch a transition
with ordinary work. It must require exactly one affected row and separately
obtain authoritative primary readbacks using the complete control/schema query
shapes. A response echo is not readback. Schema pins from this synthetic fixture
must not be substituted for the exact qualified hosted candidate manifest.

Zero changed rows are refusal. Lost acknowledgment, timeout, malformed receipt,
affected-row mismatch or failed readback after dispatch leaves the outcome
unknown. Do not replay a mutation, allocate a new generation, repair, fall back,
or automatically reopen. Only the exact later packet's bounded read-only
reconciliation may resolve uncertainty. A closed maximum generation remains
closed. Reserve headroom before any separately authorized lifecycle.

## What the tests prove

Run from the API repository using its pinned environment:

```text
uv run --frozen python -m unittest discover -s probes/pmb1-d1 -p test_*.py -v
uv run --frozen ruff check probes/pmb1-d1
uv run --frozen ruff format --check probes/pmb1-d1
```

The finite tests exercise the full migration-derived schema plus clearly marked
micro-fixtures. They cover closed bootstrap, rollback of partial DDL, exact
int64/TEXT and exhaustion, malformed/missing/extra/unreadable authority,
INSERT/UPDATE/DELETE/UPSERT/REPLACE/IGNORE, recursive-trigger settings, cascades,
trigger effects, generated values, ABORT versus complete batch rollback,
zero-row non-admission, schema/receipt refusal and existing suppression,
append-only and domain protections while open. The cascade/trigger driver and
TEMP transaction witness are deliberately uncovered fault-injection mechanisms,
not additions to the candidate's complete-table inventory.

The delayed-worker test intentionally demonstrates that closure blocks an old
write, but reopen can make that same old write succeed. Generation is not an
invocation fence. Independently settling all pre-close and temporary-artifact
executions remains a mandatory precondition to reopening; no global provider
drain acknowledgment is invented.

## Qualification limits

Local SQLite behavior does not qualify actual D1 batch rollback, writer ordering,
primary/readback consistency, schema installation atomicity, stop/restart,
restore or the all-store common closed interval. Actual D1 migration/sequence/
bookkeeping and internal/provider state remain unobserved. Supported stability
evidence is required for state ordinary triggers cannot cover; absent evidence
refuses the all-store candidate. Do not install unsupported internal triggers or
exclude those facts from equality. Unknown schema/extra tables refuse this
source fixture; no actual schema discovery has occurred.

No Durable Object closure, admitted external work disposition, custody embargo,
complete REAL reader, retained artifact or production writer census is proved
here. Existing production write gates remain independently paused under their
own authority. All historical exact-original NO-GO and complete typed equality
requirements remain intact. The separate all-store qualification and exact
action decisions still own every hosted/install/capture/restore/cleanup/reopen
authorization.
