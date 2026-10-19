# PMB-1 object-local source candidate

Date: 2026-10-19. Ticket #0186. Status: **Unregistered source candidate;
synthetic local checks and independent High implementation re-review passed.**

This implements the object-local part of the
[accepted PMB-1 source contract](prospective-maintenance-contract-decision-2026-10-18.md#future-artifact-durable-objects-and-other-writers).
The source is [candidate.ts](../../probes/pmb1-object/candidate.ts). It has no
Worker entry point, HTTP routes, Durable Object registration, binding, provider
configuration, active migration or production import. All materialization,
capture, deployment, restoration and reopening readiness remains **false**.
The existing registered Worker and historical retained artifacts are untouched.

## Fixed source behavior

- Explicit isolated bootstrap creates the contract's typed SQL singleton at
  generation `1`, closed, and installs adjacent-generation transition guards
  and unrestricted INSERT/UPDATE/DELETE guards on both candidate ordinary
  tables. Unexpected SQL schema, KV entries or an exposed alarm refuses
  bootstrap. Only the provider's documented hidden `__cf_kv` relation is allowed
  as preexisting schema; its actual content is checked through the KV API.
  Bootstrap is never an ordinary-request or constructor repair path.
- Control generation uses canonical decimal text at the interface, exact
  SQLite INTEGER storage, `CAST(... AS TEXT)` readback and bigint range checks.
  No JavaScript number owns generation. Same-state, duplicate, stale, malformed
  or exhausted transitions refuse. There is no counter reset or timeout unlock.
- Fixed ordinary operations admit an invocation, stop admission, write or
  delete the single synthetic work item, finish or cancel undispatched work,
  mark an external dispatch pending, settle a confirmed external result, and
  process an explicitly identified alarm callback. SQL, transactional KV and
  explicit alarm create/update/delete use the same asynchronous object-local
  `storage.transaction` boundary and recheck durable open generation there.
  No caller supplies SQL, a table/key name, arbitrary callback or storage handle
  to an ordinary operation. The injected storage handle remains trusted code.
- Each invocation has an immutable ID/generation and durable execution state.
  Drain first persists admission off. Already admitted work may finish while
  draining; no new external dispatch marker may be admitted. Close refuses any
  unresolved execution, explicit alarm time or alarm marker. It changes only
  the control singleton after all preceding local work has committed or aborted.
- An external marker must commit before any caller dispatches an external
  effect. This source sends no external request. Confirmed success/failure
  result storage stays allowed during drain; failed result storage rolls back
  and retains `external_pending`. Unknown results have no settlement/cancel
  shortcut and continue blocking close across restart. Domain-specific safety
  result transactions and actual dispatchers must be integrated and qualified
  later; the synthetic work value is not that integration.
- Construction/restart performs no write, admission, alarm rearm or repair.
  Every callback mutation checks both its durable execution state and exact
  current generation. A cancelled, settled, closed or superseded invocation
  cannot regain authority through ordinary callback methods after reopening.
- Reopen has no default proof path. A trusted, separately qualified disposition
  verifier must confirm the exact generation and independent disposition of
  pre-close/temporary executions, old versions, queues and alarm callbacks.
  The transaction then rechecks generation, closed state, empty drain and no
  alarm. Test-provided verifier results are synthetic; they supply no actual
  independent evidence or authorization. External operator journals and bounded
  read-only reconciliation remain required; these methods never replay a failed
  transition or automatically reopen after an uncertain acknowledgment.

## Deliberate qualification gaps

Every non-null alarm write returns an `AlarmDispatch` containing the invocation
identity plus a new exact `alarmGeneration`. A separate durable KV sequence
increments atomically on every arm/replacement, including equal-time replacement
for the same invocation. It never resets on deletion or reopening; malformed,
missing or exhausted sequence state refuses and rolls back the whole operation.
The sequence and marker are included in the KV baseline.

`alarmCallback(dispatch)` requires that complete frozen dispatch identity, verifies it
against the durable alarm marker, and rejects old identity against a replacement
marker. It is **not** a native zero-argument `alarm()` handler. The provider's
native event does not itself carry this application identity; simply reading the
latest marker could let an old retry consume new work. No delivery-provenance
adapter is supplied or qualified here. Actual native alarm integration must
prove the required disposition or refuse the candidate. Automatic delivery,
retry/removal metadata and its closed-interval stability remain unqualified.

`inspect()` is a diagnostic source-local read of the singleton, the two known
ordinary tables, the complete exposed KV listing and exposed alarm time. A
transition response or this same-writer observation is **not independent
readback**, a complete typed SQL/schema reader, or a closed-interval receipt.
Neither this read nor local tests establish actual object enumeration, prior
versions/writers, hidden provider state, complete schema/guard pinning or
independent SQL/KV/alarm equality. Unsupported or unreadable state refuses the
later all-store candidate; nothing here authorizes omitting it.

The implementation targets SQLite-backed Durable Object storage. Its async
transaction choice follows the provider's documented ability to include SQL
operations in `storage.transaction` alongside transactional KV and alarms.
Synchronous transactions cannot include async alarm operations. See the
[official SQLite storage API](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/#transaction)
and [alarm semantics](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/#alarms),
read on 2026-10-19. These documents guide the source, rather than establish
qualified behavior of the exact pinned hosted runtime. Explicit alarm deletion
does not cancel an already executing callback.

There is no common transaction with D1, other objects, secrets, deployment
configuration or provider operations. Actual complete census, effective writer
embargo, supported atomic SQL/KV/alarm behavior, independent complete reader,
old-version/queue disposition and automatic alarm metadata stability remain
#0182 qualification gates under the accepted contract. No private evidence,
credential, provider/account/DNS call, native action, deployment, install,
migration or cleanup occurred for this source work.

## Local validation

Pinned Node **24.22.0** and native TypeScript **7.0.2** were used. The scoped
`probes/pmb1-object/tsconfig.json` extends the repository's canonical strict
compiler options and projects only the candidate include; root `npm run check`
does not include this directory by itself.

Commands from the API repository with that pinned Node on PATH:

```text
node --test probes/pmb1-object/candidate.test.mjs
node node_modules/typescript/bin/tsc -p probes/pmb1-object/tsconfig.json --noEmit
git diff --check -- probes/pmb1-object docs/operations/pmb1-object-source-2026-10-19.md
```

The **23** finite synthetic cases passed, including typed/bootstrap/control
refusals, exact maximum generation, nonzero SQL row guards, SQL/KV/alarm rollback
at five failure points, admission/close concurrency, result settlement failure,
restart persistence, explicit alarm settlement and stale alarm/callback identity
across reopening, same-invocation/equal-time alarm replacement, and alarm-sequence
nonreset/malformed/exhaustion refusals. The local adapter uses in-memory SQLite and a serialized
transaction queue with KV/alarm rollback. It proves the candidate against that
model; it does not qualify workerd, actual distributed scheduling, provider
metadata, native alarms, an independent reader or any deployed object.

The first independent High review identified reuse of an invocation token for
replacement alarms. The source now gives each arm its own durable identity;
the added regressions reject the old callback without consuming replacement
work. Independent re-review of the corrected frozen bytes passed.

Independent High implementation review resolved the material alarm finding. The accepted contract and #0182
remain the authority for actual qualification and separate action decisions.

## Independent review and integration

Corrected source passed fresh independent High re-review: twenty-three author
tests, eleven independent fault cases and the scoped native TypeScript gate.
The reviewer checked durable per-arm identity, concurrent replacements, deletion
and restart, exact counters above JavaScript safe integers, rollback and maximum
exhaustion. The parent reproduced twenty-three installed tests and scoped native
TypeScript 7.0.2 under Node 24.22.0. This is unregistered source evidence only;
native alarm provenance, automatic metadata and all-store qualification remain
unpassed. No action or deployment permission follows.
